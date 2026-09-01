"""记住上次设置：MergeConfig + 文件列表持久化为 JSON。

存储位置：打包态随 exe 所在目录，开发态随脚本目录。
"""
import json
import os
import sys
from dataclasses import asdict

from config import MergeConfig, validate


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
    files = [f for f in data.get("files", [])
             if isinstance(f, str) and os.path.exists(f)]
    return cfg, files


def save(cfg: MergeConfig, files: list[str]) -> None:
    """静默保存；失败不抛。文件列表原样存，加载时再校验存在性。"""
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump({
                "config": asdict(validate(cfg)),
                "files": list(files),
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
