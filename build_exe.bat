@echo off
REM ============================================================
REM  SFBRN VPAT Reviewer - Windows build script
REM
REM  Produces a single, shareable executable:
REM      dist\VPAT_Reviewer.exe
REM
REM  Just double-click this file. It installs the app and its build
REM  tools into your Python environment, then runs PyInstaller using
REM  vpat_reviewer.spec (which bundles wcag.json and all dependencies).
REM
REM  Requires: Python 3.10+ on PATH. Nothing else — the .exe it makes
REM  is self-contained and runs on machines with no Python installed.
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo === [1/2] Installing the app + build tools ===
python -m pip install --upgrade pip
python -m pip install -e ".[build]"
if errorlevel 1 (
    echo ERROR: install failed. Is Python 3.10+ on your PATH?
    pause
    exit /b 1
)

echo.
echo === [2/2] Building VPAT_Reviewer.exe with PyInstaller ===
python -m PyInstaller vpat_reviewer.spec --noconfirm --clean
if errorlevel 1 (
    echo ERROR: PyInstaller build failed. See the output above.
    pause
    exit /b 1
)

echo.
echo === Build complete ===
echo Output: dist\VPAT_Reviewer.exe   (this single file is what you share)
echo.
echo Optional: to make a click-through installer that also creates the
echo Desktop folders and a shortcut, open installer.iss in Inno Setup
echo (free, https://jrsoftware.org) and press Build ^> Compile.
pause
endlocal
