"""PyMuPDF 封装：合并 / 预览 / 导出。

纯计算层：不 import 任何 UI 库，仅依赖 PyMuPDF（预览拼图用 Pillow）。
"""
import io
import os

import pymupdf as fitz  # PyMuPDF（fitz 别名前向兼容，避免旧 import 警告）
from PIL import Image

from config import MergeConfig, PAGE_PT, GRID, MM2PT


def page_size_pt(cfg: MergeConfig) -> tuple[float, float]:
    """输出页尺寸(pt)：纵向基准，横向时交换宽高。"""
    w, h = PAGE_PT[cfg.page_size]
    return (h, w) if cfg.orientation == "横向" else (w, h)


def grid_rc(cfg: MergeConfig) -> tuple[int, int]:
    """(rows, cols)。"""
    return GRID[cfg.mode][cfg.orientation]


def cell_rect(i: int, cfg: MergeConfig, pw: float, ph: float) -> fitz.Rect:
    """第 i 个源页的网格单元(pt)。"""
    rows, cols = grid_rc(cfg)
    r, c = divmod(i, cols)
    gh = cfg.gap_h_mm * MM2PT
    gv = cfg.gap_v_mm * MM2PT
    m = cfg.margin_mm * MM2PT
    cw = (pw - 2 * m - (cols - 1) * gh) / cols
    ch = (ph - 2 * m - (rows - 1) * gv) / rows
    x0 = m + c * (cw + gh)
    y0 = m + r * (ch + gv)
    return fitz.Rect(x0, y0, x0 + cw, y0 + ch)


def _fit(src_rect: fitz.Rect, cell: fitz.Rect) -> fitz.Rect:
    """源页等比缩放进 cell 并居中，保持比例不变形。"""
    if src_rect.width <= 0 or src_rect.height <= 0:
        return cell
    s = min(cell.width / src_rect.width, cell.height / src_rect.height)
    dw, dh = src_rect.width * s, src_rect.height * s
    dx = cell.x0 + (cell.width - dw) / 2
    dy = cell.y0 + (cell.height - dh) / 2
    return fitz.Rect(dx, dy, dx + dw, dy + dh)


def build_merged(file_paths, cfg: MergeConfig, log=None):
    """合并多份单页 PDF。

    每页容量 cap = rows*cols（2合1=2、4合1=4…）；文件数超过 cap 时
    自动新增输出页，直到全部排完。例如 3 个文件 + 2合1 → 2 页：
    第1页排文件1/2，第2页按同样缩小格式排文件3（占第1个槽位）。
    矢量保真。log: 可选回调 log(msg, level)。
    """
    pw, ph = page_size_pt(cfg)
    rows, cols = grid_rc(cfg)
    cap = rows * cols
    out = fitz.open()
    page = None
    placed = 0          # 已成功放置的源页数（决定槽位与翻页）
    failed = 0

    for p in file_paths:
        try:
            src = fitz.open(p)
        except Exception as e:
            failed += 1
            if log:
                log(f"打开失败 {os.path.basename(p)}: {e}", "error")
            continue
        try:
            if src.page_count == 0:
                if log:
                    log(f"{os.path.basename(p)} 无页面，跳过", "warn")
                continue
            if src.page_count > 1 and log:
                log(f"{os.path.basename(p)} 多页，取第1页", "warn")
            slot = placed % cap
            if slot == 0:                      # 当前页排满 → 新开一页
                page = out.new_page(width=pw, height=ph)
            src_page = src[0]
            cell = cell_rect(slot, cfg, pw, ph)
            page.show_pdf_page(_fit(src_page.rect, cell), src, 0)
            placed += 1
        finally:
            src.close()

    if placed == 0:                 # 无有效文件：留一张空白页，保证预览/导出不崩
        out.new_page(width=pw, height=ph)

    n_pages = out.page_count
    if log:
        if n_pages > 1:
            log(f"共 {placed} 个文件，按 {cap}合1 排成 {n_pages} 页")
        if failed:
            log(f"{failed} 个文件打开失败，已跳过", "warn")
    return out


def render_preview(file_paths, cfg: MergeConfig, target_w: int = 1600, log=None) -> bytes:
    """预览 PNG bytes：单页直接渲染；多页时纵向拼接为一张长图（页间留灰缝）。"""
    doc = build_merged(file_paths, cfg, log=log)
    try:
        zoom = target_w / doc[0].rect.width
        mat = fitz.Matrix(zoom, zoom)
        if doc.page_count == 1:
            pix = doc[0].get_pixmap(matrix=mat, alpha=False)
            return pix.tobytes("png")

        gap = 28                                   # 页间灰缝（与预览区底色 #F1F5F9 呼应）
        imgs = []
        for page in doc:
            pix = page.get_pixmap(matrix=mat, alpha=False)
            mode = "RGB" if pix.n >= 3 else "L"
            imgs.append(Image.frombytes(mode, (pix.width, pix.height), pix.samples))
        w = max(im.width for im in imgs)
        h = sum(im.height for im in imgs) + gap * (len(imgs) - 1)
        canvas = Image.new("RGB", (w, h), (241, 245, 249))
        y = 0
        for im in imgs:
            canvas.paste(im, (0, y))
            y += im.height + gap
        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue()
    finally:
        doc.close()


def export(doc: fitz.Document, out_path: str, cfg: MergeConfig) -> list[str]:
    """导出 PDF / JPG / PNG，返回实际写出的文件路径列表。

    pdf: 多页直接存入同一个 PDF；
    jpg/png: 每页一张图，多页时文件名自动加 _p1/_p2… 页码后缀。
    """
    if cfg.export_format == "pdf":
        doc.save(out_path)
        return [out_path]

    m = fitz.Matrix(cfg.dpi / 72.0, cfg.dpi / 72.0)
    base, ext = os.path.splitext(out_path)
    multi = doc.page_count > 1
    paths: list[str] = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=m, alpha=False)
        p = f"{base}_p{i + 1}{ext}" if multi else out_path
        pix.save(p)                     # 按后缀 .png/.jpg 自动选编码
        paths.append(p)
    return paths
