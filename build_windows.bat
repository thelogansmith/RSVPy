@echo off
REM ============================================================
REM  RSVPy Installer Builder (Windows)
REM
REM  Run this from the RSVPy project root.
REM
REM  Step 1: Bundles the app with PyInstaller  ->  dist\RSVPy\
REM  Step 2: Wraps it in an installer with Inno Setup  ->  Output\Setup_RSVPy_0.1.0-beta.exe
REM
REM  Prerequisites:
REM    - Python 3.10+  (python.org)
REM    - Inno Setup 6  (https://jrsoftware.org/isinfo.php)
REM
REM  If Inno Setup is not installed, step 1 still completes
REM  and you get the portable dist\RSVPy folder.
REM ============================================================

echo.
echo === RSVPy Installer Builder ===
echo.

REM --- Check Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

REM --- Create/activate venv ---
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat

REM --- Install dependencies ---
echo Installing dependencies...
pip install -r requirements.txt pyinstaller --quiet

REM --- Step 1: PyInstaller ---
echo.
echo [Step 1/2] Building application with PyInstaller...
pyinstaller RSVPy.spec --noconfirm

if not exist dist\RSVPy\RSVPy.exe (
    echo.
    echo PYINSTALLER FAILED — check the output above for errors.
    pause
    exit /b 1
)

echo.
echo PyInstaller done: dist\RSVPy\RSVPy.exe

REM --- Step 2: Inno Setup ---
echo.
echo [Step 2/2] Building installer with Inno Setup...

REM Try common Inno Setup install locations
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
) else (
    where iscc >nul 2>&1
    if not errorlevel 1 (
        set "ISCC=iscc"
    )
)

if "%ISCC%"=="" (
    echo.
    echo Inno Setup not found — skipping installer creation.
    echo.
    echo To create the installer exe:
    echo   1. Install Inno Setup 6 from https://jrsoftware.org/isinfo.php
    echo   2. Open RSVPy_installer.iss in Inno Setup
    echo   3. Click Build ^> Compile
    echo.
    echo Or re-run this script after installing Inno Setup.
    echo.
    echo In the meantime, you can share the dist\RSVPy folder as a
    echo portable app — users just run RSVPy.exe from inside it.
    pause
    exit /b 0
)

"%ISCC%" RSVPy_installer.iss

if exist Output\Setup_RSVPy_0.1.0-beta.exe (
    echo.
    echo ============================================================
    echo  SUCCESS!
    echo.
    echo  Installer:  Output\Setup_RSVPy_0.1.0-beta.exe
    echo.
    echo  Send this single file to anyone. They double-click it,
    echo  get a standard install wizard, and RSVPy shows up in
    echo  their Start Menu and optionally on their desktop.
    echo ============================================================
) else (
    echo.
    echo Inno Setup failed — check the output above.
    echo The portable version is still available at dist\RSVPy\RSVPy.exe
)

echo.
pause
