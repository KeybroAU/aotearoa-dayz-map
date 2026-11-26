"""New Zealand food and drink: retextured vanilla cans, tins, chip bags and biscuit packets.

    python nz_food.py

Every item inherits a vanilla class and only swaps the texture of its camoGround selection, so it
keeps the vanilla model, nutrition, sounds and actions. It writes:

  data/food/<key>.png                the label artwork (pack_mod.py converts it to <key>_co.paa)
  config/food.hpp                    the item classes, included inside CfgVehicles in config.cpp
  scripts/4_World/AotearoaFood.c     tins open into their own opened class instead of the vanilla one
  preview/nz_food.png                every texture on one sheet

economy.py takes the loot entries from ITEMS: each item copies its vanilla class's types.xml entry,
and the vanilla classes they replace are set to nominal 0.

The texture layouts follow the vanilla UV maps: the soda can label is the band at the bottom of the
texture with the lids above it, food tins wrap the label round the lower part, and the chip bag
model shows the whole square on each face with the crimped seals at the top and bottom.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

MAP_DIR = Path(__file__).resolve().parents[1]
OUT = MAP_DIR / "data" / "food"
TEXTURE = "maps\\aotearoa\\data\\food\\{}_co.paa"
FONTS = {
    "sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "italic": "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
    "serif": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "script": "/usr/share/fonts/truetype/liberation/LiberationSerif-BoldItalic.ttf",
    "plain": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
}

# Label band of each vanilla layout as fractions of the texture (x0, y0, x1, y1), the texture size,
# and how many times the front repeats round the can.
LAYOUTS = {
    "soda": ((0.0, 0.466, 0.85, 0.946), (1024, 1024), 2),
    "tin": ((0.0, 0.571, 1.0, 0.973), (1024, 1024), 2),
    "tin250": ((0.0, 0.758, 1.0, 0.961), (1024, 512), 3),
    "tin100": ((0.0, 0.0, 1.0, 1.0), (1024, 512), 2),
    "bag": ((0.0, 0.0, 1.0, 1.0), (1024, 1024), 1),
}


@dataclass
class Item:
    key: str
    cls: str
    base: str
    layout: str
    name: str
    desc: str
    loot: tuple[int, int]
    art: dict
    opened: str | None = None
    usages: list[str] | None = None


SODA = "A 355 ml can. "
ITEMS = [
    # Fizzy drinks: one for each vanilla soda can.
    Item("lp", "Aotearoa_SodaCan_LP", "SodaCan_Cola", "soda", "L&P",
         "Lemon & Paeroa. " + SODA + "Sweet, lemony and made in Paeroa since 1907.", (20, 16),
         dict(brand="L&P", sub="LEMON & PAEROA", tag="Since 1907", bg=(247, 205, 30), bg2=(120, 72, 30),
              fg=(70, 40, 18), motif="lp")),
    Item("freshup", "Aotearoa_SodaCan_FreshUp", "SodaCan_Fronta", "soda", "Fresh Up Apple",
         SODA + "Sparkling apple juice drink.", (20, 16),
         dict(brand="Fresh Up", sub="SPARKLING APPLE", tag="NZ apples", bg=(46, 150, 60), bg2=(200, 230, 90),
              fg=(255, 255, 255), motif="apples")),
    Item("foxton_cream", "Aotearoa_SodaCan_FoxtonCream", "SodaCan_Spite", "soda", "Foxton Fizz Creaming Soda",
         SODA + "Creaming soda from Foxton.", (20, 16),
         dict(brand="Foxton Fizz", sub="CREAMING SODA", tag="Est. 1918", bg=(250, 238, 214), bg2=(226, 80, 140),
              fg=(140, 30, 80), motif="bubbles")),
    Item("foxton_rasp", "Aotearoa_SodaCan_FoxtonRaspberry", "SodaCan_Pipsi", "soda", "Foxton Fizz Raspberry",
         SODA + "Raspberry soda from Foxton.", (20, 16),
         dict(brand="Foxton Fizz", sub="RASPBERRY", tag="Est. 1918", bg=(196, 22, 60), bg2=(250, 160, 190),
              fg=(255, 255, 255), motif="bubbles")),
    Item("liftplus", "Aotearoa_SodaCan_LiftPlus", "SodaCan_Kvass", "soda", "Lift Plus",
         SODA + "Lemon energy drink with guarana.", (20, 16),
         dict(brand="Lift Plus", sub="ENERGY", tag="with guarana", bg=(250, 222, 40), bg2=(20, 70, 160),
              fg=(20, 50, 130), motif="bolt")),
    # Bluebird chips and Munchos, on the vanilla chip bag.
    Item("bluebird_salted", "Aotearoa_Chips_BluebirdReadySalted", "Chips", "bag", "Bluebird Ready Salted",
         "Bluebird Originals ready salted potato chips.", (7, 5),
         dict(brand="Bluebird", sub="READY SALTED", tag="Originals", bg=(22, 80, 170), bg2=(120, 190, 240),
              fg=(255, 255, 255), motif="chips", flavour=(240, 240, 240))),
    Item("bluebird_vinegar", "Aotearoa_Chips_BluebirdSaltVinegar", "Chips", "bag", "Bluebird Salt & Vinegar",
         "Bluebird Originals salt and vinegar potato chips.", (7, 5),
         dict(brand="Bluebird", sub="SALT & VINEGAR", tag="Originals", bg=(30, 140, 70), bg2=(170, 225, 120),
              fg=(255, 255, 255), motif="chips", flavour=(220, 240, 200))),
    Item("bluebird_chicken", "Aotearoa_Chips_BluebirdChicken", "Chips", "bag", "Bluebird Chicken",
         "Bluebird Originals chicken flavoured potato chips.", (7, 5),
         dict(brand="Bluebird", sub="CHICKEN", tag="Originals", bg=(245, 170, 20), bg2=(255, 225, 120),
              fg=(255, 255, 255), motif="chips", flavour=(250, 230, 160))),
    Item("munchos", "Aotearoa_Chips_MunchosTomato", "Chips", "bag", "Munchos Tomato",
         "Munchos tomato flavoured potato crisps.", (7, 5),
         dict(brand="Munchos", sub="TOMATO", tag="crunchy crisps", bg=(206, 28, 34), bg2=(255, 200, 40),
              fg=(255, 230, 60), motif="tomatoes")),
    # Griffin's biscuits, on the vanilla crackers packet.
    Item("toffeepops", "Aotearoa_Biscuits_ToffeePops", "Crackers", "bag", "Griffin's Toffee Pops",
         "Griffin's Toffee Pops: chocolate coated biscuits with a caramel centre.", (8, 6),
         dict(brand="Griffin's", sub="TOFFEE POPS", tag="caramel centre", bg=(170, 20, 30), bg2=(240, 190, 90),
              fg=(255, 255, 255), motif="toffeepops")),
    Item("shrewsburys", "Aotearoa_Biscuits_Shrewsburys", "Crackers", "bag", "Griffin's Shrewsburys",
         "Griffin's Shrewsburys: shortbread biscuits with a raspberry jam centre.", (8, 6),
         dict(brand="Griffin's", sub="SHREWSBURYS", tag="raspberry jam", bg=(230, 90, 130), bg2=(255, 230, 200),
              fg=(255, 255, 255), motif="shrewsburys")),
    Item("chocthins", "Aotearoa_Biscuits_ChocolateThins", "Crackers", "bag", "Griffin's Chocolate Thins",
         "Griffin's Chocolate Thins: thin crisp chocolate biscuits.", (8, 6),
         dict(brand="Griffin's", sub="CHOCOLATE THINS", tag="thin & crispy", bg=(50, 30, 90), bg2=(200, 160, 80),
              fg=(255, 255, 255), motif="chocthins")),
    # Wattie's tins.
    Item("watties_beans", "Aotearoa_Watties_BakedBeans", "BakedBeansCan", "tin", "Wattie's Baked Beans",
         "Wattie's baked beans in tomato sauce. 420 g.", (25, 18),
         dict(brand="Wattie's", sub="BAKED BEANS", tag="in tomato sauce", bg=(250, 250, 245), bg2=(200, 30, 40),
              fg=(200, 30, 40), motif="beans"),
         opened="BakedBeansCan_Opened", usages=["Town", "Village", "Hunting"]),
    Item("watties_spaghetti", "Aotearoa_Watties_Spaghetti", "SpaghettiCan", "tin", "Wattie's Spaghetti",
         "Wattie's spaghetti in tomato sauce. 420 g.", (18, 14),
         dict(brand="Wattie's", sub="SPAGHETTI", tag="in tomato sauce", bg=(250, 250, 245), bg2=(230, 120, 20),
              fg=(200, 30, 40), motif="spaghetti"),
         opened="SpaghettiCan_Opened"),
    Item("watties_peaches", "Aotearoa_Watties_Peaches", "PeachesCan", "tin", "Wattie's Peach Slices",
         "Wattie's Hawke's Bay peach slices in juice. 410 g.", (25, 18),
         dict(brand="Wattie's", sub="PEACH SLICES", tag="Hawke's Bay", bg=(250, 250, 245), bg2=(250, 150, 50),
              fg=(200, 30, 40), motif="peaches"),
         opened="PeachesCan_Opened", usages=["Town", "Village", "School"]),
    Item("palm_cornedbeef", "Aotearoa_Palm_CornedBeef", "PorkCan", "tin250", "Palm Corned Beef",
         "Palm corned beef. A Kiwi and Pacific favourite, fried with onion.", (18, 14),
         dict(brand="Palm", sub="CORNED BEEF", tag="", bg=(190, 20, 30), bg2=(240, 200, 60),
              fg=(255, 230, 120), motif="palm"),
         opened="PorkCan_Opened"),
    Item("marmite", "Aotearoa_Marmite", "BrisketSpread", "tin100", "Marmite",
         "Marmite yeast spread. You either love it or you hate it.", (20, 15),
         dict(brand="Marmite", sub="YEAST SPREAD", tag="made in NZ", bg=(250, 200, 20), bg2=(200, 20, 30),
              fg=(20, 20, 20), motif="marmite"),
         opened="BrisketSpread_Opened"),
]
ITEM_CLASSES = {i.cls for i in ITEMS} | {i.cls + "_Opened" for i in ITEMS if i.opened}


def replaced() -> list[str]:
    """Vanilla classes whose loot the New Zealand items take over."""
    return sorted({i.base for i in ITEMS})


def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONTS[kind], max(6, int(size)))
    except OSError:
        return ImageFont.load_default()


def fit(d: ImageDraw.ImageDraw, text: str, kind: str, width: float, height: float) -> ImageFont.FreeTypeFont:
    size = int(height)
    while size > 6:
        f = font(kind, size)
        b = d.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= width and b[3] - b[1] <= height:
            return f
        size -= 2
    return font(kind, 6)


def text(d, xy, s, kind, width, height, fill, stroke=0, stroke_fill=(0, 0, 0)):
    f = fit(d, s, kind, width, height)
    d.text(xy, s, font=f, fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=stroke_fill)


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def noise(size, sigma, rng) -> Image.Image:
    """Grey Gaussian noise round 128, seeded so the textures rebuild identically."""
    g = np.random.default_rng(rng.randrange(2**32)).normal(128, sigma, (size[1], size[0]))
    return Image.fromarray(np.clip(g, 0, 255).astype(np.uint8), "L")


def metal(size, rng) -> Image.Image:
    """Brushed tinplate for the parts of a texture outside the label."""
    w, h = size
    streaks = noise((max(1, w // 64), h), 14, rng).resize((w, h), Image.BILINEAR)
    grain = noise((w, h), 6, rng)
    im = Image.blend(streaks, grain, 0.35).point(lambda v: int(170 + (v - 128) * 0.6))
    im = im.filter(ImageFilter.BoxBlur(1))
    return Image.merge("RGB", (im, im, im.point(lambda v: min(255, v + 6))))


def wear(im: Image.Image, rng, amount=10) -> Image.Image:
    """Fine grain and a few scuffs so the labels sit with DayZ's worn vanilla textures."""
    w, h = im.size
    grain = noise((w, h), amount, rng).convert("RGB")
    im = Image.blend(im, Image.composite(im, grain, Image.new("L", (w, h), 230)), 0.5)
    d = ImageDraw.Draw(im, "RGBA")
    for _ in range(int(w * h / 9000)):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.uniform(1, 4)
        d.ellipse((x - r, y - r * 0.4, x + r, y + r * 0.4), fill=(255, 255, 255, rng.randint(15, 45)))
    return im


# Motifs: small drawings for the lower half of a front panel, inside box (x0, y0, x1, y1).

def m_chips(d, box, a, rng):
    x0, y0, x1, y1 = box
    for _ in range(26):
        cx, cy = rng.uniform(x0 + 0.1 * (x1 - x0), x1 - 0.1 * (x1 - x0)), rng.uniform(y0 + 0.3 * (y1 - y0), y1)
        rx, ry = rng.uniform(0.08, 0.13) * (x1 - x0), rng.uniform(0.04, 0.07) * (x1 - x0)
        base = (238, 190, 80) if rng.random() < 0.7 else (225, 165, 60)
        d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=base, outline=shade(base, 0.7), width=3)
        d.arc((cx - rx * 0.7, cy - ry * 0.6, cx + rx * 0.7, cy + ry * 0.6), 200, 340, fill=shade(base, 1.12), width=4)
        for _ in range(3):
            fx, fy = cx + rng.uniform(-rx, rx) * 0.6, cy + rng.uniform(-ry, ry) * 0.5
            d.ellipse((fx - 3, fy - 3, fx + 3, fy + 3), fill=a.get("flavour", (240, 240, 240)))


def m_bird(d, cx, cy, s, fill):
    """A small bird in flight (the Bluebird mark, drawn from scratch)."""
    body = [(cx - s, cy), (cx - 0.2 * s, cy - 0.25 * s), (cx + 0.6 * s, cy - 0.2 * s), (cx + s, cy - 0.45 * s),
            (cx + 0.85 * s, cy - 0.05 * s), (cx + 0.3 * s, cy + 0.2 * s), (cx - 0.4 * s, cy + 0.15 * s)]
    wing = [(cx - 0.3 * s, cy - 0.15 * s), (cx + 0.1 * s, cy - 0.9 * s), (cx + 0.35 * s, cy - 0.85 * s),
            (cx + 0.25 * s, cy - 0.15 * s)]
    d.polygon(body, fill=fill)
    d.polygon(wing, fill=fill)
    d.ellipse((cx + 0.62 * s, cy - 0.38 * s, cx + 0.72 * s, cy - 0.28 * s), fill=(20, 20, 40))


def m_tomatoes(d, box, a, rng):
    x0, y0, x1, y1 = box
    w = x1 - x0
    for cx, cy, r in ((0.3, 0.62, 0.17), (0.66, 0.66, 0.2), (0.48, 0.42, 0.14)):
        X, Y, R = x0 + cx * w, y0 + cy * (y1 - y0), r * w
        d.ellipse((X - R, Y - R * 0.9, X + R, Y + R * 0.9), fill=(230, 40, 30), outline=(150, 15, 15), width=4)
        d.ellipse((X - R * 0.5, Y - R * 0.6, X - R * 0.1, Y - R * 0.3), fill=(255, 140, 120))
        for k in range(5):
            t = k * 2 * math.pi / 5
            d.line((X, Y - R * 0.85, X + math.cos(t) * R * 0.35, Y - R * 0.85 + math.sin(t) * R * 0.2),
                   fill=(40, 130, 40), width=6)
    m_chips(d, (x0, y0 + 0.35 * (y1 - y0), x1, y1), dict(flavour=(230, 60, 40)), rng)


def biscuit(d, X, Y, R, kind):
    if kind == "toffeepops":
        d.ellipse((X - R, Y - R * 0.55, X + R, Y + R * 0.55), fill=(70, 38, 20), outline=(35, 18, 8), width=4)
        d.ellipse((X - R * 0.92, Y - R * 0.62, X + R * 0.92, Y + R * 0.38), fill=(92, 52, 28))
        d.arc((X - R * 0.7, Y - R * 0.45, X + R * 0.4, Y + R * 0.1), 190, 290, fill=(150, 100, 70), width=5)
    elif kind == "shrewsburys":
        d.ellipse((X - R, Y - R * 0.55, X + R, Y + R * 0.55), fill=(232, 196, 130), outline=(180, 140, 80), width=4)
        for k in range(16):
            t = k * 2 * math.pi / 16
            d.ellipse((X + math.cos(t) * R * 0.92 - 5, Y + math.sin(t) * R * 0.5 - 4,
                       X + math.cos(t) * R * 0.92 + 5, Y + math.sin(t) * R * 0.5 + 4), fill=(210, 170, 100))
        d.ellipse((X - R * 0.32, Y - R * 0.2, X + R * 0.32, Y + R * 0.2), fill=(190, 20, 50), outline=(120, 10, 30), width=3)
        d.ellipse((X - R * 0.18, Y - R * 0.14, X - R * 0.02, Y - R * 0.06), fill=(240, 110, 130))
    else:
        d.ellipse((X - R, Y - R * 0.5, X + R, Y + R * 0.5), fill=(55, 30, 18), outline=(25, 12, 6), width=3)
        d.ellipse((X - R * 0.95, Y - R * 0.5, X + R * 0.95, Y + R * 0.36), fill=(78, 44, 26))
        for k in range(6):
            d.line((X - R * 0.6 + k * R * 0.24, Y - R * 0.3, X - R * 0.7 + k * R * 0.24, Y + R * 0.2),
                   fill=(95, 58, 36), width=3)


def m_biscuits(d, box, a, rng):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    for i, (cx, cy) in enumerate(((0.22, 0.55), (0.52, 0.48), (0.8, 0.56), (0.36, 0.8), (0.67, 0.82))):
        biscuit(d, x0 + cx * w, y0 + cy * h, 0.17 * w, a["motif"])


def m_bubbles(d, box, a, rng):
    x0, y0, x1, y1 = box
    for _ in range(40):
        r = rng.uniform(4, 22)
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        d.ellipse((x - r, y - r, x + r, y + r), outline=shade(a["bg2"], 1.0), width=3)
        d.ellipse((x - r * 0.5, y - r * 0.6, x - r * 0.1, y - r * 0.2), fill=(255, 255, 255))


def m_apples(d, box, a, rng):
    x0, y0, x1, y1 = box
    w = x1 - x0
    for cx, cy, r in ((0.32, 0.6, 0.17), (0.66, 0.66, 0.19)):
        X, Y, R = x0 + cx * w, y0 + cy * (y1 - y0), r * w
        d.ellipse((X - R, Y - R * 0.9, X - R * 0.05, Y + R * 0.9), fill=(120, 200, 60))
        d.ellipse((X + R * 0.05, Y - R * 0.9, X + R, Y + R * 0.9), fill=(120, 200, 60))
        d.ellipse((X - R * 0.8, Y - R * 0.6, X + R * 0.8, Y + R * 0.95), fill=(110, 190, 55), outline=(40, 110, 30), width=3)
        d.line((X, Y - R * 0.8, X + R * 0.1, Y - R * 1.15), fill=(90, 60, 30), width=6)
        d.ellipse((X + R * 0.1, Y - R * 1.2, X + R * 0.55, Y - R * 0.95), fill=(60, 150, 50))
        d.ellipse((X - R * 0.55, Y - R * 0.45, X - R * 0.25, Y - R * 0.1), fill=(200, 240, 160))
    m_bubbles(d, box, dict(bg2=(220, 245, 200)), rng)


def m_bolt(d, box, a, rng):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    pts = [(0.55, 0.0), (0.25, 0.55), (0.48, 0.55), (0.38, 1.0), (0.78, 0.38), (0.54, 0.38), (0.68, 0.0)]
    d.polygon([(x0 + px * w, y0 + py * h) for px, py in pts], fill=a["bg2"], outline=(255, 255, 255))


def m_lp(d, box, a, rng):
    x0, y0, x1, y1 = box
    w = x1 - x0
    X, Y, R = x0 + 0.5 * w, y0 + 0.55 * (y1 - y0), 0.22 * w
    d.ellipse((X - R, Y - R * 0.75, X + R, Y + R * 0.75), fill=(255, 235, 60), outline=(200, 160, 20), width=5)
    d.ellipse((X + R * 0.8, Y - R * 0.2, X + R * 1.1, Y + R * 0.2), fill=(255, 235, 60), outline=(200, 160, 20), width=4)
    d.ellipse((X - R * 0.55, Y - R * 0.5, X - R * 0.15, Y - R * 0.2), fill=(255, 250, 190))
    m_bubbles(d, box, dict(bg2=(255, 245, 200)), rng)


def m_beans(d, box, a, rng):
    x0, y0, x1, y1 = box
    X, Y = (x0 + x1) / 2, y0 + 0.6 * (y1 - y0)
    R = 0.36 * (x1 - x0)
    d.ellipse((X - R, Y - R * 0.45, X + R, Y + R * 0.45), fill=(240, 240, 235), outline=(170, 170, 170), width=4)
    d.ellipse((X - R * 0.85, Y - R * 0.33, X + R * 0.85, Y + R * 0.33), fill=(205, 70, 30))
    for _ in range(70):
        bx, by = X + rng.uniform(-0.75, 0.75) * R, Y + rng.uniform(-0.25, 0.25) * R
        if ((bx - X) / (0.8 * R)) ** 2 + ((by - Y) / (0.3 * R)) ** 2 > 1:
            continue
        d.ellipse((bx - 9, by - 6, bx + 9, by + 6), fill=(235, 140, 70), outline=(170, 70, 30), width=2)


def m_spaghetti(d, box, a, rng):
    x0, y0, x1, y1 = box
    X, Y = (x0 + x1) / 2, y0 + 0.6 * (y1 - y0)
    R = 0.36 * (x1 - x0)
    d.ellipse((X - R, Y - R * 0.45, X + R, Y + R * 0.45), fill=(240, 240, 235), outline=(170, 170, 170), width=4)
    d.ellipse((X - R * 0.85, Y - R * 0.33, X + R * 0.85, Y + R * 0.33), fill=(215, 80, 30))
    for _ in range(26):
        cx, cy = X + rng.uniform(-0.6, 0.6) * R, Y + rng.uniform(-0.18, 0.18) * R
        r = rng.uniform(0.08, 0.2) * R
        d.arc((cx - r, cy - r * 0.5, cx + r, cy + r * 0.5), rng.uniform(0, 180), rng.uniform(200, 360),
              fill=(250, 190, 90), width=5)


def m_peaches(d, box, a, rng):
    x0, y0, x1, y1 = box
    w = x1 - x0
    for cx, cy, r in ((0.3, 0.62, 0.16), (0.55, 0.55, 0.18), (0.75, 0.68, 0.14)):
        X, Y, R = x0 + cx * w, y0 + cy * (y1 - y0), r * w
        d.pieslice((X - R, Y - R * 0.7, X + R, Y + R * 0.7), 180, 360, fill=(250, 170, 60), outline=(200, 110, 30), width=4)
        d.chord((X - R * 0.7, Y - R * 0.45, X + R * 0.7, Y + R * 0.1), 180, 360, fill=(255, 205, 100))
    d.ellipse((x0 + 0.62 * w, y0 + 0.2 * (y1 - y0), x0 + 0.68 * w, y0 + 0.32 * (y1 - y0)), fill=(70, 150, 50))


def m_palm(d, box, a, rng):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    bx, by = x0 + 0.5 * w, y1
    tx, ty = x0 + 0.56 * w, y0 + 0.15 * h
    for k in range(10):
        t0, t1 = k / 10, (k + 1) / 10
        d.line((bx + (tx - bx) * t0, by + (ty - by) * t0, bx + (tx - bx) * t1, by + (ty - by) * t1),
               fill=(120, 70, 30), width=int(0.06 * w * (1 - 0.5 * t0)))
    for ang in (-160, -130, -100, -70, -40, -10, 20):
        t = math.radians(ang)
        ex, ey = tx + math.cos(t) * 0.42 * w, ty + math.sin(t) * 0.25 * h + 0.25 * h
        d.line((tx, ty, (tx + ex) / 2, ty - 0.08 * h, ex, ey), fill=(30, 120, 50), width=int(0.04 * w), joint="curve")


def m_marmite(d, box, a, rng):
    x0, y0, x1, y1 = box
    w = x1 - x0
    X, Y = x0 + 0.5 * w, y0 + 0.62 * (y1 - y0)
    s = min(0.2 * w, 0.4 * (y1 - y0))
    for dx, dy in ((0.0, 0.0), (0.5, 0.18)):
        cx, cy = X + (dx - 0.25) * s * 2, Y + dy * s
        d.rectangle((cx - s, cy - 0.55 * s, cx + s, cy + s), fill=(190, 120, 50))
        d.ellipse((cx - s, cy - s, cx, cy - 0.1 * s), fill=(190, 120, 50))
        d.ellipse((cx, cy - s, cx + s, cy - 0.1 * s), fill=(190, 120, 50))
        d.rectangle((cx - 0.85 * s, cy - 0.45 * s, cx + 0.85 * s, cy + 0.85 * s), fill=(240, 205, 140))
        d.ellipse((cx - 0.85 * s, cy - 0.85 * s, cx, cy - 0.15 * s), fill=(240, 205, 140))
        d.ellipse((cx, cy - 0.85 * s, cx + 0.85 * s, cy - 0.15 * s), fill=(240, 205, 140))
        d.rounded_rectangle((cx - 0.7 * s, cy - 0.5 * s, cx + 0.7 * s, cy + 0.7 * s), radius=int(0.2 * s),
                            fill=(50, 22, 10))


MOTIFS = {"chips": m_chips, "tomatoes": m_tomatoes, "toffeepops": m_biscuits, "shrewsburys": m_biscuits,
          "chocthins": m_biscuits, "bubbles": m_bubbles, "apples": m_apples, "bolt": m_bolt, "lp": m_lp,
          "beans": m_beans, "spaghetti": m_spaghetti, "peaches": m_peaches, "palm": m_palm, "marmite": m_marmite}


def front(w: int, h: int, item: Item, rng) -> Image.Image:
    """One face of the label: brand at the top, product name, then the picture."""
    a = item.art
    im = Image.new("RGB", (w, h), a["bg"])
    d = ImageDraw.Draw(im)
    for y in range(h):
        k = 1.06 - 0.14 * y / h
        d.line((0, y, w, y), fill=shade(a["bg"], k))
    tin = item.layout.startswith("tin")
    if tin:
        # Wattie's-style: white label, coloured band across the middle, red wordmark.
        d.rectangle((0, int(0.40 * h), w, int(0.62 * h)), fill=a["bg2"])
        d.rectangle((0, int(0.40 * h), w, int(0.42 * h)), fill=shade(a["bg2"], 0.75))
        d.rectangle((0, int(0.60 * h), w, int(0.62 * h)), fill=shade(a["bg2"], 0.75))
    else:
        d.polygon([(0, 0.62 * h), (w, 0.42 * h), (w, 0.58 * h), (0, 0.78 * h)], fill=a["bg2"])
    if item.layout != "tin250":
        MOTIFS[a["motif"]](d, (0.06 * w, 0.48 * h, 0.94 * w, 0.95 * h) if not tin else (0.1 * w, 0.6 * h, 0.9 * w, 0.98 * h),
                           a, rng)
    brand_y, brand_h = (0.16, 0.2) if not tin else (0.2, 0.24)
    if item.layout == "soda":
        brand_y, brand_h = (0.2, 0.3)
    if item.layout == "tin250":
        brand_y, brand_h = (0.32, 0.5)
    if a["brand"] == "Bluebird":
        m_bird(d, 0.5 * w, 0.31 * h, 0.12 * w, (255, 255, 255))
    if a["brand"] == "Marmite" or item.layout == "tin100":
        d.rounded_rectangle((0.08 * w, 0.06 * h, 0.92 * w, 0.32 * h), radius=int(0.08 * h), fill=a["bg2"],
                            outline=(20, 20, 20), width=6)
        text(d, (0.5 * w, 0.19 * h), a["brand"], "serif", 0.78 * w, 0.2 * h, (250, 200, 20), 3, (20, 20, 20))
        text(d, (0.5 * w, 0.4 * h), a["sub"], "sans", 0.8 * w, 0.09 * h, a["fg"])
    elif item.layout == "tin250":
        MOTIFS[a["motif"]](d, (0.04 * w, 0.06 * h, 0.04 * w + 0.9 * h, 0.94 * h), a, rng)
        text(d, (0.55 * w, 0.32 * h), a["brand"], "script", 0.6 * w, 0.48 * h, a["fg"], 3, (90, 10, 15))
        text(d, (0.55 * w, 0.78 * h), a["sub"], "sans", 0.62 * w, 0.3 * h, (255, 255, 255), 2, (90, 10, 15))
    else:
        kind = "script" if a["brand"] in ("Wattie's", "Griffin's", "Foxton Fizz") else "italic"
        stroke = shade(a["bg"], 0.45) if a["fg"] == (255, 255, 255) else (255, 255, 255)
        text(d, (0.5 * w, brand_y * h), a["brand"], kind, 0.86 * w, brand_h * h, a["fg"], max(3, w // 120), stroke)
        sub_y = 0.42 if not tin else 0.51
        sub_fill = (255, 255, 255) if tin else a["fg"]
        sub_stroke = (255, 255, 255) if sum(sub_fill) < 300 else shade(a["bg2"], 0.5)
        text(d, (0.5 * w, sub_y * h), a["sub"], "sans", 0.84 * w, 0.09 * h, sub_fill, max(2, w // 200), sub_stroke)
        if a["tag"]:
            text(d, (0.5 * w, (sub_y + 0.075) * h if not tin else 0.36 * h), a["tag"], "italic", 0.6 * w, 0.05 * h,
                 a["fg"] if tin else (255, 255, 255), 1, shade(a["bg"], 0.5))
    return im


def strip(w: int, h: int, item: Item, rng) -> Image.Image:
    """A narrow back panel between fronts: barcode, a few lines of small print, the size."""
    a = item.art
    im = Image.new("RGB", (w, h), a["bg"])
    d = ImageDraw.Draw(im)
    lines = ["Made in New Zealand", "Store in a cool dry place", "Best before: see base", "Aotearoa DayZ"]
    small = min((fit(d, s, "plain", 0.86 * w, h / 40) for s in lines), key=lambda f: f.size)
    for i, s in enumerate(lines):
        d.text((w / 2, 0.18 * h + i * h * 0.05), s, font=small, fill=a["fg"] if not item.layout.startswith("tin")
               else (60, 60, 60), anchor="mm")
    bw, bh = 0.7 * w, 0.16 * h
    bx, by = (w - bw) / 2, 0.55 * h
    d.rectangle((bx - 6, by - 6, bx + bw + 6, by + bh + 20), fill=(255, 255, 255))
    x = bx
    while x < bx + bw:
        lw = rng.choice((1, 2, 2, 3, 4))
        d.rectangle((x, by, x + lw - 1, by + bh), fill=(15, 15, 15))
        x += lw + rng.choice((1, 2, 3))
    d.text((w / 2, by + bh + 8), "9 400" + "".join(str(rng.randint(0, 9)) for _ in range(8)), font=small,
           fill=(15, 15, 15), anchor="mm")
    return im


def label(w: int, h: int, item: Item, repeats: int, rng) -> Image.Image:
    im = Image.new("RGB", (w, h))
    period = w / repeats
    back = int(period * 0.28) if item.layout in ("soda", "tin") else 0
    for k in range(repeats):
        x = int(k * period)
        fw = int(period) - back
        im.paste(front(fw, h, item, rng), (x, 0))
        if back:
            im.paste(strip(back, h, item, rng), (x + fw, 0))
    return im


def crimp(im: Image.Image, frac: float, rng) -> None:
    """Heat-sealed ends of a chip bag: ridged foil across the top and bottom."""
    w, h = im.size
    d = ImageDraw.Draw(im, "RGBA")
    band = int(frac * h)
    for y0 in (0, h - band):
        d.rectangle((0, y0, w, y0 + band), fill=(255, 255, 255, 40))
        for x in range(0, w, 10):
            d.line((x, y0, x, y0 + band), fill=(0, 0, 0, 40), width=3)
            d.line((x + 5, y0, x + 5, y0 + band), fill=(255, 255, 255, 50), width=2)


def texture(item: Item) -> Image.Image:
    rng = random.Random(item.key)
    (fx0, fy0, fx1, fy1), (w, h), repeats = LAYOUTS[item.layout]
    box = (int(fx0 * w), int(fy0 * h), int(fx1 * w), int(fy1 * h))
    lw, lh = box[2] - box[0], box[3] - box[1]
    if item.layout == "bag":
        im = front(w, h, item, rng)
        crimp(im, 0.1, rng)
        return wear(im, rng, 8)
    im = metal((w, h), rng)
    im.paste(wear(label(lw, lh, item, repeats, rng), rng), box[:2])
    if item.layout == "tin100":
        # The lid disc sits over the right half of the texture.
        d = ImageDraw.Draw(im)
        cx, cy, r = 0.75 * w, 0.5 * h, 0.5 * h - 2
        lid = metal((w, h), rng)
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
        im.paste(lid, (0, 0), mask)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(120, 120, 120), width=6)
        d.ellipse((cx - r * 0.85, cy - r * 0.85, cx + r * 0.85, cy + r * 0.85), outline=(140, 140, 140), width=4)
        text(d, (cx, cy), item.art["brand"], "serif", 1.3 * r, 0.4 * r, (210, 30, 40), 2, (60, 10, 10))
    return im


def write_textures() -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    paths = []
    for item in ITEMS:
        p = OUT / f"{item.key}.png"
        texture(item).save(p)
        paths.append(p)
    return paths


def write_config() -> Path:
    bases = sorted({i.base for i in ITEMS} | {i.opened for i in ITEMS if i.opened})
    out = ["// New Zealand food and drink, generated by tools/nz_food.py. Included inside CfgVehicles in config.cpp.",
           "// Each class inherits a vanilla item and only swaps its label texture."]
    out += [f"class {b};" for b in bases]

    def block(cls, base, item, display=True):
        lines = [f"class {cls}: {base}", "{", "\tscope = 2;"]
        if display:
            lines += [f'\tdisplayName = "{item.name}";', f'\tdescriptionShort = "{item.desc}";']
        lines += [f'\thiddenSelectionsTextures[] = {{"{TEXTURE.format(item.key)}"}};', "};"]
        return lines

    for item in ITEMS:
        out += block(item.cls, item.base, item)
        if item.opened:
            out += block(item.cls + "_Opened", item.opened, item)
    p = MAP_DIR / "config" / "food.hpp"
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    return p


def write_script() -> Path:
    out = ["// New Zealand food and drink, generated by tools/nz_food.py. Tins open into their own opened",
           "// class, so the label stays the same once opened. The other items (and the opened tins) need no",
           "// script: the engine uses the script class of their nearest vanilla parent.", ""]
    for item in ITEMS:
        if item.opened:
            out += [f"class {item.cls} : {item.base}", "{", "\toverride void Open()", "\t{",
                    f'\t\tReplaceEdibleWithNew("{item.cls}_Opened");', "\t}", "}", ""]
    p = MAP_DIR / "scripts" / "4_World" / "AotearoaFood.c"
    p.write_text("\n".join(out), encoding="utf-8")
    return p


def write_preview(paths: list[Path]) -> Path:
    cell = 300
    cols = 6
    rows = math.ceil(len(paths) / cols)
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 30)), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    f = font("sans", 16)
    for i, (p, item) in enumerate(zip(paths, ITEMS)):
        im = Image.open(p).convert("RGB")
        im.thumbnail((cell - 10, cell - 10))
        x, y = (i % cols) * cell, (i // cols) * (cell + 30)
        sheet.paste(im, (x + (cell - im.width) // 2, y + 5 + (cell - 10 - im.height) // 2))
        d.text((x + cell / 2, y + cell + 12), item.name, font=f, fill=(235, 235, 235), anchor="mm")
    p = MAP_DIR / "preview" / "nz_food.png"
    sheet.save(p, optimize=True)
    return p


def main() -> None:
    paths = write_textures()
    write_config()
    write_script()
    write_preview(paths)
    print(f"{len(ITEMS)} New Zealand food and drink items, {len(paths)} textures in {OUT.relative_to(MAP_DIR)}")


if __name__ == "__main__":
    main()
