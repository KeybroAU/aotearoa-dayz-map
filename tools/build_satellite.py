"""Build the Aotearoa satellite texture from the generated terrain and the photo-sampled colours.

Reads source/heightmap_4096.png, source/mask_4096.png, source/water_4096.png, source/sat_tint_512.png,
tools/satellite_palette.json and source/objects/towns_spawner.json, and writes
source/satellite_<size>.png plus previews. Terrain Builder wants 20480 (1 m per pixel):

    python build_satellite.py --size 20480

That needs about 5 GB of memory. The default 4096 is for a quick look.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

import generate_terrain as g
import towns as towns_mod

STRIP = 1024
# The photo is dark and hazy next to in-game lighting.
BRIGHTEN = 1.15
SNOWLINE_M = 330.0

# The photo is too coarse to separate layers, so it supplies the regional colour and each layer
# adjusts it: (multiplier on the photo colour, fixed colour, share of the fixed colour).
LAYER_STYLE = {
    "beach": ((1.0, 1.0, 1.0), (196, 182, 140), 0.85),
    "pasture": ((1.0, 1.05, 0.95), None, 0.0),
    "farmland": ((1.15, 1.1, 0.9), (150, 140, 90), 0.2),
    "bush": ((0.72, 0.85, 0.72), (38, 62, 34), 0.35),
    "pine": ((0.65, 0.75, 0.68), (40, 55, 42), 0.4),
    "tussock": ((1.3, 1.18, 0.95), (170, 150, 95), 0.45),
    "scree": ((1.0, 1.0, 1.0), (150, 146, 138), 0.7),
    "rock": ((0.9, 0.9, 0.9), (110, 105, 98), 0.6),
    "volcanic": ((0.9, 0.85, 0.85), (105, 92, 80), 0.6),
}
URBAN = np.array([150, 146, 136], dtype=np.float32)
ROOF_HOUSE = [(120, 70, 60), (95, 95, 100), (150, 140, 125), (70, 80, 90)]
ROOF_BIG = (135, 135, 135)
LAKE = np.array([46, 104, 122], dtype=np.float32)
GLACIAL = np.array([88, 170, 178], dtype=np.float32)
RIVER = np.array([92, 128, 134], dtype=np.float32)


def load_inputs():
    meta = json.loads((g.SOURCE_DIR / "heightmap.json").read_text())
    raw = np.asarray(Image.open(g.SOURCE_DIR / "heightmap_4096.png")).astype(np.float32)
    h = meta["png_black_m"] + raw / 65535.0 * (meta["png_white_m"] - meta["png_black_m"])
    mask_rgb = np.asarray(Image.open(g.SOURCE_DIR / "mask_4096.png").convert("RGB")).astype(int)
    lut = np.array([s[1] for s in g.SURFACES])
    idx = np.argmin(((mask_rgb[..., None, :] - lut[None, None]) ** 2).sum(-1), axis=-1).astype(np.uint8)
    tint = np.asarray(Image.open(g.SOURCE_DIR / "sat_tint_512.png").convert("RGB")).astype(np.float32)
    palette = json.loads((g.MAP_DIR / "tools" / "satellite_palette.json").read_text())["colours"]
    water = np.asarray(Image.open(g.SOURCE_DIR / "water_4096.png").convert("RGB")).astype(np.float32) / 255.0
    return h, idx, tint, palette, water[..., 0], water[..., 1]


class Lattice:
    """Tileable value noise sampled in world metres, so every strip lines up."""

    def __init__(self, seed: int, n: int = 1024):
        self.grid = np.random.default_rng(seed).random((n, n)).astype(np.float32) * 2 - 1

    def __call__(self, x: np.ndarray, y: np.ndarray, wavelength: float) -> np.ndarray:
        return ndimage.map_coordinates(self.grid, [y / wavelength, x / wavelength], order=1, mode="grid-wrap")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=int, default=4096)
    args = ap.parse_args()
    size = args.size
    mpp = g.SIZE_M / size

    h, idx, tint, palette, lake, river = load_inputs()
    lake_depth = np.clip(ndimage.distance_transform_edt(lake > 0.5) * g.CELL / 120.0, 0, 1).astype(np.float32)
    # Snow-fed Mackenzie lakes are milky turquoise; the rest read as ordinary deep lake water.
    glacial = np.zeros_like(lake)
    for lk in json.loads((g.SOURCE_DIR / "lakes.json").read_text(encoding="utf-8")):
        if lk["name"] in ("Pukaki", "Tekapo", "Ōhau"):
            cx, cy = lk["centre"]
            r, c = int((g.SIZE_M - cy) / g.CELL), int(cx / g.CELL)
            lab, _ = ndimage.label(lake > 0.5)
            if lab[r, c]:
                glacial[lab == lab[r, c]] = 1.0
    names = [s[0] for s in g.SURFACES]
    mult_lut = np.array([LAYER_STYLE[n][0] for n in names], dtype=np.float32)
    fixed_lut = np.array([LAYER_STYLE[n][1] or (0, 0, 0) for n in names], dtype=np.float32)
    share_lut = np.array([LAYER_STYLE[n][2] for n in names], dtype=np.float32)

    gy, gx = np.gradient(h, g.CELL)
    az, alt = math.radians(315), math.radians(45)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    shade = np.clip(np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)
    shade = shade.astype(np.float32)

    urban = urban_weight(h > 0)
    snow = np.array(palette["snow"], dtype=np.float32)
    sea_shallow = np.array(palette["sea_shallow"], dtype=np.float32)
    sea_deep = np.array(palette["sea_deep"], dtype=np.float32)
    noise = Lattice(g.SEED + 10)
    jitter = Lattice(g.SEED + 11)

    out = np.empty((size, size, 3), dtype=np.uint8)
    cols = (np.arange(size) + 0.5) * mpp
    for r0 in range(0, size, STRIP):
        r1 = min(size, r0 + STRIP)
        wy = g.SIZE_M - (np.arange(r0, r1) + 0.5) * mpp
        X, Y = np.meshgrid(cols, wy)
        cr = (g.SIZE_M - Y) / g.CELL - 0.5
        cc = X / g.CELL - 0.5

        hs = ndimage.map_coordinates(h, [cr, cc], order=1, mode="nearest")
        jr = cr + jitter(X, Y, 9.0) * 0.8 + jitter(X, Y + 7000, 45.0) * 2.5
        jc = cc + jitter(X + 5000, Y, 9.0) * 0.8 + jitter(X + 3000, Y + 7000, 45.0) * 2.5
        cls = idx[np.clip(np.rint(jr), 0, g.GRID - 1).astype(int), np.clip(np.rint(jc), 0, g.GRID - 1).astype(int)]

        tr = cr * tint.shape[0] / g.GRID
        tc = cc * tint.shape[1] / g.GRID
        local_tint = np.stack([ndimage.map_coordinates(tint[..., i], [tr, tc], order=1, mode="nearest")
                               for i in range(3)], -1)
        # Coastal photo pixels carry shallow-water blue; land never reads bluer than its green.
        local_tint[..., 2] = np.minimum(local_tint[..., 2], local_tint[..., 1] * 0.85)
        share = share_lut[cls][..., None]
        colour = local_tint * BRIGHTEN * mult_lut[cls] * (1 - share) + fixed_lut[cls] * share

        texture = 1.0 + 0.07 * noise(X, Y, 60.0) + 0.05 * noise(X, Y, 14.0) + 0.04 * noise(X, Y, 3.0)
        canopy = np.isin(cls, [names.index("bush"), names.index("pine")])
        texture = np.where(canopy, texture - 0.10 * np.maximum(noise(X + 9000, Y, 4.0), 0), texture)
        colour = colour * texture[..., None]

        uw = ndimage.map_coordinates(urban, [cr, cc], order=1, mode="nearest")[..., None]
        colour = colour * (1 - 0.3 * uw) + URBAN * 0.3 * uw

        sh = ndimage.map_coordinates(shade, [cr, cc], order=1, mode="nearest")
        colour = colour * (0.72 + 0.42 * sh)[..., None]

        line = SNOWLINE_M + 35.0 * noise(X, Y, 120.0) + 10.0 * noise(X, Y, 20.0)
        sw = np.clip((hs - line) / 30.0, 0, 1)[..., None]
        colour = colour * (1 - sw) + snow * (0.85 + 0.2 * sh[..., None]) * sw

        rw = ndimage.map_coordinates(river, [cr, cc], order=1, mode="nearest")
        braid = np.clip((rw - 0.75) * 4.0 + 0.9 * noise(X + 4000, Y, 18.0), 0, 1)[..., None]
        colour = colour * (1 - braid) + RIVER * (0.8 + 0.25 * sh[..., None]) * braid

        lw = np.clip(ndimage.map_coordinates(lake, [cr, cc], order=1, mode="nearest") * 1.6 - 0.3, 0, 1)[..., None]
        ld = ndimage.map_coordinates(lake_depth, [cr, cc], order=1, mode="nearest")[..., None]
        gl = ndimage.map_coordinates(glacial, [cr, cc], order=1, mode="nearest")[..., None]
        lake_colour = (LAKE * (1 - gl) + GLACIAL * gl) * (1.05 - 0.25 * ld)
        colour = colour * (1 - lw) + lake_colour * lw

        depth = np.clip(-hs / 30.0, 0, 1)[..., None]
        water = sea_shallow * (1 - depth) + sea_deep * depth
        water = water * (1.0 + 0.03 * noise(X, Y, 200.0))[..., None]
        wet = np.clip(hs / 0.8, 0, 1)[..., None]
        colour = np.where(hs[..., None] <= 0, water, colour * wet + water * (1 - wet))

        out[r0:r1] = np.clip(colour, 0, 255).astype(np.uint8)
        print(f"  rows {r1}/{size}")

    img = Image.fromarray(out)
    del out
    draw_towns(img, mpp)

    path = g.SOURCE_DIR / f"satellite_{size}.png"
    img.save(path, optimize=size <= 8192)
    print(f"Wrote {path}")
    img.resize((2048, 2048), Image.LANCZOS).save(g.PREVIEW_DIR / "satellite_2048.png", optimize=True)
    if size >= 8192:
        crop_town(img, "Christchurch", mpp).save(g.PREVIEW_DIR / "satellite_christchurch.png", optimize=True)


def urban_weight(land: np.ndarray) -> np.ndarray:
    import csv

    grid = towns_mod.Grid(g.SIZE_M, g.CELL, g.GRID)
    w = np.zeros(land.shape, dtype=np.float32)
    with (g.SOURCE_DIR / "towns.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            x, y, r = float(row["x"]), float(row["y"]), float(row["radius"])
            win, wx, wy = grid.window(x, y, r)
            t = np.clip((r - np.hypot(wx - x, wy - y)) / (0.2 * r), 0, 1)
            w[win] = np.maximum(w[win], t * t * (3 - 2 * t))
    return w * land


def draw_towns(img: Image.Image, mpp: float) -> None:
    d = ImageDraw.Draw(img)
    objects = json.loads((g.SOURCE_DIR / "objects" / "towns_spawner.json").read_text())["Objects"]
    rng = np.random.default_rng(g.SEED + 12)
    for o in objects:
        w, l = towns_mod.FOOTPRINTS.get(o["name"], (10, 12))
        bx, by = o["pos"][0], o["pos"][2]
        a = math.radians(o["ypr"][0])
        pts = []
        for sx, sy in ((-w / 2, -l / 2), (w / 2, -l / 2), (w / 2, l / 2), (-w / 2, l / 2)):
            ex = bx + sx * math.cos(a) + sy * math.sin(a)
            ey = by - sx * math.sin(a) + sy * math.cos(a)
            pts.append((ex / mpp, (g.SIZE_M - ey) / mpp))
        house = o["name"].startswith("Land_House")
        roof = ROOF_HOUSE[rng.integers(len(ROOF_HOUSE))] if house else ROOF_BIG
        d.polygon(pts, fill=roof)


def crop_town(img: Image.Image, name: str, mpp: float, span: float = 900.0) -> Image.Image:
    import csv

    with (g.SOURCE_DIR / "towns.csv").open(encoding="utf-8") as f:
        row = next(r for r in csv.DictReader(f) if r["name"] == name)
    x, y = float(row["x"]), float(row["y"])
    box = [(x - span / 2) / mpp, (g.SIZE_M - y - span / 2) / mpp,
           (x + span / 2) / mpp, (g.SIZE_M - y + span / 2) / mpp]
    return img.crop(tuple(int(v) for v in box)).resize((900, 900), Image.LANCZOS)


if __name__ == "__main__":
    main()
