"""Road signs: town names on every road into a town, plus State Highway shields, speed limits,
Give Way and One Lane Bridge signs.

There are two shared models, each with a texture per sign set through a config class:
  structures/sign_town/sign_town.p3d   the big green place-name board (docs/models/sign_town.obj)
  structures/sign_post/sign_post.p3d   a 1 m square cut-out sign on one post (docs/models/sign_post.obj)
They are placed with object spawners, because only spawned objects can swap textures.

Writes:
  data/signs/sign_<Town>.png                   town textures, 1024 x 1024 (face in the top half)
  data/signs/post_<Sign>.png                   post sign textures, 512 x 1024 with alpha (face top, back bottom)
  config/signs.hpp                             CfgVehicles classes Land_Aotearoa_Sign_* and Land_Aotearoa_SignPost_*
  mission/.../aotearoa/signs_spawner.json      town signs
  mission/.../aotearoa/roadsigns_spawner.json  post signs
  preview/signs_sheet.png                      every sign face on one sheet

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
POST_SPAWNER = SPAWNER.with_name("roadsigns_spawner.json")
MODEL = "\\maps\\aotearoa\\structures\\sign_town\\sign_town.p3d"
POST_MODEL = "\\maps\\aotearoa\\structures\\sign_post\\sign_post.p3d"
TEXTURE = "maps\\aotearoa\\data\\signs\\sign_{cls}_co.paa"
POST_TEXTURE = "maps\\aotearoa\\data\\signs\\post_{cls}_ca.paa"

SHIELD_EVERY_M = 2000.0  # along each highway, alternating direction, so each way sees one every 4 km
SHIELD_TOWN_GAP_M = 150.0
GIVE_WAY_BACK_M = 9.0  # from the end of the side road
GIVE_WAY_REACH_M = 6.0  # a side road ending this close to a highway's edge joins it
ONE_LANE_BACK_M = 30.0  # from the end of the bridge
# Rural South Island highways, where most real bridges are one lane; every non-highway bridge is too.
ONE_LANE_HIGHWAYS = {"SH6", "SH7", "SH8", "SH63", "SH65", "SH73", "SH83", "SH94"}
SIGN_GAP_M = 4.0  # between any two post signs
RED = (200, 16, 46)
YELLOW = (255, 200, 0)
BLACK = (20, 20, 20)
POST_GREY = (150, 152, 154)

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


def _dense(points, step: float = 2.0) -> np.ndarray:
    pts = np.array(points, dtype=float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    n = np.maximum(1, np.ceil(seg / step)).astype(int)
    return np.concatenate([np.linspace(pts[i], pts[i + 1], n[i], endpoint=False) for i in range(len(seg))]
                          + [pts[-1:]])


def _unit(dx: float, dy: float) -> tuple[float, float]:
    norm = math.hypot(dx, dy) or 1.0
    return dx / norm, dy / norm


def facing(cx: float, cy: float, tx: float, ty: float, off: float, **extra) -> dict:
    """A sign `off` metres to the left of a road at (cx, cy), facing the traffic travelling along (tx, ty)."""
    return {"x": cx - ty * off, "y": cy + tx * off, "yaw": math.degrees(math.atan2(-tx, -ty)) % 360, **extra}


def town_crossings(roads: list[dict], towns: list[dict], kinds):
    """Each place a road enters a town: (town, road, dense line, index just outside, step, distances, edge)."""
    for road in roads:
        if road["kind"] not in kinds or len(road["points"]) < 2:
            continue
        dense = _dense(road["points"])
        for t in towns:
            tx, ty, r = float(t["x"]), float(t["y"]), float(t["radius"]) + EDGE_PAD_M
            d = np.hypot(dense[:, 0] - tx, dense[:, 1] - ty)
            inside = d <= r
            for step in (1, -1):  # walk the line both ways: either end may be the one coming in
                order = range(len(dense) - 1) if step == 1 else range(len(dense) - 1, 0, -1)
                for i in order:
                    if not inside[i] and inside[i + step]:
                        yield t, road, dense, i, step, d, r


def _travel(dense, k, step) -> tuple[float, float]:
    a = dense[k]
    b = dense[min(max(k + step, 0), len(dense) - 1)]
    return _unit(b[0] - a[0], b[1] - a[1])


def entry_points(roads: list[dict], towns: list[dict]) -> list[dict]:
    """Where each road crosses into a town: a point OUTSIDE_M out, on the left verge for traffic coming in."""
    out = []
    for t, road, dense, i, step, d, r in town_crossings(roads, towns, SIGN_ROADS):
        # Back away from the edge until OUTSIDE_M out, against the direction of travel.
        k = i
        while 0 <= k - step < len(dense) and d[k] < r + OUTSIDE_M:
            k -= step
        if d[k] < r + OUTSIDE_M * 0.5:
            continue
        tx, ty = _travel(dense, k, step)
        out.append(facing(*dense[k], tx, ty, VERGE_M[road["kind"]], town=t["name"], maori=t.get("maori", ""),
                          road=road["kind"]))
    return out


def speed_signs(roads: list[dict], towns: list[dict]) -> list[dict]:
    """50 at the town edge for traffic coming in; 100 opposite it for traffic leaving."""
    out = []
    for t, road, dense, i, step, d, r in town_crossings(roads, towns, ("highway", "gravel")):
        tx, ty = _travel(dense, i, step)
        off = VERGE_M[road["kind"]]
        out.append(facing(*dense[i], tx, ty, off, cls="Speed50", prio=2))
        out.append(facing(*dense[i], -tx, -ty, off, cls="Speed100", prio=2))
    return out


def shields(roads: list[dict], towns: list[dict], bridges: list[dict]) -> list[dict]:
    """State Highway shields every SHIELD_EVERY_M along each highway, facing alternate ways."""
    out = []
    for road in roads:
        ref = road.get("ref", "")
        if road["kind"] != "highway" or not ref.startswith("SH") or len(road["points"]) < 2:
            continue
        dense = _dense(road["points"])
        dist = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(dense, axis=0).T))])
        for n, at in enumerate(np.arange(SHIELD_EVERY_M / 2, dist[-1] - 50.0, SHIELD_EVERY_M)):
            k = int(np.searchsorted(dist, at))
            x, y = dense[k]
            if any(math.hypot(x - float(t["x"]), y - float(t["y"])) < float(t["radius"]) + SHIELD_TOWN_GAP_M
                   for t in towns):
                continue
            if any(math.hypot(x - b["x"], y - b["y"]) < b["span"] / 2 + 40.0 for b in bridges):
                continue
            step = 1 if n % 2 == 0 else -1
            out.append(facing(x, y, *_travel(dense, k, step), VERGE_M["highway"], cls=ref, prio=3))
    # A shield for drivers leaving each town, as on real State Highways.
    for t, road, dense, i, step, d, r in town_crossings(roads, towns, ("highway",)):
        if not road.get("ref", "").startswith("SH"):
            continue
        k = i
        while 0 <= k - step < len(dense) and d[k] < r + SHIELD_TOWN_GAP_M:
            k -= step
        if d[k] < r + SHIELD_TOWN_GAP_M * 0.7:
            continue
        tx, ty = _travel(dense, k, step)
        out.append(facing(*dense[k], -tx, -ty, VERGE_M["highway"], cls=road["ref"], prio=3))
    return out


def give_ways(roads: list[dict]) -> list[dict]:
    """A Give Way sign on every side road where it meets a highway."""
    highways = RoadIndex([r for r in roads if r["kind"] == "highway"])
    out = []
    for road in roads:
        if road["kind"] == "highway" or len(road["points"]) < 2:
            continue
        dense = _dense(road["points"], 1.0)
        for end, step in ((0, -1), (len(dense) - 1, 1)):
            if highways.clearance(*dense[end]) > GIVE_WAY_REACH_M:
                continue
            # Walk back from the junction until clear of the highway, then GIVE_WAY_BACK_M more.
            k, walked = end, 0.0
            while 0 < k < len(dense) - 1 or k == end:
                k -= step
                if not 0 <= k < len(dense):
                    break
                if highways.clearance(*dense[k]) > 0:
                    walked += 1.0
                    if walked >= GIVE_WAY_BACK_M:
                        break
            if not 0 <= k < len(dense) or walked < GIVE_WAY_BACK_M:
                continue
            tx, ty = _travel(dense, k, step)
            out.append(facing(*dense[k], tx, ty, ROAD_WIDTH_M[road["kind"]] / 2 + 1.5, cls="GiveWay", prio=0))
    return out


def one_lane_bridges(bridges: list[dict]) -> list[dict]:
    out = []
    for b in bridges:
        ref = b.get("ref", "")
        if ref.startswith("SH") and ref not in ONE_LANE_HIGHWAYS:
            continue
        ux, uy = math.sin(math.radians(b["heading"])), math.cos(math.radians(b["heading"]))
        back = b["span"] / 2 + ONE_LANE_BACK_M
        off = VERGE_M["highway"] if ref.startswith("SH") else VERGE_M["gravel"]
        for tx, ty in ((ux, uy), (-ux, -uy)):
            out.append(facing(b["x"] - tx * back, b["y"] - ty * back, tx, ty, off, cls="OneLaneBridge", prio=1))
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
        if h[r, c] < 0.5 or not place_clear(s, index, buildings) or ground(h, s["x"], s["y"], cell, size_m) < 0.5:
            continue
        s["z"] = ground(h, s["x"], s["y"], cell, size_m)
        kept.append(s)
    return kept


def place_posts(signs: list[dict], town_signs: list[dict], towns, h, cell, size_m, index: RoadIndex) -> list[dict]:
    kept: list[dict] = []
    buildings = building_tree()
    taken = [(t["x"], t["y"]) for t in town_signs]
    for s in sorted(signs, key=lambda s: s["prio"]):
        r = int(np.clip((size_m - s["y"]) / cell, 0, h.shape[0] - 1))
        c = int(np.clip(s["x"] / cell, 0, h.shape[1] - 1))
        if h[r, c] < 0.5 or not place_clear(s, index, buildings) or ground(h, s["x"], s["y"], cell, size_m) < 0.5:
            continue
        if any(math.hypot(x - s["x"], y - s["y"]) < SIGN_GAP_M for x, y in taken):
            continue
        if any(k["cls"] == s["cls"] and math.hypot(k["x"] - s["x"], k["y"] - s["y"]) < 25.0 for k in kept):
            continue
        s["z"] = ground(h, s["x"], s["y"], cell, size_m)
        taken.append((s["x"], s["y"]))
        kept.append(s)
    return kept


def _face_shape(cls: str) -> Image.Image:
    """The 512 x 512 RGBA face of a post sign."""
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if cls.startswith("SH"):
        def shield(inset):
            top, side_end, bottom = 36 + inset, 300, 486 - inset * 1.4
            left, right = 50 + inset, 462 - inset
            pts = [(left, top), (256, top + 18), (right, top), (right, side_end)]
            for i in range(1, 21):  # curve in to the point at the bottom
                a = i / 20 * math.pi / 2
                pts.append((256 + (right - 256) * math.cos(a), side_end + (bottom - side_end) * math.sin(a)))
            for i in range(19, 0, -1):
                a = i / 20 * math.pi / 2
                pts.append((256 - (256 - left) * math.cos(a), side_end + (bottom - side_end) * math.sin(a)))
            pts.append((left, side_end))
            return pts
        d.polygon(shield(0), fill=WHITE)
        d.polygon(shield(18), fill=RED)
        num = cls[2:]
        d.text((256, 250), num, font=_fit(d, num, FONTS_BOLD, 260, 300), fill=WHITE, anchor="mm")
    elif cls.startswith("Speed"):
        d.ellipse([26, 26, 486, 486], fill=RED)
        d.ellipse([78, 78, 434, 434], fill=WHITE)
        num = cls[5:]
        d.text((256, 262), num, font=_fit(d, num, FONTS_BOLD, 200, 290), fill=BLACK, anchor="mm")
    elif cls == "GiveWay":
        d.polygon([(20, 46), (492, 46), (256, 470)], fill=RED)
        d.polygon([(112, 100), (400, 100), (256, 360)], fill=WHITE)
    elif cls == "OneLaneBridge":
        d.polygon([(256, 8), (504, 256), (256, 504), (8, 256)], fill=BLACK)
        d.polygon([(256, 30), (482, 256), (256, 482), (30, 256)], fill=YELLOW)
        f = _font(FONTS_BOLD, 76)
        for y, word in ((178, "ONE"), (256, "LANE"), (334, "BRIDGE")):
            d.text((256, y), word, font=f, fill=BLACK, anchor="mm")
    return img


def draw_post(cls: str) -> Image.Image:
    """512 x 1024 RGBA: the face in the top half, the grey back (same outline) in the bottom half."""
    face = _face_shape(cls)
    img = Image.new("RGBA", (512, 1024), (0, 0, 0, 0))
    img.paste(face, (0, 0))
    back = Image.new("RGBA", (512, 512), POST_GREY + (255,))
    back.putalpha(face.getchannel("A").transpose(Image.FLIP_LEFT_RIGHT))
    img.paste(back, (0, 512))
    return img


def write_hpp(names: dict[str, str], posts: list[str], path: Path) -> None:
    lines = ["// Road sign classes, generated by tools/signs.py. Included inside CfgVehicles in config.cpp.",
             "class Land_Aotearoa_Sign_Base: HouseNoDestruct", "{", "\tscope = 1;", f'\tmodel = "{MODEL}";',
             '\thiddenSelections[] = {"camo"};', "};"]
    for cls in sorted(names):
        lines += [f"class Land_Aotearoa_Sign_{cls}: Land_Aotearoa_Sign_Base", "{",
                  f'\thiddenSelectionsTextures[] = {{"{TEXTURE.format(cls=cls)}"}};', "};"]
    lines += ["class Land_Aotearoa_SignPost_Base: HouseNoDestruct", "{", "\tscope = 1;", f'\tmodel = "{POST_MODEL}";',
              '\thiddenSelections[] = {"camo"};', "};"]
    for cls in sorted(posts):
        lines += [f"class Land_Aotearoa_SignPost_{cls}: Land_Aotearoa_SignPost_Base", "{",
                  f'\thiddenSelectionsTextures[] = {{"{POST_TEXTURE.format(cls=cls)}"}};', "};"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\r\n")


def _spawner(path: Path, objects: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"Objects": [{
        "name": o["name"],
        "pos": [round(o["x"], 2), round(o["z"], 3), round(o["y"], 2)],
        "ypr": [round(o["yaw"], 1), 0.0, 0.0],
        "scale": 1.0,
        "enableCEPersistency": 0,
    } for o in objects]}, indent=1) + "\n", encoding="utf-8")


def build(h: np.ndarray, towns: list[dict], roads: dict, cell: float, size_m: float) -> dict[str, list[dict]]:
    named = [t for t in towns if t["tier"] != "hamlet"]
    index = RoadIndex(roads["roads"])
    town_signs = dedupe(entry_points(roads["roads"], named), named, h, cell, size_m, index)
    candidates = (speed_signs(roads["roads"], named) + shields(roads["roads"], towns, roads["bridges"])
                  + give_ways(roads["roads"]) + one_lane_bridges(roads["bridges"]))
    posts = place_posts(candidates, town_signs, towns, h, cell, size_m, index)

    SIGN_DIR.mkdir(parents=True, exist_ok=True)
    for old in list(SIGN_DIR.glob("sign_*.png")) + list(SIGN_DIR.glob("post_*.png")):
        old.unlink()
    names = {class_name(t["name"]): t for t in named}
    thumbs = []
    for cls, t in sorted(names.items()):
        img = draw_sign(t["name"], t["maori"])
        img.save(SIGN_DIR / f"sign_{cls}.png", optimize=True)
        thumbs.append(img.crop((0, 0, 1024, 512)).resize((256, 128), Image.LANCZOS))
    post_classes = sorted({p["cls"] for p in posts}, key=lambda c: (not c.startswith("SH"), len(c), c))
    for cls in post_classes:
        img = draw_post(cls)
        img.save(SIGN_DIR / f"post_{cls}.png", optimize=True)
        thumbs.append(img.crop((0, 0, 512, 512)).resize((128, 128), Image.LANCZOS))
    write_hpp(names, post_classes, MAP_DIR / "config" / "signs.hpp")

    for s in town_signs:
        s["name"] = f"Land_Aotearoa_Sign_{class_name(s['town'])}"
    for p in posts:
        p["name"] = f"Land_Aotearoa_SignPost_{p['cls']}"
    _spawner(SPAWNER, town_signs)
    _spawner(POST_SPAWNER, posts)

    x = y = 8
    rows = []
    for th in thumbs:
        if x + th.width > 6 * 264 + 8:
            x, y = 8, y + 136
        rows.append((th, x, y))
        x += th.width + 8
    sheet = Image.new("RGB", (6 * 264 + 8, y + 136), (30, 30, 30))
    for th, x, y in rows:
        sheet.paste(th, (x, y), th if th.mode == "RGBA" else None)
    sheet.save(MAP_DIR / "preview" / "signs_sheet.png", optimize=True)
    return {"town": town_signs, "post": posts}


def main() -> None:
    meta = json.loads((SOURCE / "heightmap.json").read_text())
    raw = np.asarray(Image.open(SOURCE / "heightmap_4096.png")).astype(np.float32)
    h = meta["png_black_m"] + raw / 65535.0 * (meta["png_white_m"] - meta["png_black_m"])
    with (SOURCE / "towns.csv").open(encoding="utf-8") as f:
        towns = list(csv.DictReader(f))
    roads = json.loads((SOURCE / "roads.json").read_text(encoding="utf-8"))
    signs = build(h, towns, roads, meta["cell_size_m"], meta["terrain_size_m"])
    print(summary(signs, towns))


def summary(signs: dict[str, list[dict]], towns: list[dict]) -> str:
    per_town = {s["town"] for s in signs["town"]}
    kinds: dict[str, int] = {}
    for p in signs["post"]:
        key = "State Highway shields" if p["cls"].startswith("SH") else p["cls"]
        kinds[key] = kinds.get(key, 0) + 1
    lines = [f"Town signs: {len(signs['town'])} at {len(per_town)} towns",
             f"Post signs: {len(signs['post'])} (" + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())) + ")"]
    missing = sorted(t["name"] for t in towns if t["tier"] != "hamlet" and t["name"] not in per_town)
    if missing:
        lines.append("  no road in: " + ", ".join(missing))
    return "\n".join(lines)


if __name__ == "__main__":
    main()
