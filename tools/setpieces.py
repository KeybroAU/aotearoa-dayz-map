"""Set pieces built from vanilla objects: city landmarks (Sky Tower, Harbour Bridge, the Beehive's
neighbours, the cathedral), the Interislander wreck in Cook Strait,
bigger military bases, the Waiouru ammunition area and the Ōhakea Hercules crash.

Called from build_mission.py after the towns, sites and trader compounds are placed. Writes

  source/objects/setpieces_tb.txt        Terrain Builder import (same format as towns_tb.txt)
  source/objects/setpieces_spawner.json  the same objects as a cfggameplay.json object spawner
  source/setpieces.json                  each set piece's label, kind and centre, for the maps

and returns the static gas zones and dynamic gas positions for the mission.

Every class here is a vanilla building with loot points in mapgroupproto.xml, or a vanilla
object listed in the structures config, so nothing needs a custom model.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import cKDTree

import generate_terrain as g

# Clearance radius (m) around each class, used to keep pieces off buildings, roads and each other.
RADIUS = {
    "Land_Tower_TC2_Base": 14, "Land_Office_Municipal2": 22, "Land_Office1": 16, "Land_Ruin_Church2": 16,
    "Land_Mil_Barracks6": 30, "Land_Mil_Barracks5": 20, "Land_Mil_Barracks4": 18, "Land_Mil_Barracks_Round": 14,
    "Land_Mil_Tent_Big2_1": 16, "Land_Mil_Tent_Big2_2": 16, "Land_Mil_Tent_Big2_3": 16, "Land_Mil_Tent_Big2_4": 16,
    "Land_Mil_Tent_Big1_3": 12, "Land_Mil_Tent_Big3": 12, "Land_Mil_Tent_Big4": 12, "Land_Mil_Guardhouse2": 8,
    "Land_Mil_Guardhouse3": 8, "Land_Mil_GuardTower": 5, "Land_Mil_Fortified_Nest_Watchtower": 6,
    "Land_Mil_Fortified_Nest_Big": 10, "Land_Bunker1_Double": 10, "Land_Bunker2_Double": 10,
    "Land_Mil_AircraftShelter": 25, "Land_Mil_ControlTower": 12, "Land_Wreck_C130J_Cargo": 35,
    "StaticObj_Wreck_Ship_Big_Lifeboat": 6,
}
DEFAULT_RADIUS = 8.0
MAX_RELIEF_M = 1.6  # highest minus lowest ground under a building
WRECK_RELIEF_M = 4.0

# The TV tower is three stacked pieces; heights are above the base piece.
SKY_TOWER = [("Land_Tower_TC2_Base", 0.0), ("Land_Tower_TC2_Mid", 49.6), ("Land_Tower_TC2_Top", 99.3)]

# The large ship wreck as it lies off Berezino on Chernarus: (class, x, height, z, yaw). Heights
# are above sea level; the hull's long axis runs 90 degrees clockwise from its yaw.
SHIP = [("Land_Ship_Big_BackB", 13785.21, 17.145, 11138.83, -22.853),
        ("Land_Ship_Big_Castle", 13795.79, 27.302, 11143.06, -22.853),
        ("Land_Ship_Big_BackA", 13803.59, 18.661, 11145.91, -22.853),
        ("Land_Ship_Big_FrontB", 13845.03, 16.808, 11159.36, -11.499),
        ("Land_Ship_Big_FrontA", 13864.09, 18.308, 11165.59, -11.499)]
SHIP_DEPTH_M = (-8.0, -2.0)  # sea bed depth along the hull: aground, not sunk

# Extra buildings for each base: (town name, classes). Placed around the existing camp.
BASES = [
    ("Waiouru Army Camp", ["Land_Mil_Barracks6", "Land_Mil_Barracks5", "Land_Mil_Tent_Big2_1", "Land_Mil_Tent_Big2_3",
                           "Land_Mil_Tent_Big3", "Land_Mil_Guardhouse2", "Land_Mil_GuardTower", "Land_Mil_GuardTower",
                           "Land_Mil_GuardTower", "Land_Mil_Fortified_Nest_Watchtower"]),
    ("Burnham Military Camp", ["Land_Mil_Barracks5", "Land_Mil_Barracks4", "Land_Mil_Tent_Big2_2",
                               "Land_Mil_Tent_Big1_3", "Land_Mil_Guardhouse2", "Land_Mil_GuardTower",
                               "Land_Mil_GuardTower"]),
    ("Linton Army Camp", ["Land_Mil_Barracks_Round", "Land_Mil_Barracks4", "Land_Mil_Tent_Big2_4", "Land_Mil_Tent_Big3",
                          "Land_Mil_Guardhouse3", "Land_Mil_GuardTower", "Land_Mil_GuardTower"]),
    ("RNZAF Base Ōhakea", ["Land_Mil_AircraftShelter", "Land_Mil_AircraftShelter", "Land_Mil_ControlTower",
                           "Land_Mil_Tent_Big2_2", "Land_Mil_GuardTower", "Land_Mil_GuardTower"]),
]
AMMO_AREA = ["Land_Bunker1_Double", "Land_Bunker1_Double", "Land_Bunker2_Double", "Land_Bunker2_Double",
             "Land_Mil_Fortified_Nest_Big", "Land_Mil_Tent_Big4", "Land_Mil_GuardTower", "Land_Mil_GuardTower"]
AMMO_AREA_DIST_M = (700.0, 1400.0)  # from the camp centre
AMMO_GAS_RADIUS_M = 200.0
HERCULES_DIST_M = (1200.0, 2600.0)  # from the Ōhakea runway

# The Harbour Bridge: steel truss spans over the shortest water crossing near Auckland's centre.
BRIDGE_CLASS, BRIDGE_SPAN_M = "StaticObj_Bridge_Metal_25", 25.0
BRIDGE_LENGTH_M = (40.0, 200.0)  # water to cross
BRIDGE_SEARCH_M = 6000.0

# Dynamic gas (vanilla StaticContaminatedArea) turns up at the bases, airfields, industrial sites
# and ports, plus open back country.
DYNAMIC_GAS_BACKCOUNTRY = 24


@dataclass
class Piece:
    label: str
    kind: str  # landmark, wreck, military, gas
    x: float
    y: float
    objects: list[tuple[str, float, float, float, float]] = field(default_factory=list)  # class, x, y, z, yaw


class Placer:
    """Finds flat, clear ground for each object and remembers what it has placed."""

    def __init__(self, h, land, roads, occupied):
        self.h, self.land = h, land
        road_mask = np.asarray(Image.open(g.SOURCE_DIR / "roads_4096.png")) > 0
        self.road_dist = ndimage.distance_transform_edt(~road_mask) * g.CELL
        rail_pts = []
        for line in roads.get("rails", []):
            pts = np.array(line["points"])
            for a, b in zip(pts[:-1], pts[1:]):
                n = max(1, int(np.hypot(*(b - a)) / 5.0))
                rail_pts += [a + (b - a) * k / n for k in range(n)]
        self.rails = cKDTree(np.array(rail_pts)) if rail_pts else None
        self.points = [(x, y, r) for x, y, r in occupied]
        self._tree()

    def _tree(self):
        self.tree = cKDTree(np.array([(x, y) for x, y, _ in self.points])) if self.points else None
        self.max_r = max((r for *_, r in self.points), default=0.0)

    def cell(self, x, y):
        r = int(np.clip((g.SIZE_M - y) / g.CELL, 0, g.GRID - 1))
        c = int(np.clip(x / g.CELL, 0, g.GRID - 1))
        return r, c

    def z(self, x, y) -> float:
        return float(ndimage.map_coordinates(self.h, [[(g.SIZE_M - y) / g.CELL - 0.5], [x / g.CELL - 0.5]],
                                             order=1, mode="nearest")[0])

    def relief(self, x, y, radius) -> float:
        r, c = self.cell(x, y)
        k = max(1, int(radius / g.CELL))
        win = self.h[max(0, r - k):r + k + 1, max(0, c - k):c + k + 1]
        return float(win.max() - win.min())

    def clear(self, x, y, radius, max_relief=MAX_RELIEF_M) -> bool:
        r, c = self.cell(x, y)
        k = max(1, int(radius / g.CELL))
        if not self.land[max(0, r - k):r + k + 1, max(0, c - k):c + k + 1].all() or self.h[r, c] < 1.5:
            return False
        if self.road_dist[r, c] < radius + 4.0 or self.relief(x, y, radius) > max_relief:
            return False
        if self.rails is not None and self.rails.query((x, y))[0] < radius + 6.0:
            return False
        if self.tree is not None:
            for i in self.tree.query_ball_point((x, y), radius + self.max_r + 4.0):
                px, py, pr = self.points[i]
                if math.hypot(x - px, y - py) < radius + pr + 4.0:
                    return False
        return True

    def find(self, cx, cy, rmin, rmax, radius, step=12.0, max_relief=MAX_RELIEF_M):
        """Clear spot nearest to rmin from (cx, cy), searching out to rmax."""
        best = None
        for d in np.arange(rmin, rmax + 0.1, step):
            n = max(8, int(2 * math.pi * d / step))
            start = (cx * 7.0 + cy * 3.0 + d) % (2 * math.pi)
            for k in range(n):
                a = start + 2 * math.pi * k / n
                x, y = cx + d * math.sin(a), cy + d * math.cos(a)
                if 0 < x < g.SIZE_M and 0 < y < g.SIZE_M and self.clear(x, y, radius, max_relief):
                    best = (x, y)
                    break
            if best:
                break
        return best

    def add(self, x, y, radius):
        self.points.append((x, y, radius))
        self._tree()


def facing(px, py, cx, cy) -> float:
    """Yaw that turns a building's front towards (cx, cy), snapped to 15 degrees."""
    return round(math.degrees(math.atan2(cx - px, cy - py)) / 15.0) * 15.0 % 360


def place_group(placer, piece, classes, cx, cy, rmin, rmax, max_relief=MAX_RELIEF_M):
    for cls in classes:
        rad = RADIUS.get(cls, DEFAULT_RADIUS)
        spot = placer.find(cx, cy, rmin, rmax, rad, max_relief=max_relief)
        if not spot:
            continue
        x, y = spot
        placer.add(x, y, rad)
        piece.objects.append((cls, x, y, placer.z(x, y), facing(x, y, cx, cy)))


def town(towns, name):
    return next(t for t in towns if t["name"] == name)


def sky_tower(placer, towns) -> Piece | None:
    t = town(towns, "Auckland")
    spot = placer.find(float(t["x"]), float(t["y"]), 40.0, 400.0, RADIUS["Land_Tower_TC2_Base"])
    if not spot:
        return None
    x, y = spot
    placer.add(x, y, RADIUS["Land_Tower_TC2_Base"])
    z = placer.z(x, y)
    return Piece("Sky Tower", "landmark", x, y, [(cls, x, y, z + dz, 0.0) for cls, dz in SKY_TOWER])


def civic(placer, towns, name, label, classes) -> Piece | None:
    t = town(towns, name)
    piece = Piece(label, "landmark", float(t["x"]), float(t["y"]))
    place_group(placer, piece, classes, float(t["x"]), float(t["y"]), 30.0, 420.0)
    if not piece.objects:
        return None
    piece.x = float(np.mean([o[1] for o in piece.objects]))
    piece.y = float(np.mean([o[2] for o in piece.objects]))
    return piece


def ship_layout(x, y, bearing):
    """The wreck's five parts with the hull's long axis on bearing (degrees clockwise from north)."""
    bx, _, bz, byaw = SHIP[0][1], SHIP[0][2], SHIP[0][3], SHIP[0][4]
    base_bearing = byaw + 90.0
    turn = math.radians(bearing - base_bearing)
    out = []
    for cls, px, pz_h, pz, yaw in SHIP:
        dx, dz = px - bx, pz - bz
        rx = dx * math.cos(turn) + dz * math.sin(turn)
        rz = -dx * math.sin(turn) + dz * math.cos(turn)
        out.append((cls, x + rx, y + rz, pz_h, (yaw + bearing - base_bearing) % 360))
    return out


def harbour_bridge(placer, towns) -> Piece | None:
    t = town(towns, "Auckland")
    cx, cy = float(t["x"]), float(t["y"])
    h = placer.h

    def wet(x, y):
        r, c = placer.cell(x, y)
        return h[r, c] < -0.5

    def dry(x, y):
        r, c = placer.cell(x, y)
        return h[r, c] > 1.5

    best = None
    for y in np.arange(cy - BRIDGE_SEARCH_M, cy + BRIDGE_SEARCH_M, 50.0):
        for x in np.arange(cx - BRIDGE_SEARCH_M, cx + BRIDGE_SEARCH_M, 50.0):
            if not wet(x, y) or math.hypot(x - cx, y - cy) > BRIDGE_SEARCH_M:
                continue
            for hd in range(0, 180, 10):
                ux, uy = math.sin(math.radians(hd)), math.cos(math.radians(hd))
                ends = []
                for sgn in (-1, 1):
                    d = 0.0
                    while d < BRIDGE_LENGTH_M[1] and not dry(x + sgn * ux * d, y + sgn * uy * d):
                        d += g.CELL
                    ends.append(d)
                length = sum(ends)
                if ends[0] >= BRIDGE_LENGTH_M[1] or ends[1] >= BRIDGE_LENGTH_M[1] or length < BRIDGE_LENGTH_M[0]:
                    continue
                mx, my = x + ux * (ends[1] - ends[0]) / 2, y + uy * (ends[1] - ends[0]) / 2
                score = length + 0.05 * math.hypot(mx - cx, my - cy)
                if best is None or score < best[0]:
                    best = (score, mx, my, hd, length)
    if not best:
        return None
    _, mx, my, hd, length = best
    ux, uy = math.sin(math.radians(hd)), math.cos(math.radians(hd))
    n = math.ceil((length + 2 * BRIDGE_SPAN_M / 2) / BRIDGE_SPAN_M)
    half = n * BRIDGE_SPAN_M / 2
    deck = max(placer.z(mx - ux * half, my - uy * half), placer.z(mx + ux * half, my + uy * half), 2.0)
    piece = Piece("Harbour Bridge", "landmark", mx, my)
    for k in range(n):
        along = (k - (n - 1) / 2) * BRIDGE_SPAN_M
        piece.objects.append((BRIDGE_CLASS, mx + ux * along, my + uy * along, deck, float(hd)))
    placer.add(mx, my, half)
    return piece


def interislander_wreck(placer, pois) -> Piece | None:
    """Aground in the shallows near the mouth of Wellington Harbour, like the Wahine in 1968."""
    term = next(p for p in pois if p["class"] == "InterislanderWellington")
    h = placer.h
    best = None
    for d in np.arange(800.0, 6000.0, 50.0):
        for k in range(72):
            a = math.radians(k * 5.0)
            x, y = term["x"] + d * math.sin(a), term["y"] + d * math.cos(a)
            for bearing in range(0, 180, 15):
                parts = ship_layout(x, y, bearing)
                ok = True
                for _, px, py, _, _ in parts:
                    r, c = placer.cell(px, py)
                    if not (SHIP_DEPTH_M[0] <= h[r, c] <= SHIP_DEPTH_M[1]):
                        ok = False
                        break
                if ok:
                    best = (x, y, bearing)
                    break
            if best:
                break
        if best:
            break
    if not best:
        return None
    x, y, bearing = best
    piece = Piece("Interislander wreck", "wreck", x, y, [(c, px, py, z, yaw) for c, px, py, z, yaw in
                                                         ship_layout(x, y, bearing)])
    # A lifeboat washed up on the nearest beach.
    for d in np.arange(100.0, 2500.0, 25.0):
        hit = None
        for k in range(36):
            a = math.radians(k * 10.0)
            lx, ly = x + d * math.sin(a), y + d * math.cos(a)
            r, c = placer.cell(lx, ly)
            if 0.4 < h[r, c] < 2.0 and placer.relief(lx, ly, 6.0) < 2.5:
                hit = (lx, ly)
                break
        if hit:
            lx, ly = hit
            piece.objects.append(("StaticObj_Wreck_Ship_Big_Lifeboat", lx, ly, placer.z(lx, ly), (bearing + 40) % 360))
            break
    return piece


def bases(placer, towns) -> list[Piece]:
    out = []
    for name, classes in BASES:
        t = town(towns, name)
        cx, cy, r = float(t["x"]), float(t["y"]), float(t["radius"])
        piece = Piece(name, "military", cx, cy)
        place_group(placer, piece, classes, cx, cy, r + 20.0, r + 320.0)
        out.append(piece)
    return out


def ammo_area(placer, towns) -> Piece | None:
    t = town(towns, "Waiouru Army Camp")
    cx, cy = float(t["x"]), float(t["y"])
    centre = placer.find(cx, cy, AMMO_AREA_DIST_M[0], AMMO_AREA_DIST_M[1], 60.0, step=40.0, max_relief=6.0)
    if not centre:
        return None
    piece = Piece("Waiouru Ammunition Area", "gas", *centre)
    place_group(placer, piece, AMMO_AREA, centre[0], centre[1], 0.0, AMMO_GAS_RADIUS_M * 0.7)
    return piece if piece.objects else None


def hercules(placer, pois) -> Piece | None:
    field_ = next(p for p in pois if p["kind"] == "airfield" and "Ōhakea" in p["label"])
    rad = RADIUS["Land_Wreck_C130J_Cargo"]
    spot = placer.find(field_["x"], field_["y"], *HERCULES_DIST_M, rad, step=30.0, max_relief=WRECK_RELIEF_M)
    if not spot:
        return None
    x, y = spot
    placer.add(x, y, rad)
    yaw = (field_["heading"] + 25.0) % 360
    return Piece("Hercules crash site", "wreck", x, y, [("Land_Wreck_C130J_Cargo", x, y, placer.z(x, y), yaw)])


def dynamic_gas(h, land, towns, pois, ammo, rng) -> list[tuple[float, float]]:
    pts = []
    for t in towns:
        if t["tier"] == "military":
            pts.append((float(t["x"]), float(t["y"])))
    for p in pois:
        if p["kind"] in ("airfield", "industrial", "port", "naval"):
            pts.append((p["x"], p["y"]))
    if ammo:
        pts.append((ammo.x, ammo.y))
    # Open back country well away from towns.
    rows, cols = np.nonzero(land[::16, ::16] & (h[::16, ::16] > 60.0))
    cand = [((c * 16 + 0.5) * g.CELL, g.SIZE_M - (r * 16 + 0.5) * g.CELL) for r, c in zip(rows, cols)]
    cand = [q for q in cand if all(math.hypot(q[0] - float(t["x"]), q[1] - float(t["y"])) > float(t["radius"]) + 800
                                   for t in towns)]
    if cand:
        cand = np.array(cand)
        chosen = [int(rng.integers(len(cand)))]
        d = np.hypot(*(cand - cand[chosen[0]]).T)
        for _ in range(DYNAMIC_GAS_BACKCOUNTRY - 1):
            i = int(np.argmax(d))
            chosen.append(i)
            d = np.minimum(d, np.hypot(*(cand - cand[i]).T))
        pts += [tuple(map(float, cand[i])) for i in chosen]
    return pts


def occupied(pois, traders) -> list[tuple[float, float, float]]:
    import pois as pois_mod
    import towns as towns_mod

    occ = []
    for name in ("towns_spawner.json", "pois_spawner.json"):
        for o in json.loads((g.SOURCE_DIR / "objects" / name).read_text())["Objects"]:
            w, l = towns_mod.FOOTPRINTS.get(o["name"], (10, 12))
            occ.append((o["pos"][0], o["pos"][2], math.hypot(w, l) / 2))
    occ += [(p["x"], p["y"], 20.0) for p in pois if p["kind"] == "ferry"]
    occ += [(x, y, r) for x, y, r in traders]
    return occ


def write(pieces: list[Piece]) -> int:
    meta = json.loads((g.SOURCE_DIR / "heightmap.json").read_text())
    easting, northing = meta["easting"], meta["northing"]
    objs = [o for p in pieces for o in p.objects]
    with (g.SOURCE_DIR / "objects" / "setpieces_tb.txt").open("w", newline="\r\n") as f:
        for cls, x, y, z, yaw in objs:
            template = cls[5:].lower() if cls.startswith("Land_") else cls[10:].lower() if cls.startswith("StaticObj_") \
                else cls.lower()
            offset = z - _ground(x, y)
            f.write(f'"{template}";{x + easting:.3f};{y + northing:.3f};{yaw:.3f};0;0;1;{offset:.3f};\n')
    spawner = [{"name": cls, "pos": [round(x, 3), round(z, 3), round(y, 3)], "ypr": [round(yaw, 3), 0.0, 0.0],
                "scale": 1.0, "enableCEPersistency": 0} for cls, x, y, z, yaw in objs]
    (g.SOURCE_DIR / "objects" / "setpieces_spawner.json").write_text(json.dumps({"Objects": spawner}, indent=1) + "\n")
    sites = [{"label": p.label, "kind": p.kind, "x": round(p.x, 1), "y": round(p.y, 1), "objects": len(p.objects)}
             for p in pieces if p.objects]
    (g.SOURCE_DIR / "setpieces.json").write_text(json.dumps(sites, indent=1, ensure_ascii=False) + "\n",
                                                 encoding="utf-8")
    return len(objs)


_H = None


def _ground(x, y) -> float:
    return float(ndimage.map_coordinates(_H, [[(g.SIZE_M - y) / g.CELL - 0.5], [x / g.CELL - 0.5]],
                                         order=1, mode="nearest")[0])


def build(h, land, towns, roads, pois, traders, rng) -> dict:
    global _H
    _H = h
    placer = Placer(h, land, roads, occupied(pois, traders))
    pieces = [sky_tower(placer, towns), harbour_bridge(placer, towns),
              civic(placer, towns, "Wellington", "Parliament Buildings", ["Land_Office_Municipal2", "Land_Office1"]),
              civic(placer, towns, "Christchurch", "ChristChurch Cathedral", ["Land_Ruin_Church2"]),
              interislander_wreck(placer, pois), hercules(placer, pois)]
    pieces += bases(placer, towns)
    ammo = ammo_area(placer, towns)
    pieces.append(ammo)
    pieces = [p for p in pieces if p]
    n = write(pieces)
    gas = [] if not ammo else [{"name": "WaiouruAmmunitionArea", "x": ammo.x, "y": ammo.y,
                                "z": _ground(ammo.x, ammo.y), "radius": AMMO_GAS_RADIUS_M}]
    return {"pieces": pieces, "objects": n, "gas": gas, "placer": placer,
            "dynamic_gas": dynamic_gas(h, land, towns, pois, ammo, rng)}
