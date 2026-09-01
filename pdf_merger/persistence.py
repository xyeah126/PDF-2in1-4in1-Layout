"""记住上次设置：MergeConfig + 文件列表持久化为 JSON。

存储位置：打包态随 exe 所在目录，开发态随脚本目录。
"""
import json
import os
import sys
from dataclasses import asdict

from config import MergeConfig, validate

# 设置版本：升版时用于把旧默认值迁移到新默认值
# v2: 间距 5mm → 10mm, DPI 150 → 200
# v3: DPI 200 → 300
SETTINGS_VERSION = 3


def config_path() -> str:
    """配置文件路径。"""
    base = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "pdf_merger_config.json")


def load() -> tuple[MergeConfig | None, list[str]]:
    """读取上次设置与文件列表。

    文件不存在的自动剔除（路径失效不致崩溃）。
    返回 (cfg | None, files)。
    """
    p = config_path()
    if not os.path.exists(p):
        return None, []
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None, []

    cfg = None
    try:
        cfg = validate(MergeConfig(**data.get("config", {})))
    except Exception:
        cfg = None
    # 旧版设置迁移：把旧默认值升级到新版
    ver = int(data.get("version", 0))
    if cfg is not None and ver < SETTINGS_VERSION:
        # v1→v2
        if cfg.gap_h_mm == 5.0:
            cfg.gap_h_mm = 10.0
        if cfg.gap_v_mm == 5.0:
            cfg.gap_v_mm = 10.0
        if cfg.margin_mm == 5.0:
            cfg.margin_mm = 10.0
        if cfg.dpi == 150:
            cfg.dpi = 200
        # v2→v3
        if cfg.dpi == 200:
            cfg.dpi = 300
    files = [f for f in data.get("files", [])
             if isinstance(f, str) and os.path.exists(f)]
    return cfg, files


def save(cfg: MergeConfig, files: list[str]) -> None:
    """静默保存；失败不抛。文件列表原样存，加载时再校验存在性。"""
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump({
            "version": SETTINGS_VERSION,
            "config": asdict(validate(cfg)),
            "files": list(files),
        }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
