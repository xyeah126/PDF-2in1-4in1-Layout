@echo off
REM ============================================================
REM  PDF Merger build script
REM  Output goes two levels up (..\..) = the project root folder
REM ============================================================

set DIST=..\..

echo [1/2] Installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 ( echo pip install failed & pause & exit /b 1 )

echo [2/2] Building exe, output to %DIST%
python -m PyInstaller --noconfirm --distpath "%DIST%" build.spec
if errorlevel 1 ( echo build failed & pause & exit /b 1 )

echo.
echo Done. Check %DIST% for PDFMerger_v*.exe
pause
