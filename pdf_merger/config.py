"""合并配置与尺寸/网格常量。

纯数据层：不依赖任何 UI 库，可被 engine / worker / app 共用。
"""
from dataclasses import dataclass


@dataclass
class MergeConfig:
    mode: int = 4                 # 2 / 4 / 6 / 8
    page_size: str = "A4"         # "A4" | "A3"
    orientation: str = "横向"     # "横向" | "纵向"  → 输出页方向 + 网格行列
    gap_h_mm: float = 10.0        # 列间距
    gap_v_mm: float = 10.0        # 行间距
    margin_mm: float = 10.0       # 外边距
    export_format: str = "pdf"    # "pdf" | "jpg" | "png"
    dpi: int = 300                # 仅 jpg / png 生效（默认 300，清晰打印级）


# 页面尺寸（PDF 点，1pt = 1/72 inch），纵向基准
PAGE_PT = {
    "A4": (595.28, 841.89),
    "A3": (841.89, 1190.55),
}

# mode -> orientation -> (rows, cols)
GRID = {
    2: {"横向": (1, 2), "纵向": (2, 1)},
    4: {"横向": (2, 2), "纵向": (2, 2)},
    6: {"横向": (2, 3), "纵向": (3, 2)},
    8: {"横向": (2, 4), "纵向": (4, 2)},
}

MM2PT = 72.0 / 25.4

VALID_MODES = (2, 4, 6, 8)
VALID_SIZES = ("A4", "A3")
VALID_ORI = ("横向", "纵向")
VALID_FMT = ("pdf", "jpg", "png")


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def validate(cfg: MergeConfig) -> MergeConfig:
    """回退非法值为默认，保证 engine 永不收到脏数据。"""
    cfg.mode = cfg.mode if cfg.mode in VALID_MODES else 4
    cfg.page_size = cfg.page_size if cfg.page_size in VALID_SIZES else "A4"
    cfg.orientation = cfg.orientation if cfg.orientation in VALID_ORI else "横向"
    cfg.export_format = cfg.export_format if cfg.export_format in VALID_FMT else "pdf"
    cfg.gap_h_mm = clamp(float(cfg.gap_h_mm or 0), 0, 100)
    cfg.gap_v_mm = clamp(float(cfg.gap_v_mm or 0), 0, 100)
    cfg.margin_mm = clamp(float(cfg.margin_mm or 0), 0, 50)
    cfg.dpi = int(clamp(int(cfg.dpi or 300), 72, 600))
    return cfg
