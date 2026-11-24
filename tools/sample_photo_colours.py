"""Sample satellite colours from a north-up photo of New Zealand for the Aotearoa satellite texture.

Lines the photo up with the terrain by matching coastlines, then writes:

  tools/satellite_palette.json  median photo colour per surface layer, plus snow and sea colours
  source/sat_tint_512.png       the photo's regional colour, resampled into map space and blurred

The photo itself is not stored. Run:  python sample_photo_colours.py path/to/photo.png
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage, optimize

import generate_terrain as g

TOOLS_DIR = Path(__file__).resolve().parent
TINT_SIZE = 512


def merc_y(lat: np.ndarray) -> np.ndarray:
    return np.degrees(np.log(np.tan(np.pi / 4 + np.radians(lat) / 2)))


def photo_sea_mask(rgb: np.ndarray) -> np.ndarray:
    r, gr, b = (rgb[..., i].astype(np.float32) for i in range(3))
    sea = (b > r + 22) & (b > gr - 5)
    sea = ndimage.binary_opening(sea, iterations=1)
    return ndimage.binary_closing(sea, iterations=1)


def to_photo(params: np.ndarray, lon: np.ndarray, lat: np.ndarray, centre: tuple[float, float]):
    sx, sy, ox, oy, rot = params
    x = (lon - centre[0]) * sx
    y = -(merc_y(lat) - merc_y(np.array(centre[1]))) * sy
    c, s = math.cos(rot), math.sin(rot)
    return x * c - y * s + ox, x * s + y * c + oy


def main() -> None:
    photo_path = Path(sys.argv[1])
    rgb = np.asarray(Image.open(photo_path).convert("RGB"))
    sea_photo = photo_sea_mask(rgb)
    land_photo = ~sea_photo
    ph, pw = land_photo.shape

    meta = json.loads((g.SOURCE_DIR / "heightmap.json").read_text())
    proj = meta["projection"]
    raw = np.asarray(Image.open(g.SOURCE_DIR / "heightmap_4096.png")).astype(np.float32)
    h = meta["png_black_m"] + raw / 65535.0 * (meta["png_white_m"] - meta["png_black_m"])
    mask_rgb = np.asarray(Image.open(g.SOURCE_DIR / "mask_4096.png").convert("RGB"))
    colours = np.array([s[1] for s in g.SURFACES])
    idx = np.argmin(((mask_rgb[..., None, :].astype(int) - colours[None, None]) ** 2).sum(-1), axis=-1)

    gx, gy = g.game_grid()
    lon, lat = g.game_to_lonlat(gx, gy, proj)
    land = h > 0

    step = 8
    slon, slat, sland = lon[::step, ::step].ravel(), lat[::step, ::step].ravel(), land[::step, ::step].ravel()

    # Start from the land bounding boxes, then refine scale, offset and rotation on coastline agreement.
    rows, cols = np.nonzero(land_photo[int(ph * 0.02):int(ph * 0.98), int(pw * 0.02):int(pw * 0.98)])
    rows, cols = rows + int(ph * 0.02), cols + int(pw * 0.02)
    centre = (float(slon[sland].mean()), float(slat[sland].mean()))
    lon_span = np.ptp(slon[sland])
    my_span = np.ptp(merc_y(slat[sland]))
    p0 = np.array([np.ptp(cols) / lon_span, np.ptp(rows) / my_span, cols.mean(), rows.mean(), 0.0])

    def score(p):
        px, py = to_photo(p, slon, slat, centre)
        inside = (px >= 0) & (px < pw - 1) & (py >= 0) & (py < ph - 1)
        hit = np.zeros_like(sland)
        hit[inside] = land_photo[py[inside].astype(int), px[inside].astype(int)]
        tp = (hit & sland).sum()
        return -2 * tp / (hit.sum() + sland.sum())

    steps = np.array([p0[0] * 0.05, p0[1] * 0.05, 10.0, 10.0, 0.05])
    simplex = np.vstack([p0, p0 + np.diag(steps)])
    best = optimize.minimize(score, p0, method="Nelder-Mead",
                             options={"xatol": 1e-3, "fatol": 1e-5, "maxiter": 3000, "initial_simplex": simplex})
    params = best.x
    print(f"Coastline match (Dice): {-best.fun:.3f}  start {-score(p0):.3f}")

    px, py = to_photo(params, lon, lat, centre)
    coords = [np.clip(py, 0, ph - 1), np.clip(px, 0, pw - 1)]
    sampled = np.stack([ndimage.map_coordinates(rgb[..., i].astype(np.float32), coords, order=1)
                        for i in range(3)], axis=-1)
    photo_land_here = ndimage.map_coordinates(land_photo.astype(np.float32), coords, order=0) > 0.5

    palette = {}
    for i, (name, _, _) in enumerate(g.SURFACES):
        sel = (idx == i) & land & photo_land_here
        if name == "beach":
            sel &= h < 4
        if sel.sum() < 50:
            continue
        palette[name] = [int(v) for v in np.median(sampled[sel], axis=0)]

    lum = sampled.mean(-1)
    high = land & photo_land_here & (h > 300)
    snow_sel = high & (lum > np.percentile(lum[high], 92))
    palette["snow"] = [int(v) for v in np.median(sampled[snow_sel], axis=0)]

    dist_sea = ndimage.distance_transform_edt(~land) * g.CELL
    sea_here = ~land & ~photo_land_here
    shallow = sea_here & (dist_sea < 120)
    deep = sea_here & (dist_sea > 1500)
    palette["sea_shallow"] = [int(v) for v in np.median(sampled[shallow], axis=0)]
    palette["sea_deep"] = [int(v) for v in np.median(sampled[deep], axis=0)]

    out = {"source": photo_path.name, "coastline_match": round(float(-best.fun), 3), "colours": palette}
    (TOOLS_DIR / "satellite_palette.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(palette))

    # Regional tint: land colour only, filled outward over the sea so coastal blends stay land-coloured.
    good = land & photo_land_here
    _, (ri, ci) = ndimage.distance_transform_edt(~good, return_indices=True)
    filled = sampled[ri, ci]
    small = np.stack([ndimage.zoom(filled[..., i], TINT_SIZE / filled.shape[0], order=1) for i in range(3)], -1)
    small = np.stack([ndimage.gaussian_filter(small[..., i], 2.0) for i in range(3)], -1)
    Image.fromarray(np.clip(small, 0, 255).astype(np.uint8)).save(g.SOURCE_DIR / f"sat_tint_{TINT_SIZE}.png")

    check = rgb.copy()
    mpx, mpy = to_photo(params, slon[sland], slat[sland], centre)
    ok = (mpx >= 0) & (mpx < pw) & (mpy >= 0) & (mpy < ph)
    check[mpy[ok].astype(int), mpx[ok].astype(int)] = [255, 0, 0]
    Image.fromarray(check).save("/tmp/photo_alignment.png")


if __name__ == "__main__":
    main()
