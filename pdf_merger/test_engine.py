"""engine 真实合并/预览/导出测试（无需 GUI）。"""
import os
import tempfile
import pymupdf as fitz  # noqa

from config import MergeConfig, validate
from pdf_engine import build_merged, render_preview, export, grid_rc, page_size_pt


def make_single_page(path, label, size=(595, 842)):
    """生成一个单页 PDF，画一个矩形和文字标识。"""
    doc = fitz.open()
    page = doc.new_page(width=size[0], height=size[1])
    page.draw_rect(fitz.Rect(20, 20, size[0] - 20, size[1] - 20),
                   color=(0.3, 0.3, 0.9), width=2)
    page.insert_text((size[0] / 2 - 60, size[1] / 2), label,
                     fontsize=40, color=(0.2, 0.2, 0.6))
    doc.save(path)
    doc.close()


def main():
    tmp = tempfile.mkdtemp(prefix="pdfmerge_")
    print("tmp:", tmp)

    files = []
    for i in range(4):
        p = os.path.join(tmp, f"p{i + 1}.pdf")
        make_single_page(p, f"PAGE {i + 1}")
        files.append(p)

    results = []
    for mode in (2, 4, 6, 8):
        for ori in ("横向", "纵向"):
            cfg = validate(MergeConfig(mode=mode, orientation=ori,
                                        gap_h_mm=5, gap_v_mm=5, margin_mm=5))
            pw, ph = page_size_pt(cfg)
            rows, cols = grid_rc(cfg)

            doc = build_merged(files, cfg)
            assert doc.page_count == 1, f"{mode}/{ori} 应输出单页"
            page = doc[0]
            w, h = page.rect.width, page.rect.height
            assert abs(w - pw) < 0.1 and abs(h - ph) < 0.1, \
                f"{mode}/{ori} 页面尺寸 {w:.1f}x{h:.1f} != {pw:.1f}x{ph:.1f}"

            out_pdf = os.path.join(tmp, f"out_{mode}{ori}.pdf")
            export(doc, out_pdf, MergeConfig(export_format="pdf"))
            doc.close()

            # 预览 png
            png = render_preview(files, cfg, target_w=480)
            assert png[:8] == b"\x89PNG\r\n\x1a\n", "preview 非 PNG"

            # jpg / png 导出
            for fmt in ("jpg", "png"):
                out = os.path.join(tmp, f"out_{mode}{ori}.{fmt}")
                d2 = build_merged(files, cfg)
                export(d2, out, MergeConfig(export_format=fmt, dpi=150))
                d2.close()
                sz = os.path.getsize(out)
                assert sz > 0, f"{fmt} 空文件"

            results.append((f"{mode}合1 {ori}", f"{rows}x{cols}",
                            f"{w:.0f}x{h:.0f}pt",
                            f"pdf={os.path.getsize(out_pdf)}B png={len(png)}B"))

    print("\nmode/方向      网格   输出页尺寸      产物")
    print("-" * 60)
    for r in results:
        print(f"{r[0]:<12} {r[1]:<6} {r[2]:<14} {r[3]}")
    print(f"\n全部通过：{len(results)} 组配置 × (pdf/jpg/png) 导出无误")


if __name__ == "__main__":
    main()
