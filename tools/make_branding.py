"""Build the mod's logo, icons, loading screens and map picture from the art in data/branding/art/.

    python make_branding.py

Writes data/branding/: logo_512.png, icon_128.png, icon_64.png (with alpha), loading_1.jpg and
loading_2.jpg (2048 x 1024, logo, strapline and the "Designed by Keybro" / Keybrogaming.com
watermark added) and map_picture.jpg (the satellite preview with the logo and Keybrogaming.com). Convert them to .paa with ImageToPAA from DayZ Tools; see the README.

Also writes workshop/preview.jpg, the 1024 x 1024 Steam Workshop image (Steam wants a square under 1 MB), and
.github/banner.png, the 1280 x 640 GitHub banner (README header and the repo's social preview).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import watermark
import fontpaths

MAP_DIR = Path(__file__).resolve().parents[1]
OUT = MAP_DIR / "data" / "branding"
ART = OUT / "art"
WORKSHOP = MAP_DIR / "workshop"
BANNER = MAP_DIR / ".github" / "banner.png"
STRAPLINE = "A New Zealand survival terrain"
FONT = fontpaths.path("DejaVuSans-Bold.ttf")


def main() -> None:
    logo = Image.open(ART / "logo.jpg").convert("RGB").resize((512, 512), Image.LANCZOS)
    mask = Image.new("L", (512, 512), 0)
    ImageDraw.Draw(mask).ellipse([18, 18, 494, 494], fill=255)
    logo.putalpha(mask.filter(ImageFilter.GaussianBlur(10)))
    logo.save(OUT / "logo_512.png", optimize=True)
    for size in (128, 64):
        logo.resize((size, size), Image.LANCZOS).save(OUT / f"icon_{size}.png", optimize=True)

    try:
        font = ImageFont.truetype(FONT, 34)
    except OSError:
        font = ImageFont.load_default()
    for art in sorted(ART.glob("loading_*.jpg")):
        im = Image.open(art).convert("RGB").resize((2048, 1024), Image.LANCZOS)
        badge = logo.resize((300, 300), Image.LANCZOS)
        im.paste(badge, (60, 1024 - 360), badge)
        ImageDraw.Draw(im).text((380, 1024 - 200), STRAPLINE, font=font, fill=(235, 232, 220),
                                stroke_width=2, stroke_fill=(0, 0, 0))
        im = watermark.stamp(im, [watermark.CREDIT, watermark.SITE], 46, margin=56)
        im.save(OUT / art.name, quality=90)

    sat = Image.open(MAP_DIR / "preview" / "satellite_2048.png").convert("RGB").resize((1024, 1024), Image.LANCZOS)
    badge = logo.resize((220, 220), Image.LANCZOS)
    sat.paste(badge, (1024 - 240, 20), badge)
    sat = watermark.stamp(sat, [watermark.SITE], 26)
    sat.save(OUT / "map_picture.jpg", quality=88)
    workshop(logo)
    banner(logo)
    print(f"Wrote {OUT}, {WORKSHOP} and {BANNER}")


def workshop(logo: Image.Image, size: int = 1024) -> None:
    """Loading-screen art behind the satellite map, logo and title, with the Keybro watermark."""
    art = Image.open(ART / "loading_1.jpg").convert("RGB")
    side = min(art.size)
    left, top = (art.size[0] - side) // 2, (art.size[1] - side) // 2
    im = art.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
    im = im.filter(ImageFilter.GaussianBlur(3))
    shade = Image.linear_gradient("L").resize((size, size)).point(lambda v: 70 + v * 0.55)
    im = Image.composite(Image.new("RGB", im.size, (8, 12, 10)), im, shade)

    sat = Image.open(MAP_DIR / "preview" / "satellite_2048.png").convert("RGB").resize((560, 560), Image.LANCZOS)
    frame = Image.new("RGB", (sat.size[0] + 8, sat.size[1] + 8), (235, 232, 220))
    frame.paste(sat, (4, 4))
    im.paste(frame, (size - frame.size[0] - 40, 40))
    badge = logo.resize((300, 300), Image.LANCZOS)
    im.paste(badge, (40, 40), badge)

    d = ImageDraw.Draw(im)
    title = ImageFont.truetype(FONT, 132) if Path(FONT).exists() else ImageFont.load_default()
    sub = ImageFont.truetype(FONT, 34) if Path(FONT).exists() else ImageFont.load_default()
    d.text((48, 630), "AOTEAROA", font=title, fill=(245, 242, 232), stroke_width=4, stroke_fill=(0, 0, 0))
    d.text((54, 780), STRAPLINE, font=sub, fill=(235, 232, 220), stroke_width=2, stroke_fill=(0, 0, 0))
    d.text((54, 826), "25.6 km  ·  North, South and Stewart Island", font=sub, fill=(200, 210, 190),
           stroke_width=2, stroke_fill=(0, 0, 0))
    im = watermark.stamp(im, [watermark.CREDIT, watermark.SITE], 40, margin=40, opacity=200)
    WORKSHOP.mkdir(exist_ok=True)
    im.save(WORKSHOP / "preview.jpg", quality=90, optimize=True)


def banner(logo: Image.Image, w: int = 1280, h: int = 640) -> None:
    """Loading-screen art with the logo, title and a large "Designed by Keybro", the satellite map on the right."""
    art = Image.open(ART / "loading_2.jpg").convert("RGB")
    scale = max(w / art.size[0], h / art.size[1])
    art = art.resize((int(art.size[0] * scale) + 1, int(art.size[1] * scale) + 1), Image.LANCZOS)
    left, top = (art.size[0] - w) // 2, (art.size[1] - h) // 2
    im = art.crop((left, top, left + w, top + h)).filter(ImageFilter.GaussianBlur(2))
    shade = Image.linear_gradient("L").rotate(90).resize((w, h)).point(lambda v: 60 + v * 0.6)
    im = Image.composite(Image.new("RGB", im.size, (8, 12, 10)), im, shade)

    sat = Image.open(MAP_DIR / "preview" / "satellite_2048.png").convert("RGB").resize((470, 470), Image.LANCZOS)
    frame = Image.new("RGB", (sat.size[0] + 8, sat.size[1] + 8), (235, 232, 220))
    frame.paste(sat, (4, 4))
    im.paste(frame, (w - frame.size[0] - 56, (h - frame.size[1]) // 2))
    badge = logo.resize((210, 210), Image.LANCZOS)
    im.paste(badge, (56, 48), badge)

    d = ImageDraw.Draw(im)
    bold = lambda s: ImageFont.truetype(FONT, s) if Path(FONT).exists() else ImageFont.load_default()
    regular = lambda s: (ImageFont.truetype(watermark.FONT, s) if Path(watermark.FONT).exists()
                         else ImageFont.load_default())
    ink, edge = (245, 242, 232), (0, 0, 0)
    d.text((60, 290), "AOTEAROA", font=bold(96), fill=ink, stroke_width=4, stroke_fill=edge)
    d.text((64, 410), "A New Zealand survival terrain for DayZ", font=bold(27), fill=(225, 228, 215),
           stroke_width=2, stroke_fill=edge)
    d.line([(64, 470), (560, 470)], fill=(200, 170, 100), width=3)
    d.text((64, 490), watermark.CREDIT, font=bold(46), fill=ink, stroke_width=3, stroke_fill=edge)
    d.text((66, 552), watermark.SITE, font=regular(30), fill=(200, 210, 190), stroke_width=2, stroke_fill=edge)
    BANNER.parent.mkdir(exist_ok=True)
    im.save(BANNER, optimize=True)


if __name__ == "__main__":
    main()
