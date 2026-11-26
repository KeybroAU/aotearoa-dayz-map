"""Loot, animals and weather for the Aotearoa mission.

Called from build_mission.py. Writes into mission/dayzOffline.aotearoa/:

  mapgrouppos.xml               every town and site building, so loot spawns before the first
                                ExportProxyData run (that run replaces it with exact positions)
  aotearoa_ce/types.xml         New Zealand loot changes, loaded after vanilla db/types.xml
  cfgeconomycore.aotearoa.xml   the <ce> block that loads aotearoa_ce
  loot_tiers.json               the loot tier of every town and site
  env/*_territories.xml         animal herds: sheep and cattle on the farms, feral goats on steep
                                country, red deer mostly in the back country; no wolves, bears,
                                roe deer or foxes
  cfgweather.xml                windy, changeable New Zealand weather

plus preview/loot_tiers_2048.png, the tier map to paint into the Value layer.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

import generate_terrain as g

TIER_COLOURS = {1: (60, 170, 60), 2: (230, 210, 60), 3: (240, 130, 40), 4: (210, 40, 40)}

# New Zealand loot changes, applied on top of the vanilla entry of the same name
# (tools/vanilla_types.xml): name: (nominal, min, usages, values). usages or values None keeps
# vanilla's; [] values means every tier. Everything else (lifetime, quantities, flags, tags) stays
# vanilla. Refresh the vanilla copy with tools/refresh_vanilla_types.py.
ALL = ["Tier1", "Tier2", "Tier3", "Tier4"]
NZ_TYPES = {
    # Deer stalking and pest control: hunting rifles and shotguns on every farm.
    "Winchester70": (20, 12, ["Hunting", "Farm"], ["Tier2", "Tier3", "Tier4"]),
    "CZ527": (25, 18, ["Farm", "Hunting"], ["Tier2", "Tier3", "Tier4"]),
    "Mag_CZ527_5rnd": (30, 20, ["Farm", "Hunting"], None),
    "Ruger1022": (35, 25, ["Farm", "Village", "Town"], ["Tier1", "Tier2"]),
    "Izh18": (45, 35, ["Farm", "Village", "Hunting"], ["Tier1", "Tier2", "Tier3"]),
    "Repeater": (25, 18, ["Farm", "Hunting"], ["Tier2", "Tier3"]),
    "Mosin9130": (25, 18, ["Hunting", "Village"], ["Tier2", "Tier3", "Tier4"]),
    "SKS": (8, 4, ["Hunting"], ["Tier3", "Tier4"]),
    "Izh43Shotgun": (35, 28, ["Farm", "Village"], ["Tier1", "Tier2", "Tier3"]),
    "Mp133Shotgun": (12, 8, ["Police", "Farm"], ["Tier2", "Tier3", "Tier4"]),
    "Ammo_308Win": (60, 40, ["Farm", "Hunting", "Village"], None),
    "Ammo_22": (100, 80, ["Town", "Village", "Farm", "Hunting"], None),
    "Ammo_12gaPellets": (110, 85, None, None),
    # NZDF: the Steyr AUG was the service rifle, the M4 pattern MARS-L replaced it, the L1A1 (FAL) before.
    "AugShort": (8, 5, ["Military"], ["Tier3", "Tier4"]),
    "Aug": (5, 3, ["Military"], ["Tier4"]),
    "Mag_Aug_30Rnd": (12, 8, ["Military"], ["Tier3", "Tier4"]),
    "M4A1": (5, 3, ["Military"], ["Tier4"]),
    "Mag_STANAG_30Rnd": (10, 6, ["Military"], ["Tier3", "Tier4"]),
    "FAL": (3, 1, ["Military"], ["Tier4"]),
    "Mag_FAL_20Rnd": (6, 3, ["Military"], ["Tier4"]),
    "AKM": (2, 1, ["Military"], ["Tier4"]),
    "SVD": (1, 1, ["Military"], ["Tier4"]),
    # Handguns are rare in New Zealand; the police carry Glocks.
    "Glock19": (25, 18, ["Police"], ALL),
    "MKII": (20, 14, ["Town", "Village", "Farm"], ["Tier1", "Tier2"]),
    "CZ75": (10, 6, ["Military"], ["Tier2", "Tier3", "Tier4"]),
    "Deagle": (4, 2, ["Town"], ["Tier2", "Tier3"]),
    # Dairy country, mānuka honey, kaimoana and tramping-hut food.
    "Honey": (30, 22, ["Farm", "Village", "Town"], ["Tier1", "Tier2", "Tier3"]),
    "PowderedMilk": (30, 22, ["Farm", "Town", "Village"], ["Tier1", "Tier2", "Tier3"]),
    "SardinesCan": (30, 20, ["Coast", "Town", "Village"], None),
    "TunaCan": (30, 20, ["Coast", "Town", "Office"], None),
    "PeachesCan": (25, 18, ["Town", "Village", "School"], None),
    "BakedBeansCan": (25, 18, ["Town", "Village", "Hunting"], None),
    "Rice": (25, 18, ["Village", "Town", "Hunting"], None),
    "Marmalade": (25, 18, ["Village", "Town", "School"], None),
    "Tomato": (25, 18, ["Farm", "Village"], None),
    "TomatoSeedsPack": (35, 25, ["Farm"], None),
    # Fishing, fencing and tramping gear.
    "FishingRod": (45, 30, ["Coast", "Village", "Farm"], None),
    "Hook": (60, 45, ["Coast", "Village"], None),
    "HuntingKnife": (60, 50, ["Hunting", "Farm", "Village"], None),
    "Rope": (110, 90, ["Industrial", "Farm"], None),
    "BarbedWire": (80, 60, ["Industrial", "Farm"], None),
    "Compass": (70, 50, ["Hunting", "Military", "Village"], None),
    "Binoculars": (50, 30, ["Hunting", "Military", "Police", "Farm"], None),
    "PortableGasStove": (35, 28, ["Hunting", "Farm", "Village"], None),
    "SmallGasCanister": (40, 30, ["Industrial", "Farm", "Hunting"], None),
    "Canteen": (30, 20, ["Military", "Hunting"], None),
    "MountainBag_Blue": (10, 6, ["Village", "Hunting"], None),
    "MountainBag_Green": (10, 6, ["Village", "Hunting"], None),
    "MountainBag_Orange": (12, 8, ["Village", "Hunting"], None),
    "MountainBag_Red": (12, 8, ["Village", "Hunting"], None),
    # Gumboots, raincoats, wool jumpers and beanies for the weather.
    **{f"Wellies_{c}": (35, 25, ["Farm", "Village"], None) for c in ("Black", "Brown", "Green", "Grey")},
    **{f"Raincoat_{c}": (35, 25, ["Coast", "Town", "Village", "Hunting"], None)
       for c in ("Black", "Blue", "Green", "Orange", "Pink", "Red", "Yellow")},
    **{f"Sweater_{c}": (30, 22, ["Town", "Village", "Farm", "Hunting"], None) for c in ("Blue", "Gray", "Green", "Red")},
    **{f"BeanieHat_{c}": (15, 10, ["Village", "Farm", "Hunting", "Town"], None)
       for c in ("Beige", "Black", "Blue", "Brown", "Green", "Grey", "Pink", "Red")},
    "HikingBoots_Brown": (35, 25, ["Town", "Village", "Hunting"], None),
    "HikingBoots_Black": (35, 25, ["Town", "Village", "Hunting"], None),
    "HuntingJacket_Brown": (20, 12, ["Hunting"], ["Tier2", "Tier3", "Tier4"]),
    "HuntingJacket_Autumn": (22, 14, ["Hunting"], ["Tier2", "Tier3", "Tier4"]),
    "HunterPants_Brown": (20, 12, ["Hunting"], ["Tier2", "Tier3", "Tier4"]),
    "HunterPants_Autumn": (24, 15, ["Hunting"], ["Tier2", "Tier3", "Tier4"]),
}
VANILLA_TYPES = Path(__file__).resolve().parent / "vanilla_types.xml"
# Civilian towns stay at or below this tier, so a town next to a base or high in the Alps doesn't
# get military loot in every house. Military areas reach out MILITARY_RING_M past the base.
TOWN_TIER_CAP = 3
MILITARY_RING_M = 150.0

# Herd settings: (zones per herd, zone radius, smin, smax, dmin, dmax). Goats share the sheep file
# (vanilla's AnimalGoat and AnimalSheep both use sheep_goat_territories).
HERDS = {
    "red_deer": (90, 3, 70.0, 0, 0, 4, 7),
    "wild_boar": (50, 3, 50.0, 0, 0, 3, 6),
    "sheep_goat": (90, 2, 50.0, 0, 0, 4, 8),
    "goat": (40, 2, 40.0, 0, 0, 3, 6),
    "cattle": (45, 2, 50.0, 0, 0, 3, 6),
    "pig": (12, 2, 30.0, 0, 0, 2, 4),
    "hen": (35, 1, 20.0, 0, 0, 3, 6),
    "hare": (60, 1, 40.0, 0, 0, 1, 3),
}
HERD_FILE = {"goat": "sheep_goat"}
# Red deer are a back-country pest: this share of their herds goes above BACK_COUNTRY_M.
DEER_HIGH_SHARE = 0.65
BACK_COUNTRY_M = 100.0  # about 700 m in real heights
NO_ANIMALS = ["wolf", "bear", "fox", "roe_deer", "domestic_animals"]


def south_cells(land: np.ndarray, towns) -> np.ndarray:
    """The South Island plus every islet closer to it than to the North Island (Stewart Island too)."""
    lab, _ = ndimage.label(land)

    def island_of(name):
        t = next(t for t in towns if t["name"] == name)
        return lab == lab[int((g.SIZE_M - float(t["y"])) / g.CELL), int(float(t["x"]) / g.CELL)]

    d_north = ndimage.distance_transform_edt(~island_of("Auckland")[::4, ::4])
    d_south = ndimage.distance_transform_edt(~island_of("Christchurch")[::4, ::4])
    closer = np.repeat(np.repeat(d_south < d_north, 4, axis=0), 4, axis=1)
    return land & closer


def tier_map(h: np.ndarray, land: np.ndarray, towns, pois) -> np.ndarray:
    """Tier 1 on the northern coasts, rising inland, southwards and uphill; military areas are 4 and
    civilian towns at most TOWN_TIER_CAP."""
    south = south_cells(land, towns)
    dist_sea = ndimage.distance_transform_edt(land) * g.CELL
    tier = np.where(dist_sea < 500, 1, np.where(dist_sea < 1500, 2, 3)).astype(np.uint8)
    tier[south] = np.minimum(tier[south] + 1, 4)
    tier[h > 300] = 4
    rows, cols = np.mgrid[0:g.GRID, 0:g.GRID]
    for t in towns:
        if t["tier"] == "military":
            r0, c0 = (g.SIZE_M - float(t["y"])) / g.CELL, float(t["x"]) / g.CELL
            tier[np.hypot(rows - r0, cols - c0) * g.CELL < float(t["radius"]) + MILITARY_RING_M] = 4
    for p in pois:
        if p["kind"] == "naval" or (p["kind"] == "airfield" and "Ōhakea" in p["label"]):
            r0, c0 = (g.SIZE_M - p["y"]) / g.CELL, p["x"] / g.CELL
            tier[np.hypot(rows - r0, cols - c0) * g.CELL < p["radius"] + 60] = 4
    for t in towns:
        if t["tier"] != "military":
            r0, c0 = (g.SIZE_M - float(t["y"])) / g.CELL, float(t["x"]) / g.CELL
            inside = np.hypot(rows - r0, cols - c0) * g.CELL < float(t["radius"]) + 30
            tier[inside] = np.minimum(tier[inside], TOWN_TIER_CAP)
    tier[~land] = 0
    return tier


def tier_at(tier, x, y) -> int:
    r = int(np.clip((g.SIZE_M - y) / g.CELL, 0, g.GRID - 1))
    c = int(np.clip(x / g.CELL, 0, g.GRID - 1))
    return int(tier[r, c])


def write_mapgrouppos(path: Path) -> int:
    objs = []
    for name in ("towns_spawner.json", "pois_spawner.json", "setpieces_spawner.json"):
        src = g.SOURCE_DIR / "objects" / name
        if src.exists():
            objs += json.loads(src.read_text())["Objects"]
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>',
             "<!-- Building positions for Aotearoa, generated by tools/economy.py. Replace with the output of",
             "     ExportProxyData once the world is built (see init.c). -->", "<map>"]
    for o in objs:
        x, z, y = o["pos"]
        # Vanilla writes the spawner yaw as the roll-pitch-yaw z and a = 90 - yaw.
        yaw = o["ypr"][0]
        a = (90.0 - yaw + 180.0) % 360.0 - 180.0
        lines.append(f'    <group name="{o["name"]}" pos="{x:.3f} {z:.3f} {y:.3f}" rpy="0 0 {yaw:.3f}" a="{a:.3f}" />')
    lines += ["</map>", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return len(objs)


def write_types(path: Path) -> None:
    import xml.etree.ElementTree as ET

    vanilla = {e.get("name"): e for e in ET.parse(VANILLA_TYPES).getroot().iter("type")}
    missing = sorted(set(NZ_TYPES) - set(vanilla))
    if missing:
        raise SystemExit(f"Not in {VANILLA_TYPES.name}: {', '.join(missing)}. Run refresh_vanilla_types.py.")
    root = ET.Element("types")
    for name, (nominal, mn, usages, values) in NZ_TYPES.items():
        e = ET.fromstring(ET.tostring(vanilla[name]))
        e.find("nominal").text, e.find("min").text = str(nominal), str(mn)
        for kind, names in (("usage", usages), ("value", values)):
            if names is None:
                continue
            for old in e.findall(kind):
                e.remove(old)
            for n in names:
                ET.SubElement(e, kind, name=n)
        order = ["nominal", "lifetime", "restock", "min", "quantmin", "quantmax", "cost", "flags", "category",
                 "tag", "usage", "value"]
        e[:] = sorted(e, key=lambda c: order.index(c.tag) if c.tag in order else len(order))
        root.append(e)
    ET.indent(root, space="    ")
    body = ET.tostring(root, encoding="unicode")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    "<!-- New Zealand loot changes for Aotearoa, generated by tools/economy.py from the vanilla\n"
                    "     entries. Loaded after db/types.xml through cfgeconomycore.xml, so these replace them. -->\n"
                    + body + "\n", encoding="utf-8")


CORE_SNIPPET = """<!-- Add inside <economycore> in cfgeconomycore.xml to load the New Zealand loot changes. -->
<ce folder="aotearoa_ce">
    <file name="types.xml" type="types" />
</ce>
"""


def herd_sites(kind, h, idx, land, towns, pois, rng) -> list[tuple[float, float]]:
    """Candidate herd centres for one animal, in random order, kept 250 m clear of towns."""
    if kind in ("hen", "pig", "cattle"):
        pts = [(p["x"], p["y"]) for p in pois if p["kind"] == "farm"]
        rng.shuffle(pts)
        return pts
    s = g.SURFACE_INDEX
    step = 8
    gy, gx = np.gradient(h, g.CELL)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    ok = land & (slope < 25)
    if kind == "red_deer":
        cand = ok & ((idx == s["bush"]) | (idx == s["pine"]) | (idx == s["tussock"]))
    elif kind == "wild_boar":
        cand = ok & (idx == s["bush"])
    elif kind == "sheep_goat":
        cand = ok & ((idx == s["pasture"]) | (idx == s["tussock"]))
    elif kind == "goat":
        # Feral goats on the steep bush, tussock and scree that sheep and deer avoid.
        cand = land & (slope >= 15) & (slope < 40) & ((idx == s["bush"]) | (idx == s["tussock"]) | (idx == s["scree"]))
    else:
        cand = ok & ((idx == s["pasture"]) | (idx == s["farmland"]))
    high = (h >= BACK_COUNTRY_M)[::step, ::step]
    cand = cand[::step, ::step]
    rows, cols = np.mgrid[0:cand.shape[0], 0:cand.shape[1]]
    xs, ys = (cols * step + 0.5) * g.CELL, g.SIZE_M - (rows * step + 0.5) * g.CELL
    for t in towns:
        cand &= np.hypot(xs - float(t["x"]), ys - float(t["y"])) > float(t["radius"]) + 250
    rr, cc = np.nonzero(cand)
    order = rng.permutation(len(rr))
    if kind == "red_deer":
        up = [i for i in order if high[rr[i], cc[i]]]
        low = [i for i in order if not high[rr[i], cc[i]]]
        mixed = []
        while up or low:
            pick = up if up and (not low or rng.random() < DEER_HIGH_SHARE) else low
            mixed.append(pick.pop())
        order = mixed
    return [(float(xs[rr[i], cc[i]]), float(ys[rr[i], cc[i]])) for i in order]


def write_territories(env_dir: Path, h, idx, land, towns, pois, rng) -> dict[str, int]:
    env_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    files: dict[str, list[str]] = {}
    for kind, (herds, zones_per, radius, smin, smax, dmin, dmax) in HERDS.items():
        sites = herd_sites(kind, h, idx, land, towns, pois, rng)
        chosen: list[tuple[float, float]] = []
        spacing = 400.0 if kind not in ("hen", "pig", "cattle") else 0.0
        for x, y in sites:
            if len(chosen) >= herds:
                break
            if all(math.hypot(x - a, y - b) >= spacing for a, b in chosen):
                chosen.append((x, y))
        lines = files.setdefault(HERD_FILE.get(kind, kind), [])
        lines.append(f"    <!-- {kind.replace('_', ' ')} -->")
        for x, y in chosen:
            lines.append('    <territory color="4291611852">')
            for k, name in enumerate(["Rest", "Graze", "Graze"][:zones_per] if zones_per > 1 else ["Graze"]):
                a = rng.uniform(0, 2 * math.pi)
                d = 0.0 if k == 0 else rng.uniform(radius, radius * 2.5)
                zx, zy = x + d * math.cos(a), y + d * math.sin(a)
                lines.append(f'        <zone name="{name}" smin="{smin}" smax="{smax}" dmin="{dmin}" dmax="{dmax}" '
                             f'x="{zx:.1f}" z="{zy:.1f}" r="{radius:.0f}" />')
            lines.append("    </territory>")
        counts[kind] = len(chosen)
    for name, body in files.items():
        text = ['<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>',
                f"<!-- {name.replace('_', ' ')} herds for Aotearoa, generated by tools/economy.py. -->",
                "<territory-type>", *body, "</territory-type>", ""]
        (env_dir / f"{name}_territories.xml").write_text("\n".join(text), encoding="utf-8")
    for kind in NO_ANIMALS:
        (env_dir / f"{kind}_territories.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
            f"<!-- No {kind.replace('_', ' ')} in New Zealand. -->\n<territory-type>\n</territory-type>\n",
            encoding="utf-8")
    return counts


WEATHER = """<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<!-- Windy, changeable New Zealand weather for Aotearoa, generated by tools/economy.py.
     Four seasons in one day: overcast changes often, showers are common, wind is rarely calm. -->
<weather reset="0" enable="1">
    <overcast>
        <current actual="0.45" time="120" duration="240" />
        <limits min="0.1" max="1.0" />
        <timelimits min="600" max="1500" />
        <changelimits min="0.1" max="0.8" />
    </overcast>
    <fog>
        <current actual="0.05" time="120" duration="240" />
        <limits min="0.0" max="0.25" />
        <timelimits min="900" max="2400" />
        <changelimits min="0.0" max="0.15" />
    </fog>
    <rain>
        <current actual="0.0" time="60" duration="120" />
        <limits min="0.0" max="0.8" />
        <timelimits min="300" max="1200" />
        <changelimits min="0.0" max="0.6" />
        <thresholds min="0.55" max="1.0" end="120" />
    </rain>
    <windMagnitude>
        <current actual="9.0" time="120" duration="240" />
        <limits min="3.0" max="20.0" />
        <timelimits min="300" max="900" />
        <changelimits min="0.0" max="6.0" />
    </windMagnitude>
    <windDirection>
        <current actual="-0.8" time="120" duration="240" />
        <limits min="-3.14" max="3.14" />
        <timelimits min="600" max="1800" />
        <changelimits min="0.0" max="0.6" />
    </windDirection>
    <snowfall>
        <!-- Off here; scripts/4_World/AotearoaData.c raises the limit in June to August. -->
        <current actual="0.0" time="0" duration="32768" />
        <limits min="0.0" max="0.0" />
        <timelimits min="300" max="3600" />
        <changelimits min="0.0" max="0.5" />
        <thresholds min="0.85" max="1.0" end="120" />
    </snowfall>
    <storm density="1.0" threshold="0.8" timeout="30" />
</weather>
"""


def draw_tiers(tier: np.ndarray, towns, pois) -> Image.Image:
    from PIL import ImageDraw

    import towns as towns_mod

    relief = Image.open(g.PREVIEW_DIR / "relief_2048.png").convert("RGB")
    lut = np.zeros((5, 3), dtype=np.uint8)
    for k, rgb in TIER_COLOURS.items():
        lut[k] = rgb
    small = tier[::2, ::2]
    colour = Image.fromarray(lut[small])
    alpha = Image.fromarray(((small > 0) * 150).astype(np.uint8))
    relief.paste(colour, (0, 0), alpha)
    d = ImageDraw.Draw(relief)
    font = towns_mod._font(18)
    for k in (1, 2, 3, 4):
        y = 20 + (k - 1) * 30
        d.rectangle([20, y, 44, y + 22], fill=TIER_COLOURS[k], outline=(0, 0, 0))
        d.text((54, y + 1), f"Tier {k}", fill=(255, 255, 255), font=font, stroke_width=2, stroke_fill=(0, 0, 0))
    return relief


def build(out: Path, h, idx, land, towns, pois, rng) -> None:
    tier = tier_map(h, land, towns, pois)
    n = write_mapgrouppos(out / "mapgrouppos.xml")
    write_types(out / "aotearoa_ce" / "types.xml")
    (out / "cfgeconomycore.aotearoa.xml").write_text(CORE_SNIPPET, encoding="utf-8")
    table = {"towns": {t["name"]: tier_at(tier, float(t["x"]), float(t["y"])) for t in towns},
             "sites": {p["label"]: tier_at(tier, p["x"], p["y"]) for p in pois if p["label"]}}
    (out / "loot_tiers.json").write_text(json.dumps(table, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    draw_tiers(tier, towns, pois).save(g.PREVIEW_DIR / "loot_tiers_2048.png", optimize=True)
    counts = write_territories(out / "env", h, idx, land, towns, pois, rng)
    (out / "cfgweather.xml").write_text(WEATHER, encoding="utf-8")
    print(f"Loot: {n} building positions, {len(NZ_TYPES)} New Zealand type changes")
    print("Animal herds: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
