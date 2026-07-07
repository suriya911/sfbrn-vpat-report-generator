@echo off
REM ============================================================
REM  SFBRN VPAT Reviewer v10 - Windows build script
REM
REM  RECONSTRUCTED FILE. The original build_exe.bat was lost in the
REM  file-name shuffle; this is rebuilt from BUILD_INSTRUCTIONS.md and
REM  installer.iss, which require PyInstaller to emit:
REM      dist\VPAT_Reviewer\VPAT_Reviewer.exe   (+ bundled assets\)
REM
REM  Usage: double-click this file, or run it from a command prompt.
REM  It installs dependencies, runs PyInstaller, and copies the logo.
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo === [1/3] Installing dependencies ===
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: dependency installation failed.
    pause
    exit /b 1
)

echo.
echo === [2/3] Building VPAT_Reviewer.exe with PyInstaller ===
REM  --windowed : GUI app, no console window
REM  --onedir   : folder build (installer.iss bundles dist\VPAT_Reviewer\*)
REM  --add-data : bundle the assets folder (logo) if it exists
set ADDDATA=
if exist "assets" set ADDDATA=--add-data "assets;assets"

python -m PyInstaller run_app.py ^
    --name VPAT_Reviewer ^
    --windowed ^
    --onedir ^
    --noconfirm ^
    --clean ^
    %ADDDATA%
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo === [3/3] Ensuring the logo is bundled ===
if exist "assets\SFBRN_Logo.png" (
    if not exist "dist\VPAT_Reviewer\assets" mkdir "dist\VPAT_Reviewer\assets"
    copy /y "assets\SFBRN_Logo.png" "dist\VPAT_Reviewer\assets\SFBRN_Logo.png" >nul
    echo Logo copied.
) else (
    echo NOTE: assets\SFBRN_Logo.png not found - the app will use its text badge fallback.
)

echo.
echo === Build complete ===
echo Output: dist\VPAT_Reviewer\VPAT_Reviewer.exe
echo Next:   open installer.iss in Inno Setup and press Build ^> Compile
echo         to produce Output\VPAT_Reviewer_Setup.exe
pause
endlocal
