"""Trader posts, safe zones and spawn regions for popular server mods.

Picks four trader sites on flat, open land well away from towns, sites and farms: three safe-zone
trading posts near the State Highways (one in the Waikato, one on the central plateau, one in
Canterbury) and a black market up a back road in the Mackenzie high country. Each gets a fenced
compound of vanilla objects, so it needs no extra mod to appear.

Writes:
  mission/dayzOffline.aotearoa/aotearoa/traders_spawner.json   the compounds (vanilla object spawner)
  mission/mods/expansion/...                                   DayZ Expansion trader NPCs, trader zones,
                                                               safe zones and spawn regions
  mission/mods/traderplus/...                                  TraderPlus traders and safe areas
  mission/mods/README.md                                       the sites and how to install each mod's files
  preview/traders_<site>.png                                   a close-up of each compound (only when run
                                                               on its own, as it reads the full satellite)

build_mission.py runs this before placing vehicles, so no car spawns inside a safe zone.

    python mod_support.py
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

MAP_DIR = Path(__file__).resolve().parents[1]
SOURCE = MAP_DIR / "source"
MISSION = MAP_DIR / "mission" / "dayzOffline.aotearoa"
MODS = MAP_DIR / "mission" / "mods"
SPAWNER = MISSION / "aotearoa" / "traders_spawner.json"

MAP_SIZE_M = 25600.0
SAFE_RADIUS_M = 150.0
TOWN_GAP_M = 350.0  # 250 m for hamlets
SITE_GAP_M = 250.0  # from airfields, ports and every other site; 200 m from farms
FLAT_DEG = 6.0
CLEAR_OF_OBJECTS_M = 45.0
MAX_DRIFT_M = 4000.0  # from the target between the anchor towns
COMPOUND = (60.0, 44.0)  # fence, along x the side facing the road, along y the depth

# (name, anchor towns averaged for the target, kind)
SITES = [
    ("Waikato Trading Post", ("Auckland", "Hamilton"), "trader"),
    ("Central Plateau Trading Post", ("Taupō", "Waiouru Army Camp"), "trader"),
    ("Rakaia Trading Post", ("Christchurch", "Ashburton"), "trader"),
    ("Mackenzie Black Market", ("Twizel",), "black_market"),
]

# Trader stalls: (local x, local y, Expansion trader file, TraderPlus role, NPC class)
STALLS = [
    (-18.0, 8.0, "Weapons", "Weapons", "ExpansionTraderMirek"),
    (0.0, 8.0, "Clothing", "Clothing", "ExpansionTraderDenis"),
    (18.0, 8.0, "Hospital", "Medic", "ExpansionTraderBoris"),
    (-18.0, -10.0, "Building_Supplies", "Building", "ExpansionTraderCyril"),
    (18.0, -12.0, "Vehicles", "Vehicles", "ExpansionTraderElias"),
    (0.0, -12.0, "Aotearoa_Navigation", "Navigation", "ExpansionTraderLewis"),
]
BLACK_MARKET_STALLS = [
    (-10.0, 6.0, "Black_Market", "BlackMarket", "ExpansionTraderFrancis"),
    (10.0, 6.0, "Weapons", "Weapons", "ExpansionTraderGuo"),
]
NPC_GEAR = "TShirt_Green,Jeans_Blue,AthleticShoes_Black,BaseballCap_Black"
# The navigation stall's stock: (class, min price, max price, max stock). AotearoaMap needs @AotearoaMap.
NAVIGATION = [("AotearoaMap", 60, 150, 40), ("Compass", 80, 200, 20), ("OrienteeringCompass", 100, 250, 20),
              ("Binoculars", 150, 400, 15), ("Chemlight_White", 10, 30, 50), ("Flashlight", 40, 100, 20)]


@dataclass
class TraderSite:
    name: str
    kind: str
    x: float
    y: float
    z: float
    yaw: float  # the gate faces this way (towards the road)
    objects: list = field(default_factory=list)  # (class, x, y, yaw)
    npcs: list = field(default_factory=list)  # (npc class, trader file, role, x, y, yaw)

    @property
    def safe(self) -> bool:
        return self.kind == "trader"


def _local(site_x, site_y, yaw, lx, ly):
    """Local compound coordinates (x across the gate, y towards the gate) to world."""
    a = math.radians(yaw)
    fx, fy = math.sin(a), math.cos(a)  # towards the gate
    rx, ry = fy, -fx  # to the right, facing the gate
    return site_x + rx * lx + fx * ly, site_y + ry * lx + fy * ly


def _compound(site: TraderSite) -> None:
    w, d = COMPOUND if site.kind == "trader" else (36.0, 26.0)
    put = lambda cls, lx, ly, turn=0.0: site.objects.append((cls, *_local(site.x, site.y, site.yaw, lx, ly),
                                                             (site.yaw + turn) % 360))
    panel = 5.0
    for side, (length, fixed, along_x) in {"front": (w, d / 2, True), "back": (w, -d / 2, True),
                                           "left": (d, -w / 2, False), "right": (d, w / 2, False)}.items():
        n = int(length // panel)
        for i in range(n):
            t = -length / 2 + panel * (i + 0.5)
            if side == "front" and abs(t) < 6.0:  # the gate
                continue
            if along_x:
                put("Land_Wall_Fen1_5", t, fixed, 90.0)
            else:
                put("Land_Wall_Fen1_5", fixed, t, 0.0)
    stalls = STALLS if site.kind == "trader" else BLACK_MARKET_STALLS
    for lx, ly, file, role, npc in stalls:
        if file == "Vehicles":
            put("Land_Shed_W4", lx, ly, 0.0)
        else:
            put("Land_Mil_Tent_Big1_1", lx, ly, 90.0)
        nx, ny = _local(site.x, site.y, site.yaw, lx, ly + 5.5)
        site.npcs.append((npc, file, role, nx, ny, site.yaw))
    if site.kind == "trader":
        put("Land_Container_1Bo", -24.0, -17.0, 90.0)
        put("Land_Container_1Mo", -16.0, -17.0, 90.0)
        put("Land_Tank_Medium", 25.0, 15.0)
    else:
        put("Land_Container_1Aoh", 0.0, -8.0, 90.0)


def _load():
    meta = json.loads((SOURCE / "heightmap.json").read_text())
    raw = np.asarray(Image.open(SOURCE / "heightmap_4096.png")).astype(np.float32)
    h = meta["png_black_m"] + raw / 65535.0 * (meta["png_white_m"] - meta["png_black_m"])
    with (SOURCE / "towns.csv").open(encoding="utf-8") as f:
        towns = list(csv.DictReader(f))
    roads = json.loads((SOURCE / "roads.json").read_text(encoding="utf-8"))
    pois = json.loads((SOURCE / "pois.json").read_text(encoding="utf-8"))
    return meta, h, towns, roads, pois


def choose_sites(h, towns, roads, pois, cell, size_m) -> list[TraderSite]:
    gy, gx = np.gradient(h, cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    # Flat over the whole compound: the worst slope within 40 m.
    flat = ndimage.maximum_filter(slope, size=int(80 / cell) | 1) < FLAT_DEG
    ok = flat & (h > 5.0) & (h < 900.0)
    road_px = np.zeros_like(ok)
    hw_px = np.zeros_like(ok)
    for r in roads["roads"]:
        for x, y in r["points"]:
            rr, cc = int((size_m - y) / cell), int(x / cell)
            if 0 <= rr < ok.shape[0] and 0 <= cc < ok.shape[1]:
                road_px[rr, cc] = True
                if r["kind"] == "highway":
                    hw_px[rr, cc] = True
    for line in roads.get("rails", []):
        pts = np.array(line["points"], dtype=float)
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            for t in np.linspace(0, 1, int(math.hypot(bx - ax, by - ay) / cell) + 2):
                rr, cc = int((size_m - (ay + (by - ay) * t)) / cell), int((ax + (bx - ax) * t) / cell)
                if 0 <= rr < ok.shape[0] and 0 <= cc < ok.shape[1]:
                    road_px[rr, cc] = True
    to_road = ndimage.distance_transform_edt(~road_px) * cell
    to_hw = ndimage.distance_transform_edt(~hw_px) * cell
    water = h < 0.5
    to_water = ndimage.distance_transform_edt(~water) * cell
    ok &= (to_road > 45.0) & (to_water > 80.0)
    avoid = [(float(t["x"]), float(t["y"]), float(t["radius"]) + (250.0 if t["tier"] == "hamlet" else TOWN_GAP_M))
             for t in towns]
    avoid += [(p["x"], p["y"], p.get("radius", 50.0) + (200.0 if p["kind"] == "farm" else SITE_GAP_M)) for p in pois]
    T = {t["name"]: t for t in towns}
    rows, cols = np.nonzero(ok[::4, ::4])
    rows, cols = rows * 4, cols * 4
    xs, ys = (cols + 0.5) * cell, size_m - (rows + 0.5) * cell
    clutter = world_objects()
    keep = np.ones(len(xs), dtype=bool)
    if clutter is not None:
        keep &= clutter.query(np.column_stack([xs, ys]))[0] > CLEAR_OF_OBJECTS_M
    for ax, ay, ar in avoid:
        keep &= np.hypot(xs - ax, ys - ay) > ar
    out = []
    for name, anchors, kind in SITES:
        tx = np.mean([float(T[a]["x"]) for a in anchors])
        ty = np.mean([float(T[a]["y"]) for a in anchors])
        if kind == "trader":
            reach = (to_hw[rows, cols] > 70.0) & (to_hw[rows, cols] < 450.0)
        else:
            reach = (to_hw[rows, cols] > 800.0) & (to_road[rows, cols] < 600.0)
        cand = np.nonzero(keep & reach)[0]
        dist = np.hypot(xs[cand] - tx, ys[cand] - ty)
        if not len(cand) or dist.min() > MAX_DRIFT_M:
            raise SystemExit(f"No spot for {name} within {MAX_DRIFT_M:.0f} m of its target")
        i = cand[np.argmin(dist)]
        x, y = float(xs[i]), float(ys[i])
        # Face the gate towards the nearest road point.
        best, gate = 1e18, 0.0
        for r in roads["roads"]:
            if kind == "trader" and r["kind"] != "highway":
                continue
            for px, py in r["points"]:
                dd = (px - x) ** 2 + (py - y) ** 2
                if dd < best:
                    best, gate = dd, math.degrees(math.atan2(px - x, py - y)) % 360
        out.append(TraderSite(name, kind, x, y, 0.0, round(gate / 5) * 5 % 360))
    return out


def world_objects():
    """Every Terrain Builder object (trees, rocks, hedges, fences, poles, buildings) as a KD-tree."""
    from scipy.spatial import cKDTree

    meta = json.loads((SOURCE / "heightmap.json").read_text())
    pts = []
    for f in (SOURCE / "objects").glob("*_tb.txt"):
        for line in f.read_text(encoding="utf-8").splitlines():
            parts = line.split(";")
            if len(parts) > 2:
                pts.append((float(parts[1]) - meta["easting"], float(parts[2]) - meta["northing"]))
    return cKDTree(pts) if pts else None


def _ground(h, x, y, cell, size_m):
    fc, fr = x / cell, (size_m - y) / cell
    c0, r0 = int(np.clip(fc, 0, h.shape[1] - 2)), int(np.clip(fr, 0, h.shape[0] - 2))
    tc, tr = fc - c0, fr - r0
    return float((h[r0, c0] * (1 - tc) + h[r0, c0 + 1] * tc) * (1 - tr) +
                 (h[r0 + 1, c0] * (1 - tc) + h[r0 + 1, c0 + 1] * tc) * tr)


def build(h, towns, roads, pois, cell, size_m) -> list[TraderSite]:
    sites = choose_sites(h, towns, roads, pois, cell, size_m)
    for s in sites:
        s.z = _ground(h, s.x, s.y, cell, size_m)
        _compound(s)
    g = lambda x, y: round(_ground(h, x, y, cell, size_m), 3)

    SPAWNER.parent.mkdir(parents=True, exist_ok=True)
    SPAWNER.write_text(json.dumps({"Objects": [
        {"name": cls, "pos": [round(x, 2), g(x, y), round(y, 2)], "ypr": [round(yaw, 1), 0.0, 0.0], "scale": 1.0,
         "enableCEPersistency": 0}
        for s in sites for cls, x, y, yaw in s.objects]}, indent=1) + "\n", encoding="utf-8")
    write_expansion(sites, g)
    write_traderplus(sites, g)
    write_readme(sites)
    return sites


FOOT = {"Land_Mil_Tent_Big1_1": (6.0, 12.0), "Land_Shed_W4": (9.0, 12.0), "Land_Container_1Bo": (2.5, 6.0),
        "Land_Container_1Mo": (2.5, 6.0), "Land_Container_1Aoh": (2.5, 6.0), "Land_Tank_Medium": (5.0, 5.0),
        "Land_Wall_Fen1_5": (0.3, 5.0)}


def preview(sites, roads, size_m) -> None:
    from PIL import ImageDraw

    sat_path = SOURCE / "satellite_25600.png"
    if not sat_path.exists():
        print("  (no source/satellite_25600.png, so no previews)")
        return
    Image.MAX_IMAGE_PIXELS = None
    sat = Image.open(sat_path).convert("RGB")
    k_sat = sat.width / size_m
    for s in sites:
        half = 60.0
        box = [int((s.x - half) * k_sat), int((size_m - s.y - half) * k_sat),
               int((s.x + half) * k_sat), int((size_m - s.y + half) * k_sat)]
        im = sat.crop(box).resize((480, 480), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        k = 480 / (2 * half)
        P = lambda x, y: ((x - s.x + half) * k, (s.y - y + half) * k)
        for r in roads["roads"]:
            pts = [P(x, y) for x, y in r["points"]]
            d.line(pts, fill=(250, 210, 80) if r["kind"] == "highway" else (220, 220, 220), width=int(5 * k))
        if s.safe:
            c = P(s.x, s.y)
            d.ellipse([c[0] - SAFE_RADIUS_M * k, c[1] - SAFE_RADIUS_M * k, c[0] + SAFE_RADIUS_M * k,
                       c[1] + SAFE_RADIUS_M * k], outline=(80, 200, 255), width=2)
        for cls, x, y, yaw in s.objects:
            w, l = FOOT.get(cls, (3.0, 3.0))
            a = math.radians(yaw)
            ux, uy, vx, vy = math.sin(a), math.cos(a), math.cos(a), -math.sin(a)
            pts = [P(x + ux * l / 2 * i + vx * w / 2 * j, y + uy * l / 2 * i + vy * w / 2 * j)
                   for i, j in ((1, 1), (1, -1), (-1, -1), (-1, 1))]
            d.polygon(pts, fill=(120, 120, 110) if cls != "Land_Wall_Fen1_5" else (60, 60, 60),
                      outline=(30, 30, 30))
        for npc, file, role, x, y, yaw in s.npcs:
            a, b = P(x, y)
            d.ellipse([a - 4, b - 4, a + 4, b + 4], fill=(255, 60, 60))
            d.text((a + 6, b - 6), role, fill=(255, 255, 255))
        d.text((8, 8), s.name, fill=(255, 255, 255))
        im.save(MAP_DIR / "preview" / f"traders_{_slug(s.name).lower()}.png", optimize=True)


def safe_zones(sites: list[TraderSite]) -> list[tuple[float, float, float]]:
    return [(s.x, s.y, SAFE_RADIUS_M) for s in sites if s.safe]


def _slug(name: str) -> str:
    return name.replace(" ", "")


def write_expansion(sites, g) -> None:
    root = MODS / "expansion"
    traders = root / "mpmissions" / "dayzOffline.aotearoa" / "expansion" / "traders"
    zones = root / "profiles" / "ExpansionMod" / "TraderZones"
    for d in (traders, zones):
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*"):
            old.unlink()
    for s in sites:
        lines = [f"{npc}.{file}|{x:.3f} {g(x, y):.3f} {y:.3f}|{yaw % 360:.1f} 0.0 0.0|{NPC_GEAR}"
                 for npc, file, role, x, y, yaw in s.npcs]
        (traders / f"Aotearoa_{_slug(s.name)}.map").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (zones / f"Aotearoa_{_slug(s.name)}.json").write_text(json.dumps({
            "m_Version": 7,
            "m_DisplayName": s.name,
            "m_ZoneName": f"Aotearoa_{_slug(s.name)}",
            "Position": [round(s.x, 2), round(s.z, 2), round(s.y, 2)],
            "Radius": SAFE_RADIUS_M if s.safe else 60.0,
            "BuyPricePercent": 100.0 if s.safe else 130.0,
            "SellPricePercent": -1.0,
            "Stock": {},
        }, indent=4) + "\n", encoding="utf-8")
    market = root / "profiles" / "ExpansionMod" / "Market"
    trader_defs = root / "profiles" / "ExpansionMod" / "Traders"
    for d in (market, trader_defs):
        d.mkdir(parents=True, exist_ok=True)
    (market / "Aotearoa_Navigation.json").write_text(json.dumps({
        "m_Version": 12,
        "DisplayName": "Maps and Navigation",
        "Icon": "Deliver",
        "Color": "FBFCFEFF",
        "IsExchange": 0,
        "InitStockPercent": 75.0,
        "Items": [{"ClassName": cls.lower(), "MaxPriceThreshold": hi, "MinPriceThreshold": lo,
                   "SellPricePercent": -1.0, "MaxStockThreshold": stock, "MinStockThreshold": 1,
                   "QuantityPercent": -1, "SpawnAttachments": [], "Variants": []}
                  for cls, lo, hi, stock in NAVIGATION],
    }, indent=4) + "\n", encoding="utf-8")
    (trader_defs / "Aotearoa_Navigation.json").write_text(json.dumps({
        "m_Version": 12,
        "DisplayName": "Navigation",
        "MinRequiredReputation": 0,
        "MaxRequiredReputation": 2147483647,
        "RequiredFaction": "",
        "RequiredCompletedQuestID": -1,
        "TraderIcon": "Map",
        "Currencies": [],
        "DisplayCurrencyValue": 1,
        "DisplayCurrencyName": "",
        "UseCategoryOrder": 0,
        "Categories": ["Aotearoa_Navigation"],
        "Items": {},
    }, indent=4) + "\n", encoding="utf-8")
    snippets = root / "snippets"
    snippets.mkdir(exist_ok=True)
    (snippets / "SafeZoneSettings.CircleZones.json").write_text(json.dumps([
        {"Center": [round(s.x, 2), round(s.z, 2), round(s.y, 2)], "Radius": SAFE_RADIUS_M} for s in sites if s.safe
    ], indent=4) + "\n", encoding="utf-8")
    (snippets / "SpawnSettings.SpawnLocations.json").write_text(json.dumps(spawn_regions(g), indent=4) + "\n",
                                                               encoding="utf-8")


def spawn_regions(g) -> list[dict]:
    """The coastal player spawns grouped by the nearest city, for Expansion's spawn selection screen."""
    import xml.etree.ElementTree as ET

    spawns = [(float(p.get("x")), float(p.get("z")))
              for p in ET.parse(MISSION / "cfgplayerspawnpoints.xml").getroot().find("fresh").iter("pos")]
    with (SOURCE / "towns.csv").open(encoding="utf-8") as f:
        cities = [t for t in csv.DictReader(f) if t["tier"] in ("capital", "city")]
    regions: dict[str, list] = {}
    for x, y in spawns:
        c = min(cities, key=lambda t: math.hypot(x - float(t["x"]), y - float(t["y"])))
        regions.setdefault(f"{c['name']} coast", []).append([round(x, 1), g(x, y), round(y, 1)])
    return [{"Name": name, "Positions": pos, "UseCooldown": 1} for name, pos in sorted(regions.items())]


def write_traderplus(sites, g) -> None:
    root = MODS / "traderplus" / "snippets"
    root.mkdir(parents=True, exist_ok=True)
    traders, n = [], 0
    for s in sites:
        for npc, file, role, x, y, yaw in s.npcs:
            traders.append({"Id": n, "Name": "SurvivorM_Mirek", "GivenName": f"{s.name} {role}", "Role": role,
                            "Position": [round(x, 2), g(x, y), round(y, 2)],
                            "Orientation": [round(yaw % 360, 1), 0.0, 0.0],
                            "Clothes": NPC_GEAR.split(",")})
            n += 1
    (root / "TraderPlusGeneralConfig.Traders.json").write_text(json.dumps(traders, indent=4) + "\n", encoding="utf-8")
    # TraderPlus products: "class,coefficient,max stock,trade quantity,buy price,sell price".
    (root / "TraderPlusPriceConfig.TraderCategories.json").write_text(json.dumps([{
        "CategoryName": "Aotearoa Navigation",
        "Products": [f"{cls},1,{stock},1,{hi},{lo}" for cls, lo, hi, stock in NAVIGATION],
    }], indent=4) + "\n", encoding="utf-8")
    (root / "TraderPlusSafeAreaConfig.SafeAreaLocation.json").write_text(json.dumps([
        {"SafeZoneStatut": s.name, "X": round(s.x, 2), "Y": round(s.y, 2), "Radius": SAFE_RADIUS_M, "Countdown": 30}
        for s in sites if s.safe], indent=4) + "\n", encoding="utf-8")


def write_readme(sites) -> None:
    rows = "\n".join(f"| {s.name} | {'safe zone, ' + str(int(SAFE_RADIUS_M)) + ' m' if s.safe else 'no safe zone (PvP)'} "
                     f"| {s.x:.0f} / {s.y:.0f} | {int(s.x // 1000):02d} {int((MAP_SIZE_M - s.y) // 1000):02d} | "
                     f"{', '.join(n[2] for n in s.npcs)} |" for s in sites)
    (MODS / "README.md").write_text(f"""# Mod support

Generated by `tools/mod_support.py`; rerun `python tools/build_mission.py` to regenerate.

## Trader sites

Map grid squares count across from the west and down from the north, as on the in-game map.

| Site | Type | x / y (m) | Map grid | Stalls |
|---|---|---|---|---|
{rows}

Each site has a fenced compound of vanilla objects (tents, a vehicle shed, containers) in
`dayzOffline.aotearoa/aotearoa/traders_spawner.json`. Vehicle spawns are kept out of the safe zones.

## Any server: just the compounds

`pack.bat --traders` adds the compound spawner to `cfggameplay.json`. No mod needed; useful as meeting
points or for traders you place yourself.

## DayZ Expansion (Market, Basebuilding, Groups)

`pack.bat --expansion` (implies `--traders`) copies:

- `expansion/mpmissions/dayzOffline.aotearoa/expansion/traders/*.map`: the trader NPCs. Each line is
  `NpcClass.TraderFile|x y z|yaw pitch roll|clothing`. The trader file names (`Weapons`, `Clothing`,
  `Hospital`, `Building_Supplies`, `Vehicles`, `Black_Market`) must match files in
  `profiles/ExpansionMod/Traders/`; rename them here or there to fit your market setup.
- `expansion/profiles/ExpansionMod/Traders/Aotearoa_Navigation.json` and
  `Market/Aotearoa_Navigation.json`: the navigation stall at each trading post, selling the
  `AotearoaMap` (from `@AotearoaMap`), compasses, binoculars, chemlights and torches.
- `expansion/profiles/ExpansionMod/TraderZones/*.json`: one trader zone per site (the black market
  charges 30% more).

Two files Expansion owns are not overwritten; paste these arrays in by hand after the first start:

- `snippets/SafeZoneSettings.CircleZones.json` into `CircleZones` in
  `profiles/ExpansionMod/Settings/SafeZoneSettings.json`.
- `snippets/SpawnSettings.SpawnLocations.json` into `SpawnLocations` in
  `profiles/ExpansionMod/Settings/SpawnSettings.json`; it groups the 40 coastal spawns by the nearest
  city for the spawn selection screen.

The formats follow Expansion 1.8. If yours differs, compare with the files your server writes on first
start; the positions are what matter.

## TraderPlus

Paste `traderplus/snippets/TraderPlusGeneralConfig.Traders.json` into `Traders` in
`profiles/TraderPlus/TraderPlusConfig/TraderPlusGeneralConfig.json`, and
`traderplus/snippets/TraderPlusSafeAreaConfig.SafeAreaLocation.json` into `SafeAreaLocation` in
`TraderPlusSafeAreaConfig.json`. Match each `Role` to a category set in your TraderPlus price config.
Add `traderplus/snippets/TraderPlusPriceConfig.TraderCategories.json` to `TraderCategories` in
`TraderPlusPriceConfig.json` and give the `Navigation` traders that category; it sells the `AotearoaMap`.
Run with `pack.bat --traders` for the compounds.

## Code Lock, BaseBuildingPlus and similar

They need nothing map-specific. Add them to `-mod=` in `start_server.bat` / `start_server.sh` and to the
clients' launcher, and put their `.bikey` in `keys/`.
""", encoding="utf-8")


def main() -> None:
    meta, h, towns, roads, pois = _load()
    sites = build(h, towns, roads, pois, meta["cell_size_m"], meta["terrain_size_m"])
    preview(sites, roads, meta["terrain_size_m"])
    for s in sites:
        print(f"{s.name}: {s.x:.0f}, {s.y:.0f}, {s.z:.0f} m up, gate facing {s.yaw:.0f}, "
              f"{len(s.objects)} objects, {len(s.npcs)} traders")


if __name__ == "__main__":
    main()
