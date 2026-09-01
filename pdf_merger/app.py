"""UI 层：构建界面、绑定事件、主线程分发 bus 消息。

v7 特性：
- 预览图 Canvas 化：支持缩放 + 手型拖动（pan）
- 所有卡片圆角+统一间距；tk.PanedWindow 可在预览/中部/底部间拖动分隔
- SegmentedButton 未选中态使用淡色底（非灰）
- 文件列表淡蓝背景 + 黑色常亮文字
- 5 个操作按钮分色等宽
- 预览图像在主线程严格解绑/重建，避免 pyimage doesn't exist 崩溃
"""
import io
import os
import sys
import datetime

import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk

from config import MergeConfig, validate
from pdf_engine import grid_rc
from bus import Bus
from worker import Worker
from version import VERSION
import persistence

# ===== 字体：全局统一黑体 =====
FONT = "SimHei"                    # 黑体（中文清晰、统一）
FONT_MONO = "SimHei"               # 日志同样用黑体，避免中文回退英文体

# ===== 预览区（像素），真实窗口可更大 =====
PREVIEW_W, PREVIEW_H = 580, 400

# ===== 配色 =====
# 按钮（主色, hover）
C_UP    = ("#8B5CF6", "#7C3AED")    # 上移 - 紫
C_DN    = ("#06B6D4", "#0891B2")    # 下移 - 青
C_ADD   = ("#16A34A", "#15803D")    # 添加文件 - 绿
C_DEL   = ("#DC2626", "#B91C1C")    # 删除 - 红
C_CLR   = ("#F97316", "#EA580C")    # 清空 - 橙
C_ZOO   = ("#6366F1", "#4F46E5")    # 缩放出 - 靛
C_ZIN   = ("#EC4899", "#DB2777")    # 缩放入 - 粉
C_ONE   = ("#F59E0B", "#D97706")    # 1:1 - 琥珀
C_EXP   = ("#2563EB", "#1D4ED8")    # 导出 - 蓝

# 卡片
C_CARD      = ("#FFFFFF", "#1F2937")   # 卡片底色（白底 更清爽）
C_BORDER    = ("#CBD5E1", "#475569")   # 卡片边框
C_HEAD      = ("#F8FAFC", "#1F2937")   # 卡头

# 文件卡淡蓝底
C_LIST_BG   = ("#EFF6FF", "#1E3A5F")   # 文件列表淡蓝底

# SegmentedButton 未选中态（非灰 用淡色体系）
C_SEG_UNSEL = ("#E0F2FE", "#1E3A5F")   # 淡青底
C_SEG_SEL   = ("#2563EB", "#1D4ED8")   # 选中品牌蓝
C_SEG_TXT_U = ("#0C4A6E", "#A5F3FC")   # 未选中文字（深色可读）
C_SEG_TXT_S = ("#FFFFFF", "#FFFFFF")   # 选中文字

# 拖拽可选支持：导入失败则降级为按钮添加
DND_ENABLED = False
DND_FILES = None
try:  # pragma: no cover - 依赖可选
    from tkinterdnd2 import DND_FILES  # type: ignore
    DND_ENABLED = True
except Exception:
    pass


def _apply_global_font(root):
    """全局字体兜底：tk 命名字体 + customtkinter 主题默认字体，统一黑体加粗。

    所有自定义控件虽已显式传入 SimHei bold，这里再兜底一次，
    防止 SegmentedButton/Scrollbar/弹窗等内部元素回退 Roboto 细体（中文发虚）。
    """
    import tkinter.font as tkfont
    for name in ("TkDefaultFont", "TkTextFont", "TkFixedFont", "TkMenuFont",
                 "TkHeadingFont", "TkCaptionFont", "TkSmallCaptionFont",
                 "TkIconFont", "TkTooltipFont"):
        try:
            f = tkfont.nametofont(name)
            f.configure(family=FONT, weight="bold")
        except Exception:
            pass
    # customtkinter 无参 CTkFont() 读取的主题字体（family/weight 都要覆盖）
    try:
        ct = ctk.ThemeManager.theme.setdefault("CTkFont", {})
        ct["family"] = FONT
        ct["weight"] = "bold"
    except Exception:
        pass


def _default_dir() -> str:
    """默认目录：打包态指 exe 所在目录，开发态指脚本目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _ori_short(ori: str) -> str:
    return "横版" if ori == "横向" else "纵版"


class App:
    def __init__(self, root, dnd_enabled: bool = False):
        self.root = root
        _apply_global_font(root)   # 全局字体兜底：统一黑体
        self.dnd_enabled = dnd_enabled and DND_ENABLED
        self.bus = Bus()
        self.worker = Worker(self.bus)
        self.files: list[str] = []
        self.sel = -1
        self._deb = None
        self._save_id = None

        # 预览图相关
        self._prev_pil = None        # 原 PIL 图
        self._prev_scaled = None     # 缩放后 PIL 图（用于 Tk.PhotoImage）
        self._prev_tk = None         # tk.PhotoImage，强引用防 GC
        self._zoom = 1.0             # 1.0=刚好适应
        self._pan_x = 0
        self._pan_y = 0
        self._drag_active = False
        self._drag_sx = 0
        self._drag_sy = 0
        self._drag_s_px = 0
        self._drag_s_py = 0

        # 字体：全部黑体加粗（SimHei bold），中文清晰不发虚
        self.f_title  = ctk.CTkFont(family=FONT, size=15, weight="bold")
        self.f_big    = ctk.CTkFont(family=FONT, size=16, weight="bold")
        self.f_body   = ctk.CTkFont(family=FONT, size=14, weight="bold")
        self.f_body_b = ctk.CTkFont(family=FONT, size=14, weight="bold")
        self.f_meta   = ctk.CTkFont(family=FONT, size=13, weight="bold")
        self.f_small  = ctk.CTkFont(family=FONT, size=12, weight="bold")
        self.f_log    = ctk.CTkFont(family=FONT_MONO, size=12, weight="bold")
        self.f_list   = ctk.CTkFont(family=FONT, size=13, weight="bold")

        self._build_ui()
        # 记住上次设置
        saved_cfg, saved_files = persistence.load()
        if saved_cfg:
            self._apply_config(saved_cfg)
        if saved_files:
            self.files = saved_files
            self.sel = len(self.files) - 1
            self._log(f"已恢复 {len(self.files)} 个文件")
        self._render_files()
        self._update_meta()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.bus.start(root, {
            "log":      self._h_log,
            "preview":  self._h_preview,
            "done":     self._h_done,
            "error":    self._h_error,
        })
        self._log("就绪")
        self._trigger_preview()

    # ================= UI 构建 =================
    def _build_ui(self):
        root = self.root
        root.title(f"PDF 单页合并器 v{VERSION}")
        root.geometry("1240x940")
        root.minsize(1120, 840)

        # 主体：tk.PanedWindow（可拖拽分隔条，悬停双箭头）
        self.pan = tk.PanedWindow(root, orient="vertical", sashwidth=6,
                                  sashrelief="flat", bg="#E2E8F0",
                                  handlesize=10, opaqueresize=False)
        self.pan.pack(fill="both", expand=True, padx=10, pady=10)

        # Pane 1：预览
        p1 = ctk.CTkFrame(self.pan, fg_color="transparent")
        self.pan.add(p1, minsize=300)
        self._build_preview(p1)

        # Pane 2：中部三卡
        p2 = ctk.CTkFrame(self.pan, fg_color="transparent")
        self.pan.add(p2, minsize=170)
        self._build_controls(p2)

        # Pane 3：底部日志 + 导出（minsize 留小，允许 16% 比例）
        p3 = ctk.CTkFrame(self.pan, fg_color="transparent")
        self.pan.add(p3, minsize=120)
        self._build_bottom(p3)

        # 首次布局后把分隔条定位到 57%/27%/16%（预览/中部三卡/日志+导出）
        # 之后用户可自行拖拽；连设两次防止布局未稳定时失效
        root.after(300, self._set_sashes)
        root.after(900, self._set_sashes)

    def _set_sashes(self):
        """定位分隔条到 57%/27%/16%。

        注意 tkinter 方法名随版本不同：
        Py3.14+ 为 sash_place(index,x,y)，旧版为 sashpos(index,y)。
        之前调用不存在的 sashpos 会抛 AttributeError 被吞掉，导致三栏均分。
        """
        try:
            total = self.pan.winfo_height()
            if total <= 100:
                return
            y0, y1 = int(total * 0.57), int(total * 0.84)  # 预览 57%，中部 27%，底部 16%
            if hasattr(self.pan, "sash_place"):          # 垂直方向：x=0，y 定位
                self.pan.sash_place(0, 0, y0)
                self.pan.sash_place(1, 0, y1)
            else:
                self.pan.sashpos(0, y0)
                self.pan.sashpos(1, y1)
        except Exception:
            pass

    def _card(self, parent, **kw):
        """统一卡片：白底 + 14 圆角 + 轻边。"""
        return ctk.CTkFrame(parent, fg_color=C_CARD, border_width=1,
                            border_color=C_BORDER, corner_radius=14, **kw)

    # ----- 预览（Canvas 支持拖动） -----
    def _build_preview(self, parent):
        f = self._card(parent)
        f.pack(fill="both", expand=True)
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)

        # 头：标题 + 元信息 + 缩放三键（分色）
        head = ctk.CTkFrame(f, fg_color=C_HEAD, corner_radius=12)
        head.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, text="合并预览", font=self.f_big).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        self.meta_var = ctk.StringVar(value="4合1 · A4 横向 · 2×2 · 间距 10/10mm")
        ctk.CTkLabel(head, textvariable=self.meta_var, font=self.f_meta).grid(row=0, column=1, padx=8, sticky="e")

        zb = ctk.CTkFrame(head, fg_color="transparent")
        zb.grid(row=0, column=2, padx=8, pady=8, sticky="e")
        ctk.CTkButton(zb, text="－", width=36, height=30, font=self.f_body_b,
                      fg_color=C_ZOO, hover_color=C_ZOO[1],
                      command=self._zoom_out).pack(side="left", padx=2)
        ctk.CTkButton(zb, text="1:1", width=46, height=30, font=self.f_small,
                      fg_color=C_ONE, hover_color=C_ONE[1],
                      command=self._zoom_reset).pack(side="left", padx=2)
        ctk.CTkButton(zb, text="＋", width=36, height=30, font=self.f_body_b,
                      fg_color=C_ZIN, hover_color=C_ZIN[1],
                      command=self._zoom_in).pack(side="left", padx=2)

        # 预览 Canvas（手型 + 拖动）
        cv_w = ctk.CTkFrame(f, fg_color="transparent")
        cv_w.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.prev_canvas = tk.Canvas(cv_w, bg="#F1F5F9", highlightthickness=0,
                                     cursor="hand2")
        self.prev_canvas.pack(fill="both", expand=True)
        self.prev_canvas.bind("<ButtonPress-1>", self._pan_start)
        self.prev_canvas.bind("<B1-Motion>", self._pan_drag)
        self.prev_canvas.bind("<ButtonRelease-1>", self._pan_end)
        self.prev_canvas.bind("<Configure>", lambda e: self._apply_preview())
        # 滚轮缩放：Windows/macOS 为 <MouseWheel>（delta±120），Linux 为 Button-4/5
        self.prev_canvas.bind("<MouseWheel>", self._on_wheel)
        self.prev_canvas.bind("<Button-4>", lambda e: self._wheel_zoom(1))
        self.prev_canvas.bind("<Button-5>", lambda e: self._wheel_zoom(-1))
        if self.dnd_enabled:
            try:
                self.prev_canvas.drop_target_register(DND_FILES)
                self.prev_canvas.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                self.dnd_enabled = False
        # 占位文字
        self.prev_canvas.create_text(0, 0, text="（无文件）", tags="__placeholder__",
                                     fill="#94A3B8", font=(FONT, 14, "bold"))

    # ----- 中部：输入文件 / 合并设置 / 页间距 -----
    def _build_controls(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True)
        f.grid_columnconfigure(0, weight=2)
        f.grid_columnconfigure(1, weight=1)
        f.grid_columnconfigure(2, weight=1)
        f.grid_rowconfigure(0, weight=1)

        # 输入文件卡：左右布局 —— 左列表（淡蓝底），右侧竖排 5 个分色按钮
        c1 = self._card(f)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        c1.grid_columnconfigure(0, weight=1)   # 列表列吃满宽度
        c1.grid_rowconfigure(1, weight=1)      # 列表行吃满高度
        ctk.CTkLabel(c1, text="输入文件（单页 PDF）", font=self.f_title).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 6))

        # 列表：淡蓝底
        self.file_box = ctk.CTkScrollableFrame(c1, height=120, fg_color=C_LIST_BG)
        self.file_box.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 12))

        # 右侧竖排按钮列
        tb = ctk.CTkFrame(c1, fg_color="transparent")
        tb.grid(row=1, column=1, sticky="ns", padx=(0, 12), pady=(0, 12))
        btns = [
            ("↑ 上移",   lambda: self._move(-1), C_UP),
            ("↓ 下移",   lambda: self._move(1),  C_DN),
            ("✕ 删除",   self._delete,           C_DEL),
            ("清空列表", self._clear,            C_CLR),
            ("＋ 添加",  self._add_files,        C_ADD),
        ]
        for i, (txt, cmd, col_) in enumerate(btns):
            ctk.CTkButton(tb, text=txt, width=92, height=30, font=self.f_body_b,
                          fg_color=col_, hover_color=col_[1],
                          command=cmd).pack(fill="x", pady=3)

        # 合并设置
        c2 = self._card(f)
        c2.grid(row=0, column=1, sticky="nsew", padx=6)
        ctk.CTkLabel(c2, text="合并设置", font=self.f_title).pack(anchor="w", padx=12, pady=(12, 6))
        self.mode_seg = self._seg_row(c2, "模式",   ["2合1", "4合1", "6合1", "8合1"], "4合1", self._on_cfg)
        self.page_seg = self._seg_row(c2, "页面",   ["A4", "A3"],                 "A4",   self._on_cfg)
        self.ori_seg  = self._seg_row(c2, "方向",   ["横向", "纵向"],             "横向", self._on_cfg)
        self.dpi_ent  = self._entry_row(c2, "DPI 设置", "300", self._on_cfg)

        # 页间距
        c3 = self._card(f)
        c3.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(c3, text="页间距", font=self.f_title).pack(anchor="w", padx=12, pady=(12, 6))
        self.gap_h  = self._entry_row(c3, "横向",   "10", self._on_cfg, "mm")
        self.gap_v  = self._entry_row(c3, "纵向",   "10", self._on_cfg, "mm")
        self.margin = self._entry_row(c3, "外边距", "10", self._on_cfg, "mm")

    # ----- 底部：日志 + 导出 -----
    def _build_bottom(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True)
        f.grid_columnconfigure(0, weight=3)   # 日志占 75% 宽
        f.grid_columnconfigure(1, weight=2)
        f.grid_rowconfigure(0, weight=1)

        # 日志
        lc = self._card(f)
        lc.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        lc.grid_rowconfigure(1, weight=1)
        lc.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(lc, text="运行日志", font=self.f_title).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        self.log_box = ctk.CTkTextbox(lc, height=120, font=self.f_log, wrap="word")
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")

        # 导出
        ec = self._card(f)
        ec.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(ec, text="导出", font=self.f_title).pack(anchor="w", padx=12, pady=(12, 6))
        self.fmt_seg = self._seg_row(ec, "格式", ["PDF", "JPG", "PNG"], "PDF")
        # 另存为：靠右对齐
        ctk.CTkButton(ec, text="另存为…", width=130, height=34, font=self.f_body_b,
                      fg_color=C_EXP, hover_color=C_EXP[1],
                      command=self._save_as).pack(anchor="e", padx=12, pady=(12, 4))
        ctk.CTkLabel(ec, text=f"v{VERSION}", text_color="gray", font=self.f_small).pack(
            anchor="e", padx=12, pady=(0, 12))

    # ---------- 通用行组件 ----------
    def _seg_row(self, parent, label, values, default, command=None):
        """SegmentedButton：未选中态淡色底（非灰）。"""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(row, text=label, width=66, anchor="w", font=self.f_body).pack(side="left")
        seg = ctk.CTkSegmentedButton(
            row, values=values, command=command, font=self.f_body_b,
            fg_color=C_SEG_UNSEL,
            selected_color=C_SEG_SEL,
            selected_hover_color=C_SEG_SEL[1],
            unselected_color=C_SEG_UNSEL,
            unselected_hover_color=C_SEG_UNSEL,
            text_color=C_SEG_TXT_U,
            dynamic_resizing=True, height=30, corner_radius=10,
        )
        seg.set(default)
        seg.pack(side="left", expand=True, fill="x", padx=(6, 0))
        return seg

    def _entry_row(self, parent, label, default, command, suffix=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(row, text=label, width=66, anchor="w", font=self.f_body).pack(side="left")
        if suffix:
            ctk.CTkLabel(row, text=suffix, font=self.f_body).pack(side="right", padx=(2, 4))
        ent = ctk.CTkEntry(row, width=80, justify="center", font=self.f_body_b, height=30)
        ent.insert(0, default)
        ent.pack(side="right")
        ent.bind("<FocusOut>", lambda e: command())
        ent.bind("<Return>", lambda e: command())
        return ent

    # ================= 预览：缩放 & 拖动 =================
    def _on_wheel(self, event):
        """鼠标滚轮：上滚放大、下滚缩小（Windows/macOS）。"""
        self._wheel_zoom(1 if event.delta > 0 else -1)

    def _wheel_zoom(self, direction: int):
        if self._prev_pil is None:
            return
        factor = 1.15 if direction > 0 else 1 / 1.15
        self._zoom = max(0.25, min(self._zoom * factor, 6.0))
        self._apply_preview()

    def _zoom_in(self):
        self._zoom = min(self._zoom * 1.25, 6.0)
        self._apply_preview()

    def _zoom_out(self):
        self._zoom = max(self._zoom / 1.25, 0.25)
        self._apply_preview()

    def _zoom_reset(self):
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._apply_preview()

    def _pan_start(self, event):
        self._drag_active = True
        self._drag_sx = event.x
        self._drag_sy = event.y
        self._drag_s_px = self._pan_x
        self._drag_s_py = self._pan_y
        self.prev_canvas.configure(cursor="fleur")

    def _pan_drag(self, event):
        if not self._drag_active or self._prev_scaled is None:
            return
        self._pan_x = self._drag_s_px + (event.x - self._drag_sx)
        self._pan_y = self._drag_s_py + (event.y - self._drag_sy)
        self._draw_image()

    def _pan_end(self, event):
        self._drag_active = False
        self.prev_canvas.configure(cursor="hand2")

    def _apply_preview(self):
        """根据 self._zoom 重建 self._prev_scaled，并绘制。"""
        if self._prev_pil is None:
            return
        pw = self.prev_canvas.winfo_width() or PREVIEW_W
        ph = self.prev_canvas.winfo_height() or PREVIEW_H
        w, h = self._prev_pil.size
        fit = min(pw / w, ph / h, 1.0) if pw and ph else 1.0
        nw = max(1, int(w * fit * self._zoom))
        nh = max(1, int(h * fit * self._zoom))
        self._prev_scaled = self._prev_pil.resize((nw, nh), Image.LANCZOS)
        self._draw_image()

    def _draw_image(self):
        """在 Canvas 中心 + pan offset 处画图像；严格解绑旧 tk.PhotoImage 防 pyimage。"""
        if self._prev_scaled is None:
            return
        cv = self.prev_canvas
        # 1) 先清空 Canvas 上的旧图像/占位
        cv.delete("all")
        # 2) 销毁旧 PhotoImage（关键：让 Tk 注销 pyimageX）
        if self._prev_tk is not None:
            try:
                self._prev_tk.__del__()
            except Exception:
                pass
            self._prev_tk = None
        # 3) 构建新的 PhotoImage
        self._prev_tk = ImageTk.PhotoImage(self._prev_scaled)
        pw = cv.winfo_width()
        ph = cv.winfo_height()
        iw = self._prev_scaled.width
        ih = self._prev_scaled.height
        cx = pw / 2 + self._pan_x
        cy = ph / 2 + self._pan_y
        cv.create_image(int(cx), int(cy), image=self._prev_tk, anchor="center")

    def _draw_placeholder(self, text="（无文件）"):
        cv = self.prev_canvas
        cv.delete("all")
        self._prev_tk = None
        pw = cv.winfo_width() or 100
        ph = cv.winfo_height() or 100
        cv.create_text(int(pw / 2), int(ph / 2), text=text,
                       fill="#94A3B8", font=(FONT, 14, "bold"))

    # ================= 配置读取 =================
    def _mode_int(self) -> int:
        return int(self.mode_seg.get().replace("合1", ""))

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
            dpi=int(self._num(self.dpi_ent, 300)),
        )

    def _update_meta(self):
        cfg = validate(self._cfg())
        rows, cols = grid_rc(cfg)
        cap = rows * cols
        n = len(self.files)
        pages = max(1, (n + cap - 1) // cap) if n else 0
        page_txt = f" · 共 {pages} 页" if pages > 1 else ""
        self.meta_var.set(
            f"{cfg.mode}合1 · {cfg.page_size} {cfg.orientation} · {rows}×{cols} · "
            f"间距 {cfg.gap_h_mm:.0f}/{cfg.gap_v_mm:.0f}mm · {n} 个文件{page_txt}"
        )

    def _apply_config(self, cfg: MergeConfig):
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

    # ================= 事件 =================
    def _on_cfg(self, _=None):
        self._update_meta()
        if self._deb:
            self.root.after_cancel(self._deb)
        self._deb = self.root.after(300, self._trigger_preview)
        if self._save_id:
            self.root.after_cancel(self._save_id)
        self._save_id = self.root.after(600, self._do_save)

    def _trigger_preview(self):
        self._deb = None
        if self.files:
            self._log("渲染预览…")
            self.worker.preview(list(self.files), self._cfg())
        else:
            self._clear_preview()

    def _clear_preview(self):
        self._prev_pil = None
        self._prev_scaled = None
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self.root.after(1, self._draw_placeholder)

    def _do_save(self):
        self._save_id = None
        persistence.save(self._cfg(), self.files)

    def _on_close(self):
        if self._save_id:
            self.root.after_cancel(self._save_id)
        persistence.save(self._cfg(), self.files)
        self.root.destroy()

    # ================= 文件列表 =================
    def _update_list_scrollbar(self):
        """文件 ≤5 个时隐藏右侧滚动条（内容本就不需要滚动），更多时恢复。"""
        sb = getattr(self.file_box, "_scrollbar", None)
        if sb is None:
            return
        try:
            if len(self.files) <= 5:
                sb.grid_remove()
            elif not sb.winfo_ismapped():
                # 恢复 CTkScrollableFrame 内部垂直滚动条的原始 grid 位
                sb.grid(row=1, column=1, sticky="nsew", padx=3, pady=3)
        except Exception:
            pass

    def _render_files(self):
        for w in self.file_box.winfo_children():
            w.destroy()
        if not self.files:
            ctk.CTkLabel(self.file_box, text="（无文件）", text_color=("black", "black"),
                         font=self.f_body).pack(pady=8)
        else:
            for i, p in enumerate(self.files):
                title = f"{i + 1}. {os.path.basename(p)}"
                selected = (i == self.sel)
                bg = ("#BFDBFE", "#2563EB") if selected else "transparent"
                tc = "black"  # 列表文字常亮黑
                btn = ctk.CTkButton(
                    self.file_box, text=title, anchor="w", height=28,
                    font=self.f_list,
                    fg_color=bg,
                    text_color=(tc, tc),
                    hover_color=("#DBEAFE", "#1D4ED8"),
                    command=lambda i=i: self._select(i),
                )
                btn.pack(fill="x", pady=2)
        self._update_list_scrollbar()
        self._update_meta()

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

    # ================= 导出 =================
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

    # ================= bus handler（严格主线程）=================
    def _h_log(self, msg, level="info"):
        self._log(msg, level)

    def _h_preview(self, png: bytes):
        """主线程：从 bytes → PIL，严格主线程创建/重建 tk.Image。"""
        try:
            new_pil = Image.open(io.BytesIO(png))
            # 确保 RGBA→RGB（若 alpha），CTk/Tk 都能正确显示
            if new_pil.mode not in ("RGB", "L"):
                new_pil = new_pil.convert("RGB")
            self._prev_pil = new_pil
            # 重置 pan 但保留 zoom
            self._pan_x = 0
            self._pan_y = 0
            self._apply_preview()
        except Exception as e:
            # 闭环：打出错误 + 栈片段，便于下次排查
            import traceback
            tb = traceback.format_exc(limit=4)
            self._log(f"预览渲染失败: {e}\n{tb}", "error")

    def _h_done(self, paths):
        if isinstance(paths, (list, tuple)):
            if len(paths) == 1:
                self._log(f"导出完成: {paths[0]}", "ok")
            else:
                self._log(f"导出完成：共 {len(paths)} 个文件 → {os.path.dirname(paths[0])}", "ok")
                for p in paths:
                    self._log(f"  · {os.path.basename(p)}", "ok")
        else:
            self._log(f"导出完成: {paths}", "ok")

    def _h_error(self, msg):
        self._log(msg, "error")

    # ================= 日志 =================
    def _log(self, msg, level="info"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        tag = {"info": "", "warn": "[!] ", "error": "[X] ", "ok": "[v] "}.get(level, "")
        line = f"[{ts}] {tag}{msg}\n"
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
