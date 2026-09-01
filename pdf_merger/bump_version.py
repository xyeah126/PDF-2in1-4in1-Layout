"""一键升级版本号：同步改 version.py 与 version_info.txt。

用法：
    python bump_version.py            # 查看当前版本
    python bump_version.py 0.7        # 升到 0.7
    python bump_version.py 1.2.3      # 升到 1.2.3（exe 属性 1.2.3.0）
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
VERSION_PY = ROOT / "version.py"
VERSION_INFO = ROOT / "version_info.txt"


def parse(ver: str) -> tuple[int, ...]:
    """'0.7' → (0,7,0,0)；'1.2.3' → (1,2,3,0)。"""
    parts = [int(x) for x in ver.strip().split(".")]
    if not parts or len(parts) > 4:
        raise ValueError("版本号应为 1~4 段数字，如 0.7 / 1.2.3 / 1.2.3.4")
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def current() -> str:
    m = re.search(r'VERSION\s*=\s*"([^"]+)"', VERSION_PY.read_text(encoding="utf-8"))
    return m.group(1) if m else "?"


def bump(ver: str) -> None:
    a, b, c, d = parse(ver)
    quad = f"{a}, {b}, {c}, {d}"
    full = f"{a}.{b}.{c}.{d}"

    # version.py
    v_text = VERSION_PY.read_text(encoding="utf-8")
    v_text = re.sub(r'VERSION\s*=\s*"[^"]*"',
                    f'VERSION = "{ver}"', v_text)
    VERSION_PY.write_text(v_text, encoding="utf-8")

    # version_info.txt
    i_text = VERSION_INFO.read_text(encoding="utf-8")
    i_text = re.sub(r'filevers\s*=\s*\([^)]*\)', f'filevers = ({quad})', i_text)
    i_text = re.sub(r'prodvers\s*=\s*\([^)]*\)', f'prodvers = ({quad})', i_text)
    i_text = re.sub(r"\('FileVersion',\s*'[^']*'\)",
                    f"('FileVersion', '{full}')", i_text)
    i_text = re.sub(r"\('ProductVersion',\s*'[^']*'\)",
                    f"('ProductVersion', '{full}')", i_text)
    VERSION_INFO.write_text(i_text, encoding="utf-8")

    print(f"已升级：{current()}  →  version.py=VERSION={ver!r}, exe 属性={full}")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(f"当前版本：{current()}")
        print("用法：python bump_version.py <新版本号>  如 0.7")
        sys.exit(0)
    try:
        bump(sys.argv[1])
    except ValueError as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)
