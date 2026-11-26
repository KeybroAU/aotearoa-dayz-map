"""Steam Workshop screenshots: 1920 x 1080 feature cards built from the map previews.

    python make_workshop_shots.py

Writes workshop/screenshots/NN_<name>.jpg, each with a caption, the logo and the "Designed by Keybro" /
Keybrogaming.com watermark. Run build_mission.py, build_player_map.py and build_map_item.py first so the
previews are current. Swap in real in-game screenshots once the world is built.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import watermark

MAP_DIR = Path(__file__).resolve().parents[1]
PREVIEW = MAP_DIR / "preview"
BRANDING = MAP_DIR / "data" / "branding"
OUT = MAP_DIR / "workshop" / "screenshots"
W, H = 1920, 1080
INK, SOFT, ACCENT = (245, 242, 232), (205, 212, 196), (200, 170, 100)

# (file name, source image, crop box as fractions (left, top, right, bottom) or None, title, lines)
SHOTS = [
    ("01_aotearoa", "player_map_4096.jpg", None, "All of Aotearoa",
     ["25.6 km terrain from real elevation data", "North, South and Stewart Island", "Southern Alps, Fiordland, Ruapehu, Taranaki",
      "Bilingual English and te reo Māori names"]),
    ("02_north_island", "player_map_4096.jpg", (0.50, 0.05, 0.95, 0.50), "Te Ika-a-Māui",
     ["Auckland, Hamilton, Tauranga, Rotorua", "The central volcanic plateau", "Waiouru Army Camp and RNZAF Base Ōhakea",
      "Hobbiton, Waitomo Caves, Huka Falls"]),
    ("03_south_island", "player_map_4096.jpg", (0.12, 0.38, 0.62, 0.88), "Te Waipounamu",
     ["Christchurch, Dunedin, Queenstown", "Aoraki / Mount Cook and the Southern Alps", "Milford Sound and Fiordland",
      "Burnham Military Camp"]),
    ("04_towns", "towns_2048.png", (0.55, 0.12, 0.85, 0.42), "51 towns and bases",
     ["Cities, towns and villages placed from real coordinates", "45 hamlets in the back country",
      "Hospitals, police, fire stations, pubs and churches", "Baches, surf clubs, holiday parks and DOC huts"]),
    ("05_roads_rail", "roads_2048.png", (0.55, 0.12, 0.85, 0.42), "Roads and rail",
     ["State highways, gravel back roads and town streets", "North Island Main Trunk and Main North Line",
      "18 railway stations", "Bridges, guardrails and power lines"]),
    ("06_christchurch", "satellite_christchurch.png", None, "Christchurch / Ōtautahi",
     ["Street grid on the Canterbury Plains", "ChristChurch Cathedral in ruins", "Satellite texture coloured from real imagery",
      "Lyttelton harbour over the hill"]),
    ("07_loot", "loot_tiers_2048.png", None, "New Zealand loot",
     ["Hunting rifles and shotguns on the farms", "NZDF Steyr AUGs at the bases, police Glocks",
      "Mānuka honey, milk powder, gumboots and raincoats", "Loot tiers rise inland, southwards and uphill"]),
    ("08_map_item", "map_item_sheet.png", None, "A survivor's map",
     ["Paper road map with the 1 km grid", "Every town and site with its grid square",
      "Printable player map included", "Designed for Aotearoa"]),
    ("09_food", "nz_food_showcase.png", None, "Kiwi tucker",
     ["L&P, Fresh Up, Foxton Fizz and Lift Plus", "Bluebird chips, Munchos and Pineapple Lumps",
      "Toffee Pops, Shrewsburys and Whittaker's", "Wattie's, Sealord, Weet-Bix and Marmite"]),
]


def font(path: str, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def background() -> Image.Image:
    art = Image.open(BRANDING / "art" / "loading_2.jpg").convert("RGB").resize((W, H), Image.LANCZOS)
    art = art.filter(ImageFilter.GaussianBlur(6))
    return Image.blend(art, Image.new("RGB", (W, H), (8, 12, 10)), 0.6)


def fit(img: Image.Image, box_w: int, box_h: int) -> Image.Image:
    scale = min(box_w / img.size[0], box_h / img.size[1])
    return img.resize((int(img.size[0] * scale), int(img.size[1] * scale)), Image.LANCZOS)


def card(src: Image.Image, title: str, lines: list[str], logo: Image.Image) -> Image.Image:
    im = background()
    pic = fit(src, 1100, 960)
    frame = Image.new("RGB", (pic.size[0] + 8, pic.size[1] + 8), INK)
    frame.paste(pic, (4, 4))
    im.paste(frame, (60, (H - frame.size[1]) // 2))

    x = 60 + frame.size[0] + 70
    badge = logo.resize((170, 170), Image.LANCZOS)
    im.paste(badge, (x, 70), badge)
    d = ImageDraw.Draw(im)
    bold, regular = watermark.FONT_BOLD, watermark.FONT
    size = 64
    while d.textlength(title, font=font(bold, size)) > W - x - 60 and size > 30:
        size -= 2
    d.text((x, 290), title, font=font(bold, size), fill=INK, stroke_width=3, stroke_fill=(0, 0, 0))
    d.line([(x, 390), (x + 380, 390)], fill=ACCENT, width=4)
    y = 425
    body = font(regular, 30)
    for line in lines:
        words, row = line.split(), ""
        for word in words:
            trial = f"{row} {word}".strip()
            if d.textlength("• " + trial, font=body) > W - x - 60:
                d.text((x, y), ("• " if not row.startswith(" ") else "  ") + row, font=body, fill=SOFT)
                y, row = y + 42, "  " + word
            else:
                row = trial
        d.text((x, y), "• " + row.strip() if not row.startswith(" ") else row, font=body, fill=SOFT)
        y += 58
    return watermark.stamp(im, [watermark.CREDIT, watermark.SITE], 40, margin=48, opacity=210)


def main() -> None:
    Image.MAX_IMAGE_PIXELS = None
    OUT.mkdir(parents=True, exist_ok=True)
    logo = Image.open(BRANDING / "logo_512.png").convert("RGBA")
    for name, file, crop, title, lines in SHOTS:
        src = Image.open(PREVIEW / file).convert("RGB")
        if crop:
            w, h = src.size
            src = src.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
        card(src, title, lines, logo).save(OUT / f"{name}.jpg", quality=90, optimize=True)
    print(f"Wrote {len(SHOTS)} screenshots to {OUT}")


if __name__ == "__main__":
    main()
