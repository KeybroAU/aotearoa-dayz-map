"""Sanity checks on the committed map files, run by GitHub Actions on every push.

    python check_map.py

Checks that the heightmap, mask and config agree on size, that every XML and JSON file parses,
that buildings, spawns and events sit on the map and on land, that the Terrain Builder files are
well formed, that every road kind has a RoadsLib entry, and that every object name exists in DayZ. Exits non-zero on any failure.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nz_food  # noqa: E402

MAP_DIR = Path(__file__).resolve().parents[1]
SOURCE = MAP_DIR / "source"
MISSION = MAP_DIR / "mission" / "dayzOffline.aotearoa"
TB_LINE = re.compile(r'^"[^";]+";(-?\d+(\.\d+)?;){7}$')

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(("  ok    " if ok else "  FAIL  ") + msg)
    if not ok:
        failures.append(msg)


def _names(path: Path) -> set[str]:
    return {line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")}


def object_names() -> None:
    """Every spawner class and Terrain Builder template is a DayZ object (tools/dayz_*.txt) or one of the mod's own."""
    classes, models = _names(MAP_DIR / "tools" / "dayz_classes.txt"), _names(MAP_DIR / "tools" / "dayz_models.txt")
    own = ("land_aotearoa_", "aotearoa_")
    for path in sorted(list(SOURCE.glob("objects/*_spawner.json")) + list(MISSION.rglob("*_spawner.json"))):
        names = {o["name"] for o in json.loads(path.read_text(encoding="utf-8"))["Objects"]}
        bad = sorted(n for n in names if n.lower() not in classes and not n.lower().startswith(own))
        check(not bad, f"{path.relative_to(MAP_DIR)}: {len(names)} classes exist in DayZ"
              + (f" (unknown: {', '.join(bad[:5])})" if bad else ""))
    gear: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("itemType"), str):
                gear.add(node["itemType"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for path in MISSION.glob("*spawngear*.json"):
        walk(json.loads(path.read_text(encoding="utf-8")))
    # "" is an empty slot; AotearoaMap is the map item mod's paper map.
    bad = sorted(n for n in gear if n and n.lower() not in classes and n != "AotearoaMap")
    check(bool(gear) and not bad, f"{len(gear)} starting gear items exist in DayZ"
          + (f" (unknown: {', '.join(bad[:5])})" if bad else ""))
    for path in sorted(SOURCE.glob("objects/*_tb.txt")):
        names = {line.split(";", 1)[0].strip('"').lower() for line in path.read_text(encoding="utf-8").splitlines() if line}
        bad = sorted(n for n in names if n not in models and not n.startswith(own))
        check(not bad, f"{path.relative_to(MAP_DIR)}: {len(names)} templates exist in DayZ"
              + (f" (unknown: {', '.join(bad[:5])})" if bad else ""))


# From vanilla cfglimitsdefinition.xml.
USAGES = {"Military", "Police", "Medic", "Firefighter", "Industrial", "Farm", "Coast", "Town", "Village", "Hunting",
          "Office", "School", "Prison", "Lunapark", "SeasonalEvent", "ContaminatedArea", "Historical"}
VALUES = {"Tier1", "Tier2", "Tier3", "Tier4", "Unique"}


def loot() -> None:
    """The New Zealand types.xml uses vanilla limits and keeps every vanilla field."""
    classes = _names(MAP_DIR / "tools" / "dayz_classes.txt")
    vanilla = {e.get("name"): e for e in ET.parse(MAP_DIR / "tools" / "vanilla_types.xml").getroot().iter("type")}
    types = list(ET.parse(MISSION / "aotearoa_ce" / "types.xml").getroot().iter("type"))
    names = [e.get("name") for e in types]
    check(bool(types) and len(set(names)) == len(names), f"{len(types)} New Zealand loot types, no duplicates")
    base = {i.cls: i.base for i in nz_food.ITEMS}
    check(all(n in base or (n.lower() in classes and n in vanilla) for n in names),
          "every loot type is a vanilla DayZ type or a New Zealand food item")
    bad_limits = sorted({u.get("name") for e in types for u in e.iter("usage")} - USAGES
                        | {v.get("name") for e in types for v in e.iter("value")} - VALUES)
    check(not bad_limits, "usages and values are in cfglimitsdefinition.xml" + (f" (unknown: {bad_limits})" if bad_limits else ""))
    check(all(0 <= int(e.findtext("min")) <= int(e.findtext("nominal")) for e in types), "min is at most nominal")
    same = ("lifetime", "restock", "quantmin", "quantmax", "cost")
    src = {n: vanilla[base.get(n, n)] for n in names}
    changed = [e.get("name") for e in types if any(e.findtext(k) != src[e.get("name")].findtext(k) for k in same)
               or [c.attrib for c in e.iter("tag")] != [c.attrib for c in src[e.get("name")].iter("tag")]]
    check(not changed, "lifetimes, quantities and tags match vanilla" + (f" ({changed[:3]})" if changed else ""))
    tiers = json.loads((MISSION / "loot_tiers.json").read_text(encoding="utf-8"))["towns"]
    towns = {r["name"]: r["tier"] for r in csv.DictReader((SOURCE / "towns.csv").open(encoding="utf-8"))}
    hot = sorted(n for n, v in tiers.items() if v > 3 and towns.get(n) != "military")
    check(not hot, "civilian towns are tier 3 or lower" + (f" ({', '.join(hot[:4])})" if hot else ""))
    by_name = {e.get("name"): e for e in types}
    check(all(n in by_name and by_name[n].findtext("nominal") == "0" for n in nz_food.replaced()),
          f"the {len(nz_food.replaced())} vanilla items the New Zealand food replaces are set to nominal 0")


def food() -> None:
    """Every New Zealand food item has a config class, a label texture and, for tins, an opened class."""
    hpp = (MAP_DIR / "config" / "food.hpp").read_text(encoding="utf-8")
    script = (MAP_DIR / "scripts" / "4_World" / "AotearoaFood.c").read_text(encoding="utf-8")
    cfg = (MAP_DIR / "config.cpp").read_text(encoding="utf-8")
    vanilla = _names(MAP_DIR / "tools" / "dayz_classes.txt")
    items = nz_food.ITEMS
    check('#include "config\\food.hpp"' in cfg and all(a in cfg for a in ('"DZ_Gear_Food"', '"DZ_Gear_Drinks"')),
          "config.cpp includes food.hpp and requires the vanilla food and drink addons")
    defined = set(re.findall(r"^class (\w+):", hpp, re.M))
    check(defined == nz_food.ITEM_CLASSES, f"food.hpp defines the {len(nz_food.ITEM_CLASSES)} food classes")
    bases = {i.base for i in items} | {i.opened for i in items if i.opened}
    check(all(b.lower() in vanilla for b in bases), "every food item inherits a vanilla class")
    missing = [i.key for i in items if not (MAP_DIR / "data" / "food" / f"{i.key}.png").exists()
               or nz_food.item_texture(i) not in hpp]
    check(not missing, f"{len(items)} food label textures" + (f" (missing: {missing})" if missing else ""))
    sizes = {i.key: Image.open(MAP_DIR / "data" / "food" / f"{i.key}.png").size for i in items if i.key not in missing}
    check(all(sizes[i.key] == nz_food.LAYOUTS[i.layout][1] for i in items if i.key in sizes),
          "food textures match their vanilla layout size")
    checklist = (MAP_DIR / "docs" / "IN_GAME_TEST_CHECKLIST.md").read_text(encoding="utf-8")
    check(all(f"`{i.cls}`" in checklist for i in items), "the in-game test checklist lists every food item")
    own = sorted({i.model for i in items if i.model})
    gaps = [f"{m}{part}" for m in own for part in (".obj", "_lod1.obj", "_lod2.obj", "_geometry.obj")
            if not (MAP_DIR / "docs" / "models" / f"{m}{part}").exists()]
    gaps += [f"{m}{ext}" for m in own for ext in (".png", ".rvmat") if not (MAP_DIR / "data" / "food" / "models" / f"{m}{ext}").exists()]
    ready = [m for m in own if (MAP_DIR / nz_food.MODELS[m]["p3d"]).exists()]
    check(not gaps, f"{len(own)} custom drink model sources (tools/drink_models.py)"
          + (f" (missing: {', '.join(gaps)})" if gaps else "") + (f"; built: {', '.join(ready)}" if ready else
                                                                  "; waiting for the .p3d, so the vanilla can stands in"))
    tins = [i for i in items if i.opened]
    check(all(f'ReplaceEdibleWithNew("{i.cls}_Opened")' in script for i in tins),
          f"{len(tins)} tins open into their own opened class")
    wip_cfg = MAP_DIR / "wip" / "food" / "config.cpp"
    wip = set(re.findall(r"^\tclass (AotearoaWIP_\w+):", wip_cfg.read_text(encoding="utf-8"), re.M)) if wip_cfg.exists() else set()
    check(wip == {c.replace("Aotearoa_", "AotearoaWIP_", 1) for c in nz_food.ITEM_CLASSES},
          "the work-in-progress food copy (wip/food/) matches the food items; run tools/wip_food.py")
    path = MISSION / "aotearoa" / "food_stashes.json"
    stashes = json.loads(path.read_text(encoding="utf-8"))["stashes"] if path.exists() else []
    bad = [s["label"] for s in stashes if not s["items"] or not set(s["items"]) <= nz_food.ITEM_CLASSES
           or not 0 < s["minItems"] <= s["maxItems"]]
    check(bool(stashes) and not bad, f"{len(stashes)} food stashes hold New Zealand food"
          + (f" (bad: {bad[:3]})" if bad else ""))
    check("aotearoa/food_stashes.json" in (MISSION / "init.c").read_text(encoding="utf-8"),
          "init.c restocks the food stashes")
    path = MISSION / "aotearoa" / "dynamic_events.json"
    events = json.loads(path.read_text(encoding="utf-8"))["events"] if path.exists() else []
    known = _names(MAP_DIR / "tools" / "dayz_classes.txt")
    used = {o["cls"] for e in events for s in e["sites"] for o in s["objects"]}
    used |= {i for e in events for s in e["sites"] for i in s["loot"]["items"]}
    bad = sorted(c for c in used if c.lower() not in known and c not in nz_food.ITEM_CLASSES)
    empty = [e["label"] for e in events if len(e["sites"]) < e["active"]]
    check(bool(events) and not bad and not empty, f"{len(events)} dynamic events, "
          f"{sum(len(e['sites']) for e in events)} sites, {len(used)} classes exist"
          + (f" (unknown: {', '.join(bad[:5])})" if bad else "") + (f" (too few sites: {empty})" if empty else ""))
    check("aotearoa/dynamic_events.json" in (MISSION / "init.c").read_text(encoding="utf-8"),
          "init.c starts the dynamic events")


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
    version = (MAP_DIR / "VERSION").read_text().strip()
    mv = re.search(r'version\s*=\s*"([^"]+)"', (MAP_DIR / "mod" / "mod.cpp").read_text())
    check(bool(mv) and mv.group(1) == version, f"mod.cpp version {mv.group(1) if mv else '?'} matches VERSION {version}")
    check(f"## {version} " in (MAP_DIR / "CHANGELOG.md").read_text(encoding="utf-8"), f"CHANGELOG.md has a {version} section")
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
        # The Interislander wreck and the Harbour Bridge stand in the sea on purpose.
        wet = sum(ground(o["pos"][0], o["pos"][2]) < 0.0 for o in objs
                  if not re.search(r"Ship_Big|Bridge_Metal", o["name"]))
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

    print("Trader sites")
    traders = json.loads((MISSION / "aotearoa" / "traders_spawner.json").read_text(encoding="utf-8"))["Objects"]
    check(bool(traders) and all(on_map(o["pos"][0], o["pos"][2]) and ground(o["pos"][0], o["pos"][2]) > 0.0
                                for o in traders), f"{len(traders)} trader compound objects, all on land")
    mods = MAP_DIR / "mission" / "mods"
    zones = [json.loads(f.read_text(encoding="utf-8")) for f in (mods / "expansion" / "profiles" / "ExpansionMod" / "TraderZones").glob("*.json")]
    maps = list((mods / "expansion" / "mpmissions" / "dayzOffline.aotearoa" / "expansion" / "traders").glob("*.map"))
    check(len(zones) == len(maps) >= 3, f"{len(zones)} Expansion trader zones and {len(maps)} trader files")
    circles = json.loads((mods / "expansion" / "snippets" / "SafeZoneSettings.CircleZones.json").read_text(encoding="utf-8"))
    ev_pos = [(float(p.get("x")), float(p.get("z"))) for ev in events.iter("event") if ev.get("name").startswith("Vehicle")
              for p in ev.iter("pos")]
    inside = sum(any(math.hypot(x - c["Center"][0], y - c["Center"][2]) < c["Radius"] for c in circles) for x, y in ev_pos)
    check(inside == 0, f"no vehicle spawns inside the {len(circles)} safe zones ({inside} found)")

    print("Signs and models")
    signs = json.loads((MISSION / "aotearoa" / "signs_spawner.json").read_text(encoding="utf-8"))["Objects"]
    posts = json.loads((MISSION / "aotearoa" / "roadsigns_spawner.json").read_text(encoding="utf-8"))["Objects"]
    hpp = (MAP_DIR / "config" / "signs.hpp").read_text(encoding="utf-8")
    classes = set(re.findall(r"class (Land_Aotearoa_Sign_\w+):", hpp)) - {"Land_Aotearoa_Sign_Base"}
    post_classes = set(re.findall(r"class (Land_Aotearoa_SignPost_\w+):", hpp)) - {"Land_Aotearoa_SignPost_Base"}
    check(bool(posts) and all(o["name"] in post_classes for o in posts), f"{len(posts)} road signs, all with a config class")
    check(all(on_map(o["pos"][0], o["pos"][2]) and ground(o["pos"][0], o["pos"][2]) > 0.0 for o in posts),
          "road signs all on land")
    check(all((MAP_DIR / "data" / "signs" / f"post_{c.removeprefix('Land_Aotearoa_SignPost_')}.png").exists()
              for c in post_classes), f"{len(post_classes)} road sign textures in data/signs")
    for name in ("sign_town", "sign_post", "bach", "doc_hut", "woolshed", "dairy"):
        check((MAP_DIR / "docs" / "models" / f"{name}.obj").exists(), f"docs/models/{name}.obj")
    check(all((MAP_DIR / "data" / "signs" / f"{n}.rvmat").exists() for n in ("sign_town", "sign_post"))
          and (MAP_DIR / "docs" / "models" / "SIGNS_BRIEF.md").exists(), "sign materials and modeller brief")
    check('#include "config\\structures.hpp"' in cfg, "config.cpp includes config\\structures.hpp")
    check(bool(signs) and all(o["name"] in classes for o in signs), f"{len(signs)} signs, all with a config class")
    check(all(on_map(o["pos"][0], o["pos"][2]) and ground(o["pos"][0], o["pos"][2]) > 0.0 for o in signs),
          "signs all on land")
    textures = {c.removeprefix("Land_Aotearoa_Sign_") for c in classes}
    check(all((MAP_DIR / "data" / "signs" / f"sign_{t}.png").exists() for t in textures),
          f"{len(textures)} sign textures in data/signs")
    check('#include "config\\signs.hpp"' in cfg, "config.cpp includes config\\signs.hpp")
    named = {r["name"] for r in csv.DictReader((SOURCE / "towns.csv").open(encoding="utf-8")) if r["tier"] != "hamlet"}
    signed = {o["name"] for o in signs}
    check(len(signed) == len(named), f"{len(signed)}/{len(named)} named towns have a sign")

    print("Map item")
    item_cfg = (MAP_DIR / "mapitem" / "config.cpp").read_text(encoding="utf-8")
    check("class AotearoaMap: ChernarusMap" in item_cfg, "mapitem/config.cpp defines AotearoaMap from ChernarusMap")
    check("class AotearoaMap extends ChernarusMap" in (MAP_DIR / "mapitem" / "scripts" / "4_World" / "AotearoaMap.c")
          .read_text(encoding="utf-8"), "mapitem/scripts/4_World/AotearoaMap.c")
    textures = ["closed", "opened", "legend"]
    check(all((MAP_DIR / "mapitem" / "data" / f"aotearoa_map_{t}.png").exists() for t in textures),
          "map item textures in mapitem/data (tools/build_map_item.py)")
    check(all(f"mapitem\\aotearoa_map_{t}_co.paa" in cfg and f"aotearoa_map\\data\\aotearoa_map_{t}_co.paa" in item_cfg
              for t in textures), "world and item configs point at the map textures")
    check('name="AotearoaMap"' in (MAP_DIR / "mapitem" / "ce" / "types.xml").read_text(encoding="utf-8"),
          "mapitem/ce/types.xml spawns AotearoaMap")
    names_hpp = (MAP_DIR / "config" / "names.hpp").read_text(encoding="utf-8")
    labelled = {n for n in named} | {p["label"] for p in json.loads((SOURCE / "pois.json").read_text(encoding="utf-8"))
                                     if p["label"]}
    missing = sorted(n for n in labelled if f'"{n}' not in names_hpp)
    check(not missing, f"{len(labelled)} towns and places labelled on the 2D map"
          + (f" (missing: {', '.join(missing[:5])})" if missing else ""))
    features = json.loads((SOURCE / "labels.json").read_text(encoding="utf-8"))
    check(bool(features) and all(f"class {lb['class']}" in names_hpp for lb in features)
          and all(on_map(*lb["xy"]) for lb in features), f"{len(features)} rivers, peaks, water and stations labelled")
    old_types = re.findall(r'type = "(Name\w+)"', names_hpp)
    check(not old_types, "map labels use the DayZ location types" + (f" ({old_types[0]} found)" if old_types else ""))

    groups = {gr.get("name") for gr in ET.parse(MISSION / "cfgeventgroups.xml").getroot().iter("group")}
    used = {p.get("group") for p in ET.parse(MISSION / "cfgeventspawns.xml").getroot().iter("pos") if p.get("group")}
    check(bool(used) and used <= groups, f"{len(used)} event spawns use the {len(groups)} groups in cfgeventgroups.xml"
          + (f" (unknown: {sorted(used - groups)[:3]})" if used - groups else ""))
    zombie_names = {z.get("name") for z in ET.parse(MISSION / "env" / "zombie_territories.xml").getroot().iter("zone")}
    check("InfectedMilitary" not in zombie_names, "infected zones use vanilla names (no InfectedMilitary)")
    pieces = json.loads((SOURCE / "objects" / "setpieces_spawner.json").read_text())["Objects"]
    check(bool(pieces) and all(on_map(o["pos"][0], o["pos"][2]) for o in pieces), f"{len(pieces)} set piece objects on the map")
    check(all((MAP_DIR / "scripts" / d / f).exists() for d, f in (("4_World", "AotearoaData.c"), ("5_Mission", "AotearoaMission.c")))
          and "maps/aotearoa/scripts/4_World" in cfg, "weather and season scripts are in the mod")
    layout = MAP_DIR / "gui" / "layouts" / "aotearoa_map_watermark.layout"
    menu = (MAP_DIR / "scripts" / "5_Mission" / "AotearoaMapMenu.c").read_text(encoding="utf-8")
    check(layout.exists() and "maps/aotearoa/gui/layouts/aotearoa_map_watermark.layout" in menu
          and layout.read_text(encoding="utf-8").count("{") == layout.read_text(encoding="utf-8").count("}"),
          "in-game map watermark layout is in the mod")

    print("Object names")
    object_names()

    print("Loot")
    loot()

    print("Food and drink")
    food()

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        sys.exit(1)
    print("All checks passed")


if __name__ == "__main__":
    main()
