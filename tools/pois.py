"""Points of interest for the Aotearoa terrain.

Airfields with runways, container ports, ski fields with lift lines, industrial plants, the
Devonport naval base, the Cape Reinga lighthouse, Hobbiton, farms along the highways, and Whakaari / White Island as a volcanic islet with a contaminated zone. Each site
is fitted onto dry land clear of towns, roads and water, flattened, and given vanilla DayZ
objects (class names to check against your P: drive, like the town buildings).

Writes source/pois.json (sites, paved surfaces and zones for the satellite and mission files)
and source/objects/pois_tb.txt / pois_spawner.json.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import numpy as np
from scipy import ndimage

import towns as towns_mod
from towns import Building

# Headings are multiples of 45 degrees for the same reason as the town grids: whichever way the
# engine turns yaw, a building at 45 + 90k lines up with something at 45 + 90k.
HEADINGS = (0.0, 45.0, 90.0, 135.0)

AIRFIELDS = [
    # name, label, lat, lon, near town
    ("AucklandAirport", "Auckland Airport", -37.008, 174.792, "Auckland"),
    ("ChristchurchAirport", "Christchurch Airport", -43.489, 172.532, "Christchurch"),
    ("OhakeaAirfield", "Ōhakea Airfield", -40.206, 175.388, "RNZAF Base Ōhakea"),
]
RUNWAY_LENGTH = 900.0
RUNWAY_WIDTH = 30.0
APRON = (160.0, 70.0)

PORTS = ["Auckland", "Wellington", "Christchurch", "Dunedin", "Tauranga", "Napier", "Picton", "Nelson",
         "Invercargill", "Timaru", "New Plymouth"]
PORT_NAMES = {"Christchurch": "Lyttelton", "Dunedin": "Port Chalmers", "Invercargill": "Bluff",
              "Tauranga": "Port of Tauranga", "Napier": "Port of Napier", "New Plymouth": "Port Taranaki"}
PORT_PAD = (130.0, 70.0)

SKI_FIELDS = [
    ("Remarkables", "The Remarkables", -45.054, 168.812),
    ("CoronetPeak", "Coronet Peak", -44.926, 168.736),
    ("MtHutt", "Mt Hutt", -43.474, 171.531),
    ("Whakapapa", "Whakapapa", -39.232, 175.558),
]
LIFT_LENGTH = 420.0

HOBBITON = ("Hobbiton", "Hobbiton", -37.8721, 175.6829)
INDUSTRIAL = [
    # name, label, lat, lon, layout
    ("FonterraWhareroa", "Fonterra Whareroa", -39.6130, 174.2620, "dairy"),
    ("FonterraEltham", "Fonterra Eltham", -39.4320, 174.2960, "dairy"),
    ("MarsdenPoint", "Marsden Point Refinery", -35.8350, 174.4970, "refinery"),
    ("HuntlyPowerStation", "Huntly Power Station", -37.5450, 175.1530, "power"),
    ("GlenbrookSteelMill", "Glenbrook Steel Mill", -37.2070, 174.7460, "mill"),
    ("KinleithMill", "Kinleith Mill", -38.2720, 175.9000, "mill"),
    ("TiwaiPointSmelter", "Tiwai Point Smelter", -46.5900, 168.3800, "smelter"),
]
INDUSTRIAL_PAD = (170.0, 110.0)
# layout: (along, across, class, quarter turns) relative to the pad centre; containers fill the rest.
INDUSTRIAL_LAYOUTS = {
    "dairy": [(-50.0, 20.0, "Land_Factory_Small", 1), (-15.0, 20.0, "Land_Factory_Small", 1),
              (20.0, 20.0, "Land_Factory_Small", 1), (55.0, 25.0, "Land_Barn_Metal_Big", 1),
              (-55.0, -32.0, "Land_Office2", 0), (5.0, -35.0, "Land_Shed_W4", 0)],
    "refinery": [(-55.0, 25.0, "Land_Tank_Big", 0), (-20.0, 25.0, "Land_Tank_Big", 0),
                 (15.0, 25.0, "Land_Tank_Big", 0), (-55.0, -10.0, "Land_Tank_Medium_Stairs", 0),
                 (-30.0, -10.0, "Land_Tank_Medium_Stairs", 0), (55.0, 20.0, "Land_Workshop1", 0),
                 (55.0, -30.0, "Land_Office2", 0), (0.0, -35.0, "Land_Factory_Small", 0)],
    "power": [(-35.0, 15.0, "Land_Power_Station", 0), (35.0, 30.0, "Land_Smokestack_Big", 0),
              (45.0, -10.0, "Land_Power_Transformer_Build", 0), (-55.0, -35.0, "Land_Office2", 0),
              (10.0, -35.0, "Land_Workshop1", 0)],
    "mill": [(-35.0, 20.0, "Land_Factory_Small", 1), (0.0, 20.0, "Land_Factory_Small", 1), (35.0, 20.0, "Land_Factory_Small", 1),
             (65.0, 25.0, "Land_Smokestack_Big", 0), (-55.0, -32.0, "Land_Office2", 0),
             (5.0, -32.0, "Land_Workshop1", 0)],
    "smelter": [(-45.0, 20.0, "Land_Factory_Small", 0), (0.0, 20.0, "Land_Factory_Small", 0), (45.0, 20.0, "Land_Factory_Small", 0),
                (-45.0, -15.0, "Land_Factory_Small", 0), (-55.0, -40.0, "Land_Office2", 0),
                (60.0, -25.0, "Land_Power_Transformer_Build", 0)],
}

NAVAL = ("DevonportNavalBase", "Devonport Naval Base", -36.8290, 174.7870, "Auckland")
LIGHTHOUSE = ("CapeReinga", "Cape Reinga / Te Rerenga Wairua", -34.4267, 172.6777)
# Landmarks outside the towns: (class, label, lat, lon, layout).
LANDMARKS = [
    ("MilfordSound", "Milford Sound / Piopiotahi", -44.6414, 167.8974, "lodge"),
    ("AorakiVillage", "Aoraki / Mount Cook Village", -43.7340, 170.0960, "lodge"),
    ("ChateauTongariro", "Chateau Tongariro", -39.2003, 175.5410, "hotel"),
    ("WaitomoCaves", "Waitomo Caves", -38.2609, 175.1036, "visitor"),
    ("HukaFalls", "Huka Falls", -38.6491, 176.0898, "visitor"),
    ("GoodShepherd", "Church of the Good Shepherd", -44.0047, 170.4772, "church"),
    ("MoerakiBoulders", "Moeraki Boulders", -45.3453, 170.8283, "boulders"),
    ("StirlingPoint", "Stirling Point", -46.6145, 168.3589, "signpost"),
    ("RakaiaHuts", "Rakaia Huts", -43.8990, 172.2120, "fishing_huts"),
]
# Pad size, then (class, along, across, quarter turns) for each building. The Chateau is vanilla's
# grand hotel.
LANDMARK_LAYOUTS = {
    "lodge": ((70.0, 50.0), [("Land_Village_Pub", 0.0, 6.0, 0), ("Land_House_2W01", -24.0, 8.0, 0),
                             ("Land_House_1W03", 24.0, 8.0, 0), ("Land_House_1W01", 24.0, -12.0, 2),
                             ("Land_Shed_W4", -26.0, -14.0, 0)]),
    "hotel": ((70.0, 60.0), [("Land_Hotel", 0.0, 8.0, 0), ("Land_Shed_W4", 28.0, -16.0, 0)]),
    "visitor": ((40.0, 35.0), [("Land_Village_HealthCare", 0.0, 6.0, 0), ("Land_Shed_W4", 14.0, -9.0, 0)]),
    "church": ((30.0, 30.0), [("Land_Church3", 0.0, 4.0, 0)]),
    "boulders": ((40.0, 30.0), [("Land_Shed_W4", -12.0, 8.0, 0)]),
    "signpost": ((30.0, 25.0), [("Land_House_1W02", -6.0, 5.0, 0), ("Land_Shed_W4", 9.0, 5.0, 0)]),
    # Salmon fishing huts and baches in two rows along a gravel lane, with boat sheds.
    "fishing_huts": ((100.0, 56.0), [("Land_House_1W01", -40.0, 14.0, 0), ("Land_House_1W04", -24.0, 14.0, 0),
                                     ("Land_House_1W02", -8.0, 14.0, 0), ("Land_House_1W06", 8.0, 14.0, 0),
                                     ("Land_House_1W05", 25.0, 14.0, 0), ("Land_House_1W01", 41.0, 14.0, 0),
                                     ("Land_House_1W03", -32.0, -12.0, 2), ("Land_House_1W02", -14.0, -12.0, 2),
                                     ("Land_House_1W06", 4.0, -12.0, 2), ("Land_Shed_W4", 20.0, -14.0, 0),
                                     ("Land_Shed_W4", 30.0, -14.0, 0), ("Land_Shed_W4", 40.0, -14.0, 0)]),
}
# Landmark layouts that are really small settlements, and the site kind they count as for loot and infected.
LANDMARK_KINDS = {"fishing_huts": "bach"}
BOULDERS = ["stone1", "stone2"]

WHAKAARI = ("Whakaari", "Whakaari / White Island", -37.52, 177.18)
WHAKAARI_RADIUS = 260.0
WHAKAARI_PEAK = 70.0

FERRIES = [("InterislanderWellington", "Interislander Terminal", "Wellington"),
           ("InterislanderPicton", "Picton Ferry Terminal", "Picton")]
BOAT_RAMPS = ["Paihia", "Whangārei", "Thames", "Whakatāne", "Gisborne", "Ōpunake", "Kaikōura", "Westport",
              "Greymouth", "Ōamaru", "Te Anau", "Taupō", "Wānaka", "Queenstown", "Picton", "Nelson"]
RAMP_PAD = (30.0, 8.0)
SURF_CLUBS = ["Auckland", "Tauranga", "Gisborne", "Napier", "New Plymouth", "Christchurch", "Dunedin", "Whangārei"]
HOLIDAY_PARKS = [("Taupō", "Lake Taupō Holiday Park"), ("Rotorua", "Rotorua Holiday Park"),
                 ("Wānaka", "Wānaka Lakeview Holiday Park"), ("Te Anau", "Te Anau Holiday Park"),
                 ("Queenstown", "Queenstown Holiday Park"), ("Hanmer Springs", "Hanmer Springs Holiday Park"),
                 ("Franz Josef", "Franz Josef Holiday Park"), ("Paihia", "Bay of Islands Holiday Park")]
BACH_CLUSTERS = 14
DOC_HUTS = 16
STATION_PAD = (34.0, 16.0)

FARM_COUNT = 70
FARM_SPACING = 320.0

FOOTPRINTS = {
    "Land_Airfield_Hangar_Green": (30, 40), "Land_Mil_ATC_Big": (14, 14),
    "Land_Airfield_ServiceHangar_L": (18, 28), "Land_Container_1Bo": (3, 12), "Land_Container_1Mo": (3, 12),
    "Land_Container_1Moh": (3, 12), "Land_Container_1Aoh": (3, 12), "Land_Factory_Small": (24, 48),
    "Land_Barn_Metal_Big": (16, 28), "Land_Farm_CowshedA": (12, 30), "Land_Shed_W4": (6, 8),
    "Land_Power_Pole_Wood1_Amp": (1, 1), "Land_Office2": (16, 28), "Land_Workshop1": (12, 20),
    "Land_Tank_Big": (24, 24), "Land_Tank_Medium_Stairs": (14, 14), "Land_Power_Station": (40, 60),
    "Land_Smokestack_Big": (10, 10), "Land_Power_Transformer_Build": (8, 10), "Land_Lighthouse": (10, 10),
    "Land_Mil_Barracks1": (10, 32), "Land_Mil_Barracks2": (10, 32), "Land_Mil_Guardhouse1": (6, 8),
    "Land_Rail_Station_Big": (12, 30),
    "Land_Hotel": (20, 50),
}
towns_mod.FOOTPRINTS.update(FOOTPRINTS)
CONTAINERS = ["Land_Container_1Bo", "Land_Container_1Mo", "Land_Container_1Moh", "Land_Container_1Aoh"]


@dataclass
class Site:
    kind: str
    class_name: str
    label: str
    x: float
    y: float
    radius: float
    heading: float = 0.0
    name_type: str = "Local"
    buildings: list[Building] = field(default_factory=list)
    surfaces: list[dict] = field(default_factory=list)  # {"kind": asphalt|concrete|gravel, "points": [...]}
    extra: dict = field(default_factory=dict)


def axes(heading: float) -> tuple[float, float]:
    hd = math.radians(heading)
    return math.sin(hd), math.cos(hd)


def local_to_world(cx, cy, heading, along, across):
    ax, ay = axes(heading)
    return cx + along * ax + across * ay, cy + along * ay - across * ax


def rect_points(cx, cy, heading, length, width, along0=0.0, across0=0.0):
    return [local_to_world(cx, cy, heading, along0 + sa * length / 2, across0 + sc * width / 2)
            for sa, sc in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def rect_local(grid, cx, cy, heading, reach):
    win, wx, wy = grid.window(cx, cy, reach)
    ax, ay = axes(heading)
    dx, dy = wx - cx, wy - cy
    return win, dx * ax + dy * ay, dx * ay - dy * ax


def rect_fits(ok: np.ndarray, grid, cx, cy, heading, length, width, need: float = 1.0) -> bool:
    step = max(grid.cell * 2, 10.0)
    al = np.arange(-length / 2, length / 2 + 0.1, step)
    ac = np.arange(-width / 2, width / 2 + 0.1, step)
    A, C = np.meshgrid(al, ac)
    x, y = local_to_world(cx, cy, heading, A.ravel(), C.ravel())
    r, c = grid.to_cell(x, y)
    r, c = np.rint(r).astype(int), np.rint(c).astype(int)
    inside = (r >= 0) & (r < grid.n) & (c >= 0) & (c < grid.n)
    if not inside.all():
        return False
    return float(ok[r, c].mean()) >= need


def rect_relief(h, grid, cx, cy, heading, length, width) -> float:
    step = max(grid.cell * 3, 15.0)
    A, C = np.meshgrid(np.arange(-length / 2, length / 2 + 0.1, step), np.arange(-width / 2, width / 2 + 0.1, step))
    x, y = local_to_world(cx, cy, heading, A.ravel(), C.ravel())
    z = grid.sample(h, x, y)
    G = np.column_stack([A.ravel(), C.ravel(), np.ones(A.size)])
    resid = z - G @ np.linalg.lstsq(G, z, rcond=None)[0]
    return float(np.sqrt(np.mean(resid ** 2)))


def flatten_rect(h, land, grid, cx, cy, heading, length, width, blend=40.0, max_grade=0.01, min_z=1.2):
    h = h.copy()
    reach0 = math.hypot(length, width) / 2
    win, al, ac = rect_local(grid, cx, cy, heading, reach0 + 2 * grid.cell)
    inner = (np.abs(al) <= length / 2) & (np.abs(ac) <= width / 2) & land[win]
    if inner.sum() < 4:
        return h
    G = np.column_stack([al[inner], ac[inner], np.ones(inner.sum())])
    a, b, c = np.linalg.lstsq(G, h[win][inner], rcond=None)[0]
    g = math.hypot(a, b)
    if g > max_grade:
        a, b = a * max_grade / g, b * max_grade / g
        c = float(np.median(h[win][inner] - a * al[inner] - b * ac[inner]))
    c = max(c, min_z)

    win2, al2, ac2 = rect_local(grid, cx, cy, heading, reach0 + blend * 4)
    out = np.hypot(np.maximum(np.abs(al2) - length / 2, 0), np.maximum(np.abs(ac2) - width / 2, 0))
    plane = a * al2 + b * ac2 + c
    ring = (out > 0) & (out < blend * 2) & land[win2]
    gap = np.abs(h[win2] - plane)[ring]
    reach = blend + 1.6 * (float(np.percentile(gap, 90)) if gap.size else 0.0)
    reach = min(reach, blend * 4)
    s = np.clip(1.0 - out / reach, 0.0, 1.0)
    w = s * s * (3 - 2 * s)
    hw = h[win2]
    h[win2] = np.where(land[win2], hw * (1 - w) + plane * w, hw)
    return h


def find_rect(ok, h, grid, cx, cy, search_r, length, width, headings=HEADINGS, need=1.0, step=40.0):
    """Best placement near (cx, cy): fits on ok cells, flat, and close to the target."""
    best, best_score = None, math.inf
    n = int(search_r / step)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = cx + i * step, cy + j * step
            d = math.hypot(x - cx, y - cy)
            if d > search_r:
                continue
            for hd in headings:
                if not rect_fits(ok, grid, x, y, hd, length, width, need):
                    continue
                score = rect_relief(h, grid, x, y, hd, length, width) + 0.004 * d
                if score < best_score:
                    best, best_score = (x, y, hd), score
    return best


def mark(blocked, grid, cx, cy, heading, length, width, pad=15.0):
    win, al, ac = rect_local(grid, cx, cy, heading, math.hypot(length, width) / 2 + pad + grid.cell)
    blocked[win] |= (np.abs(al) <= length / 2 + pad) & (np.abs(ac) <= width / 2 + pad)


def build_pois(h, land, lake_mask, river_mask, road_footprint, towns, grid,
               lonlat_to_world: Callable, seed: int):
    rng = np.random.default_rng(seed)
    by_name = {t.name: t for t in towns}
    sites: list[Site] = []

    h, land, whakaari = make_whakaari(h, land, grid, lonlat_to_world)
    if whakaari:
        sites.append(whakaari)

    town_zone = ndimage.binary_dilation(towns_mod.town_mask(towns, grid), iterations=6)
    roads_zone = ndimage.binary_dilation(road_footprint > 0, iterations=2)
    blocked = town_zone | roads_zone | lake_mask | ndimage.binary_dilation(river_mask, iterations=2)
    ok = lambda: land & ~blocked & (ndimage.distance_transform_edt(land) * grid.cell > 15.0)  # noqa: E731
    ok_now = ok()

    for cls, label, lat, lon, near in AIRFIELDS:
        tx, ty = lonlat_to_world(lon, lat)
        t = by_name[near]
        tx, ty = 0.5 * (tx + t.x), 0.5 * (ty + t.y)
        length, width = RUNWAY_LENGTH + 40.0, RUNWAY_WIDTH + 2 * APRON[1] + 20.0
        spot = find_rect(ok_now, h, grid, tx, ty, 2500.0, length, width, step=60.0)
        if spot is None:
            print(f"  {label}: no room for a runway")
            continue
        x, y, hd = spot
        h = flatten_rect(h, land, grid, x, y, hd, length, width, blend=50.0)
        site = Site("airfield", cls, label, x, y, length / 2, hd, "Local")
        site.surfaces.append({"kind": "asphalt", "points": rect_points(x, y, hd, RUNWAY_LENGTH, RUNWAY_WIDTH)})
        apron_c = RUNWAY_WIDTH / 2 + 25.0 + APRON[1] / 2
        site.surfaces.append({"kind": "concrete", "points": rect_points(x, y, hd, APRON[0], APRON[1], 0.0, apron_c)})
        site.surfaces.append({"kind": "asphalt", "points": rect_points(x, y, hd, 14.0, 30.0, 0.0, RUNWAY_WIDTH / 2 + 15.0)})
        site.extra["runway"] = {"length": RUNWAY_LENGTH, "width": RUNWAY_WIDTH}
        site.extra["entrance"] = local_to_world(x, y, hd, 0.0, apron_c + APRON[1] / 2 + 45.0)
        for along, cls_b, turn in ((-55.0, "Land_Airfield_Hangar_Green", 0), (-15.0, "Land_Airfield_Hangar_Green", 0),
                                   (30.0, "Land_Airfield_ServiceHangar_L", 0), (65.0, "Land_Mil_ATC_Big", 0)):
            bx, by = local_to_world(x, y, hd, along, apron_c + APRON[1] / 2 + 22.0)
            site.buildings.append(Building(cls_b, bx, by, (hd + 90.0 * turn) % 360))
        sites.append(site)
        mark(blocked, grid, x, y, hd, length, width)
        ok_now = ok()
        print(f"  {label}: runway heading {hd:.0f}")

    dist_sea = ndimage.distance_transform_edt(land) * grid.cell
    for town_name in PORTS:
        t = by_name[town_name]
        label = PORT_NAMES.get(town_name, f"Port of {town_name}")
        near_coast = (dist_sea > 25.0) & (dist_sea < 45.0)
        port_ok = land & ~blocked
        spot = None
        for search in (t.radius + 500.0, t.radius + 1200.0, t.radius + 2200.0):
            spot = find_port(port_ok, near_coast, h, dist_sea, grid, t, search)
            if spot:
                break
        if spot is None:
            print(f"  {label}: no coastal room")
            continue
        x, y, hd = spot
        h = flatten_rect(h, land, grid, x, y, hd, PORT_PAD[0], PORT_PAD[1], blend=25.0, min_z=2.0)
        site = Site("port", label.replace(" ", "").replace("PortOf", "Port"), label, x, y, PORT_PAD[0] / 2, hd)
        site.surfaces.append({"kind": "concrete", "points": rect_points(x, y, hd, *PORT_PAD)})
        for row in range(4):
            for col in range(6):
                if rng.random() < 0.2:
                    continue
                bx, by = local_to_world(x, y, hd, -50.0 + col * 15.0, -26.0 + row * 9.0)
                site.buildings.append(Building(CONTAINERS[rng.integers(len(CONTAINERS))], bx, by, hd % 360))
        bx, by = local_to_world(x, y, hd, 25.0, 18.0)
        site.buildings.append(Building("Land_Factory_Small", bx, by, (hd + 90.0) % 360))
        sites.append(site)
        mark(blocked, grid, x, y, hd, *PORT_PAD)
        print(f"  {label}: port")

    gy, gx = np.gradient(h, grid.cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    for cls, label, lat, lon in SKI_FIELDS:
        tx, ty = lonlat_to_world(lon, lat)
        site = place_ski_field(h, land, ok(), slope, grid, cls, label, tx, ty)
        if site is None:
            print(f"  {label}: no slope found")
            continue
        h = flatten_rect(h, land, grid, site.x, site.y, site.heading, 60.0, 40.0, blend=25.0, max_grade=0.03)
        sites.append(site)
        # Neighbouring fields (Coronet Peak and the Remarkables) must not pick the same summit.
        mark(blocked, grid, site.x, site.y, site.heading, 60.0, 40.0, pad=800.0)
        print(f"  {label}: lodge at {grid.sample(h, site.x, site.y)[0]:.0f} m")

    for cls, label, lat, lon, layout in INDUSTRIAL:
        tx, ty = lonlat_to_world(lon, lat)
        spot = find_rect(ok(), h, grid, tx, ty, 1500.0, *INDUSTRIAL_PAD)
        if spot is None:
            print(f"  {label}: no room")
            continue
        x, y, hd = spot
        h = flatten_rect(h, land, grid, x, y, hd, *INDUSTRIAL_PAD, blend=40.0)
        site = Site("industrial", cls, label, x, y, INDUSTRIAL_PAD[0] / 2, hd, "Local")
        site.surfaces.append({"kind": "concrete", "points": rect_points(x, y, hd, *INDUSTRIAL_PAD)})
        for along, across, cls_b, turn in INDUSTRIAL_LAYOUTS[layout]:
            bx, by = local_to_world(x, y, hd, along, across)
            site.buildings.append(Building(cls_b, bx, by, (hd + 90.0 * turn) % 360))
        for k in range(8 if layout == "dairy" else 4):
            bx, by = local_to_world(x, y, hd, 25.0 + (k % 4) * 15.0, -32.0 - (k // 4) * 9.0)
            site.buildings.append(Building(CONTAINERS[rng.integers(len(CONTAINERS))], bx, by, hd % 360))
        site.extra["layout"] = layout
        site.extra["entrance"] = local_to_world(x, y, hd, 0.0, -INDUSTRIAL_PAD[1] / 2 - 20.0)
        sites.append(site)
        mark(blocked, grid, x, y, hd, *INDUSTRIAL_PAD)
        print(f"  {label}: industrial site")

    cls, label, lat, lon, near = NAVAL
    tx, ty = lonlat_to_world(lon, lat)
    target = SimpleNamespace(x=tx, y=ty, radius=0.0)
    near_coast = (dist_sea > 25.0) & (dist_sea < 45.0)
    spot = None
    for search in (500.0, 1200.0):
        spot = find_port(land & ~blocked, near_coast, h, dist_sea, grid, target, search)
        if spot:
            break
    if spot:
        x, y, hd = spot
        h = flatten_rect(h, land, grid, x, y, hd, *PORT_PAD, blend=25.0, min_z=2.0)
        site = Site("naval", cls, label, x, y, PORT_PAD[0] / 2, hd)
        site.surfaces.append({"kind": "concrete", "points": rect_points(x, y, hd, *PORT_PAD)})
        for along, across, cls_b, turn in ((-40.0, 18.0, "Land_Mil_Barracks1", 1), (-15.0, 18.0, "Land_Mil_Barracks2", 1),
                                           (25.0, 18.0, "Land_Factory_Small", 0), (-50.0, -22.0, "Land_Mil_Guardhouse1", 0),
                                           (0.0, -20.0, "Land_Mil_ATC_Small", 0)):
            bx, by = local_to_world(x, y, hd, along, across)
            site.buildings.append(Building(cls_b, bx, by, (hd + 90.0 * turn) % 360))
        for k in range(6):
            bx, by = local_to_world(x, y, hd, 20.0 + (k % 3) * 15.0, -18.0 - (k // 3) * 9.0)
            site.buildings.append(Building(CONTAINERS[rng.integers(len(CONTAINERS))], bx, by, hd % 360))
        sites.append(site)
        mark(blocked, grid, x, y, hd, *PORT_PAD)
        print(f"  {label}: naval base")
    else:
        print(f"  {label}: no coastal room")

    cls, label, lat, lon = LIGHTHOUSE
    tx, ty = lonlat_to_world(lon, lat)
    spot = find_rect(ok(), h, grid, tx, ty, 900.0, 40.0, 40.0, step=20.0)
    if spot:
        x, y, hd = spot
        h = flatten_rect(h, land, grid, x, y, hd, 40.0, 40.0, blend=20.0, max_grade=0.05)
        site = Site("landmark", cls, label, x, y, 25.0, hd, "Local")
        site.buildings.append(Building("Land_Lighthouse", x, y, hd))
        site.buildings.append(Building("Land_Shed_W4", *local_to_world(x, y, hd, -14.0, 12.0), hd))
        site.surfaces.append({"kind": "gravel", "points": rect_points(x, y, hd, 30.0, 8.0, 0.0, -16.0)})
        sites.append(site)
        mark(blocked, grid, x, y, hd, 40.0, 40.0)
        print(f"  {label}: lighthouse")

    for cls, label, lat, lon, layout in LANDMARKS:
        tx, ty = lonlat_to_world(lon, lat)
        (length, width), parts = LANDMARK_LAYOUTS[layout]
        spot = find_rect(ok(), h, grid, tx, ty, 1200.0, length, width, step=20.0)
        if spot is None:
            print(f"  {label}: no room")
            continue
        x, y, hd = spot
        h = flatten_rect(h, land, grid, x, y, hd, length, width, blend=20.0, max_grade=0.05)
        site = Site(LANDMARK_KINDS.get(layout, "landmark"), cls, label, x, y, max(length, width) / 2, hd, "Local")
        for b_cls, along, across, turn in parts:
            site.buildings.append(Building(b_cls, *local_to_world(x, y, hd, along, across), (hd + 90.0 * turn) % 360))
        if layout == "fishing_huts":
            site.surfaces.append({"kind": "gravel", "points": rect_points(x, y, hd, length * 0.95, 6.0, 0.0, 1.0)})
        else:
            site.surfaces.append({"kind": "gravel",
                                  "points": rect_points(x, y, hd, length * 0.6, 8.0, 0.0, -width / 2 + 6.0)})
        if layout == "boulders":
            site.extra["props"] = [(str(rng.choice(BOULDERS)), *local_to_world(x, y, hd, float(rng.uniform(-60, 60)),
                                                                              float(rng.uniform(-40, -20))),
                                    float(rng.uniform(0, 360)), float(rng.uniform(0.5, 0.9))) for _ in range(14)]
        sites.append(site)
        mark(blocked, grid, x, y, hd, length, width)
        print(f"  {label}: landmark")

    cls, label, lat, lon = HOBBITON
    tx, ty = lonlat_to_world(lon, lat)
    spot = find_rect(ok(), h, grid, tx, ty, 1500.0, 140.0, 110.0, headings=(0.0, 45.0))
    if spot:
        x, y, hd = spot
        h = flatten_rect(h, land, grid, x, y, hd, 140.0, 110.0, blend=40.0, max_grade=0.05)
        site = Site("hobbiton", cls, label, x, y, 80.0, hd, "Village")
        # Hobbit holes need a custom model; ordinary cottages stand in until there is one.
        for k in range(9):
            ang = 2 * math.pi * k / 9
            bx, by = x + 45.0 * math.cos(ang), y + 38.0 * math.sin(ang)
            site.buildings.append(Building(towns_mod.HOUSES[k % 6][0], bx, by, (hd + 90.0 * (k % 4)) % 360))
        site.buildings.append(Building("Land_Village_Pub", *local_to_world(x, y, hd, 0.0, 0.0), hd))
        site.surfaces.append({"kind": "gravel", "points": rect_points(x, y, hd, 100.0, 6.0)})
        sites.append(site)
        mark(blocked, grid, x, y, hd, 140.0, 110.0)
        print("  Hobbiton placed")

    # Interislander terminals: the only big boats between the islands start here.
    for cls, label, near in FERRIES:
        t = by_name[near]
        near_coast = (dist_sea > 25.0) & (dist_sea < 45.0)
        spot = None
        for search in (t.radius + 500.0, t.radius + 1200.0, t.radius + 2200.0):
            spot = find_port(land & ~blocked, near_coast, h, dist_sea, grid, t, search)
            if spot:
                break
        if spot is None:
            print(f"  {label}: no coastal room")
            continue
        x, y, hd = spot
        h = flatten_rect(h, land, grid, x, y, hd, *PORT_PAD, blend=25.0, min_z=2.0)
        site = Site("ferry", cls, label, x, y, PORT_PAD[0] / 2, hd)
        site.surfaces.append({"kind": "concrete", "points": rect_points(x, y, hd, *PORT_PAD)})
        for along, across, cls_b, turn in ((-30.0, 18.0, "Land_Factory_Small", 0), (35.0, 20.0, "Land_Office2", 1),
                                           (40.0, -20.0, "Land_Mil_ATC_Small", 0)):
            site.buildings.append(Building(cls_b, *local_to_world(x, y, hd, along, across), (hd + 90.0 * turn) % 360))
        for k in range(6):
            bx, by = local_to_world(x, y, hd, -50.0 + (k % 3) * 15.0, -18.0 - (k // 3) * 9.0)
            site.buildings.append(Building(CONTAINERS[rng.integers(len(CONTAINERS))], bx, by, hd % 360))
        sites.append(site)
        mark(blocked, grid, x, y, hd, *PORT_PAD)
        print(f"  {label}: ferry terminal")

    dist_water = ndimage.distance_transform_edt(land & ~lake_mask) * grid.cell
    near_coast = (dist_water > 8.0) & (dist_water < 25.0)
    for town_name in BOAT_RAMPS:
        t = by_name[town_name]
        spot = None
        for search in (t.radius + 400.0, t.radius + 1000.0):
            spot = find_coast_spot(land & ~blocked, near_coast, h, dist_water, grid, t, search, *RAMP_PAD)
            if spot:
                break
        if spot is None:
            continue
        x, y, hd = spot
        h = flatten_rect(h, land, grid, x, y, hd, *RAMP_PAD, blend=12.0, max_grade=0.08, min_z=0.6)
        site = Site("ramp", f"BoatRamp{t.class_name}", "", x, y, RAMP_PAD[0] / 2, hd, "")
        site.surfaces.append({"kind": "concrete", "points": rect_points(x, y, hd, *RAMP_PAD)})
        site.buildings.append(Building("Land_Shed_W4", *local_to_world(x, y, hd, -10.0, 9.0), hd))
        sites.append(site)
        mark(blocked, grid, x, y, hd, *RAMP_PAD)
    print(f"  Boat ramps: {sum(s.kind == 'ramp' for s in sites)}")

    near_beach = (dist_sea > 40.0) & (dist_sea < 90.0) & (h < 12.0)
    for town_name in SURF_CLUBS:
        t = by_name[town_name]
        spot = None
        for search in (t.radius + 500.0, t.radius + 1200.0):
            spot = find_coast_spot(ok(), near_beach, h, dist_sea, grid, t, search, 40.0, 30.0)
            if spot:
                break
        if spot is None:
            continue
        x, y, hd = spot
        h = flatten_rect(h, land, grid, x, y, hd, 40.0, 30.0, blend=20.0, min_z=2.0)
        site = Site("surfclub", f"SurfClub{t.class_name}", f"{t.name} Surf Life Saving Club", x, y, 22.0, hd,
                    "Local")
        site.buildings.append(Building("Land_Village_HealthCare", x, y, hd))
        site.buildings.append(Building("Land_Shed_W4", *local_to_world(x, y, hd, 14.0, -8.0), hd))
        site.surfaces.append({"kind": "gravel", "points": rect_points(x, y, hd, 30.0, 8.0, 0.0, -14.0)})
        sites.append(site)
        mark(blocked, grid, x, y, hd, 40.0, 30.0)
    print(f"  Surf clubs: {sum(s.kind == 'surfclub' for s in sites)}")

    for town_name, label in HOLIDAY_PARKS:
        t = by_name[town_name]
        spot = find_rect(ok(), h, grid, t.x, t.y, t.radius + 900.0, 70.0, 50.0, step=30.0)
        if spot is None:
            continue
        x, y, hd = spot
        h = flatten_rect(h, land, grid, x, y, hd, 70.0, 50.0, blend=25.0, max_grade=0.03)
        site = Site("campground", f"HolidayPark{t.class_name}", label, x, y, 40.0, hd, "Local")
        site.buildings.append(Building(towns_mod.HOUSES[0][0], *local_to_world(x, y, hd, -24.0, -14.0), hd))
        site.buildings.append(Building("Land_Shed_W4", *local_to_world(x, y, hd, -24.0, 10.0), hd))
        for k in range(4):
            site.buildings.append(Building("Land_Mil_Tent_Big1_1",
                                           *local_to_world(x, y, hd, 2.0 + (k % 2) * 22.0, -12.0 + (k // 2) * 24.0),
                                           (hd + 90.0) % 360))
        site.surfaces.append({"kind": "gravel", "points": rect_points(x, y, hd, 60.0, 6.0)})
        sites.append(site)
        mark(blocked, grid, x, y, hd, 70.0, 50.0)
    print(f"  Holiday parks: {sum(s.kind == 'campground' for s in sites)}")

    h, extra = place_baches(h, land, ok(), dist_sea, grid, rng, by_name)
    for s in extra:
        mark(blocked, grid, s.x, s.y, s.heading, 60.0, 30.0)
    sites.extend(extra)
    print(f"  Bach clusters: {len(extra)}")

    h, extra = place_huts(h, land, ok(), grid, rng)
    sites.extend(extra)
    print(f"  DOC huts: {len(extra)}")

    h, farms = place_farms(h, land, ok(), road_footprint, grid, rng)
    sites.extend(farms)
    print(f"  Farms: {len(farms)}")

    for s in sites:
        for b in s.buildings:
            b.z = float(grid.sample(h, b.x, b.y)[0])
    return h, land, sites


def find_port(ok, near_coast, h, dist_sea, grid, t, search):
    best, best_score = None, math.inf
    step = 30.0
    n = int(search / step)
    gy, gx = np.gradient(dist_sea)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = t.x + i * step, t.y + j * step
            d = math.hypot(x - t.x, y - t.y)
            if d > search or d < t.radius + 40.0:
                continue
            r, c = grid.to_cell(x, y)
            r, c = int(round(float(r))), int(round(float(c)))
            if not (0 <= r < grid.n and 0 <= c < grid.n) or not near_coast[r, c]:
                continue
            # Long side along the shore: perpendicular to the direction away from the sea.
            inland = math.degrees(math.atan2(gx[r, c], -gy[r, c])) % 180
            along_shore = (inland + 90.0) % 180
            hd = min(HEADINGS, key=lambda a: min(abs(a - along_shore), 180 - abs(a - along_shore)))
            if not rect_fits(ok, grid, x, y, hd, PORT_PAD[0], PORT_PAD[1], need=0.85):
                continue
            score = rect_relief(h, grid, x, y, hd, *PORT_PAD) + 0.01 * d
            if score < best_score:
                best, best_score = (x, y, hd), score
    return best


def place_ski_field(h, land, ok, slope, grid, cls, label, tx, ty) -> Site | None:
    best, best_score = None, math.inf
    step = 40.0
    for i in range(-60, 61):
        for j in range(-60, 61):
            x, y = tx + i * step, ty + j * step
            d = math.hypot(x - tx, y - ty)
            if d > 2400.0:
                continue
            for hd in (0.0, 90.0):
                if not rect_fits(ok, grid, x, y, hd, 60.0, 40.0):
                    continue
                z = float(grid.sample(h, x, y)[0])
                relief = rect_relief(h, grid, x, y, hd, 60.0, 40.0)
                score = -z + 6.0 * relief + 0.01 * d
                if score < best_score:
                    best, best_score = (x, y, hd), score
    if best is None:
        return None
    x, y, hd = best
    site = Site("ski", cls, label, x, y, 120.0, hd, "Local")
    site.buildings.append(Building("Land_Village_Pub", x, y, hd))
    site.surfaces.append({"kind": "gravel", "points": rect_points(x, y, hd, 50.0, 30.0)})

    # Lift line straight up the fall line from the lodge, with a tower every 50 m.
    gy, gx = np.gradient(ndimage.gaussian_filter(h, 6.0), grid.cell)
    r, c = grid.to_cell(x, y)
    ux, uy = float(ndimage.map_coordinates(gx, [[r], [c]], order=1)[0]), \
        -float(ndimage.map_coordinates(gy, [[r], [c]], order=1)[0])
    norm = math.hypot(ux, uy) or 1.0
    ux, uy = ux / norm, uy / norm
    towers = []
    for k in range(1, int(LIFT_LENGTH / 50.0) + 1):
        px, py = x + ux * (30.0 + 50.0 * k), y + uy * (30.0 + 50.0 * k)
        rr, cc = grid.to_cell(px, py)
        if not (0 <= rr < grid.n and 0 <= cc < grid.n) or not land[int(rr), int(cc)]:
            break
        towers.append((px, py))
        site.buildings.append(Building("Land_Power_Pole_Wood1_Amp", px, py, math.degrees(math.atan2(ux, uy)) % 360))
    site.extra["lift"] = [[round(px, 1), round(py, 1)] for px, py in [(x, y)] + towers]
    return site


def find_coast_spot(ok, band, h, dist_sea, grid, t, search, length, width):
    """Like find_port, for smaller pads: long side along the shore, inside the band."""
    best, best_score = None, math.inf
    step = 20.0
    n = int(search / step)
    gy, gx = np.gradient(dist_sea)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = t.x + i * step, t.y + j * step
            d = math.hypot(x - t.x, y - t.y)
            if d > search or d < t.radius + 30.0:
                continue
            r, c = grid.to_cell(x, y)
            r, c = int(round(float(r))), int(round(float(c)))
            if not (0 <= r < grid.n and 0 <= c < grid.n) or not band[r, c]:
                continue
            inland = math.degrees(math.atan2(gx[r, c], -gy[r, c])) % 180
            # A ramp runs down into the water; everything else lies along the shore.
            want = inland if length > 3 * width else (inland + 90.0) % 180
            hd = min(HEADINGS, key=lambda a: min(abs(a - want), 180 - abs(a - want)))
            if not rect_fits(ok, grid, x, y, hd, length, width, need=0.6 if length > 3 * width else 0.9):
                continue
            score = rect_relief(h, grid, x, y, hd, length, width) + 0.01 * d
            if score < best_score:
                best, best_score = (x, y, hd), score
    return best


def place_baches(h, land, ok, dist_sea, grid, rng, by_name):
    """Rows of holiday homes behind quiet beaches, away from the towns."""
    cand = ok & (dist_sea > 50.0) & (dist_sea < 110.0) & (h < 10.0)
    rows, cols = np.nonzero(cand[::6, ::6])
    order = rng.permutation(len(rows))
    out, taken = [], [(t.x, t.y, t.radius + 700.0) for t in by_name.values()]
    gy, gx = np.gradient(dist_sea)
    for k in order:
        if len(out) >= BACH_CLUSTERS:
            break
        r, c = rows[k] * 6, cols[k] * 6
        x, y = (c + 0.5) * grid.cell, grid.size_m - (r + 0.5) * grid.cell
        if any(math.hypot(x - a, y - b) < rr for a, b, rr in taken):
            continue
        inland = math.degrees(math.atan2(gx[r, c], -gy[r, c])) % 180
        hd = min(HEADINGS, key=lambda a: min(abs(a - (inland + 90.0) % 180), 180 - abs(a - (inland + 90.0) % 180)))
        if not rect_fits(ok, grid, x, y, hd, 60.0, 30.0):
            continue
        h = flatten_rect(h, land, grid, x, y, hd, 60.0, 30.0, blend=20.0, max_grade=0.04, min_z=2.0)
        site = Site("bach", f"Baches{len(out) + 1:02d}", "", x, y, 32.0, hd, "")
        for i in range(4):
            cls = towns_mod.HOUSES[int(rng.integers(6))][0]
            site.buildings.append(Building(cls, *local_to_world(x, y, hd, -22.5 + i * 15.0, 4.0), hd))
        site.surfaces.append({"kind": "gravel", "points": rect_points(x, y, hd, 60.0, 5.0, 0.0, -10.0)})
        out.append(site)
        taken.append((x, y, 900.0))
    return h, out


def place_huts(h, land, ok, grid, rng):
    """Back-country huts high in the ranges, on the few flat benches."""
    gy, gx = np.gradient(h, grid.cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    cand = ok & (h > 250.0) & (h < 480.0) & (slope < 10.0)
    rows, cols = np.nonzero(cand[::6, ::6])
    order = rng.permutation(len(rows))
    out, taken = [], []
    for k in order:
        if len(out) >= DOC_HUTS:
            break
        x, y = (cols[k] * 6 + 0.5) * grid.cell, grid.size_m - (rows[k] * 6 + 0.5) * grid.cell
        if any(math.hypot(x - a, y - b) < 1200.0 for a, b in taken):
            continue
        hd = float(rng.choice([0.0, 90.0]))
        if not rect_fits(ok, grid, x, y, hd, 24.0, 18.0):
            continue
        h = flatten_rect(h, land, grid, x, y, hd, 24.0, 18.0, blend=15.0, max_grade=0.05)
        site = Site("hut", f"DocHut{len(out) + 1:02d}", "", x, y, 14.0, hd, "")
        site.buildings.append(Building(towns_mod.HOUSES[0][0], x, y, hd))
        site.buildings.append(Building("Land_Shed_W4", *local_to_world(x, y, hd, 9.0, 6.0), hd))
        out.append(site)
        taken.append((x, y))
    return h, out


def make_stations(h, land, stations, grid):
    """A station building at each stop on the railway, beside the line."""
    out = []
    for st in stations:
        x, y, hd = st["x"], st["y"], st["heading"]
        bx, by = local_to_world(x, y, hd, 0.0, 14.0)
        h = flatten_rect(h, land, grid, bx, by, hd, *STATION_PAD, blend=15.0, max_grade=0.02)
        site = Site("station", "Station" + "".join(ch for ch in st["town"] if ch.isascii() and ch.isalnum()), "",
                    bx, by, 18.0, hd, "")
        site.buildings.append(Building("Land_Rail_Station_Big", bx, by, hd))
        site.surfaces.append({"kind": "concrete", "points": rect_points(bx, by, hd, STATION_PAD[0], 6.0, 0.0, -8.0)})
        out.append(site)
    return h, out


def place_farms(h, land, ok, road_footprint, grid, rng):
    gy, gx = np.gradient(h, grid.cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    road_dist = ndimage.distance_transform_edt(road_footprint == 0) * grid.cell
    cand = ok & (slope < 6.0) & (h < 220.0) & (h > 3.0) & (road_dist > 30.0) & (road_dist < 120.0)
    rows, cols = np.nonzero(cand[::8, ::8])
    order = rng.permutation(len(rows))
    farms: list[Site] = []
    taken: list[tuple[float, float]] = []
    for k in order:
        if len(farms) >= FARM_COUNT:
            break
        r, c = rows[k] * 8, cols[k] * 8
        x, y = (c + 0.5) * grid.cell, grid.size_m - (r + 0.5) * grid.cell
        if any(math.hypot(x - a, y - b) < FARM_SPACING for a, b in taken):
            continue
        hd = float(rng.choice([0.0, 90.0]))
        if not rect_fits(ok, grid, x, y, hd, 60.0, 50.0):
            continue
        h = flatten_rect(h, land, grid, x, y, hd, 60.0, 50.0, blend=20.0, max_grade=0.04)
        n = len(farms) + 1
        site = Site("farm", f"Farm{n:02d}", "", x, y, 35.0, hd, "")
        site.buildings.append(Building(towns_mod.HOUSES[int(rng.integers(6))][0],
                                       *local_to_world(x, y, hd, -15.0, -12.0), hd))
        site.buildings.append(Building(str(rng.choice(["Land_Barn_Metal_Big", "Land_Farm_CowshedA"])),
                                       *local_to_world(x, y, hd, 10.0, 8.0), hd))
        site.buildings.append(Building("Land_Shed_W4", *local_to_world(x, y, hd, -18.0, 14.0), hd))
        site.surfaces.append({"kind": "gravel", "points": rect_points(x, y, hd, 40.0, 30.0)})
        farms.append(site)
        taken.append((x, y))
    return h, farms


def make_whakaari(h, land, grid, lonlat_to_world):
    cls, label, lat, lon = WHAKAARI
    x, y = lonlat_to_world(lon, lat)
    x = float(np.clip(x, WHAKAARI_RADIUS + 200.0, grid.size_m - WHAKAARI_RADIUS - 200.0))
    y = float(np.clip(y, WHAKAARI_RADIUS + 200.0, grid.size_m - WHAKAARI_RADIUS - 200.0))
    win, wx, wy = grid.window(x, y, WHAKAARI_RADIUS * 1.6)
    d = np.hypot(wx - x, wy - y)
    if land[win][d < WHAKAARI_RADIUS * 1.2].any():
        print("  Whakaari: site already has land, skipped")
        return h, land, None
    noise = ndimage.gaussian_filter(np.random.default_rng(7).standard_normal(d.shape), 4.0) * 25.0
    r = d / WHAKAARI_RADIUS
    cone = WHAKAARI_PEAK * np.clip(1.0 - r, 0, 1) ** 0.8 + noise * np.clip(1.0 - r, 0, 1)
    crater = np.clip(1.0 - d / 95.0, 0, 1)
    cone = cone - crater ** 0.6 * (WHAKAARI_PEAK - 8.0)
    # The shelf drops away under the sea instead of ending at a wall.
    shelf = -12.0 + 14.0 * np.clip(1.4 - r, 0, 1)
    island = np.where(r < 1.0, np.maximum(cone, 0.8 + 6.0 * (1.0 - r)), shelf)
    h = h.copy()
    land = land.copy()
    h[win] = np.where(d < WHAKAARI_RADIUS * 1.4, np.maximum(h[win], island), h[win])
    land[win] |= (d < WHAKAARI_RADIUS) & (h[win] > 0.3)
    site = Site("whakaari", cls, label, x, y, WHAKAARI_RADIUS, 0.0, "Local")
    site.extra["zone"] = {"radius": WHAKAARI_RADIUS + 60.0, "crater_radius": 95.0}
    print(f"  Whakaari islet at {x:.0f}, {y:.0f}")
    return h, land, site


def whakaari_mask(sites: list[Site], grid) -> np.ndarray:
    m = np.zeros((grid.n, grid.n), dtype=bool)
    for s in sites:
        if s.kind == "whakaari":
            win, wx, wy = grid.window(s.x, s.y, s.radius)
            m[win] |= np.hypot(wx - s.x, wy - s.y) <= s.radius
    return m


def write_pois(sites: list[Site], path: Path, easting: float, northing: float) -> None:
    data = [{
        "kind": s.kind, "class": s.class_name, "label": s.label,
        "x": round(s.x, 1), "y": round(s.y, 1), "tb": [round(s.x + easting, 1), round(s.y + northing, 1)],
        "heading": s.heading, "radius": round(s.radius, 1),
        "surfaces": [{"kind": f["kind"], "points": [[round(a, 1), round(b, 1)] for a, b in f["points"]]}
                     for f in s.surfaces],
        **s.extra,
    } for s in sites]
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def draw_preview(relief, sites: list[Site], size_m: float):
    from PIL import ImageDraw

    colours = {"airfield": (40, 40, 40), "port": (30, 90, 200), "ski": (255, 255, 255), "hobbiton": (250, 200, 0),
               "farm": (150, 90, 40), "whakaari": (220, 30, 30),
               "industrial": (160, 60, 200), "naval": (20, 40, 120), "landmark": (255, 255, 255),
               "ferry": (0, 160, 220), "ramp": (0, 200, 200), "surfclub": (255, 220, 0), "campground": (60, 160, 60),
               "bach": (230, 140, 90), "hut": (200, 60, 60), "station": (40, 40, 40)}
    img = relief.convert("RGB").copy()
    d = ImageDraw.Draw(img)
    font = towns_mod._font(15)
    k = img.width / size_m
    for s in sites:
        px, py = s.x * k, (size_m - s.y) * k
        for surf in s.surfaces:
            d.polygon([(a * k, (size_m - b) * k) for a, b in surf["points"]], fill=(70, 70, 70))
        r = 3 if s.kind in ("farm", "bach", "hut", "ramp", "station") else 6
        d.ellipse([px - r, py - r, px + r, py + r], fill=colours[s.kind], outline=(0, 0, 0))
        if s.label:
            d.text((px + 8, py - 8), s.label, fill=(255, 255, 255), font=font, stroke_width=2, stroke_fill=(0, 0, 0))
    return img
