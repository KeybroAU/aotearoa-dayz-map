#!/usr/bin/env bash
# Launch loop for an Aotearoa DayZ server on Linux. Put this next to DayZServer,
# with @Aotearoa in the server folder and dayzOffline.aotearoa in mpmissions.
set -u
cd "$(dirname "$0")"
SERVER_PORT=${SERVER_PORT:-2302}
CPU_COUNT=${CPU_COUNT:-4}
while true; do
    echo "$(date) starting Aotearoa"
    ./DayZServer -config=serverDZ.cfg -port="$SERVER_PORT" -mod=@Aotearoa -profiles=profiles \
        -cpuCount="$CPU_COUNT" -dologs -adminlog -netlog -freezecheck
    sleep 10
done
