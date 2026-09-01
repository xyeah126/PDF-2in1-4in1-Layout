"""PyMuPDF 封装：合并 / 预览 / 导出。

纯计算层：不 import 任何 UI 库，仅依赖 PyMuPDF。
"""
import os

import pymupdf as fitz  # PyMuPDF（fitz 别名前向兼容，避免旧 import 警告）

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
    """合并多份单页 PDF 为新单页，矢量保真。

    log: 可选回调 log(msg, level)，用于回传进度/警告。
    """
    pw, ph = page_size_pt(cfg)
    out = fitz.open()
    page = out.new_page(width=pw, height=ph)
    rows, cols = grid_rc(cfg)
    cap = rows * cols

    for i, p in enumerate(file_paths):
        if i >= cap:
            if log:
                log(f"文件数超过 {cap}，仅取前 {cap} 个", "warn")
            break
        try:
            src = fitz.open(p)
        except Exception as e:
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
            src_page = src[0]
            cell = cell_rect(i, cfg, pw, ph)
            page.show_pdf_page(_fit(src_page.rect, cell), src, 0)
        finally:
            src.close()
    return out


def render_preview(file_paths, cfg: MergeConfig, target_w: int = 1600, log=None) -> bytes:
    """低 DPI PNG bytes，供预览控件刷新。"""
    doc = build_merged(file_paths, cfg, log=log)
    try:
        zoom = target_w / doc[0].rect.width
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


def export(doc: fitz.Document, out_path: str, cfg: MergeConfig) -> None:
    """导出 PDF / JPG / PNG。

    pdf: doc.save；jpg/png: get_pixmap(dpi).save(按后缀自动选编码)。
    """
    if cfg.export_format == "pdf":
        doc.save(out_path)
        return
    m = fitz.Matrix(cfg.dpi / 72.0, cfg.dpi / 72.0)
    pix = doc[0].get_pixmap(matrix=m, alpha=False)
    pix.save(out_path)  # 按后缀 .png/.jpg 自动选编码
