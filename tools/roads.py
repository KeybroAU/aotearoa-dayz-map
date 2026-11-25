"""Roads for the Aotearoa terrain.

State highways are least-cost routes between towns along the real highway links. The cost
favours gentle grades, avoids lakes and the sea, makes river crossings expensive, follows town
streets rather than cutting through blocks, and reuses roads already built so routes share
corridors. Town streets come from the block grid in towns.py. Highways outside towns are graded
into the terrain as a smooth road bed.

Writes source/roads/roads.shp with RoadsLib.cfg for Terrain Builder, source/roads.json (used by
the satellite and forest builders) and source/roads_4096.png (road footprint).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from skimage import graph, measure

import towns as towns_mod

# Each chain is routed leg by leg, in this order, so later highways join earlier ones.
HIGHWAYS = [
    ("SH1", ["Kaitāia", "Paihia", "Whangārei", "Auckland", "Hamilton", "Taupō", "Waiouru Army Camp",
             "Palmerston North", "Wellington"]),
    ("SH1", ["Picton", "Blenheim", "Kaikōura", "Christchurch", "Burnham Military Camp", "Ashburton",
             "Timaru", "Ōamaru", "Dunedin", "Gore", "Invercargill"]),
    ("SH2", ["Auckland", "Thames", "Tauranga", "Whakatāne", "Gisborne", "Napier", "Hastings", "Masterton",
             "Wellington"]),
    ("SH3", ["Hamilton", "New Plymouth", "Whanganui", "RNZAF Base Ōhakea", "Palmerston North"]),
    ("SH4", ["Hamilton", "Taumarunui", "Whanganui"]),
    ("SH5", ["Hamilton", "Rotorua", "Taupō", "Napier"]),
    ("SH30", ["Rotorua", "Whakatāne"]),
    ("SH36", ["Rotorua", "Tauranga"]),
    ("SH6", ["Blenheim", "Nelson", "Westport", "Greymouth", "Hokitika", "Franz Josef", "Wānaka", "Queenstown",
             "Invercargill"]),
    ("SH7", ["Greymouth", "Hanmer Springs", "Christchurch"]),
    ("SH73", ["Christchurch", "Greymouth"]),
    ("SH8", ["Timaru", "Twizel", "Wānaka"]),
    ("SH83", ["Ōamaru", "Twizel"]),
    ("SH8", ["Dunedin", "Queenstown"]),
    ("SH94", ["Gore", "Te Anau", "Queenstown"]),
]

KINDS = {
    "highway": {"id": 1, "width": 8.0},
    "street": {"id": 2, "width": 6.0},
    "track": {"id": 3, "width": 4.0},
}
ACCESS_SEARCH_M = 1500.0
WINDOW_MARGIN_M = 2500.0
COMFORT_GRADE = 0.08
RIVER_CROSSING_COST = 60.0
REUSE_FACTOR = 0.35
GRADE_SIGMA_M = 45.0
BED_BLEND_M = 10.0


@dataclass
class Road:
    kind: str
    ref: str
    points: list[tuple[float, float]]
    bridges: list[tuple[float, float, float]] = field(default_factory=list)  # x, y, heading deg


def town_streets(t: towns_mod.Town) -> list[list[tuple[float, float]]]:
    """Street centrelines around the town's laid-out blocks, merged into runs."""
    if not t.blocks:
        return []
    ang = math.radians(t.grid_angle)
    ca, sa = math.cos(ang), math.sin(ang)

    def to_world(u, v):
        return (t.x + u * ca + v * sa, t.y - u * sa + v * ca)

    have = set(t.blocks)
    lines = []
    for axis in (0, 1):
        ks = {b[axis] for b in have} | {b[axis] + 1 for b in have}
        for k in sorted(ks):
            # Line at index k along this axis borders blocks k-1 and k.
            js = sorted({b[1 - axis] for b in have if b[axis] in (k - 1, k)})
            run = []
            for j in js + [None]:
                if run and (j is None or j != run[-1] + 1):
                    a, b = run[0] * towns_mod.PITCH, (run[-1] + 1) * towns_mod.PITCH
                    p = k * towns_mod.PITCH
                    ends = [(p, a), (p, b)] if axis == 0 else [(a, p), (b, p)]
                    lines.append([to_world(u, v) for u, v in ends])
                    run = []
                if j is not None:
                    run.append(j)
    return lines


def street_extent(t: towns_mod.Town) -> float:
    if not t.blocks:
        return t.radius * 0.5
    return max(math.hypot(abs(i + 0.5) + 0.5, abs(j + 0.5) + 0.5) for i, j in t.blocks) * towns_mod.PITCH


def base_cost(h, land, lake_mask, river_mask, towns, grid) -> np.ndarray:
    gy, gx = np.gradient(h, grid.cell)
    grade = np.hypot(gx, gy)
    cost = 1.0 + 0.5 * (grade / COMFORT_GRADE) ** 2
    cost = np.minimum(cost, 400.0)
    cost[river_mask] += RIVER_CROSSING_COST
    cost[~land | lake_mask] = np.inf
    for t in towns:
        win, wx, wy = grid.window(t.x, t.y, t.radius * 1.1)
        ang = math.radians(t.grid_angle)
        dx, dy = wx - t.x, wy - t.y
        u = dx * math.cos(ang) - dy * math.sin(ang)
        v = dx * math.sin(ang) + dy * math.cos(ang)
        on_street = (np.minimum(np.abs(np.remainder(u + towns_mod.PITCH / 2, towns_mod.PITCH) - towns_mod.PITCH / 2),
                                np.abs(np.remainder(v + towns_mod.PITCH / 2, towns_mod.PITCH) - towns_mod.PITCH / 2))
                     <= towns_mod.STREET / 2)
        inside = np.hypot(dx, dy) <= street_extent(t)
        sub = cost[win]
        sub = np.where(inside & np.isfinite(sub), np.where(on_street, 0.4, 300.0), sub)
        cost[win] = sub
    return cost


def route(cost: np.ndarray, a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]] | None:
    n = cost.shape[0]
    margin = int(WINDOW_MARGIN_M / 5.0)
    for pad in (margin, margin * 3, n):
        r0, r1 = max(0, min(a[0], b[0]) - pad), min(n, max(a[0], b[0]) + pad + 1)
        c0, c1 = max(0, min(a[1], b[1]) - pad), min(n, max(a[1], b[1]) + pad + 1)
        sub = cost[r0:r1, c0:c1]
        mcp = graph.MCP_Geometric(sub, fully_connected=True)
        costs, _ = mcp.find_costs([(a[0] - r0, a[1] - c0)], [(b[0] - r0, b[1] - c0)])
        if np.isfinite(costs[b[0] - r0, b[1] - c0]):
            path = mcp.traceback((b[0] - r0, b[1] - c0))
            return [(r + r0, c + c0) for r, c in path]
        if r1 - r0 >= n and c1 - c0 >= n:
            break
    return None


def chaikin(points: np.ndarray, rounds: int = 2) -> np.ndarray:
    for _ in range(rounds):
        if len(points) < 3:
            break
        q = 0.75 * points[:-1] + 0.25 * points[1:]
        r = 0.25 * points[:-1] + 0.75 * points[1:]
        mid = np.empty((2 * len(q), 2))
        mid[0::2], mid[1::2] = q, r
        points = np.vstack([points[:1], mid, points[-1:]])
    return points


def clip_to_outside(points: np.ndarray, towns) -> list[np.ndarray]:
    """Split a highway where it runs on town streets; each piece keeps one point inside the town."""
    inside = np.zeros(len(points), dtype=bool)
    for t in towns:
        inside |= np.hypot(points[:, 0] - t.x, points[:, 1] - t.y) < street_extent(t) - towns_mod.STREET
    pieces, start = [], None
    for i in range(len(points)):
        if not inside[i] and start is None:
            start = max(0, i - 1)
        if inside[i] and start is not None:
            pieces.append(points[start:i + 1])
            start = None
    if start is not None:
        pieces.append(points[start:])
    return [p for p in pieces if len(p) >= 2 and np.hypot(*(p[-1] - p[0])) > 20.0]


def snap_ends(piece: np.ndarray, towns, street_lines) -> np.ndarray:
    """Move a highway end that stops inside a town onto the nearest point of its streets."""
    piece = piece.copy()
    for end in (0, -1):
        p = piece[end]
        for t in towns:
            if math.hypot(p[0] - t.x, p[1] - t.y) > street_extent(t) + towns_mod.PITCH:
                continue
            best, best_d = None, 60.0
            for (ax, ay), (bx, by) in street_lines[t.name]:
                ab = np.array([bx - ax, by - ay])
                k = np.clip(np.dot(p - (ax, ay), ab) / max(np.dot(ab, ab), 1e-9), 0.0, 1.0)
                q = np.array([ax, ay]) + k * ab
                d = float(np.hypot(*(p - q)))
                if d < best_d:
                    best, best_d = q, d
            if best is not None:
                piece[end] = best
                break
    return piece


def densify(points: np.ndarray, step: float) -> np.ndarray:
    seg = np.hypot(*np.diff(points, axis=0).T)
    dist = np.concatenate([[0.0], np.cumsum(seg)])
    s = np.arange(0.0, dist[-1], step)
    s = np.append(s, dist[-1])
    return np.stack([np.interp(s, dist, points[:, 0]), np.interp(s, dist, points[:, 1])], -1)


def build_roads(h, land, lake_mask, river_mask, towns, grid) -> tuple[np.ndarray, list[Road], np.ndarray]:
    by_name = {t.name: t for t in towns}
    cost = base_cost(h, land, lake_mask, river_mask, towns, grid)
    roads: list[Road] = []
    street_lines = {t.name: town_streets(t) for t in towns}

    for ref, chain in HIGHWAYS:
        for a_name, b_name in zip(chain, chain[1:]):
            ta, tb = by_name[a_name], by_name[b_name]
            ra, ca = grid.to_cell(ta.x, ta.y)
            rb, cb = grid.to_cell(tb.x, tb.y)
            a, b = (int(round(float(ra))), int(round(float(ca)))), (int(round(float(rb))), int(round(float(cb))))
            cost[a] = cost[b] = 1.0
            path = route(cost, a, b)
            if path is None:
                print(f"  {ref} {a_name} - {b_name}: no route")
                continue
            rr, cc = np.array(path).T
            reuse = np.zeros(cost.shape, dtype=bool)
            reuse[rr, cc] = True
            reuse = ndimage.binary_dilation(reuse, iterations=1)
            cost = np.where(reuse & np.isfinite(cost), np.minimum(cost, cost * REUSE_FACTOR + 0.2), cost)

            world = np.stack([(cc + 0.5) * grid.cell, grid.size_m - (rr + 0.5) * grid.cell], -1)
            simple = measure.approximate_polygon(world, tolerance=3.0)
            smooth = chaikin(simple, 2)
            for piece in clip_to_outside(smooth, towns):
                piece = snap_ends(piece, towns, street_lines)
                road = Road("highway", ref, [(float(x), float(y)) for x, y in piece])
                road.bridges = find_bridges(piece, river_mask, grid)
                roads.append(road)
            print(f"  {ref} {a_name} - {b_name}: {len(path) * grid.cell / 1000:.1f} km")

    for t in towns:
        for line in street_lines[t.name]:
            roads.append(Road("street", t.class_name, line))

    h = grade_highways(h, land, lake_mask, [r for r in roads if r.kind == "highway"], towns, grid)
    footprint = road_footprint(roads, grid)
    return h, roads, footprint


def add_access_roads(h, land, lake_mask, river_mask, towns, grid, roads: list[Road], sites) -> tuple[list[Road], np.ndarray]:
    """Join each site to the nearest road: sealed for airfields and ports, gravel tracks otherwise."""
    from skimage import draw

    open_cost = base_cost(h, land, lake_mask, river_mask, towns, grid)
    owner = np.full(open_cost.shape, -1, dtype=np.int32)
    for i, site in enumerate(sites):
        for surf in site.surfaces:
            pr, pc = grid.to_cell(*np.array(surf["points"]).T)
            rr, cc = draw.polygon(pr, pc, shape=owner.shape)
            owner[rr, cc] = i
    cost = np.where(owner >= 0, np.inf, open_cost)
    footprint = road_footprint(roads, grid) > 0
    for i, site in enumerate(sites):
        if site.kind == "whakaari":
            continue
        sx, sy = site.extra.get("entrance", (site.x, site.y))
        r0, c0 = (int(round(float(v))) for v in grid.to_cell(sx, sy))
        k = int(ACCESS_SEARCH_M / grid.cell)
        ra, rb = max(0, r0 - k), min(grid.n, r0 + k + 1)
        ca, cb = max(0, c0 - k), min(grid.n, c0 + k + 1)
        sub = cost[ra:rb, ca:cb].copy()
        if "entrance" not in site.extra:
            # Leave from inside the site's own yard; only an airfield's runway stays off limits.
            own = owner[ra:rb, ca:cb] == i
            sub[own] = open_cost[ra:rb, ca:cb][own]
        sub[r0 - ra, c0 - ca] = 1.0
        targets = footprint[ra:rb, ca:cb]
        if not targets.any():
            continue
        mcp = graph.MCP_Geometric(sub, fully_connected=True)
        acc, _ = mcp.find_costs([(r0 - ra, c0 - ca)])
        acc = np.where(targets, acc, np.inf)
        end = np.unravel_index(np.argmin(acc), acc.shape)
        if not np.isfinite(acc[end]):
            continue
        path = np.array(mcp.traceback(end))
        rr, cc = path[:, 0] + ra, path[:, 1] + ca
        world = np.stack([(cc + 0.5) * grid.cell, grid.size_m - (rr + 0.5) * grid.cell], -1)
        if len(world) < 2:
            continue
        pts = chaikin(measure.approximate_polygon(world, tolerance=2.0), 2)
        kind = "street" if site.kind in ("airfield", "port") else "track"
        road = Road(kind, site.class_name, [(float(x), float(y)) for x, y in pts])
        road.bridges = find_bridges(pts, river_mask, grid)
        roads.append(road)
    return roads, road_footprint(roads, grid)


def find_bridges(points: np.ndarray, river_mask: np.ndarray, grid) -> list[tuple[float, float, float]]:
    dense = densify(points, grid.cell)
    r, c = grid.to_cell(dense[:, 0], dense[:, 1])
    wet = river_mask[np.clip(np.rint(r).astype(int), 0, grid.n - 1), np.clip(np.rint(c).astype(int), 0, grid.n - 1)]
    lab, n = ndimage.label(wet)
    out = []
    for k in range(1, n + 1):
        idx = np.flatnonzero(lab == k)
        i0, i1 = max(0, idx[0] - 1), min(len(dense) - 1, idx[-1] + 1)
        mid = dense[(i0 + i1) // 2]
        dx, dy = dense[i1] - dense[i0]
        out.append((float(mid[0]), float(mid[1]), float(math.degrees(math.atan2(dx, dy)) % 360)))
    return out


def grade_highways(h, land, lake_mask, roads, towns, grid) -> np.ndarray:
    target = np.full(h.shape, np.nan, dtype=np.float32)
    for road in roads:
        dense = densify(np.array(road.points), grid.cell * 0.5)
        z = grid.sample(h, dense[:, 0], dense[:, 1])
        z = ndimage.gaussian_filter1d(z, GRADE_SIGMA_M / (grid.cell * 0.5), mode="nearest")
        z = np.maximum(z, 0.8)
        r, c = grid.to_cell(dense[:, 0], dense[:, 1])
        r = np.clip(np.rint(r).astype(int), 0, grid.n - 1)
        c = np.clip(np.rint(c).astype(int), 0, grid.n - 1)
        target[r, c] = z
    has = np.isfinite(target)
    dist, (ri, ci) = ndimage.distance_transform_edt(~has, return_indices=True)
    dist *= grid.cell
    half = KINDS["highway"]["width"] / 2 + 1.0
    bed = target[ri, ci]
    # Deep cuts and high fills need a wider batter to stay under the terrain's slope cap.
    blend = BED_BLEND_M + 1.6 * np.abs(h[ri, ci] - bed)
    w = np.clip(1.0 - (dist - half) / blend, 0.0, 1.0)
    w = w * w * (3 - 2 * w)
    w[~land | lake_mask | towns_mod.town_mask(towns, grid)] = 0.0
    return np.where(w > 0, h * (1 - w) + bed * w, h).astype(np.float32)


def road_footprint(roads: list[Road], grid) -> np.ndarray:
    """1 within each road's half width of its centreline, else 0."""
    out = np.zeros((grid.n, grid.n), dtype=np.float32)
    for kind, spec in KINDS.items():
        centre = np.zeros((grid.n, grid.n), dtype=bool)
        for road in roads:
            if road.kind != kind:
                continue
            dense = densify(np.array(road.points), grid.cell * 0.5)
            r, c = grid.to_cell(dense[:, 0], dense[:, 1])
            centre[np.clip(np.rint(r).astype(int), 0, grid.n - 1), np.clip(np.rint(c).astype(int), 0, grid.n - 1)] = True
        if centre.any():
            dist = ndimage.distance_transform_edt(~centre) * grid.cell
            out = np.maximum(out, (dist <= spec["width"] / 2 + grid.cell / 2).astype(np.float32))
    return out


def write_outputs(roads: list[Road], footprint: np.ndarray, source_dir: Path, easting: float, northing: float) -> None:
    import shapefile

    out = source_dir / "roads"
    out.mkdir(parents=True, exist_ok=True)
    with shapefile.Writer(str(out / "roads"), shapeType=shapefile.POLYLINE) as w:
        w.field("ID", "N", 4)
        w.field("REF", "C", 24)
        for road in roads:
            w.line([[[x + easting, y + northing] for x, y in road.points]])
            w.record(KINDS[road.kind]["id"], road.ref)
    (out / "RoadsLib.cfg").write_text(ROADS_LIB)

    data = {
        "kinds": KINDS,
        "roads": [{"kind": r.kind, "ref": r.ref, "points": [[round(x, 1), round(y, 1)] for x, y in r.points]}
                  for r in roads],
        "bridges": [{"ref": r.ref, "x": round(x, 1), "y": round(y, 1), "heading": round(hd, 1)}
                    for r in roads for x, y, hd in r.bridges],
    }
    (source_dir / "roads.json").write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
    Image.fromarray((footprint * 255).astype(np.uint8)).save(source_dir / "roads_4096.png", optimize=True)


ROADS_LIB = """// Road types for source/roads/roads.shp (field ID). Generated by tools/roads.py.
// The texture and material paths are placeholders: point them at road textures that exist on
// your P: drive (for example under P:\\DZ\\structures\\roads\\data) before importing.
class RoadTypesLibrary
{
\tclass Road0001
\t{
\t\twidth = 8;
\t\tmainStrTex = "DZ\\structures\\roads\\data\\highway_ca.paa";
\t\tmainTerTex = "DZ\\structures\\roads\\data\\highway_end_ca.paa";
\t\tmainMat = "DZ\\structures\\roads\\data\\highway.rvmat";
\t\tmap = "main road";
\t\tAILineCount = 2;
\t\tLeftWayCount = 1;
\t\tRightWayCount = 1;
\t};
\tclass Road0002
\t{
\t\twidth = 6;
\t\tmainStrTex = "DZ\\structures\\roads\\data\\street_ca.paa";
\t\tmainTerTex = "DZ\\structures\\roads\\data\\street_end_ca.paa";
\t\tmainMat = "DZ\\structures\\roads\\data\\street.rvmat";
\t\tmap = "road";
\t\tAILineCount = 1;
\t\tLeftWayCount = 1;
\t\tRightWayCount = 1;
\t};
\tclass Road0003
\t{
\t\twidth = 4;
\t\tmainStrTex = "DZ\\structures\\roads\\data\\dirt_ca.paa";
\t\tmainTerTex = "DZ\\structures\\roads\\data\\dirt_end_ca.paa";
\t\tmainMat = "DZ\\structures\\roads\\data\\dirt.rvmat";
\t\tmap = "track";
\t\tAILineCount = 1;
\t\tLeftWayCount = 0;
\t\tRightWayCount = 0;
\t};
};
"""


def draw_preview(relief: Image.Image, roads: list[Road], size_m: float) -> Image.Image:
    img = relief.convert("RGB").copy()
    d = ImageDraw.Draw(img)
    k = img.width / size_m
    for road in roads:
        pts = [(x * k, (size_m - y) * k) for x, y in road.points]
        if road.kind == "highway":
            d.line(pts, fill=(230, 60, 40), width=3)
        elif road.kind == "street":
            d.line(pts, fill=(250, 250, 250), width=1)
        else:
            d.line(pts, fill=(200, 170, 110), width=1)
    for road in roads:
        for x, y, _ in road.bridges:
            d.ellipse([x * k - 3, (size_m - y) * k - 3, x * k + 3, (size_m - y) * k + 3], outline=(255, 230, 0), width=2)
    return img
