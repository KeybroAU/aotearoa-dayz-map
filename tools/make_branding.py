"""Build the mod's logo, icons, loading screens and map picture from the art in data/branding/art/.

    python make_branding.py

Writes data/branding/: logo_512.png, icon_128.png, icon_64.png (with alpha), loading_1.jpg and
loading_2.jpg (2048 x 1024, logo, strapline and the "Designed by Keybro" / Keybrogaming.com
watermark added) and map_picture.jpg (the satellite preview with the logo and Keybrogaming.com). Convert them to .paa with ImageToPAA from DayZ Tools; see the README.

Also writes workshop/preview.jpg, the 1024 x 1024 Steam Workshop image (Steam wants a square under 1 MB).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import watermark

MAP_DIR = Path(__file__).resolve().parents[1]
OUT = MAP_DIR / "data" / "branding"
ART = OUT / "art"
WORKSHOP = MAP_DIR / "workshop"
STRAPLINE = "A New Zealand survival terrain"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


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
    print(f"Wrote {OUT} and {WORKSHOP}")


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


if __name__ == "__main__":
    main()
