"""Build the server mission files for the Aotearoa terrain.

Reads the generated terrain (source/heightmap_4096.png, mask_4096.png, towns.csv, roads.json,
pois.json) and writes mission/dayzOffline.aotearoa/ with player spawns, vehicle and crash
events, infected zones, the Whakaari and Waiouru contaminated areas, init.c and a cfggameplay
snippet, plus mission/serverDZ.cfg. economy.py adds loot positions and tiers, animals and weather;
server_files.py adds starting gear, server messages and launch scripts; signs.py the road signs;
mod_support.py trader sites for server mods; setpieces.py the landmarks, wrecks and base
extensions; event_groups.py the convoys, roadblocks, pile-ups and trains (cfgeventgroups.xml).
Copy the rest of the mission (db/, cfgeconomycore.xml and so on)
from vanilla dayzOffline.chernarusplus; see the README.

    python build_mission.py
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

import economy
import event_groups
import mod_support
import generate_terrain as g
import server_files
import setpieces
import signs

MISSION = "dayzOffline.aotearoa"
OUT = g.MAP_DIR / "mission"
SPAWN_COUNT = 40
HELI_CRASHES = 24
VEHICLE_SPACING_M = 450.0
RURAL_VEHICLE_SPACING_M = 1200.0  # farm utes and trucks along the back roads and farm tracks
MAX_VEHICLE_GAP_M = 1000.0  # fill_vehicle_gaps adds a ute wherever land is further than this from a vehicle
RURAL_VEHICLES = ["VehicleOffroad02", "VehicleTruck01", "VehicleOffroadHatchback"]

VEHICLES = ["VehicleCivilianSedan", "VehicleSedan02", "VehicleHatchback02", "VehicleOffroadHatchback",
            "VehicleOffroad02", "VehicleTruck01"]
INFECTED_ZONES = {
    # tier: (zone name, zones per 100 m of radius, dmin, dmax)
    "capital": ("InfectedCity", 3.2, 3, 7),
    "city": ("InfectedCity", 3.0, 2, 6),
    "town": ("InfectedVillage", 2.6, 2, 5),
    "village": ("InfectedVillage", 2.4, 1, 3),
    "military": ("InfectedArmy", 3.0, 2, 5),
    "hamlet": ("InfectedVillage", 2.0, 1, 2),
}
# Monthly temperature range (deg C, January first), roughly Canterbury.
MIN_TEMPS = [12, 12, 10, 7, 4, 2, 1, 2, 4, 6, 8, 11]
MAX_TEMPS = [23, 22, 20, 17, 14, 11, 10, 12, 14, 17, 19, 21]


def load():
    meta = json.loads((g.SOURCE_DIR / "heightmap.json").read_text())
    raw = np.asarray(Image.open(g.SOURCE_DIR / "heightmap_4096.png")).astype(np.float32)
    h = meta["png_black_m"] + raw / 65535.0 * (meta["png_white_m"] - meta["png_black_m"])
    mask_rgb = np.asarray(Image.open(g.SOURCE_DIR / "mask_4096.png").convert("RGB")).astype(int)
    lut = np.array([s[1] for s in g.SURFACES])
    idx = np.argmin(((mask_rgb[..., None, :] - lut[None, None]) ** 2).sum(-1), axis=-1).astype(np.uint8)
    with (g.SOURCE_DIR / "towns.csv").open(encoding="utf-8") as f:
        towns = list(csv.DictReader(f))
    roads = json.loads((g.SOURCE_DIR / "roads.json").read_text(encoding="utf-8"))
    pois = json.loads((g.SOURCE_DIR / "pois.json").read_text(encoding="utf-8"))
    return h, idx, towns, roads, pois


def cell(x, y):
    r = int(np.clip((g.SIZE_M - y) / g.CELL, 0, g.GRID - 1))
    c = int(np.clip(x / g.CELL, 0, g.GRID - 1))
    return r, c


def world(r, c):
    return (c + 0.5) * g.CELL, g.SIZE_M - (r + 0.5) * g.CELL


def farthest_points(points: np.ndarray, k: int, rng) -> np.ndarray:
    if len(points) <= k:
        return points
    chosen = [int(rng.integers(len(points)))]
    d = np.hypot(*(points - points[chosen[0]]).T)
    for _ in range(k - 1):
        i = int(np.argmax(d))
        chosen.append(i)
        d = np.minimum(d, np.hypot(*(points - points[i]).T))
    return points[chosen]


def keep_out(towns, pois, extra=0.0):
    zones = [(float(t["x"]), float(t["y"]), float(t["radius"]) + extra + (300.0 if t["tier"] == "military" else 0.0))
             for t in towns]
    zones += [(p["x"], p["y"], p["radius"] + extra) for p in pois if p["kind"] != "farm"]
    return zones


def outside(zones, x, y):
    return all(math.hypot(x - zx, y - zy) > zr for zx, zy, zr in zones)


def spawn_points(h, land, slope, towns, pois, rng):
    dist_sea = ndimage.distance_transform_edt(land) * g.CELL
    # Only the two main islands: nobody should spawn on an islet with no way off.
    lab, n = ndimage.label(land)
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    main = np.isin(lab, np.argsort(sizes)[-2:])
    cand = main & (dist_sea > 15.0) & (dist_sea < 60.0) & (slope < 12.0) & (h < 15.0)
    rows, cols = np.nonzero(cand[::4, ::4])
    pts = np.array([world(r * 4, c * 4) for r, c in zip(rows, cols)])
    zones = keep_out(towns, pois, 150.0)
    whakaari = [p for p in pois if p["kind"] == "whakaari"]
    zones += [(p["x"], p["y"], p["radius"] + 600.0) for p in whakaari]
    pts = np.array([p for p in pts if outside(zones, *p)])
    return farthest_points(pts, SPAWN_COUNT, rng)


def write_spawns(points, path):
    bubbles = "\n".join(f'            <pos x="{x:.1f}" z="{y:.1f}" />' for x, y in points)

    def block(tag, min_inf, max_inf):
        return f"""    <{tag}>
        <spawn_params>
            <min_dist_infected>{min_inf}</min_dist_infected>
            <max_dist_infected>{max_inf}</max_dist_infected>
            <min_dist_player>65</min_dist_player>
            <max_dist_player>150</max_dist_player>
            <min_dist_static>0</min_dist_static>
            <max_dist_static>2</max_dist_static>
        </spawn_params>
        <generator_params>
            <grid_density>4</grid_density>
            <grid_width>60</grid_width>
            <grid_height>60</grid_height>
            <min_dist_static>0</min_dist_static>
            <max_dist_static>2</max_dist_static>
            <min_steepness>-45</min_steepness>
            <max_steepness>45</max_steepness>
        </generator_params>
        <generator_posbubbles>
{bubbles}
        </generator_posbubbles>
    </{tag}>"""

    text = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<!-- Coastal spawns for Aotearoa, '
            'generated by tools/build_mission.py. -->\n<playerspawnpoints>\n'
            + "\n".join([block("fresh", 30, 70), block("hop", 25, 70), block("travel", 25, 70)])
            + "\n</playerspawnpoints>\n")
    path.write_text(text, encoding="utf-8")


def highway_samples(roads, step):
    out = []
    for r in roads["roads"]:
        if r["kind"] != "highway":
            continue
        pts = np.array(r["points"])
        seg = np.hypot(*np.diff(pts, axis=0).T)
        dist = np.concatenate([[0.0], np.cumsum(seg)])
        for s in np.arange(step / 2, dist[-1], step):
            i = int(np.searchsorted(dist, s) - 1)
            i = max(0, min(i, len(pts) - 2))
            k = (s - dist[i]) / max(seg[i], 1e-6)
            x, y = pts[i] + k * (pts[i + 1] - pts[i])
            dx, dy = pts[i + 1] - pts[i]
            out.append((float(x), float(y), math.degrees(math.atan2(dx, dy)) % 360, r["ref"]))
    return out


def events(h, idx, land, slope, towns, roads, pois, rng):
    ev: dict[str, list[tuple[float, float, float]]] = {}
    zones = keep_out(towns, pois, 60.0)

    # Cars parked on the left verge of the highways, facing along them.
    for i, (x, y, hd, _) in enumerate(p for p in highway_samples(roads, VEHICLE_SPACING_M) if outside(zones, p[0], p[1])):
        side = math.radians(hd - 90.0)
        px, py = x + 3.5 * math.sin(side), y + 3.5 * math.cos(side)
        ev.setdefault(VEHICLES[i % len(VEHICLES)], []).append((px, py, hd))

    # Farm utes and trucks on the back roads and farm tracks, so the back country has transport too.
    k = 0
    for r in roads["roads"]:
        if r["kind"] not in ("gravel", "track"):
            continue
        pts = np.array(r["points"])
        seg = np.hypot(*np.diff(pts, axis=0).T)
        dist = np.concatenate([[0.0], np.cumsum(seg)])
        for at in np.arange(RURAL_VEHICLE_SPACING_M / 2, dist[-1] - 100.0, RURAL_VEHICLE_SPACING_M):
            i = max(0, min(int(np.searchsorted(dist, at) - 1), len(pts) - 2))
            f = (at - dist[i]) / max(seg[i], 1e-6)
            x, y = pts[i] + f * (pts[i + 1] - pts[i])
            if not outside(zones, x, y):
                continue
            hd = math.degrees(math.atan2(*(pts[i + 1] - pts[i]))) % 360
            side = math.radians(hd - 90.0)
            ev.setdefault(RURAL_VEHICLES[k % len(RURAL_VEHICLES)], []).append(
                (x + 3.0 * math.sin(side), y + 3.0 * math.cos(side), hd))
            k += 1

    # Boats tied up off each port, ferry terminal and boat ramp.
    for p in pois:
        if p["kind"] not in ("port", "ferry", "ramp"):
            continue
        want = 3 if p["kind"] == "ferry" else 1
        placed = 0
        pts = np.array(p["surfaces"][0]["points"])
        for (ax, ay), (bx, by) in zip(pts, np.roll(pts, -1, axis=0)):
            mx, my = (ax + bx) / 2, (ay + by) / 2
            nx, ny = mx - p["x"], my - p["y"]
            norm = math.hypot(nx, ny) or 1.0
            ox, oy = mx + nx / norm * 25.0, my + ny / norm * 25.0
            r, c = cell(ox, oy)
            for k in range(want - placed):
                along = (k - (want - placed - 1) / 2) * 14.0
                ux, uy = (bx - ax) / (math.hypot(bx - ax, by - ay) or 1.0), (by - ay) / (math.hypot(bx - ax, by - ay) or 1.0)
                qx, qy = ox + ux * along, oy + uy * along
                r, c = cell(qx, qy)
                if h[r, c] < -1.0:
                    ev.setdefault("VehicleBoat", []).append((qx, qy, math.degrees(math.atan2(bx - ax, by - ay)) % 360))
                    placed += 1
            if placed >= want:
                break

    # Helicopter crashes in open country well away from towns and roads.
    open_land = land & (slope < 8.0) & np.isin(idx, [g.SURFACE_INDEX[n] for n in ("pasture", "farmland", "tussock")])
    road_mask = np.asarray(Image.open(g.SOURCE_DIR / "roads_4096.png")) > 0
    open_land &= ndimage.distance_transform_edt(~road_mask) * g.CELL > 60.0
    rows, cols = np.nonzero(open_land[::6, ::6])
    pts = np.array([world(r * 6, c * 6) for r, c in zip(rows, cols)])
    far = keep_out(towns, pois, 300.0)
    pts = np.array([q for q in pts if outside(far, *q)])
    for x, y in farthest_points(pts, HELI_CRASHES, rng):
        ev.setdefault("StaticHeliCrash", []).append((x, y, float(rng.uniform(0, 360))))

    # Police cars on town streets; convoys on the highways near the bases.
    for t in towns:
        if t["tier"] not in ("capital", "city", "town"):
            continue
        streets = [r for r in roads["roads"] if r["kind"] == "street" and r["ref"] == class_name(t["name"])]
        for r in rng.permutation(len(streets))[:2 if t["tier"] == "town" else 3]:
            (ax, ay), (bx, by) = streets[r]["points"][0], streets[r]["points"][-1]
            ev.setdefault("StaticPoliceCar", []).append(((ax + bx) / 2, (ay + by) / 2,
                                                         math.degrees(math.atan2(bx - ax, by - ay)) % 360))
    # Civilian cars parked along town streets, on the left kerb.
    for t in towns:
        if t["tier"] not in ("capital", "city", "town", "village"):
            continue
        streets = [r for r in roads["roads"] if r["kind"] == "street" and r["ref"] == class_name(t["name"])]
        share = {"capital": 0.5, "city": 0.4, "town": 0.35, "village": 0.3}[t["tier"]]
        for k in rng.permutation(len(streets))[:max(1, int(len(streets) * share))]:
            pts = np.array(streets[k]["points"])
            if len(pts) < 2:
                continue
            i = int(rng.integers(len(pts) - 1))
            (ax, ay), (bx, by) = pts[i], pts[i + 1]
            hd = math.degrees(math.atan2(bx - ax, by - ay)) % 360
            side = math.radians(hd - 90.0)
            f = float(rng.uniform(0.3, 0.7))
            px, py = ax + f * (bx - ax) + 4.0 * math.sin(side), ay + f * (by - ay) + 4.0 * math.cos(side)
            ev.setdefault(VEHICLES[int(rng.integers(len(VEHICLES)))], []).append((px, py, hd))

    return ev


def class_name(name: str) -> str:
    import unicodedata

    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return "".join(ch for ch in ascii_name.title() if ch.isalnum())


def fill_vehicle_gaps(ev, h, land, slope, roads, zones, safe):
    """Add farm utes where land is more than MAX_VEHICLE_GAP_M from any vehicle: on the nearest road
    within 800 m, else on flat open ground. Returns how many were added."""
    from scipy.spatial import cKDTree

    step = int(50 / g.CELL)
    rr, cc = np.nonzero(land[::step, ::step])
    land_xy = np.column_stack([(cc * step + 0.5) * g.CELL, g.SIZE_M - (rr * step + 0.5) * g.CELL])
    road_pts = np.array([p for r in roads["roads"] for p in r["points"]])
    road_tree = cKDTree(road_pts)
    cars = [(x, y) for name, pts in ev.items() if name.startswith("Vehicle") and name != "VehicleBoat"
            for x, y, _ in pts]
    added, tried = 0, set()
    while True:
        gap, _ = cKDTree(cars).query(land_xy)
        order = np.argsort(-gap)
        i = next((int(j) for j in order[:200] if gap[j] > MAX_VEHICLE_GAP_M and int(j) not in tried), None)
        if i is None:
            return added
        tried.add(i)
        x, y = land_xy[i]
        d, k = road_tree.query((x, y))
        hd = 0.0
        if d < 800.0:
            x, y = road_pts[k]
            nb = road_pts[min(k + 1, len(road_pts) - 1)] if k + 1 < len(road_pts) else road_pts[k - 1]
            hd = math.degrees(math.atan2(nb[0] - x, nb[1] - y)) % 360
            side = math.radians(hd - 90.0)
            x, y = x + 3.0 * math.sin(side), y + 3.0 * math.cos(side)
        r, c = int((g.SIZE_M - y) / g.CELL), int(x / g.CELL)
        if not (0 <= r < h.shape[0] and 0 <= c < h.shape[1]) or not land[r, c] or slope[r, c] > 15.0 \
                or not outside(zones, x, y) or not outside(safe, x, y):
            continue
        ev.setdefault("VehicleOffroadHatchback", []).append((float(x), float(y), hd))
        cars.append((x, y))
        added += 1


def write_events(ev, path, grouped=None):
    """ev: {event: [(x, y, a)]}; grouped: {event: [(x, y, z, group)]} for events that spawn a
    cfgeventgroups.xml group."""
    grouped = grouped or {}
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             "<!-- Event positions for Aotearoa, generated by tools/build_mission.py. -->", "<eventposdef>"]
    for name in sorted(set(ev) | set(grouped)):
        lines.append(f'    <event name="{name}">')
        if name in event_groups.ZONES:
            smin, smax, dmin, dmax, r = event_groups.ZONES[name]
            lines.append(f'        <zone smin="{smin}" smax="{smax}" dmin="{dmin}" dmax="{dmax}" r="{r}" />')
        lines += [f'        <pos x="{x:.1f}" z="{y:.1f}" a="{a:.0f}" />' for x, y, a in ev.get(name, [])]
        lines += [f'        <pos x="{x:.3f}" z="{y:.3f}" a="0" y="{z:.2f}" group="{grp}" />'
                  for x, y, z, grp in grouped.get(name, [])]
        lines.append("    </event>")
    lines.append("</eventposdef>\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def infected_zones(land, towns, pois, rng):
    zones = []

    def scatter(x, y, radius, n, name, dmin, dmax, r=45.0):
        placed = 0
        for _ in range(n * 30):
            if placed >= n:
                break
            a, d = rng.uniform(0, 2 * math.pi), radius * math.sqrt(rng.uniform(0, 1))
            px, py = x + d * math.cos(a), y + d * math.sin(a)
            rr, cc = cell(px, py)
            if land[rr, cc]:
                zones.append((name, dmin, dmax, px, py, r))
                placed += 1

    for t in towns:
        name, per100, dmin, dmax = INFECTED_ZONES[t["tier"]]
        radius = float(t["radius"])
        scatter(float(t["x"]), float(t["y"]), radius * 0.9, max(2, int(round(per100 * radius / 100.0))), name, dmin, dmax)
    for p in pois:
        if p["kind"] == "farm":
            scatter(p["x"], p["y"], 20.0, 1, "InfectedSolitude", 1, 2, 30.0)
        elif p["kind"] in ("bach", "hut"):
            scatter(p["x"], p["y"], 25.0, 1, "InfectedSolitude", 1, 2, 30.0)
        elif p["kind"] in ("surfclub", "campground", "station"):
            scatter(p["x"], p["y"], 30.0, 1, "InfectedVillage", 1, 3)
        elif p["kind"] in ("port", "industrial", "ferry"):
            scatter(p["x"], p["y"], 60.0, 2, "InfectedIndustrial", 2, 4)
        elif p["kind"] == "airfield":
            kind = "InfectedArmy" if "Ōhakea" in p["label"] else "InfectedIndustrial"
            scatter(p["x"], p["y"], 150.0, 3, kind, 2, 5)
        elif p["kind"] == "naval":
            scatter(p["x"], p["y"], 60.0, 3, "InfectedArmy", 2, 4)
        elif p["kind"] == "landmark":
            scatter(p["x"], p["y"], 20.0, 1, "InfectedSolitude", 1, 2, 30.0)
        elif p["kind"] in ("ski", "hobbiton"):
            scatter(p["x"], p["y"], 50.0, 2, "InfectedVillage", 1, 3)
    return zones


# Vanilla infected types for particular buildings and set pieces.
BUILDING_INFECTED = {"Land_City_PoliceStation": "InfectedPolice", "Land_Village_PoliceStation": "InfectedPolice",
                     "Land_City_Hospital": "InfectedMedic", "Land_Village_HealthCare": "InfectedMedic",
                     "Land_City_FireStation": "InfectedFirefighter", "Land_Church1_Yellow": "InfectedReligious",
                     "Land_Church2_1": "InfectedReligious", "Land_Church3": "InfectedReligious"}
SETPIECE_INFECTED = {"military": ("InfectedArmy", 2, 4), "gas": ("InfectedNBC", 2, 4), "wreck": ("InfectedArmy", 1, 3),
                     "landmark": ("InfectedCity", 2, 4)}


def special_infected(pieces, rng):
    zones = []
    for name in ("towns_spawner.json", "pois_spawner.json"):
        for o in json.loads((g.SOURCE_DIR / "objects" / name).read_text())["Objects"]:
            kind = BUILDING_INFECTED.get(o["name"])
            if kind:
                zones.append((kind, 1, 3, o["pos"][0], o["pos"][2], 30.0))
    for p in pieces:
        kind, dmin, dmax = SETPIECE_INFECTED[p.kind]
        if p.label == "Interislander wreck":
            kind = "InfectedVillage"
        if p.label.startswith("Waiouru") and p.kind == "military":
            kind = "InfectedArmyHard"
        for _, x, y, _, _ in p.objects[::2]:
            zones.append((kind, dmin, dmax, x + float(rng.uniform(-8, 8)), y + float(rng.uniform(-8, 8)), 35.0))
    return zones


def write_zombie_territories(zones, path):
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>',
             "<!-- Infected zones for Aotearoa, generated by tools/build_mission.py. -->",
             "<territory-type>", '    <territory color="4291611852">']
    lines += [f'        <zone name="{n}" smin="0" smax="0" dmin="{a}" dmax="{b}" x="{x:.1f}" z="{y:.1f}" r="{r:.0f}" />'
              for n, a, b, x, y, r in zones]
    lines += ["    </territory>", "</territory-type>", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_effect_area(h, land, pois, path, gas=()):
    areas, safe = [], []
    dist_sea = ndimage.distance_transform_edt(land) * g.CELL
    for zone in gas:
        areas.append({
            "AreaName": zone["name"],
            "Type": "ContaminatedArea_Static",
            "TriggerType": "ContaminatedTrigger",
            "Data": {
                "Pos": [round(zone["x"], 1), round(zone["z"], 1), round(zone["y"], 1)],
                "Radius": round(zone["radius"]),
                "PosHeight": 25,
                "NegHeight": 10,
                "InnerRingCount": 2,
                "InnerPartDist": 50,
                "OuterRingToggle": 1,
                "OuterPartDist": 40,
                "OuterOffset": 0,
                "VerticalLayers": 0,
                "VerticalOffset": 0,
                "ParticleName": "graphics/particles/contaminated_area_gas_bigass",
            },
            "PlayerData": {
                "AroundPartName": "graphics/particles/contaminated_area_gas_around",
                "TinyPartName": "graphics/particles/contaminated_area_gas_around_tiny",
                "PPERequesterType": "PPERequester_ContaminatedAreaTint",
            },
        })
        # Players who log in inside the gas are moved to open ground 150 m past its edge.
        for k in range(4):
            a = math.radians(45 + 90 * k)
            d = zone["radius"] + 150.0
            x, y = zone["x"] + d * math.sin(a), zone["y"] + d * math.cos(a)
            r, c = cell(x, y)
            if land[r, c]:
                safe.append([round(x, 1), round(y, 1)])
    for p in pois:
        if p["kind"] != "whakaari":
            continue
        r, c = cell(p["x"], p["y"])
        areas.append({
            "AreaName": "Whakaari",
            "Type": "ContaminatedArea_Static",
            "TriggerType": "ContaminatedTrigger",
            "Data": {
                "Pos": [round(p["x"], 1), round(float(max(h[r, c], 0.0)), 1), round(p["y"], 1)],
                "Radius": round(p["zone"]["radius"]),
                "PosHeight": 60,
                "NegHeight": 20,
                "InnerRingCount": 2,
                "InnerPartDist": 50,
                "OuterRingToggle": 1,
                "OuterPartDist": 40,
                "OuterOffset": 0,
                "VerticalLayers": 0,
                "VerticalOffset": 0,
                "ParticleName": "graphics/particles/contaminated_area_gas_bigass",
            },
            "PlayerData": {
                "AroundPartName": "graphics/particles/contaminated_area_gas_around",
                "TinyPartName": "graphics/particles/contaminated_area_gas_around_tiny",
                "PPERequesterType": "PPERequester_ContaminatedAreaTint",
            },
        })
        # Safe positions are where players caught in the zone at login get moved to: the
        # nearest stretch of mainland coast.
        cand = np.argwhere((dist_sea > 20.0) & (dist_sea < 60.0))
        pts = np.array([world(rr, cc) for rr, cc in cand[::7]])
        d = np.hypot(pts[:, 0] - p["x"], pts[:, 1] - p["y"])
        pts = pts[d > p["zone"]["radius"] + 300.0]
        d = d[d > p["zone"]["radius"] + 300.0]
        for x, y in pts[np.argsort(d)[:200:50]]:
            safe.append([round(float(x), 1), round(float(y), 1)])
    path.write_text(json.dumps({"Areas": areas, "SafePositions": safe}, indent=4, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def write_gameplay_snippet(path):
    data = {
        "WorldsData": {
            "environmentMinTemps": MIN_TEMPS,
            "environmentMaxTemps": MAX_TEMPS,
        },
        "PlayerData": {"spawnGearPresetFiles": server_files.preset_files()},
    }
    path.write_text(json.dumps(data, indent=4) + "\n")


INIT_C = r"""// init.c for Aotearoa, based on vanilla dayzOffline.chernarusplus.
void main()
{
	Hive ce = CreateHive();
	if ( ce )
		ce.InitOffline();

	// Seasons. The date follows the server clock (serverTime = "SystemTime"), so the seasons are
	// New Zealand's: summer in January, snow storms and short days in July. To stay in one
	// season, set pin_month to a month (1 = January, mid-summer; 7 = July, mid-winter).
	int pin_month = 0;
	int year, month, day, hour, minute;
	GetGame().GetWorld().GetDate(year, month, day, hour, minute);
	if (pin_month > 0 && month != pin_month)
	{
		GetGame().GetWorld().SetDate(year, pin_month, 10, hour, minute);
	}

	// Loot positions: once the world is built, uncomment the next two lines, start the server
	// once, and copy storage_1/export/mapgrouppos.xml and the mapgroupcluster*.xml files (fruit
	// trees, mushrooms) into this mission folder. Then comment them out again.
	// GetCEApi().ExportProxyData(Vector(12800, 0, 12800), 25600);
	// GetCEApi().ExportClusterData();
}

// Food stashes (tools/food_stashes.py): Countdown truck crashes, dairy stock rooms and bach
// pantries. Each is topped up when it runs low; delete aotearoa/food_stashes.json to turn them off.
class AotearoaStash
{
	string kind;
	string label;
	float x;
	float z;
	float r;
	int minItems;
	int maxItems;
	ref array<string> items;
}

class AotearoaStashFile
{
	int restockMinutes;
	ref array<ref AotearoaStash> stashes;
}

class AotearoaStashes
{
	ref AotearoaStashFile m_File;

	void AotearoaStashes()
	{
		string path = "$mission:aotearoa/food_stashes.json";
		if ( !FileExist( path ) )
			return;
		JsonFileLoader<AotearoaStashFile>.JsonLoadFile( path, m_File );
		if ( !m_File || !m_File.stashes )
			return;
		Restock();
		int minutes = m_File.restockMinutes;
		if ( minutes < 5 )
			minutes = 5;
		GetGame().GetCallQueue( CALL_CATEGORY_GAMEPLAY ).CallLater( Restock, minutes * 60000, true );
	}

	void Restock()
	{
		foreach ( AotearoaStash s : m_File.stashes )
		{
			if ( !s.items || s.items.Count() == 0 )
				continue;
			vector centre = Vector( s.x, GetGame().SurfaceY( s.x, s.z ), s.z );
			array<Object> near = new array<Object>;
			GetGame().GetObjectsAtPosition( centre, s.r + 2, near, null );
			int have = 0;
			foreach ( Object o : near )
			{
				if ( s.items.Find( o.GetType() ) != -1 )
					have++;
			}
			if ( have >= s.minItems )
				continue;
			int want = Math.RandomIntInclusive( s.minItems, s.maxItems ) - have;
			for ( int i = 0; i < want; i++ )
			{
				float a = Math.RandomFloat( 0, Math.PI2 );
				float d = Math.RandomFloat( 0, s.r );
				float px = s.x + Math.Cos( a ) * d;
				float pz = s.z + Math.Sin( a ) * d;
				GetGame().CreateObjectEx( s.items.GetRandomElement(), Vector( px, GetGame().SurfaceY( px, pz ), pz ), ECE_PLACE_ON_SURFACE );
			}
		}
	}
}

class CustomMission: MissionServer
{
	ref AotearoaStashes m_FoodStashes;

	override void OnInit()
	{
		super.OnInit();
		m_FoodStashes = new AotearoaStashes();
	}

	void SetRandomHealth(EntityAI itemEnt)
	{
		if ( itemEnt )
		{
			float rndHlt = Math.RandomFloat( 0.45, 0.65 );
			itemEnt.SetHealth01( "", "", rndHlt );
		}
	}

	override PlayerBase CreateCharacter(PlayerIdentity identity, vector pos, ParamsReadContext ctx, string characterName)
	{
		Entity playerEnt;
		playerEnt = GetGame().CreatePlayer( identity, characterName, pos, 0, "NONE" );
		Class.CastTo( m_player, playerEnt );
		GetGame().SelectPlayer( identity, m_player );
		return m_player;
	}

	override void StartingEquipSetup(PlayerBase player, bool clothesChosen)
	{
		EntityAI itemClothing;
		EntityAI itemEnt;
		float rand;

		itemClothing = player.FindAttachmentBySlotName( "Body" );
		if ( itemClothing )
		{
			SetRandomHealth( itemClothing );
			itemEnt = itemClothing.GetInventory().CreateInInventory( "BandageDressing" );
			player.SetQuickBarEntityShortcut( itemEnt, 2 );

			string chemlightArray[] = { "Chemlight_White", "Chemlight_Yellow", "Chemlight_Green", "Chemlight_Red" };
			int rndIndex = Math.RandomInt( 0, 4 );
			itemEnt = itemClothing.GetInventory().CreateInInventory( chemlightArray[rndIndex] );
			SetRandomHealth( itemEnt );
			player.SetQuickBarEntityShortcut( itemEnt, 1 );

			rand = Math.RandomFloatInclusive( 0.0, 1.0 );
			if ( rand < 0.35 )
				itemEnt = player.GetInventory().CreateInInventory( "Apple" );
			else if ( rand > 0.65 )
				itemEnt = player.GetInventory().CreateInInventory( "Pear" );
			else
				itemEnt = player.GetInventory().CreateInInventory( "Plum" );
			player.SetQuickBarEntityShortcut( itemEnt, 3 );
			SetRandomHealth( itemEnt );
		}

		itemClothing = player.FindAttachmentBySlotName( "Legs" );
		if ( itemClothing )
			SetRandomHealth( itemClothing );

		itemClothing = player.FindAttachmentBySlotName( "Feet" );
	}
};

Mission CreateCustomMission(string path)
{
	return new CustomMission();
}
"""

SERVER_CFG = """// serverDZ.cfg template for an Aotearoa server. Start the server with -mod=@Aotearoa
// (and the same mod on clients), and put dayzOffline.aotearoa in the server's mpmissions folder.
hostname = "Aotearoa";
password = "";
passwordAdmin = "CHANGE_ME";
description = "A 25.6 km New Zealand terrain";
maxPlayers = 60;
verifySignatures = 2;
forceSameBuild = 1;
disableVoN = 0;
vonCodecQuality = 20;
disable3rdPerson = 0;
disableCrosshair = 0;
disablePersonalLight = 1;
lightingConfig = 0;
serverTime = "SystemTime";
serverTimeAcceleration = 4;
serverNightTimeAcceleration = 8;
serverTimePersistent = 0;
guaranteedUpdates = 1;
loginQueueConcurrentPlayers = 5;
loginQueueMaxPlayers = 500;
instanceId = 1;
storageAutoFix = 1;
enableCfgGameplayFile = 1;
enableWhitelist = 0;          // 1 to only admit players listed in whitelist.txt

class Missions
{
	class DayZ
	{
		template = "dayzOffline.aotearoa";
	};
};
"""


def draw_preview(spawns, ev, zones, grouped, pieces):
    from PIL import ImageDraw

    img = Image.open(g.PREVIEW_DIR / "relief_2048.png").convert("RGB")
    d = ImageDraw.Draw(img)
    k = img.width / g.SIZE_M

    def dot(x, y, r, fill):
        px, py = x * k, (g.SIZE_M - y) * k
        d.ellipse([px - r, py - r, px + r, py + r], fill=fill, outline=(0, 0, 0))

    for _, _, _, x, y, _ in zones:
        dot(x, y, 2, (150, 0, 0))
    colours = {"StaticHeliCrash": (255, 140, 0), "StaticMilitaryConvoy": (60, 90, 40), "StaticPoliceCar": (40, 80, 255),
               "StaticPoliceSituation": (90, 120, 255), "StaticTrain": (120, 60, 20), "VehicleBoat": (0, 220, 255),
               "StaticContaminatedArea": (200, 230, 0), "ItemPlanks": (180, 140, 90)}
    for name, pts in ev.items():
        for x, y, _ in pts:
            dot(x, y, 3, colours.get(name, (255, 255, 255)))
    for name, pts in grouped.items():
        for x, y, _, _ in pts:
            dot(x, y, 4, colours.get(name, (255, 255, 255)))
    for p in pieces:
        dot(p.x, p.y, 7, (255, 0, 255))
    for x, y in spawns:
        dot(x, y, 6, (0, 255, 0))
    return img


def main() -> None:
    rng = np.random.default_rng(g.SEED + 20)
    h, idx, towns, roads, pois = load()
    land = h > 0.3
    gy, gx = np.gradient(h, g.CELL)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))

    out = OUT / MISSION
    out.mkdir(parents=True, exist_ok=True)
    (out / "init.c").write_text(INIT_C, newline="\r\n")
    (OUT / "serverDZ.cfg").write_text(SERVER_CFG, newline="\r\n")

    spawns = spawn_points(h, land, slope, towns, pois, rng)
    write_spawns(spawns, out / "cfgplayerspawnpoints.xml")
    traders = mod_support.build(h, towns, roads, pois, g.CELL, g.SIZE_M)
    safe = [(x, y, r + 50.0) for x, y, r in mod_support.safe_zones(traders)]
    sp = setpieces.build(h, land, towns, roads, pois, safe, rng)
    ev = events(h, idx, land, slope, towns, roads, pois, rng)
    ev = {name: [p for p in pts if outside(safe, p[0], p[1])] for name, pts in ev.items()}
    filled = fill_vehicle_gaps(ev, h, land, slope, roads, keep_out(towns, pois, 60.0), safe)
    eg = event_groups.build(h, towns, roads, pois, highway_samples(roads, 150.0), rng, safe, sp["placer"])
    for name, pts in eg["positions"].items():
        ev.setdefault(name, []).extend(pts)
    ev["StaticContaminatedArea"] = [(x, y, 0.0) for x, y in sp["dynamic_gas"]]
    write_events(ev, out / "cfgeventspawns.xml", eg["grouped"])
    event_groups.write_groups(eg["groups"], out / "cfgeventgroups.xml")
    zones = infected_zones(land, towns, pois, rng) + special_infected(sp["pieces"], rng)
    write_zombie_territories(zones, out / "env" / "zombie_territories.xml")
    write_effect_area(h, land, pois, out / "cfgEffectArea.json", sp["gas"])
    write_gameplay_snippet(out / "cfggameplay.worldsdata.json")
    economy.build(out, h, idx, land, towns, pois, rng)
    server_files.write(out, OUT / "server")
    road_signs = signs.build(h, towns, roads, g.CELL, g.SIZE_M)
    import labels
    labels.main()
    import food_stashes
    stashes = food_stashes.build()
    food_stashes.write(stashes)

    draw_preview(spawns, ev, zones, eg["grouped"], sp["pieces"]).save(g.PREVIEW_DIR / "mission_2048.png", optimize=True)
    print(f"Spawn points: {len(spawns)}")
    for name in sorted(set(ev) | set(eg["grouped"])):
        print(f"  {name}: {len(ev.get(name, [])) + len(eg['grouped'].get(name, []))}")
    print(f"  ({filled} farm utes added to close gaps over {MAX_VEHICLE_GAP_M:.0f} m)")
    print(f"Event groups: {len(eg['groups'])} (convoys, roadblocks, pile-ups and trains)")
    print("Set pieces: " + ", ".join(f"{p.label} ({len(p.objects)})" for p in sp["pieces"])
          + f"; {sp['objects']} objects")
    print(f"Infected zones: {len(zones)}")
    print(signs.summary(road_signs, towns))
    print(food_stashes.summary(stashes))
    print("Trader sites: " + ", ".join(t.name for t in traders))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
