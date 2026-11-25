"""Natural feature and station labels for the 2D map, added to config/names.hpp.

    python labels.py

Adds named rivers (snapped onto the traced river channels), peaks (snapped to the local high point),
lakes, bays and straits (kept only where there is open water), railway stations and the set pieces
from source/setpieces.json (build_mission.py runs it again after placing them). It also sets
every label to the location types the DayZ map styles (Capital, City, Village, Local, ...), not the
older Arma ones. generate_terrain.py runs it after writing names.hpp; running it again replaces the
block it added. Writes source/labels.json for the player map.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

MAP_DIR = Path(__file__).resolve().parents[1]
SOURCE = MAP_DIR / "source"
NAMES = MAP_DIR / "config" / "names.hpp"
MARK = "\t// Rivers, peaks, water and stations: tools/labels.py"
TYPES = {"NameCityCapital": "Capital", "NameCity": "City", "NameVillage": "Village", "NameLocal": "Local"}
RIVER_SNAP_M = 300.0
PEAK_SNAP_M = 250.0
SEA_SNAP_M = 1200.0

# (label, lat, lon) of a point on the lower or middle course.
RIVERS = [
    ("Waikato River", -37.62, 175.15), ("Whanganui River", -39.55, 175.08), ("Rangitīkei River", -40.05, 175.48),
    ("Manawatū River", -40.33, 175.55), ("Ruamāhanga River", -41.15, 175.42), ("Mōkau River", -38.68, 174.75),
    ("Rangitaiki River", -38.25, 176.75), ("Mohaka River", -39.05, 176.85), ("Tukituki River", -39.75, 176.75),
    ("Waihou River", -37.4, 175.6), ("Wairau River", -41.55, 173.65), ("Motueka River", -41.25, 172.9),
    ("Buller River / Kawatiri", -41.8, 172.0), ("Grey River / Māwheranui", -42.4, 171.4),
    ("Waiau Uwha River", -42.7, 173.15), ("Waimakariri River", -43.4, 172.4), ("Rakaia River", -43.6, 171.95),
    ("Rangitata River", -43.9, 171.3), ("Waitaki River", -44.75, 170.75), ("Taieri River", -45.85, 170.05),
    ("Clutha River / Mata-Au", -46.1, 169.6), ("Mataura River", -46.2, 168.85), ("Ōreti River", -46.2, 168.3),
    ("Waiau River", -46.0, 167.75),
]
PEAKS = [
    ("Aoraki / Mount Cook", -43.595, 170.142), ("Tititea / Mount Aspiring", -44.384, 168.728),
    ("Ruapehu", -39.281, 175.564), ("Tongariro", -39.13, 175.642), ("Ngāuruhoe", -39.157, 175.632),
    ("Taranaki Maunga", -39.296, 174.064), ("Tapuae-o-Uenuku", -41.995, 173.67), ("Hikurangi", -37.92, 178.06),
    ("Mount Owen", -41.548, 172.538), ("Pikirakatahi / Mount Earnslaw", -44.62, 168.4),
    ("Mount Tutoko", -44.597, 168.009), ("Rangitoto", -36.786, 174.86), ("Mauao / Mount Maunganui", -37.632, 176.172),
    ("Kaimanawa Range", -39.2, 176.0), ("Tararua Range", -40.8, 175.4), ("Ruahine Range", -39.85, 176.1),
    ("Kaikōura Ranges", -42.1, 173.6), ("Southern Alps / Kā Tiritiri o te Moana", -43.25, 170.85),
]
SEAS = [
    ("Tasman Sea", -40.0, 171.5), ("Pacific Ocean", -42.0, 177.0), ("Hauraki Gulf / Tīkapa Moana", -36.6, 175.05),
    ("Bay of Plenty / Te Moana-a-Toi", -37.65, 176.9), ("Hawke Bay", -39.35, 177.2), ("Cook Strait / Te Moana-o-Raukawa", -41.2, 174.45),
    ("Golden Bay / Mohua", -40.7, 172.85), ("Tasman Bay / Te Tai-o-Aorere", -41.0, 173.1),
    ("Pegasus Bay", -43.3, 172.95), ("Canterbury Bight", -44.4, 171.85), ("Foveaux Strait / Te Ara a Kiwa", -46.7, 168.2),
    ("Kaipara Harbour", -36.45, 174.2), ("Manukau Harbour", -37.03, 174.7),
]


def _grid():
    meta = json.loads((SOURCE / "heightmap.json").read_text())
    raw = np.asarray(Image.open(SOURCE / "heightmap_4096.png")).astype(np.float32)
    h = meta["png_black_m"] + raw / 65535.0 * (meta["png_white_m"] - meta["png_black_m"])
    rivers = np.asarray(Image.open(SOURCE / "water_4096.png"))[..., 1] > 127
    return meta, h, rivers


def _cell(x, y, size, cell):
    n = int(size / cell)
    return min(n - 1, max(0, int((size - y) / cell))), min(n - 1, max(0, int(x / cell)))


def _xy(r, c, size, cell):
    return (c + 0.5) * cell, size - (r + 0.5) * cell


def _window(r, c, radius_cells, n):
    return slice(max(0, r - radius_cells), min(n, r + radius_cells + 1)), slice(max(0, c - radius_cells), min(n, c + radius_cells + 1))


def _class(label: str) -> str:
    ascii_ = label.translate(str.maketrans("āēīōūĀĒĪŌŪ", "aeiouAEIOU"))
    return "Label" + re.sub(r"[^A-Za-z0-9]", "", ascii_.split(" / ")[0])


def build() -> list[dict]:
    import generate_terrain as g

    proj = g.projection()
    meta, h, rivers = _grid()
    size, cell = meta["terrain_size_m"], meta["cell_size_m"]
    n = h.shape[0]

    def project(lat, lon):
        x, y = g.lonlat_to_world(np.array([lon]), np.array([lat]), proj)
        return float(x[0]), float(y[0])

    labels = []
    for name, lat, lon in RIVERS:
        x, y = project(lat, lon)
        if not (0 <= x < size and 0 <= y < size):
            continue
        r, c = _cell(x, y, size, cell)
        rad = int(RIVER_SNAP_M / cell)
        win = _window(r, c, rad, n)
        rr, cc = np.nonzero(rivers[win])
        if not len(rr):
            continue
        rr, cc = rr + win[0].start, cc + win[1].start
        i = int(np.argmin((rr - r) ** 2 + (cc - c) ** 2))
        labels.append({"name": name, "kind": "river", "type": "Marine", "xy": _xy(rr[i], cc[i], size, cell)})
    for name, lat, lon in PEAKS:
        x, y = project(lat, lon)
        if not (0 <= x < size and 0 <= y < size):
            continue
        r, c = _cell(x, y, size, cell)
        win = _window(r, c, int(PEAK_SNAP_M / cell), n)
        sub = h[win]
        if sub.max() <= 20.0:
            continue
        pr, pc = np.unravel_index(int(np.argmax(sub)), sub.shape)
        labels.append({"name": name, "kind": "peak", "type": "Hill",
                       "xy": _xy(pr + win[0].start, pc + win[1].start, size, cell), "z": float(sub.max())})
    for lake in json.loads((SOURCE / "lakes.json").read_text(encoding="utf-8")):
        if lake["name"] != "unnamed" and lake["area_m2"] >= 1500:
            labels.append({"name": f"Lake {lake['name']}", "kind": "lake", "type": "Marine",
                           "xy": tuple(lake["centre"])})
    for name, lat, lon in SEAS:
        x, y = project(lat, lon)
        x, y = min(max(x, 600.0), size - 600.0), min(max(y, 600.0), size - 600.0)
        r, c = _cell(x, y, size, cell)
        # Nearest point within SEA_SNAP_M with 100 m of open water all round.
        win = _window(r, c, int(SEA_SNAP_M / cell), n)
        open_water = ndimage.minimum_filter(h[win] < 0.0, size=int(200 / cell))
        rr, cc = np.nonzero(open_water)
        if len(rr):
            rr, cc = rr + win[0].start, cc + win[1].start
            i = int(np.argmin((rr - r) ** 2 + (cc - c) ** 2))
            labels.append({"name": name, "kind": "sea", "type": "Marine", "xy": _xy(rr[i], cc[i], size, cell)})
    roads = json.loads((SOURCE / "roads.json").read_text(encoding="utf-8"))
    for st in roads.get("stations", []):
        labels.append({"name": f"{st['town']} Station", "kind": "station", "type": "RailroadStation",
                       "xy": (st["x"], st["y"])})

    extra = SOURCE / "setpieces.json"
    for p in json.loads(extra.read_text(encoding="utf-8")) if extra.exists() else []:
        if p["kind"] != "military":
            labels.append({"name": p["label"], "kind": "place", "type": "Local", "xy": (p["x"], p["y"])})

    seen = set()
    for lb in labels:
        base = cls = _class(lb["name"])
        k = 2
        while cls in seen:
            cls, k = f"{base}{k}", k + 1
        seen.add(cls)
        lb["class"] = cls
        lb["xy"] = [round(lb["xy"][0], 1), round(lb["xy"][1], 1)]
    return labels


def update(labels: list[dict], path: Path = NAMES) -> None:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if "\n" + MARK in text:
        text = text.split("\n" + MARK)[0].rstrip()
    else:
        text = text.rstrip()
        if not text.endswith("};"):
            raise SystemExit(f"{path} does not end with the Names class's closing brace")
        text = text[:-2].rstrip()
    for old, new in TYPES.items():
        text = text.replace(f'type = "{old}";', f'type = "{new}";')
    lines = [text, MARK]
    for lb in labels:
        x, y = lb["xy"]
        lines += [f"\tclass {lb['class']}", "\t{", f'\t\tname = "{lb["name"]}";',
                  f"\t\tposition[] = {{{x:.1f}, {y:.1f}}};", f'\t\ttype = "{lb["type"]}";',
                  "\t\tradiusA = 100;", "\t\tradiusB = 100;", "\t\tangle = 0;", "\t};"]
    lines += ["};", ""]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\r\n")


def main() -> None:
    labels = build()
    update(labels)
    (SOURCE / "labels.json").write_text(json.dumps(labels, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = {}
    for lb in labels:
        counts[lb["kind"]] = counts.get(lb["kind"], 0) + 1
    print("Map labels added: " + ", ".join(f"{v} {k}s" for k, v in counts.items()))
    wanted = {n for n, *_ in RIVERS + PEAKS}
    missing = sorted(wanted - {lb["name"] for lb in labels})
    if missing:
        print("  not on the map or not found: " + ", ".join(missing))


if __name__ == "__main__":
    main()
