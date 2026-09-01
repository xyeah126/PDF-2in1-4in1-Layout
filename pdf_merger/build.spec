# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：单文件、无控制台窗口
# 用法：pyinstaller build.spec  →  产物 dist/PDFMerger_v<版本号>.exe
import os
import re

import customtkinter

# 从 version.py 读取版本号，让 exe 文件名自带版本
with open("version.py", encoding="utf-8") as _f:
    _VER = re.search(r'VERSION\s*=\s*"([^"]+)"', _f.read()).group(1)
EXE_NAME = f"PDFMerger_v{_VER}"

datas = [
    # customtkinter 主题资源必须随包
    (customtkinter.__path__[0], "customtkinter"),
]

# 拖拽支持可选：缺失则构建出的 exe 自动降级为按钮添加
try:
    import tkinterdnd2
    datas.append((os.path.dirname(tkinterdnd2.__file__), "tkinterdnd2"))
except ImportError:
    pass

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=["PIL"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=EXE_NAME,
    onefile=True,
    console=False,         # 无控制台窗口（关键：EXE 只认 console，不认 windowed）
    upx=True,
    icon="app.ico",                 # 应用图标
    version="version_info.txt",     # exe 属性显示版本号
)
