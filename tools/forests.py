"""Trees and bushes for the Aotearoa terrain.

Native bush (the "bush" surface layer) gets an irregular mix of broadleaf trees with an
understorey; pine (the "pine" layer) is planted in straight rows like New Zealand's radiata
plantations. Forest edges get a fringe of bushes. Nothing is placed on roads, in towns or
sites, in water, or on slopes too steep to stand on.

Writes source/objects/forest_tb.txt, a Terrain Builder text import. The model names are
vanilla DayZ trees (P:\\DZ\\plants\\tree and P:\\DZ\\plants\\bush); check them against your P:
drive and edit the lists below if a name differs.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from scipy import ndimage

# Native bush leans on beech (standing in for Nothofagus) with cycads from the Takistan DLC as tree
# ferns; plantations mix Takistan's Brutian pine (the nearest to radiata) with Scots pine.
BUSH_TREES = ["t_fagussylvatica_2f", "t_fagussylvatica_3f", "t_fagussylvatica_2s", "t_betulapendula_2w",
              "t_quercusrobur_3s", "t_carpinus_2s"]
UNDERSTOREY = ["b_corylusavellana_2s", "b_cycas_2s", "b_crataeguslaevigata_2s", "b_cycas_2s"]
PINE_TREES = ["t_pinusbrutia_2s", "t_pinusbrutia_2sb", "t_pinussylvestris_3f", "t_pinussylvestris_2s"]
EDGE_BUSHES = ["b_corylusavellana_1f", "b_prunusspinosa_2s", "b_sambucusnigra_1s"]

BUSH_SPACING = 10.0
PINE_SPACING = 7.5
EDGE_WIDTH_M = 12.0
MAX_TREE_SLOPE_DEG = 38.0


def build_forests(idx, h, land, exclude, grid, surface_index: dict, seed: int) -> list[tuple]:
    rng = np.random.default_rng(seed)
    gy, gx = np.gradient(h, grid.cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    allowed = land & ~exclude & (slope < MAX_TREE_SLOPE_DEG)
    bush = (idx == surface_index["bush"]) & allowed
    pine = (idx == surface_index["pine"]) & allowed
    forest = bush | pine
    edge = forest & (ndimage.distance_transform_edt(forest) * grid.cell < EDGE_WIDTH_M)

    out: list[tuple] = []

    def at(mask, x, y):
        r, c = grid.to_cell(x, y)
        r = np.clip(np.rint(r).astype(int), 0, grid.n - 1)
        c = np.clip(np.rint(c).astype(int), 0, grid.n - 1)
        return mask[r, c]

    # Native bush: jittered grid, so trees never stack but never line up either.
    xs = np.arange(BUSH_SPACING / 2, grid.size_m, BUSH_SPACING)
    X, Y = np.meshgrid(xs, xs)
    X = X + rng.uniform(-0.45, 0.45, X.shape) * BUSH_SPACING
    Y = Y + rng.uniform(-0.45, 0.45, Y.shape) * BUSH_SPACING
    keep = at(bush, X, Y) & (rng.random(X.shape) < 0.85)
    for x, y in zip(X[keep], Y[keep]):
        on_edge = bool(at(edge, np.array([x]), np.array([y]))[0])
        if on_edge and rng.random() < 0.6:
            out.append((EDGE_BUSHES[rng.integers(len(EDGE_BUSHES))], x, y, rng.uniform(0, 360), rng.uniform(0.8, 1.2)))
        else:
            out.append((BUSH_TREES[rng.integers(len(BUSH_TREES))], x, y, rng.uniform(0, 360), rng.uniform(0.75, 1.25)))
        if rng.random() < 0.35:
            ox, oy = rng.uniform(-3.5, 3.5, 2)
            out.append((UNDERSTOREY[rng.integers(len(UNDERSTOREY))], x + ox, y + oy, rng.uniform(0, 360),
                        rng.uniform(0.7, 1.1)))

    # Pine plantations: rows on a lattice turned per block of land, with a few gaps.
    lab, n = ndimage.label(pine)
    if n:
        turn = rng.uniform(0, 90, n + 1)
        xs = np.arange(0.0, grid.size_m, PINE_SPACING * 0.6)
        X, Y = np.meshgrid(xs, xs)
        r, c = grid.to_cell(X, Y)
        r = np.clip(np.rint(r).astype(int), 0, grid.n - 1)
        c = np.clip(np.rint(c).astype(int), 0, grid.n - 1)
        stand = lab[r, c]
        a = np.radians(turn[stand])
        # Snap a fine sample onto each stand's turned lattice; duplicates collapse to one tree.
        iu = np.round((X * np.cos(a) - Y * np.sin(a)) / PINE_SPACING).astype(np.int64)
        iv = np.round((X * np.sin(a) + Y * np.cos(a)) / PINE_SPACING).astype(np.int64)
        sel = stand > 0
        keys = np.unique(np.stack([stand[sel], iu[sel], iv[sel]], -1), axis=0)
        k_stand, k_u, k_v = keys.T
        a = np.radians(turn[k_stand])
        u, v = k_u * PINE_SPACING, k_v * PINE_SPACING
        PX = u * np.cos(a) + v * np.sin(a) + rng.normal(0, 0.3, len(keys))
        PY = -u * np.sin(a) + v * np.cos(a) + rng.normal(0, 0.3, len(keys))
        keep = at(pine, PX, PY) & (rng.random(len(keys)) < 0.93)
        for x, y in zip(PX[keep], PY[keep]):
            out.append((PINE_TREES[rng.integers(len(PINE_TREES))], x, y, rng.uniform(0, 360), rng.uniform(0.85, 1.15)))
    return out


def write_forest(trees: list[tuple], path: Path, easting: float, northing: float) -> None:
    """Terrain Builder text import: "template";x;y;yaw;pitch;roll;scale;z offset;"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="\r\n") as f:
        for name, x, y, yaw, scale in trees:
            f.write(f'"{name}";{x + easting:.2f};{y + northing:.2f};{yaw:.1f};0;0;{scale:.2f};0;\n')


def density_preview(trees: list[tuple], size_m: float, px: int = 1024) -> np.ndarray:
    img = np.zeros((px, px), dtype=np.float32)
    if not trees:
        return img.astype(np.uint8)
    xy = np.array([(t[1], t[2]) for t in trees])
    c = np.clip((xy[:, 0] / size_m * px).astype(int), 0, px - 1)
    r = np.clip(((size_m - xy[:, 1]) / size_m * px).astype(int), 0, px - 1)
    np.add.at(img, (r, c), 1.0)
    return np.clip(img / max(1.0, np.percentile(img[img > 0], 95)) * 255, 0, 255).astype(np.uint8)
