"""A printable, labelled map for players: the satellite image with the grid, towns, sites,
roads, railway and a legend.

    python build_player_map.py [--size 4096] [--satellite ../path/to/satellite.png]

Reads the satellite from source/satellite_<n>.png (or --satellite), and writes
preview/player_map_<size>.jpg. Grid squares are 1 km and numbered like the in-game map.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MAP_DIR = Path(__file__).resolve().parents[1]
SOURCE = MAP_DIR / "source"
PREVIEW = MAP_DIR / "preview"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TIER_STYLE = {  # font scale, dot radius scale
    "capital": (1.8, 1.6), "city": (1.45, 1.3), "town": (1.15, 1.0), "village": (0.9, 0.8), "military": (1.0, 1.0),
}
SITE_SYMBOL = {
    "airfield": ((40, 40, 40), "✈"), "port": ((30, 90, 200), "⚓"), "ferry": ((0, 170, 230), "⇄"),
    "naval": ((20, 40, 120), "⚓"), "industrial": ((120, 80, 40), "■"), "ski": ((255, 255, 255), "▲"),
    "hobbiton": ((250, 200, 0), "●"), "landmark": ((255, 255, 255), "★"), "whakaari": ((200, 40, 40), "☢"),
    "surfclub": ((255, 220, 0), "●"), "campground": ((60, 160, 60), "▲"),
}


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=4096)
    ap.add_argument("--satellite", type=Path)
    args = ap.parse_args()
    Image.MAX_IMAGE_PIXELS = None

    meta = json.loads((SOURCE / "heightmap.json").read_text())
    size_m = meta["terrain_size_m"]
    sat_path = args.satellite or max(SOURCE.glob("satellite_*.png"), key=lambda p: p.stat().st_size, default=None)
    if sat_path is None:
        sat_path = PREVIEW / "satellite_2048.png"
    img = Image.open(sat_path).convert("RGB").resize((args.size, args.size), Image.LANCZOS)
    k = args.size / size_m
    s = args.size / 4096

    def px(x, y):
        return x * k, (size_m - y) * k

    d = ImageDraw.Draw(img, "RGBA")
    roads = json.loads((SOURCE / "roads.json").read_text(encoding="utf-8"))
    for road in roads["roads"]:
        if road["kind"] == "highway":
            d.line([px(*p) for p in road["points"]], fill=(230, 60, 40, 230), width=max(2, int(4 * s)), joint="curve")
        elif road["kind"] == "gravel":
            d.line([px(*p) for p in road["points"]], fill=(250, 230, 170, 200), width=max(1, int(2 * s)))
    for line in roads.get("rails", []):
        pts = [px(*p) for p in line["points"]]
        d.line(pts, fill=(20, 20, 20, 255), width=max(2, int(4 * s)))
        d.line(pts, fill=(250, 250, 250, 255), width=max(1, int(2 * s)))

    # 1 km grid, numbered from the north-west corner like the in-game map.
    grid_font = font(FONT_BOLD, int(20 * s))
    for i in range(0, int(size_m // 1000) + 1):
        v = i * 1000 * k
        d.line([(v, 0), (v, args.size)], fill=(255, 255, 255, 70), width=1)
        d.line([(0, v), (args.size, v)], fill=(255, 255, 255, 70), width=1)
        if i < size_m // 1000:
            label = f"{i:02d}"
            for pos in ((v + 6 * s, 4 * s), (v + 6 * s, args.size - 28 * s)):
                d.text(pos, label, font=grid_font, fill=(255, 255, 255, 220), stroke_width=2, stroke_fill=(0, 0, 0, 200))
            for pos in ((4 * s, v + 6 * s), (args.size - 34 * s, v + 6 * s)) if i else ():
                d.text(pos, label, font=grid_font, fill=(255, 255, 255, 220), stroke_width=2, stroke_fill=(0, 0, 0, 200))

    sym_font = font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(22 * s))
    site_font = font(FONT, int(15 * s))
    for p in json.loads((SOURCE / "pois.json").read_text(encoding="utf-8")):
        style = SITE_SYMBOL.get(p["kind"])
        if not style:
            continue
        x, y = px(p["x"], p["y"])
        colour, sym = style
        d.text((x, y), sym, font=sym_font, anchor="mm", fill=colour + (255,), stroke_width=2, stroke_fill=(0, 0, 0, 255))
        if p["label"]:
            d.text((x + 14 * s, y), p["label"], font=site_font, anchor="lm", fill=(255, 255, 255, 235),
                   stroke_width=2, stroke_fill=(0, 0, 0, 220))
    for st in roads.get("stations", []):
        x, y = px(st["x"], st["y"])
        r = 5 * s
        d.rectangle([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=2)

    with (SOURCE / "towns.csv").open(encoding="utf-8") as f:
        towns = [t for t in csv.DictReader(f) if t["tier"] != "hamlet"]
    for t in sorted(towns, key=lambda t: float(t["radius"])):
        scale, dot = TIER_STYLE.get(t["tier"], (1.0, 1.0))
        x, y = px(float(t["x"]), float(t["y"]))
        r = max(4.0, float(t["radius"]) * k) * dot * 0.6
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 245, 200, 90), outline=(0, 0, 0, 230), width=2)
        f1 = font(FONT_BOLD, int(19 * s * scale))
        d.text((x, y - r - 2 * s), t["name"], font=f1, anchor="md", fill=(255, 255, 255, 255),
               stroke_width=max(2, int(3 * s)), stroke_fill=(0, 0, 0, 255))
        if t["maori"] and t["tier"] in ("capital", "city", "town"):
            f2 = font(FONT, int(14 * s * scale))
            d.text((x, y + r + 2 * s), t["maori"], font=f2, anchor="ma", fill=(220, 240, 255, 235),
                   stroke_width=2, stroke_fill=(0, 0, 0, 230))

    # Title, legend and scale bar in the empty Tasman Sea.
    title = font(FONT_BOLD, int(64 * s))
    body = font(FONT, int(22 * s))
    x0, y0 = 60 * s, 90 * s
    d.rounded_rectangle([x0 - 20 * s, y0 - 20 * s, x0 + 560 * s, y0 + 520 * s], radius=int(16 * s), fill=(0, 0, 0, 150))
    d.text((x0, y0), "AOTEAROA", font=title, fill=(255, 255, 255, 255))
    d.text((x0, y0 + 76 * s), "Survivor's map, 1 km grid", font=body, fill=(230, 230, 230, 255))
    yy = y0 + 130 * s
    legend = [("line", (230, 60, 40), "State highway"), ("line", (250, 230, 170), "Gravel road"),
              ("rail", None, "Railway, □ station")]
    legend += [("sym", SITE_SYMBOL[k_][0], (SITE_SYMBOL[k_][1], label)) for k_, label in (
        ("airfield", "Airfield"), ("port", "Port"), ("ferry", "Interislander ferry"), ("industrial", "Industry"),
        ("ski", "Ski field"), ("landmark", "Landmark"), ("surfclub", "Surf club"), ("campground", "Holiday park"),
        ("whakaari", "Toxic zone"))]
    for kind, colour, text in legend:
        if kind == "line":
            d.line([(x0, yy + 12 * s), (x0 + 40 * s, yy + 12 * s)], fill=colour + (255,), width=max(2, int(4 * s)))
            d.text((x0 + 55 * s, yy), text, font=body, fill=(255, 255, 255, 255))
        elif kind == "rail":
            d.line([(x0, yy + 12 * s), (x0 + 40 * s, yy + 12 * s)], fill=(20, 20, 20, 255), width=max(2, int(4 * s)))
            d.line([(x0, yy + 12 * s), (x0 + 40 * s, yy + 12 * s)], fill=(250, 250, 250, 255), width=max(1, int(2 * s)))
            d.text((x0 + 55 * s, yy), text, font=body, fill=(255, 255, 255, 255))
        else:
            sym, label = text
            d.text((x0 + 20 * s, yy + 12 * s), sym, font=sym_font, anchor="mm", fill=colour + (255,),
                   stroke_width=2, stroke_fill=(255, 255, 255, 255) if sum(colour) < 200 else (0, 0, 0, 255))
            d.text((x0 + 55 * s, yy), label, font=body, fill=(255, 255, 255, 255))
        yy += 30 * s
    bar = 2000 * k
    by = args.size - 120 * s
    d.rectangle([x0, by, x0 + bar, by + 10 * s], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    d.rectangle([x0, by, x0 + bar / 2, by + 10 * s], fill=(0, 0, 0, 255))
    d.text((x0, by - 28 * s), "0", font=body, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
    d.text((x0 + bar, by - 28 * s), "2 km", font=body, anchor="ma", fill=(255, 255, 255, 255), stroke_width=2,
           stroke_fill=(0, 0, 0, 255))
    d.text((x0 + bar + 40 * s, by - 40 * s), "N ↑", font=title, fill=(255, 255, 255, 255), stroke_width=2,
           stroke_fill=(0, 0, 0, 255))

    out = PREVIEW / f"player_map_{args.size}.jpg"
    img.save(out, quality=88)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
