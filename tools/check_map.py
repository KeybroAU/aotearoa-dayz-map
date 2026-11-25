"""Sanity checks on the committed map files, run by GitHub Actions on every push.

    python check_map.py

Checks that the heightmap, mask and config agree on size, that every XML and JSON file parses,
that buildings, spawns and events sit on the map and on land, that the Terrain Builder files are
well formed, and that every road kind has a RoadsLib entry. Exits non-zero on any failure.
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

MAP_DIR = Path(__file__).resolve().parents[1]
SOURCE = MAP_DIR / "source"
MISSION = MAP_DIR / "mission" / "dayzOffline.aotearoa"
TB_LINE = re.compile(r'^"[^";]+";(-?\d+(\.\d+)?;){7}$')

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(("  ok    " if ok else "  FAIL  ") + msg)
    if not ok:
        failures.append(msg)


def main() -> None:
    Image.MAX_IMAGE_PIXELS = None
    meta = json.loads((SOURCE / "heightmap.json").read_text())
    size, grid, cell = meta["terrain_size_m"], meta["grid"], meta["cell_size_m"]
    east, north = meta["easting"], meta["northing"]
    print("Size")
    check(abs(grid * cell - size) < 1e-6, f"grid {grid} x {cell} m = {size} m")
    hm = np.asarray(Image.open(SOURCE / "heightmap_4096.png"))
    check(hm.shape == (grid, grid), f"heightmap is {hm.shape}")
    check(Image.open(SOURCE / "mask_4096.png").size == (grid, grid), "mask_4096.png matches the grid")
    cfg = (MAP_DIR / "config.cpp").read_text()
    m = re.search(r"mapSize\s*=\s*(\d+)", cfg)
    check(bool(m) and int(m.group(1)) == round(size), f"config.cpp mapSize {m.group(1) if m else '?'}")
    bat = (MAP_DIR / "build_all.bat").read_text()
    check(str(round(size)) in bat, "build_all.bat uses the terrain size")

    h = meta["png_black_m"] + hm.astype(np.float64) / 65535.0 * (meta["png_white_m"] - meta["png_black_m"])

    def ground(x, y):
        c = int(np.clip(x / cell, 0, grid - 1))
        r = int(np.clip((size - y) / cell, 0, grid - 1))
        return h[r, c]

    def on_map(x, y):
        return 0 <= x <= size and 0 <= y <= size

    print("Files parse")
    for f in sorted(MISSION.rglob("*.xml")):
        try:
            ET.parse(f)
            ok = True
        except ET.ParseError as e:
            ok = False
            print(f"        {e}")
        check(ok, str(f.relative_to(MAP_DIR)))
    for f in sorted(list(MISSION.rglob("*.json")) + list(SOURCE.rglob("*.json"))):
        try:
            json.loads(f.read_text(encoding="utf-8"))
            ok = True
        except ValueError:
            ok = False
        check(ok, str(f.relative_to(MAP_DIR)))

    print("Objects")
    for f in sorted((SOURCE / "objects").glob("*_tb.txt")):
        lines = [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
        bad = [ln for ln in lines if not TB_LINE.match(ln)]
        off = 0
        for ln in lines:
            parts = ln.split(";")
            try:
                if not on_map(float(parts[1]) - east, float(parts[2]) - north):
                    off += 1
            except (IndexError, ValueError):
                pass
        check(not bad and off == 0 and lines, f"{f.name}: {len(lines)} objects, {len(bad)} malformed, {off} off the map")
    for f in sorted((SOURCE / "objects").glob("*_spawner.json")):
        objs = json.loads(f.read_text(encoding="utf-8"))["Objects"]
        wet = sum(ground(o["pos"][0], o["pos"][2]) < 0.0 for o in objs)
        off = sum(not on_map(o["pos"][0], o["pos"][2]) for o in objs)
        check(off == 0 and wet <= len(objs) * 0.01, f"{f.name}: {len(objs)} buildings, {wet} in the sea, {off} off the map")

    print("Mission")
    spawns = ET.parse(MISSION / "cfgplayerspawnpoints.xml").getroot().iter("pos")
    pts = [(float(p.get("x")), float(p.get("z"))) for p in spawns]
    check(len(pts) >= 10 and all(on_map(x, y) and ground(x, y) > 0.0 for x, y in pts),
          f"{len(pts)} player spawns, all on land")
    events = ET.parse(MISSION / "cfgeventspawns.xml").getroot()
    for ev in events.iter("event"):
        pos = [(float(p.get("x")), float(p.get("z"))) for p in ev.iter("pos")]
        boat = ev.get("name") == "VehicleBoat"
        good = sum(on_map(x, y) and ((ground(x, y) < 0.0) if boat else (ground(x, y) > 0.0)) for x, y in pos)
        check(good >= len(pos) * 0.95, f"{ev.get('name')}: {good}/{len(pos)} on {'water' if boat else 'land'}")
    gameplay = json.loads((MISSION / "cfggameplay.worldsdata.json").read_text())
    for name in gameplay.get("PlayerData", {}).get("spawnGearPresetFiles", []):
        check((MISSION / name).exists(), f"spawn gear preset {name}")

    print("Roads")
    roads = json.loads((SOURCE / "roads.json").read_text(encoding="utf-8"))
    lib = (MAP_DIR / "data" / "roads" / "RoadsLib.cfg").read_text()
    for kind, spec in roads["kinds"].items():
        check(f"class Road{spec['id']:04d}" in lib, f"{kind} has RoadsLib entry Road{spec['id']:04d}")
    check(all(r["kind"] in roads["kinds"] for r in roads["roads"]), f"{len(roads['roads'])} roads use known kinds")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        sys.exit(1)
    print("All checks passed")


if __name__ == "__main__":
    main()
