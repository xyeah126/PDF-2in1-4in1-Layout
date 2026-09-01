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


# ---------- 多页输出（超出单页容量自动翻页） ----------
@pytest.mark.parametrize("mode,nfiles,expect_pages", [
    (2, 3, 2),    # 用户场景：3 个文件 + 2合1 → 2 页
    (2, 5, 3),
    (4, 5, 2),
    (4, 8, 2),
    (6, 7, 2),
    (6, 8, 2),
    (8, 8, 1),
])
def test_merge_multipage(single_pages, mode, nfiles, expect_pages):
    cfg = validate(MergeConfig(mode=mode, orientation="横向"))
    doc = build_merged(single_pages[:nfiles], cfg)
    try:
        assert doc.page_count == expect_pages
        # 每一页都必须非空白（最后一页不足 cap 也要有内容）
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(0.3, 0.3))
            colors = {bytes(pix.samples[i:i + 3]) for i in range(0, len(pix.samples), 9)}
            assert len(colors) > 5
    finally:
        doc.close()


def test_merge_multipage_second_page_layout(single_pages):
    """3 文件 + 2合1：第1页 2 个槽位都有内容，第2页第1个槽位有、第2个槽位空白。"""
    cfg = validate(MergeConfig(mode=2, orientation="横向"))
    doc = build_merged(single_pages[:3], cfg)
    try:
        assert doc.page_count == 2
        pw, ph = page_size_pt(cfg)
        from pdf_engine import cell_rect
        # 第2页：槽位0 区域非白，槽位1 区域近似全白
        p2 = doc[1]
        pix = p2.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))

        def cell_nonwhite(cell):
            x0, y0, x1, y1 = (int(v) for v in (cell.x0, cell.y0, cell.x1, cell.y1))
            cnt = 0
            for y in range(max(0, y0), min(pix.height, y1), 4):
                for x in range(max(0, x0), min(pix.width, x1), 4):
                    r, g, b = pix.pixel(x, y)
                    if r < 240 or g < 240 or b < 240:
                        cnt += 1
            return cnt

        assert cell_nonwhite(cell_rect(0, cfg, pw, ph)) > 5     # 第3个文件在槽位0
        assert cell_nonwhite(cell_rect(1, cfg, pw, ph)) < 5     # 槽位1 空白
    finally:
        doc.close()


def test_preview_multipage_is_tall_png(single_pages):
    cfg = validate(MergeConfig(mode=2, orientation="横向"))
    png = render_preview(single_pages[:3], cfg, target_w=400)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    from PIL import Image
    import io as _io
    im = Image.open(_io.BytesIO(png))
    # 两页横向 A4 纵向拼接：高度明显大于宽度
    assert im.height > im.width * 1.4


def test_export_pdf_multipage(single_pages, tmp_path):
    cfg = validate(MergeConfig(mode=2, orientation="横向", export_format="pdf"))
    doc = build_merged(single_pages[:3], cfg)
    out = tmp_path / "m.pdf"
    try:
        paths = export(doc, str(out), cfg)
    finally:
        doc.close()
    assert paths == [str(out)]
    check = fitz.open(str(out))
    try:
        assert check.page_count == 2
    finally:
        check.close()


@pytest.mark.parametrize("fmt", ["jpg", "png"])
def test_export_images_multipage(single_pages, tmp_path, fmt):
    cfg = validate(MergeConfig(mode=2, orientation="横向",
                               export_format=fmt, dpi=100))
    doc = build_merged(single_pages[:3], cfg)
    out = tmp_path / f"m.{fmt}"
    try:
        paths = export(doc, str(out), cfg)
    finally:
        doc.close()
    # 多页 → 两张带页码后缀的图，单页时才用原名
    assert len(paths) == 2
    assert (tmp_path / f"m_p1.{fmt}").exists()
    assert (tmp_path / f"m_p2.{fmt}").exists()
    assert not out.exists()


def test_export_image_singlepage_keeps_name(single_pages, tmp_path):
    """单页导出图片不加页码后缀，兼容旧行为。"""
    cfg = validate(MergeConfig(mode=2, orientation="横向",
                               export_format="png", dpi=100))
    doc = build_merged(single_pages[:2], cfg)
    out = tmp_path / "one.png"
    try:
        paths = export(doc, str(out), cfg)
    finally:
        doc.close()
    assert paths == [str(out)] and out.exists()


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


# ---------- 持久化 ----------
import os
import persistence


def test_persistence_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "config_path",
                        lambda: str(tmp_path / "cfg.json"))
    orig = validate(MergeConfig(mode=6, page_size="A3", orientation="纵向",
                                gap_h_mm=12, dpi=300, export_format="png"))
    files = [str(tmp_path / "a.pdf"), str(tmp_path / "b.pdf")]
    for f in files:
        tmp_path.joinpath(os.path.basename(f)).write_bytes(b"%PDF-1.4")
    persistence.save(orig, files)
    cfg, loaded = persistence.load()
    assert cfg is not None
    assert cfg.mode == 6 and cfg.page_size == "A3" and cfg.dpi == 300
    assert loaded == files


def test_persistence_drops_missing_files(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "config_path",
                        lambda: str(tmp_path / "cfg.json"))
    files = [str(tmp_path / "a.pdf"), str(tmp_path / "gone.pdf")]
    tmp_path.joinpath("a.pdf").write_bytes(b"%PDF-1.4")
    persistence.save(MergeConfig(), files)
    _, loaded = persistence.load()
    assert loaded == [str(tmp_path / "a.pdf")]
