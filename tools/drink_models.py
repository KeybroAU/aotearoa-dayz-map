"""Custom food and drink models, ready to build in Object Builder.

    python drink_models.py

Models (sizes are the real packs, metres, y up, origin at the centre so they sit on the ground and in
the hands like the vanilla items):

  v_can             V energy drink: a tall 500 ml can, 66 mm across and 168 mm tall, with a ring pull
  watties_tin       Wattie's 420 g tins (baked beans, spaghetti, peaches): 75 mm across, 112 mm tall
  lp_bottle         L&P 1.5 litre bottle: 92 mm across, 331 mm tall
  whittakers_block  Whittaker's 250 g blocks (Creamy Milk, Dark Ghana, Peanut Slab): 165 x 80 x 18 mm

For each model it writes:

  docs/models/<model>.obj, <model>_lod1.obj, <model>_lod2.obj   resolution LODs
  docs/models/<model>_geometry.obj                              Geometry: one closed convex component
  docs/models/<model>.mtl                                       the material, pointing at a texture
  data/food/models/<model>.rvmat                                the material (shiny metal, plastic or foil)
  preview/models_<model>.png                                    renders and the texture

and for each item that uses it data/food/models/<item>.png, the item's texture in the model's UV layout
(every item on a model shares its UVs, so one .p3d serves them all). Every face is in the "camo" named
selection, which the config retextures.

Lathed models (cans, tins, bottles) put the label round the top of the texture (front centred at u = 0.5,
the seam at the back), plain bands below it, and the top and bottom discs along the bottom. The block puts
its front in the top half, its back in the bottom half and the edges in a strip along the bottom.

nz_food.py uses a model once its .p3d is saved under P:\\maps\\aotearoa\\structures\\food\\<model>\\
(docs/CUSTOM_MODELS.md, item 12); until then the items stay retextured vanilla packs. Opened tins always
use the vanilla opened model.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import nz_food as nf
from sign_handoff import rvmat

MAP_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = MAP_DIR / "docs" / "models"
TEX_DIR = MAP_DIR / "data" / "food" / "models"
TEX = 1024

V_GREEN = (88, 182, 34)
V_DARK = (16, 46, 14)
LP_AMBER = (214, 150, 40)

# Lathed models: the outline from the middle of the base, round the outside, to the middle of the top:
# (radius, height above the base, part). Each face takes the part of its lower point; parts pick where the
# faces sit on the texture: "label" and the bands by rows, "top" and "base" on the discs.
LATHES = {
    "v_can": dict(
        radius=0.033, height=0.168, mass=0.5, shine=(0.6, 70),
        profile=[(0.0, 0.010, "base"), (0.017, 0.007, "base"), (0.025, 0.0, "base"), (0.029, 0.002, "ring"),
                 (0.0322, 0.007, "ring"), (0.033, 0.014, "label"), (0.033, 0.150, "neck"), (0.0315, 0.157, "neck"),
                 (0.0278, 0.1635, "neck"), (0.0273, 0.168, "top"), (0.0262, 0.1684, "top"), (0.0254, 0.1652, "top"),
                 (0.0, 0.1655, "top")],
        lod=(0, 2, 4, 5, 6, 8, 9, 12),
        rows={"label": (0.0, 0.68), "neck": (0.70, 0.74), "ring": (0.74, 0.78)},
        items=["v_energy"]),
    "watties_tin": dict(
        radius=0.0375, height=0.112, mass=0.45, shine=(0.45, 40),
        profile=[(0.0, 0.004, "base"), (0.030, 0.003, "base"), (0.0365, 0.0, "ring"), (0.0375, 0.004, "ring"),
                 (0.0368, 0.008, "label"), (0.0368, 0.104, "neck"), (0.0375, 0.108, "neck"),
                 (0.0375, 0.112, "top"), (0.0352, 0.1116, "top"), (0.0340, 0.1085, "top"), (0.0, 0.1085, "top")],
        lod=(0, 2, 4, 5, 7, 10),
        rows={"label": (0.0, 0.66), "neck": (0.68, 0.72), "ring": (0.72, 0.76)},
        items=["watties_beans", "watties_spaghetti", "watties_peaches"]),
    "lp_bottle": dict(
        radius=0.046, height=0.331, mass=1.6, shine=(0.7, 90),
        profile=[(0.0, 0.006, "base"), (0.018, 0.0, "base"), (0.034, 0.003, "base"), (0.043, 0.014, "body"),
                 (0.046, 0.030, "body"), (0.046, 0.110, "label"), (0.046, 0.210, "body"), (0.046, 0.235, "body"),
                 (0.040, 0.262, "body"), (0.028, 0.285, "body"), (0.0145, 0.303, "cap"), (0.0155, 0.305, "cap"),
                 (0.0155, 0.330, "top"), (0.0, 0.331, "top")],
        lod=(0, 2, 4, 5, 6, 8, 10, 12, 13),
        rows={"label": (0.0, 0.40), "body": (0.42, 0.72), "cap": (0.72, 0.76)},
        items=["lp_bottle"]),
}
DISCS = {"top": (0.25, 0.89, 0.105), "base": (0.75, 0.89, 0.105)}

# The block: length along x, thickness along y, width along z, the front facing up.
BLOCK = dict(size=(0.165, 0.018, 0.080), mass=0.25, shine=(0.35, 30),
             rows={"front": (0.0, 0.48), "back": (0.49, 0.97), "edge": (0.975, 0.995)},
             items=["whittakers_milk", "whittakers_dark", "whittakers_peanut"])

MODEL_ITEMS = {**{k: m["items"] for k, m in LATHES.items()}, "whittakers_block": BLOCK["items"]}


def _uv_disc(disc, r, theta, r_max):
    cx, cy, rr = disc
    k = rr * r / r_max
    return cx + k * math.sin(theta), 1.0 - (cy - k * math.cos(theta))


def _part_y(spec):
    """Each banded part's height range, from the faces that use it."""
    out = {}
    prof = spec["profile"]
    for (_, y0, p), (_, y1, _) in zip(prof, prof[1:]):
        lo, hi = out.get(p, (math.inf, -math.inf))
        out[p] = (min(lo, y0, y1), max(hi, y0, y1))
    return out


def lathe(spec, sides: int, profile) -> tuple[list, list, list]:
    """Vertices, UVs and quads (each [(v, vt) x 4], 1-based) turned from the profile."""
    verts, uvs, faces = [], [], []
    ranges = _part_y(spec)
    height, radius = spec["height"], spec["radius"]

    def uv(r, y, part, theta, i):
        u = i / sides
        if part in spec["rows"]:
            lo, hi = ranges[part]
            rows = spec["rows"][part]
            t = min(max((y - lo) / (hi - lo), 0), 1)
            return u, 1.0 - (rows[1] - t * (rows[1] - rows[0]))
        return _uv_disc(DISCS[part], r, theta, radius)

    for j in range(len(profile) - 1):
        (r0, y0, part), (r1, y1, _) = profile[j], profile[j + 1]
        for i in range(sides):
            quad = []
            for (r, y), k in (((r0, y0), i), ((r0, y0), i + 1), ((r1, y1), i + 1), ((r1, y1), i)):
                theta = -math.pi + 2 * math.pi * k / sides
                verts.append((r * math.sin(theta), y - height / 2, r * math.cos(theta)))
                uvs.append(uv(r, y, part, theta, k))
                quad.append((len(verts), len(uvs)))
            pts = [np.array(verts[v - 1]) for v, _ in quad]
            if np.linalg.norm(pts[0] - pts[3]) < 1e-9 and np.linalg.norm(pts[1] - pts[2]) < 1e-9:
                continue
            faces.append(quad)
    return verts, uvs, faces


def tab_quads(spec) -> tuple[list, list, list]:
    """The V can's ring pull: a flat tab on the lid from the rivet towards the back."""
    y = 0.1660 - spec["height"] / 2
    corners = [(-0.006, -0.019), (0.006, -0.019), (0.006, 0.002), (-0.006, 0.002)]
    verts, uvs = [], []
    for x, z in corners:
        verts.append((x, y, z))
        uvs.append(_uv_disc(DISCS["top"], math.hypot(x, z), math.atan2(x, z), spec["radius"]))
    return verts, uvs, [[(i + 1, i + 1) for i in range(4)]]


def block_mesh() -> tuple[list, list, list]:
    """The block as six faces; the front and back each fill their half of the texture."""
    lx, ly, lz = (s / 2 for s in BLOCK["size"])
    rows = BLOCK["rows"]
    verts, uvs, faces = [], [], []

    def face(corners, uv_rect):
        u0, r0, u1, r1 = uv_rect
        quad = []
        for (x, y, z), (u, r) in zip(corners, ((u0, r1), (u1, r1), (u1, r0), (u0, r0))):
            verts.append((x, y, z))
            uvs.append((u, 1.0 - r))
            quad.append((len(verts), len(uvs)))
        faces.append(quad)

    f, b, e = rows["front"], rows["back"], rows["edge"]
    face([(-lx, ly, lz), (lx, ly, lz), (lx, ly, -lz), (-lx, ly, -lz)], (0.0, f[0], 1.0, f[1]))
    face([(lx, -ly, lz), (-lx, -ly, lz), (-lx, -ly, -lz), (lx, -ly, -lz)], (0.0, b[0], 1.0, b[1]))
    face([(-lx, -ly, lz), (lx, -ly, lz), (lx, ly, lz), (-lx, ly, lz)], (0.0, e[0], 1.0, e[1]))
    face([(lx, -ly, -lz), (-lx, -ly, -lz), (-lx, ly, -lz), (lx, ly, -lz)], (0.0, e[0], 1.0, e[1]))
    face([(lx, -ly, lz), (lx, -ly, -lz), (lx, ly, -lz), (lx, ly, lz)], (0.0, e[0], 0.5, e[1]))
    face([(-lx, -ly, -lz), (-lx, -ly, lz), (-lx, ly, lz), (-lx, ly, -lz)], (0.5, e[0], 1.0, e[1]))
    return verts, uvs, faces


def write_obj(path: Path, name: str, parts, comment: str) -> int:
    out = [f"# {comment}: generated by tools/drink_models.py. Metres, y up, front faces +z.", f"mtllib {name}.mtl"]
    v_off = t_off = 0
    body = []
    tris = 0
    for group, (verts, uvs, faces) in parts:
        out += [f"v {x:.5f} {y:.5f} {z:.5f}" for x, y, z in verts]
        out += [f"vt {u:.5f} {v:.5f}" for u, v in uvs]
        body += [f"g {group}", f"usemtl {name}"]
        for q in faces:
            body.append("f " + " ".join(f"{v + v_off}/{t + t_off}" for v, t in q))
            tris += len(q) - 2
        v_off += len(verts)
        t_off += len(uvs)
    path.write_text("\n".join(out + body) + "\n")
    return tris


def write_geometry(path: Path, name: str, mass: float, prism=None, box=None) -> None:
    out = [f"# {name} Geometry: one closed convex component. Name its selection Component01 and give the LOD "
           f"a mass of {mass} kg and the named property autocenter = 0."]
    if prism:
        radius, height = prism
        n = 8
        for y in (-height / 2, height / 2):
            for i in range(n):
                t = 2 * math.pi * i / n
                out.append(f"v {radius * math.sin(t):.5f} {y:.5f} {radius * math.cos(t):.5f}")
        out.append("g Component01")
        out.append("f " + " ".join(str(i + 1) for i in reversed(range(n))))
        out.append("f " + " ".join(str(n + i + 1) for i in range(n)))
        for i in range(n):
            a, b = i + 1, (i + 1) % n + 1
            out.append(f"f {a} {b} {n + b} {n + a}")
    else:
        lx, ly, lz = (s / 2 for s in box)
        for x, y, z in ((-lx, -ly, -lz), (lx, -ly, -lz), (lx, -ly, lz), (-lx, -ly, lz),
                        (-lx, ly, -lz), (lx, ly, -lz), (lx, ly, lz), (-lx, ly, lz)):
            out.append(f"v {x:.5f} {y:.5f} {z:.5f}")
        out.append("g Component01")
        out += ["f 1 2 3 4", "f 8 7 6 5", "f 1 5 6 2", "f 2 6 7 3", "f 3 7 8 4", "f 4 8 5 1"]
    path.write_text("\n".join(out) + "\n")


def shade(c, k):
    return nf.shade(c, k)


def disc_box(disc, frac=1.0):
    cx, cy, r = disc[0] * TEX, disc[1] * TEX, disc[2] * TEX * frac
    return (cx - r, cy - r, cx + r, cy + r)


def can_lid(d: ImageDraw.ImageDraw, disc, tab_col):
    cx, cy, r = disc[0] * TEX, disc[1] * TEX, disc[2] * TEX
    for frac, col in ((1.0, (150, 152, 156)), (0.97, (198, 200, 204)), (0.92, (170, 172, 176)), (0.86, (205, 207, 211))):
        d.ellipse(disc_box(disc, frac), fill=col)
    # The opening (keyhole) towards the front, the rivet, and the ring pull over them. Up on the disc is
    # the front of the can.
    d.rounded_rectangle((cx - 0.22 * r, cy - 0.62 * r, cx + 0.22 * r, cy - 0.12 * r), radius=int(0.16 * r),
                        outline=(140, 142, 146), width=4)
    d.ellipse((cx - 0.08 * r, cy - 0.08 * r, cx + 0.08 * r, cy + 0.08 * r), fill=(160, 162, 166))
    d.rounded_rectangle((cx - 0.22 * r, cy - 0.06 * r, cx + 0.22 * r, cy + 0.72 * r), radius=int(0.18 * r),
                        fill=tab_col, outline=shade(tab_col, 0.55), width=4)
    d.rounded_rectangle((cx - 0.12 * r, cy + 0.3 * r, cx + 0.12 * r, cy + 0.6 * r), radius=int(0.1 * r),
                        fill=(198, 200, 204))


def tin_end(d: ImageDraw.ImageDraw, disc, rings=(0.6, 0.45), mark=None, ring_pull=False):
    cx, cy, r = disc[0] * TEX, disc[1] * TEX, disc[2] * TEX
    for frac, col in ((1.0, (150, 152, 156)), (0.96, (200, 202, 206)), (0.9, (172, 174, 178)), (0.86, (196, 198, 202))):
        d.ellipse(disc_box(disc, frac), fill=col)
    for frac in rings:
        d.ellipse(disc_box(disc, frac), outline=(160, 162, 166), width=3)
    if ring_pull:
        d.ellipse(disc_box(disc, 0.8), outline=(150, 152, 156), width=4)
        d.ellipse((cx - 0.1 * r, cy - 0.62 * r, cx + 0.1 * r, cy - 0.42 * r), fill=(165, 167, 171))
        d.rounded_rectangle((cx - 0.2 * r, cy - 0.78 * r, cx + 0.2 * r, cy - 0.3 * r), radius=int(0.18 * r),
                            outline=(130, 132, 136), width=6)
    if mark:
        nf.text(d, (cx, cy), mark, "plain", 0.6 * r, 0.12 * r, (140, 142, 146))


def big_v(d: ImageDraw.ImageDraw, cx, top, h):
    """The V: two slanted strokes meeting at a point, black outline, a lime highlight down one side."""
    w = 0.92 * h
    s = 0.27 * w
    outer = [(cx - w / 2, top), (cx - w / 2 + s, top), (cx, top + 0.7 * h), (cx + w / 2 - s, top), (cx + w / 2, top),
             (cx + 0.09 * w, top + h), (cx - 0.09 * w, top + h)]
    d.polygon(outer, fill=(18, 18, 18))
    k = 0.86
    inner = [(cx + (x - cx) * k, top + 0.06 * h + (y - top) * k * 0.98) for x, y in outer]
    d.polygon(inner, fill=(255, 255, 255))
    hi = [(cx + (x - cx) * 0.72, top + 0.12 * h + (y - top) * 0.8) for x, y in outer]
    d.polygon(hi, fill=(186, 240, 60))
    d.line([hi[0], hi[-1]], fill=(255, 255, 255), width=max(2, int(h / 60)))


def barcode(d: ImageDraw.ImageDraw, box, rng):
    x0, y0, x1, y1 = box
    d.rectangle((x0 - 8, y0 - 8, x1 + 8, y1 + 8), fill=(255, 255, 255))
    x = x0
    while x < x1:
        bar = rng.choice((2, 3, 5))
        d.rectangle((x, y0, x + bar - 1, y1), fill=(10, 10, 10))
        x += bar + rng.choice((2, 3, 4))


def v_label(w, h, item, rng) -> Image.Image:
    im = Image.new("RGB", (w, h), V_GREEN)
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / h
        col = tuple(int(a * (1 - t ** 2.2) + b * t ** 2.2) for a, b in zip(shade(V_GREEN, 1.1), V_DARK))
        d.line((0, y, w, y), fill=col)
    # Energy streaks rising diagonally round the whole can.
    streaks = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(streaks)
    for _ in range(26):
        x, wid = rng.uniform(-0.3 * w, w), rng.uniform(6, 26)
        sd.polygon([(x, h), (x + wid, h), (x + wid + 0.45 * h, 0), (x + 0.45 * h, 0)],
                   fill=(210, 255, 120, rng.randint(25, 70)))
    im.paste(streaks, (0, 0), streaks.filter(ImageFilter.GaussianBlur(3)))
    d = ImageDraw.Draw(im)
    for y0, col in ((0.0, (14, 14, 14)), (0.965, (14, 14, 14))):
        d.rectangle((0, y0 * h, w, (y0 + 0.035) * h), fill=col)
    fx = 0.5 * w
    big_v(d, fx, 0.1 * h, 0.5 * h)
    nf.text(d, (fx, 0.7 * h), "ENERGY DRINK", "sans", 0.25 * w, 0.075 * h, (255, 255, 255), 3, (14, 14, 14))
    nf.text(d, (fx, 0.79 * h), "with guarana", "italic", 0.17 * w, 0.045 * h, (200, 245, 90), 2, (14, 14, 14))
    nf.text(d, (fx, 0.9 * h), "500 ml", "sans", 0.1 * w, 0.045 * h, (255, 255, 255))
    for sx in (0.2, 0.8):
        big_v(d, sx * w, 0.18 * h, 0.2 * h)
        nf.text(d, (sx * w, 0.48 * h), "THE ORIGINAL", "sans", 0.14 * w, 0.04 * h, (255, 255, 255), 2, (14, 14, 14))
        nf.text(d, (sx * w, 0.54 * h), "KIWI ENERGY", "sans", 0.14 * w, 0.04 * h, (255, 255, 255), 2, (14, 14, 14))
    lines = ["NUTRITION INFORMATION", "Servings per can: 2", "Energy 195 kJ / 100 ml", "Sugars 11.2 g / 100 ml",
             "Caffeine 31 mg / 100 ml", "", "Contains caffeine. Not", "recommended for children,", "pregnant women or",
             "people sensitive to caffeine.", "Made in New Zealand"]
    return back_panel(im, lines, rng)


def back_panel(im: Image.Image, lines, rng, width=0.36) -> Image.Image:
    """Small print and a barcode on a panel across the seam at the back."""
    w, h = im.size
    back = Image.new("RGB", (int(width * w), h), (0, 0, 0))
    bw = back.width
    back.paste(im.crop((0, 0, bw // 2, h)), (bw - bw // 2, 0))
    back.paste(im.crop((w - (bw - bw // 2), 0, w, h)), (0, 0))
    bd = ImageDraw.Draw(back)
    bd.rounded_rectangle((0.14 * bw, 0.14 * h, 0.86 * bw, 0.62 * h), radius=12, fill=(245, 245, 240),
                         outline=(14, 14, 14), width=3)
    for k, ln in enumerate(lines):
        if ln:
            nf.text(bd, (0.5 * bw, (0.18 + 0.04 * k) * h), ln, "sans" if k == 0 else "plain", 0.66 * bw, 0.03 * h,
                    (20, 20, 20))
    barcode(bd, (0.24 * bw, 0.68 * h, 0.76 * bw, 0.84 * h), rng)
    im.paste(back.crop((bw - bw // 2, 0, bw, h)), (0, 0))
    im.paste(back.crop((0, 0, bw - bw // 2, h)), (w - (bw - bw // 2), 0))
    return nf.wear(im, rng, 6)


def centred_label(w, h, item, repeats, rng) -> Image.Image:
    """nz_food's wrap-round label, turned so the first front is centred at u = 0.5."""
    im = nf.label(w, h, item, repeats, rng)
    period = w / repeats
    fw = int(period) - (int(period * 0.28) if item.layout in ("soda", "tin") else 0)
    return Image.fromarray(np.roll(np.asarray(im), int(w / 2 - fw / 2), axis=1))


def tin_label(w, h, item, rng) -> Image.Image:
    im = centred_label(w, h, item, 1, rng)
    d = ImageDraw.Draw(im)
    for y0 in (0.0, 0.985):
        d.rectangle((0, y0 * h, w, (y0 + 0.015) * h), fill=shade(item.art["bg2"], 0.8))
    return nf.wear(im, rng, 8)


def bottle_label(w, h, item, rng) -> Image.Image:
    im = centred_label(w, h, item, 2, rng)
    d = ImageDraw.Draw(im)
    for y0 in (0.0, 0.97):
        d.rectangle((0, y0 * h, w, (y0 + 0.03) * h), fill=shade(item.art["bg2"], 0.9))
    nf.text(d, (0.5 * w, 0.93 * h), "1.5 L", "sans", 0.08 * w, 0.06 * h, item.art["fg"])
    return nf.wear(im, rng, 4)


LABELS = {"v_can": v_label, "watties_tin": tin_label, "lp_bottle": bottle_label}


def lathe_texture(model: str, item) -> Image.Image:
    spec = LATHES[model]
    rng = random.Random(f"{model}/{item.key}")
    rows = spec["rows"]
    im = nf.metal((TEX, TEX), rng).point(lambda v: min(255, int(v * 1.08)))
    d = ImageDraw.Draw(im)
    if model == "lp_bottle":
        # Clear PET with the drink behind it: amber, lighter towards the top, with vertical highlights.
        lo, hi = rows["body"]
        for y in range(int(lo * TEX), int(hi * TEX) + 1):
            t = (y - lo * TEX) / ((hi - lo) * TEX)
            d.line((0, y, TEX, y), fill=shade(LP_AMBER, 0.85 + 0.35 * (1 - t)))
        for u in (0.12, 0.38, 0.62, 0.88):
            d.rectangle((u * TEX - 6, lo * TEX, u * TEX + 6, hi * TEX), fill=shade(LP_AMBER, 1.35))
        c0, c1 = rows["cap"]
        d.rectangle((0, c0 * TEX, TEX, c1 * TEX), fill=(120, 72, 30))
        for x in range(0, TEX, 10):
            d.line((x, c0 * TEX, x, c1 * TEX), fill=(90, 52, 20), width=3)
        d.ellipse(disc_box(DISCS["top"]), fill=(120, 72, 30))
        d.ellipse(disc_box(DISCS["top"], 0.86), fill=(135, 82, 34))
        nf.text(d, (DISCS["top"][0] * TEX, DISCS["top"][1] * TEX), "L&P", "serif", 0.12 * TEX, 0.06 * TEX,
                (250, 205, 30))
        d.ellipse(disc_box(DISCS["base"]), fill=shade(LP_AMBER, 0.8))
        cx, cy, r = DISCS["base"][0] * TEX, DISCS["base"][1] * TEX, DISCS["base"][2] * TEX
        for k in range(5):
            t = 2 * math.pi * k / 5
            d.ellipse((cx + 0.55 * r * math.sin(t) - 0.28 * r, cy - 0.55 * r * math.cos(t) - 0.28 * r,
                       cx + 0.55 * r * math.sin(t) + 0.28 * r, cy - 0.55 * r * math.cos(t) + 0.28 * r),
                      fill=shade(LP_AMBER, 1.05))
    else:
        for part, col in (("neck", (196, 198, 202)), ("ring", (176, 178, 182))):
            r0, r1 = rows[part]
            d.rectangle((0, r0 * TEX, TEX, r1 * TEX), fill=col)
            for k in range(4):
                y = (r0 + (r1 - r0) * (k + 0.5) / 4) * TEX
                d.line((0, y, TEX, y), fill=shade(col, 0.88), width=2)
        if model == "v_can":
            can_lid(d, DISCS["top"], V_GREEN)
            tin_end(d, DISCS["base"])
            cx, cy, r = DISCS["base"][0] * TEX, DISCS["base"][1] * TEX, DISCS["base"][2] * TEX
            nf.text(d, (cx, cy), "V", "italic", 0.4 * r, 0.3 * r, (150, 152, 156))
        else:
            tin_end(d, DISCS["top"], rings=(0.66, 0.52), ring_pull=True)
            tin_end(d, DISCS["base"], rings=(0.7, 0.55, 0.4), mark="BEST BEFORE 2031")
    l0, l1 = rows["label"]
    im.paste(LABELS[model](TEX, int((l1 - l0) * TEX), item, rng), (0, int(l0 * TEX)))
    return im


def block_face(w, h, item, rng) -> Image.Image:
    """The front of a Whittaker's block: the brand and the flavour on its colour, gold rules, a square of chocolate."""
    a = item.art
    im = Image.new("RGB", (w, h), a["bg"])
    d = ImageDraw.Draw(im)
    for y in range(h):
        d.line((0, y, w, y), fill=shade(a["bg"], 1.08 - 0.16 * y / h))
    gold = a["bg2"]
    for y0 in (0.06, 0.9):
        d.rectangle((0, y0 * h, w, (y0 + 0.04) * h), fill=gold)
    d.rectangle((0.03 * w, 0.14 * h, 0.97 * w, 0.86 * h), outline=gold, width=4)
    stroke = shade(a["bg"], 0.45) if sum(a["fg"]) > 500 else (255, 255, 255)
    nf.text(d, (0.5 * w, 0.34 * h), a["brand"], "script", 0.6 * w, 0.28 * h, a["fg"], 3, stroke)
    nf.text(d, (0.5 * w, 0.58 * h), a["sub"], "sans", 0.62 * w, 0.13 * h, a["fg"], 2, stroke)
    nf.text(d, (0.5 * w, 0.73 * h), a["tag"], "italic", 0.4 * w, 0.07 * h, gold, 1, shade(a["bg"], 0.5))
    nf.text(d, (0.88 * w, 0.78 * h), "250g", "sans", 0.1 * w, 0.07 * h, a["fg"], 1, stroke)
    sq = 0.2 * h
    for x0 in (0.08 * w, 0.92 * w - 2 * sq):
        for i in range(2):
            for j in range(2):
                x, y = x0 + i * sq, 0.4 * h + j * sq * 0.9
                d.rectangle((x, y, x + sq * 0.92, y + sq * 0.82), fill=(92, 52, 30) if "DARK" not in a["sub"] else
                            (60, 32, 22), outline=(58, 32, 18), width=3)
                d.line((x + 6, y + 6, x + sq * 0.8, y + 6), fill=(130, 82, 52), width=3)
    return nf.wear(im, rng, 6)


def block_back(w, h, item, rng) -> Image.Image:
    a = item.art
    im = Image.new("RGB", (w, h), a["bg"])
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0.06 * w, 0.12 * h, 0.6 * w, 0.88 * h), radius=14, fill=(245, 242, 232), outline=a["bg2"],
                        width=4)
    lines = ["NUTRITION INFORMATION", "Servings per pack: 10", "Energy 2250 kJ / 100 g", "Fat 32 g / 100 g",
             "Sugars 50 g / 100 g", "", "Ingredients: sugar, cocoa butter,", "cocoa mass, milk solids, emulsifier",
             "(soy lecithin). May contain nuts.", "Made by J.H. Whittaker & Sons,", "Porirua, New Zealand"]
    for k, ln in enumerate(lines):
        if ln:
            nf.text(d, (0.33 * w, (0.2 + 0.062 * k) * h), ln, "sans" if k == 0 else "plain", 0.5 * w, 0.05 * h,
                    (30, 25, 20))
    nf.text(d, (0.8 * w, 0.3 * h), "Whittaker's", "script", 0.3 * w, 0.14 * h, a["fg"])
    nf.text(d, (0.8 * w, 0.45 * h), "Good Honest Chocolate", "italic", 0.32 * w, 0.06 * h, a["bg2"])
    barcode(d, (0.68 * w, 0.58 * h, 0.92 * w, 0.82 * h), rng)
    return nf.wear(im, rng, 6)


def block_texture(item) -> Image.Image:
    rng = random.Random(f"whittakers_block/{item.key}")
    rows = BLOCK["rows"]
    im = Image.new("RGB", (TEX, TEX), item.art["bg"])
    for part, paint in (("front", block_face), ("back", block_back)):
        r0, r1 = rows[part]
        im.paste(paint(TEX, int((r1 - r0) * TEX), item, rng), (0, int(r0 * TEX)))
    d = ImageDraw.Draw(im)
    e0, e1 = rows["edge"]
    d.rectangle((0, e0 * TEX, TEX, e1 * TEX), fill=item.art["bg2"])
    return im


def render(name: str, parts, tex: Image.Image) -> Image.Image:
    """Shaded views of the model (front, side, back from above) beside its texture, by a small z-buffer rasteriser."""
    arr = np.asarray(tex.convert("RGB")).astype(float) / 255.0
    th, tw = arr.shape[:2]
    tris = []
    for _, (verts, uvs, faces) in parts:
        for q in faces:
            for k in range(1, len(q) - 1):
                tris.append([(verts[q[i][0] - 1], uvs[q[i][1] - 1]) for i in (0, k, k + 1)])
    P = np.array([[v for v, _ in t] for t in tris])
    T = np.array([[uv for _, uv in t] for t in tris])
    extent = np.abs(P).max() * 2.3
    size = 420
    light = np.array([0.4, 0.75, 0.55])
    light /= np.linalg.norm(light)
    views = []
    for yaw in (0.0, 90.0, 180.0):
        yr, pr = math.radians(yaw), math.radians(25)
        ry = np.array([[math.cos(yr), 0, math.sin(yr)], [0, 1, 0], [-math.sin(yr), 0, math.cos(yr)]])
        rx = np.array([[1, 0, 0], [0, math.cos(pr), -math.sin(pr)], [0, math.sin(pr), math.cos(pr)]])
        Q = P @ ry.T @ rx.T
        img = np.ones((size, size, 3)) * np.array([0.84, 0.88, 0.92])
        zbuf = np.full((size, size), -np.inf)
        sx = (Q[..., 0] / extent + 0.5) * size
        sy = (0.5 - Q[..., 1] / extent) * size
        for t in range(len(Q)):
            n = np.cross(Q[t, 1] - Q[t, 0], Q[t, 2] - Q[t, 0])
            ln = np.linalg.norm(n)
            if ln < 1e-12:
                continue
            n /= ln
            if n[2] < 0:
                n = -n
            x0, x1 = int(max(sx[t].min(), 0)), int(min(sx[t].max() + 1, size))
            y0, y1 = int(max(sy[t].min(), 0)), int(min(sy[t].max() + 1, size))
            if x0 >= x1 or y0 >= y1:
                continue
            ys, xs = np.mgrid[y0:y1, x0:x1] + 0.5
            (ax, bx, cx), (ay, by, cy) = sx[t], sy[t]
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-9:
                continue
            w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
            w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
            w2 = 1 - w0 - w1
            inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
            z = w0 * Q[t, 0, 2] + w1 * Q[t, 1, 2] + w2 * Q[t, 2, 2]
            sub = zbuf[y0:y1, x0:x1]
            hit = inside & (z > sub)
            if not hit.any():
                continue
            u = w0 * T[t, 0, 0] + w1 * T[t, 1, 0] + w2 * T[t, 2, 0]
            v = w0 * T[t, 0, 1] + w1 * T[t, 1, 1] + w2 * T[t, 2, 1]
            ui = np.clip((u * tw).astype(int), 0, tw - 1)
            vi = np.clip(((1 - v) * th).astype(int), 0, th - 1)
            d = max(float(n @ light), 0)
            lit = 0.4 + 0.6 * d + 0.3 * d ** 20
            sub[hit] = z[hit]
            img[y0:y1, x0:x1][hit] = np.clip(arr[vi[hit], ui[hit]] * lit, 0, 1)
        views.append(Image.fromarray((img * 255).astype(np.uint8)))
    sheet = Image.new("RGB", (4 * size, size + 40), (34, 30, 28))
    for k, v in enumerate(views):
        sheet.paste(v, (k * size, 0))
    sheet.paste(tex.resize((size, size)), (3 * size, 0))
    d = ImageDraw.Draw(sheet)
    f = nf.font("sans", 18)
    for k, s in enumerate(("front", "side", "back", "texture (UV layout)")):
        d.text((k * size + size / 2, size + 20), s, font=f, fill=(235, 235, 235), anchor="mm")
    return sheet


def model_lods(model: str):
    """(suffix, parts) for each resolution LOD, then the texture painter."""
    if model == "whittakers_block":
        mesh = block_mesh()
        return [(s, [("camo", mesh)]) for s in ("", "_lod1", "_lod2")], lambda item: block_texture(item)
    spec = LATHES[model]
    low = [spec["profile"][i] for i in spec["lod"]]
    lods = []
    for suffix, sides, profile in (("", 32, spec["profile"]), ("_lod1", 16, spec["profile"]), ("_lod2", 8, low)):
        parts = [("camo", lathe(spec, sides, profile))]
        if model == "v_can" and not suffix:
            parts.append(("camo", tab_quads(spec)))
        lods.append((suffix, parts))
    return lods, lambda item: lathe_texture(model, item)


def build(model: str) -> list[str]:
    """Write one model's files; returns the fingerprint keys of the textures written."""
    items = {i.key: i for i in nf.ITEMS}
    lods, paint = model_lods(model)
    for suffix, parts in lods:
        tris = write_obj(MODEL_DIR / f"{model}{suffix}.obj", model, parts, f"{model}{suffix}")
        print(f"{model}{suffix}.obj: {tris} triangles")
    if model == "whittakers_block":
        write_geometry(MODEL_DIR / f"{model}_geometry.obj", model, BLOCK["mass"], box=BLOCK["size"])
        spec = BLOCK
    else:
        spec = LATHES[model]
        write_geometry(MODEL_DIR / f"{model}_geometry.obj", model, spec["mass"], prism=(spec["radius"], spec["height"]))
    first = MODEL_ITEMS[model][0]
    (MODEL_DIR / f"{model}.mtl").write_text(f"newmtl {model}\nKd 1 1 1\nmap_Kd ../../data/food/models/{first}.png\n")
    (TEX_DIR / f"{model}.rvmat").write_text(rvmat(*spec["shine"], False), encoding="utf-8", newline="\r\n")
    texs = []
    for key in MODEL_ITEMS[model]:
        tex = paint(items[key])
        tex.save(TEX_DIR / f"{key}.png", optimize=True)
        texs.append(tex)
    with np.errstate(invalid="ignore"):
        sheet = render(model, lods[0][1], texs[0])
    if len(texs) > 1:
        strip = Image.new("RGB", (sheet.width, 220), (34, 30, 28))
        for k, t in enumerate(texs):
            strip.paste(t.resize((200, 200)), (10 + k * 210, 10))
        full = Image.new("RGB", (sheet.width, sheet.height + strip.height))
        full.paste(sheet, (0, 0))
        full.paste(strip, (0, sheet.height))
        sheet = full
    sheet.save(MAP_DIR / "preview" / f"models_{model}.png", optimize=True)
    print(f"Wrote {', '.join(f'data/food/models/{k}.png' for k in MODEL_ITEMS[model])} and preview/models_{model}.png")
    return ["models/" + k for k in MODEL_ITEMS[model]]


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    TEX_DIR.mkdir(parents=True, exist_ok=True)
    keys = []
    for model in MODEL_ITEMS:
        keys += build(model)
    nf.record(keys)


if __name__ == "__main__":
    main()
