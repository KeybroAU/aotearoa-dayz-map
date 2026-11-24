"""Generate the Aotearoa DayZ terrain source data from real New Zealand elevation.

Downloads public Terrarium elevation tiles (AWS Open Data, derived from SRTM,
GEBCO, LINZ and others), fits the North and South Islands north-up into a
20480 m square, compresses the relief so slopes are playable at DayZ scale,
adds game-scale detail, and writes:

  source/heightmap_4096.png   16-bit grayscale, see heightmap.json for the range
  source/heightmap.json       height range, grid and projection details
  source/mask_<size>.png      surface mask using the colours in layers.cfg
  source/towns.csv            town positions in world and Terrain Builder coordinates
  source/objects/towns_tb.txt Terrain Builder object import for the town buildings
  source/objects/towns_spawner.json  the same buildings as a cfggameplay.json object spawner
  config/names.hpp            CfgWorlds Names class with the town labels
  preview/*.png               shaded relief, surface mask, slope, town overview and close-ups
  <out>/heightmap_4096.asc    ESRI ASCII grid for Terrain Builder (--asc only)

Run from anywhere:  python generate_terrain.py [--asc] [--mask-size 20480]
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

import towns as towns_mod

MAP_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = MAP_DIR / "source"
PREVIEW_DIR = MAP_DIR / "preview"
CACHE_DIR = Path(os.environ.get("AOTEAROA_TILE_CACHE", Path.home() / ".cache" / "aotearoa-tiles"))

TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
ZOOM = 9

GRID = 4096
CELL = 5.0
SIZE_M = GRID * CELL
MARGIN_M = 650.0

# Mainland New Zealand plus Stewart Island; the Chathams and outlying islands are left out.
LAT_N, LAT_S = -34.30, -47.35
LON_W, LON_E = 166.35, 178.65
LAT0 = (LAT_N + LAT_S) / 2
LON0 = (LON_W + LON_E) / 2
KM_PER_DEG_LAT = 110.57
KM_PER_DEG_LON = 111.32 * math.cos(math.radians(LAT0))

# Turning the country clockwise lays its length along the map diagonal; north-up wastes more sea.
ROTATION_DEG = -16.0

MAX_HEIGHT = 480.0  # height of the broad Southern Alps around Aoraki / Mt Cook, before detail
BROAD_SIGMA = 22.0  # grid cells
MIDDLE_SIGMA = 8.0
MIDDLE_WEIGHT = 0.35
COAST_RAMP_M = 450.0
SEA_DEPTH = 45.0
MAX_SLOPE_DEG = 40.0
MIN_ISLAND_CELLS = 400  # 0.01 km2

# Easting offset Terrain Builder projects use for DayZ terrains.
EASTING = 200000
NORTHING = 0

SEED = 1840

DETAIL_TOWNS = ["Auckland", "Wellington", "Christchurch", "Queenstown"]


def lonlat_to_tile(lon: np.ndarray, lat: np.ndarray, z: int) -> tuple[np.ndarray, np.ndarray]:
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    lat_r = np.radians(lat)
    y = (1.0 - np.log(np.tan(lat_r) + 1.0 / np.cos(lat_r)) / math.pi) / 2.0 * n
    return x, y


def fetch_tile(z: int, x: int, y: int) -> np.ndarray:
    path = CACHE_DIR / str(z) / str(x) / f"{y}.png"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        url = TILE_URL.format(z=z, x=x, y=y)
        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    data = r.read()
                break
            except OSError:
                if attempt == 4:
                    raise
        path.write_bytes(data)
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    return rgb[..., 0] * 256.0 + rgb[..., 1] + rgb[..., 2] / 256.0 - 32768.0


def build_mosaic() -> tuple[np.ndarray, int, int]:
    tx0, ty0 = lonlat_to_tile(np.array(LON_W), np.array(LAT_N), ZOOM)
    tx1, ty1 = lonlat_to_tile(np.array(LON_E), np.array(LAT_S), ZOOM)
    xs = range(int(tx0), int(tx1) + 1)
    ys = range(int(ty0), int(ty1) + 1)
    jobs = [(x, y) for y in ys for x in xs]
    print(f"Elevation tiles: {len(jobs)} at zoom {ZOOM}")
    with ThreadPoolExecutor(16) as pool:
        tiles = list(pool.map(lambda j: fetch_tile(ZOOM, *j), jobs))
    mosaic = np.zeros((len(ys) * 256, len(xs) * 256), dtype=np.float32)
    for (x, y), t in zip(jobs, tiles):
        r, c = (y - ys.start) * 256, (x - xs.start) * 256
        mosaic[r:r + 256, c:c + 256] = t
    return mosaic, xs.start, ys.start


def tile_to_lonlat(px: np.ndarray, py: np.ndarray, z: int) -> tuple[np.ndarray, np.ndarray]:
    n = 2 ** z
    lon = px / n * 360.0 - 180.0
    lat = np.degrees(np.arctan(np.sinh(math.pi * (1.0 - 2.0 * py / n))))
    return lon, lat


def rotate(x: np.ndarray, y: np.ndarray, deg: float) -> tuple[np.ndarray, np.ndarray]:
    t = math.radians(deg)
    return x * math.cos(t) - y * math.sin(t), x * math.sin(t) + y * math.cos(t)


def projection(mosaic: np.ndarray, tx0: int, ty0: int) -> dict:
    """Scale and centre that fit the rotated land into the map with MARGIN_M of sea."""
    rows, cols = np.nonzero(mosaic[::4, ::4] > 0.5)
    lon, lat = tile_to_lonlat(tx0 + (cols * 4 + 0.5) / 256, ty0 + (rows * 4 + 0.5) / 256, ZOOM)
    inside = (lon >= LON_W) & (lon <= LON_E) & (lat <= LAT_N) & (lat >= LAT_S)
    xk = (lon[inside] - LON0) * KM_PER_DEG_LON
    yk = (lat[inside] - LAT0) * KM_PER_DEG_LAT
    u, v = rotate(xk, yk, ROTATION_DEG)
    span_km = max(np.ptp(u), np.ptp(v))
    return {
        "real_m_per_game_m": float(span_km * 1000.0 / (SIZE_M - 2 * MARGIN_M)),
        "centre_u_km": float((u.max() + u.min()) / 2),
        "centre_v_km": float((v.max() + v.min()) / 2),
        "span_km": float(span_km),
    }


def game_to_lonlat(gx: np.ndarray, gy: np.ndarray, proj: dict) -> tuple[np.ndarray, np.ndarray]:
    """Game metres relative to the map centre (y north) to longitude and latitude."""
    scale = proj["real_m_per_game_m"] / 1000.0
    u = gx * scale + proj["centre_u_km"]
    v = gy * scale + proj["centre_v_km"]
    xk, yk = rotate(u, v, -ROTATION_DEG)
    return LON0 + xk / KM_PER_DEG_LON, LAT0 + yk / KM_PER_DEG_LAT


def lonlat_to_world(lon: np.ndarray, lat: np.ndarray, proj: dict) -> tuple[np.ndarray, np.ndarray]:
    """Longitude and latitude to world metres (origin at the south-west corner, y north)."""
    xk = (lon - LON0) * KM_PER_DEG_LON
    yk = (lat - LAT0) * KM_PER_DEG_LAT
    u, v = rotate(xk, yk, ROTATION_DEG)
    scale = proj["real_m_per_game_m"] / 1000.0
    return (u - proj["centre_u_km"]) / scale + SIZE_M / 2, (v - proj["centre_v_km"]) / scale + SIZE_M / 2


def game_grid() -> tuple[np.ndarray, np.ndarray]:
    # Row 0 is the northern edge, matching image and Terrain Builder import orientation.
    centres = (np.arange(GRID) + 0.5) * CELL - SIZE_M / 2
    return np.meshgrid(centres, -centres)


def sample_real_heights(mosaic: np.ndarray, tx0: int, ty0: int, proj: dict) -> np.ndarray:
    lon, lat = game_to_lonlat(*game_grid(), proj)
    px, py = lonlat_to_tile(lon, lat, ZOOM)
    px = (px - tx0) * 256 - 0.5
    py = (py - ty0) * 256 - 0.5
    return ndimage.map_coordinates(mosaic, [py, px], order=1, mode="nearest").astype(np.float32)


def fbm(shape: tuple[int, int], wavelength: float, octaves: int, rng: np.random.Generator,
        ridged: bool = False) -> np.ndarray:
    out = np.zeros(shape, dtype=np.float32)
    amp, total = 1.0, 0.0
    for _ in range(octaves):
        cells = max(2, int(shape[0] / wavelength) + 3)
        coarse = rng.standard_normal((cells, cells)).astype(np.float32)
        layer = ndimage.zoom(coarse, shape[0] / (cells - 3), order=3)[: shape[0], : shape[1]]
        if ridged:
            layer = 1.0 - np.abs(layer)
        out += layer * amp
        total += amp
        amp *= 0.5
        wavelength /= 2.0
    out /= total
    return (out - out.mean()) / (out.std() + 1e-6)


def smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def clean_land_mask(real: np.ndarray) -> np.ndarray:
    land = real > 0.5
    labels, n = ndimage.label(land)
    sizes = ndimage.sum(land, labels, np.arange(1, n + 1))
    keep = np.zeros(n + 1, dtype=bool)
    keep[1:] = sizes >= MIN_ISLAND_CELLS
    land = keep[labels]
    sea_labels, m = ndimage.label(~land)
    sea_sizes = ndimage.sum(~land, sea_labels, np.arange(1, m + 1))
    fill = np.zeros(m + 1, dtype=bool)
    fill[1:] = sea_sizes < MIN_ISLAND_CELLS
    return land | fill[sea_labels]


def limit_slope(h: np.ndarray, max_deg: float, radius: int = 3, max_iterations: int = 200) -> np.ndarray:
    """Lower every cell to at most max_deg above any neighbour, so no slope exceeds it."""
    rise = math.tan(math.radians(max_deg)) * CELL
    yy, xx = np.mgrid[-radius:radius + 1, -radius:radius + 1]
    structure = (-np.hypot(yy, xx) * rise).astype(np.float32)
    h = h.astype(np.float32)
    for _ in range(max_iterations):
        lowered = ndimage.grey_erosion(h, structure=structure)
        if float(np.max(h - lowered)) < 0.01:
            break
        h = lowered
    return h


def slope_degrees(h: np.ndarray) -> np.ndarray:
    gy, gx = np.gradient(h, CELL)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def build_heights(real: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(SEED)
    land = clean_land_mask(real)
    dist_land = ndimage.distance_transform_edt(land) * CELL
    dist_sea = ndimage.distance_transform_edt(~land) * CELL

    # Real relief squeezed ~65x horizontally turns into cliffs, so the height comes from a
    # broad band (ranges, plateaus, basins) plus a damped middle band (main valleys and spurs),
    # and the small-scale detail is procedural.
    relief = np.clip(real, 0.0, None)
    broad = ndimage.gaussian_filter(relief, BROAD_SIGMA)
    middle = ndimage.gaussian_filter(relief, MIDDLE_SIGMA) - broad
    k = MAX_HEIGHT / float(broad.max())
    base = MAX_HEIGHT * np.power(broad / float(broad.max()), 1.1) + MIDDLE_WEIGHT * k * middle
    base = np.maximum(base, 0.0)

    mountain = smoothstep(base / 250.0)
    hills = fbm(real.shape, 220.0, 5, rng)
    ridges = fbm(real.shape, 140.0, 5, rng, ridged=True)
    rolling = fbm(real.shape, 90.0, 4, rng)
    detail = (
        rolling * (1.5 + 0.02 * base)
        + hills * (4.0 + 0.05 * base)
        + ridges * mountain * (0.06 * base)
    )
    h = base + detail

    coast = smoothstep(dist_land / COAST_RAMP_M)
    beach = 0.6 + np.minimum(dist_land, 60.0) * 0.03
    h = np.maximum(h, 2.0) * coast + beach * (1.0 - coast)
    h = np.where(land, h, 0.0)
    h = limit_slope(h, MAX_SLOPE_DEG)
    h = ndimage.gaussian_filter(h, 1.2)
    h = np.where(land, np.maximum(h, 0.5), 0.0)

    shelf = SEA_DEPTH * (1.0 - np.exp(-dist_sea / 260.0)) + 0.8
    seabed = -shelf + fbm(real.shape, 300.0, 3, rng) * np.minimum(dist_sea / 200.0, 1.0) * 2.0
    h = np.where(land, h, np.minimum(seabed, -0.3))
    return h.astype(np.float32), land


# name, rgb, DayZ surface material. Material paths match the vanilla DZ\surfaces\data\terrain set;
# confirm against P:\DZ\surfaces\data\terrain before building.
SURFACES = [
    ("beach", (255, 230, 140), r"DZ\surfaces\data\terrain\sa_beach.rvmat"),
    ("pasture", (120, 190, 60), r"DZ\surfaces\data\terrain\cp_grass.rvmat"),
    ("farmland", (200, 200, 90), r"DZ\surfaces\data\terrain\cp_grass_tall.rvmat"),
    ("bush", (20, 90, 30), r"DZ\surfaces\data\terrain\cp_broadleaf_dense1.rvmat"),
    ("pine", (60, 110, 70), r"DZ\surfaces\data\terrain\cp_conifer_common1.rvmat"),
    ("tussock", (190, 160, 80), r"DZ\surfaces\data\terrain\sa_grass_brown.rvmat"),
    ("scree", (150, 150, 150), r"DZ\surfaces\data\terrain\cp_gravel.rvmat"),
    ("rock", (90, 80, 75), r"DZ\surfaces\data\terrain\cp_rock.rvmat"),
    ("volcanic", (120, 60, 50), r"DZ\surfaces\data\terrain\sa_volcanic_red.rvmat"),
]


def build_mask(h: np.ndarray, land: np.ndarray, proj: dict) -> np.ndarray:
    rng = np.random.default_rng(SEED + 1)
    slope = slope_degrees(h)
    dist_land = ndimage.distance_transform_edt(land) * CELL
    patch = fbm(h.shape, 120.0, 4, rng)
    patch2 = fbm(h.shape, 60.0, 4, rng)

    lon, lat = game_to_lonlat(*game_grid(), proj)
    south = lat < -40.6
    # Main divide runs roughly SW-NE through the South Island; west of it is wet bush country.
    divide_lon = 168.0 + (lat + 46.0) * (-1.25)
    west_coast = south & (lon < divide_lon + 0.25)
    plateau = (lat > -39.5) & (lat < -38.9) & (lon > 175.3) & (lon < 175.9)

    idx = np.full(h.shape, 1, dtype=np.uint8)
    idx[(h < 90) & (slope < 6) & (patch2 > 0.2)] = 2
    idx[(slope > 11) & (h < 520) & (patch > -0.5)] = 3
    idx[west_coast & (h < 560) & (patch > -1.0)] = 3
    idx[(~south) & (h > 60) & (h < 300) & (slope < 14) & (patch2 > 0.9)] = 4
    idx[south & ~west_coast & (h > 140) & (h < 600) & (slope < 22)] = 5
    idx[(h > 560) | ((h > 450) & (patch < -0.3))] = 6
    idx[plateau & (h > 260)] = 8
    idx[slope > 36] = 7
    idx[(h < 3.2) & (dist_land < 120) & (slope < 8)] = 0
    idx[~land] = 0
    return idx


def mask_to_rgb(idx: np.ndarray) -> np.ndarray:
    lut = np.array([s[1] for s in SURFACES], dtype=np.uint8)
    return lut[idx]


def upscale_mask(idx: np.ndarray, size: int) -> np.ndarray:
    """Nearest-neighbour upscale with jittered sampling so class edges are not blocky."""
    rng = np.random.default_rng(SEED + 2)
    f = size / idx.shape[0]
    out = np.empty((size, size), dtype=np.uint8)
    step = 2048
    jitter = rng.uniform(-0.6, 0.6, (2, step, size)).astype(np.float32)
    cols = (np.arange(size) + 0.5) / f - 0.5
    for r0 in range(0, size, step):
        rows = (np.arange(r0, min(size, r0 + step)) + 0.5) / f - 0.5
        rr, cc = np.meshgrid(rows, cols, indexing="ij")
        n = rr.shape[0]
        ri = np.clip(np.rint(rr + jitter[0, :n]), 0, idx.shape[0] - 1).astype(np.int32)
        ci = np.clip(np.rint(cc + jitter[1, :n]), 0, idx.shape[1] - 1).astype(np.int32)
        out[r0:r0 + n] = idx[ri, ci]
    return out


def write_layers_cfg(path: Path) -> None:
    lines = ["class Layers", "{"]
    for name, _, rvmat in SURFACES:
        lines += [
            f"\tclass {name}",
            "\t{",
            '\t\ttexture = "";',
            f'\t\tmaterial = "{rvmat}";',
            "\t};",
        ]
    lines += ["};", "", "class Legend", "{", '\tpicture = "maps\\aotearoa\\source\\mapLegend.png";',
              "\tclass Colors", "\t{"]
    for name, rgb, _ in SURFACES:
        lines.append(f"\t\t{name}[] = {{{{{rgb[0]},{rgb[1]},{rgb[2]}}}}};")
    lines += ["\t};", "};", ""]
    path.write_text("\n".join(lines), newline="\r\n")


def write_legend(path: Path) -> None:
    from PIL import ImageDraw

    img = Image.new("RGB", (260, 28 * len(SURFACES) + 10), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for i, (name, rgb, _) in enumerate(SURFACES):
        y = 6 + i * 28
        d.rectangle([8, y, 40, y + 22], fill=rgb, outline=(0, 0, 0))
        d.text((50, y + 5), name, fill=(0, 0, 0))
    img.save(path)


def shaded_relief(h: np.ndarray, size: int) -> Image.Image:
    f = size / h.shape[0]
    hs = ndimage.zoom(h, f, order=1)
    cell = CELL / f
    gy, gx = np.gradient(hs, cell)
    az, alt = math.radians(315), math.radians(40)
    slope = np.arctan(np.hypot(gx, gy) * 2.0)
    aspect = np.arctan2(-gx, gy)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    shade = np.clip(shade, 0, 1)

    stops = np.array([0, 5, 40, 130, 260, 400, 560], dtype=np.float32)
    colours = np.array([
        [214, 200, 150], [110, 160, 80], [80, 140, 60], [150, 150, 80],
        [140, 110, 80], [170, 160, 150], [245, 245, 250]], dtype=np.float32)
    rgb = np.stack([np.interp(hs, stops, colours[:, i]) for i in range(3)], axis=-1)
    rgb = rgb * (0.35 + 0.75 * shade[..., None])
    sea = hs <= 0
    depth = np.clip(-hs / SEA_DEPTH, 0, 1)[..., None]
    sea_rgb = np.array([120, 185, 215]) * (1 - depth) + np.array([25, 60, 110]) * depth
    rgb = np.where(sea[..., None], sea_rgb, rgb)
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))


def write_asc(h: np.ndarray, path: Path) -> None:
    with path.open("w", newline="\n") as f:
        f.write(f"ncols {GRID}\nnrows {GRID}\nxllcorner {EASTING}\nyllcorner {NORTHING}\n"
                f"cellsize {CELL:g}\nNODATA_value -9999\n")
        for row in h:
            f.write(" ".join(f"{v:.2f}" for v in row))
            f.write("\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--asc", type=Path, nargs="?", const=SOURCE_DIR, default=None,
                    help="also write heightmap_4096.asc into this folder (default: source/)")
    ap.add_argument("--mask-size", type=int, default=4096,
                    help="surface mask size in pixels; Terrain Builder wants the satellite/mask size, e.g. 20480")
    args = ap.parse_args()

    mosaic, tx0, ty0 = build_mosaic()
    proj = projection(mosaic, tx0, ty0)
    scale = proj["real_m_per_game_m"]
    print(f"Land span {proj['span_km']:.0f} km after {ROTATION_DEG:g} deg rotation, "
          f"1 game m = {scale:.1f} real m")

    cached = CACHE_DIR / f"real_{GRID}_{ROTATION_DEG:g}_{MARGIN_M:g}.npy"
    if cached.exists():
        real = np.load(cached)
    else:
        real = sample_real_heights(mosaic, tx0, ty0, proj)
        np.save(cached, real)
    del mosaic
    h, land = build_heights(real)

    grid = towns_mod.Grid(SIZE_M, CELL, GRID)
    towns = towns_mod.load_towns()
    towns_mod.place_towns(towns, lambda lon, lat: lonlat_to_world(lon, lat, proj), land, grid)
    h = towns_mod.flatten_towns(h, land, towns, grid)
    h = np.where(land, limit_slope(np.where(land, h, 0.0), MAX_SLOPE_DEG), h)
    towns_mod.layout_towns(towns, h, land, grid, SEED + 3)
    for t in towns:
        moved = f", moved {t.moved_m:.0f} m inland" if t.moved_m > 1 else ""
        print(f"  {t.name}: {len(t.buildings)} buildings, radius {t.radius:.0f} m{moved}")
    print(f"Towns: {len(towns)}, buildings: {sum(len(t.buildings) for t in towns)}")

    slope = slope_degrees(h)
    land_slope = slope[land]
    print(f"Height range {h.min():.1f} .. {h.max():.1f} m, land {land.mean() * 100:.1f}% of map "
          f"({land.sum() * CELL * CELL / 1e6:.0f} km2)")
    print("Land slope percentiles (deg) 50/90/99/max: "
          + " / ".join(f"{np.percentile(land_slope, p):.1f}" for p in (50, 90, 99, 100)))

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    hmin, hmax = float(math.floor(h.min())), float(math.ceil(h.max()))
    png16 = np.rint((h - hmin) / (hmax - hmin) * 65535).astype(np.uint16)
    Image.fromarray(png16).save(SOURCE_DIR / "heightmap_4096.png", optimize=True)
    (SOURCE_DIR / "heightmap.json").write_text(json.dumps({
        "grid": GRID,
        "cell_size_m": CELL,
        "terrain_size_m": SIZE_M,
        "easting": EASTING,
        "northing": NORTHING,
        "png_black_m": hmin,
        "png_white_m": hmax,
        "sea_level_m": 0.0,
        "real_metres_per_game_metre": round(scale, 2),
        "source": "Terrarium elevation tiles, AWS Open Data (Mapzen/Nextzen), zoom %d" % ZOOM,
        "bounds_lonlat": [LON_W, LAT_S, LON_E, LAT_N],
        "rotation_deg_clockwise": -ROTATION_DEG,
        "centre_lonlat": [round(float(c), 4) for c in game_to_lonlat(np.array(0.0), np.array(0.0), proj)],
        "seed": SEED,
    }, indent=2) + "\n")

    idx = build_mask(h, land, proj)
    idx[towns_mod.town_mask(towns, grid) & land & (idx != 0)] = 1
    mask = idx if args.mask_size == GRID else upscale_mask(idx, args.mask_size)
    Image.fromarray(mask_to_rgb(mask)).save(SOURCE_DIR / f"mask_{args.mask_size}.png", optimize=True)
    write_layers_cfg(SOURCE_DIR / "layers.cfg")
    write_legend(SOURCE_DIR / "mapLegend.png")

    towns_mod.write_towns_csv(towns, SOURCE_DIR / "towns.csv", EASTING, NORTHING)
    towns_mod.write_names_hpp(towns, MAP_DIR / "config" / "names.hpp")
    towns_mod.write_terrain_builder_objects(towns, SOURCE_DIR / "objects" / "towns_tb.txt", EASTING, NORTHING)
    towns_mod.write_object_spawner(towns, SOURCE_DIR / "objects" / "towns_spawner.json")

    relief = shaded_relief(h, 2048)
    relief.save(PREVIEW_DIR / "relief_2048.png", optimize=True)
    towns_mod.draw_overview(relief, towns, SIZE_M).save(PREVIEW_DIR / "towns_2048.png", optimize=True)
    for name in DETAIL_TOWNS:
        town = next(t for t in towns if t.name == name)
        towns_mod.draw_town_detail(h, town, grid).save(
            PREVIEW_DIR / f"town_{town.class_name.lower()}.png", optimize=True)
    Image.fromarray(mask_to_rgb(idx)).resize((2048, 2048), Image.NEAREST).save(
        PREVIEW_DIR / "mask_2048.png", optimize=True)
    slope_img = np.clip(slope / 50.0 * 255, 0, 255).astype(np.uint8)
    Image.fromarray(slope_img).resize((2048, 2048), Image.BILINEAR).save(PREVIEW_DIR / "slope_2048.png")

    if args.asc:
        args.asc.mkdir(parents=True, exist_ok=True)
        write_asc(h, args.asc / "heightmap_4096.asc")
        print(f"Wrote {args.asc / 'heightmap_4096.asc'}")
    print("Done")


if __name__ == "__main__":
    main()
