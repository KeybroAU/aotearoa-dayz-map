"""World detail objects for the Aotearoa terrain.

Bridges over every river crossing, water surfaces for the lakes, wooden power lines beside the
highways, guardrails on high fills and bridge approaches, fences round the farms, hedgerows along
the highways through farmland, and rocks on cliffs and riverbeds.

Each group is written to its own Terrain Builder text file in source/objects/ so it can be
imported (or left out) as a layer. The models are in OBJECTS below; check them against your
P: drive like the town buildings.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from scipy import ndimage

import forests as forests_mod
import towns as towns_mod
from roads import densify

# Model names, with the length one model covers where it is laid end to end.
OBJECTS = {
    "bridge": ("Land_Bridge_Wood_25", 25.0),
    "water": ("aotearoa_water_50", 50.0),  # square water plane, top surface at the model origin
    "power_pole": ("Land_Power_Pole_Wood1", 40.0),
    "guardrail": ("Land_Wall_Railing_4", 4.0),
    "fence": ("Land_Wall_Fen1_5", 5.0),
    "rocks": ["r2_boulder1", "r2_boulder2", "r2_rock1"],
    "stones": ["r2_stone1", "r2_stone2"],
}

POWER_OFFSET_M = 14.0
GUARDRAIL_OFFSET_M = 5.0
GUARDRAIL_DROP_M = 3.0
HEDGE_OFFSET_M = 18.0
HEDGE_SPACING_M = 5.0
HEDGE_RUN_M = 70.0
HEDGE_GAP_M = 25.0
ROCK_SLOPE_DEG = 34.0
ROCK_SPACING_M = 18.0
STONE_SPACING_M = 14.0
FARM_FENCE = (70.0, 60.0)


def template(cls: str) -> str:
    return cls[5:].lower() if cls.startswith("Land_") else cls.lower()


def _cells(grid, x, y):
    r, c = grid.to_cell(np.asarray(x), np.asarray(y))
    return (np.clip(np.rint(r).astype(int), 0, grid.n - 1), np.clip(np.rint(c).astype(int), 0, grid.n - 1))


def _side_points(points: np.ndarray, step: float, offset: float):
    """Points every step along a line, pushed offset to the left (negative offset: right)."""
    dense = densify(points, step)
    if len(dense) < 2:
        return dense, np.zeros(len(dense))
    d = np.gradient(dense, axis=0)
    n = np.hypot(d[:, 0], d[:, 1])[:, None] + 1e-9
    d /= n
    left = np.stack([-d[:, 1], d[:, 0]], -1)
    heading = np.degrees(np.arctan2(d[:, 0], d[:, 1])) % 360
    return dense + left * offset, heading


def bridges(roads, h, grid) -> list[tuple]:
    """Deck pieces laid across each crossing, lifted to the level of the road on the banks."""
    cls, length = OBJECTS["bridge"]
    out = []
    for road in roads:
        for x, y, hd, span in road.bridges:
            ux, uy = math.sin(math.radians(hd)), math.cos(math.radians(hd))
            total = span + 2 * grid.cell
            n = max(1, math.ceil(total / length))
            ends = grid.sample(h, [x - ux * (total / 2 + 4), x + ux * (total / 2 + 4)],
                               [y - uy * (total / 2 + 4), y + uy * (total / 2 + 4)])
            deck = float(np.mean(ends))
            for k in range(n):
                along = (k - (n - 1) / 2) * length
                px, py = x + ux * along, y + uy * along
                ground = float(grid.sample(h, px, py)[0])
                out.append((template(cls), px, py, hd, 1.0, max(0.0, deck - ground)))
    return out


def water_surfaces(lakes, grid) -> list[tuple]:
    """Water planes tiled over each lake, all at the lake's surface level."""
    cls, size = OBJECTS["water"]
    out = []
    for lk in lakes:
        rows, cols = np.nonzero(lk.cells)
        if len(rows) == 0:
            continue
        x0, x1 = cols.min() * grid.cell, (cols.max() + 1) * grid.cell
        y0, y1 = grid.size_m - (rows.max() + 1) * grid.cell, grid.size_m - rows.min() * grid.cell
        # Tiles overlap the shore by half a tile so no gaps show; the banks hide the overhang.
        grown = ndimage.binary_dilation(lk.cells, iterations=max(1, int(size / 2 / grid.cell)))
        for px in np.arange(x0 + size / 2, x1 + size / 2, size):
            for py in np.arange(y0 + size / 2, y1 + size / 2, size):
                r, c = _cells(grid, px, py)
                if lk.cells[r, c] or (grown[r, c] and _tile_touches(lk.cells, grid, px, py, size)):
                    out.append((template(cls), px, py, 0.0, 1.0, lk.level))
    return out


def _tile_touches(cells, grid, x, y, size) -> bool:
    win, wx, wy = grid.window(x, y, size / 2)
    inside = (np.abs(wx - x) <= size / 2) & (np.abs(wy - y) <= size / 2)
    return bool(cells[win][inside].any())


def power_lines(roads, towns, sites, blocked, grid) -> list[tuple]:
    cls, spacing = OBJECTS["power_pole"]
    out = []
    for road in roads:
        if road.kind != "highway":
            continue
        pts, hd = _side_points(np.array(road.points), spacing, POWER_OFFSET_M)
        r, c = _cells(grid, pts[:, 0], pts[:, 1])
        ok = ~blocked[r, c]
        for (px, py), a, good in zip(pts, hd, ok):
            if good and not _near_town(towns, px, py):
                out.append((template(cls), px, py, a, 1.0, 0.0))
    return out


def _near_town(towns, x, y, extra=20.0) -> bool:
    return any(math.hypot(x - t.x, y - t.y) < t.radius + extra for t in towns)


def guardrails(roads, towns, h, land, grid) -> list[tuple]:
    """Rails on the side of a highway where the ground falls away, and on bridge approaches."""
    cls, length = OBJECTS["guardrail"]
    out = []
    for road in roads:
        if road.kind != "highway":
            continue
        pts = np.array(road.points)
        centre = densify(pts, length)
        if len(centre) < 2:
            continue
        zc = grid.sample(h, centre[:, 0], centre[:, 1])
        near_bridge = np.zeros(len(centre), dtype=bool)
        for bx, by, _, span in road.bridges:
            near_bridge |= np.hypot(centre[:, 0] - bx, centre[:, 1] - by) < span / 2 + 25.0
        for side in (1.0, -1.0):
            rail, hd = _side_points(pts, length, side * GUARDRAIL_OFFSET_M)
            probe, _ = _side_points(pts, length, side * (GUARDRAIL_OFFSET_M + 6.0))
            n = min(len(rail), len(probe), len(centre))
            drop = zc[:n] - grid.sample(h, probe[:n, 0], probe[:n, 1])
            r, c = _cells(grid, rail[:n, 0], rail[:n, 1])
            want = ((drop > GUARDRAIL_DROP_M) | near_bridge[:n]) & land[r, c]
            # Rails come in runs; drop single pieces left on their own.
            want = ndimage.binary_opening(want, structure=np.ones(3, dtype=bool))
            for i in np.flatnonzero(want):
                if not _near_town(towns, rail[i, 0], rail[i, 1], 0.0):
                    out.append((template(cls), rail[i, 0], rail[i, 1], hd[i], 1.0, 0.0))
    return out


def farm_fences(sites) -> list[tuple]:
    cls, length = OBJECTS["fence"]
    out = []
    for s in sites:
        if s.kind != "farm":
            continue
        a, b = FARM_FENCE
        ux, uy = math.sin(math.radians(s.heading)), math.cos(math.radians(s.heading))
        vx, vy = uy, -ux
        corners = [(-a / 2, -b / 2), (a / 2, -b / 2), (a / 2, b / 2), (-a / 2, b / 2)]
        for i, (p, q) in enumerate(zip(corners, corners[1:] + corners[:1])):
            side = math.hypot(q[0] - p[0], q[1] - p[1])
            n = int(side // length)
            for k in range(n):
                t = (k + 0.5) / n
                al, ac = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
                # A gate gap in the middle of the first side.
                if i == 0 and abs(al) < length:
                    continue
                x, y = s.x + al * ux + ac * vx, s.y + al * uy + ac * vy
                yaw = (s.heading + (0.0 if i % 2 == 0 else 90.0)) % 360
                out.append((template(cls), x, y, yaw, 1.0, 0.0))
    return out


def hedgerows(roads, idx, blocked, towns, grid, surface_index, rng) -> list[tuple]:
    farmland = (idx == surface_index["pasture"]) | (idx == surface_index["farmland"])
    out = []
    period = HEDGE_RUN_M + HEDGE_GAP_M
    for road in roads:
        if road.kind != "highway":
            continue
        for side in (1.0, -1.0):
            pts, hd = _side_points(np.array(road.points), HEDGE_SPACING_M, side * HEDGE_OFFSET_M)
            along = np.arange(len(pts)) * HEDGE_SPACING_M + rng.uniform(0, period)
            r, c = _cells(grid, pts[:, 0], pts[:, 1])
            ok = farmland[r, c] & ~blocked[r, c] & (np.remainder(along, period) < HEDGE_RUN_M)
            for (px, py), good in zip(pts, ok):
                if good and not _near_town(towns, px, py):
                    jx, jy = rng.uniform(-1.0, 1.0, 2)
                    name = forests_mod.EDGE_BUSHES[rng.integers(len(forests_mod.EDGE_BUSHES))]
                    out.append((name, px + jx, py + jy, rng.uniform(0, 360), rng.uniform(0.8, 1.2), 0.0))
    return out


def rocks(h, land, river_mask, blocked, grid, rng) -> list[tuple]:
    gy, gx = np.gradient(h, grid.cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    out = []
    for mask, spacing, names, chance, scale in (
            (land & (slope > ROCK_SLOPE_DEG) & ~blocked, ROCK_SPACING_M, OBJECTS["rocks"], 0.55, (0.6, 1.6)),
            (river_mask & ~blocked, STONE_SPACING_M, OBJECTS["stones"], 0.3, (0.5, 1.2))):
        xs = np.arange(spacing / 2, grid.size_m, spacing)
        X, Y = np.meshgrid(xs, xs)
        X = X + rng.uniform(-0.45, 0.45, X.shape) * spacing
        Y = Y + rng.uniform(-0.45, 0.45, Y.shape) * spacing
        r, c = _cells(grid, X, Y)
        keep = mask[r, c] & (rng.random(X.shape) < chance)
        for x, y in zip(X[keep], Y[keep]):
            out.append((names[rng.integers(len(names))], x, y, rng.uniform(0, 360), rng.uniform(*scale), 0.0))
    return out


def build_details(h, idx, land, lake_mask, river_mask, road_footprint, towns, roads, sites, lakes, grid,
                  surface_index, seed) -> dict[str, list[tuple]]:
    rng = np.random.default_rng(seed)
    site_mask = np.zeros(land.shape, dtype=bool)
    for s in sites:
        win, wx, wy = grid.window(s.x, s.y, s.radius + 20.0)
        site_mask[win] |= np.hypot(wx - s.x, wy - s.y) <= s.radius + 20.0
    roads_zone = ndimage.binary_dilation(road_footprint > 0, iterations=1)
    town_zone = towns_mod.town_mask(towns, grid)
    blocked = ~land | lake_mask | river_mask | roads_zone | town_zone | site_mask
    return {
        "bridges": bridges(roads, h, grid),
        "lakes": water_surfaces(lakes, grid),
        "powerlines": power_lines(roads, towns, sites, blocked, grid),
        "guardrails": guardrails(roads, towns, h, land, grid),
        "fences": farm_fences(sites),
        "hedgerows": hedgerows(roads, idx, blocked, towns, grid, surface_index, rng),
        "rocks": rocks(h, land, river_mask, roads_zone | town_zone | site_mask | lake_mask, grid, rng),
    }


def write_details(groups: dict[str, list[tuple]], out_dir: Path, easting: float, northing: float) -> None:
    """Terrain Builder text import, one file per group: "template";x;y;yaw;pitch;roll;scale;z offset;

    Lake planes carry their absolute water level in the last field; import that file with
    absolute heights (or subtract the ground) in Terrain Builder.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, objs in groups.items():
        with (out_dir / f"{name}_tb.txt").open("w", newline="\r\n") as f:
            for tpl, x, y, yaw, scale, z in objs:
                f.write(f'"{tpl}";{x + easting:.2f};{y + northing:.2f};{yaw:.1f};0;0;{scale:.2f};{z:.2f};\n')
