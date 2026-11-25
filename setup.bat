@echo off
rem Installs the Python packages the build scripts need. Run once.
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python 3.10 or newer from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" in the installer, then run this again.
    pause
    exit /b 1
)
python -m pip install --upgrade pip
python -m pip install -r tools\requirements.txt
if errorlevel 1 (
    echo Package install failed.
    pause
    exit /b 1
)
echo.
echo Done. Run build_all.bat next.
pause
