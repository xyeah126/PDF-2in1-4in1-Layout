@echo off
chcp 65001 >nul
REM ============================================================
REM  PDF 单页合并器  Windows 构建脚本
REM  产物直出：S:\trae work\合并pdf排版程序app\PDFMerger.exe
REM ============================================================

set DIST=S:\trae work\合并pdf排版程序app

echo [1/2] 安装依赖...
pip install -r requirements.txt
if errorlevel 1 ( echo 依赖安装失败 & pause & exit /b 1 )

echo [2/2] 构建 exe（输出到 %DIST%）...
pyinstaller --noconfirm --distpath "%DIST%" build.spec
if errorlevel 1 ( echo 构建失败 & pause & exit /b 1 )

echo.
echo 完成：%DIST%\PDFMerger.exe
pause
