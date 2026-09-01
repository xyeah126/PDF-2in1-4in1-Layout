"""UI 层：构建界面、绑定事件、主线程分发 bus 消息。

按 v6 布局：预览(顶) → 输入文件/合并设置/页间距 三卡(中) → 日志+导出(底)。
两项调整：图片 DPI 移入"合并设置"；导出卡只留"格式 + 另存为"。
"""
import io
import os
import sys
import datetime

import customtkinter as ctk
from PIL import Image

from config import MergeConfig, validate, grid_rc
from bus import Bus
from worker import Worker

# 预览显示区上限（像素），真实窗口可更大
PREVIEW_W, PREVIEW_H = 520, 360

# 拖拽可选支持：导入失败则降级为按钮添加
DND_ENABLED = False
DND_FILES = None
try:  # pragma: no cover - 依赖可选
    from tkinterdnd2 import DND_FILES  # type: ignore
    DND_ENABLED = True
except Exception:
    pass


def _default_dir() -> str:
    """默认导出目录：打包态指 exe 所在目录，开发态指脚本目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


class App:
    def __init__(self, root, dnd_enabled: bool = False):
        self.root = root
        self.dnd_enabled = dnd_enabled and DND_ENABLED
        self.bus = Bus()
        self.worker = Worker(self.bus)
        self.files: list[str] = []
        self.sel = -1
        self._deb = None
        self._prev_image = None

        self._build_ui()
        self._render_files()
        self._update_meta()

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
        root.title("PDF 单页合并器")
        root.geometry("980x740")
        root.minsize(820, 620)

        body = ctk.CTkFrame(root, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=12)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)   # 预览可拉伸
        body.grid_rowconfigure(1, weight=0)
        body.grid_rowconfigure(2, weight=0)

        self._build_preview(body)
        self._build_controls(body)
        self._build_bottom(body)

    def _build_preview(self, parent):
        f = ctk.CTkFrame(parent)
        f.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(f, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, text="合并预览",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w")
        self.meta_var = ctk.StringVar(value="4合1 · A4 横向 · 2×2 · 间距 5/5mm")
        ctk.CTkLabel(head, textvariable=self.meta_var,
                     font=ctk.CTkFont(family="Courier", size=12)).grid(row=0, column=1, sticky="e")

        wrap = ctk.CTkFrame(f, fg_color="transparent")
        wrap.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.preview_label = ctk.CTkLabel(wrap, text="（无文件）", text_color="gray")
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

        # ---- 输入文件 ----
        c1 = ctk.CTkFrame(f)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(c1, text="输入文件（单页 PDF）",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(10, 4))
        self.file_box = ctk.CTkScrollableFrame(c1, height=150)
        self.file_box.pack(fill="x", padx=10)
        tb = ctk.CTkFrame(c1, fg_color="transparent")
        tb.pack(fill="x", padx=10, pady=6)
        for txt, cmd in [("↑", lambda: self._move(-1)),
                         ("↓", lambda: self._move(1)),
                         ("✕", self._delete),
                         ("清空", self._clear)]:
            ctk.CTkButton(tb, text=txt, height=26,
                          command=cmd).pack(side="left", expand=True, fill="x", padx=2)
        add_txt = "＋ 添加文件" + (" / 拖拽到此" if self.dnd_enabled else "")
        ctk.CTkButton(c1, text=add_txt, height=26,
                      command=self._add_files).pack(fill="x", padx=10, pady=(0, 10))

        # ---- 合并设置（含 DPI）----
        c2 = ctk.CTkFrame(f)
        c2.grid(row=0, column=1, sticky="nsew", padx=8)
        ctk.CTkLabel(c2, text="合并设置",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(10, 4))
        self.mode_seg = self._seg_row(c2, "模式", ["2合1", "4合1", "6合1", "8合1"], "4合1", self._on_cfg)
        self.page_seg = self._seg_row(c2, "页面", ["A4", "A3"], "A4", self._on_cfg)
        self.ori_seg = self._seg_row(c2, "方向", ["横向", "纵向"], "横向", self._on_cfg)
        self.dpi_ent = self._entry_row(c2, "DPI", "150", self._on_cfg)

        # ---- 页间距 ----
        c3 = ctk.CTkFrame(f)
        c3.grid(row=0, column=2, sticky="nsew")
        ctk.CTkLabel(c3, text="页间距",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(10, 4))
        self.gap_h = self._entry_row(c3, "横向", "5", self._on_cfg, "mm")
        self.gap_v = self._entry_row(c3, "纵向", "5", self._on_cfg, "mm")
        self.margin = self._entry_row(c3, "外边距", "5", self._on_cfg, "mm")

    def _build_bottom(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=2, column=0, sticky="nsew")
        f.grid_columnconfigure(0, weight=2)   # 日志加宽
        f.grid_columnconfigure(1, weight=1)
        f.grid_rowconfigure(0, weight=1)

        # ---- 日志 ----
        lc = ctk.CTkFrame(f)
        lc.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(lc, text="运行日志",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(10, 4))
        self.log_box = ctk.CTkTextbox(lc, height=120,
                                      font=ctk.CTkFont(family="Courier", size=12))
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log_box.configure(state="disabled")

        # ---- 导出（格式 + 另存为）----
        ec = ctk.CTkFrame(f)
        ec.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(ec, text="导出",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(10, 4))
        self.fmt_seg = self._seg_row(ec, "格式", ["PDF", "JPG", "PNG"], "PDF")
        ctk.CTkButton(ec, text="另存为…", height=30,
                      command=self._save_as).pack(fill="x", padx=10, pady=(10, 10))

    # ---------- 通用行组件 ----------
    def _seg_row(self, parent, label, values, default, command=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(row, text=label, width=46, anchor="w").pack(side="left")
        seg = ctk.CTkSegmentedButton(row, values=values, command=command)
        seg.set(default)
        seg.pack(side="left", expand=True, fill="x", padx=(4, 0))
        return seg

    def _entry_row(self, parent, label, default, command, suffix=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(row, text=label, width=46, anchor="w").pack(side="left")
        if suffix:
            ctk.CTkLabel(row, text=suffix).pack(side="right", padx=(2, 4))
        ent = ctk.CTkEntry(row, width=56, justify="center")
        ent.insert(0, default)
        ent.pack(side="right")
        ent.bind("<FocusOut>", lambda e: command())
        ent.bind("<Return>", lambda e: command())
        return ent

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
            gap_h_mm=self._num(self.gap_h, 5),
            gap_v_mm=self._num(self.gap_v, 5),
            margin_mm=self._num(self.margin, 5),
            export_format=self.fmt_seg.get().lower(),
            dpi=int(self._num(self.dpi_ent, 150)),
        )

    def _update_meta(self):
        cfg = validate(self._cfg())
        rows, cols = grid_rc(cfg)
        self.meta_var.set(
            f"{cfg.mode}合1 · {cfg.page_size} {cfg.orientation} · {rows}×{cols} · "
            f"间距 {cfg.gap_h_mm:.0f}/{cfg.gap_v_mm:.0f}mm"
        )

    # ========== 事件：配置变更 → 防抖预览 ==========
    def _on_cfg(self, _=None):
        self._update_meta()
        if self._deb:
            self.root.after_cancel(self._deb)
        self._deb = self.root.after(300, self._trigger_preview)

    def _trigger_preview(self):
        self._deb = None
        if self.files:
            self.worker.preview(list(self.files), self._cfg())
        else:
            self._clear_preview()

    def _clear_preview(self):
        self.preview_label.configure(image=None, text="（无文件）", text_color="gray")
        self._prev_image = None

    # ========== 文件列表 ==========
    def _render_files(self):
        for w in self.file_box.winfo_children():
            w.destroy()
        if not self.files:
            ctk.CTkLabel(self.file_box, text="（无文件）", text_color="gray").pack(pady=10)
            return
        for i, p in enumerate(self.files):
            title = f"{i + 1}. {os.path.basename(p)}"
            selected = (i == self.sel)
            btn = ctk.CTkButton(
                self.file_box, text=title, anchor="w", height=24,
                fg_color=("gray75", "gray25") if selected else "transparent",
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
            title="选择单页 PDF", filetypes=[("PDF 文件", "*.pdf")]
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
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"merged_{cfg.mode}in1_{cfg.page_size}{cfg.orientation[0]}_{ts}.{ext}"
        path = filedialog.asksaveasfilename(
            title="导出到", initialdir=_default_dir(), initialfile=name,
            defaultextension=f".{ext}", filetypes=[(ext.upper(), f"*.{ext}")],
        )
        if not path:
            return
        self.worker.export(list(self.files), self._cfg(), path)

    # ========== bus handler（主线程）==========
    def _h_log(self, msg, level="info"):
        self._log(msg, level)

    def _h_preview(self, png: bytes):
        try:
            img = Image.open(io.BytesIO(png))
            w, h = img.size
            scale = min(PREVIEW_W / w, PREVIEW_H / h, 1.0)
            dw, dh = max(int(w * scale), 1), max(int(h * scale), 1)
            self._prev_image = ctk.CTkImage(light_image=img, size=(dw, dh))
            self.preview_label.configure(image=self._prev_image, text="")
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
