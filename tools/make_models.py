"""Ready-to-import model sources for the custom models in docs/CUSTOM_MODELS.md.

Object Builder imports Wavefront OBJ, so each model is written as OBJ files plus tiling textures:

  docs/models/<name>.obj           resolution LOD: the visible model, one group per named selection
  docs/models/<name>_geometry.obj  Geometry / Fire Geometry: closed convex boxes, one group per component
  docs/models/<name>_roadway.obj   Roadway: the floors, deck, steps and ramp players walk on
  docs/models/<name>.mtl           materials, pointing at data/models/*.png
  data/models/<texture>.png        tiling textures (pack.bat turns them into _co.paa)
  config/structures.hpp            CfgVehicles classes Land_Aotearoa_<Name>
  mission/dayzOffline.aotearoa/mapgroupproto.aotearoa.xml
                                   loot points for each building (pack.bat adds a building's group to the
                                   server's mapgroupproto.xml once its .p3d exists)
  preview/models_<name>.png        a quick render of each model

Units are metres, y is up and the model's front faces +z (north when placed with yaw 0). The origin is
the centre of the footprint at ground level. Doorways are open (no animated doors), so the buildings
need no model.cfg or memory points to be enterable.

    python make_models.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

MAP_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = MAP_DIR / "docs" / "models"
TEX_DIR = MAP_DIR / "data" / "models"
TEX_PATH = "maps\\aotearoa\\data\\models\\{name}_co.paa"

# Texture name: (metres covered by one tile, generator)
TEXTURES: dict[str, tuple[float, callable]] = {}


def texture(name: str, tile_m: float):
    def wrap(fn):
        TEXTURES[name] = (tile_m, fn)
        return fn
    return wrap


def _noise(rng, size, blur, amount):
    n = Image.fromarray((rng.random((size, size)) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur))
    return (np.asarray(n, dtype=np.float32) / 255.0 - 0.5) * amount


def _tint(base, shade):
    arr = np.clip(np.array(base, dtype=np.float32)[None, None, :] * (1.0 + shade[..., None]), 0, 255)
    return Image.fromarray(arr.astype(np.uint8))


def _weatherboard(colour, seed):
    rng = np.random.default_rng(seed)
    y = np.arange(512)[:, None].repeat(512, 1)
    board = (y % 64) / 64.0  # 8 boards per 2 m tile: 250 mm boards
    shade = -0.28 * (board > 0.9) + 0.06 * (1 - board) + _noise(rng, 512, 2, 0.12) + _noise(rng, 512, 30, 0.15)
    return _tint(colour, shade)


def _corrugated(colour, seed, rust=0.0):
    rng = np.random.default_rng(seed)
    x = np.arange(512)[None, :].repeat(512, 0)
    shade = 0.16 * np.sin(x / 512 * 2 * math.pi * 13) + _noise(rng, 512, 1.5, 0.08)
    img = _tint(colour, shade)
    if rust:
        r = np.clip(_noise(rng, 512, 18, 2.4) + rust - 0.5, 0, 1)
        rust_img = _tint((128, 64, 34), shade)
        img = Image.composite(rust_img, img, Image.fromarray((r * 255).astype(np.uint8)))
    return img


@texture("aotearoa_weatherboard_mint", 2.0)
def _wb_mint():
    return _weatherboard((170, 214, 190), 1)


@texture("aotearoa_weatherboard_cream", 2.0)
def _wb_cream():
    return _weatherboard((232, 222, 190), 2)


@texture("aotearoa_iron_roof_red", 2.0)
def _roof_red():
    return _corrugated((150, 40, 32), 3, rust=0.25)


@texture("aotearoa_iron_grey", 2.0)
def _iron_grey():
    return _corrugated((150, 156, 160), 4, rust=0.15)


@texture("aotearoa_iron_doc_orange", 2.0)
def _iron_orange():
    return _corrugated((214, 96, 34), 5)


@texture("aotearoa_timber", 2.0)
def _timber():
    rng = np.random.default_rng(6)
    x = np.arange(512)[None, :].repeat(512, 0)
    shade = -0.3 * ((x % 43) < 3) + _noise(rng, 512, 3, 0.2) + 0.08 * np.sin(np.arange(512)[:, None] / 9.0)
    return _tint((150, 112, 72), shade)


@texture("aotearoa_concrete", 4.0)
def _concrete():
    rng = np.random.default_rng(7)
    return _tint((170, 168, 160), _noise(rng, 512, 1, 0.12) + _noise(rng, 512, 40, 0.18))


@texture("aotearoa_window", 1.0)
def _window():
    img = Image.new("RGB", (512, 512), (232, 232, 226))
    d = ImageDraw.Draw(img)
    d.rectangle([28, 28, 484, 484], fill=(52, 70, 84))
    d.rectangle([248, 28, 264, 484], fill=(232, 232, 226))
    for i in range(6):
        d.line([(60 + i * 30, 470), (200 + i * 30, 60)], fill=(80, 100, 114), width=6)
    return img


@texture("aotearoa_trim_white", 1.0)
def _trim_white():
    rng = np.random.default_rng(8)
    return _tint((236, 234, 226), _noise(rng, 512, 2, 0.06) + _noise(rng, 512, 30, 0.08))


@texture("aotearoa_brick", 1.2)
def _brick():
    rng = np.random.default_rng(9)
    y, x = np.mgrid[0:512, 0:512]
    row = y // 32
    mortar = ((y % 32) < 3) | (((x + (row % 2) * 64) % 128) < 3)
    shade = _noise(rng, 512, 2, 0.18) + 0.12 * np.sin(row * 2.7 + (x + (row % 2) * 64) // 128 * 1.9)
    img = np.asarray(_tint((150, 70, 52), shade)).copy()
    img[mortar] = (190, 184, 172)
    return Image.fromarray(img)


@texture("aotearoa_vinyl", 1.0)
def _vinyl():
    rng = np.random.default_rng(10)
    return _tint((40, 92, 110), _noise(rng, 512, 1, 0.08) + _noise(rng, 512, 50, 0.12))


@texture("aotearoa_burlap", 0.6)
def _burlap():
    rng = np.random.default_rng(11)
    y, x = np.mgrid[0:512, 0:512]
    weave = 0.1 * np.sin(x / 2.5) * np.sin(y / 2.5) + _noise(rng, 512, 1, 0.16)
    return _tint((196, 176, 132), weave)


@texture("aotearoa_shelf_goods", 1.0)
def _shelf_goods():
    """Rows of packets and tins on shelves, seen from the aisle."""
    rng = np.random.default_rng(12)
    img = Image.new("RGB", (512, 512), (120, 96, 70))
    d = ImageDraw.Draw(img)
    colours = [(220, 40, 40), (250, 200, 30), (40, 90, 170), (60, 150, 60), (240, 240, 235), (230, 120, 30),
               (120, 60, 30), (30, 30, 30), (200, 60, 140)]
    for r in range(4):
        y1 = 128 * (r + 1) - 10
        d.rectangle([0, y1, 512, y1 + 10], fill=(200, 200, 196))
        x = 4
        while x < 508:
            w = int(rng.integers(18, 44))
            h = int(rng.integers(50, 108))
            c = colours[int(rng.integers(len(colours)))]
            d.rectangle([x, y1 - h, min(x + w, 508), y1], fill=c, outline=tuple(int(v * 0.7) for v in c))
            d.rectangle([x + 3, y1 - h + 8, min(x + w, 508) - 3, y1 - h + 18], fill=(250, 250, 250))
            x += w + 2
    return img


@texture("aotearoa_fridge", 1.0)
def _fridge():
    img = Image.new("RGB", (512, 512), (236, 236, 236))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(13)
    for k in range(2):
        x0 = 20 + k * 246
        d.rectangle([x0, 60, x0 + 226, 492], fill=(70, 96, 110))
        for r in range(4):
            y1 = 160 + r * 100
            d.rectangle([x0 + 8, y1, x0 + 218, y1 + 5], fill=(200, 205, 210))
            for i in range(7):
                c = [(250, 205, 30), (60, 170, 40), (220, 40, 40), (240, 240, 240), (40, 90, 170)][int(rng.integers(5))]
                d.rounded_rectangle([x0 + 12 + i * 29, y1 - 70, x0 + 34 + i * 29, y1], radius=5, fill=c)
        d.rectangle([x0 + 200, 240, x0 + 210, 320], fill=(180, 180, 184))
    from signs import FONTS_BOLD, _font
    d.rectangle([0, 0, 512, 50], fill=(220, 30, 40))
    d.text((256, 25), "COLD DRINKS", font=_font(FONTS_BOLD, 36), fill=(255, 255, 255), anchor="mm")
    return img


@texture("aotearoa_icecream_sign", 1.0)
def _icecream_sign():
    from signs import FONTS_BOLD, _font
    img = Image.new("RGB", (512, 512), (250, 250, 246))
    d = ImageDraw.Draw(img)
    d.rectangle([12, 12, 500, 500], outline=(30, 80, 160), width=14)
    d.text((256, 92), "ICE CREAM", font=_font(FONTS_BOLD, 70), fill=(30, 80, 160), anchor="mm")
    d.polygon([(206, 300), (306, 300), (256, 470)], fill=(214, 160, 90), outline=(150, 100, 50))
    for i in range(5):
        d.line([(214 + i * 20, 300), (256, 460)], fill=(170, 120, 60), width=3)
    for (cx, cy, c) in ((256, 270, (240, 220, 160)), (226, 230, (250, 180, 190)), (286, 230, (120, 80, 50)),
                        (256, 190, (250, 240, 200))):
        d.ellipse([cx - 46, cy - 42, cx + 46, cy + 42], fill=c, outline=tuple(int(v * 0.8) for v in c), width=3)
    d.text((256, 140), "Hokey Pokey", font=_font(FONTS_BOLD, 34), fill=(200, 40, 40), anchor="mm")
    return img


@texture("aotearoa_doc_sign", 1.0)
def _doc_sign():
    from signs import FONTS_BOLD, FONTS, _font
    img = Image.new("RGB", (512, 512), (36, 78, 52))
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 501, 245], outline=(236, 214, 150), width=8)
    d.text((256, 90), "BACKCOUNTRY HUT", font=_font(FONTS_BOLD, 46), fill=(236, 214, 150), anchor="mm")
    d.text((256, 160), "6 bunks  ·  Fill in the intentions book", font=_font(FONTS, 22), fill=(236, 214, 150),
           anchor="mm")
    d.rectangle([0, 256, 512, 512], fill=(116, 88, 60))
    return img


@texture("aotearoa_dairy_sign", 1.0)
def _dairy_sign():
    from signs import FONTS_BOLD, _font
    img = Image.new("RGB", (512, 512), (240, 240, 236))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 511, 255], fill=(220, 30, 40))
    d.text((256, 128), "DAIRY", font=_font(FONTS_BOLD, 150), fill=(255, 255, 255), anchor="mm")
    for i in range(8):  # awning stripes
        d.rectangle([i * 64, 256, i * 64 + 31, 511], fill=(30, 110, 60))
    return img


@dataclass
class Mesh:
    name: str
    verts: list = field(default_factory=list)
    uvs: list = field(default_factory=list)
    faces: list = field(default_factory=list)  # (group, material, [(v, vt), ...])
    components: list = field(default_factory=list)  # 8 corners each, for Geometry
    roadway: list = field(default_factory=list)  # quads

    def quad(self, pts, mat, group, flip=False):
        pts = [np.array(p, dtype=float) for p in pts]
        if flip:
            pts = pts[::-1]
        tile = TEXTURES[mat][0] if mat in TEXTURES else 1.0
        u_axis = pts[1] - pts[0]
        u_axis /= np.linalg.norm(u_axis) or 1.0
        normal = np.cross(pts[1] - pts[0], pts[-1] - pts[0])
        v_axis = np.cross(normal, u_axis)
        v_axis /= np.linalg.norm(v_axis) or 1.0
        idx = []
        for p in pts:
            self.verts.append(p)
            rel = p - pts[0]
            self.uvs.append((rel @ u_axis / tile, rel @ v_axis / tile))
            idx.append((len(self.verts), len(self.uvs)))
        self.faces.append((group, mat, idx))

    def stretched(self, pts, mat, group):
        """A quad with the whole texture stretched over it (signs, windows)."""
        start = len(self.verts)
        for p, uv in zip(pts, [(0, 0), (1, 0), (1, 1), (0, 1)]):
            self.verts.append(np.array(p, dtype=float))
            self.uvs.append(uv)
        self.faces.append((group, mat, [(start + i + 1, start + i + 1) for i in range(4)]))

    def hexa(self, c, mat, group, solid=True, skip=()):
        """Eight corners: c[0..3] the bottom (counter-clockwise from above), c[4..7] the top above them."""
        b, t = c[:4], c[4:]
        sides = {"bottom": [b[3], b[2], b[1], b[0]], "top": [t[0], t[1], t[2], t[3]]}
        for i in range(4):
            sides[f"side{i}"] = [b[i], b[(i + 1) % 4], t[(i + 1) % 4], t[i]]
        for key, q in sides.items():
            if key not in skip:
                self.quad(q, mat, group)
        if solid:
            self.components.append(c)

    def box(self, x0, x1, y0, y1, z0, z1, mat, group, solid=True, walk=False, skip=()):
        c = [(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0),
             (x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)]
        # Bottom corners run anticlockwise seen from above: front-left, front-right, back-right, back-left.
        c = [c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7]]
        self.hexa(c, mat, group, solid, skip)
        if walk:
            self.roadway.append([(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)])

    def wall_x(self, x0, x1, z, t, y0, y1, mat, group, openings=()):
        """A wall along x at depth z with openings [(x_start, x_end, bottom, top)], as solid boxes."""
        cuts = sorted(openings)
        x = x0
        for a, b, lo, hi in cuts:
            if a > x:
                self.box(x, a, y0, y1, z - t / 2, z + t / 2, mat, group)
            if lo > y0:
                self.box(a, b, y0, lo, z - t / 2, z + t / 2, mat, group)
            if hi < y1:
                self.box(a, b, hi, y1, z - t / 2, z + t / 2, mat, group)
            x = b
        if x < x1:
            self.box(x, x1, y0, y1, z - t / 2, z + t / 2, mat, group)

    def wall_z(self, z0, z1, x, t, y0, y1, mat, group, openings=()):
        cuts = sorted(openings)
        z = z0
        for a, b, lo, hi in cuts:
            if a > z:
                self.box(x - t / 2, x + t / 2, y0, y1, z, a, mat, group)
            if lo > y0:
                self.box(x - t / 2, x + t / 2, y0, lo, a, b, mat, group)
            if hi < y1:
                self.box(x - t / 2, x + t / 2, hi, y1, a, b, mat, group)
            z = b
        if z < z1:
            self.box(x - t / 2, x + t / 2, y0, y1, z, z1, mat, group)

    def gable_roof(self, w, d, eave_y, ridge_y, overhang, thick, mat, end_mat, along_x=True, z0=0.0):
        """Two sloping slabs meeting at a ridge, plus gable-end triangles. Ridge runs along x by default,
        over z = z0."""
        hw, hd = w / 2 + overhang, d / 2 + overhang
        start_v = len(self.verts)
        start_c = len(self.components)
        if along_x:
            for side in (1, -1):
                # Slab from the eave (z = side * hd) up to the ridge (z = 0).
                drop = (ridge_y - eave_y) * overhang / (d / 2)
                c = [(-hw, eave_y - drop, side * hd), (hw, eave_y - drop, side * hd), (hw, ridge_y, 0), (-hw, ridge_y, 0)]
                if side < 0:
                    c = [c[1], c[0], c[3], c[2]]
                top = [(x, y + thick, z) for x, y, z in c]
                self.hexa(c + top, mat, "roof")
            for sx in (1, -1):
                x = sx * w / 2
                tri = [(x, eave_y, d / 2), (x, eave_y, -d / 2), (x, ridge_y, 0)]
                if sx < 0:
                    tri = tri[::-1]
                start = len(self.verts)
                tile = TEXTURES[end_mat][0]
                for p in tri:
                    self.verts.append(np.array(p, dtype=float))
                    self.uvs.append((p[2] / tile, p[1] / tile))
                self.faces.append(("walls", end_mat, [(start + i + 1, start + i + 1) for i in range(3)]))
        if z0:
            for i in range(start_v, len(self.verts)):
                self.verts[i] = self.verts[i] + np.array([0.0, 0.0, z0])
            for i in range(start_c, len(self.components)):
                self.components[i] = [(x, y, z + z0) for x, y, z in self.components[i]]

    def write(self):
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        head = [f"# {self.name}: generated by tools/make_models.py. Metres, y up, front faces +z.",
                f"mtllib {self.name}.mtl"]
        out = head + [f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in self.verts]
        out += [f"vt {u:.4f} {v:.4f}" for u, v in self.uvs]
        cur = None
        for group, mat, idx in sorted(self.faces, key=lambda f: (f[0], f[1])):
            if (group, mat) != cur:
                out += [f"g {group}", f"usemtl {mat}"]
                cur = (group, mat)
            out.append("f " + " ".join(f"{v}/{t}" for v, t in idx))
        (MODEL_DIR / f"{self.name}.obj").write_text("\n".join(out) + "\n")
        mats = sorted({f[1] for f in self.faces})
        (MODEL_DIR / f"{self.name}.mtl").write_text("".join(
            f"newmtl {m}\nKd 1 1 1\nmap_Kd ../../data/{'signs' if m.startswith('sign_') or m.startswith('post_') else 'models'}/{m}.png\n"
            for m in mats))
        if self.components:
            geo = [f"# {self.name} Geometry: {len(self.components)} closed convex components. Give each its own "
                   "named selection ComponentNN (Structure > Convexity > Component Convex Hull)."]
            for n, c in enumerate(self.components, 1):
                base = n * 8 - 7
                geo += [f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in c]
                geo.append(f"g Component{n:02d}")
                b = [base + i for i in range(8)]
                geo += [f"f {b[3]} {b[2]} {b[1]} {b[0]}", f"f {b[4]} {b[5]} {b[6]} {b[7]}"]
                for i in range(4):
                    geo.append(f"f {b[i]} {b[(i + 1) % 4]} {b[4 + (i + 1) % 4]} {b[4 + i]}")
            (MODEL_DIR / f"{self.name}_geometry.obj").write_text("\n".join(geo) + "\n")
        if self.roadway:
            rw = [f"# {self.name} Roadway: every surface players walk on."]
            for n, q in enumerate(self.roadway):
                rw += [f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in q]
                rw.append("f " + " ".join(str(n * 4 + i + 1) for i in range(4)))
            (MODEL_DIR / f"{self.name}_roadway.obj").write_text("\n".join(rw) + "\n")

    def tris(self):
        return sum(len(idx) - 2 for _, _, idx in self.faces)


def sign_town() -> Mesh:
    m = Mesh("sign_town")
    board = [(-1.2, 1.1, 0.03), (1.2, 1.1, 0.03), (1.2, 2.3, 0.03), (-1.2, 2.3, 0.03)]
    start = len(m.verts)
    for p, uv in zip(board, [(0, 0.5), (1, 0.5), (1, 1), (0, 1)]):
        m.verts.append(np.array(p))
        m.uvs.append(uv)
    m.faces.append(("camo", "sign_Wellington", [(start + i + 1, start + i + 1) for i in range(4)]))
    grey = [(0.1, 0.1), (0.4, 0.1), (0.4, 0.4), (0.1, 0.4)]

    def grey_box(x0, x1, y0, y1, z0, z1, group, skip_front=False):
        c = [(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)]
        quads = [[c[3], c[2], c[1], c[0]], [c[4], c[5], c[6], c[7]]] + \
                [[c[i], c[(i + 1) % 4], c[4 + (i + 1) % 4], c[4 + i]] for i in range(4)]
        for qi, q in enumerate(quads):
            if skip_front and qi == 2:  # side0 runs along the front edge (z1)
                continue
            s = len(m.verts)
            for p, uv in zip(q, grey):
                m.verts.append(np.array(p))
                m.uvs.append(uv)
            m.faces.append((group, "sign_Wellington", [(s + i + 1, s + i + 1) for i in range(4)]))
        m.components.append(c)

    grey_box(-1.2, 1.2, 1.1, 2.3, -0.03, 0.03, "back", skip_front=True)
    grey_box(-0.94, -0.86, -0.5, 2.25, -0.11, -0.03, "posts")
    grey_box(0.86, 0.94, -0.5, 2.25, -0.11, -0.03, "posts")
    return m


def sign_post() -> Mesh:
    """A 1 m square cut-out sign: two faces 4 mm apart (no edges, so the alpha outline shows) on one post."""
    m = Mesh("sign_post")
    y0, y1, s = 1.6, 2.6, 0.5
    for z, uvs, order in ((0.002, [(0, 0.5), (1, 0.5), (1, 1), (0, 1)], (0, 1, 2, 3)),
                          (-0.002, [(1, 0), (0, 0), (0, 0.5), (1, 0.5)], (1, 0, 3, 2))):
        corners = [(-s, y0, z), (s, y0, z), (s, y1, z), (-s, y1, z)]
        start = len(m.verts)
        for i in order:
            m.verts.append(np.array(corners[i]))
            m.uvs.append(uvs[i])
        m.faces.append(("camo", "post_SH1", [(start + i + 1, start + i + 1) for i in range(4)]))
    post_uv = [(0.47, 0.23), (0.53, 0.23), (0.53, 0.27), (0.47, 0.27)]
    x0, x1, z0, z1 = -0.03, 0.03, -0.10, -0.04
    c = [(x0, -0.5, z1), (x1, -0.5, z1), (x1, -0.5, z0), (x0, -0.5, z0),
         (x0, 2.3, z1), (x1, 2.3, z1), (x1, 2.3, z0), (x0, 2.3, z0)]
    for q in [[c[i], c[(i + 1) % 4], c[4 + (i + 1) % 4], c[4 + i]] for i in range(4)] + [[c[4], c[5], c[6], c[7]]]:
        start = len(m.verts)
        for p, uv in zip(q, post_uv):
            m.verts.append(np.array(p))
            m.uvs.append(uv)
        m.faces.append(("camo", "post_SH1", [(start + i + 1, start + i + 1) for i in range(4)]))
    m.components.append(c)
    m.components.append([(-s, y0, 0.01), (s, y0, 0.01), (s, y0, -0.01), (-s, y0, -0.01),
                         (-s, y1, 0.01), (s, y1, 0.01), (s, y1, -0.01), (-s, y1, -0.01)])
    return m


def window(m: Mesh, x0, x1, y0, y1, z, along_x=True):
    if along_x:
        m.stretched([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], "aotearoa_window", "glass")
        m.stretched([(x1, y0, z), (x0, y0, z), (x0, y1, z), (x1, y1, z)], "aotearoa_window", "glass")
    else:
        m.stretched([(z, y0, x1), (z, y0, x0), (z, y1, x0), (z, y1, x1)], "aotearoa_window", "glass")
        m.stretched([(z, y0, x0), (z, y0, x1), (z, y1, x1), (z, y1, x0)], "aotearoa_window", "glass")


def frame(m: Mesh, x0, x1, y0, y1, z, t, along_x=True, sill=True, mat="aotearoa_trim_white", w=0.08, out=0.03):
    """Trim round an opening on both faces of a wall of thickness t (head, jambs and, for windows, a sill)."""
    for side in (1, -1):
        f0, f1 = sorted((z + side * t / 2, z + side * (t / 2 + out)))
        parts = [(x0 - w, x0, y0, y1 + w), (x1, x1 + w, y0, y1 + w), (x0 - w, x1 + w, y1, y1 + w)]
        if sill:
            parts.append((x0 - w, x1 + w, y0 - w, y0))
        for a, b, lo, hi in parts:
            if along_x:
                m.box(a, b, lo, hi, f0, f1, mat, "trim", solid=False)
            else:
                m.box(f0, f1, lo, hi, a, b, mat, "trim", solid=False)


def table(m: Mesh, x0, x1, z0, z1, y, h=0.75, mat="aotearoa_timber", group="furniture"):
    m.box(x0, x1, y + h - 0.05, y + h, z0, z1, mat, group, solid=False)
    for x in (x0 + 0.03, x1 - 0.08):
        for zz in (z0 + 0.03, z1 - 0.08):
            m.box(x, x + 0.05, y, y + h - 0.05, zz, zz + 0.05, mat, group, solid=False)


def bach() -> Mesh:
    """9 x 7 m 1960s bach: raised floor, two rooms, front deck, low gable roof."""
    m = Mesh("bach")
    W, D, F, H, T = 9.0, 5.0, 0.45, 2.4, 0.12  # house body 9 x 5, deck 2 m in front
    wb, zb = "aotearoa_weatherboard_mint", -1.0  # body centred 1 m back so the deck fits in 7 m
    m.box(-W / 2, W / 2, 0, F, zb - D / 2, zb + D / 2, "aotearoa_timber", "floor", walk=True)
    top = F + H
    front, back = zb + D / 2, zb - D / 2
    m.wall_x(-W / 2, W / 2, front, T, F, top, wb, "walls",
             openings=[(-3.4, -1.4, F + 0.9, F + 2.0), (-0.6, 1.4, F, F + 2.1), (2.4, 4.0, F + 0.9, F + 2.0)])
    m.wall_x(-W / 2, W / 2, back, T, F, top, wb, "walls", openings=[(1.0, 1.8, F, F + 2.0), (-3.0, -1.8, F + 1.0, F + 1.8)])
    m.wall_z(back + T / 2, front - T / 2, -W / 2, T, F, top, wb, "walls", openings=[(zb - 0.6, zb + 0.6, F + 0.9, F + 1.9)])
    m.wall_z(back + T / 2, front - T / 2, W / 2, T, F, top, wb, "walls")
    m.wall_z(back + T / 2, front - T / 2, 0.0, 0.08, F, top, wb, "walls", openings=[(zb - 0.4, zb + 0.4, F, F + 2.0)])
    window(m, -3.4, -1.4, F + 0.9, F + 2.0, front)
    window(m, 2.4, 4.0, F + 0.9, F + 2.0, front)
    window(m, -3.0, -1.8, F + 1.0, F + 1.8, back)
    m.box(-W / 2, W / 2, 0, F - 0.05, front, 3.5, "aotearoa_timber", "deck", walk=True)
    m.box(-0.6, 1.4, 0, 0.22, 3.5, 3.85, "aotearoa_timber", "deck", walk=True)
    for x in (-W / 2 + 0.1, W / 2 - 0.1):
        m.box(x - 0.05, x + 0.05, F, F + 0.9, front, 3.45, "aotearoa_timber", "deck")
    m.gable_roof(W, D, top, top + 1.1, 0.45, 0.06, "aotearoa_iron_roof_red", wb, z0=zb)
    m.box(-W / 2, W / 2, top, top + 0.02, back, front, "aotearoa_timber", "ceiling", solid=False, skip=("top",))
    trim = "aotearoa_trim_white"
    for x0, x1, y0, y1 in ((-3.4, -1.4, F + 0.9, F + 2.0), (2.4, 4.0, F + 0.9, F + 2.0)):
        frame(m, x0, x1, y0, y1, front, T)
    frame(m, -0.6, 1.4, F, F + 2.1, front, T, sill=False)
    frame(m, -3.0, -1.8, F + 1.0, F + 1.8, back, T)
    frame(m, 1.0, 1.8, F, F + 2.0, back, T, sill=False)
    frame(m, zb - 0.6, zb + 0.6, F + 0.9, F + 1.9, -W / 2, T, along_x=False)
    for x in (-W / 2, W / 2):  # corner boards
        for z in (back, front):
            m.box(x - 0.08, x + 0.08, F, top, z - 0.08, z + 0.08, trim, "trim", solid=False)
    for z in (back - 0.45, front + 0.45):  # fascia boards along the eaves
        m.box(-W / 2 - 0.45, W / 2 + 0.45, top - 0.2, top - 0.02, z - 0.02, z + 0.02, trim, "trim", solid=False)
    # Deck rail along the front, open at the steps.
    for a, b in ((-W / 2, -0.6), (1.4, W / 2)):
        m.box(a, b, F + 0.85, F + 0.93, 3.4, 3.48, "aotearoa_timber", "deck", solid=False)
        for x in np.arange(a + 0.05, b, 0.6):
            m.box(x, x + 0.05, F, F + 0.85, 3.42, 3.47, "aotearoa_timber", "deck", solid=False)
    # Brick chimney on the right-hand end wall, above the ridge.
    m.box(W / 2 + T / 2, W / 2 + 0.6, 0, top + 1.6, zb - 0.9, zb - 0.2, "aotearoa_brick", "chimney")
    # Inside: kitchen bench, table and chairs, couch in the living room; bed and wardrobe in the bedroom.
    m.box(-W / 2 + 0.1, -2.2, F, F + 0.9, back + 0.08, back + 0.7, "aotearoa_trim_white", "furniture", walk=True)
    m.box(-W / 2 + 0.1, -2.2, F + 0.9, F + 0.94, back + 0.06, back + 0.72, "aotearoa_timber", "furniture", solid=False)
    table(m, -2.6, -1.4, zb - 0.1, zb + 0.7, F)
    m.box(-4.3, -2.4, F, F + 0.45, front - 0.95, front - 0.15, "aotearoa_vinyl", "furniture")
    m.box(-4.3, -2.4, F + 0.45, F + 0.85, front - 0.3, front - 0.15, "aotearoa_vinyl", "furniture", solid=False)
    m.box(1.6, 3.6, F, F + 0.5, back + 0.1, back + 2.1, "aotearoa_vinyl", "furniture", walk=True)
    m.box(3.9, 4.4, F, F + 1.9, front - 1.1, front - 0.15, "aotearoa_timber", "furniture")
    # The long drop out the back: a 1.1 m square dunny with its door facing the house.
    lz = back - 2.6
    m.box(2.4, 3.5, 0, 0.15, lz - 0.55, lz + 0.55, "aotearoa_timber", "longdrop", walk=True)
    m.wall_x(2.4, 3.5, lz + 0.55, 0.06, 0.15, 2.2, wb, "longdrop", openings=[(2.65, 3.25, 0.15, 2.0)])
    m.wall_x(2.4, 3.5, lz - 0.55, 0.06, 0.15, 2.1, wb, "longdrop")
    m.wall_z(lz - 0.52, lz + 0.52, 2.4, 0.06, 0.15, 2.15, wb, "longdrop")
    m.wall_z(lz - 0.52, lz + 0.52, 3.5, 0.06, 0.15, 2.15, wb, "longdrop")
    c = [(2.3, 2.1, lz - 0.7), (3.6, 2.1, lz - 0.7), (3.6, 2.25, lz + 0.7), (2.3, 2.25, lz + 0.7)]
    c = [c[3], c[2], c[1], c[0]]
    m.hexa(c + [(x, y + 0.04, z) for x, y, z in c], "aotearoa_iron_roof_red", "longdrop")
    m.box(2.5, 3.4, 0.15, 0.6, lz - 0.5, lz - 0.05, "aotearoa_timber", "longdrop", solid=False)
    return m


def doc_hut() -> Mesh:
    """8 x 6 m tramping hut: orange iron, veranda, bunks, chimney, water tank."""
    m = Mesh("doc_hut")
    W, D, F, H, T = 6.0, 4.5, 0.3, 2.3, 0.1
    iron, zb = "aotearoa_iron_doc_orange", -0.75
    front, back = zb + D / 2, zb - D / 2
    top = F + H
    m.box(-W / 2, W / 2, 0, F, back, front, "aotearoa_timber", "floor", walk=True)
    m.wall_x(-W / 2, W / 2, front, T, F, top + 0.4, iron, "walls",
             openings=[(-0.4, 0.5, F, F + 2.0), (1.2, 2.4, F + 0.9, F + 1.8)])
    m.wall_x(-W / 2, W / 2, back, T, F, top, iron, "walls")
    m.wall_z(back + T / 2, front - T / 2, -W / 2, T, F, top, iron, "walls", openings=[(zb - 0.5, zb + 0.5, F + 0.9, F + 1.7)])
    m.wall_z(back + T / 2, front - T / 2, W / 2, T, F, top, iron, "walls")
    window(m, 1.2, 2.4, F + 0.9, F + 1.8, front)
    # Mono-pitch roof: high at the front, low at the back.
    oh = 0.4
    c = [(-W / 2 - oh, top + 0.05, back - oh), (W / 2 + oh, top + 0.05, back - oh), (W / 2 + oh, top + 0.6, front + 1.5),
         (-W / 2 - oh, top + 0.6, front + 1.5)]
    c = [c[3], c[2], c[1], c[0]]
    m.hexa(c + [(x, y + 0.06, z) for x, y, z in c], "aotearoa_iron_grey", "roof")
    for sx in (-1, 1):  # side gussets between wall top and sloping roof
        x = sx * W / 2
        tri = [(x, top, back), (x, top, front), (x, top + 0.4, front)]
        start = len(m.verts)
        for p in (tri if sx > 0 else tri[::-1]):
            m.verts.append(np.array(p))
            m.uvs.append((p[2] / 2, p[1] / 2))
        m.faces.append(("walls", iron, [(start + i + 1, start + i + 1) for i in range(3)]))
    m.box(-W / 2, W / 2, 0, F - 0.05, front, front + 1.5, "aotearoa_timber", "veranda", walk=True)
    for x in (-W / 2 + 0.1, W / 2 - 0.1):
        m.box(x - 0.06, x + 0.06, F, top + 0.58, front + 1.35, front + 1.47, "aotearoa_timber", "veranda")
    for y in (F + 0.4, F + 1.4):  # double bunks along the back wall
        m.box(-W / 2 + 0.1, W / 2 - 0.1, y, y + 0.12, back + 0.1, back + 0.9, "aotearoa_timber", "bunks", walk=True)
    m.box(-W / 2 + 0.1, -W / 2 + 0.7, F, F + 0.8, front - 0.9, front - 0.3, "aotearoa_iron_grey", "stove")
    m.box(-W / 2 + 0.3, -W / 2 + 0.5, F + 0.8, top + 1.4, front - 0.7, front - 0.5, "aotearoa_iron_grey", "chimney")
    n = 12  # water tank on a stand
    cx, cz, r = W / 2 + 0.9, back + 0.8, 0.55
    m.box(cx - 0.6, cx + 0.6, 0, 0.9, cz - 0.6, cz + 0.6, "aotearoa_timber", "tank")
    ring = [(cx + r * math.cos(2 * math.pi * i / n), cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    for i in range(n):
        (ax, az), (bx, bz) = ring[i], ring[(i + 1) % n]
        m.quad([(ax, 0.9, az), (ax, 2.1, az), (bx, 2.1, bz), (bx, 0.9, bz)], "aotearoa_iron_grey", "tank")
        m.quad([(cx, 2.1, cz), (bx, 2.1, bz), (ax, 2.1, az), (cx, 2.1, cz)], "aotearoa_iron_grey", "tank")
    m.components.append([(cx - r, 0.9, cz + r), (cx + r, 0.9, cz + r), (cx + r, 0.9, cz - r), (cx - r, 0.9, cz - r),
                         (cx - r, 2.1, cz + r), (cx + r, 2.1, cz + r), (cx + r, 2.1, cz - r), (cx - r, 2.1, cz - r)])
    frame(m, -0.4, 0.5, F, F + 2.0, front, T, sill=False, mat="aotearoa_timber")
    frame(m, 1.2, 2.4, F + 0.9, F + 1.8, front, T, mat="aotearoa_timber")
    frame(m, zb - 0.5, zb + 0.5, F + 0.9, F + 1.7, -W / 2, T, along_x=False, mat="aotearoa_timber")
    # Hut sign over the door, the intentions book box beside it, and a bench and woodpile on the veranda.
    m.stretched([(-1.0, F + 2.1, front + T / 2 + 0.01), (1.0, F + 2.1, front + T / 2 + 0.01),
                 (1.0, F + 2.6, front + T / 2 + 0.01), (-1.0, F + 2.6, front + T / 2 + 0.01)], "aotearoa_doc_sign", "sign")
    m.box(-1.1, -0.7, F + 1.1, F + 1.45, front + T / 2, front + T / 2 + 0.18, "aotearoa_iron_grey", "veranda", solid=False)
    m.box(-2.6, -1.3, F, F + 0.45, front + 0.2, front + 0.55, "aotearoa_timber", "veranda", walk=True)
    for k in range(4):
        y = F + 0.12 + k * 0.2
        m.box(1.4, 2.8, y - 0.1, y + 0.1, front + 0.15 + (k % 2) * 0.05, front + 0.75, "aotearoa_timber", "woodpile",
              solid=k == 0)
    # Mattresses on the bunks, a table with bench seats, and a gutter and downpipe to the tank.
    for y in (F + 0.52, F + 1.52):
        for x0 in (-W / 2 + 0.15, -1.0, 1.0):
            m.box(x0, x0 + 1.85, y, y + 0.1, back + 0.15, back + 0.85, "aotearoa_vinyl", "bunks", solid=False)
    table(m, 0.2, 2.0, zb - 0.1, zb + 0.6, F)
    for z0 in (zb - 0.45, zb + 0.75):
        m.box(0.2, 2.0, F + 0.4, F + 0.45, z0, z0 + 0.3, "aotearoa_timber", "furniture", solid=False)
    m.box(-W / 2 - oh, W / 2 + oh, top - 0.07, top + 0.05, back - oh - 0.12, back - oh, "aotearoa_iron_grey", "roof",
          solid=False)
    m.box(W / 2 + 0.25, W / 2 + 0.33, 2.1, top - 0.07, back - oh - 0.1, back - oh - 0.02, "aotearoa_iron_grey", "tank",
          solid=False)
    return m


def woolshed() -> Mesh:
    """30 x 14 m raised woolshed: iron walls and roof, shearing board, pens, ramp and two big doorways."""
    m = Mesh("woolshed")
    W, D, F, H, T = 28.0, 12.0, 1.2, 3.2, 0.15
    iron = "aotearoa_iron_grey"
    top = F + H
    m.box(-W / 2, W / 2, 0, F, -D / 2, D / 2, "aotearoa_timber", "floor", walk=True)
    m.wall_x(-W / 2, W / 2, D / 2, T, F, top, iron, "walls",
             openings=[(-9.0, -6.0, F, F + 2.8), (2.0, 4.0, F + 1.2, F + 2.2), (8.0, 10.0, F + 1.2, F + 2.2)])
    m.wall_x(-W / 2, W / 2, -D / 2, T, F, top, iron, "walls", openings=[(-1.0, 0.0, F, F + 2.0)])
    m.wall_z(-D / 2 + T / 2, D / 2 - T / 2, -W / 2, T, F, top, iron, "walls", openings=[(-1.5, 1.5, F, F + 3.0)])
    m.wall_z(-D / 2 + T / 2, D / 2 - T / 2, W / 2, T, F, top, iron, "walls")
    for x0 in (2.0, 8.0):
        window(m, x0, x0 + 2.0, F + 1.2, F + 2.2, D / 2)
    m.box(-W / 2, W / 2, 0, F, -D / 2 + T, D / 2 - T, iron, "piles", solid=False, skip=("top", "bottom"))
    m.gable_roof(W, D, top, top + 2.6, 0.6, 0.08, "aotearoa_iron_roof_red", iron)
    # Loading ramp up to the end doorway, as a sloped slab.
    rc = [(-W / 2 - 6.0, 0.0, 1.5), (-W / 2, F, 1.5), (-W / 2, F, -1.5), (-W / 2 - 6.0, 0.0, -1.5)]
    m.hexa([(x, y - 0.15, z) for x, y, z in rc] + rc, "aotearoa_timber", "ramp")
    m.roadway.append(rc)
    for z in (-1.5, 1.5):
        m.box(-W / 2 - 6.0, -W / 2, 0.0, F + 1.0, z - 0.04, z + 0.04, "aotearoa_timber", "ramp", solid=False)
    m.box(-W / 2 + 0.2, W / 2 - 0.2, F, F + 0.05, D / 2 - 3.2, D / 2 - 0.2, "aotearoa_timber", "board", walk=True)
    for x in np.arange(-W / 2 + 4.0, W / 2 - 1.0, 4.0):  # pen rails across the back half
        m.box(x - 0.05, x + 0.05, F, F + 1.0, -D / 2 + 0.2, 0.5, "aotearoa_timber", "pens")
    m.box(-W / 2 + 0.2, W / 2 - 0.2, F, F + 1.0, 0.45, 0.55, "aotearoa_timber", "pens")
    m.box(W / 2 - 2.6, W / 2 - 1.0, F, F + 2.2, -D / 2 + 0.5, -D / 2 + 1.5, "aotearoa_iron_grey", "woolpress")
    # Covered sheep yard against the back wall.
    m.box(-W / 2, -2.0, 0, 0.12, -D / 2 - 5.0, -D / 2, "aotearoa_concrete", "yard", walk=True)
    for x in np.arange(-W / 2, -1.9, 3.0):
        m.box(x - 0.06, x + 0.06, 0.12, 1.1, -D / 2 - 5.0, -D / 2 - 4.9, "aotearoa_timber", "yard")
    m.box(-W / 2, -2.0, 0.12, 1.1, -D / 2 - 5.0, -D / 2 - 4.92, "aotearoa_timber", "yard", solid=False)
    for y in (0.5, 0.9):
        m.box(-W / 2, -2.0, y, y + 0.08, -D / 2 - 5.0, -D / 2 - 4.94, "aotearoa_timber", "yard", solid=False)
    for x0 in (2.0, 8.0):
        frame(m, x0, x0 + 2.0, F + 1.2, F + 2.2, D / 2, T, mat="aotearoa_timber")
    frame(m, -9.0, -6.0, F, F + 2.8, D / 2, T, sill=False, mat="aotearoa_timber", w=0.15)
    # Shearing stands along the board: a pole, the overhead gear box and the drop to the handpiece.
    for x in (-10.0, -6.0, -2.0, 2.0, 6.0):
        m.box(x - 0.06, x + 0.06, F, top, D / 2 - 0.5, D / 2 - 0.38, "aotearoa_timber", "stands", solid=False)
        m.box(x - 0.25, x + 0.25, top - 0.8, top - 0.5, D / 2 - 1.4, D / 2 - 0.4, "aotearoa_iron_grey", "stands", solid=False)
        m.box(x - 0.03, x + 0.03, F + 1.0, top - 0.8, D / 2 - 1.3, D / 2 - 1.24, "aotearoa_iron_grey", "stands", solid=False)
        m.box(x - 0.4, x + 0.4, F, F + 1.0, D / 2 - 0.3, D / 2 - 0.2, "aotearoa_timber", "stands", solid=False)
    # The wool table (slatted top), the sorting bins, and the bales by the press.
    table(m, 6.0, 9.0, -0.6, 1.4, F, h=0.9, group="wooltable")
    for x in np.arange(6.05, 9.0, 0.15):
        m.box(x, x + 0.08, F + 0.9, F + 0.93, -0.6, 1.4, "aotearoa_timber", "wooltable", solid=False)
    for k in range(4):
        x0 = 4.0 + k * 1.6
        m.box(x0, x0 + 1.5, F, F + 1.2, -D / 2 + 0.2, -D / 2 + 0.28, "aotearoa_timber", "bins", solid=False)
        m.box(x0 - 0.04, x0, F, F + 1.2, -D / 2 + 0.2, -D / 2 + 1.6, "aotearoa_timber", "bins", solid=False)
    for k, (bx, bz) in enumerate(((W / 2 - 4.0, -D / 2 + 0.6), (W / 2 - 4.0, -D / 2 + 1.5), (W / 2 - 5.0, -D / 2 + 0.6))):
        m.box(bx - 0.4, bx + 0.4, F, F + 1.2, bz - 0.4, bz + 0.4, "aotearoa_burlap", "bales")
    return m


def dairy() -> Mesh:
    """12 x 9 m corner dairy: flat roof, parapet with the sign, shop window, awning, back room."""
    m = Mesh("dairy")
    W, D, H, T = 12.0, 8.0, 3.4, 0.2
    wall, zb = "aotearoa_weatherboard_cream", -0.5
    front, back = zb + D / 2, zb - D / 2
    m.box(-W / 2, W / 2, 0, 0.15, back, front + 1.0, "aotearoa_concrete", "floor", walk=True)
    m.wall_x(-W / 2, W / 2, front, T, 0.15, H, wall, "walls",
             openings=[(-5.0, -0.5, 0.7, 2.6), (0.5, 2.0, 0.15, 2.3), (2.6, 5.2, 0.7, 2.6)])
    m.wall_x(-W / 2, W / 2, back, T, 0.15, H, wall, "walls", openings=[(3.5, 4.4, 0.15, 2.1)])
    m.wall_z(back + T / 2, front - T / 2, -W / 2, T, 0.15, H, wall, "walls", openings=[(zb - 1.0, zb + 1.0, 1.0, 2.2)])
    m.wall_z(back + T / 2, front - T / 2, W / 2, T, 0.15, H, wall, "walls")
    m.wall_x(-W / 2 + T, W / 2 - T, back + 2.6, 0.1, 0.15, H, wall, "walls", openings=[(-4.5, -3.6, 0.15, 2.1)])
    window(m, -5.0, -0.5, 0.7, 2.6, front)
    window(m, 2.6, 5.2, 0.7, 2.6, front)
    window(m, zb - 1.0, zb + 1.0, 1.0, 2.2, -W / 2, along_x=False)
    m.box(-W / 2 - 0.1, W / 2 + 0.1, H, H + 0.15, back - 0.1, front + 0.1, "aotearoa_concrete", "roof", walk=True)
    m.box(-W / 2 - 0.1, W / 2 + 0.1, H + 0.15, H + 1.1, front - 0.05, front + 0.15, wall, "parapet")
    m.stretched([(-3.0, H + 0.2, front + 0.16), (3.0, H + 0.2, front + 0.16), (3.0, H + 1.05, front + 0.16),
                 (-3.0, H + 1.05, front + 0.16)], "aotearoa_dairy_sign", "sign")
    # Striped awning sloping out over the footpath.
    aw = [(-W / 2, 2.55, front + 1.8), (W / 2, 2.55, front + 1.8), (W / 2, 2.95, front + 0.1), (-W / 2, 2.95, front + 0.1)]
    start = len(m.verts)
    for p, uv in zip(aw, [(0, 0), (6, 0), (6, 0.5), (0, 0.5)]):
        m.verts.append(np.array(p))
        m.uvs.append(uv)
    m.faces.append(("awning", "aotearoa_dairy_sign", [(start + i + 1, start + i + 1) for i in range(4)]))
    m.faces.append(("awning", "aotearoa_dairy_sign", [(start + i + 1, start + i + 1) for i in (3, 2, 1, 0)]))
    m.box(-W / 2 + 0.4, -W / 2 + 4.4, 0.15, 1.05, back + 2.8, back + 3.4, "aotearoa_timber", "counter")
    for x in (-1.0, 1.5, 4.0):
        m.box(x, x + 0.5, 0.15, 1.9, back + 3.4, front - 1.2, "aotearoa_timber", "shelves")
    m.box(-W / 2 - 0.1, W / 2 + 0.1, H - 0.02, H, back, front, "aotearoa_concrete", "ceiling", solid=False, skip=("top",))
    for x0, x1 in ((-5.0, -0.5), (2.6, 5.2)):
        frame(m, x0, x1, 0.7, 2.6, front, T, w=0.1)
    frame(m, 0.5, 2.0, 0.15, 2.3, front, T, sill=False, w=0.1)
    frame(m, 3.5, 4.4, 0.15, 2.1, back, T, sill=False)
    # Stock on both faces of each shelf unit, a drinks fridge on the right wall, the till on the counter.
    for x in (-1.0, 1.5, 4.0):
        for fx, order in ((x - 0.01, (0, 1)), (x + 0.51, (1, 0))):
            z0, z1 = back + 3.5, front - 1.3
            zs = (z0, z1) if order == (0, 1) else (z1, z0)
            m.stretched([(fx, 0.2, zs[0]), (fx, 0.2, zs[1]), (fx, 1.85, zs[1]), (fx, 1.85, zs[0])], "aotearoa_shelf_goods",
                        "shelves")
    m.box(W / 2 - T / 2 - 0.75, W / 2 - T / 2, 0.15, 2.15, -1.6, 1.6, "aotearoa_trim_white", "fridge")
    m.stretched([(W / 2 - T / 2 - 0.76, 0.2, 1.55), (W / 2 - T / 2 - 0.76, 0.2, -1.55),
                 (W / 2 - T / 2 - 0.76, 2.1, -1.55), (W / 2 - T / 2 - 0.76, 2.1, 1.55)], "aotearoa_fridge", "fridge")
    m.box(-3.0, -2.5, 1.05, 1.3, back + 2.9, back + 3.3, "aotearoa_iron_grey", "counter", solid=False)
    # Out front: an ice cream sign board on the footpath, a bench seat and a letterbox.
    for side in (1, -1):
        zf = front + 1.2 + side * 0.2
        pts = [(4.4, 0.15, zf), (5.2, 0.15, zf), (5.2, 1.1, front + 1.2), (4.4, 1.1, front + 1.2)]
        if side < 0:
            pts = [pts[1], pts[0], pts[3], pts[2]]
        m.stretched(pts, "aotearoa_icecream_sign", "sign")
    m.box(-5.5, -3.5, 0.15, 0.6, front + 0.3, front + 0.7, "aotearoa_timber", "bench", walk=True)
    m.box(-W / 2 + 0.3, -W / 2 + 0.38, 0, 1.0, front + 0.9, front + 0.98, "aotearoa_timber", "letterbox", solid=False)
    m.box(-W / 2 + 0.15, -W / 2 + 0.55, 1.0, 1.3, front + 0.75, front + 1.15, "aotearoa_iron_roof_red", "letterbox",
          solid=False)
    # Back room: a table and a stack of cartons.
    table(m, -2.0, -0.6, back + 0.6, back + 1.6, 0.15)
    for k in range(3):
        m.box(2.0, 2.6, 0.15 + k * 0.4, 0.55 + k * 0.4, back + 0.3, back + 0.9, "aotearoa_burlap", "stock", solid=k == 0)
    return m


MODELS = {"sign_town": sign_town, "sign_post": sign_post, "bach": bach, "doc_hut": doc_hut, "woolshed": woolshed,
          "dairy": dairy}
BUILDINGS = {"bach": "Bach", "doc_hut": "DocHut", "woolshed": "Woolshed", "dairy": "Dairy"}
MAPGROUPPROTO = MAP_DIR / "mission" / "dayzOffline.aotearoa" / "mapgroupproto.aotearoa.xml"

# Loot points in model coordinates (x, height, z), the same as the OBJ files. The Geometry LOD needs the
# named property autocenter = 0 so the game keeps this origin. Each container: (name, categories, tags,
# lootmax, [(x, y, z, range, height), ...]); y is the surface the loot lies on.
LOOT = {
    "bach": dict(usages=["Village", "Town"], lootmax=7, containers=[
        ("lootFloor", ["food", "tools", "clothes", "containers"], ["floor"], 4,
         [(-3.5, 0.45, -1.0, 0.6, 1.0), (-1.0, 0.45, 0.6, 0.6, 1.0), (1.2, 0.45, 0.8, 0.5, 1.0),
          (3.0, 0.45, -0.6, 0.5, 1.0), (2.6, 0.45, 2.6, 0.6, 1.0), (2.95, 0.15, -6.0, 0.25, 1.0)]),
        ("lootshelves", ["food", "tools", "clothes"], ["shelves"], 3,
         [(-3.4, 1.39, -3.1, 0.25, 0.4), (-2.6, 1.39, -3.1, 0.25, 0.4), (-2.0, 1.2, -0.7, 0.3, 0.4),
          (2.6, 0.95, -2.4, 0.4, 0.4)]),
    ]),
    "doc_hut": dict(usages=["Hunting"], lootmax=6, containers=[
        ("lootFloor", ["food", "tools", "clothes", "containers"], ["floor"], 3,
         [(-1.5, 0.3, -1.0, 0.5, 1.0), (1.0, 0.3, 0.6, 0.5, 1.0), (-2.3, 0.3, 0.3, 0.4, 1.0), (0.0, 0.3, 2.2, 0.5, 1.0)]),
        ("lootshelves", ["food", "tools", "clothes"], ["shelves"], 3,
         [(-2.0, 0.92, -2.5, 0.4, 0.4), (0.0, 0.92, -2.5, 0.4, 0.4), (2.0, 0.92, -2.5, 0.4, 0.4),
          (-2.0, 1.92, -2.5, 0.4, 0.4), (0.0, 1.92, -2.5, 0.4, 0.4), (2.0, 1.92, -2.5, 0.4, 0.4),
          (1.1, 1.05, -0.45, 0.3, 0.4)]),
    ]),
    "woolshed": dict(usages=["Farm"], lootmax=7, containers=[
        ("lootFloor", ["tools", "clothes", "containers"], ["floor"], 5,
         [(-8.0, 1.25, 4.5, 0.8, 1.0), (0.0, 1.25, 4.5, 0.8, 1.0), (5.0, 1.2, -2.0, 0.8, 1.0),
          (-6.0, 1.2, -4.0, 0.8, 1.0), (2.0, 1.2, -4.0, 0.8, 1.0), (11.5, 1.2, -3.2, 0.5, 1.0),
          (-8.0, 0.12, -8.5, 1.5, 1.0)]),
        ("lootshelves", ["tools", "clothes"], ["shelves"], 2, [(7.5, 2.13, 0.4, 0.8, 0.4), (6.5, 2.13, -0.2, 0.4, 0.4)]),
    ]),
    "dairy": dict(usages=["Town", "Village"], lootmax=9, containers=[
        ("lootFloor", ["food", "tools", "containers"], ["floor"], 4,
         [(-3.0, 0.15, 1.5, 0.6, 1.0), (0.7, 0.15, 0.0, 0.4, 1.0), (3.2, 0.15, 0.0, 0.4, 1.0), (-4.5, 0.15, 2.6, 0.5, 1.0),
          (-1.3, 0.9, -3.4, 0.4, 0.4), (2.3, 1.35, -3.9, 0.3, 0.4), (0.5, 0.15, -3.2, 0.6, 1.0)]),
        ("lootshelves", ["food"], ["shelves"], 5,
         [(-0.75, 1.9, 0.5, 0.3, 0.3), (1.75, 1.9, 0.5, 0.3, 0.3), (4.25, 1.9, 0.5, 0.3, 0.3),
          (-4.0, 1.05, -1.4, 0.4, 0.3), (4.7, 0.15, 0.8, 0.4, 1.0), (4.7, 0.15, -0.8, 0.4, 1.0)]),
    ]),
}


def mapgroupproto_text() -> str:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>',
           "<!-- Loot points for the Aotearoa buildings, generated by tools/make_models.py. pack.bat adds each",
           "     group to the server's mapgroupproto.xml once the building's .p3d exists. -->",
           "<prototype>"]
    for name, cls in BUILDINGS.items():
        spec = LOOT[name]
        out.append(f'    <group name="Land_Aotearoa_{cls}" lootmax="{spec["lootmax"]}">')
        out += [f'        <usage name="{u}" />' for u in spec["usages"]]
        for cname, cats, tags, lootmax, points in spec["containers"]:
            out.append(f'        <container name="{cname}" lootmax="{lootmax}">')
            out += [f'            <category name="{c}" />' for c in cats]
            out += [f'            <tag name="{t}" />' for t in tags]
            out += [f'            <point pos="{x:.3f} {y:.3f} {z:.3f}" range="{r:.3f}" height="{h:.3f}" flags="32" />'
                    for x, y, z, r, h in points]
            out.append("        </container>")
        out.append("    </group>")
    out.append("</prototype>")
    return "\n".join(out) + "\n"


def render(m: Mesh, path: Path) -> None:
    """Flat-shaded three-quarter view with a z-buffer, using each material's average colour."""
    colours = {}
    for name, (_, fn) in TEXTURES.items():
        colours[name] = np.asarray(fn().resize((1, 1), Image.BOX))[0, 0].astype(float)
    yaw, pitch = math.radians(35), math.radians(25)
    rot = np.array([[math.cos(yaw), 0, -math.sin(yaw)], [0, 1, 0], [math.sin(yaw), 0, math.cos(yaw)]])
    tilt = np.array([[1, 0, 0], [0, math.cos(pitch), -math.sin(pitch)], [0, math.sin(pitch), math.cos(pitch)]])
    view = tilt @ rot
    verts = np.array(m.verts) @ view.T
    span = max(np.ptp(verts[:, 0]), np.ptp(verts[:, 1])) or 1.0
    size = 640
    scale = 560 / span
    cx, cy = verts[:, 0].mean(), verts[:, 1].mean()
    light = np.array([0.4, 0.8, 0.45])
    light /= np.linalg.norm(light)
    img = np.ones((size, size, 3)) * np.array([214.0, 226.0, 236.0])
    zbuf = np.full((size, size), -np.inf)
    for group, mat, idx in m.faces:
        world = np.array([m.verts[v - 1] for v, _ in idx])
        n = np.cross(world[1] - world[0], world[-1] - world[0])
        if np.linalg.norm(n) == 0:
            continue
        n /= np.linalg.norm(n)
        col = np.clip(colours.get(mat, np.array([200.0, 200.0, 200.0])) * (0.45 + 0.55 * abs(float(n @ light))), 0, 255)
        pts = np.array([verts[v - 1] for v, _ in idx])
        sx = size / 2 + (pts[:, 0] - cx) * scale
        sy = size / 2 - (pts[:, 1] - cy) * scale
        for k in range(1, len(pts) - 1):
            tri = (0, k, k + 1)
            xs_, ys_, zs_ = sx[list(tri)], sy[list(tri)], pts[list(tri), 2]
            x0, x1 = int(max(xs_.min(), 0)), int(min(xs_.max() + 1, size))
            y0, y1 = int(max(ys_.min(), 0)), int(min(ys_.max() + 1, size))
            if x0 >= x1 or y0 >= y1:
                continue
            (ax, bx, cx_), (ay, by, cy_) = xs_, ys_
            den = (by - cy_) * (ax - cx_) + (cx_ - bx) * (ay - cy_)
            if abs(den) < 1e-9:
                continue
            yy, xx = np.mgrid[y0:y1, x0:x1] + 0.5
            w0 = ((by - cy_) * (xx - cx_) + (cx_ - bx) * (yy - cy_)) / den
            w1 = ((cy_ - ay) * (xx - cx_) + (ax - cx_) * (yy - cy_)) / den
            w2 = 1 - w0 - w1
            z = w0 * zs_[0] + w1 * zs_[1] + w2 * zs_[2]
            sub = zbuf[y0:y1, x0:x1]
            hit = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6) & (z > sub + 1e-4)
            sub[hit] = z[hit]
            img[y0:y1, x0:x1][hit] = col
    out = Image.fromarray(img.astype(np.uint8))
    ImageDraw.Draw(out).text((10, 10), f"{m.name}: {m.tris()} triangles, {len(m.components)} geometry components",
                             fill=(30, 30, 30))
    out.save(path, optimize=True)


def write_config() -> None:
    lines = ["// Custom building classes, generated by tools/make_models.py. Included inside CfgVehicles in config.cpp.",
             "// Each needs its model (docs/CUSTOM_MODELS.md) before it is placed."]
    for name, cls in BUILDINGS.items():
        lines += [f"class Land_Aotearoa_{cls}: HouseNoDestruct", "{", "\tscope = 1;",
                  f'\tmodel = "\\maps\\aotearoa\\structures\\{name}\\{name}.p3d";', "};"]
    (MAP_DIR / "config" / "structures.hpp").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\r\n")


def main() -> None:
    TEX_DIR.mkdir(parents=True, exist_ok=True)
    for name, (_, fn) in TEXTURES.items():
        fn().save(TEX_DIR / f"{name}.png", optimize=True)
    for name, make in MODELS.items():
        m = make()
        m.write()
        render(m, MAP_DIR / "preview" / f"models_{name}.png")
        print(f"{name}: {m.tris()} triangles, {len(m.components)} geometry components, {len(m.roadway)} roadway faces")
    write_config()
    MAPGROUPPROTO.write_text(mapgroupproto_text(), encoding="utf-8")
    print(f"Wrote {MAPGROUPPROTO.relative_to(MAP_DIR)}: loot points for {len(LOOT)} buildings")


if __name__ == "__main__":
    main()
