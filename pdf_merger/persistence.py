"""记住上次设置：把 MergeConfig 持久化为 JSON。

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


def load() -> MergeConfig | None:
    """读取上次设置；缺失/损坏返回 None。"""
    p = config_path()
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return validate(MergeConfig(**data))
    except Exception:
        return None


def save(cfg: MergeConfig) -> None:
    """静默保存；失败不抛（设置丢失不致命）。"""
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(asdict(validate(cfg)), f, ensure_ascii=False, indent=2)
    except Exception:
        pass
