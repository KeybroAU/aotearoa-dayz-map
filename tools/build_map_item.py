"""Textures for the paper map item, AotearoaMap (the mapitem/ mod), and for vanilla ChernarusMap on
this terrain (CfgWorlds mapTexture* in config.cpp).

    python build_map_item.py [--opened 2048] [--legend 1024x2048] [--closed 1024x2048]

The item has three textures, as on vanilla ChernarusMap:
    closed   the folded map's cover
    opened   the unfolded sheet: the labelled map with the 1 km grid
    legend   the side panel: key, then every town and named site with its grid square

Writes mapitem/data/aotearoa_map_{closed,opened,legend}.png and preview/map_item_sheet.png.
pack_mod.py turns them into _co.paa in both mapitem/data/ and data/mapitem/. Compare the sizes with
vanilla P:\\DZ\\gear\\navigation\\data\\ and P:\\DZ\\structures\\signs\\tourist\\data\\karta_*.paa and
pass other sizes if the sheet looks squashed in game.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

import build_player_map as pm
import watermark

MAP_DIR = Path(__file__).resolve().parents[1]
OUT = MAP_DIR / "mapitem" / "data"
PAPER = (238, 230, 208)
INK = (40, 34, 26)
GREEN = (24, 66, 48)

def size_arg(text: str) -> tuple[int, int]:
    w, _, h = text.lower().partition("x")
    return int(w), int(h or w)


def grid_ref(x: float, y: float, size_m: float) -> str:
    """Square numbers as on the in-game map and the player map: across from the west, down from the north."""
    return f"{int(x // 1000):02d}-{int((size_m - y) // 1000):02d}"


def places(size_m: float) -> tuple[list[tuple], list[tuple]]:
    towns = [(t["name"], t["tier"], grid_ref(float(t["x"]), float(t["y"]), size_m)) for t in pm.load_towns()]
    pois = pm.load_sites()
    sites = [(p["label"], p["kind"], grid_ref(p["x"], p["y"], size_m)) for p in pois if p["label"]]
    return sorted(towns), sorted(sites)


def opened(size: int) -> Image.Image:
    sat = Image.open(pm.PREVIEW / "satellite_2048.png").convert("RGB").resize((size, size), Image.LANCZOS)
    printed = Image.blend(sat, Image.new("RGB", sat.size, PAPER), 0.22)
    img = pm.render(printed, size, text_scale=4096 / size * 0.62, legend=False)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, size - 1, size - 1], outline=PAPER, width=max(4, size // 256))
    return img


def legend(w: int, h: int, size_m: float) -> Image.Image:
    img = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(img)
    u = w / 1024
    title, sub = pm.font(pm.FONT_BOLD, int(76 * u)), pm.font(pm.FONT, int(26 * u))
    head, body = pm.font(pm.FONT_BOLD, int(26 * u)), pm.font(pm.FONT, int(19 * u))
    sym_font = pm.font(pm.FONT, int(22 * u))
    d.rectangle([0, 0, w, 150 * u], fill=GREEN)
    d.text((w / 2, 62 * u), "AOTEAROA", font=title, anchor="mm", fill=PAPER)
    d.text((w / 2, 118 * u), "Survivor's map  ·  1 km grid  ·  north up", font=sub, anchor="mm", fill=PAPER)

    y = 180 * u
    d.text((40 * u, y), "KEY", font=head, fill=INK)
    y += 40 * u
    key = [("line", (230, 60, 40), "State highway"), ("line", (200, 170, 100), "Gravel road"),
           ("rail", None, "Railway, □ station"), ("town", None, "Town or city")]
    key += [("sym", k, label) for k, label in (
        ("airfield", "Airfield"), ("port", "Port"), ("ferry", "Interislander ferry"), ("industrial", "Industry"),
        ("ski", "Ski field"), ("landmark", "Landmark"), ("surfclub", "Surf club"), ("campground", "Holiday park"),
        ("whakaari", "Toxic zone"))]
    col_w = (w - 80 * u) / 2
    for i, (kind, what, label) in enumerate(key):
        x = 40 * u + (i % 2) * col_w
        yy = y + (i // 2) * 34 * u
        mid = yy + 12 * u
        if kind == "line":
            d.line([(x, mid), (x + 40 * u, mid)], fill=what, width=max(2, int(5 * u)))
        elif kind == "rail":
            d.line([(x, mid), (x + 40 * u, mid)], fill=(20, 20, 20), width=max(2, int(6 * u)))
            d.line([(x, mid), (x + 40 * u, mid)], fill=(250, 250, 250), width=max(1, int(2 * u)))
        elif kind == "town":
            d.ellipse([x + 10 * u, mid - 10 * u, x + 30 * u, mid + 10 * u], fill=(255, 245, 200), outline=INK, width=2)
        else:
            colour, sym = pm.SITE_SYMBOL[what]
            d.text((x + 20 * u, mid), sym, font=sym_font, anchor="mm", fill=colour, stroke_width=2,
                   stroke_fill=INK if sum(colour) > 200 else PAPER)
        d.text((x + 55 * u, yy), label, font=body, fill=INK)
    y += ((len(key) + 1) // 2) * 34 * u + 24 * u

    towns, sites = places(size_m)
    columns = [("TOWNS AND CITIES", [(None, n, g) for n, _, g in towns]),
               ("PLACES", [(k, n, g) for n, k, g in sites])]
    d.text((40 * u, y), "GRID SQUARES  (across - down)", font=head, fill=INK)
    y += 44 * u
    line_h = min(30 * u, (h - 40 * u - y) / (max(len(rows) for _, rows in columns) + 1))
    body = pm.font(pm.FONT, max(10, int(line_h * 0.72)))
    head = pm.font(pm.FONT_BOLD, max(10, int(line_h * 0.78)))
    small_sym = pm.font(pm.FONT, max(10, int(line_h * 0.7)))
    for c, (title_text, rows) in enumerate(columns):
        x = 40 * u + c * col_w
        right = x + col_w - 24 * u
        d.text((x, y), title_text, font=head, fill=GREEN)
        for i, (kind, name, ref) in enumerate(rows, start=1):
            yy = y + i * line_h
            left = x
            if kind:
                colour, sym = pm.SITE_SYMBOL.get(kind) or pm.NAMED_SETTLEMENT
                d.text((x + 8 * u, yy + line_h * 0.45), sym, font=small_sym, anchor="mm", fill=colour,
                       stroke_width=1, stroke_fill=INK if sum(colour) > 200 else PAPER)
                left = x + 22 * u
            while name and d.textlength(name, font=body) > right - left - 70 * u:
                name = name[:-2] + "…"
            d.text((left, yy), name, font=body, fill=INK)
            d.text((right, yy), ref, font=body, anchor="ra", fill=INK)
            start = left + d.textlength(name, font=body) + 6 * u
            end = right - d.textlength(ref, font=body) - 6 * u
            if end > start:
                d.line([(start, yy + line_h * 0.62), (end, yy + line_h * 0.62)], fill=(170, 160, 140), width=1)
    d.text((w / 2, h - 18 * u), f"{watermark.CREDIT}  ·  {watermark.SITE}", font=pm.font(pm.FONT, int(16 * u)),
           anchor="mm", fill=GREEN)
    return img


def closed(w: int, h: int, sheet: Image.Image) -> Image.Image:
    """Cover: title band over a crop of the sheet, like a folded road map."""
    img = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(img)
    u = w / 1024
    band = int(h * 0.26)
    d.rectangle([0, 0, w, band], fill=GREEN)
    d.text((w / 2, band * 0.42), "AOTEAROA", font=pm.font(pm.FONT_BOLD, int(150 * u)), anchor="mm", fill=PAPER)
    d.text((w / 2, band * 0.78), "ROAD  ·  RAIL  ·  TRACK", font=pm.font(pm.FONT, int(46 * u)), anchor="mm",
           fill=PAPER)
    margin = int(40 * u)
    box_w, box_h = w - 2 * margin, h - band - 2 * margin - int(110 * u)
    s = sheet.size[0]
    cw = int(s * 0.42)
    ch = int(cw * box_h / box_w)
    cx, cy = int(s * 0.62), int(s * 0.32)
    crop = sheet.crop((cx - cw // 2, cy - ch // 2, cx + cw // 2, cy + ch // 2)).resize((box_w, box_h), Image.LANCZOS)
    img.paste(crop, (margin, band + margin))
    d.rectangle([margin, band + margin, margin + box_w, band + margin + box_h], outline=INK, width=max(2, int(4 * u)))
    d.text((w / 2, h - int(86 * u)), "New Zealand  ·  Te Ika-a-Māui  ·  Te Waipounamu",
           font=pm.font(pm.FONT_BOLD, int(36 * u)), anchor="mm", fill=INK)
    d.text((w / 2, h - int(40 * u)), f"{watermark.CREDIT}  ·  {watermark.SITE}",
           font=pm.font(pm.FONT, int(26 * u)), anchor="mm", fill=GREEN)
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--opened", type=int, default=2048)
    ap.add_argument("--legend", type=size_arg, default=(1024, 2048))
    ap.add_argument("--closed", type=size_arg, default=(1024, 2048))
    args = ap.parse_args()
    size_m = json.loads((pm.SOURCE / "heightmap.json").read_text())["terrain_size_m"]

    OUT.mkdir(parents=True, exist_ok=True)
    sheet = opened(args.opened)
    side = legend(*args.legend, size_m)
    cover = closed(*args.closed, sheet)
    for name, img in (("opened", sheet), ("legend", side), ("closed", cover)):
        path = OUT / f"aotearoa_map_{name}.png"
        img.save(path, optimize=True)
        print(f"Wrote {path} {img.size[0]}x{img.size[1]}")

    h = 1024
    parts = [im.resize((round(im.size[0] * h / im.size[1]), h), Image.LANCZOS) for im in (cover, sheet, side)]
    preview = Image.new("RGB", (sum(p.size[0] for p in parts) + 40 * (len(parts) + 1), h + 80), (60, 60, 60))
    x = 40
    for p in parts:
        preview.paste(p, (x, 40))
        x += p.size[0] + 40
    preview.save(pm.PREVIEW / "map_item_sheet.png", optimize=True)
    towns, sites = places(size_m)
    print(f"Wrote {pm.PREVIEW / 'map_item_sheet.png'}: {len(towns)} towns and {len(sites)} places listed")


if __name__ == "__main__":
    main()
