"""Lakes and rivers for the Aotearoa terrain.

Lakes come from the real elevation data, where lake surfaces are stored perfectly flat. Each one
is dug into the game terrain as a basin with a rim, ready for a water surface in Terrain Builder.
River courses are traced on the real elevation (the game terrain's generated ridges would break them
into short streams) and cut as shallow gravel beds that always run downhill; near the coast they
drop below sea level, where DayZ's sea fills them.
"""

from __future__ import annotations

import json
import heapq
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import ndimage
from skimage import draw, measure, morphology

LAKE_FLAT_TOL_M = 0.6
LAKE_MIN_CELLS = 30
LAKE_MAX_DEPTH_M = 10.0
RIVER_GRID = 1024
RIVER_MIN_CATCHMENT_KM2 = 0.25  # game km2 draining to a point before it shows as a riverbed
RIVER_DEPTH_M = 1.4
MAX_CUT_M = 8.0

# Known lakes, matched to detected basins within 20 km (real).
LAKE_NAMES = [
    ("Taupō", -38.80, 175.90), ("Rotorua", -38.08, 176.27), ("Tarawera", -38.20, 176.43),
    ("Rotoiti", -38.04, 176.43), ("Wakatipu", -45.05, 168.55), ("Wānaka", -44.47, 169.12),
    ("Hāwea", -44.50, 169.27), ("Te Anau", -45.25, 167.75), ("Manapōuri", -45.52, 167.52),
    ("Pukaki", -44.07, 170.16), ("Tekapo", -43.92, 170.52), ("Ōhau", -44.22, 169.85),
    ("Benmore", -44.39, 170.23), ("Aviemore", -44.62, 170.30), ("Brunner", -42.62, 171.45),
    ("Coleridge", -43.36, 171.53), ("Hauroko", -45.95, 167.33), ("Waikaremoana", -38.77, 177.10),
    ("Waikare", -37.43, 175.20),
]


@dataclass
class Lake:
    name: str
    level: float
    cells: np.ndarray  # boolean mask over the grid
    outline: list[list[tuple[float, float]]] = field(default_factory=list)  # one ring per shore
    area_m2: float = 0.0
    centre: tuple[float, float] = (0.0, 0.0)


def detect_lakes(real: np.ndarray, land: np.ndarray) -> list[tuple[np.ndarray, float]]:
    spread = ndimage.maximum_filter(real, 3) - ndimage.minimum_filter(real, 3)
    flat = (spread < LAKE_FLAT_TOL_M) & (real > 2.0) & land
    flat = ndimage.binary_closing(flat, iterations=2) & land
    lab, n = ndimage.label(flat)
    sizes = np.bincount(lab.ravel())
    found = []
    for k in range(1, n + 1):
        if sizes[k] < LAKE_MIN_CELLS:
            continue
        m = lab == k
        level = float(np.median(real[m]))
        # A flat valley floor is not a lake: real lake surfaces barely vary at all.
        if np.percentile(np.abs(real[m] - level), 80) > 0.3:
            continue
        found.append((m, level))
    return found


def merge_lakes(found, cell: float, size_m: float, to_lonlat) -> list[tuple[str, np.ndarray]]:
    """Group detected basins by the lake they belong to; narrows often split one lake in the data."""
    groups: dict[str, np.ndarray] = {}
    unnamed = []
    for m, _ in found:
        rows, cols = np.nonzero(m)
        cx, cy = (cols.mean() + 0.5) * cell, size_m - (rows.mean() + 0.5) * cell
        lon, lat = to_lonlat(np.array([cx]), np.array([cy]))
        name = name_lake(float(lon[0]), float(lat[0]))
        if not name:
            unnamed.append(("", m))
        elif name in groups:
            groups[name] = groups[name] | m
        else:
            groups[name] = m
    merged = []
    for name, m in groups.items():
        lab, n = ndimage.label(m)
        if n > 1:
            # Join the pieces across the narrows with a channel at the same water level.
            bridged = ndimage.binary_closing(m, iterations=6)
            lab2, _ = ndimage.label(bridged)
            m = bridged & np.isin(lab2, np.unique(lab2[m]))
        merged.append((name, m))
    return merged + unnamed


def carve_lakes(h: np.ndarray, found, cell: float, size_m: float, to_lonlat) -> tuple[np.ndarray, list[Lake]]:
    h = h.copy()
    lakes = []
    for name, m in merge_lakes(found, cell, size_m, to_lonlat):
        ring = ndimage.binary_dilation(m, iterations=8) & ~ndimage.binary_dilation(m, iterations=2)
        level = float(np.percentile(h[ring], 25))
        inside = ndimage.distance_transform_edt(m) * cell
        depth = np.minimum(LAKE_MAX_DEPTH_M, 1.0 + inside * 0.12)
        h = np.where(m, level - depth, h)
        rim = ndimage.binary_dilation(m, iterations=4) & ~m
        h = np.where(rim, np.maximum(h, level + 0.6), h)

        rows, cols = np.nonzero(m)
        cx, cy = (cols.mean() + 0.5) * cell, size_m - (rows.mean() + 0.5) * cell
        outline = []
        for contour in measure.find_contours(np.pad(m, 1).astype(float), 0.5):
            if len(contour) < 8:
                continue
            contour = measure.approximate_polygon(contour, tolerance=1.0)
            outline.append([((c - 0.5) * cell, size_m - (r - 0.5) * cell) for r, c in contour])
        lakes.append(Lake(name, level, m, outline, float(m.sum() * cell * cell), (float(cx), float(cy))))
    return h, lakes


def name_lake(lon: float, lat: float) -> str:
    best, best_d = "", 20.0
    for name, la, lo in LAKE_NAMES:
        d = math.hypot((lo - lon) * 84.0, (la - lat) * 110.6)
        if d < best_d:
            best, best_d = name, d
    return best


def flow_accumulation(h: np.ndarray, sea: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Priority-flood routing from the sea inwards, so every land cell drains to the coast.

    Returns (accumulated cells, downstream flat index, visit order from the coast inwards).
    """
    n0, n1 = h.shape
    hf = h.ravel().astype(np.float64).tolist()
    seaf = sea.ravel()
    visited = seaf.copy()
    visited[0:n1] = True
    visited[-n1:] = True
    visited[::n1] = True
    visited[n1 - 1::n1] = True
    down = np.arange(n0 * n1)
    level = list(hf)
    heap = []
    edge = visited & ~ndimage.binary_erosion(visited.reshape(n0, n1), border_value=1).ravel()
    for i in np.flatnonzero(edge).tolist():
        heapq.heappush(heap, (hf[i], i))
    vis = visited.tolist()
    dl = down.tolist()
    order = []
    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    while heap:
        z, c = heapq.heappop(heap)
        r, q = divmod(c, n1)
        for dr, dq in offsets:
            rr, qq = r + dr, q + dq
            if 0 <= rr < n0 and 0 <= qq < n1:
                j = rr * n1 + qq
                if not vis[j]:
                    vis[j] = True
                    dl[j] = c
                    zj = max(hf[j], z + 1e-4)
                    level[j] = zj
                    order.append(j)
                    heapq.heappush(heap, (zj, j))

    al = [1.0] * (n0 * n1)
    for i in reversed(order):
        al[dl[i]] += al[i]
    acc = np.array(al).reshape(n0, n1)
    acc[sea] = 0
    return acc, np.array(dl).reshape(n0, n1), np.array(order, dtype=np.int64)


def carve_rivers(h: np.ndarray, real: np.ndarray, land: np.ndarray, lake_mask: np.ndarray,
                 cell: float, keep_out: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Trace rivers on the real elevation and cut them into the game terrain.

    The game terrain's generated ridges break drainage into short catchments, so river courses come
    from the real data. Beds always run downhill: each cell is no higher than the bed upstream of
    it, cutting at most MAX_CUT_M into the land. Returns the carved heightmap and a 0..1 riverbed
    weight on the grid.
    """
    n = h.shape[0]
    f = n // RIVER_GRID
    rs = real.reshape(RIVER_GRID, f, RIVER_GRID, f).mean(axis=(1, 3))
    hs = h.reshape(RIVER_GRID, f, RIVER_GRID, f).min(axis=(1, 3))
    sea = ~(land.reshape(RIVER_GRID, f, RIVER_GRID, f).mean(axis=(1, 3)) > 0.5)
    acc, down, order = flow_accumulation(rs, sea)
    catchment = acc * (cell * f / 1000.0) ** 2
    channel = (catchment >= RIVER_MIN_CATCHMENT_KM2) & ~sea
    channel = morphology.remove_small_objects(channel, max_size=12, connectivity=2)
    strength = np.where(channel, np.log10(catchment / RIVER_MIN_CATCHMENT_KM2 + 1.0), 0.0)

    bed = np.full(hs.shape, np.inf)
    inflow = np.full(hs.size, np.inf)
    flat_down = down.ravel()
    order = order[::-1]
    cflat = channel.ravel()
    hflat = hs.ravel()
    sflat = strength.ravel()
    bflat = bed.ravel()
    for i in order[cflat[order]].tolist():
        want = hflat[i] - RIVER_DEPTH_M * (1.0 + 0.6 * sflat[i])
        b = max(min(inflow[i], want), hflat[i] - MAX_CUT_M)
        if hflat[i] < 2.5:
            b = min(b, -0.6)
        bflat[i] = b
        j = flat_down[i]
        if j != i:
            inflow[j] = min(inflow[j], b)

    _, (ri, ci) = ndimage.distance_transform_edt(~channel, return_indices=True)
    bed_near = ndimage.gaussian_filter(bflat.reshape(hs.shape)[ri, ci], 2.5)
    strength_near = strength[ri, ci]
    bed_field = ndimage.zoom(bed_near, f, order=1)
    strength_field = ndimage.zoom(strength_near, f, order=1)
    centre = np.zeros(h.shape, dtype=bool)
    for i in np.flatnonzero(channel).tolist():
        j = int(flat_down[i])
        r0, c0 = divmod(i, RIVER_GRID)
        r1, c1 = divmod(j, RIVER_GRID)
        lr, lc = draw.line(r0 * f + f // 2, c0 * f + f // 2, r1 * f + f // 2, c1 * f + f // 2)
        centre[np.clip(lr, 0, n - 1), np.clip(lc, 0, n - 1)] = True
    dist, (fr, fc) = ndimage.distance_transform_edt(~centre, return_indices=True)
    dist *= cell
    bed_full = np.maximum(bed_field[fr, fc], h[fr, fc] - MAX_CUT_M)
    half_width = 5.0 + 12.0 * strength_field[fr, fc]
    cut = np.maximum(h - bed_full, 0.0)
    bank = 5.0 + 1.6 * cut
    w = np.clip((half_width + bank - dist) / bank, 0.0, 1.0)
    w = ndimage.gaussian_filter(w * w * (3 - 2 * w), 2.0)
    w = np.where(land & ~lake_mask, w, 0.0)
    if keep_out is not None:
        fade = ndimage.distance_transform_edt(~keep_out) * cell
        w = w * np.clip(fade / 60.0, 0.0, 1.0)
    inner = np.clip((half_width - dist) / 2.0 + 1.0, 0.0, 1.0)
    target = np.where(inner > 0, np.minimum(h, bed_full), h)
    carved = h * (1 - w) + target * w
    carved = np.where(w > 0.01, carved * (1 - w) + ndimage.gaussian_filter(carved, 1.5) * w, carved)
    return carved.astype(np.float32), np.clip((w - 0.5) * 2.5, 0.0, 1.0).astype(np.float32)


def write_lakes(lakes: list[Lake], path: Path, easting: float, northing: float) -> None:
    data = [{
        "name": lk.name or "unnamed",
        "surface_m": round(lk.level, 2),
        "area_m2": round(lk.area_m2),
        "centre": [round(lk.centre[0], 1), round(lk.centre[1], 1)],
        "centre_tb": [round(lk.centre[0] + easting, 1), round(lk.centre[1] + northing, 1)],
        "outlines": [[[round(x, 1), round(y, 1)] for x, y in ring] for ring in lk.outline],
    } for lk in lakes]
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
