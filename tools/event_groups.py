"""Event object groups for Aotearoa: army convoys, police roadblocks, highway pile-ups and train
wrecks, laid out along this map's roads and railways.

Vanilla's StaticMilitaryConvoy, StaticPoliceSituation and StaticTrain events spawn a group from
cfgeventgroups.xml at each position; the vanilla groups are drawn for Chernarus's roads, so this
map has its own. Also places motorbikes (VehicleMotorbike) and plank piles (ItemPlanks), which
need positions on every map. Called from build_mission.py.
"""

from __future__ import annotations

import math
import unicodedata
from pathlib import Path

import numpy as np

import generate_terrain as g

CONVOYS_PER_BASE = 5
CONVOY_RANGE_M = (350.0, 4000.0)  # from the camp centre
TRAFFIC_SITES = 34
TRAIN_SITES = 12
MILITARY_TRAINS = 3
PLANKS_PER_FARM = 1

CONVOY_TYPES = ["StaticObj_Wreck_HMMWV_DE", "StaticObj_Wreck_MTVR_Cargo_DE", "StaticObj_Wreck_Stryker_DE",
                "StaticObj_Wreck_MTVR_Cargo_DE", "Land_wreck_truck01_aban1_green_DE", "StaticObj_Wreck_HMMWV_DE",
                "Land_wreck_truck01_aban2_green_DE", "StaticObj_Wreck_Stryker_DE"]
CIVIL_WRECKS = ["Land_Wreck_sed01_aban1_white_DE", "Land_Wreck_sed02_aban1_red_DE", "Land_Wreck_hb01_aban1_blue_DE",
                "Land_Wreck_hb02_aban2_black_DE", "Land_Wreck_sed02_aban1_grey_DE", "Land_Wreck_hb01_aban2_green_DE",
                "Land_Wreck_offroad02_aban1_DE", "Land_Wreck_offroad02_aban2_DE", "Land_wreck_truck01_aban1_orange_DE",
                "Land_Wreck_sed01_aban2_black_DE", "Land_Wreck_hb02_aban1_red_DE", "Land_Wreck_sed02_aban2_yellow_DE"]
RURAL_WRECKS = ["Land_Wreck_Tractor_DE", "Land_Wreck_Trailer_Closed_DE", "Land_wreck_truck01_aban2_blue_DE"]
BUS = "Land_Wreck_Ikarus_DE"
POLICE = ["Land_Wreck_sed01_aban1_police_DE", "Land_Wreck_sed01_aban2_police_DE", "Land_Wreck_hb01_aban1_police_DE"]
DECAL = "StaticObj_Wreck_Decal_Small1_DE"
BARRIER_LONG = "StaticObj_Roadblock_Wood_Long_DE"
BARRIER_SMALL = "StaticObj_Roadblock_Wood_Small_DE"

# Rolling stock: (class, length along the track in m, height above the rail, loot min, loot max).
STOCK = {
    "loco": ("StaticObj_Wreck_Train_742_Red_DE", 13.0, 1.9, 1, 3),
    "loco_blue": ("StaticObj_Wreck_Train_742_Blue_DE", 13.0, 1.9, 1, 3),
    "box": ("Land_Train_Wagon_Box_DE", 12.2, 1.36, 2, 3),
    "tanker": ("StaticObj_Wreck_Train_Wagon_Tanker_DE", 11.4, 1.78, 1, 3),
    "flat": ("StaticObj_Wreck_Train_Wagon_Flat_DE", 16.4, 0.15, 1, 3),
    "logs": ("StaticObj_Train_Wagon_Flat_Industrial_Planks_DE", 16.4, 0.15, 1, 3),
    "loco_mil": ("StaticObj_Wreck_Train_742_Blue_Mil_DE", 13.0, 1.9, 1, 3),
    "box_mil": ("Land_Train_Wagon_Box_Mil_DE", 12.2, 1.36, 1, 3),
    "tanker_mil": ("StaticObj_Wreck_Train_Wagon_Tanker_Mil_DE", 11.4, 1.78, 1, 3),
    "flat_mil": ("StaticObj_Wreck_Train_Wagon_Flat_Mil_DE", 16.4, 0.23, 1, 3),
}
CONTAINER = ("Land_Container_1Aoh_DE", 2.04)
CONTAINER_MIL = ("Land_Container_1Moh_DE", 2.15)
CONSISTS = [["loco", "box", "box", "box", "logs", "logs", "flat", "flat"],
            ["loco_blue", "tanker", "tanker", "tanker", "box", "box"],
            ["loco", "flat", "flat", "flat", "flat", "box", "box"],
            ["loco_blue", "logs", "logs", "logs", "logs", "tanker"]]
MILITARY_CONSIST = ["loco_mil", "flat_mil", "flat_mil", "box_mil", "box_mil", "tanker_mil", "tanker_mil"]

# Secondary infected around each kind of group, as vanilla: smin, smax, dmin, dmax, r.
ZONES = {"StaticMilitaryConvoy": (0, 0, 1, 1, 20), "StaticPoliceSituation": (0, 0, 1, 2, 20),
         "StaticTrain": (0, 0, 1, 2, 20), "StaticContaminatedArea": (0, 0, 5, 8, 75)}


def _child(cls, dx, dz, a, y=None, loot=(2, 3), decal=False) -> dict:
    c = {"type": cls, "x": dx, "z": dz, "a": a % 360}
    if y is not None:
        c["y"] = y
    if decal or cls.startswith("StaticObj_Roadblock"):
        c["spawnsecondary"] = "false"
    elif loot:
        c["deloot"], c["lootmin"], c["lootmax"] = 1, loot[0], loot[1]
    return c


def _local(hd, along, across):
    """Offset for a point along the road (forward) and across it (right) from a heading."""
    s, c = math.sin(math.radians(hd)), math.cos(math.radians(hd))
    return along * s + across * c, along * c - across * s


def ascii_name(name: str) -> str:
    """Town or base name as a class-safe word: "Ōhakea" -> "Ohakea"."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return "".join(ch for ch in plain.title() if ch.isalnum())


def _outside(zones, x, y):
    return all(math.hypot(x - zx, y - zy) > zr for zx, zy, zr in zones)


def _spread(points, k, rng, min_gap=0.0):
    """Up to k of the points, as far apart as possible."""
    if not points:
        return []
    arr = np.array([(p[0], p[1]) for p in points])
    chosen = [int(rng.integers(len(arr)))]
    d = np.hypot(*(arr - arr[chosen[0]]).T)
    while len(chosen) < min(k, len(arr)):
        i = int(np.argmax(d))
        if d[i] < min_gap:
            break
        chosen.append(i)
        d = np.minimum(d, np.hypot(*(arr - arr[i]).T))
    return [points[i] for i in chosen]


def convoy(hd, rng) -> list[dict]:
    """Army trucks and NZLAV-like armour stopped in the left lane, one slewed into the ditch."""
    n = int(rng.integers(4, 7))
    ditch = int(rng.integers(1, n))
    out = []
    start = int(rng.integers(len(CONVOY_TYPES)))
    for k in range(n):
        cls = CONVOY_TYPES[(start + k) % len(CONVOY_TYPES)]
        across = -1.9 + float(rng.uniform(-0.6, 0.6))
        a = hd + float(rng.uniform(-10, 10))
        if k == ditch:
            across, a = -7.0, hd - 35.0
        dx, dz = _local(hd, -15.0 * k + float(rng.uniform(-2, 2)), across)
        out.append(_child(cls, dx, dz, a))
        if rng.random() < 0.5:
            out.append(_child(DECAL, dx + 0.3, dz - 0.4, float(rng.uniform(0, 360)), decal=True))
    return out


def roadblock(hd, rng) -> list[dict]:
    """A police checkpoint across the highway on the edge of a town, with a queue behind it."""
    out = []
    for across in (-3.2, 3.2):
        dx, dz = _local(hd, 0.0, across)
        out.append(_child(BARRIER_LONG, dx, dz, hd + 90))
    for along, across in ((4.0, -6.5), (4.0, 6.5)):
        dx, dz = _local(hd, along, across)
        out.append(_child(BARRIER_SMALL, dx, dz, hd + 90 + float(rng.uniform(-15, 15))))
    for along, across, turn in ((8.0, -5.0, 30.0), (10.0, 5.5, 200.0)):
        dx, dz = _local(hd, along, across)
        out.append(_child(POLICE[int(rng.integers(len(POLICE)))], dx, dz, hd + turn, loot=(2, 4)))
    for k in range(int(rng.integers(2, 4))):
        dx, dz = _local(hd, -9.0 - 7.5 * k, -1.8 + float(rng.uniform(-0.4, 0.4)))
        out.append(_child(CIVIL_WRECKS[int(rng.integers(len(CIVIL_WRECKS)))], dx, dz, hd + float(rng.uniform(-8, 8))))
    return out


def pileup(hd, rural, rng) -> list[dict]:
    """Two to four wrecks tangled across both lanes."""
    out = []
    n = int(rng.integers(2, 5))
    pool = CIVIL_WRECKS + (RURAL_WRECKS if rural else [BUS])
    for k in range(n):
        dx, dz = _local(hd, -6.0 * k + float(rng.uniform(-2, 2)), float(rng.uniform(-3.5, 3.5)))
        cls = pool[int(rng.integers(len(pool)))]
        out.append(_child(cls, dx, dz, hd + float(rng.choice([-1, 1])) * float(rng.uniform(15, 70))))
        out.append(_child(DECAL, dx, dz, float(rng.uniform(0, 360)), decal=True))
    if rng.random() < 0.25:
        dx, dz = _local(hd, 10.0, 4.0)
        out.append(_child(POLICE[int(rng.integers(len(POLICE)))], dx, dz, hd + 160, loot=(2, 4)))
    return out


def _rail_walk(pts: np.ndarray, start: float, length: float):
    """Point and heading at arc length start + length along a polyline (clamped to its ends)."""
    seg = np.hypot(*np.diff(pts, axis=0).T)
    dist = np.concatenate([[0.0], np.cumsum(seg)])
    s = float(np.clip(start + length, 0.0, dist[-1] - 1e-3))
    i = max(0, min(int(np.searchsorted(dist, s) - 1), len(pts) - 2))
    f = (s - dist[i]) / max(seg[i], 1e-6)
    x, y = pts[i] + f * (pts[i + 1] - pts[i])
    dx, dy = pts[i + 1] - pts[i]
    return float(x), float(y), math.degrees(math.atan2(dx, dy)) % 360


def train(pts, s0, consist, h, cell, size_m, rng) -> tuple[tuple[float, float], list[dict]]:
    def ground(x, y):
        r = int(np.clip((size_m - y) / cell, 0, h.shape[0] - 1))
        c = int(np.clip(x / cell, 0, h.shape[1] - 1))
        return float(h[r, c])

    ox, oy, _ = _rail_walk(pts, s0, 0.0)
    oz = ground(ox, oy)
    out, s = [], 0.0
    for k, kind in enumerate(consist):
        cls, length, lift, lo, hi = STOCK[kind]
        x, y, hd = _rail_walk(pts, s0, s + length / 2)
        a = hd + (180.0 if k == 0 else 0.0)
        dy = ground(x, y) - oz
        out.append(_child(cls, x - ox, y - oy, a, y=round(dy + lift, 3), loot=(lo, hi)))
        if kind in ("flat", "flat_mil") and rng.random() < 0.7:
            cname, clift = CONTAINER_MIL if kind == "flat_mil" else CONTAINER
            out.append(_child(cname, x - ox, y - oy, a, y=round(dy + clift, 3), loot=(3, 4)))
        s += length + 0.8
    return (ox, oy), out


def build(h, towns, roads, pois, highway, rng, safe, placer) -> dict:
    """Returns {"groups": {name: children}, "grouped": {event: [(x, y, z, group)]},
    "positions": {event: [(x, y, a)]}}."""
    size_m, cell = g.SIZE_M, g.CELL

    def z(x, y):
        return round(placer.z(x, y), 2)

    town_zones = [(float(t["x"]), float(t["y"]), float(t["radius"]) + 80.0) for t in towns]
    site_zones = [(p["x"], p["y"], p["radius"] + 40.0) for p in pois if p["kind"] != "farm"]
    keep = town_zones + site_zones + safe
    groups: dict[str, list[dict]] = {}
    grouped: dict[str, list[tuple]] = {}
    positions: dict[str, list[tuple]] = {}

    def add(event, name, x, y, children):
        groups[name] = children
        grouped.setdefault(event, []).append((x, y, z(x, y), name))

    # Convoys on the highways out of each base.
    for t in towns:
        if t["tier"] != "military":
            continue
        bx, by = float(t["x"]), float(t["y"])
        cand = [p for p in highway if CONVOY_RANGE_M[0] < math.hypot(p[0] - bx, p[1] - by) < CONVOY_RANGE_M[1]
                and _outside(keep, p[0], p[1])]
        slug = ascii_name(t["name"].replace("RNZAF Base ", "").split()[0])
        for k, (x, y, hd, _) in enumerate(_spread(cand, CONVOYS_PER_BASE, rng, min_gap=500.0)):
            add("StaticMilitaryConvoy", f"Convoy_{slug}_{k + 1}", x, y, convoy(hd, rng))

    # Police checkpoints where a highway enters each city and town.
    for t in towns:
        if t["tier"] not in ("capital", "city", "town"):
            continue
        tx, ty, tr = float(t["x"]), float(t["y"]), float(t["radius"])
        cand = [p for p in highway if tr + 60.0 < math.hypot(p[0] - tx, p[1] - ty) < tr + 220.0
                and _outside(safe, p[0], p[1])
                and _outside([zz for zz in town_zones if zz[:2] != (tx, ty)], p[0], p[1])]
        if not cand:
            continue
        x, y, hd, _ = cand[int(rng.integers(len(cand)))]
        # Face the barrier towards the town so the queue is on the way in.
        to_town = math.degrees(math.atan2(tx - x, ty - y)) % 360
        if abs((hd - to_town + 180) % 360 - 180) > 90:
            hd = (hd + 180) % 360
        name = "Block_" + ascii_name(t["name"])
        add("StaticPoliceSituation", name, x, y, roadblock(hd, rng))

    # Pile-ups on the open highway.
    cand = [p for p in highway if _outside(keep, p[0], p[1])]
    for k, (x, y, hd, ref) in enumerate(_spread(cand, TRAFFIC_SITES, rng, min_gap=1200.0)):
        rural = all(math.hypot(x - float(t["x"]), y - float(t["y"])) > float(t["radius"]) + 1500 for t in towns)
        add("StaticPoliceSituation", f"Traffic_{ref}_{k + 1}", x, y, pileup(hd, rural, rng))

    # Train wrecks on open track, a few of them army trains near Waiouru and Linton.
    rail_cand = []
    stations = [(s["x"], s["y"]) for s in roads.get("stations", [])]
    for line in roads.get("rails", []):
        pts = np.array(line["points"])
        total = float(np.hypot(*np.diff(pts, axis=0).T).sum())
        for s0 in np.arange(150.0, total - 250.0, 200.0):
            x, y, _ = _rail_walk(pts, s0, 0.0)
            if not _outside(keep, x, y) or any(math.hypot(x - sx, y - sy) < 300 for sx, sy in stations):
                continue
            ok = all(placer.z(*_rail_walk(pts, s0, d)[:2]) > 0.8 for d in range(0, 121, 15))
            if ok:
                rail_cand.append((x, y, line["ref"], pts, float(s0)))
    bases = [(float(t["x"]), float(t["y"])) for t in towns if t["tier"] == "military"]
    mil = sorted(rail_cand, key=lambda c: min(math.hypot(c[0] - bx, c[1] - by) for bx, by in bases))
    mil = [c for c in mil if min(math.hypot(c[0] - bx, c[1] - by) for bx, by in bases) < 5000.0]
    chosen_mil = _spread(mil, MILITARY_TRAINS, rng, min_gap=1500.0)
    rest = [c for c in rail_cand if all(math.hypot(c[0] - m[0], c[1] - m[1]) > 1500 for m in chosen_mil)]
    chosen = _spread(rest, TRAIN_SITES - len(chosen_mil), rng, min_gap=1500.0)
    for k, (_, _, ref, pts, s0) in enumerate(chosen_mil):
        (ox, oy), kids = train(pts, s0, MILITARY_CONSIST, h, cell, size_m, rng)
        add("StaticTrain", f"Train_Mil_{ref}_{k + 1}", ox, oy, kids)
    for k, (_, _, ref, pts, s0) in enumerate(chosen):
        consist = CONSISTS[k % len(CONSISTS)]
        (ox, oy), kids = train(pts, s0, consist, h, cell, size_m, rng)
        add("StaticTrain", f"Train_{ref}_{k + 1}", ox, oy, kids)

    # Motorbikes parked on town streets and at the beach and lake settlements.
    bikes = []
    for t in towns:
        if t["tier"] not in ("capital", "city", "town", "village"):
            continue
        ref = ascii_name(t["name"])
        streets = [r for r in roads["roads"] if r["kind"] == "street" and r["ref"] == ref]
        n = {"capital": 4, "city": 3, "town": 2, "village": 1}[t["tier"]]
        for i in rng.permutation(len(streets))[:n]:
            pts = np.array(streets[i]["points"])
            if len(pts) < 2:
                continue
            (ax, ay), (bx, by) = pts[0], pts[1]
            hd = math.degrees(math.atan2(bx - ax, by - ay)) % 360
            dx, dy = _local(hd, 0.0, -4.5)
            x, y = (ax + bx) / 2 + dx, (ay + by) / 2 + dy
            if _outside(safe, x, y):
                bikes.append((float(x), float(y), hd))
    for p in pois:
        if p["kind"] in ("bach", "campground", "surfclub", "hut"):
            spot = placer.find(p["x"], p["y"], 10.0, 45.0, 2.0, step=5.0, max_relief=2.0)
            if spot and _outside(safe, *spot):
                bikes.append((spot[0], spot[1], float(rng.uniform(0, 360))))
    positions["VehicleMotorbike"] = bikes

    # Plank piles in the farm yards, industrial sites and huts, for building.
    planks = []
    for p in pois:
        want = {"farm": PLANKS_PER_FARM, "industrial": 3, "hut": 1, "station": 1, "port": 2}.get(p["kind"], 0)
        for k in range(want):
            spot = placer.find(p["x"], p["y"], 12.0 + 8.0 * k, 70.0, 3.0, step=5.0, max_relief=1.5)
            if spot and _outside(safe, *spot):
                placer.add(spot[0], spot[1], 3.0)
                planks.append((spot[0], spot[1], float(rng.uniform(0, 360))))
    positions["ItemPlanks"] = planks
    return {"groups": groups, "grouped": grouped, "positions": positions}


def write_groups(groups: dict[str, list[dict]], path: Path) -> None:
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             "<!-- Event groups for Aotearoa (convoys, roadblocks, pile-ups, trains), generated by",
             "     tools/event_groups.py. Child x/z are metres east/north of the event position. -->",
             "<eventgroupdef>"]
    for name in sorted(groups):
        lines.append(f'    <group name="{name}">')
        for c in groups[name]:
            attrs = [f'type="{c["type"]}"']
            for key in ("spawnsecondary", "deloot", "lootmax", "lootmin"):
                if key in c:
                    attrs.append(f'{key}="{c[key]}"')
            attrs += [f'x="{c["x"]:.3f}"', f'z="{c["z"]:.3f}"', f'a="{c["a"]:.3f}"']
            if "y" in c:
                attrs.append(f'y="{c["y"]:.3f}"')
            lines.append("        <child " + " ".join(attrs) + "/>")
        lines.append("    </group>")
    lines += ["</eventgroupdef>", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
