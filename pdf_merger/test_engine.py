"""engine 的 pytest 测试套件。

运行：cd pdf_merger && pytest -q
"""
import pytest
import pymupdf as fitz

from config import MergeConfig, validate
from pdf_engine import (
    build_merged, render_preview, export,
    grid_rc, page_size_pt, _fit,
)


def _make_single_page(path: str, label: str, size=(595, 842)) -> None:
    """生成一个带边框与文字的单页 PDF。"""
    doc = fitz.open()
    page = doc.new_page(width=size[0], height=size[1])
    page.draw_rect(fitz.Rect(20, 20, size[0] - 20, size[1] - 20),
                   color=(0.3, 0.3, 0.9), width=2)
    page.insert_text((size[0] / 2 - 60, size[1] / 2), label,
                     fontsize=40, color=(0.2, 0.2, 0.6))
    doc.save(path)
    doc.close()


@pytest.fixture(scope="session")
def single_pages(tmp_path_factory):
    """8 个单页 PDF，足够覆盖 8 合1。"""
    d = tmp_path_factory.mktemp("pages")
    paths = []
    for i in range(8):
        p = d / f"p{i + 1}.pdf"
        _make_single_page(str(p), f"PAGE {i + 1}")
        paths.append(str(p))
    return paths


# ---------- 布局正确性 ----------
@pytest.mark.parametrize("mode", [2, 4, 6, 8])
@pytest.mark.parametrize("ori", ["横向", "纵向"])
def test_merge_layout(single_pages, mode, ori):
    cfg = validate(MergeConfig(mode=mode, orientation=ori))
    rows, cols = grid_rc(cfg)
    assert rows * cols == mode

    doc = build_merged(single_pages[:mode], cfg)
    try:
        assert doc.page_count == 1
        pw, ph = page_size_pt(cfg)
        page = doc[0]
        assert abs(page.rect.width - pw) < 0.1
        assert abs(page.rect.height - ph) < 0.1
    finally:
        doc.close()


# ---------- 导出格式 ----------
@pytest.mark.parametrize("mode", [2, 4, 6, 8])
@pytest.mark.parametrize("fmt", ["pdf", "jpg", "png"])
def test_export_formats(single_pages, tmp_path, mode, fmt):
    cfg = validate(MergeConfig(mode=mode, orientation="横向",
                               export_format=fmt, dpi=150))
    doc = build_merged(single_pages[:mode], cfg)
    out = tmp_path / f"out.{fmt}"
    try:
        export(doc, str(out), cfg)
    finally:
        doc.close()
    assert out.exists()
    assert out.stat().st_size > 0


def test_preview_is_png(single_pages):
    cfg = validate(MergeConfig(mode=4))
    png = render_preview(single_pages[:4], cfg, target_w=400)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_merged_non_blank(single_pages):
    """确认 show_pdf_page 真把源页贴进网格，非空白。"""
    cfg = validate(MergeConfig(mode=4, orientation="横向"))
    doc = build_merged(single_pages[:4], cfg)
    try:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(0.3, 0.3))
        colors = {bytes(pix.samples[i:i + 3]) for i in range(0, len(pix.samples), 9)}
        assert len(colors) > 5
    finally:
        doc.close()


# ---------- 单元：校验与居中 ----------
def test_validate_clamps():
    bad = MergeConfig(mode=99, page_size="A0", orientation="斜",
                      gap_h_mm=-5, dpi=99999)
    c = validate(bad)
    assert c.mode == 4
    assert c.page_size == "A4"
    assert c.orientation == "横向"
    assert c.gap_h_mm == 0
    assert c.dpi == 600


def test_fit_preserves_aspect_and_centers():
    src = fitz.Rect(0, 0, 100, 50)   # 2:1
    cell = fitz.Rect(0, 0, 100, 100)
    r = _fit(src, cell)
    assert abs(r.width - 100) < 0.01
    assert abs(r.height - 50) < 0.01
    assert abs(r.x0 - 0) < 0.01
    assert abs(r.y0 - 25) < 0.01
