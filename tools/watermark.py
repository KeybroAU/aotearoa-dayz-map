"""The Keybro credit stamped on the mod's images: loading screens, map picture, player map and map item."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

CREDIT = "Designed by Keybro"
SITE = "Keybrogaming.com"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _font(path: str, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(path, max(8, size))
    except OSError:
        return ImageFont.load_default()


def stamp(img: Image.Image, lines: list[str], height: float, corner: str = "br", margin: float | None = None,
          opacity: int = 170) -> Image.Image:
    """Semi-transparent white text with a dark outline in one corner; the first line is bold.

    height is the first line's text size in pixels; corner is "br", "bl", "tr" or "tl".
    """
    base = img.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    margin = height * 0.9 if margin is None else margin
    fonts = [_font(FONT_BOLD, int(height))] + [_font(FONT, int(height * 0.72))] * (len(lines) - 1)
    gap = height * 0.25
    sizes = [d.textbbox((0, 0), t, font=f) for t, f in zip(lines, fonts)]
    total = sum(b[3] - b[1] for b in sizes) + gap * (len(lines) - 1)
    right, bottom = corner[1] == "r", corner[0] == "b"
    y = base.size[1] - margin - total if bottom else margin
    stroke = max(1, int(height / 14))
    for text, f, b in zip(lines, fonts, sizes):
        x = base.size[0] - margin if right else margin
        d.text((x, y - b[1]), text, font=f, anchor="ra" if right else "la", fill=(255, 255, 255, opacity),
               stroke_width=stroke, stroke_fill=(0, 0, 0, int(opacity * 0.8)))
        y += b[3] - b[1] + gap
    out = Image.alpha_composite(base, layer)
    return out if img.mode == "RGBA" else out.convert(img.mode)
