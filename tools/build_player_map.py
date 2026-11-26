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

import labelplace
import watermark
import fontpaths

MAP_DIR = Path(__file__).resolve().parents[1]
SOURCE = MAP_DIR / "source"
PREVIEW = MAP_DIR / "preview"
FONT = fontpaths.path("DejaVuSans.ttf")
FONT_BOLD = fontpaths.path("DejaVuSans-Bold.ttf")
FONT_ITALIC = fontpaths.path("DejaVuSans-Oblique.ttf")
TIER_STYLE = {  # font scale, dot radius scale
    "capital": (1.8, 1.6), "city": (1.45, 1.3), "town": (1.15, 1.0), "village": (0.9, 0.8), "military": (1.0, 1.0),
}
TOWN_ORDER = ["capital", "city", "military", "town", "village"]
# New Zealand map abbreviations, used where the text is scaled up on a small texture (the map item).
SHORT = [(" Surf Life Saving Club", " SLSC"), (" Holiday Park", " Holiday Pk"), ("Port of ", "Port "),
         (" Ferry Terminal", " Ferry")]
SITE_SYMBOL = {
    "airfield": ((40, 40, 40), "✈"), "port": ((30, 90, 200), "⚓"), "ferry": ((0, 170, 230), "⇄"),
    "naval": ((20, 40, 120), "⚓"), "industrial": ((120, 80, 40), "■"), "ski": ((255, 255, 255), "▲"),
    "hobbiton": ((250, 200, 0), "●"), "landmark": ((255, 255, 255), "★"), "whakaari": ((200, 40, 40), "☢"),
    "surfclub": ((255, 220, 0), "●"), "campground": ((60, 160, 60), "▲"),
    "wreck": ((210, 210, 210), "✖"), "military": ((120, 150, 70), "✪"), "gas": ((220, 230, 0), "☢"),
}
NAMED_SETTLEMENT = ((235, 225, 200), "●")  # named bach and fishing settlements such as Rakaia Huts


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def find_satellite(given: Path | None = None) -> Path:
    if given:
        return given
    best = max(SOURCE.glob("satellite_*.png"), key=lambda p: p.stat().st_size, default=None)
    return best or PREVIEW / "satellite_2048.png"


def load_sites() -> list[dict]:
    """The sites from pois.json plus the set pieces (landmarks, wrecks, base extensions)."""
    sites = json.loads((SOURCE / "pois.json").read_text(encoding="utf-8"))
    extra = SOURCE / "setpieces.json"
    if extra.exists():
        sites += [p for p in json.loads(extra.read_text(encoding="utf-8")) if p["kind"] != "military"]
    return sites


def load_towns() -> list[dict]:
    with (SOURCE / "towns.csv").open(encoding="utf-8") as f:
        return [t for t in csv.DictReader(f) if t["tier"] != "hamlet"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=4096)
    ap.add_argument("--satellite", type=Path)
    args = ap.parse_args()
    Image.MAX_IMAGE_PIXELS = None
    img = render(Image.open(find_satellite(args.satellite)), args.size)
    out = PREVIEW / f"player_map_{args.size}.jpg"
    img.save(out, quality=88)
    print(f"Wrote {out}")


def render(satellite: Image.Image, size: int, text_scale: float = 1.0, legend: bool = True) -> Image.Image:
    """The labelled map at size x size. text_scale > 1 keeps labels readable on small textures."""
    size_m = json.loads((SOURCE / "heightmap.json").read_text())["terrain_size_m"]
    img = satellite.convert("RGB").resize((size, size), Image.LANCZOS)
    k = size / size_m
    s = size / 4096 * text_scale

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
        d.line([(v, 0), (v, size)], fill=(255, 255, 255, 70), width=1)
        d.line([(0, v), (size, v)], fill=(255, 255, 255, 70), width=1)
        if i < size_m // 1000:
            label = f"{i:02d}"
            for pos in ((v + 6 * s, 4 * s), (v + 6 * s, size - 28 * s)):
                d.text(pos, label, font=grid_font, fill=(255, 255, 255, 220), stroke_width=2, stroke_fill=(0, 0, 0, 200))
            for pos in ((4 * s, v + 6 * s), (size - 34 * s, v + 6 * s)) if i else ():
                d.text(pos, label, font=grid_font, fill=(255, 255, 255, 220), stroke_width=2, stroke_fill=(0, 0, 0, 200))

    sym_font = font(fontpaths.path("DejaVuSans.ttf"), int(22 * s))
    site_font = font(FONT, int(15 * s))
    water_font = font(FONT_ITALIC, int(15 * s))
    sea_font = font(FONT_ITALIC, int(30 * s))
    peak_font = font(FONT, int(14 * s))
    placer = labelplace.Placer(d, img.size, pad=2 * s, stroke=2)

    # Symbols first, reserved so no label covers them.
    sites = []
    for p in load_sites():
        style = SITE_SYMBOL.get(p["kind"]) or (NAMED_SETTLEMENT if p["label"] and p["kind"] == "bach" else None)
        if not style:
            continue
        x, y = px(p["x"], p["y"])
        colour, sym = style
        d.text((x, y), sym, font=sym_font, anchor="mm", fill=colour + (255,), stroke_width=2, stroke_fill=(0, 0, 0, 255))
        placer.reserve((x - 9 * s, y - 9 * s, x + 9 * s, y + 9 * s))
        if p["label"]:
            label = p["label"]
            if text_scale > 1:
                for long, short in SHORT:
                    label = label.replace(long, short)
            sites.append((label, x, y))
    for st in roads.get("stations", []):
        x, y = px(st["x"], st["y"])
        r = 5 * s
        d.rectangle([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=2)
        placer.reserve((x - r, y - r, x + r, y + r))

    labels_path = SOURCE / "labels.json"
    features = json.loads(labels_path.read_text(encoding="utf-8")) if labels_path.exists() else []
    for lb in features:
        if lb["kind"] == "peak":
            x, y = px(*lb["xy"])
            d.text((x, y), "▲", font=sym_font, anchor="mm", fill=(120, 80, 50, 255), stroke_width=2,
                   stroke_fill=(255, 255, 255, 230))
            placer.reserve((x - 8 * s, y - 8 * s, x + 8 * s, y + 8 * s))

    towns = sorted(load_towns(), key=lambda t: (TOWN_ORDER.index(t["tier"]) if t["tier"] in TOWN_ORDER
                                                else len(TOWN_ORDER), -float(t["radius"])))
    rings = []
    for t in towns:
        _, dot = TIER_STYLE.get(t["tier"], (1.0, 1.0))
        x, y = px(float(t["x"]), float(t["y"]))
        r = max(4.0, float(t["radius"]) * k) * dot * 0.6
        rings.append((t, x, y, r))
    for t, x, y, r in sorted(rings, key=lambda a: -a[3]):
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 245, 200, 90), outline=(0, 0, 0, 230), width=2)
        placer.reserve((x - r, y - r, x + r, y + r))

    # Labels, most important first: towns, then sites, peaks, water and seas.
    for t, x, y, r in rings:
        scale, _ = TIER_STYLE.get(t["tier"], (1.0, 1.0))
        f1 = font(FONT_BOLD, int(19 * s * scale))
        name = (t["name"], f1, (255, 255, 255, 255))
        if t["maori"] and t["tier"] in ("capital", "city", "town"):
            maori = (t["maori"], font(FONT, int(14 * s * scale)), (220, 240, 255, 235))
            usual = placer._parts([name], x, y - r - 4 * s, "centre", "bottom") \
                + placer._parts([maori], x, y + r + 4 * s, "centre", "top")
            placer.label([name, maori], x, y, r=r, gap=4 * s, first=usual, stroke=max(2, int(3 * s)),
                         stroke_fill=(0, 0, 0, 255))
        else:
            first = placer._parts([name], x, y - r - 4 * s, "centre", "bottom")
            placer.label([name], x, y, r=r, gap=4 * s, first=first, stroke=max(2, int(3 * s)),
                         stroke_fill=(0, 0, 0, 255))
    for label, x, y in sites:
        placer.label([(label, site_font, (255, 255, 255, 235))], x, y, r=9 * s, gap=4 * s, stroke_fill=(0, 0, 0, 220))
    for lb in features:
        x, y = px(*lb["xy"])
        if lb["kind"] == "peak":
            placer.label([(lb["name"], peak_font, (255, 250, 235, 240))], x, y, r=8 * s, gap=4 * s,
                         stroke_fill=(60, 40, 20, 220))
    for lb in features:
        x, y = px(*lb["xy"])
        if lb["kind"] in ("river", "lake"):
            centre = placer._parts([(lb["name"], water_font, (190, 225, 255, 240))], x, y, "centre", "middle")
            placer.label([(lb["name"], water_font, (190, 225, 255, 240))], x, y, r=4 * s, gap=4 * s, first=centre,
                         optional=True, stroke_fill=(10, 40, 80, 220))
    for lb in features:
        x, y = px(*lb["xy"])
        if lb["kind"] == "sea":
            centre = placer._parts([(lb["name"], sea_font, (170, 205, 240, 200))], x, y, "centre", "middle")
            placer.label([(lb["name"], sea_font, (170, 205, 240, 200))], x, y, r=10 * s, gap=10 * s, first=centre,
                         stroke=0, optional=True)

    render.last = placer
    img = watermark.stamp(img, [watermark.CREDIT, watermark.SITE], 30 * s, opacity=150)
    d = ImageDraw.Draw(img, "RGBA")
    if not legend:
        return img
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
    by = size - 120 * s
    d.rectangle([x0, by, x0 + bar, by + 10 * s], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    d.rectangle([x0, by, x0 + bar / 2, by + 10 * s], fill=(0, 0, 0, 255))
    d.text((x0, by - 28 * s), "0", font=body, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
    d.text((x0 + bar, by - 28 * s), "2 km", font=body, anchor="ma", fill=(255, 255, 255, 255), stroke_width=2,
           stroke_fill=(0, 0, 0, 255))
    d.text((x0 + bar + 40 * s, by - 40 * s), "N ↑", font=title, fill=(255, 255, 255, 255), stroke_width=2,
           stroke_fill=(0, 0, 0, 255))
    return img


if __name__ == "__main__":
    main()
