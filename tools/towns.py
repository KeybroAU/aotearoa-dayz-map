"""Towns for the Aotearoa terrain.

Reads tools/towns.csv (real latitude and longitude), moves each site onto usable land,
flattens the ground there, lays out a street grid of DayZ buildings, and writes the map
labels and object lists.
"""

from __future__ import annotations

import csv
import json
import math
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

import labelplace
from PIL import Image, ImageDraw
from scipy import ndimage

import fontpaths

TOWNS_CSV = Path(__file__).resolve().parent / "towns.csv"

TIERS = {
    "capital": {"radius": 320.0, "name_type": "Capital", "big_share": 0.45},
    "city": {"radius": 210.0, "name_type": "City", "big_share": 0.30},
    "town": {"radius": 165.0, "name_type": "Village", "big_share": 0.12},
    "village": {"radius": 110.0, "name_type": "Village", "big_share": 0.0},
    "military": {"radius": 140.0, "name_type": "Local", "big_share": 0.0},
    "hamlet": {"radius": 70.0, "name_type": "", "big_share": 0.0},
}
MIN_LAND_SHARE = 0.7
MAX_PUSH_M = 300.0
HAMLET_COUNT = 45
HAMLET_SPACING_M = 800.0
HAMLET_TOWN_GAP_M = 450.0
# Tiers whose special buildings are small enough to share a block with two houses.
HALF_BLOCK_SPECIALS = {"town", "village"}

BLOCK = 45.0
STREET = 12.0
PITCH = BLOCK + STREET
MAX_TOWN_GRADE_DEG = 3.0
MAX_BLOCK_SLOPE_DEG = 12.0

# Vanilla DayZ building classes with rough footprints (width x length, metres). Terrain Builder
# templates are usually the model name, i.e. the class without "Land_"; check them against your
# library and edit here if a name differs.
HOUSES = [
    ("Land_House_1W01", 9, 12), ("Land_House_1W02", 9, 12), ("Land_House_1W03", 10, 14),
    ("Land_House_1W04", 9, 12), ("Land_House_1W05", 10, 13), ("Land_House_1W06", 9, 12),
    ("Land_House_2W01", 10, 14), ("Land_House_2W02", 10, 15), ("Land_House_2W03", 11, 15),
    ("Land_House_2B01", 10, 14), ("Land_House_2B02", 10, 14), ("Land_House_2B03", 11, 15),
]
BIG = [
    ("Land_Tenement_Big", 18, 38), ("Land_Tenement_Small", 14, 26),
    ("Land_Office1", 16, 30), ("Land_Office2", 16, 28), ("Land_City_Store", 14, 22),
]
SPECIALS = {
    "capital": ["Land_City_Hospital", "Land_City_PoliceStation", "Land_City_FireStation",
                "Land_Church1_Yellow", "Land_Village_Pub", "Land_Village_Pub", "Land_City_Store"],
    "city": ["Land_City_Hospital", "Land_City_PoliceStation", "Land_City_FireStation",
             "Land_Church2_1", "Land_Village_Pub"],
    "town": ["Land_Village_HealthCare", "Land_Village_PoliceStation", "Land_Church3",
             "Land_Village_Pub"],
    "village": ["Land_Village_Pub"],
    "hamlet": [],
    "military": ["Land_Mil_Guardhouse1", "Land_Mil_Barracks1", "Land_Mil_Barracks1",
                 "Land_Mil_Barracks2", "Land_Mil_Barracks3", "Land_Mil_ATC_Small",
                 "Land_Mil_Tent_Big1_1", "Land_Mil_Tent_Big1_1", "Land_Mil_Firestation"],
}
FOOTPRINTS = {name: (w, l) for name, w, l in HOUSES + BIG}
FOOTPRINTS.update({
    "Land_City_Hospital": (30, 42), "Land_City_PoliceStation": (20, 30),
    "Land_City_FireStation": (18, 30), "Land_Church1_Yellow": (16, 30), "Land_Church2_1": (14, 26),
    "Land_Church3": (12, 22), "Land_Village_Pub": (12, 18), "Land_Village_HealthCare": (12, 20),
    "Land_Village_PoliceStation": (12, 18), "Land_Mil_Guardhouse1": (8, 10),
    "Land_Mil_Barracks1": (10, 30), "Land_Mil_Barracks2": (10, 30), "Land_Mil_Barracks3": (12, 30),
    "Land_Mil_ATC_Small": (10, 10), "Land_Mil_Tent_Big1_1": (10, 20), "Land_Mil_Firestation": (16, 22),
})


@dataclass
class Building:
    cls: str
    x: float  # world metres, 0..terrain size, y north
    y: float
    yaw: float
    z: float = 0.0


@dataclass
class Town:
    name: str
    lat: float
    lon: float
    tier: str
    radius: float
    x: float = 0.0
    y: float = 0.0
    moved_m: float = 0.0
    grid_angle: float = 0.0
    maori: str = ""
    buildings: list[Building] = field(default_factory=list)
    blocks: list[tuple[int, int]] = field(default_factory=list)  # (i, j) of each laid-out block

    @property
    def class_name(self) -> str:
        ascii_name = unicodedata.normalize("NFKD", self.name).encode("ascii", "ignore").decode()
        return "".join(ch for ch in ascii_name.title() if ch.isalnum())

    @property
    def label(self) -> str:
        return f"{self.name} / {self.maori}" if self.maori else self.name


def load_towns() -> list[Town]:
    towns = []
    with TOWNS_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tier = row["tier"].strip()
            radius = float(row["radius"]) if row.get("radius", "").strip() else TIERS[tier]["radius"]
            towns.append(Town(row["name"].strip(), float(row["lat"]), float(row["lon"]), tier, radius,
                              maori=(row.get("maori") or "").strip()))
    return towns


class Grid:
    """Conversions between world metres (origin south-west, y north) and heightmap cells."""

    def __init__(self, size_m: float, cell: float, n: int):
        self.size_m, self.cell, self.n = size_m, cell, n

    def to_cell(self, x, y):
        return (self.size_m - np.asarray(y)) / self.cell - 0.5, np.asarray(x) / self.cell - 0.5

    def sample(self, arr: np.ndarray, x, y) -> np.ndarray:
        r, c = self.to_cell(x, y)
        return ndimage.map_coordinates(arr, [np.atleast_1d(r), np.atleast_1d(c)], order=1, mode="nearest")

    def window(self, x: float, y: float, radius: float):
        r, c = self.to_cell(x, y)
        k = int(math.ceil(radius / self.cell)) + 1
        r0, r1 = max(0, int(r) - k), min(self.n, int(r) + k + 1)
        c0, c1 = max(0, int(c) - k), min(self.n, int(c) + k + 1)
        rows, cols = np.mgrid[r0:r1, c0:c1]
        wx = (cols + 0.5) * self.cell
        wy = self.size_m - (rows + 0.5) * self.cell
        return (slice(r0, r1), slice(c0, c1)), wx, wy


def place_towns(towns: list[Town], lonlat_to_world: Callable, land: np.ndarray, grid: Grid) -> None:
    dist_land = ndimage.distance_transform_edt(land) * grid.cell
    for t in towns:
        x, y = lonlat_to_world(np.array(t.lon), np.array(t.lat))
        t.x, t.y = float(x), float(y)

    # The smaller of two overlapping neighbours steps away from the larger one (Cambridge from
    # Hamilton), up to MAX_PUSH_M, so big cities keep their size.
    pushed = {id(t): 0.0 for t in towns}
    for _ in range(6):
        for i, a in enumerate(towns):
            for b in towns[i + 1:]:
                small, big = (a, b) if a.radius < b.radius else (b, a)
                dx, dy = small.x - big.x, small.y - big.y
                d = math.hypot(dx, dy) or 1.0
                need = (a.radius + b.radius) / 0.9 - d
                room = MAX_PUSH_M - pushed[id(small)]
                if need > 0 and room > 0:
                    step = min(need, room)
                    small.x += dx / d * step
                    small.y += dy / d * step
                    pushed[id(small)] += step

    # Shrink neighbours that still overlap (e.g. Napier and Hastings).
    for _ in range(4):
        for i, a in enumerate(towns):
            for b in towns[i + 1:]:
                d = math.hypot(a.x - b.x, a.y - b.y)
                if a.radius + b.radius > 0.9 * d:
                    f = max(0.9 * d / (a.radius + b.radius), 0.5)
                    a.radius, b.radius = max(a.radius * f, 45.0), max(b.radius * f, 45.0)

    # Coastal towns move inland until most of the town sits on land.
    for t in towns:
        win, wx, wy = grid.window(t.x, t.y, 900.0 + t.radius)
        k = max(3, int(1.6 * t.radius / grid.cell))
        share = ndimage.uniform_filter(land[win].astype(np.float32), size=k, mode="constant")
        ok = (share >= MIN_LAND_SHARE) & (dist_land[win] >= 20.0)
        if not ok.any():
            raise RuntimeError(f"No land near {t.name}")
        d2 = (wx - t.x) ** 2 + (wy - t.y) ** 2
        d2 = np.where(ok, d2, np.inf)
        i = np.unravel_index(np.argmin(d2), d2.shape)
        t.moved_m = float(math.sqrt(d2[i]))
        t.x, t.y = float(wx[i]), float(wy[i])


def make_hamlets(towns: list[Town], h: np.ndarray, land: np.ndarray, grid: Grid, seed: int) -> list[Town]:
    """Small unnamed clusters of houses in the countryside between the named towns."""
    rng = np.random.default_rng(seed)
    gy, gx = np.gradient(h, grid.cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    dist_sea = ndimage.distance_transform_edt(land) * grid.cell
    smooth = ndimage.uniform_filter(slope, size=int(140 / grid.cell))
    cand = land & (h > 3.0) & (h < 300.0) & (smooth < 12.0) & (dist_sea > 100.0)
    step = 8
    rows, cols = np.nonzero(cand[::step, ::step])
    order = rng.permutation(len(rows))
    taken = [(t.x, t.y, t.radius + HAMLET_TOWN_GAP_M) for t in towns]
    out: list[Town] = []
    for k in order:
        if len(out) >= HAMLET_COUNT:
            break
        x, y = (cols[k] * step + 0.5) * grid.cell, grid.size_m - (rows[k] * step + 0.5) * grid.cell
        if any(math.hypot(x - a, y - b) < r for a, b, r in taken):
            continue
        t = Town(f"Hamlet {len(out) + 1:02d}", 0.0, 0.0, "hamlet", TIERS["hamlet"]["radius"], x=float(x), y=float(y))
        out.append(t)
        taken.append((x, y, HAMLET_SPACING_M))
    return out


def flatten_towns(h: np.ndarray, land: np.ndarray, towns: list[Town], grid: Grid) -> np.ndarray:
    h = h.copy()
    dist_land = ndimage.distance_transform_edt(land) * grid.cell
    max_grade = math.tan(math.radians(MAX_TOWN_GRADE_DEG))
    for t in towns:
        win, wx, wy = grid.window(t.x, t.y, t.radius)
        dx, dy = wx - t.x, wy - t.y
        inner = (np.hypot(dx, dy) <= t.radius) & land[win]
        if inner.sum() < 10:
            continue
        hi = h[win][inner]
        A = np.column_stack([dx[inner], dy[inner], np.ones(inner.sum())])
        a, b, _ = np.linalg.lstsq(A, hi, rcond=None)[0]
        grade = math.hypot(a, b)
        if grade > max_grade:
            a, b = a * max_grade / grade, b * max_grade / grade
        c = max(float(np.median(hi - a * dx[inner] - b * dy[inner])), 4.0)

        # Widen the blend where the town platform sits well above or below the land around it,
        # so the edge stays under the slope cap instead of being cut back into the town.
        ring, rx, ry = grid.window(t.x, t.y, t.radius * 2.5)
        rdx, rdy = rx - t.x, ry - t.y
        rd = np.hypot(rdx, rdy)
        around = (rd > t.radius) & (rd <= t.radius * 2.5) & land[ring]
        gap = np.abs(h[ring] - (a * rdx + b * rdy + c))[around]
        spread = float(np.percentile(gap, 90)) if gap.size else 0.0
        reach = t.radius + min(max(0.6 * t.radius, 2.2 * spread), 500.0)

        win, wx, wy = grid.window(t.x, t.y, reach)
        hw, lw = h[win], land[win]
        dx, dy = wx - t.x, wy - t.y
        d = np.hypot(dx, dy)
        plane = a * dx + b * dy + c
        flat = plane + np.clip(0.12 * (hw - plane), -1.5, 1.5)
        s = np.clip((reach - d) / (reach - t.radius), 0.0, 1.0)
        w = s * s * (3 - 2 * s)
        coast = np.clip(dist_land[win] / 30.0, 0.0, 1.0)
        w = w * coast * coast * (3 - 2 * coast)
        h[win] = np.where(lw, hw * (1 - w) + np.maximum(flat, 0.6) * w, hw)
    return h


def layout_towns(towns: list[Town], h: np.ndarray, land: np.ndarray, grid: Grid, seed: int) -> None:
    rng = np.random.default_rng(seed)
    dist_land = ndimage.distance_transform_edt(land) * grid.cell
    gy, gx = np.gradient(h, grid.cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))

    for t in towns:
        # Grids at 0 or 45 degrees look the same whichever way the yaw convention turns.
        t.grid_angle = float(rng.choice([0.0, 45.0]))
        ang = math.radians(t.grid_angle)
        ca, sa = math.cos(ang), math.sin(ang)

        def to_world(u, v):
            return t.x + u * ca + v * sa, t.y - u * sa + v * ca

        n = int(t.radius / PITCH) + 1
        blocks = []
        for i in range(-n, n):
            for j in range(-n, n):
                u, v = (i + 0.5) * PITCH, (j + 0.5) * PITCH
                d = math.hypot(u, v)
                if d > t.radius - BLOCK * 0.3:
                    continue
                corners = [to_world(u + su * BLOCK / 2, v + sv * BLOCK / 2)
                           for su in (-1, 0, 1) for sv in (-1, 0, 1)]
                cx, cy = zip(*corners)
                if grid.sample(dist_land, cx, cy).min() < 8.0:
                    continue
                s = grid.sample(slope, cx, cy)
                if np.median(s) > MAX_BLOCK_SLOPE_DEG or s.max() > 2 * MAX_BLOCK_SLOPE_DEG:
                    continue
                blocks.append((d, u, v))
        blocks.sort()
        if not blocks:
            continue
        t.blocks = [(int(round(u / PITCH - 0.5)), int(round(v / PITCH - 0.5))) for _, u, v in blocks]

        tier = TIERS[t.tier]
        specials = list(SPECIALS[t.tier])
        military = t.tier == "military"
        n_big = int(round(tier["big_share"] * sum(1 for d, _, _ in blocks if d < 0.5 * t.radius)))
        if not military:
            reserved = max(1, int(0.4 * len(blocks)))
            specials = specials[:reserved]
            n_big = min(n_big, reserved - len(specials))

        for d, u, v in blocks:
            if not specials and military:
                break
            keep = 1.0 if d < 0.6 * t.radius else 0.55 + 0.45 * (t.radius - d) / (0.4 * t.radius)
            if not specials and rng.random() > keep:
                continue
            yaw_base = t.grid_angle + 90.0 * rng.integers(0, 4)
            house_cols = (-1, 1)
            if specials and t.tier in HALF_BLOCK_SPECIALS:
                side = int(rng.choice([-1, 1]))
                x, y = to_world(u + side * BLOCK / 4, v)
                yaw = t.grid_angle + (90.0 if side > 0 else 270.0)
                t.buildings.append(Building(specials.pop(0), x, y, yaw % 360))
                house_cols = (-side,)
            elif specials or n_big > 0:
                if specials:
                    cls = specials.pop(0)
                else:
                    cls = BIG[rng.integers(len(BIG))][0]
                    n_big -= 1
                x, y = to_world(u, v)
                t.buildings.append(Building(cls, x, y, yaw_base % 360))
                continue
            for su in house_cols:
                for sv in (-1, 1):
                    if rng.random() > 0.85:
                        continue
                    cls = HOUSES[rng.integers(len(HOUSES))][0]
                    x, y = to_world(u + su * BLOCK / 4, v + sv * BLOCK / 4)
                    # Face the nearer street: out along u or v.
                    if rng.random() < 0.5:
                        yaw = t.grid_angle + (90.0 if su > 0 else 270.0)
                    else:
                        yaw = t.grid_angle + (0.0 if sv > 0 else 180.0)
                    t.buildings.append(Building(cls, x, y, yaw % 360))

        if t.buildings:
            zs = grid.sample(h, [b.x for b in t.buildings], [b.y for b in t.buildings])
            for b, z in zip(t.buildings, zs):
                b.z = float(z)


def town_mask(towns: list[Town], grid: Grid) -> np.ndarray:
    m = np.zeros((grid.n, grid.n), dtype=bool)
    for t in towns:
        win, wx, wy = grid.window(t.x, t.y, t.radius * 1.05)
        m[win] |= np.hypot(wx - t.x, wy - t.y) <= t.radius * 1.05
    return m


def write_names_hpp(towns: list[Town], path: Path) -> None:
    lines = ["// Map labels for CfgWorlds >> aotearoa >> Names. Generated by tools/generate_terrain.py.",
             "class Names", "{"]
    for t in towns:
        if getattr(t, "tier", "") == "hamlet":
            continue
        lines += [
            f"\tclass {t.class_name}",
            "\t{",
            f'\t\tname = "{t.label}";',
            f"\t\tposition[] = {{{t.x:.1f}, {t.y:.1f}}};",
            f'\t\ttype = "{getattr(t, "name_type", None) or TIERS[t.tier]["name_type"]}";',
            f"\t\tradiusA = {t.radius:.0f};",
            f"\t\tradiusB = {t.radius:.0f};",
            "\t\tangle = 0;",
            "\t};",
        ]
    lines += ["};", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\r\n")


def write_towns_csv(towns: list[Town], path: Path, easting: float, northing: float) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "maori", "tier", "x", "y", "tb_x", "tb_y", "z", "radius", "buildings", "moved_m"])
        for t in towns:
            z = t.buildings[0].z if t.buildings else 0.0
            w.writerow([t.name, t.maori, t.tier, f"{t.x:.1f}", f"{t.y:.1f}", f"{t.x + easting:.1f}",
                        f"{t.y + northing:.1f}", f"{z:.1f}", f"{t.radius:.0f}", len(t.buildings),
                        f"{t.moved_m:.0f}"])


def write_terrain_builder_objects(towns: list[Town], path: Path, easting: float, northing: float) -> None:
    """Terrain Builder text import: "template";x;y;yaw;pitch;roll;scale;z offset;"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="\r\n") as f:
        for t in towns:
            for b in t.buildings:
                template = b.cls[5:].lower() if b.cls.startswith("Land_") else b.cls.lower()
                f.write(f'"{template}";{b.x + easting:.3f};{b.y + northing:.3f};{b.yaw:.3f};0;0;1;0;\n')


def write_object_spawner(towns: list[Town], path: Path) -> None:
    """DayZ cfggameplay.json objectSpawnersArr file, for trying towns on a server before the WRP is rebuilt."""
    objects = [
        {"name": b.cls, "pos": [round(b.x, 3), round(b.z, 3), round(b.y, 3)],
         "ypr": [round(b.yaw, 3), 0.0, 0.0], "scale": 1.0, "enableCEPersistency": 0}
        for t in towns for b in t.buildings
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"Objects": objects}, indent=1) + "\n")


def _font(size: int):
    from PIL import ImageFont

    # Pillow's built-in font has no macrons, so prefer a system font that does.
    for name in (fontpaths.path("DejaVuSans.ttf"), "DejaVuSans.ttf", "arial.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def draw_overview(img: Image.Image, towns: list[Town], size_m: float) -> Image.Image:
    img = img.copy()
    d = ImageDraw.Draw(img)
    f = img.size[0] / size_m
    for t in towns:
        for b in t.buildings:
            px, py = b.x * f, (size_m - b.y) * f
            d.rectangle([px - 1, py - 1, px + 1, py + 1], fill=(200, 40, 40))
    placer = labelplace.Placer(d, img.size)
    named = [t for t in towns if getattr(t, "tier", "") != "hamlet"]
    for t in named:
        px, py = t.x * f, (size_m - t.y) * f
        r = max(3.0, t.radius * f)
        placer.reserve((px - r, py - r, px + r, py + r))
    for t in sorted(named, key=lambda t: -t.radius):
        px, py = t.x * f, (size_m - t.y) * f
        colour = (255, 255, 0) if t.tier == "military" else (255, 255, 255)
        placer.label([(t.label, _font(13), colour)], px, py, r=max(3.0, t.radius * f), gap=4,
                     stroke_fill=(0, 0, 0))
    return img


def draw_town_detail(h: np.ndarray, town: Town, grid: Grid, span: float = 900.0) -> Image.Image:
    """1 px per metre close-up with building footprints."""
    win, wx, wy = grid.window(town.x, town.y, span / 2)
    hw = h[win]
    gy, gx = np.gradient(hw, grid.cell)
    shade = np.clip(0.6 + 0.4 * (-gx - gy) / (np.hypot(gx, gy) + 0.3), 0.2, 1.0)
    base = np.where(hw[..., None] > 0, np.array([110, 160, 80]), np.array([60, 110, 170]))
    rgb = (base * shade[..., None]).clip(0, 255).astype(np.uint8)
    f = int(grid.cell)
    img = Image.fromarray(rgb).resize((rgb.shape[1] * f, rgb.shape[0] * f), Image.BILINEAR)
    x0, y1 = float(wx[0, 0]) - grid.cell / 2, float(wy[0, 0]) + grid.cell / 2
    d = ImageDraw.Draw(img)
    for b in town.buildings:
        w, l = FOOTPRINTS.get(b.cls, (10, 12))
        a = math.radians(b.yaw)
        pts = []
        for sx, sy in ((-w / 2, -l / 2), (w / 2, -l / 2), (w / 2, l / 2), (-w / 2, l / 2)):
            ex = b.x + sx * math.cos(a) + sy * math.sin(a)
            ey = b.y - sx * math.sin(a) + sy * math.cos(a)
            pts.append((ex - x0, y1 - ey))
        colour = (230, 230, 220) if b.cls in FOOTPRINTS and b.cls.startswith("Land_House") else (220, 90, 60)
        d.polygon(pts, fill=colour, outline=(40, 40, 40))
    d.text((8, 8), f"{town.label}  ({len(town.buildings)} buildings, radius {town.radius:.0f} m)",
           fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0), font=_font(16))
    return img
