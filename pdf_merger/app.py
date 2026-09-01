"""UI 层：构建界面、绑定事件、主线程分发 bus 消息。

布局：预览(顶) → 输入文件/合并设置/页间距 三卡(中) → 日志+导出(底)。
美化：微软雅黑加粗放大、按钮分色、卡片圆角、预览可缩放。
"""
import io
import os
import sys
import datetime

import customtkinter as ctk
from PIL import Image

from config import MergeConfig, validate
from pdf_engine import grid_rc
from bus import Bus
from worker import Worker
from version import VERSION
import persistence

# 字体
FONT = "Microsoft YaHei"          # 微软雅黑
FONT_MONO = "Consolas"            # 日志用清晰等宽字体

# 预览显示区（像素），真实窗口可更大
PREVIEW_W, PREVIEW_H = 560, 380

# 按钮配色（light, dark）
C_ADD = ("#16A34A", "#15803D")      # 添加文件 - 绿
C_DEL = ("#DC2626", "#B91C1C")      # 删除 - 红
C_NEU = ("#6B7280", "#4B5563")      # 移动/清空/缩放 - 灰
C_EXP = ("#2563EB", "#1D4ED8")      # 导出 - 蓝
C_CARD = ("gray95", "gray16")       # 卡片底色
C_BORDER = ("gray80", "gray30")     # 卡片边框

# 拖拽可选支持：导入失败则降级为按钮添加
DND_ENABLED = False
DND_FILES = None
try:  # pragma: no cover - 依赖可选
    from tkinterdnd2 import DND_FILES  # type: ignore
    DND_ENABLED = True
except Exception:
    pass


def _default_dir() -> str:
    """默认目录：打包态指 exe 所在目录，开发态指脚本目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _ori_short(ori: str) -> str:
    """横向→横版，纵向→纵版。"""
    return "横版" if ori == "横向" else "纵版"


class App:
    def __init__(self, root, dnd_enabled: bool = False):
        self.root = root
        self.dnd_enabled = dnd_enabled and DND_ENABLED
        self.bus = Bus()
        self.worker = Worker(self.bus)
        self.files: list[str] = []
        self.sel = -1
        self._deb = None
        self._save_id = None
        self._prev_pil = None        # 预览原图（PIL）
        self._prev_image = None      # 当前 CTkImage
        self._zoom = 1.0             # 预览缩放倍率（1.0=适应区域）

        # 字体实例（root 已存在，可安全创建）
        self.f_title = ctk.CTkFont(family=FONT, size=15, weight="bold")
        self.f_big = ctk.CTkFont(family=FONT, size=16, weight="bold")
        self.f_body = ctk.CTkFont(family=FONT, size=14)
        self.f_body_b = ctk.CTkFont(family=FONT, size=14, weight="bold")
        self.f_meta = ctk.CTkFont(family=FONT, size=13)
        self.f_small = ctk.CTkFont(family=FONT, size=12)
        self.f_log = ctk.CTkFont(family=FONT_MONO, size=12)

        self._build_ui()
        # 记住上次设置：启动载入配置与文件列表
        saved_cfg, saved_files = persistence.load()
        if saved_cfg:
            self._apply_config(saved_cfg)
        if saved_files:
            self.files = saved_files
            self.sel = len(self.files) - 1
            self._log(f"已恢复 {len(self.files)} 个文件")
        self._render_files()
        self._update_meta()
        # 关闭时保存
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.bus.start(root, {
            "log": self._h_log,
            "preview": self._h_preview,
            "done": self._h_done,
            "error": self._h_error,
        })
        self._log("就绪")
        self._trigger_preview()

    # ========== UI 构建 ==========
    def _build_ui(self):
        root = self.root
        root.title(f"PDF 单页合并器 v{VERSION}")
        root.geometry("1040x780")
        root.minsize(920, 700)

        body = ctk.CTkFrame(root, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=14)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)   # 预览可拉伸
        body.grid_rowconfigure(1, weight=0)
        body.grid_rowconfigure(2, weight=0)

        self._build_preview(body)
        self._build_controls(body)
        self._build_bottom(body)

    def _card(self, parent, **kw):
        """统一卡片样式：圆角 + 轻边框。"""
        return ctk.CTkFrame(parent, fg_color=C_CARD, border_width=1,
                            border_color=C_BORDER, corner_radius=14, **kw)

    def _build_preview(self, parent):
        f = self._card(parent)
        f.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(f, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, text="合并预览", font=self.f_big).grid(row=0, column=0, sticky="w")
        self.meta_var = ctk.StringVar(value="4合1 · A4 横向 · 2×2 · 间距 10/10mm")
        ctk.CTkLabel(head, textvariable=self.meta_var, font=self.f_meta).grid(row=0, column=1, sticky="e", padx=10)
        # 缩放按钮
        zb = ctk.CTkFrame(head, fg_color="transparent")
        zb.grid(row=0, column=2, sticky="e")
        ctk.CTkButton(zb, text="－", width=34, height=28, font=self.f_body_b,
                      fg_color=C_NEU, hover_color=C_NEU[1],
                      command=self._zoom_out).pack(side="left", padx=2)
        ctk.CTkButton(zb, text="1:1", width=40, height=28, font=self.f_small,
                      fg_color=C_NEU, hover_color=C_NEU[1],
                      command=self._zoom_reset).pack(side="left", padx=2)
        ctk.CTkButton(zb, text="＋", width=34, height=28, font=self.f_body_b,
                      fg_color=C_NEU, hover_color=C_NEU[1],
                      command=self._zoom_in).pack(side="left", padx=2)

        wrap = ctk.CTkFrame(f, fg_color="transparent")
        wrap.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))
        self.preview_label = ctk.CTkLabel(wrap, text="（无文件）", text_color="gray",
                                          font=self.f_body)
        self.preview_label.pack(expand=True)
        if self.dnd_enabled:
            try:
                wrap.drop_target_register(DND_FILES)
                wrap.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                self.dnd_enabled = False

    def _build_controls(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        f.grid_columnconfigure(0, weight=2)
        f.grid_columnconfigure(1, weight=1)
        f.grid_columnconfigure(2, weight=1)

        # ---- 输入文件（紧凑布局）----
        c1 = self._card(f)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        c1.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(c1, text="输入文件（单页 PDF）", font=self.f_title).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        self.file_box = ctk.CTkScrollableFrame(c1, height=116)
        self.file_box.grid(row=1, column=0, sticky="ew", padx=12)
        # 工具栏：左 4 个小按钮，右 添加文件（同一行，省空间）
        tb = ctk.CTkFrame(c1, fg_color="transparent")
        tb.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 12))
        tb.grid_columnconfigure(4, weight=1)
        for col, (txt, cmd, col_) in enumerate([
            ("↑", lambda: self._move(-1), C_NEU),
            ("↓", lambda: self._move(1), C_NEU),
            ("✕", self._delete, C_DEL),
            ("清空", self._clear, C_NEU),
        ]):
            ctk.CTkButton(tb, text=txt, width=40, height=30, font=self.f_body_b,
                          fg_color=col_, hover_color=col_[1],
                          command=cmd).grid(row=0, column=col, padx=(0, 4))
        add_txt = "＋ 添加文件" + (" / 拖拽" if self.dnd_enabled else "")
        ctk.CTkButton(tb, text=add_txt, height=30, font=self.f_body_b,
                      fg_color=C_ADD, hover_color=C_ADD[1],
                      command=self._add_files).grid(row=0, column=4, sticky="ew", padx=(4, 0))

        # ---- 合并设置（含 DPI）----
        c2 = self._card(f)
        c2.grid(row=0, column=1, sticky="nsew", padx=8)
        ctk.CTkLabel(c2, text="合并设置", font=self.f_title).pack(anchor="w", padx=12, pady=(12, 4))
        self.mode_seg = self._seg_row(c2, "模式", ["2合1", "4合1", "6合1", "8合1"], "4合1", self._on_cfg)
        self.page_seg = self._seg_row(c2, "页面", ["A4", "A3"], "A4", self._on_cfg)
        self.ori_seg = self._seg_row(c2, "方向", ["横向", "纵向"], "横向", self._on_cfg)
        self.dpi_ent = self._entry_row(c2, "DPI", "200", self._on_cfg)

        # ---- 页间距 ----
        c3 = self._card(f)
        c3.grid(row=0, column=2, sticky="nsew")
        ctk.CTkLabel(c3, text="页间距", font=self.f_title).pack(anchor="w", padx=12, pady=(12, 4))
        self.gap_h = self._entry_row(c3, "横向", "10", self._on_cfg, "mm")
        self.gap_v = self._entry_row(c3, "纵向", "10", self._on_cfg, "mm")
        self.margin = self._entry_row(c3, "外边距", "10", self._on_cfg, "mm")

    def _build_bottom(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=2, column=0, sticky="nsew")
        f.grid_columnconfigure(0, weight=2)   # 日志加宽
        f.grid_columnconfigure(1, weight=1)
        f.grid_rowconfigure(0, weight=1)

        # ---- 日志 ----
        lc = self._card(f)
        lc.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        lc.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(lc, text="运行日志", font=self.f_title).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        self.log_box = ctk.CTkTextbox(lc, height=120, font=self.f_log)
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")

        # ---- 导出（格式 + 另存为）----
        ec = self._card(f)
        ec.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(ec, text="导出", font=self.f_title).pack(anchor="w", padx=12, pady=(12, 4))
        self.fmt_seg = self._seg_row(ec, "格式", ["PDF", "JPG", "PNG"], "PDF")
        ctk.CTkButton(ec, text="另存为…", height=34, font=self.f_body_b,
                      fg_color=C_EXP, hover_color=C_EXP[1],
                      command=self._save_as).pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(ec, text=f"v{VERSION}", text_color="gray", font=self.f_small).pack(pady=(0, 12))

    # ---------- 通用行组件 ----------
    def _seg_row(self, parent, label, values, default, command=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row, text=label, width=52, anchor="w", font=self.f_body).pack(side="left")
        seg = ctk.CTkSegmentedButton(row, values=values, command=command, font=self.f_body)
        seg.set(default)
        seg.pack(side="left", expand=True, fill="x", padx=(6, 0))
        return seg

    def _entry_row(self, parent, label, default, command, suffix=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row, text=label, width=52, anchor="w", font=self.f_body).pack(side="left")
        if suffix:
            ctk.CTkLabel(row, text=suffix, font=self.f_body).pack(side="right", padx=(2, 4))
        ent = ctk.CTkEntry(row, width=70, justify="center", font=self.f_body)
        ent.insert(0, default)
        ent.pack(side="right")
        ent.bind("<FocusOut>", lambda e: command())
        ent.bind("<Return>", lambda e: command())
        return ent

    # ========== 预览缩放 ==========
    def _zoom_in(self):
        self._zoom = min(self._zoom * 1.25, 4.0)
        self._apply_preview()

    def _zoom_out(self):
        self._zoom = max(self._zoom / 1.25, 0.25)
        self._apply_preview()

    def _zoom_reset(self):
        self._zoom = 1.0
        self._apply_preview()

    def _apply_preview(self):
        """按当前 _zoom 把 _prev_pil 渲染到预览控件。"""
        if self._prev_pil is None:
            return
        w, h = self._prev_pil.size
        fit = min(PREVIEW_W / w, PREVIEW_H / h)   # 适应区域的基准缩放
        dw = max(1, int(w * fit * self._zoom))
        dh = max(1, int(h * fit * self._zoom))
        self._prev_image = ctk.CTkImage(light_image=self._prev_pil, size=(dw, dh))
        self.preview_label.configure(image=self._prev_image, text="")

    # ========== 配置读取 ==========
    def _mode_int(self) -> int:
        v = self.mode_seg.get()
        return int(v.replace("合1", ""))

    def _num(self, ent, default):
        try:
            return float(ent.get().strip())
        except ValueError:
            return default

    def _cfg(self) -> MergeConfig:
        return MergeConfig(
            mode=self._mode_int(),
            page_size=self.page_seg.get(),
            orientation=self.ori_seg.get(),
            gap_h_mm=self._num(self.gap_h, 10),
            gap_v_mm=self._num(self.gap_v, 10),
            margin_mm=self._num(self.margin, 10),
            export_format=self.fmt_seg.get().lower(),
            dpi=int(self._num(self.dpi_ent, 200)),
        )

    def _update_meta(self):
        cfg = validate(self._cfg())
        rows, cols = grid_rc(cfg)
        self.meta_var.set(
            f"{cfg.mode}合1 · {cfg.page_size} {cfg.orientation} · {rows}×{cols} · "
            f"间距 {cfg.gap_h_mm:.0f}/{cfg.gap_v_mm:.0f}mm"
        )

    def _apply_config(self, cfg: MergeConfig):
        """把保存的配置回填到控件。"""
        self.mode_seg.set(f"{cfg.mode}合1")
        self.page_seg.set(cfg.page_size)
        self.ori_seg.set(cfg.orientation)
        self.fmt_seg.set(cfg.export_format.upper())
        for ent, val in ((self.dpi_ent, cfg.dpi),
                         (self.gap_h, cfg.gap_h_mm),
                         (self.gap_v, cfg.gap_v_mm),
                         (self.margin, cfg.margin_mm)):
            ent.delete(0, "end")
            ent.insert(0, f"{val:g}")

    # ========== 事件：配置变更 → 防抖预览 ==========
    def _on_cfg(self, _=None):
        self._update_meta()
        if self._deb:
            self.root.after_cancel(self._deb)
        self._deb = self.root.after(300, self._trigger_preview)
        # 记住上次设置：防抖保存
        if self._save_id:
            self.root.after_cancel(self._save_id)
        self._save_id = self.root.after(600, self._do_save)

    def _trigger_preview(self):
        self._deb = None
        if self.files:
            self.worker.preview(list(self.files), self._cfg())
        else:
            self._clear_preview()

    def _clear_preview(self):
        self._prev_pil = None
        self._prev_image = None
        self.preview_label.configure(image=None, text="（无文件）", text_color="gray")

    def _do_save(self):
        """防抖落盘：配置变更 600ms 后静默保存。"""
        self._save_id = None
        persistence.save(self._cfg(), self.files)

    def _on_close(self):
        """关闭窗口：保存配置后销毁。"""
        if self._save_id:
            self.root.after_cancel(self._save_id)
        persistence.save(self._cfg(), self.files)
        self.root.destroy()

    # ========== 文件列表 ==========
    def _render_files(self):
        for w in self.file_box.winfo_children():
            w.destroy()
        if not self.files:
            ctk.CTkLabel(self.file_box, text="（无文件）", text_color="gray",
                         font=self.f_body).pack(pady=10)
            return
        for i, p in enumerate(self.files):
            title = f"{i + 1}. {os.path.basename(p)}"
            selected = (i == self.sel)
            btn = ctk.CTkButton(
                self.file_box, text=title, anchor="w", height=28, font=self.f_body,
                fg_color=("gray75", "gray30") if selected else "transparent",
                text_color=("black", "white") if selected else None,
                command=lambda i=i: self._select(i),
            )
            btn.pack(fill="x", pady=2)

    def _select(self, i):
        self.sel = i
        self._render_files()

    def _add_files(self):
        from tkinter import filedialog
        paths = filedialog.askopenfilenames(
            title="选择单页 PDF", initialdir=_default_dir(),
            filetypes=[("PDF 文件", "*.pdf")],
        )
        if not paths:
            return
        for p in paths:
            if p not in self.files:
                self.files.append(p)
        self.sel = len(self.files) - 1
        self._render_files()
        self._log(f"已添加 {len(paths)} 个文件，共 {len(self.files)} 个")
        self._trigger_preview()

    def _on_drop(self, event):
        try:
            paths = self.root.tk.splitlist(event.data)
        except Exception:
            paths = [event.data]
        added = 0
        for p in paths:
            if p.lower().endswith(".pdf") and p not in self.files:
                self.files.append(p)
                added += 1
        if added:
            self.sel = len(self.files) - 1
            self._render_files()
            self._log(f"拖入 {added} 个文件，共 {len(self.files)} 个")
            self._trigger_preview()

    def _move(self, d):
        if self.sel < 0 or not self.files:
            return
        j = self.sel + d
        if j < 0 or j >= len(self.files):
            return
        self.files[self.sel], self.files[j] = self.files[j], self.files[self.sel]
        self.sel = j
        self._render_files()
        self._trigger_preview()

    def _delete(self):
        if 0 <= self.sel < len(self.files):
            name = os.path.basename(self.files[self.sel])
            del self.files[self.sel]
            if self.sel >= len(self.files):
                self.sel = len(self.files) - 1
            self._render_files()
            self._log(f"已删除 {name}")
            self._trigger_preview()

    def _clear(self):
        if not self.files:
            return
        self.files.clear()
        self.sel = -1
        self._render_files()
        self._log("已清空文件列表")
        self._trigger_preview()

    # ========== 导出（另存为）==========
    def _save_as(self):
        if not self.files:
            self._log("请先添加文件", "warn")
            return
        from tkinter import filedialog
        cfg = validate(self._cfg())
        ext = cfg.export_format
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        name = f"{cfg.mode}张合并一张_{cfg.page_size}{_ori_short(cfg.orientation)}_{ts}.{ext}"
        path = filedialog.asksaveasfilename(
            title="导出到", initialdir=_default_dir(), initialfile=name,
            defaultextension=f".{ext}", filetypes=[(ext.upper(), f"*.{ext}")],
        )
        if not path:
            return
        self._log(f"开始导出：{os.path.basename(path)}（{ext.upper()}）")
        self.worker.export(list(self.files), self._cfg(), path)

    # ========== bus handler（主线程）==========
    def _h_log(self, msg, level="info"):
        self._log(msg, level)

    def _h_preview(self, png: bytes):
        try:
            self._prev_pil = Image.open(io.BytesIO(png))
            self._apply_preview()
        except Exception as e:
            self._log(f"预览渲染失败: {e}", "error")

    def _h_done(self, path):
        self._log(f"导出完成: {path}", "ok")

    def _h_error(self, msg):
        self._log(msg, "error")

    # ========== 日志写入 ==========
    def _log(self, msg, level="info"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        tag = {"info": "", "warn": "[!] ", "error": "[X] ", "ok": "[v] "}.get(level, "")
        line = f"[{ts}] {tag}{msg}\n"
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
