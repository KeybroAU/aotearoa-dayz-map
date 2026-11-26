"""Kiwi food stashes: crashed Countdown supermarket trucks on the state highways, the stock out the
back of each dairy (the corner shops), and the pantries at the baches.

    python tools/food_stashes.py

Writes, in mission/dayzOffline.aotearoa/aotearoa/:

  foodstash_spawner.json   the truck crashes (a jack-knifed truck and trailer with spilled crates and
                           pallets), an object spawner that pack_mod.py adds to cfggameplay.json
  food_stashes.json        every stash: where it is, how big, and which New Zealand food it holds

init.c reads food_stashes.json when the server starts and keeps each stash stocked: every
RESTOCK_MINUTES it counts the stash's food lying within its radius and, if there are fewer than its
minimum, tops it up to a random amount between its minimum and maximum. So a looted stash refills
slowly and an untouched one never piles up. The food is extra to the central economy's nominal
counts. Called from build_mission.py; run it alone after changing the food items.
"""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

import generate_terrain as g
import nz_food

MAP_DIR = Path(__file__).resolve().parents[1]
MISSION = MAP_DIR / "mission" / "dayzOffline.aotearoa"
RESTOCK_MINUTES = 45
TRUCKS = 8
TRUCK_GAP_M = 4000.0
TRAFFIC_GAP_M = 500.0  # from the highway pile-up events
SAFE_ZONE_M = 400.0  # from the trader compounds, whose safe zones forbid looting

TRUCK = "Land_wreck_truck01_aban1_green_DE"
TRAILER = "Land_Wreck_Trailer_Closed_DE"
SPILL = ["StaticObj_Misc_WoodenCrate", "StaticObj_Crates_Small", "StaticObj_Misc_Pallets1", "StaticObj_Misc_Pallet",
         "StaticObj_Crates_Small_Stack", "StaticObj_Misc_BoxWooden"]
DECAL = "StaticObj_Wreck_Decal_Small1_DE"
STORE = "Land_City_Store"
STORE_BACK_M = 13.0  # from the store's centre to the yard behind it

GROUPS = {
    "snacks": ["bluebird_salted", "bluebird_vinegar", "bluebird_chicken", "munchos", "toffeepops", "shrewsburys",
               "chocthins", "pineapplelumps", "whittakers_milk", "whittakers_dark", "whittakers_peanut"],
    "fizzy": ["lp", "freshup", "foxton_cream", "foxton_rasp", "liftplus", "v_energy", "pump_water"],
    "dairy": ["anchor_milk", "airborne_honey"],
    "fish": ["sealord_tuna", "pams_sardines"],
    "pantry": ["risotto", "weetbix", "marmite", "watties_beans", "watties_spaghetti", "watties_peaches",
               "palm_cornedbeef", "hellers_bacon"],
    "pets": ["tux_dogfood", "jellimeat"],
}
# Each kind of stash: label, the food groups it holds, radius (m), and min/max items.
KINDS = {
    "countdown": ("Countdown truck crash", ["snacks", "fizzy", "dairy", "fish", "pantry", "pets"], 14.0, 6, 10),
    "dairy": ("Dairy stock room", ["snacks", "fizzy", "dairy"], 4.0, 2, 4),
    "bach": ("Bach pantry", ["pantry", "fish", "dairy", "fizzy"], 4.0, 2, 4),
}


def classes(groups: list[str]) -> list[str]:
    by_key = {i.key: i.cls for i in nz_food.ITEMS}
    return [by_key[k] for grp in groups for k in GROUPS[grp]]


def load_height() -> np.ndarray:
    meta = json.loads((g.SOURCE_DIR / "heightmap.json").read_text())
    raw = np.asarray(Image.open(g.SOURCE_DIR / "heightmap_4096.png")).astype(np.float32)
    return meta["png_black_m"] + raw / 65535.0 * (meta["png_white_m"] - meta["png_black_m"])


class Ground:
    def __init__(self, h):
        self.h = h

    def z(self, x, y) -> float:
        return float(ndimage.map_coordinates(self.h, [[(g.SIZE_M - y) / g.CELL - 0.5], [x / g.CELL - 0.5]],
                                             order=1, mode="nearest")[0])

    def flat(self, x, y, r, relief=1.5) -> bool:
        zs = [self.z(x + dx, y + dy) for dx in (-r, 0, r) for dy in (-r, 0, r)]
        return min(zs) > 0.8 and max(zs) - min(zs) < relief


def _local(hd, along, across):
    s, c = math.sin(math.radians(hd)), math.cos(math.radians(hd))
    return along * s + across * c, along * c - across * s


def highway_samples(roads, step=150.0):
    out = []
    for r in roads["roads"]:
        if r["kind"] != "highway":
            continue
        pts = np.array(r["points"])
        seg = np.hypot(*np.diff(pts, axis=0).T)
        dist = np.concatenate([[0.0], np.cumsum(seg)])
        for s in np.arange(step / 2, dist[-1], step):
            i = max(0, min(int(np.searchsorted(dist, s) - 1), len(pts) - 2))
            k = (s - dist[i]) / max(seg[i], 1e-6)
            x, y = pts[i] + k * (pts[i + 1] - pts[i])
            dx, dy = pts[i + 1] - pts[i]
            out.append((float(x), float(y), math.degrees(math.atan2(dx, dy)) % 360))
    return out


def traffic_events() -> list[tuple[float, float]]:
    path = MISSION / "cfgeventspawns.xml"
    if not path.exists():
        return []
    out = []
    for ev in ET.parse(path).getroot():
        if ev.get("name") in ("StaticPoliceSituation", "StaticMilitaryConvoy", "StaticTrain"):
            out += [(float(p.get("x")), float(p.get("z"))) for p in ev.iter("pos")]
    return out


def spread(points, k, min_gap, rng):
    if not points:
        return []
    arr = np.array([p[:2] for p in points])
    chosen = [int(rng.integers(len(arr)))]
    d = np.hypot(*(arr - arr[chosen[0]]).T)
    while len(chosen) < min(k, len(arr)):
        i = int(np.argmax(d))
        if d[i] < min_gap:
            break
        chosen.append(i)
        d = np.minimum(d, np.hypot(*(arr - arr[i]).T))
    return [points[i] for i in chosen]


def truck_crash(x, y, hd, ground, rng) -> list[dict]:
    """The cab slewed into the ditch, the trailer jack-knifed across the lane, crates spilled behind."""
    objs = []

    def put(cls, along, across, yaw):
        dx, dy = _local(hd, along, across)
        px, py = x + dx, y + dy
        objs.append({"name": cls, "pos": [round(px, 3), round(ground.z(px, py), 3), round(py, 3)],
                     "ypr": [round(yaw % 360, 3), 0.0, 0.0], "scale": 1.0, "enableCEPersistency": 0})

    put(TRUCK, 9.0, 5.5, hd + 35.0)
    put(TRAILER, -3.0, 0.5, hd + 70.0 + float(rng.uniform(-10, 10)))
    put(DECAL, 2.0, 2.0, float(rng.uniform(0, 360)))
    for k in range(7):
        put(SPILL[k % len(SPILL)], -12.0 - 2.5 * k + float(rng.uniform(-1, 1)), float(rng.uniform(-5, 6)),
            float(rng.uniform(0, 360)))
    return objs


def build(rng=None) -> dict:
    rng = rng or np.random.default_rng(g.SEED + 41)
    ground = Ground(load_height())
    import csv
    with (g.SOURCE_DIR / "towns.csv").open(encoding="utf-8") as f:
        towns = list(csv.DictReader(f))
    roads = json.loads((g.SOURCE_DIR / "roads.json").read_text(encoding="utf-8"))
    pois = json.loads((g.SOURCE_DIR / "pois.json").read_text(encoding="utf-8"))
    buildings = []
    for name in ("towns_spawner.json", "pois_spawner.json", "setpieces_spawner.json"):
        path = g.SOURCE_DIR / "objects" / name
        if path.exists():
            buildings += json.loads(path.read_text())["Objects"]
    tree = None
    if buildings:
        from scipy.spatial import cKDTree
        tree = cKDTree([(o["pos"][0], o["pos"][2]) for o in buildings])

    def clear(x, y, r):
        return tree is None or not tree.query_ball_point((x, y), r)

    stashes, spawner = [], []

    def stash(kind, x, y, label):
        what, groups, r, lo, hi = KINDS[kind]
        stashes.append({"kind": kind, "label": label, "x": round(x, 2), "z": round(y, 2), "r": r,
                        "minItems": lo, "maxItems": hi, "items": classes(groups)})

    # Countdown trucks on the open highway, away from towns, sites and the other road events.
    zones = [(float(t["x"]), float(t["y"]), float(t["radius"]) + 150.0) for t in towns]
    zones += [(p["x"], p["y"], p["radius"] + 60.0) for p in pois if p["kind"] != "farm"]
    traders = MISSION / "aotearoa" / "traders_spawner.json"
    if traders.exists():
        zones += [(o["pos"][0], o["pos"][2], SAFE_ZONE_M) for o in json.loads(traders.read_text())["Objects"]]
    events = traffic_events()
    cand = [(x, y, hd) for x, y, hd in highway_samples(roads)
            if all(math.hypot(x - zx, y - zy) > zr for zx, zy, zr in zones)
            and all(math.hypot(x - ex, y - ey) > TRAFFIC_GAP_M for ex, ey in events)
            and ground.flat(x, y, 15.0, relief=2.5) and clear(x, y, 30.0)]
    for k, (x, y, hd) in enumerate(spread(cand, TRUCKS, TRUCK_GAP_M, rng)):
        spawner += truck_crash(x, y, hd, ground, rng)
        bx, by = _local(hd, -14.0, 0.5)
        stash("countdown", x + bx, y + by, f"Countdown truck crash {k + 1}")

    # The yard behind every dairy.
    for o in buildings:
        if o["name"] != STORE:
            continue
        sx, sy, yaw = o["pos"][0], o["pos"][2], o["ypr"][0]
        for side in (180.0, 0.0, 90.0, 270.0):
            dx, dy = _local(yaw + side, STORE_BACK_M, 0.0)
            if ground.z(sx + dx, sy + dy) > 0.8:
                stash("dairy", sx + dx, sy + dy, "Dairy stock room")
                break

    # A pantry beside each bach, clear of the buildings.
    for p in pois:
        if p["kind"] != "bach":
            continue
        for r in (10.0, 14.0, 18.0, 24.0):
            spot = next(((p["x"] + r * math.sin(math.radians(a)), p["y"] + r * math.cos(math.radians(a)))
                         for a in range(0, 360, 30)
                         if ground.flat(p["x"] + r * math.sin(math.radians(a)), p["y"] + r * math.cos(math.radians(a)),
                                        3.0) and clear(p["x"] + r * math.sin(math.radians(a)),
                                                       p["y"] + r * math.cos(math.radians(a)), 7.0)), None)
            if spot:
                stash("bach", spot[0], spot[1], f"Bach pantry, {p['label']}" if p["label"] else "Bach pantry")
                break
    return {"stashes": stashes, "spawner": spawner}


def write(result: dict) -> None:
    out = MISSION / "aotearoa"
    out.mkdir(parents=True, exist_ok=True)
    (out / "foodstash_spawner.json").write_text(json.dumps({"Objects": result["spawner"]}, indent=1) + "\n")
    data = {"restockMinutes": RESTOCK_MINUTES, "stashes": result["stashes"]}
    (out / "food_stashes.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def summary(result: dict) -> str:
    counts = {}
    for s in result["stashes"]:
        counts[s["kind"]] = counts.get(s["kind"], 0) + 1
    return "Food stashes: " + ", ".join(f"{KINDS[k][0]} {n}" for k, n in counts.items())


def main() -> None:
    result = build()
    write(result)
    print(summary(result) + f"; {len(result['spawner'])} truck crash objects")


if __name__ == "__main__":
    main()
