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
TEXTURE = "maps\\aotearoa\\data\\food\\{}.paa"
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
    "tuna": ((0.0, 0.0, 1.0, 1.0), (1024, 1024), 1),
    "sardines": ((0.0, 0.0, 1.0, 1.0), (1024, 1024), 3),
    "cereal": ((0.0, 0.0, 1.0, 1.0), (1024, 1024), 1),
    "bar": ((0.0, 0.0, 1.0, 1.0), (1024, 1024), 1),
    "rice": ((0.0, 0.0, 1.0, 1.0), (1024, 1024), 1),
    "milk": ((0.0, 0.0, 1.0, 1.0), (1024, 1024), 1),
    "honey": ((0.0, 0.0, 1.0, 1.0), (1024, 1024), 1),
    "bottle": ((0.0, 0.06, 1.0, 0.3), (512, 512), 3),
}
# Vanilla configs that don't declare the model's retexturable selection: on these models the whole
# mesh is the "zbytek" selection.
SELECTIONS = {"rice": "zbytek", "milk": "zbytek", "honey": "zbytek", "bottle": "zbytek"}
# Vanilla chocolate bar textures carry alpha (_ca); the rest are plain colour maps (_co). The bar's UV
# layout isn't published, so its wrapper is a repeating pattern that reads from any part of the texture.
SUFFIX = {"bar": "_ca"}


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

    @property
    def paa(self) -> str:
        return self.key + SUFFIX.get(self.layout, "_co")


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
    Item("pineapplelumps", "Aotearoa_Lollies_PineappleLumps", "Crackers", "bag", "Pascall Pineapple Lumps",
         "Pascall Pineapple Lumps: chewy pineapple lollies coated in chocolate.", (8, 6),
         dict(brand="Pascall", sub="PINEAPPLE LUMPS", tag="a Kiwi classic", bg=(250, 205, 30), bg2=(110, 60, 25),
              fg=(110, 60, 25), motif="lumps")),
    # Whittaker's chocolate, on the vanilla Zagorky bars.
    Item("whittakers_milk", "Aotearoa_Whittakers_CreamyMilk", "Zagorky", "bar", "Whittaker's Creamy Milk",
         "Whittaker's Creamy Milk chocolate, made in Porirua.", (15, 12),
         dict(brand="Whittaker's", sub="CREAMY MILK", tag="33% cocoa", bg=(40, 60, 150), bg2=(215, 175, 80),
              fg=(255, 255, 255))),
    Item("whittakers_dark", "Aotearoa_Whittakers_DarkGhana", "ZagorkyChocolate", "bar", "Whittaker's Dark Ghana",
         "Whittaker's Dark Ghana 72% cocoa chocolate, made in Porirua.", (15, 12),
         dict(brand="Whittaker's", sub="DARK GHANA", tag="72% cocoa", bg=(60, 25, 20), bg2=(215, 175, 80),
              fg=(255, 255, 255))),
    Item("whittakers_peanut", "Aotearoa_Whittakers_PeanutSlab", "ZagorkyPeanuts", "bar", "Whittaker's Peanut Slab",
         "Whittaker's Peanut Slab: milk chocolate packed with peanuts.", (15, 12),
         dict(brand="Whittaker's", sub="PEANUT SLAB", tag="since 1951", bg=(250, 200, 30), bg2=(190, 30, 35),
              fg=(120, 20, 25))),
    Item("risotto", "Aotearoa_RiceRisotto", "Rice", "rice", "Rice Risotto",
         "Arborio rice for a creamy risotto. Cook it in a pot with water.", (25, 18),
         dict(brand="Rice Risotto", sub="ARBORIO RICE", tag="creamy & quick", bg=(248, 244, 232),
              bg2=(40, 120, 60), fg=(150, 30, 35)),
         usages=["Village", "Town", "Hunting"]),
    Item("anchor_milk", "Aotearoa_Anchor_MilkPowder", "PowderedMilk", "milk", "Anchor Milk Powder",
         "Anchor whole milk powder, from New Zealand dairy farms. Mix it with water.", (30, 22),
         dict(brand="Anchor", sub="WHOLE MILK POWDER", tag="NZ dairy", bg=(0, 85, 165), bg2=(250, 250, 250),
              fg=(255, 255, 255)),
         usages=["Farm", "Town", "Village"]),
    Item("airborne_honey", "Aotearoa_Airborne_Honey", "Honey", "honey", "Airborne Mānuka Honey",
         "Airborne mānuka honey from the Canterbury plains.", (30, 22),
         dict(brand="Airborne", sub="MĀNUKA HONEY", tag="Canterbury", bg=(225, 150, 30), bg2=(40, 40, 40),
              fg=(30, 30, 30)),
         usages=["Farm", "Village", "Town"]),
    Item("weetbix", "Aotearoa_WeetBix", "BoxCerealCrunchin", "cereal", "Sanitarium Weet-Bix",
         "Sanitarium Weet-Bix whole grain wheat biscuits. Three with milk will keep you going.", (23, 18),
         dict(brand="Weet-Bix", sub="WHOLE GRAIN WHEAT BISCUITS", tag="Sanitarium", bg=(250, 200, 35),
              bg2=(25, 70, 160), fg=(205, 30, 35))),
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
    Item("hellers_bacon", "Aotearoa_Hellers_Bacon", "TacticalBaconCan", "tin", "Hellers Bacon",
         "Hellers streaky bacon in a tin. Made in Canterbury.", (10, 6),
         dict(brand="Hellers", sub="STREAKY BACON", tag="Canterbury", bg=(250, 245, 230), bg2=(20, 90, 50),
              fg=(180, 25, 35), motif="bacon"),
         opened="TacticalBaconCan_Opened"),
    Item("tux_dogfood", "Aotearoa_Tux_DogFood", "DogFoodCan", "tin250", "Tux Dog Food",
         "Tux dog food. Meant for working dogs, but it'll keep you going.", (15, 10),
         dict(brand="Tux", sub="DOG FOOD", tag="", bg=(20, 60, 140), bg2=(250, 200, 30),
              fg=(255, 210, 40), motif="dog"),
         opened="DogFoodCan_Opened"),
    Item("jellimeat", "Aotearoa_Jellimeat", "CatFoodCan", "tin250", "Jellimeat",
         "Jellimeat cat food. Desperate times.", (15, 10),
         dict(brand="Jellimeat", sub="CAT FOOD", tag="", bg=(120, 40, 140), bg2=(250, 250, 250),
              fg=(255, 255, 255), motif="cat"),
         opened="CatFoodCan_Opened"),
    Item("sealord_tuna", "Aotearoa_Sealord_Tuna", "TunaCan", "tuna", "Sealord Tuna",
         "Sealord tuna chunks in spring water. 185 g.", (30, 20),
         dict(brand="Sealord", sub="TUNA", tag="in spring water", bg=(20, 45, 100), bg2=(250, 200, 40),
              fg=(255, 255, 255)),
         opened="TunaCan_Opened", usages=["Coast", "Town", "Office"]),
    Item("pump_water", "Aotearoa_Pump_Water", "WaterBottle", "bottle", "Pump Water Bottle",
         "A Pump water bottle. Refill it at a tap, a well or a stream (boil stream water first).", (100, 80),
         dict(brand="pump", sub="PURE NZ WATER", tag="refill me", bg=(0, 150, 215), bg2=(255, 255, 255),
              fg=(255, 255, 255))),
    Item("pams_sardines", "Aotearoa_Pams_Sardines", "SardinesCan", "sardines", "Pams Sardines",
         "Pams sardines in soybean oil. 106 g.", (30, 20),
         dict(brand="Pams", sub="SARDINES", tag="in soybean oil", bg=(250, 250, 245), bg2=(30, 90, 170),
              fg=(210, 30, 40), motif="fish"),
         opened="SardinesCan_Opened", usages=["Coast", "Town", "Village"]),
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


def m_lumps(d, box, a, rng):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    for _ in range(14):
        X, Y = rng.uniform(x0 + 0.12 * w, x1 - 0.12 * w), rng.uniform(y0 + 0.25 * h, y1 - 0.08 * h)
        R = rng.uniform(0.07, 0.1) * w
        d.rounded_rectangle((X - R, Y - R * 0.7, X + R, Y + R * 0.7), radius=int(R * 0.6), fill=(90, 50, 25),
                            outline=(50, 25, 10), width=3)
        if rng.random() < 0.5:
            d.ellipse((X - R * 0.5, Y - R * 0.35, X + R * 0.5, Y + R * 0.35), fill=(250, 215, 60))
        d.arc((X - R * 0.7, Y - R * 0.5, X + R * 0.2, Y), 190, 280, fill=(160, 110, 70), width=4)


def fish(d, X, Y, L, body, belly):
    d.ellipse((X - L / 2, Y - L * 0.14, X + L * 0.35, Y + L * 0.14), fill=body)
    d.chord((X - L / 2, Y - L * 0.02, X + L * 0.35, Y + L * 0.14), 0, 180, fill=belly)
    d.polygon([(X + L * 0.3, Y), (X + L / 2, Y - L * 0.14), (X + L / 2, Y + L * 0.14)], fill=body)
    d.ellipse((X - L * 0.4, Y - L * 0.05, X - L * 0.34, Y + L * 0.01), fill=(15, 15, 25))


def m_fish(d, box, a, rng):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    for k, (cx, cy) in enumerate(((0.3, 0.45), (0.65, 0.6), (0.4, 0.8))):
        fish(d, x0 + cx * w, y0 + cy * h, 0.45 * w, (90, 110, 140), (200, 210, 225))


def paw(d, X, Y, s, fill):
    d.ellipse((X - s, Y - 0.7 * s, X + s, Y + 0.9 * s), fill=fill)
    for dx, dy in ((-1.05, -1.0), (-0.38, -1.45), (0.38, -1.45), (1.05, -1.0)):
        d.ellipse((X + dx * s - 0.35 * s, Y + dy * s - 0.45 * s, X + dx * s + 0.35 * s, Y + dy * s + 0.45 * s), fill=fill)


def m_paws(d, box, a, rng):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    paw(d, x0 + 0.5 * w, y0 + 0.62 * h, 0.24 * min(w, h), a["bg2"])


def m_bacon(d, box, a, rng):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    for k in range(3):
        y = y0 + (0.35 + 0.2 * k) * h
        pts = [(x0 + (0.12 + 0.76 * t / 8) * w, y + math.sin(t * 1.3 + k) * 0.05 * h) for t in range(9)]
        d.line(pts, fill=(185, 60, 60), width=int(0.13 * h), joint="curve")
        d.line([(x, yy - 0.025 * h) for x, yy in pts], fill=(245, 215, 200), width=int(0.03 * h), joint="curve")


MOTIFS = {"bacon": m_bacon, "dog": m_paws, "cat": m_paws, "lumps": m_lumps, "fish": m_fish, "chips": m_chips, "tomatoes": m_tomatoes, "toffeepops": m_biscuits, "shrewsburys": m_biscuits,
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
    tin = item.layout.startswith("tin") or item.layout == "sardines"
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
        kind = "script" if a["brand"] in ("Wattie's", "Griffin's", "Foxton Fizz", "Pascall", "Pams") else "italic"
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


def tinted_metal(size, rng, tint) -> Image.Image:
    g = metal(size, rng).convert("L")
    return Image.merge("RGB", [g.point(lambda v, k=k: min(255, int(v * k))) for k in tint])


def tuna(item: Item, rng) -> Image.Image:
    """Flat rectangular tin: base panel top left, the printed ring-pull lid top right (its long side runs
    down the texture), the inside under the base, and the side band along the bottom."""
    a = item.art
    w = h = 1024
    im = tinted_metal((w, h), rng, (1.05, 0.88, 0.55))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0.02 * w, 0.02 * h, 0.55 * w, 0.4 * h), radius=60, outline=(120, 95, 45), width=10)
    d.rounded_rectangle((0.05 * w, 0.05 * h, 0.52 * w, 0.37 * h), radius=50, outline=(205, 175, 105), width=6)
    inside = metal((int(0.53 * w), int(0.36 * h)), rng)
    im.paste(inside, (0, int(0.4 * h)))
    lx0, ly0, lx1, ly1 = int(0.57 * w), int(0.04 * h), int(0.98 * w), int(0.64 * h)
    lab = Image.new("RGB", (ly1 - ly0, lx1 - lx0), a["bg"])
    ld = ImageDraw.Draw(lab)
    lw_, lh_ = lab.size
    ld.rectangle((0, int(0.72 * lh_), lw_, int(0.8 * lh_)), fill=a["bg2"])
    fish(ld, 0.62 * lw_, 0.5 * lh_, 0.5 * lw_, (150, 175, 205), (225, 232, 240))
    text(ld, (0.6 * lw_, 0.2 * lh_), a["brand"], "script", 0.62 * lw_, 0.3 * lh_, a["fg"], 4, shade(a["bg"], 0.5))
    text(ld, (0.6 * lw_, 0.88 * lh_), f"{a['sub']}  {a['tag'].upper()}", "sans", 0.62 * lw_, 0.12 * lh_, a["fg"])
    lab = wear(lab, rng).rotate(-90, expand=True)
    mask = Image.new("L", lab.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, lab.width - 1, lab.height - 1), radius=50, fill=255)
    im.paste(lab, (lx0, ly0), mask)
    d.rounded_rectangle((lx0, ly0, lx1, ly1), radius=50, outline=(150, 120, 60), width=10)
    rx, ry, rr = 0.775 * w, 0.13 * h, 0.06 * w
    d.ellipse((rx - rr, ry - rr, rx + rr, ry + rr), outline=(205, 205, 210), width=14)
    d.ellipse((rx - rr * 0.35, ry + rr * 0.9, rx + rr * 0.35, ry + rr * 1.6), fill=(195, 195, 200))
    sx0, sy0, sx1, sy1 = int(0.02 * w), int(0.8 * h), int(0.74 * w), int(0.98 * h)
    band = Image.new("RGB", (sx1 - sx0, sy1 - sy0), a["bg"])
    bd = ImageDraw.Draw(band)
    for k in range(3):
        cx = (k + 0.5) * band.width / 3
        text(bd, (cx, band.height * 0.5), f"{a['brand']} {a['sub'].title()}", "script", band.width / 3.4,
             band.height * 0.6, a["fg"], 2, shade(a["bg"], 0.5))
    im.paste(wear(band, rng), (sx0, sy0))
    return im


def sardines(item: Item, rng) -> Image.Image:
    """Oval tin: the inside and the ringed lid across the top, two label bands round the side below."""
    w = h = 1024
    im = metal((w, h), rng)
    d = ImageDraw.Draw(im)
    d.ellipse((0.0, 0.07 * h, 0.4 * w, 0.47 * h), fill=(150, 150, 155), outline=(110, 110, 115), width=8)
    cx, cy, r = 0.62 * w, 0.27 * h, 0.19 * w
    for k in range(6):
        rr = r * (1 - k * 0.14)
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(130 + 12 * (k % 2), 130, 135), width=8)
    for y0, y1 in ((0.51, 0.72), (0.77, 0.98)):
        box = (0, int(y0 * h), w, int(y1 * h))
        im.paste(wear(label(w, box[3] - box[1], item, 3, rng), rng), box[:2])
    return im


def cereal(item: Item, rng) -> Image.Image:
    """Cereal box: the front on the right, the back on the left, sides and flaps along the top."""
    a = item.art
    w = h = 1024
    im = Image.new("RGB", (w, h), a["bg"])
    d = ImageDraw.Draw(im)
    for y in range(h):
        d.line((0, y, w, y), fill=shade(a["bg"], 1.05 - 0.1 * y / h))
    for row in range(4):
        for col in range(5):
            text(d, ((col + 0.5) * w / 5, (row + 0.5) * 0.3 * h / 4), a["brand"], "italic", w / 6, 0.05 * h,
                 a["fg"], 2, (255, 255, 255))
    fx0, fy0, fx1, fy1 = int(0.51 * w), int(0.31 * h), w, h
    fw, fh = fx1 - fx0, fy1 - fy0
    f = Image.new("RGB", (fw, fh), a["bg"])
    fd = ImageDraw.Draw(f)
    fd.polygon([(0, 0.3 * fh), (fw, 0.18 * fh), (fw, 0.34 * fh), (0, 0.46 * fh)], fill=a["bg2"])
    text(fd, (0.5 * fw, 0.13 * fh), a["brand"], "italic", 0.9 * fw, 0.2 * fh, a["fg"], 6, (255, 255, 255))
    text(fd, (0.5 * fw, 0.32 * fh), a["sub"], "sans", 0.86 * fw, 0.06 * fh, (255, 255, 255))
    text(fd, (0.85 * fw, 0.04 * fh), a["tag"], "italic", 0.28 * fw, 0.04 * fh, (40, 90, 40))
    bx, by, br = 0.5 * fw, 0.72 * fh, 0.38 * fw
    fd.ellipse((bx - br, by - br * 0.5, bx + br, by + br * 0.75), fill=(245, 245, 250), outline=(170, 170, 180), width=6)
    fd.ellipse((bx - br * 0.9, by - br * 0.42, bx + br * 0.9, by + br * 0.3), fill=(250, 250, 240))
    for k in range(3):
        x = bx - br * 0.55 + k * br * 0.5
        fd.rounded_rectangle((x - br * 0.22, by - br * 0.32 - k * 6, x + br * 0.22, by + br * 0.05 - k * 6),
                             radius=16, fill=(205, 150, 80), outline=(150, 100, 45), width=4)
        for j in range(5):
            fd.line((x - br * 0.18, by - br * 0.26 + j * br * 0.06 - k * 6, x + br * 0.18,
                     by - br * 0.26 + j * br * 0.06 - k * 6), fill=(175, 120, 60), width=3)
    im.paste(wear(f, rng), (fx0, fy0))
    bx0, by0, bx1, by1 = int(0.03 * w), int(0.37 * h), int(0.47 * w), h
    back = Image.new("RGB", (bx1 - bx0, by1 - by0), shade(a["bg"], 0.97))
    bd = ImageDraw.Draw(back)
    bwid, bhei = back.size
    text(bd, (0.5 * bwid, 0.08 * bhei), a["brand"], "italic", 0.8 * bwid, 0.1 * bhei, a["fg"], 3, (255, 255, 255))
    bd.rectangle((0.1 * bwid, 0.2 * bhei, 0.9 * bwid, 0.62 * bhei), fill=(255, 255, 255), outline=(30, 30, 30), width=3)
    small = font("plain", int(0.03 * bhei))
    rows = ["Nutrition Information", "Servings per pack: 20", "Energy  549 kJ", "Protein  4.2 g", "Fat  0.5 g",
            "Carbohydrate  22 g", "Dietary fibre  3.7 g", "Sodium  97 mg"]
    for i, r in enumerate(rows):
        bd.text((0.14 * bwid, 0.23 * bhei + i * 0.048 * bhei), r, font=small, fill=(20, 20, 20))
    bd.text((0.5 * bwid, 0.7 * bhei), "Made in Auckland, New Zealand", font=small, fill=(20, 20, 20), anchor="mm")
    im.paste(wear(back, rng), (bx0, by0))
    return im


def bar(item: Item, rng) -> Image.Image:
    """Chocolate bar wrapper: rows of the wordmark and the flavour between foil bands, repeated so the
    front reads whichever part of the texture the model maps."""
    a = item.art
    w = h = 1024
    im = Image.new("RGB", (w, h), a["bg"])
    d = ImageDraw.Draw(im)
    rows = 8
    rh = h / rows
    for r in range(rows):
        y = r * rh
        if r % 2 == 0:
            for c in range(2):
                text(d, ((c + 0.5) * w / 2, y + rh * 0.5), a["brand"], "script",
                     w / 2.3, rh * 0.75, a["fg"], 3, shade(a["bg"], 0.5))
        else:
            d.rectangle((0, y + rh * 0.08, w, y + rh * 0.92), fill=a["bg2"])
            for c in range(3):
                text(d, ((c + 0.5) * w / 3, y + rh * 0.5), f"{a['sub']} · {a['tag']}", "sans", w / 3.3, rh * 0.4,
                     shade(a["bg"], 0.6) if sum(a["bg"]) < 400 else (255, 255, 255))
    im = wear(im, rng, 6)
    return im.convert("RGBA")


def rice(item: Item, rng) -> Image.Image:
    """Rice bag: the folded ends across the top third, the label band in the middle (front centred
    at 40% across), and the grains showing along the bottom."""
    a = item.art
    w = h = 1024
    im = Image.new("RGB", (w, h), a["bg"])
    d = ImageDraw.Draw(im)
    for k in range(3):
        x0 = k * w / 3
        d.rectangle((x0, 0, x0 + w / 3, 0.33 * h), fill=shade(a["bg"], 0.96 - 0.03 * k))
        d.line((x0 + 0.06 * w, 0.06 * h, x0 + 0.12 * w, 0.26 * h, x0 + 0.21 * w, 0.26 * h, x0 + 0.27 * w, 0.06 * h),
               fill=shade(a["bg"], 0.82), width=6)
    d.rectangle((0, 0.33 * h, w, 0.55 * h), fill=a["bg2"])
    d.rectangle((0, 0.53 * h, w, 0.56 * h), fill=(215, 175, 80))
    for k in range(4):
        y = 0.36 * h + k * 0.045 * h
        d.line((0, y, w, y), fill=shade(a["bg2"], 1.15), width=2)
    for c in range(3):
        cx = (c + 0.5) * w / 3
        text(d, (cx, 0.44 * h), "Packed in New Zealand", "italic", w / 3.6, 0.04 * h, (250, 245, 230))
    cx = 0.4 * w
    text(d, (cx, 0.62 * h), a["brand"], "script", 0.5 * w, 0.09 * h, a["fg"], 3, (255, 255, 255))
    text(d, (cx, 0.69 * h), a["sub"], "sans", 0.4 * w, 0.035 * h, a["bg2"])
    text(d, (cx, 0.73 * h), a["tag"], "italic", 0.3 * w, 0.025 * h, (90, 80, 60))
    for side in (0.8,):
        X, Y, R = side * w, 0.66 * h, 0.08 * w
        d.ellipse((X - R, Y - R * 0.5, X + R, Y + R * 0.5), fill=(250, 250, 250), outline=(170, 170, 170), width=3)
        d.ellipse((X - R * 0.8, Y - R * 0.38, X + R * 0.8, Y + R * 0.3), fill=(240, 228, 190))
        for _ in range(12):
            gx, gy = X + rng.uniform(-0.6, 0.6) * R, Y + rng.uniform(-0.2, 0.15) * R
            d.ellipse((gx - 4, gy - 2, gx + 4, gy + 2), fill=(250, 245, 225))
        d.ellipse((X - R * 0.25, Y - R * 0.15, X + R * 0.05, Y + R * 0.05), fill=(150, 110, 70))
    d.rectangle((0, 0.75 * h, w, h), fill=(236, 230, 212))
    for _ in range(2600):
        gx, gy = rng.uniform(0, w), rng.uniform(0.75 * h, h)
        L = rng.uniform(7, 11)
        t = rng.uniform(0, math.pi)
        dx, dy = math.cos(t) * L / 2, math.sin(t) * L / 2
        c = rng.randint(225, 252)
        d.line((gx - dx, gy - dy, gx + dx, gy + dy), fill=(c, c - 4, c - 18), width=5)
    return wear(im, rng, 6)


def milk(item: Item, rng) -> Image.Image:
    """Powdered milk bag: plain body on the left, the label running down the texture (rotated a quarter
    turn) in the middle, and a coloured side band on the right."""
    a = item.art
    w = h = 1024
    im = Image.new("RGB", (w, h), a["bg"])
    d = ImageDraw.Draw(im)
    for x in range(int(0.56 * w)):
        d.line((x, 0, x, h), fill=shade(a["bg"], 1.0 + 0.08 * math.sin(x / 40)))
    lab_w, lab_h = h, int(0.26 * w)
    lab = Image.new("RGB", (lab_w, lab_h), a["bg2"])
    ld = ImageDraw.Draw(lab)
    text(ld, (0.5 * lab_w, 0.38 * lab_h), a["brand"], "serif", 0.5 * lab_w, 0.5 * lab_h, a["bg"], 4, (255, 255, 255))
    text(ld, (0.5 * lab_w, 0.78 * lab_h), a["sub"], "sans", 0.55 * lab_w, 0.18 * lab_h, shade(a["bg"], 0.8))
    for side in (0.12, 0.88):
        X, Y, R = side * lab_w, 0.5 * lab_h, 0.32 * lab_h
        d2 = ld
        d2.ellipse((X - R, Y - R, X + R, Y + R), fill=a["bg"])
        d2.polygon([(X - 0.6 * R, Y + 0.5 * R), (X - 0.2 * R, Y - 0.6 * R), (X + 0.2 * R, Y + 0.1 * R),
                    (X + 0.6 * R, Y - 0.6 * R), (X + 0.8 * R, Y + 0.5 * R)], fill=(90, 170, 70))
    im.paste(lab.rotate(-90, expand=True), (int(0.56 * w), 0))
    d.rectangle((int(0.82 * w), 0, w, h), fill=shade(a["bg"], 0.8))
    band = Image.new("RGB", (h, w - int(0.82 * w)), shade(a["bg"], 0.8))
    text(ImageDraw.Draw(band), (0.5 * h, 0.5 * band.height), f"{a['sub']}  ·  {a['tag'].upper()}  ·  1 kg", "sans",
         0.8 * h, 0.4 * band.height, (255, 255, 255))
    im.paste(band.rotate(-90, expand=True), (int(0.82 * w), 0))
    for k in range(4):
        text(d, (0.28 * w, (k + 0.5) * h / 4), a["brand"], "serif", 0.4 * w, 0.1 * h, shade(a["bg"], 1.18))
    return wear(im, rng, 6)


def honey(item: Item, rng) -> Image.Image:
    """Honey jar: the jar's UV layout isn't published, so like the chocolate bars it repeats the label
    across the whole texture over a honey-coloured ground, and reads from any part the model maps."""
    a = item.art
    w = h = 1024
    im = Image.new("RGB", (w, h), a["bg"])
    d = ImageDraw.Draw(im)
    for y in range(h):
        d.line((0, y, w, y), fill=shade(a["bg"], 0.9 + 0.2 * (0.5 + 0.5 * math.sin(y / 60))))
    rows = 4
    rh = h / rows
    for r in range(rows):
        y = r * rh
        d.rectangle((0, y + 0.18 * rh, w, y + 0.82 * rh), fill=(250, 245, 230))
        d.rectangle((0, y + 0.18 * rh, w, y + 0.24 * rh), fill=a["bg2"])
        d.rectangle((0, y + 0.76 * rh, w, y + 0.82 * rh), fill=a["bg2"])
        for c in range(2):
            cx = (c + 0.5) * w / 2
            text(d, (cx, y + 0.42 * rh), a["brand"], "serif", w / 2.6, 0.24 * rh, a["fg"])
            text(d, (cx, y + 0.62 * rh), a["sub"], "sans", w / 3, 0.1 * rh, (190, 120, 20))
            bx = cx - w / 5
            for k in range(6):
                t = math.radians(60 * k)
                hx, hy, hr = bx + math.cos(t) * 0.07 * rh, y + 0.5 * rh + math.sin(t) * 0.07 * rh, 0.05 * rh
                d.regular_polygon((hx, hy, hr), 6, fill=(235, 170, 40), outline=(160, 100, 20))
    return wear(im, rng, 6)


def bottle(item: Item, rng) -> Image.Image:
    """Water bottle: the wrap-around label across the top, the ribbed plastic below it on the left, the
    cap and its ring under that, and the bottle's base on the right."""
    a = item.art
    w = h = 512
    im = Image.new("RGB", (w, h), (225, 235, 242))
    d = ImageDraw.Draw(im)
    for k in range(10):
        y = 0.32 * h + k * 0.045 * h
        d.line((0, y, 0.48 * w, y), fill=(200, 212, 222), width=3)
    d.rectangle((0, 0.3 * h, w, 0.32 * h), fill=(190, 200, 210))
    d.ellipse((0.18 * w, 0.75 * h, 0.36 * w, 0.88 * h), fill=a["bg"], outline=shade(a["bg"], 0.6), width=3)
    d.rectangle((0.02 * w, 0.88 * h, 0.45 * w, 0.97 * h), fill=a["bg"])
    for x in range(int(0.03 * w), int(0.45 * w), 6):
        d.line((x, 0.885 * h, x, 0.965 * h), fill=shade(a["bg"], 0.75), width=2)
    cx, cy, r = 0.74 * w, 0.62 * h, 0.27 * w
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(205, 215, 225), outline=(160, 170, 180), width=4)
    d.ellipse((cx - 0.45 * r, cy - 0.45 * r, cx + 0.45 * r, cy + 0.45 * r), fill=(240, 245, 250))
    box = (0, int(0.06 * h), w, int(0.3 * h))
    lab_w, lab_h = box[2] - box[0], box[3] - box[1]
    lab = Image.new("RGB", (lab_w, lab_h), a["bg"])
    ld = ImageDraw.Draw(lab)
    for y in range(lab_h):
        ld.line((0, y, lab_w, y), fill=shade(a["bg"], 1.08 - 0.2 * y / lab_h))
    period = lab_w / 3
    for k in range(3):
        x = k * period
        ld.rectangle((x, 0.66 * lab_h, x + period, 0.9 * lab_h), fill=a["bg2"])
        text(ld, (x + 0.5 * period, 0.34 * lab_h), a["brand"], "sans", 0.7 * period, 0.46 * lab_h, a["fg"], 2,
             shade(a["bg"], 0.5))
        text(ld, (x + 0.5 * period, 0.78 * lab_h), a["sub"], "sans", 0.8 * period, 0.16 * lab_h, shade(a["bg"], 0.8))
    im.paste(wear(lab, rng, 6), box[:2])
    return im


CUSTOM = {"milk": milk, "honey": honey, "bottle": bottle, "rice": rice, "tuna": tuna, "sardines": sardines, "cereal": cereal, "bar": bar}


def texture(item: Item) -> Image.Image:
    rng = random.Random(item.key)
    if item.layout in CUSTOM:
        return CUSTOM[item.layout](item, rng)
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
        if item.layout in SELECTIONS:
            lines += [f'\thiddenSelections[] = {{"{SELECTIONS[item.layout]}"}};']
        if display:
            lines += [f'\tdisplayName = "{item.name}";', f'\tdescriptionShort = "{item.desc}";']
        lines += [f'\thiddenSelectionsTextures[] = {{"{TEXTURE.format(item.paa)}"}};', "};"]
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


# The front of each pack on its texture, for the shelf picture: (x0, y0, x1, y1) and a rotation.
FRONTS = {
    "soda": ((0.0, 0.466, 0.306, 0.946), 0), "tin": ((0.0, 0.571, 0.36, 0.973), 0),
    "tin250": ((0.0, 0.758, 0.333, 0.961), 0), "tin100": ((0.0, 0.0, 0.5, 1.0), 0), "bag": ((0.0, 0.0, 1.0, 1.0), 0),
    "tuna": ((0.57, 0.04, 0.98, 0.64), 90), "sardines": ((0.0, 0.51, 0.333, 0.72), 0),
    "cereal": ((0.51, 0.31, 1.0, 1.0), 0), "bar": ((0.0, 0.0, 1.0, 0.25), 0),
    "rice": ((0.15, 0.33, 0.65, 0.78), 0), "milk": ((0.56, 0.0, 0.82, 1.0), 90),
    "honey": ((0.0, 0.0, 0.5, 0.25), 0), "bottle": ((0.0, 0.06, 0.333, 0.3), 0),
}
SHELVES = [("soda", "bar", "bottle", "honey"), ("bag", "milk"), ("tin", "tin250", "tin100", "tuna", "sardines", "cereal", "rice")]


def write_showcase(paths: list[Path]) -> Path:
    """The pack fronts on three shop shelves (preview/nz_food_showcase.png, used for a Workshop card)."""
    W, H = 1800, 1140
    im = Image.new("RGB", (W, H), (34, 30, 28))
    d = ImageDraw.Draw(im)
    row_h = H // len(SHELVES)
    for r, layouts in enumerate(SHELVES):
        packs = []
        for p, item in zip(paths, ITEMS):
            if item.layout in layouts:
                (x0, y0, x1, y1), rot = FRONTS[item.layout]
                tex = Image.open(p).convert("RGB")
                tw, th = tex.size
                packs.append(tex.crop((int(x0 * tw), int(y0 * th), int(x1 * tw), int(y1 * th))).rotate(rot, expand=True))
        max_h = row_h - 70
        scaled = [pk.resize((max(1, int(pk.width * min(max_h / pk.height, 1.6 * max_h / pk.width))),
                             int(pk.height * min(max_h / pk.height, 1.6 * max_h / pk.width)))) for pk in packs]
        total = sum(s.width for s in scaled)
        k = min(1.0, (W - 60 - 14 * len(scaled)) / total)
        scaled = [s.resize((int(s.width * k), int(s.height * k))) for s in scaled]
        gap = (W - sum(s.width for s in scaled)) / (len(scaled) + 1)
        base = (r + 1) * row_h - 40
        x = gap
        for s in scaled:
            im.paste(s, (int(x), base - s.height))
            d.rectangle((int(x), base - s.height, int(x) + s.width - 1, base - 1), outline=(0, 0, 0), width=2)
            x += s.width + gap
        d.rectangle((0, base, W, base + 26), fill=(120, 80, 45))
        d.rectangle((0, base + 26, W, base + 36), fill=(70, 45, 25))
    p = MAP_DIR / "preview" / "nz_food_showcase.png"
    im.save(p, optimize=True)
    return p


def main() -> None:
    paths = write_textures()
    write_config()
    write_script()
    write_preview(paths)
    write_showcase(paths)
    print(f"{len(ITEMS)} New Zealand food and drink items, {len(paths)} textures in {OUT.relative_to(MAP_DIR)}")


if __name__ == "__main__":
    main()
