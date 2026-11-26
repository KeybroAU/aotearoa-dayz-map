"""Custom drink models: a tall 500 ml can for V energy drink, ready to build in Object Builder.

    python drink_models.py

Writes:

  docs/models/v_can.obj, v_can_lod1.obj, v_can_lod2.obj   resolution LODs (lathed, 32 / 16 / 8 sides)
  docs/models/v_can_geometry.obj                          Geometry: one closed convex 8-sided prism
  docs/models/v_can.mtl                                   the material, pointing at the texture
  data/food/models/v_can.png                              the texture in the model's own UV layout
  data/food/models/v_can.rvmat                            a shiny aluminium material
  preview/models_v_can.png                                renders of the can and its texture

The can is 66 mm across and 168 mm tall (a real 500 ml can), metres, y up, with the origin at its
centre so it sits on the ground and in the hands like the vanilla cans. Every face is in the "camo"
named selection, which the config retextures; the ring pull is also in "tab".

Texture layout (1024 x 1024): the label wraps once round the top 68% (front centred at u = 0.5, the
seam at the back), the neck and the base ring are plain metal bands below it, and the lid and the
base are the two discs along the bottom. nz_food.py uses the model once its .p3d is saved as
P:\\maps\\aotearoa\\structures\\food\\v_can\\v_can.p3d (docs/CUSTOM_MODELS.md, item 12); until then
V is a retextured vanilla can.
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
NAME = "v_can"
P3D = Path("structures") / "food" / NAME / f"{NAME}.p3d"
TEX = 1024

RADIUS, HEIGHT = 0.033, 0.168
LID_R = 0.0262
# The can's outline from the middle of the base, round the outside, to the middle of the lid: (radius,
# height above the base, part). Parts pick where the faces sit on the texture.
PROFILE = [
    (0.0, 0.010, "base"), (0.017, 0.007, "base"), (0.025, 0.0, "base"), (0.029, 0.002, "ring"),
    (0.0322, 0.007, "ring"), (0.033, 0.014, "label"), (0.033, 0.150, "neck"), (0.0315, 0.157, "neck"),
    (0.0278, 0.1635, "neck"), (0.0273, 0.168, "lid"), (LID_R, 0.1684, "lid"), (0.0254, 0.1652, "lid"),
    (0.0, 0.1655, "lid"),
]
LOD_PROFILE = [PROFILE[i] for i in (0, 2, 4, 5, 6, 8, 9, 12)]
LABEL_Y = (0.014, 0.150)
# Texture regions, as fractions of the image from the top-left.
LABEL_ROWS = (0.0, 0.68)
NECK_ROWS = (0.70, 0.74)
RING_ROWS = (0.74, 0.78)
LID_DISC = (0.25, 0.89, 0.105)
BASE_DISC = (0.75, 0.89, 0.105)

V_GREEN = (88, 182, 34)
V_DARK = (16, 46, 14)


def _uv_disc(disc, r, theta, r_max):
    cx, cy, rr = disc
    k = rr * r / r_max
    return cx + k * math.sin(theta), 1.0 - (cy - k * math.cos(theta))


def lathe(sides: int, profile) -> tuple[list, list, list]:
    """Vertices, UVs and quads (each [(v, vt) x 4], 1-based) of the can turned from the profile."""
    verts, uvs, faces = [], [], []

    def uv(r, y, part, theta, i):
        u = i / sides
        if part == "label":
            t = (y - LABEL_Y[0]) / (LABEL_Y[1] - LABEL_Y[0])
            return u, 1.0 - (LABEL_ROWS[1] - t * (LABEL_ROWS[1] - LABEL_ROWS[0]))
        if part in ("neck", "ring"):
            rows = NECK_ROWS if part == "neck" else RING_ROWS
            lo, hi = (0.150, HEIGHT) if part == "neck" else (0.0, LABEL_Y[0])
            t = (y - lo) / (hi - lo)
            return u, 1.0 - (rows[1] - min(max(t, 0), 1) * (rows[1] - rows[0]))
        return _uv_disc(LID_DISC if part == "lid" else BASE_DISC, r, theta, RADIUS)

    for j in range(len(profile) - 1):
        (r0, y0, p0), (r1, y1, _) = profile[j], profile[j + 1]
        part = p0
        for i in range(sides):
            quad = []
            for (r, y), k in (((r0, y0), i), ((r0, y0), i + 1), ((r1, y1), i + 1), ((r1, y1), i)):
                theta = -math.pi + 2 * math.pi * k / sides
                verts.append((r * math.sin(theta), y - HEIGHT / 2, r * math.cos(theta)))
                uvs.append(uv(r, y, part if part != "label" or y <= LABEL_Y[1] else "neck", theta, k))
                quad.append((len(verts), len(uvs)))
            pts = [np.array(verts[v - 1]) for v, _ in quad]
            if np.linalg.norm(pts[0] - pts[3]) < 1e-9 and np.linalg.norm(pts[1] - pts[2]) < 1e-9:
                continue
            faces.append(quad)
    return verts, uvs, faces


def tab_quads() -> tuple[list, list, list]:
    """The ring pull: a flat tab lying on the lid from the rivet towards the back, its nose over the opening."""
    y = 0.1660 - HEIGHT / 2
    corners = [(-0.006, -0.019), (0.006, -0.019), (0.006, 0.002), (-0.006, 0.002)]
    verts, uvs = [], []
    for x, z in corners:
        verts.append((x, y, z))
        r, th = math.hypot(x, z), math.atan2(x, z)
        uvs.append(_uv_disc(LID_DISC, r, th, RADIUS))
    return verts, uvs, [[(i + 1, i + 1) for i in range(4)]]


def write_obj(path: Path, parts, comment: str) -> int:
    out = [f"# {comment}: generated by tools/drink_models.py. Metres, y up, front faces +z.", f"mtllib {NAME}.mtl"]
    v_off = t_off = 0
    body = []
    tris = 0
    for group, (verts, uvs, faces) in parts:
        out += [f"v {x:.5f} {y:.5f} {z:.5f}" for x, y, z in verts]
        out += [f"vt {u:.5f} {v:.5f}" for u, v in uvs]
        body += [f"g {group}", f"usemtl {NAME}"]
        for q in faces:
            body.append("f " + " ".join(f"{v + v_off}/{t + t_off}" for v, t in q))
            tris += len(q) - 2
        v_off += len(verts)
        t_off += len(uvs)
    path.write_text("\n".join(out + body) + "\n")
    return tris


def write_geometry(path: Path) -> None:
    n = 8
    out = [f"# {NAME} Geometry: one closed convex component. Name its selection Component01 and give the LOD "
           "a mass of 0.5 kg and the named property autocenter = 0."]
    for y in (-HEIGHT / 2, HEIGHT / 2):
        for i in range(n):
            t = 2 * math.pi * i / n
            out.append(f"v {RADIUS * math.sin(t):.5f} {y:.5f} {RADIUS * math.cos(t):.5f}")
    out.append("g Component01")
    out.append("f " + " ".join(str(i + 1) for i in reversed(range(n))))
    out.append("f " + " ".join(str(n + i + 1) for i in range(n)))
    for i in range(n):
        a, b = i + 1, (i + 1) % n + 1
        out.append(f"f {a} {b} {n + b} {n + a}")
    path.write_text("\n".join(out) + "\n")


def lid(d: ImageDraw.ImageDraw, disc, rng, base=False):
    cx, cy, r = disc[0] * TEX, disc[1] * TEX, disc[2] * TEX
    for k, (frac, col) in enumerate(((1.0, (150, 152, 156)), (0.97, (198, 200, 204)), (0.92, (170, 172, 176)),
                                      (0.86, (205, 207, 211)))):
        d.ellipse((cx - frac * r, cy - frac * r, cx + frac * r, cy + frac * r), fill=col)
    if base:
        for frac in (0.6, 0.45):
            d.ellipse((cx - frac * r, cy - frac * r, cx + frac * r, cy + frac * r), outline=(160, 162, 166), width=3)
        nf.text(d, (cx, cy), "V", "italic", 0.4 * r, 0.3 * r, (150, 152, 156))
        return
    # The opening (keyhole) towards the front, the rivet, and the ring pull over them.
    # Up on the disc is the front of the can.
    ox, oy = cx, cy
    d.rounded_rectangle((ox - 0.22 * r, oy - 0.62 * r, ox + 0.22 * r, oy - 0.12 * r), radius=int(0.16 * r),
                        outline=(140, 142, 146), width=4)
    d.ellipse((cx - 0.08 * r, cy - 0.08 * r, cx + 0.08 * r, cy + 0.08 * r), fill=(160, 162, 166))
    tab = (cx - 0.22 * r, cy - 0.06 * r, cx + 0.22 * r, cy + 0.72 * r)
    d.rounded_rectangle(tab, radius=int(0.18 * r), fill=V_GREEN, outline=shade(V_GREEN, 0.55), width=4)
    d.rounded_rectangle((cx - 0.12 * r, cy + 0.3 * r, cx + 0.12 * r, cy + 0.6 * r), radius=int(0.1 * r),
                        fill=(198, 200, 204))


def shade(c, k):
    return nf.shade(c, k)


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


def label(rng) -> Image.Image:
    w, h = TEX, int((LABEL_ROWS[1] - LABEL_ROWS[0]) * TEX)
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
    # Front, centred at u = 0.5.
    fx = 0.5 * w
    big_v(d, fx, 0.1 * h, 0.5 * h)
    nf.text(d, (fx, 0.7 * h), "ENERGY DRINK", "sans", 0.25 * w, 0.075 * h, (255, 255, 255), 3, (14, 14, 14))
    nf.text(d, (fx, 0.79 * h), "with guarana", "italic", 0.17 * w, 0.045 * h, (200, 245, 90), 2, (14, 14, 14))
    nf.text(d, (fx, 0.9 * h), "500 ml", "sans", 0.1 * w, 0.045 * h, (255, 255, 255))
    # Sides: a smaller V on each side of the front.
    for sx in (0.2, 0.8):
        big_v(d, sx * w, 0.18 * h, 0.2 * h)
        nf.text(d, (sx * w, 0.48 * h), "THE ORIGINAL", "sans", 0.14 * w, 0.04 * h, (255, 255, 255), 2, (14, 14, 14))
        nf.text(d, (sx * w, 0.54 * h), "KIWI ENERGY", "sans", 0.14 * w, 0.04 * h, (255, 255, 255), 2, (14, 14, 14))
    # Back panel across the seam: small print and a barcode.
    back = Image.new("RGB", (int(0.36 * w), h), (0, 0, 0))
    bw = back.width
    back.paste(im.crop((0, 0, bw // 2, h)), (bw - bw // 2, 0))
    back.paste(im.crop((w - (bw - bw // 2), 0, w, h)), (0, 0))
    bd = ImageDraw.Draw(back)
    bd.rounded_rectangle((0.14 * bw, 0.14 * h, 0.86 * bw, 0.62 * h), radius=12, fill=(245, 245, 240),
                         outline=(14, 14, 14), width=3)
    lines = ["NUTRITION INFORMATION", "Servings per can: 2", "Energy 195 kJ / 100 ml", "Sugars 11.2 g / 100 ml",
             "Caffeine 31 mg / 100 ml", "", "Contains caffeine. Not", "recommended for children,", "pregnant women or",
             "people sensitive to caffeine.", "Made in New Zealand"]
    for k, ln in enumerate(lines):
        if ln:
            nf.text(bd, (0.5 * bw, (0.18 + 0.04 * k) * h), ln, "sans" if k == 0 else "plain", 0.66 * bw, 0.03 * h,
                    (20, 20, 20))
    bx0, by0 = 0.24 * bw, 0.68 * h
    bd.rectangle((bx0 - 8, by0 - 8, 0.76 * bw + 8, 0.84 * h + 8), fill=(255, 255, 255))
    x = bx0
    while x < 0.76 * bw:
        bar = rng.choice((2, 3, 5))
        bd.rectangle((x, by0, x + bar - 1, 0.84 * h), fill=(10, 10, 10))
        x += bar + rng.choice((2, 3, 4))
    im.paste(back.crop((bw - bw // 2, 0, bw, h)), (0, 0))
    im.paste(back.crop((0, 0, bw - bw // 2, h)), (w - (bw - bw // 2), 0))
    return nf.wear(im, rng, 6)


def texture() -> Image.Image:
    rng = random.Random(NAME)
    im = nf.metal((TEX, TEX), rng).point(lambda v: min(255, int(v * 1.08)))
    d = ImageDraw.Draw(im)
    for rows, col in ((NECK_ROWS, (196, 198, 202)), (RING_ROWS, (176, 178, 182))):
        d.rectangle((0, rows[0] * TEX, TEX, rows[1] * TEX), fill=col)
        for k in range(4):
            y = (rows[0] + (rows[1] - rows[0]) * (k + 0.5) / 4) * TEX
            d.line((0, y, TEX, y), fill=shade(col, 0.88), width=2)
    lid(d, LID_DISC, rng)
    lid(d, BASE_DISC, rng, base=True)
    im.paste(label(rng), (0, int(LABEL_ROWS[0] * TEX)))
    return im


def render(tex: Image.Image) -> Image.Image:
    """Ray-cast three-quarter views of the can (front, side, back) beside its texture."""
    arr = np.asarray(tex.convert("RGB")).astype(float) / 255.0
    size = 420
    views = []
    for yaw in (0.0, 90.0, 180.0):
        pitch = math.radians(22)
        scale = 0.21 / size
        ys, xs = np.mgrid[0:size, 0:size]
        px = (xs - size / 2) * scale
        py = (size / 2 - ys) * scale
        # Orthographic camera looking at the can from +z, tilted down by pitch; can turned by yaw.
        fwd = np.array([0.0, -math.sin(pitch), -math.cos(pitch)])
        up = np.array([0.0, math.cos(pitch), -math.sin(pitch)])
        right = np.array([1.0, 0.0, 0.0])
        org = px[..., None] * right + py[..., None] * up - fwd * 1.0
        ox, oy, oz = org[..., 0], org[..., 1] + HEIGHT / 2, org[..., 2]
        dx, dy, dz = fwd
        a = dx * dx + dz * dz
        b = 2 * (ox * dx + oz * dz)
        c = ox * ox + oz * oz - RADIUS ** 2
        disc = b * b - 4 * a * c
        t_side = np.where(disc > 0, (-b - np.sqrt(np.maximum(disc, 0))) / (2 * a), np.inf)
        hy = oy + t_side * dy
        t_side = np.where((hy >= 0) & (hy <= HEIGHT), t_side, np.inf)
        t_top = (HEIGHT - oy) / dy
        tx, tz = ox + t_top * dx, oz + t_top * dz
        t_top = np.where(tx * tx + tz * tz <= RADIUS ** 2, t_top, np.inf)
        img = np.ones((size, size, 3)) * np.array([0.84, 0.88, 0.92])
        light = np.array([0.5, 0.7, 0.6])
        light /= np.linalg.norm(light)
        yr = math.radians(yaw)
        side = np.isfinite(t_side) & (t_side <= t_top)
        top = np.isfinite(t_top) & ~side
        sx, sz = ox + t_side * dx, oz + t_side * dz
        theta = np.arctan2(sx, sz) + yr
        theta = (theta + math.pi) % (2 * math.pi) - math.pi
        u = (theta + math.pi) / (2 * math.pi)
        y = hy
        row = np.where((y >= LABEL_Y[0]) & (y <= LABEL_Y[1]),
                       LABEL_ROWS[1] - (y - LABEL_Y[0]) / (LABEL_Y[1] - LABEL_Y[0]) * (LABEL_ROWS[1] - LABEL_ROWS[0]),
                       np.where(y > LABEL_Y[1], NECK_ROWS[0] + 0.02, RING_ROWS[0] + 0.02))
        n_side = np.stack([np.sin(np.arctan2(sx, sz)), np.zeros_like(sx), np.cos(np.arctan2(sx, sz))], -1)
        lit = 0.35 + 0.65 * np.clip(n_side @ light, 0, 1) + 0.35 * np.clip(n_side @ light, 0, 1) ** 24
        ui = np.clip((u * TEX).astype(int), 0, TEX - 1)
        vi = np.clip((row * TEX).astype(int), 0, TEX - 1)
        img[side] = np.clip(arr[vi[side], ui[side]] * lit[side][:, None], 0, 1)
        r = np.hypot(tx, tz)
        th = np.arctan2(tx, tz) + yr
        cu = LID_DISC[0] + LID_DISC[2] * (r / RADIUS) * np.sin(th)
        cv = LID_DISC[1] - LID_DISC[2] * (r / RADIUS) * np.cos(th)
        ci = np.clip((cu * TEX).astype(int), 0, TEX - 1)
        cj = np.clip((cv * TEX).astype(int), 0, TEX - 1)
        img[top] = np.clip(arr[cj[top], ci[top]] * (0.35 + 0.65 * light[1]), 0, 1)
        views.append(Image.fromarray((img * 255).astype(np.uint8)))
    sheet = Image.new("RGB", (3 * size + size, size + 40), (34, 30, 28))
    for k, v in enumerate(views):
        sheet.paste(v, (k * size, 0))
    sheet.paste(tex.resize((size, size)), (3 * size, 0))
    d = ImageDraw.Draw(sheet)
    f = nf.font("sans", 18)
    for k, s in enumerate(("front", "side", "back", "texture (UV layout)")):
        d.text((k * size + size / 2, size + 20), s, font=f, fill=(235, 235, 235), anchor="mm")
    return sheet


def mesh_lods():
    return [("", 32, PROFILE), ("_lod1", 16, PROFILE), ("_lod2", 8, LOD_PROFILE)]


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    TEX_DIR.mkdir(parents=True, exist_ok=True)
    for suffix, sides, profile in mesh_lods():
        parts = [("camo", lathe(sides, profile))]
        if not suffix:
            parts.append(("tab", tab_quads()))
        tris = write_obj(MODEL_DIR / f"{NAME}{suffix}.obj", parts, f"{NAME}{suffix} ({sides} sides)")
        print(f"{NAME}{suffix}.obj: {tris} triangles")
    write_geometry(MODEL_DIR / f"{NAME}_geometry.obj")
    (MODEL_DIR / f"{NAME}.mtl").write_text(f"newmtl {NAME}\nKd 1 1 1\nmap_Kd ../../data/food/models/{NAME}.png\n")
    tex = texture()
    tex.save(TEX_DIR / f"{NAME}.png", optimize=True)
    nf.record(["models/" + NAME])
    (TEX_DIR / f"{NAME}.rvmat").write_text(rvmat(0.6, 70, False), encoding="utf-8", newline="\r\n")
    with np.errstate(invalid="ignore"):
        sheet = render(tex)
    sheet.save(MAP_DIR / "preview" / f"models_{NAME}.png", optimize=True)
    print(f"Wrote {TEX_DIR.relative_to(MAP_DIR)}/{NAME}.png and preview/models_{NAME}.png")


if __name__ == "__main__":
    main()
