@echo off
rem Launch loop for an Aotearoa DayZ server. Put this next to DayZServer_x64.exe,
rem with @Aotearoa in the server folder and dayzOffline.aotearoa in mpmissions.
set SERVER_PORT=2302
set CPU_COUNT=4
:start
echo %date% %time% starting Aotearoa
start "Aotearoa DayZ" /min /wait DayZServer_x64.exe -config=serverDZ.cfg -port=%SERVER_PORT% "-mod=@Aotearoa" -profiles=profiles -cpuCount=%CPU_COUNT% -dologs -adminlog -netlog -freezecheck
timeout /t 10
goto start
