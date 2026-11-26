"""New Zealand clothing: retextured vanilla clothes.

    python nz_gear.py

  Swanndri Bush Shirt     red and black check wool shirt      on Shirt_RedCheck
  Swanndri Ranger Jacket  blue and black check wool jacket    on WoolCoat_BlueCheck
  Stubbies                navy cotton drill shorts            on ShortJeans_Darkblue
  Jandals                 rubber jandals                      on SandalsShoes_Black
  All Blacks Tee          black with a silver fern print      on TShirt_Black
  Canterbury Jersey       red and black rugby hoops           on TShirt_RedBlackStripes

Each class inherits the vanilla item, keeping its model, warmth and slots, and swaps the texture of its
camoGround, camoMale and camoFemale selections. The vanilla clothing UV layouts aren't published, so
every texture is a pattern that repeats seamlessly and reads the same whichever way the model maps it
(checks, a drill weave, a scattered fern print); the hoops assume the stripes run across the texture,
as on the vanilla striped T-shirt. Writes data/gear/<key>.png, config/gear.hpp and preview/nz_gear.png.
economy.py adds each item to the loot as a copy of its base's types.xml entry; the vanilla item stays.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import fontpaths  # noqa: F401  (fonts for the preview labels, via nz_food)
import nz_food as nf

MAP_DIR = Path(__file__).resolve().parents[1]
OUT = MAP_DIR / "data" / "gear"
TEXTURE = "maps\\aotearoa\\data\\gear\\{}_co.paa"
SIZE = 1024


@dataclass
class Gear:
    key: str
    cls: str
    base: str
    name: str
    desc: str
    loot: tuple[int, int]
    usages: list[str]


ITEMS = [
    Gear("swanndri_shirt", "Aotearoa_Swanndri_BushShirt", "Shirt_RedCheck", "Swanndri Bush Shirt",
         "Heavy red and black check wool bush shirt. Warm even when it's wet, which in New Zealand is most of the time.",
         (14, 8), ["Farm", "Hunting", "Village"]),
    Gear("swanndri_ranger", "Aotearoa_Swanndri_RangerJacket", "WoolCoat_BlueCheck", "Swanndri Ranger Jacket",
         "Blue and black check wool jacket with a hood, as worn by every farmer, hunter and possum trapper.",
         (8, 5), ["Farm", "Hunting"]),
    Gear("stubbies", "Aotearoa_Stubbies", "ShortJeans_Darkblue", "Stubbies",
         "Short navy cotton drill work shorts. Worn year round regardless of the weather.", (14, 8),
         ["Town", "Village", "Farm", "Industrial"]),
    Gear("jandals", "Aotearoa_Jandals", "SandalsShoes_Black", "Jandals",
         "Rubber jandals. Not much use for running, but a true Kiwi wears them anyway.", (16, 10),
         ["Town", "Village", "Coast"]),
    Gear("allblacks_tee", "Aotearoa_AllBlacks_Tee", "TShirt_Black", "All Blacks Tee",
         "Black supporters' tee with a silver fern print.", (12, 7), ["Town", "Village", "School"]),
    Gear("canterbury_jersey", "Aotearoa_Canterbury_Jersey", "TShirt_RedBlackStripes", "Canterbury Rugby Jersey",
         "Red and black hooped rugby jersey from Canterbury.", (10, 6), ["Town", "Village", "School"]),
]
ITEM_CLASSES = {i.cls for i in ITEMS}


def _knit(rng, base, amount=18.0) -> np.ndarray:
    """Fine wool or cotton grain round a colour, seamless (noise blurred with wraparound)."""
    g = np.random.default_rng(rng.randrange(2**32))
    n = g.normal(0, 1, (SIZE, SIZE))
    n = (n + np.roll(n, 1, 0) + np.roll(n, 1, 1)) / 3
    return np.clip(np.array(base, dtype=float)[None, None, :] + amount * n[..., None], 0, 255)


def check(c1, c2, checks, rng) -> Image.Image:
    """Buffalo check: two colours in squares, with the crossings darker, plus wool fuzz."""
    cell = SIZE // checks
    y, x = np.mgrid[0:SIZE, 0:SIZE]
    a, b = (x // cell) % 2, (y // cell) % 2
    c1, c2 = np.array(c1, float), np.array(c2, float)
    mid = (c1 + c2) / 2 * 0.8
    img = np.where((a & b)[..., None] == 1, c2 * 0.85, np.where((a ^ b)[..., None] == 1, mid, c1))
    # Woven look: thin lighter threads every few pixels in both directions.
    thread = ((x % 6 == 0) | (y % 6 == 0))[..., None] * 14.0
    img = img + thread + (_knit(rng, (0, 0, 0), 12.0))
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    return im.filter(ImageFilter.GaussianBlur(0.8))


def drill(colour, rng) -> Image.Image:
    y, x = np.mgrid[0:SIZE, 0:SIZE]
    twill = (((x + y) % 8) < 3)[..., None] * 16.0
    img = _knit(rng, colour, 8.0) + twill - 8.0
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))


def rubber(colour, rng) -> Image.Image:
    img = _knit(rng, colour, 6.0)
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    return im.filter(ImageFilter.GaussianBlur(1.2))


def fern(d: ImageDraw.ImageDraw, x, y, s, fill, angle):
    """A silver fern frond: a gently curved stem with solid leaflets that shorten towards the tip."""
    ca, sa = math.cos(angle), math.sin(angle)

    def at(t, off):
        bend = 0.1 * s * math.sin(t * math.pi * 0.9)
        u, v = s * t, bend + off
        return x + u * ca - v * sa, y - (u * sa + v * ca)

    d.line([at(k / 20, 0) for k in range(21)], fill=fill, width=max(3, int(s / 30)))
    for k in range(1, 19):
        t = k / 20
        length = 0.2 * s * (1 - t) ** 0.8 + 0.02 * s
        for side in (1, -1):
            base0, base1 = at(t - 0.022, 0), at(t + 0.022, 0)
            tip = at(t + 0.05, side * length)
            d.polygon([base0, tip, base1], fill=fill)


def fern_print(rng) -> Image.Image:
    im = Image.fromarray(_knit(rng, (18, 18, 20), 7.0).astype(np.uint8))
    big = Image.new("RGBA", (SIZE * 3, SIZE * 3), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    step = SIZE / 3
    for i in range(3):
        for j in range(3):
            x = SIZE + (i + 0.5 * (j % 2) + 0.1) * step
            y = SIZE + (j + 0.85) * step
            a = math.radians(60 + (i * 37 + j * 23) % 40)
            for ox in (-SIZE, 0, SIZE):
                for oy in (-SIZE, 0, SIZE):
                    fern(d, x + ox, y + oy, 0.8 * step, (200, 204, 210, 235), a)
    tile = big.crop((SIZE, SIZE, 2 * SIZE, 2 * SIZE)).filter(ImageFilter.GaussianBlur(0.7))
    im.paste(tile, (0, 0), tile)
    return im


def hoops(c1, c2, bands, rng) -> Image.Image:
    y = np.mgrid[0:SIZE, 0:SIZE][0]
    band = (y * bands // SIZE) % 2
    img = np.where(band[..., None] == 1, np.array(c2, float), np.array(c1, float))
    img = img + _knit(rng, (0, 0, 0), 9.0) + ((y % 4 == 0)[..., None] * -8.0)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))


PAINT = {
    "swanndri_shirt": lambda r: check((176, 28, 32), (22, 20, 22), 8, r),
    "swanndri_ranger": lambda r: check((36, 70, 140), (18, 20, 26), 6, r),
    "stubbies": lambda r: drill((34, 44, 78), r),
    "jandals": lambda r: rubber((26, 50, 110), r),
    "allblacks_tee": fern_print,
    "canterbury_jersey": lambda r: hoops((196, 22, 30), (16, 16, 16), 12, r),
}


def texture(item: Gear) -> Image.Image:
    return PAINT[item.key](random.Random(item.key))


def config_text() -> str:
    out = ["// New Zealand clothing, generated by tools/nz_gear.py. Included inside CfgVehicles in config.cpp.",
           "// Each class inherits a vanilla item and only swaps its textures."]
    out += [f"class {b};" for b in sorted({i.base for i in ITEMS})]
    for i in ITEMS:
        tex = TEXTURE.format(i.key)
        out += [f"class {i.cls}: {i.base}", "{", "\tscope = 2;", f'\tdisplayName = "{i.name}";',
                f'\tdescriptionShort = "{i.desc}";',
                f'\thiddenSelectionsTextures[] = {{"{tex}", "{tex}", "{tex}"}};', "};"]
    return "\n".join(out) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tiles = []
    for item in ITEMS:
        im = texture(item)
        im.save(OUT / f"{item.key}.png", optimize=True)
        tiles.append((item, im))
    (MAP_DIR / "config" / "gear.hpp").write_text(config_text(), encoding="utf-8", newline="\r\n")
    cell = 300
    sheet = Image.new("RGB", (cell * len(tiles), cell + 34), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    f = nf.font("sans", 15)
    for k, (item, im) in enumerate(tiles):
        sheet.paste(im.resize((cell - 10, cell - 10)), (k * cell + 5, 5))
        d.text((k * cell + cell / 2, cell + 16), item.name, font=f, fill=(235, 235, 235), anchor="mm")
    sheet.save(MAP_DIR / "preview" / "nz_gear.png", optimize=True)
    print(f"{len(ITEMS)} New Zealand clothing items, textures in {OUT.relative_to(MAP_DIR)}")


if __name__ == "__main__":
    main()
