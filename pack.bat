@echo off
rem Packs @Aotearoa and a ready-to-run server folder into dist\. Run after exporting the world
rem from Terrain Builder. Extra options go straight to tools\pack_mod.py, for example:
rem   pack.bat --key aotearoa --zip
cd /d "%~dp0\tools"
python pack_mod.py %*
if errorlevel 1 (
    echo.
    echo Packing failed; see the message above.
    pause
    exit /b 1
)
pause
