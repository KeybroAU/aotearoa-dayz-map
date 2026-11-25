"""Town name signs on every road into a town.

Each sign is one shared model (structures/sign_town/sign_town.p3d, made from
docs/models/sign_town.obj) with a texture per town, set through a config class. They are placed
with an object spawner, because only spawned objects can swap textures.

Writes:
  data/signs/sign_<Town>.png              one 1024 x 1024 texture per town (sign face in the top half)
  config/signs.hpp                        CfgVehicles classes Land_Aotearoa_Sign_<Town>
  mission/.../aotearoa/signs_spawner.json the sign positions, for cfggameplay objectSpawnersArr
  preview/signs_sheet.png                 every sign face on one sheet

    python signs.py        (build_mission.py also runs it)
"""

from __future__ import annotations

import csv
import json
import math
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.spatial import cKDTree

MAP_DIR = Path(__file__).resolve().parents[1]
SOURCE = MAP_DIR / "source"
SIGN_DIR = MAP_DIR / "data" / "signs"
SPAWNER = MAP_DIR / "mission" / "dayzOffline.aotearoa" / "aotearoa" / "signs_spawner.json"
MODEL = "\\maps\\aotearoa\\structures\\sign_town\\sign_town.p3d"
TEXTURE = "maps\\aotearoa\\data\\signs\\sign_{cls}_co.paa"

SIGN_ROADS = ("highway", "gravel", "track")
EDGE_PAD_M = 25.0  # highways stop just short of a small town's radius, so its edge counts as a little wider
OUTSIDE_M = 20.0  # how far outside that edge the sign stands
VERGE_M = {"highway": 5.5, "gravel": 4.0, "track": 3.5}  # from the centreline to the sign, on the left
SAME_TOWN_GAP_M = 60.0
ROAD_WIDTH_M = {"highway": 8.0, "street": 6.0, "gravel": 5.0, "track": 4.0}
CLEAR_M = 1.5  # sign edge to road edge
BUILDING_CLEAR_M = 10.0  # sign to building centre
BUILDINGS = [SOURCE / "objects" / "towns_spawner.json", SOURCE / "objects" / "pois_spawner.json"]
GREEN = (0, 104, 71)
WHITE = (255, 255, 255)
BACK_GREY = (128, 130, 132)
FONTS_BOLD = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"]


def class_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return "".join(ch for ch in ascii_name.title() if ch.isalnum())


def _font(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit(d, text, paths, start, max_w):
    size = start
    while size > 20:
        f = _font(paths, size)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return _font(paths, size)


def _two_lines(text: str) -> tuple[str, str]:
    words = text.split()
    best = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
    return " ".join(words[:best]), " ".join(words[best:])


def draw_sign(name: str, maori: str) -> Image.Image:
    """1024 x 1024: the green sign face fills the top half, plain grey (back and posts) the bottom."""
    img = Image.new("RGB", (1024, 1024), BACK_GREY)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1023, 511], fill=GREEN)
    d.rounded_rectangle([18, 18, 1005, 493], radius=28, outline=WHITE, width=12)
    if not maori and " " in name and d.textlength(name, font=_font(FONTS_BOLD, 120)) > 900:
        a, b = _two_lines(name)
        f = _fit(d, max(a, b, key=len), FONTS_BOLD, 140, 900)
        d.text((512, 180), a, font=f, fill=WHITE, anchor="mm")
        d.text((512, 335), b, font=f, fill=WHITE, anchor="mm")
    elif maori:
        f1 = _fit(d, name, FONTS_BOLD, 150, 900)
        f2 = _fit(d, maori, FONTS, 92, 900)
        d.text((512, 205), name, font=f1, fill=WHITE, anchor="mm")
        d.text((512, 365), maori, font=f2, fill=WHITE, anchor="mm")
    else:
        f1 = _fit(d, name, FONTS_BOLD, 170, 900)
        d.text((512, 256), name, font=f1, fill=WHITE, anchor="mm")
    return img


def entry_points(roads: list[dict], towns: list[dict]) -> list[dict]:
    """Where each road crosses into a town: a point OUTSIDE_M out, on the left verge for traffic coming in."""
    out = []
    for road in roads:
        if road["kind"] not in SIGN_ROADS:
            continue
        pts = np.array(road["points"], dtype=float)
        if len(pts) < 2:
            continue
        seg = np.hypot(*np.diff(pts, axis=0).T)
        n = np.maximum(1, np.ceil(seg / 2.0)).astype(int)
        dense = np.concatenate([np.linspace(pts[i], pts[i + 1], n[i], endpoint=False) for i in range(len(seg))]
                               + [pts[-1:]])
        for t in towns:
            tx, ty, r = float(t["x"]), float(t["y"]), float(t["radius"]) + EDGE_PAD_M
            d = np.hypot(dense[:, 0] - tx, dense[:, 1] - ty)
            inside = d <= r
            for step in (1, -1):  # walk the line both ways: either end may be the one coming in
                order = range(len(dense) - 1) if step == 1 else range(len(dense) - 1, 0, -1)
                for i in order:
                    j = i + step
                    if inside[i] or not inside[j]:
                        continue
                    # Back away from the edge until OUTSIDE_M out, against the direction of travel.
                    k = i
                    while 0 <= k - step < len(dense) and d[k] < r + OUTSIDE_M:
                        k -= step
                    if d[k] < r + OUTSIDE_M * 0.5:
                        continue
                    ax, ay = dense[k]
                    bx, by = dense[min(max(k + step, 0), len(dense) - 1)]
                    dx, dy = bx - ax, by - ay
                    norm = math.hypot(dx, dy) or 1.0
                    dx, dy = dx / norm, dy / norm
                    off = VERGE_M[road["kind"]]
                    out.append({"town": t["name"], "maori": t.get("maori", ""), "x": ax - dy * off, "y": ay + dx * off,
                                # The face looks back at the drivers coming in.
                                "yaw": math.degrees(math.atan2(-dx, -dy)) % 360, "road": road["kind"]})
    return out


class RoadIndex:
    """Road segments bucketed on a 100 m grid, for distance-to-road-edge checks."""

    def __init__(self, roads: list[dict], bucket: float = 100.0):
        self.bucket = bucket
        self.cells: dict[tuple[int, int], list[tuple]] = {}
        for road in roads:
            half = ROAD_WIDTH_M.get(road["kind"], 6.0) / 2
            pts = road["points"]
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                for cx in range(int(min(ax, bx) // bucket), int(max(ax, bx) // bucket) + 1):
                    for cy in range(int(min(ay, by) // bucket), int(max(ay, by) // bucket) + 1):
                        self.cells.setdefault((cx, cy), []).append((ax, ay, bx, by, half))

    def clearance(self, x: float, y: float) -> float:
        """Distance from (x, y) to the nearest road edge (negative when on the road)."""
        best = math.inf
        cx, cy = int(x // self.bucket), int(y // self.bucket)
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for ax, ay, bx, by, half in self.cells.get((cx + i, cy + j), ()):
                    dx, dy = bx - ax, by - ay
                    t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy or 1.0)))
                    best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy) - half)
        return best


def building_tree() -> cKDTree | None:
    pts = [(o["pos"][0], o["pos"][2]) for f in BUILDINGS if f.exists()
           for o in json.loads(f.read_text(encoding="utf-8"))["Objects"]]
    return cKDTree(pts) if pts else None


def place_clear(s: dict, index: RoadIndex, buildings: cKDTree | None) -> bool:
    """Push the sign further onto the verge until it is clear of every road and building."""
    yaw = math.radians(s["yaw"])
    # The left of travel is the sign's right-hand side as it faces the oncoming drivers.
    lx, ly = math.cos(yaw), -math.sin(yaw)
    for extra in (0.0, 1.0, 2.0, 3.5, 5.0, 7.0):
        x, y = s["x"] + lx * extra, s["y"] + ly * extra
        if index.clearance(x, y) >= CLEAR_M + 1.2 and (  # 1.2 m: half the board width
                buildings is None or buildings.query((x, y))[0] >= BUILDING_CLEAR_M):
            s["x"], s["y"] = x, y
            return True
    return False


def ground(h: np.ndarray, x: float, y: float, cell: float, size_m: float) -> float:
    """Bilinear height: the spawner places objects at the given height, it does not drop them to the ground."""
    fc, fr = x / cell, (size_m - y) / cell
    c0, r0 = int(np.clip(fc, 0, h.shape[1] - 2)), int(np.clip(fr, 0, h.shape[0] - 2))
    tc, tr = fc - c0, fr - r0
    top = h[r0, c0] * (1 - tc) + h[r0, c0 + 1] * tc
    bot = h[r0 + 1, c0] * (1 - tc) + h[r0 + 1, c0 + 1] * tc
    return float(top * (1 - tr) + bot * tr)


def dedupe(signs: list[dict], towns: list[dict], h, cell, size_m, index: RoadIndex) -> list[dict]:
    kept: list[dict] = []
    buildings = building_tree()
    for s in sorted(signs, key=lambda s: {"highway": 0, "gravel": 1, "track": 2}[s["road"]]):
        if any(k["town"] == s["town"] and math.hypot(k["x"] - s["x"], k["y"] - s["y"]) < SAME_TOWN_GAP_M for k in kept):
            continue
        if any(math.hypot(s["x"] - float(t["x"]), s["y"] - float(t["y"])) < float(t["radius"]) for t in towns):
            continue
        r = int(np.clip((size_m - s["y"]) / cell, 0, h.shape[0] - 1))
        c = int(np.clip(s["x"] / cell, 0, h.shape[1] - 1))
        if h[r, c] < 0.5 or not place_clear(s, index, buildings):
            continue
        s["z"] = ground(h, s["x"], s["y"], cell, size_m)
        kept.append(s)
    return kept


def write_hpp(names: dict[str, str], path: Path) -> None:
    lines = ["// Town name sign classes, generated by tools/signs.py. Included inside CfgVehicles in config.cpp.",
             "class Land_Aotearoa_Sign_Base: HouseNoDestruct", "{", "\tscope = 1;", f'\tmodel = "{MODEL}";',
             '\thiddenSelections[] = {"camo"};', "};"]
    for cls in sorted(names):
        lines += [f"class Land_Aotearoa_Sign_{cls}: Land_Aotearoa_Sign_Base", "{",
                  f'\thiddenSelectionsTextures[] = {{"{TEXTURE.format(cls=cls)}"}};', "};"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\r\n")


def build(h: np.ndarray, towns: list[dict], roads: dict, cell: float, size_m: float) -> list[dict]:
    named = [t for t in towns if t["tier"] != "hamlet"]
    signs = dedupe(entry_points(roads["roads"], named), named, h, cell, size_m, RoadIndex(roads["roads"]))

    SIGN_DIR.mkdir(parents=True, exist_ok=True)
    for old in SIGN_DIR.glob("sign_*.png"):
        old.unlink()
    names = {class_name(t["name"]): t for t in named}
    thumbs = []
    for cls, t in sorted(names.items()):
        img = draw_sign(t["name"], t["maori"])
        img.save(SIGN_DIR / f"sign_{cls}.png", optimize=True)
        thumbs.append(img.crop((0, 0, 1024, 512)).resize((256, 128), Image.LANCZOS))
    write_hpp(names, MAP_DIR / "config" / "signs.hpp")

    SPAWNER.parent.mkdir(parents=True, exist_ok=True)
    SPAWNER.write_text(json.dumps({"Objects": [{
        "name": f"Land_Aotearoa_Sign_{class_name(s['town'])}",
        "pos": [round(s["x"], 2), round(s["z"], 3), round(s["y"], 2)],
        "ypr": [round(s["yaw"], 1), 0.0, 0.0],
        "scale": 1.0,
        "enableCEPersistency": 0,
    } for s in signs]}, indent=1) + "\n", encoding="utf-8")

    cols = 6
    sheet = Image.new("RGB", (cols * 264 + 8, math.ceil(len(thumbs) / cols) * 136 + 8), (30, 30, 30))
    for i, th in enumerate(thumbs):
        sheet.paste(th, (8 + (i % cols) * 264, 8 + (i // cols) * 136))
    sheet.save(MAP_DIR / "preview" / "signs_sheet.png", optimize=True)
    return signs


def main() -> None:
    meta = json.loads((SOURCE / "heightmap.json").read_text())
    raw = np.asarray(Image.open(SOURCE / "heightmap_4096.png")).astype(np.float32)
    h = meta["png_black_m"] + raw / 65535.0 * (meta["png_white_m"] - meta["png_black_m"])
    with (SOURCE / "towns.csv").open(encoding="utf-8") as f:
        towns = list(csv.DictReader(f))
    roads = json.loads((SOURCE / "roads.json").read_text(encoding="utf-8"))
    signs = build(h, towns, roads, meta["cell_size_m"], meta["terrain_size_m"])
    per_town = {}
    for s in signs:
        per_town[s["town"]] = per_town.get(s["town"], 0) + 1
    print(f"Town signs: {len(signs)} at {len(per_town)} towns")
    missing = sorted(t["name"] for t in towns if t["tier"] != "hamlet" and t["name"] not in per_town)
    if missing:
        print("  no road in: " + ", ".join(missing))


if __name__ == "__main__":
    main()
