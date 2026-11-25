@echo off
rem Builds the large Terrain Builder inputs from the files in this repo, then the mission.
rem Needs about 6 GB of free memory and 20 minutes. Run setup.bat first.
rem
rem   build_all.bat           use the committed heightmap, mask and objects (no download)
rem   build_all.bat regen     regenerate the whole terrain first (downloads elevation tiles)
cd /d "%~dp0\tools"

if /i "%~1"=="regen" (
    echo [1/5] Regenerating terrain, towns, roads, sites and forests...
    python generate_terrain.py || goto :fail
) else (
    echo [1/5] Using the committed terrain. Pass "regen" to rebuild it.
)

echo [2/5] Heightmap to source\heightmap_4096.asc...
python png_to_asc.py || goto :fail

echo [3/5] Surface mask to source\mask_20480.png...
python upscale_mask.py 20480 || goto :fail

echo [4/5] Satellite to source\satellite_20480.png...
python build_satellite.py --size 20480 || goto :fail

echo [5/5] Mission files to mission\dayzOffline.aotearoa...
python build_mission.py || goto :fail

echo.
echo All done. Next: import into Terrain Builder (see README).
pause
exit /b 0

:fail
echo.
echo A step failed; see the message above.
pause
exit /b 1
