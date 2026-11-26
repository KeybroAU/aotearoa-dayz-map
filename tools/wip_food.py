"""Work-in-progress copy of the New Zealand food and drink, for trying real brand label artwork.

    python tools/wip_food.py

Every item in nz_food.ITEMS is duplicated into wip/food/ as its own test mod, @AotearoaFoodWIP
(addons/aotearoa_food_wip.pbo, prefix aotearoa_food_wip). Its classes are named AotearoaWIP_* and
inherit the live Aotearoa_* items, so they behave the same, but they have no loot entries: spawn them
with an admin tool to look at them in game. The live mod, its loot and its releases are untouched.

Put a label image in wip/food/labels/ named after the item's key (for example labels/lp.png or
labels/marmite.jpg) and it is fitted onto every front of that pack, over the generated artwork.
Use artwork you have the right to use. labels/, textures/ and the preview are ignored by git so
brand images stay out of this public repo and out of the source zip; README.md lists each item's
key and the shape its label should be.

It writes:
  wip/food/textures/<key>.png        each texture: the generated artwork, with your label on it if there is one
  wip/food/preview.png               live texture next to the WIP texture for every item with a label
  wip/food/config.cpp                the AotearoaWIP_* classes
  wip/food/scripts/4_World/AotearoaFoodWIP.c   WIP tins open into WIP opened tins
  wip/food/README.md                 the label list
  wip/food/templates/<key>.png       a blank label at twice the size it is used, with the safe area,
                                     the parts that are hidden or cut off, and a faint copy of the
                                     current artwork to line up against: paint over it and save it in labels/

pack_mod.py --wip converts the textures and packs dist/@AotearoaFoodWIP. Load it after @Aotearoa.
To move a finished label into the live mod, copy its texture over data/food/<key>.png (and only
if the artwork may be published).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nz_food  # noqa: E402
from nz_food import FRONTS, ITEMS, LAYOUTS  # noqa: E402

MAP_DIR = Path(__file__).resolve().parents[1]
WIP = MAP_DIR / "wip" / "food"
LABELS = WIP / "labels"
TEXTURES = WIP / "textures"
PREFIX = "aotearoa_food_wip"
TEXTURE = PREFIX + "\\data\\{}.paa"
EXTS = (".png", ".jpg", ".jpeg", ".webp")

# Layouts whose texture is a grid of identical label cells the size of the front, because their UV
# layout isn't published: the label goes in every cell.
TILED = {"bar", "honey"}
# The sardine tin carries the label twice: a second band below the first.
EXTRA_BANDS = {"sardines": [0.26]}
# The 100 g tin's lid covers the second half of its label band.
MAX_FRONTS = {"tin100": 1}


def wip_class(cls: str) -> str:
    return cls.replace("Aotearoa_", "AotearoaWIP_", 1)


def label_for(item) -> Path | None:
    for ext in EXTS:
        p = LABELS / f"{item.key}{ext}"
        if p.exists():
            return p
    return None


def slots(item) -> list[tuple[tuple[float, float, float, float], int]]:
    """Every place the front of the pack appears on its texture, as fractions, with its rotation."""
    (x0, y0, x1, y1), rot = FRONTS[item.layout]
    (bx0, _, bx1, _), _, repeats = LAYOUTS[item.layout]
    if item.layout in TILED:
        w, h = x1 - x0, y1 - y0
        return [((c * w, r * h, (c + 1) * w, (r + 1) * h), rot)
                for r in range(round(1 / h)) for c in range(round(1 / w))]
    period = (bx1 - bx0) / repeats if repeats > 1 else 0
    out = []
    for dy in [0.0] + EXTRA_BANDS.get(item.layout, []):
        for k in range(min(MAX_FRONTS.get(item.layout, repeats), repeats) if period else 1):
            out.append(((x0 + k * period, y0 + dy, x1 + k * period, y1 + dy), rot))
    return out


def slot_shape(item) -> tuple[int, int]:
    """Pixel size of one upright front, the shape a label image should have."""
    (x0, y0, x1, y1), rot = FRONTS[item.layout]
    _, (w, h), _ = LAYOUTS[item.layout]
    sw, sh = round((x1 - x0) * w), round((y1 - y0) * h)
    return (sh, sw) if rot % 180 else (sw, sh)


def apply_label(tex: Image.Image, item, label: Image.Image) -> Image.Image:
    tex = tex.copy()
    w, h = tex.size
    upright = slot_shape(item)
    art = ImageOps.fit(label.convert(tex.mode), upright, Image.LANCZOS)
    for (x0, y0, x1, y1), rot in slots(item):
        box = (round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h))
        piece = art.rotate(-rot, expand=True) if rot else art
        piece = piece.resize((box[2] - box[0], box[3] - box[1]), Image.LANCZOS)
        tex.paste(piece, box[:2])
    return tex


# Parts of an upright front that don't show well in game, as fractions (x0, y0, x1, y1) and a note.
HIDDEN = {
    "bag": [((0, 0, 1, 0.1), "heat seal: crimped"), ((0, 0.9, 1, 1), "heat seal: crimped")],
    "soda": [((0, 0, 1, 0.05), "rim"), ((0, 0.95, 1, 1), "rim")],
    "tin": [((0, 0, 1, 0.04), "rim"), ((0, 0.96, 1, 1), "rim")],
    "rice": [((0, 0, 1, 0.5), "coloured band across the bag")],
}
SAFE = 0.07


def write_templates() -> list[Path]:
    out_dir = WIP / "templates"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for item in ITEMS:
        w, h = slot_shape(item)
        W, H = 2 * w, 2 * h
        im = Image.new("RGB", (W, H), (238, 238, 238))
        live = MAP_DIR / "data" / "food" / f"{item.key}.png"
        if live.exists():
            tex = Image.open(live).convert("RGB")
            (x0, y0, x1, y1), rot = FRONTS[item.layout]
            tw, th = tex.size
            face = tex.crop((round(x0 * tw), round(y0 * th), round(x1 * tw), round(y1 * th)))
            face = (face.rotate(rot, expand=True) if rot else face).resize((W, H)).filter(ImageFilter.GaussianBlur(3))
            im = Image.blend(im, face, 0.25)
        d = ImageDraw.Draw(im, "RGBA")
        for (a, b, c, e), note in HIDDEN.get(item.layout, []):
            box = (a * W, b * H, c * W, e * H)
            d.rectangle(box, fill=(220, 40, 40, 50))
            for x in range(int(box[0]) - H, int(box[2]), 24):
                d.line((x, box[3], x + (box[3] - box[1]), box[1]), fill=(220, 40, 40, 90), width=2)
            d.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), note, font=nz_food.font("sans", max(12, H // 40)),
                   fill=(150, 20, 20), anchor="mm")
        sx, sy = SAFE * W, SAFE * H
        for k in range(0, int(W - 2 * sx), 30):
            d.line((sx + k, sy, sx + min(k + 15, W - 2 * sx), sy), fill=(30, 110, 220), width=3)
            d.line((sx + k, H - sy, sx + min(k + 15, W - 2 * sx), H - sy), fill=(30, 110, 220), width=3)
        for k in range(0, int(H - 2 * sy), 30):
            d.line((sx, sy + k, sx, sy + min(k + 15, H - 2 * sy)), fill=(30, 110, 220), width=3)
            d.line((W - sx, sy + k, W - sx, sy + min(k + 15, H - 2 * sy)), fill=(30, 110, 220), width=3)
        d.line((W / 2, 0, W / 2, H), fill=(0, 0, 0, 40), width=1)
        d.line((0, H / 2, W, H / 2), fill=(0, 0, 0, 40), width=1)
        d.rectangle((0, 0, W - 1, H - 1), outline=(0, 0, 0), width=4)
        f = nz_food.font("sans", max(14, min(W, H) // 22))
        small = nz_food.font("plain", max(12, min(W, H) // 30))
        lines = [(item.name, f), (f"save as wip/food/labels/{item.key}.png", small),
                 (f"{W} x {H} px (used at {w} x {h})", small), ("keep text inside the blue dashes", small)]
        if FRONTS[item.layout][1]:
            lines.append(("paint it upright: it is turned onto the texture", small))
        if item.layout in TILED:
            lines.append(("repeated over the whole wrapper", small))
        y = H * 0.5 - len(lines) * f.size * 0.7
        for text, fnt in lines:
            d.text((W / 2, y), text, font=fnt, fill=(20, 20, 20), anchor="mm", stroke_width=2,
                   stroke_fill=(255, 255, 255))
            y += fnt.size * 1.4
        p = out_dir / f"{item.key}.png"
        im.quantize(96).save(p, optimize=True)
        paths.append(p)
    return paths


def write_textures() -> list:
    TEXTURES.mkdir(parents=True, exist_ok=True)
    LABELS.mkdir(parents=True, exist_ok=True)
    labelled = []
    for item in ITEMS:
        live = MAP_DIR / "data" / "food" / f"{item.key}.png"
        tex = Image.open(live) if live.exists() else nz_food.texture(item)
        tex = tex.convert("RGBA" if item.paa.endswith("_ca") else "RGB")
        lab = label_for(item)
        if lab:
            tex = apply_label(tex, item, Image.open(lab))
            labelled.append(item)
        tex.save(TEXTURES / f"{item.key}.png")
    return labelled


def write_preview(labelled: list) -> Path | None:
    p = WIP / "preview.png"
    if not labelled:
        p.unlink(missing_ok=True)
        return None
    cell = 360
    sheet = Image.new("RGB", (cell * 2, len(labelled) * (cell + 30)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    font = nz_food.font("sans", 15)
    for i, item in enumerate(labelled):
        y = i * (cell + 30)
        for j, src in enumerate((MAP_DIR / "data" / "food" / f"{item.key}.png", TEXTURES / f"{item.key}.png")):
            im = Image.open(src).convert("RGB")
            im.thumbnail((cell - 20, cell - 20))
            sheet.paste(im, (j * cell + (cell - im.width) // 2, y + 10))
        d.text((cell, y + cell + 12), f"{item.name}: live (left), WIP (right)", font=font, fill=(235, 235, 235),
               anchor="mm")
    sheet.save(p)
    return p


def config_text() -> str:
    bases = sorted({i.cls for i in ITEMS} | {i.cls + "_Opened" for i in ITEMS if i.opened})
    out = ["// Work-in-progress copy of the New Zealand food and drink, generated by tools/wip_food.py.",
           "// Packed as @AotearoaFoodWIP by pack_mod.py --wip. Not in the loot: spawn the AotearoaWIP_* classes",
           "// with an admin tool. Load after @Aotearoa.", "",
           "class CfgPatches", "{", "\tclass Aotearoa_Food_WIP", "\t{",
           "\t\tunits[] = {" + ", ".join(f'"{wip_class(i.cls)}"' for i in ITEMS) + "};",
           "\t\tweapons[] = {};", "\t\trequiredVersion = 0.1;", '\t\trequiredAddons[] = {"aotearoa"};', "\t};", "};", "",
           "class CfgMods", "{", "\tclass Aotearoa_Food_WIP", "\t{", '\t\tdir = "AotearoaFoodWIP";',
           '\t\tname = "Aotearoa food (work in progress)";', '\t\tauthor = "KeybroAU";', '\t\ttype = "mod";',
           '\t\tdependencies[] = {"World"};', "\t\tclass defs", "\t\t{", "\t\t\tclass worldScriptModule", "\t\t\t{",
           '\t\t\t\tvalue = "";', f'\t\t\t\tfiles[] = {{"{PREFIX}/scripts/4_World"}};', "\t\t\t};", "\t\t};", "\t};",
           "};", "", "class CfgVehicles", "{"]
    out += [f"\tclass {b};" for b in bases]

    def block(cls, item):
        return [f"\tclass {wip_class(cls)}: {cls}", "\t{", "\t\tscope = 2;",
                f'\t\tdisplayName = "[WIP] {item.name}";',
                f'\t\thiddenSelectionsTextures[] = {{"{TEXTURE.format(item.paa)}"}};', "\t};"]

    for item in ITEMS:
        out += block(item.cls, item)
        if item.opened:
            out += block(item.cls + "_Opened", item)
    out.append("};")
    return "\n".join(out) + "\n"


def script_text() -> str:
    out = ["// Generated by tools/wip_food.py: WIP tins open into WIP opened tins, so the test label stays on.", ""]
    for item in ITEMS:
        if item.opened:
            out += [f"class {wip_class(item.cls)} : {item.cls}", "{", "\toverride void Open()", "\t{",
                    f'\t\tReplaceEdibleWithNew("{wip_class(item.cls)}_Opened");', "\t}", "}", ""]
    return "\n".join(out)


def readme_text() -> str:
    rows = []
    for item in ITEMS:
        w, h = slot_shape(item)
        g = math.gcd(w, h)
        rows.append(f"| {item.name} | `{item.key}` | `{wip_class(item.cls)}` | {w} x {h} ({w // g}:{h // g}) |")
    return "\n".join([
        "# Food and drink: work in progress",
        "",
        "A test copy of every New Zealand food and drink item, for trying real brand label artwork without touching "
        "the live items. `python tools/wip_food.py` builds it; `python tools/pack_mod.py --wip` packs it as "
        "`dist/@AotearoaFoodWIP`. Load that after `@Aotearoa` and spawn the `AotearoaWIP_*` classes with an admin "
        "tool. They aren't in the loot, and nothing here goes into a release.",
        "",
        "`templates/<key>.png` is a blank label for each item at twice the size it is used: paint over it (the "
        "faint picture is the current artwork, the blue dashes are the safe area for text, and red hatching marks "
        "parts that are crimped, rimmed or covered) and save the result in `labels/`.",
        "",
        "To try a label, put an image in `labels/` named after the item's key, such as `labels/lp.png` or "
        "`labels/marmite.jpg`, and run the script again. The image is cropped to the shape below and fitted onto "
        "every front of the pack, over the generated artwork. A flat, straight-on scan or photo of the label works "
        "best. `preview.png` shows the live texture next to the WIP one for every item that has a label.",
        "",
        "Use artwork you have the right to use. `labels/`, `textures/` and `preview.png` are ignored by git, so "
        "brand images stay out of the public repo and the source zip. A finished label moves into the live mod by "
        "copying `textures/<key>.png` over `data/food/<key>.png`, but only if the artwork may be published on the "
        "Workshop.",
        "",
        "Tins whose UV layout isn't published (the Whittaker's bars and the honey jar) repeat the label over the "
        "whole texture, as the live ones do.",
        "",
        "| Item | Key (label file name) | WIP class | Label shape in pixels |",
        "|---|---|---|---|",
        *rows,
        "",
    ])


def main() -> None:
    labelled = write_textures()
    templates = write_templates()
    preview = write_preview(labelled)
    (WIP / "config.cpp").write_text(config_text(), encoding="utf-8")
    (WIP / "scripts" / "4_World").mkdir(parents=True, exist_ok=True)
    (WIP / "scripts" / "4_World" / "AotearoaFoodWIP.c").write_text(script_text(), encoding="utf-8")
    (WIP / "$PBOPREFIX$").write_text(PREFIX + "\n")
    (WIP / "README.md").write_text(readme_text(), encoding="utf-8")
    version = (MAP_DIR / "VERSION").read_text().strip()
    (WIP / "mod.cpp").write_text("\n".join([
        'name = "Aotearoa food (work in progress)";', 'author = "KeybroAU";', f'version = "{version}";',
        'overview = "Test copies of the Aotearoa food and drink (AotearoaWIP_* classes) for trying new labels. '
        'Not for public servers. Load after @Aotearoa.";',
        'tooltip = "Aotearoa food WIP";', 'action = "https://github.com/KeybroAU/aotearoa-dayz-map";', ""]))
    print(f"{len(ITEMS)} WIP food and drink items in {WIP.relative_to(MAP_DIR)}, "
          f"{len(labelled)} with a label from labels/, {len(templates)} label templates" + (f"; preview in {preview.relative_to(MAP_DIR)}" if preview else ""))


if __name__ == "__main__":
    main()
