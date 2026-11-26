"""Dynamic events: a different few each restart, picked by the server's init.c from a pool of sites.

    python tools/dynamic_events.py

  Air New Zealand cargo plane crash   open farmland or tussock, well away from towns; 2 live at a time
  Stranded Interislander ferry        aground in the shallows, with freight washed up on the beach; 1 live
  DOC hut stash                       beside a back-country hut, left by trampers; 4 live

Writes mission/dayzOffline.aotearoa/aotearoa/dynamic_events.json: every candidate site with its wreck
objects (absolute positions, heights from the heightmap) and its loot. When the server starts,
init.c shuffles each event's sites, spawns the wreck and the loot at the first few (ACTIVE) and writes
where they are to the server log ("[Aotearoa] event: ..."). Nothing is saved, so the next restart
picks new sites and the old wrecks are gone. Delete the file to turn the events off. Called from
build_mission.py.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

import food_stashes as fs
import generate_terrain as g
import nz_gear
import setpieces

MISSION = fs.MISSION
PLANE_SITES, FERRY_SITES = 24, 10
ACTIVE = {"planecrash": 2, "ferry": 1, "dochut": 4}

PLANE = "Land_Wreck_C130J_Cargo"
PLANE_DEBRIS = ["StaticObj_ShellCrater2_Debris", "StaticObj_Misc_TirePile", "StaticObj_Misc_Tire_Big",
                "StaticObj_Crates_Small", "StaticObj_Misc_WoodenCrate", "StaticObj_ShellCrater2_Debris",
                "StaticObj_Misc_Pallets1"]
HUT_BOX = "StaticObj_Misc_BoxWooden"

MEDICAL = ["BandageDressing", "FirstAidKit", "Morphine", "Epinephrine", "TetracyclineAntibiotics"]
TOOLS = ["Flashlight", "Battery9V", "Rope", "DuctTape", "CanOpener", "Hatchet", "Roadflare", "Binoculars",
         "PersonalRadio"]
TRAMPING = ["MountainBag_Green", "MountainBag_Orange", "Compass", "Canteen", "Matchbox", "HuntingKnife",
            "Heatpack", "Raincoat_Orange", "HikingBoots_Brown", "Pot", "FishingRod", "Rope"]
GEAR = [i.cls for i in nz_gear.ITEMS if i.key in ("swanndri_shirt", "swanndri_ranger", "stubbies", "jandals",
                                                  "allblacks_tee", "canterbury_jersey")]
FREIGHT = ["CarBattery", "SparkPlug", "TireRepairKit", "FieldShovel", "Raincoat_Orange", "Rope"]

# kind: (label, loot radius m, min, max, item list builder)
LOOT = {
    "planecrash": ("Air New Zealand cargo plane crash", 16.0, 8, 12,
                   lambda: fs.classes(["snacks", "fizzy", "dairy", "pantry"]) + MEDICAL + TOOLS + GEAR),
    "ferry": ("Stranded Interislander ferry", 10.0, 6, 9,
              lambda: fs.classes(["snacks", "fizzy", "fish", "pantry"]) + FREIGHT + MEDICAL[:2]),
    "dochut": ("DOC hut stash", 3.0, 3, 5,
               lambda: TRAMPING + fs.classes(["pantry", "snacks"]) + MEDICAL[:1] + GEAR[:3]),
}


def obj(cls, x, y, z, yaw) -> dict:
    return {"cls": cls, "x": round(x, 2), "y": round(z, 2), "z": round(y, 2), "yaw": round(yaw % 360, 1)}


def site(kind, label, x, y, objects) -> dict:
    _, r, lo, hi, items = LOOT[kind]
    return {"label": label, "x": round(x, 2), "z": round(y, 2), "objects": objects,
            "loot": {"r": r, "minItems": lo, "maxItems": hi, "items": items()}}


def plane_sites(ground, towns, roads, pois, rng) -> list[dict]:
    keep = [(float(t["x"]), float(t["y"]), float(t["radius"]) + 800.0) for t in towns]
    keep += [(p["x"], p["y"], p["radius"] + 300.0) for p in pois if p["kind"] != "farm"]
    road_pts = np.array([pt for r in roads["roads"] for pt in r["points"]])
    from scipy.spatial import cKDTree
    near_road = cKDTree(road_pts)
    cand = []
    step = 200.0
    for x in np.arange(step / 2, g.SIZE_M, step):
        for y in np.arange(step / 2, g.SIZE_M, step):
            z = ground.z(x, y)
            if not 2.0 < z < 400.0 or not ground.flat(x, y, 20.0, relief=8.0):
                continue
            if any(math.hypot(x - kx, y - ky) < kr for kx, ky, kr in keep):
                continue
            if near_road.query((x, y))[0] < 100.0:
                continue
            cand.append((float(x), float(y), float(rng.uniform(0, 360))))
    out = []
    for k, (x, y, hd) in enumerate(fs.spread(cand, PLANE_SITES, 1800.0, rng)):
        objects = [obj(PLANE, x, y, ground.z(x, y), hd)]
        for j, cls in enumerate(PLANE_DEBRIS):
            dx, dy = fs._local(hd, -30.0 - 14.0 * j, float(rng.uniform(-12, 12)))
            px, py = x + dx, y + dy
            objects.append(obj(cls, px, py, ground.z(px, py), float(rng.uniform(0, 360))))
        bx, by = fs._local(hd, -40.0, 14.0)
        out.append(site("planecrash", f"Air New Zealand cargo plane crash {k + 1}", x + bx, y + by, objects))
    return out


def ferry_sites(ground, pois, rng) -> list[dict]:
    h = ground.h
    static = json.loads((g.SOURCE_DIR / "setpieces.json").read_text(encoding="utf-8"))
    wreck = [(s["x"], s["y"]) for s in static if s["label"] == "Interislander wreck"]
    ports = [(p["x"], p["y"]) for p in pois if p["kind"] in ("port", "ferry", "ramp", "surfclub")]
    cand = []
    for px, py in ports:
        for d in (900.0, 1500.0, 2200.0):
            for k in range(0, 360, 20):
                x, y = px + d * math.sin(math.radians(k)), py + d * math.cos(math.radians(k))
                if not -8.0 <= ground.z(x, y) <= -2.0:
                    continue
                if any(math.hypot(x - wx, y - wy) < 5000.0 for wx, wy in wreck):
                    continue
                cand.append((x, y, float(k)))
    out = []
    for x, y, _ in fs.spread(cand, FERRY_SITES * 3, 3000.0, rng):
        for bearing in range(0, 180, 15):
            parts = setpieces.ship_layout(x, y, bearing)
            if all(setpieces.SHIP_DEPTH_M[0] <= ground.z(px, py) <= setpieces.SHIP_DEPTH_M[1] for _, px, py, _, _ in parts):
                break
        else:
            continue
        beach = None
        for d in np.arange(100.0, 2000.0, 25.0):
            for k in range(36):
                lx, ly = x + d * math.sin(math.radians(k * 10)), y + d * math.cos(math.radians(k * 10))
                if 0.4 < ground.z(lx, ly) < 2.5 and ground.flat(lx, ly, 6.0, relief=2.0):
                    beach = (lx, ly)
                    break
            if beach:
                break
        if not beach:
            continue
        objects = [obj(c, px, py, pz, yaw) for c, px, py, pz, yaw in parts]
        lx, ly = beach
        objects.append(obj("StaticObj_Wreck_Ship_Big_Lifeboat", lx, ly, ground.z(lx, ly), bearing + 40.0))
        for j, cls in enumerate(["StaticObj_Misc_WoodenCrate", "StaticObj_Crates_Small", "StaticObj_Misc_Pallet"]):
            cx, cy = lx + 6.0 * math.cos(j * 2.1), ly + 6.0 * math.sin(j * 2.1)
            objects.append(obj(cls, cx, cy, ground.z(cx, cy), float(rng.uniform(0, 360))))
        out.append(site("ferry", f"Stranded Interislander ferry {len(out) + 1}", lx, ly, objects))
        if len(out) >= FERRY_SITES:
            break
    return out


def hut_sites(ground, pois) -> list[dict]:
    out = []
    for p in pois:
        if p["kind"] != "hut":
            continue
        for r in (8.0, 11.0, 14.0):
            spot = next(((p["x"] + r * math.sin(math.radians(a)), p["y"] + r * math.cos(math.radians(a)))
                         for a in range(0, 360, 30)
                         if ground.flat(p["x"] + r * math.sin(math.radians(a)),
                                        p["y"] + r * math.cos(math.radians(a)), 2.0, relief=1.5)), None)
            if spot:
                x, y = spot
                label = f"DOC hut stash, {p['label']}" if p["label"] else "DOC hut stash"
                out.append(site("dochut", label, x, y, [obj(HUT_BOX, x, y, ground.z(x, y), 0.0)]))
                break
    return out


def build(rng=None) -> dict:
    import csv

    rng = rng or np.random.default_rng(g.SEED + 47)
    ground = fs.Ground(fs.load_height())
    with (g.SOURCE_DIR / "towns.csv").open(encoding="utf-8") as f:
        towns = list(csv.DictReader(f))
    roads = json.loads((g.SOURCE_DIR / "roads.json").read_text(encoding="utf-8"))
    pois = json.loads((g.SOURCE_DIR / "pois.json").read_text(encoding="utf-8"))
    events = [("planecrash", plane_sites(ground, towns, roads, pois, rng)), ("ferry", ferry_sites(ground, pois, rng)),
              ("dochut", hut_sites(ground, pois))]
    return {"events": [{"kind": k, "label": LOOT[k][0], "active": ACTIVE[k], "sites": s} for k, s in events]}


def write(data: dict) -> Path:
    out = MISSION / "aotearoa" / "dynamic_events.json"
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def summary(data: dict) -> str:
    return "Dynamic events: " + ", ".join(f"{e['label']} {e['active']} of {len(e['sites'])}" for e in data["events"])


def main() -> None:
    data = build()
    write(data)
    print(summary(data))


if __name__ == "__main__":
    main()
