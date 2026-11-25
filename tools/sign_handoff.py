"""Hand-off files for the two sign models (docs/models/SIGNS_BRIEF.md).

    python sign_handoff.py

Writes:
    data/signs/sign_town.rvmat, data/signs/sign_post.rvmat   materials for the p3d faces (packed with the mod)
    preview/signs_reference.png                              front and side views with sizes, the textures
                                                             on the faces and a 1.8 m figure for scale
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

import build_player_map as pm

MAP_DIR = Path(__file__).resolve().parents[1]
MODELS = MAP_DIR / "docs" / "models"
SIGNS = MAP_DIR / "data" / "signs"

STAGE = """	class Stage{n}
	{{
		texture="{tex}";
		uvSource="{uv}";{transform}
	}};
"""
TRANSFORM = """
		class uvTransform
		{
			aside[]={1,0,0};
			up[]={0,1,0};
			dir[]={0,0,0};
			pos[]={0,0,0};
		};"""

# Retroreflective sign faces: brighter specular than painted timber. sign_post is alpha tested so the
# shield, circle, triangle and diamond outlines are cut from the square.
MATERIALS = {
    "sign_town": {"specular": 0.25, "power": 40, "alpha": False},
    "sign_post": {"specular": 0.25, "power": 40, "alpha": True},
}


def rvmat(specular: float, power: int, alpha: bool) -> str:
    stages = [("#(rgb,8,8,3)color(0.5,0.5,1,1,NOHQ)", "tex"), ("#(argb,8,8,3)color(0.5,0.5,0.5,1,DT)", "tex"),
              ("#(argb,8,8,3)color(0,0,0,0,MC)", "tex"), ("#(argb,8,8,3)color(1,1,1,1,AS)", "tex"),
              ("#(argb,8,8,3)color(0,1,1,1,SMDI)", "tex"), ("#(ai,64,64,1)fresnel(1.3,0.7)", "none"),
              ("dz\\data\\data\\env_land_co.paa", "none")]
    head = [
        "ambient[]={1,1,1,1};",
        "diffuse[]={1,1,1,1};",
        "forcedDiffuse[]={0,0,0,0};",
        "emmisive[]={0,0,0,1};",
        f"specular[]={{{specular},{specular},{specular},1}};",
        f"specularPower={power};",
        'PixelShaderID="Super";',
        'VertexShaderID="Super";',
    ]
    if alpha:
        head.append('renderFlags[]={"AlphaTest64"};')
    body = "".join(STAGE.format(n=i + 1, tex=t, uv=uv, transform=TRANSFORM if uv == "tex" else "")
                   for i, (t, uv) in enumerate(stages))
    return "\n".join(head) + "\n" + body.replace("\t", "", 0)


def load_obj(path: Path) -> tuple[list, list]:
    verts, faces = [], []
    group = ""
    for line in path.read_text().splitlines():
        if line.startswith("v "):
            verts.append(tuple(float(v) for v in line.split()[1:4]))
        elif line.startswith("g "):
            group = line.split()[1]
        elif line.startswith("f "):
            faces.append((group, [int(p.split("/")[0]) - 1 for p in line.split()[1:]]))
    return verts, faces


def view(name: str, texture: Image.Image, scale: float = 150.0) -> Image.Image:
    """Front (x, y) and side (z, y) views at `scale` px per metre, ground at y = 0."""
    verts, faces = load_obj(MODELS / f"{name}.obj")
    w, h = int(5.8 * scale), int(4.2 * scale)
    img = Image.new("RGB", (w, h), (245, 242, 235))
    d = ImageDraw.Draw(img, "RGBA")
    ground = h - int(0.8 * scale)
    front_x, side_x = int(1.7 * scale), int(4.1 * scale)
    P = lambda ox, a, y: (ox + a * scale, ground - y * scale)
    small, label = pm.font(pm.FONT, int(0.11 * scale)), pm.font(pm.FONT_BOLD, int(0.14 * scale))

    d.rectangle([0, ground, w, h], fill=(205, 190, 160))
    d.line([(0, ground), (w, ground)], fill=(90, 70, 40), width=2)
    d.text((front_x, 10), "FRONT (faces +z, yaw 0 = north)", font=label, anchor="ma", fill=(40, 40, 40))
    d.text((side_x, 10), "SIDE", font=label, anchor="ma", fill=(40, 40, 40))

    for group, idx in sorted(faces, key=lambda f: f[0] == "camo"):
        pts = [verts[i] for i in idx]
        front = [P(front_x, x, y) for x, y, z in pts]
        side = [P(side_x, -z, y) for x, y, z in pts]
        colour = (150, 150, 150, 255) if group != "camo" else (90, 90, 90, 255)
        d.polygon(side, fill=colour, outline=(40, 40, 40, 255))
        if group != "camo" or max(y for _, y, _ in pts) - min(y for _, y, _ in pts) > 1.5:
            d.polygon(front, fill=(160, 160, 160, 255), outline=(60, 60, 60, 255))
    xs = [v[0] for v, (g, idx) in ((verts[i], f) for f in faces for i in f[1]) if g == "camo"]
    ys = [v[1] for v, (g, idx) in ((verts[i], f) for f in faces for i in f[1]) if g == "camo"]
    x0, x1 = min(xs), max(xs)
    face_top = max(ys)
    face_bottom = min(y for y in ys if y > 1.0)
    face = texture.crop((0, 0, texture.size[0], texture.size[1] // 2))
    fw, fh = int((x1 - x0) * scale), int((face_top - face_bottom) * scale)
    face = face.resize((fw, fh), Image.LANCZOS)
    left, top = P(front_x, x0, face_top)
    img.paste(face, (int(left), int(top)), face if face.mode == "RGBA" else None)

    def dim(a, b, text, horizontal):
        d.line([a, b], fill=(200, 30, 30), width=2)
        for p in (a, b):
            r = 4
            d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=(200, 30, 30))
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        d.text((mid[0], mid[1] - 6) if horizontal else (mid[0] + 8, mid[1]), text, font=small,
               anchor="md" if horizontal else "lm", fill=(200, 30, 30))

    dim(P(front_x, x0, face_top + 0.15), P(front_x, x1, face_top + 0.15), f"{x1 - x0:.1f} m", True)
    dim(P(front_x, x1 + 0.2, face_bottom), P(front_x, x1 + 0.2, face_top), f"{face_top - face_bottom:.1f} m", False)
    dim(P(front_x, x0 - 0.25, 0.0), P(front_x, x0 - 0.25, face_bottom), f"{face_bottom:.1f} m to the face", False)
    bottom = min(v[1] for v in verts)
    dim(P(side_x, 0.35, bottom), P(side_x, 0.35, 0.0), f"{-bottom:.1f} m in the ground", False)

    fx = front_x + int(2.0 * scale) if name == "sign_town" else front_x + int(1.1 * scale)
    head = 0.12 * scale
    top_y = ground - 1.8 * scale
    d.ellipse([fx - head, top_y, fx + head, top_y + 2 * head], fill=(70, 90, 120))
    d.rounded_rectangle([fx - 0.2 * scale, top_y + 2 * head, fx + 0.2 * scale, ground], radius=8, fill=(70, 90, 120))
    d.text((fx, ground + 8), "1.8 m", font=small, anchor="ma", fill=(40, 40, 40))
    d.text((w // 2, h - 18), name, font=label, anchor="md", fill=(40, 40, 40))
    return img


def main() -> None:
    for name, m in MATERIALS.items():
        path = SIGNS / f"{name}.rvmat"
        path.write_text(rvmat(m["specular"], m["power"], m["alpha"]), encoding="utf-8", newline="\r\n")
        print(f"Wrote {path}")
    town = view("sign_town", Image.open(SIGNS / "sign_Wellington.png").convert("RGB"))
    post = view("sign_post", Image.open(SIGNS / "post_SH1.png").convert("RGBA"))
    sheet = Image.new("RGB", (town.size[0], town.size[1] + post.size[1] + 20), (255, 255, 255))
    sheet.paste(town, (0, 0))
    sheet.paste(post, (0, town.size[1] + 20))
    out = MAP_DIR / "preview" / "signs_reference.png"
    sheet.save(out, optimize=True)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
