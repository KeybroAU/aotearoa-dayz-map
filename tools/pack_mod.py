"""Pack Aotearoa into a ready-to-use mod and server folder.

Run it on the Windows machine with DayZ Tools, after the world is exported from Terrain Builder
(world/aotearoa.wrp and data/layers/ exist):

    python pack_mod.py
    python pack_mod.py --key aotearoa --zip

It writes dist/:

    dist/@Aotearoa/                      the client and server mod: addons/aotearoa.pbo, mod.cpp, keys/
    dist/@AotearoaMap/                   the map item mod (class AotearoaMap): addons/aotearoa_map.pbo, mod.cpp, keys/
    dist/server/                         drop this into your DayZ Server folder:
        @Aotearoa/, @AotearoaMap/, keys/, serverDZ.cfg, start_server.bat, start_server.sh,
        mpmissions/dayzOffline.aotearoa/ vanilla Chernarus mission with every Aotearoa file
                                         copied over it and cfggameplay.json / cfgeconomycore.xml merged

Steps it runs:
  1. converts the branding images in data/branding/, the sign textures in data/signs/, the model
     textures in data/models/, the food labels in data/food/ and the map item textures in mapitem/data/ to .paa with ImageToPAA
  2. packs config.cpp, config/, data/, structures/ and world/ into aotearoa.pbo with Addon Builder (prefix maps\\aotearoa),
     and mapitem/ into aotearoa_map.pbo (prefix aotearoa_map)
  3. with --key NAME, makes a signing key (once) and signs the PBOs
  4. builds the server folder, merging the mission files into a copy of vanilla dayzOffline.chernarusplus

Options:
  --tools DIR             DayZ Tools folder (found from the registry or the Steam default if not given)
  --vanilla-mission DIR   vanilla mpmissions/dayzOffline.chernarusplus (found in the DayZ Server install if not given)
  --key NAME              sign with keys/NAME.biprivatekey, creating it if needed
  --spawners              also load the town and site buildings from object spawner files. Only for a quick
                          test on a world without the Terrain Builder objects; otherwise every building doubles.
  --setpieces-in-wrp      don't load the set pieces (landmarks, Interislander wreck, base extensions) from
                          their spawner file, because you imported source/objects/setpieces_tb.txt into the WRP
  --difficulty LEVEL      easy, normal (default, vanilla feel) or hard; scales loot, vehicles and infected
  --vanilla-loot          keep vanilla loot amounts. Without it, loot is scaled to this map's loot points
                          (about half of Chernarus's), so each building holds as much as on Chernarus.
  --loot/--vehicles/--infected X   fine-tune one of those by a factor (overrides the difficulty for it)
  --wip                   also pack the work-in-progress food test mod, dist/@AotearoaFoodWIP, from wip/food/
                          (run tools/wip_food.py first). It is never added to the server folder or a release.
  --traders               load the four trader compounds (vanilla objects) from their spawner file
  --expansion             set the server up for DayZ Expansion: trader NPCs, trader zones, and the safe zone
                          and spawn snippets (implies --traders; see mission/mods/README.md)
  --traderplus            copy the TraderPlus trader and safe area snippets (implies --traders)
  --no-map-item           leave out @AotearoaMap (the AotearoaMap item and its loot entries)
  --skip-pbo              build only the server folder (reuses dist/@Aotearoa if it is there)
  --zip                   also write dist/Aotearoa_mod.zip and dist/Aotearoa_server.zip
  --dry-run               print what would run without running it
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAP_DIR = Path(__file__).resolve().parents[1]
PREFIX = "maps\\aotearoa"
MISSION = "dayzOffline.aotearoa"
PACKED = ["config.cpp", "$PBOPREFIX$", "config", "data", "gui", "navmesh", "scripts", "structures", "world"]
# Spawner files that need a custom model before they can load.
MODEL_SPAWNERS = [("structures/sign_town/sign_town.p3d", "aotearoa/signs_spawner.json", "town name signs"),
                  ("structures/sign_post/sign_post.p3d", "aotearoa/roadsigns_spawner.json", "road signs")]
SKIP_IN_DATA = ["branding/art"]
COPY_DIRECT = "*.paa,*.rvmat,*.wrp,*.png,*.jpg,*.shp,*.shx,*.dbf,*.cfg,*.hpp,*.txt,*.c,*.xml,*.nm,*.layout"
BRANDING = [("logo_512.png", "logo_512_ca.paa"), ("icon_128.png", "icon_128_ca.paa"),
            ("icon_64.png", "icon_64_ca.paa"), ("loading_1.jpg", "loading_1_co.paa"),
            ("loading_2.jpg", "loading_2_co.paa"), ("map_picture.jpg", "map_picture_co.paa")]
MAPITEM = MAP_DIR / "mapitem"
MAPITEM_PREFIX = "aotearoa_map"
MAPITEM_MOD = "@AotearoaMap"
WIP_FOOD = MAP_DIR / "wip" / "food"
WIP_PREFIX = "aotearoa_food_wip"
WIP_MOD = "@AotearoaFoodWIP"
STEAM_DIRS = [Path(r"C:\Program Files (x86)\Steam\steamapps\common"), Path(r"C:\Program Files\Steam\steamapps\common")]
SETPIECES = "setpieces_spawner.json"
MERGED_AWAY = ["cfggameplay.worldsdata.json", "cfgeconomycore.aotearoa.xml"]
# Vanilla mission files that hold Chernarus positions. Bohemia's custom terrain guide says to replace
# them: the clusters (fruit trees, mushrooms) come from ExportClusterData once the world is built,
# and areaflags.map is painted for this map in the economy editor (or left out).
CHERNARUS_ONLY = ["areaflags.map", "mapgroupdirt.xml", "cfgundergroundtriggers.json"]
CHERNARUS_CLUSTERS = "mapgroupcluster*.xml"

# Factors on vanilla amounts: loot (types nominal/min), vehicles (events nominal/min/max), infected
# (Infected* events and ZombieMaxCount).
DIFFICULTY = {
    "easy": {"loot": 1.5, "vehicles": 1.5, "infected": 0.6},
    "normal": {"loot": 1.0, "vehicles": 1.0, "infected": 1.0},
    "hard": {"loot": 0.6, "vehicles": 0.6, "infected": 1.5},
}

DRY = False


def loot_density() -> tuple[float, int, int]:
    """This map's loot points over Chernarus's, from mapgrouppos.xml and the vanilla per-building counts."""
    data = json.loads((MAP_DIR / "tools" / "loot_points.json").read_text(encoding="utf-8"))
    names = re.findall(r'<group name="([^"]+)"', (MAP_DIR / "mission" / MISSION / "mapgrouppos.xml").read_text(encoding="utf-8"))
    points = sum(data["points"].get(n, 0) for n in names)
    return points / data["chernarus_points"], points, data["chernarus_points"]


def run(cmd: list, cwd: Path | None = None) -> None:
    print("  > " + " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd))
    if DRY:
        return
    res = subprocess.run([str(c) for c in cmd], cwd=cwd)
    if res.returncode != 0:
        sys.exit(f"Command failed with exit code {res.returncode}. See its output above.")


def find_tools(given: Path | None) -> Path | None:
    if given:
        return given
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Bohemia Interactive\Dayz Tools") as k:
            return Path(winreg.QueryValueEx(k, "path")[0])
    except (ImportError, OSError):
        pass
    for d in STEAM_DIRS:
        if (d / "DayZ Tools").exists():
            return d / "DayZ Tools"
    return None


def find_vanilla(given: Path | None) -> Path | None:
    if given:
        return given
    for d in STEAM_DIRS:
        p = d / "DayZServer" / "mpmissions" / "dayzOffline.chernarusplus"
        if p.exists():
            return p
    return None


def tool(tools: Path, *parts: str) -> Path:
    p = tools.joinpath("Bin", *parts)
    if not p.exists() and not DRY:
        sys.exit(f"Can't find {p}. Pass --tools with your DayZ Tools folder.")
    return p


def convert_branding(tools: Path) -> None:
    from PIL import Image

    exe = tool(tools, "ImageToPAA", "ImageToPAA.exe")
    src_dir = MAP_DIR / "data" / "branding"
    with tempfile.TemporaryDirectory() as tmp:
        for src, dst in BRANDING:
            path = src_dir / src
            if not path.exists():
                print(f"  (no {src}, skipped)")
                continue
            if path.suffix.lower() != ".png":
                png = Path(tmp) / (path.stem + ".png")
                Image.open(path).convert("RGB").save(png)
                path = png
            run([exe, path, src_dir / dst])


def convert_textures(tools: Path) -> None:
    """Sign, model and food textures: cut-out post signs keep their alpha (_ca), the rest are colour maps (_co)."""
    exe = tool(tools, "ImageToPAA", "ImageToPAA.exe")
    jobs = [(p, "_co") for p in sorted((MAP_DIR / "data" / "signs").glob("sign_*.png"))]
    jobs += [(p, "_ca") for p in sorted((MAP_DIR / "data" / "signs").glob("post_*.png"))]
    jobs += [(p, "_co") for p in sorted((MAP_DIR / "data" / "models").glob("*.png"))]
    jobs += [(p, "_co") for p in sorted((MAP_DIR / "data" / "food" / "models").glob("*.png"))]
    jobs += [(p, "_co") for p in sorted((MAP_DIR / "data" / "gear").glob("*.png"))]
    for png, suffix in jobs:
        run([exe, png, png.with_name(png.stem + suffix + ".paa")])
    import nz_food

    for item in nz_food.ITEMS:
        png = MAP_DIR / "data" / "food" / f"{item.key}.png"
        run([exe, png, png.with_name(item.paa + ".paa")])
        jobs.append((png, item.paa))
    print(f"  {len(jobs)} sign, model and food textures")


def convert_map_item(tools: Path) -> None:
    """Map item textures, for @AotearoaMap and for the world's own mapTexture* (data/mapitem/)."""
    exe = tool(tools, "ImageToPAA", "ImageToPAA.exe")
    pngs = sorted((MAPITEM / "data").glob("aotearoa_map_*.png"))
    if not pngs:
        sys.exit("No mapitem/data/aotearoa_map_*.png. Run tools/build_map_item.py first.")
    world_copy = MAP_DIR / "data" / "mapitem"
    if not DRY:
        world_copy.mkdir(parents=True, exist_ok=True)
    for png in pngs:
        paa = png.with_name(png.stem + "_co.paa")
        run([exe, png, paa])
        if not DRY:
            shutil.copy2(paa, world_copy / paa.name)
    print(f"  {len(pngs)} map item textures")


def pack_map_item(tools: Path, mod_dir: Path) -> Path:
    stage = MAP_DIR.parent / "_aotearoa_map_pack" / MAPITEM_PREFIX
    print(f"  staging the map item in {stage}")
    if not DRY:
        shutil.rmtree(stage.parent, ignore_errors=True)
        (stage / "data").mkdir(parents=True)
        for name in ("config.cpp", "$PBOPREFIX$"):
            shutil.copy2(MAPITEM / name, stage / name)
        shutil.copytree(MAPITEM / "scripts", stage / "scripts")
        for paa in (MAPITEM / "data").glob("*.paa"):
            shutil.copy2(paa, stage / "data" / paa.name)
        (mod_dir / "addons").mkdir(parents=True, exist_ok=True)
        (stage.parent / "include.txt").write_text("*.paa,*.c")
    run([tool(tools, "AddonBuilder", "AddonBuilder.exe"), stage, mod_dir / "addons", "-clear",
         f"-prefix={MAPITEM_PREFIX}", f"-include={stage.parent / 'include.txt'}", "-project=P:\\"])
    if not DRY:
        shutil.rmtree(stage.parent, ignore_errors=True)
        shutil.copy2(MAPITEM / "mod.cpp", mod_dir / "mod.cpp")
    return mod_dir / "addons" / f"{MAPITEM_PREFIX}.pbo"


def pack_wip_food(tools: Path, mod_dir: Path) -> Path:
    """The work-in-progress food test mod from wip/food/ (built by tools/wip_food.py)."""
    import nz_food

    if not (WIP_FOOD / "textures").exists() and not DRY:
        sys.exit("No wip/food/textures/. Run tools/wip_food.py first.")
    exe = tool(tools, "ImageToPAA", "ImageToPAA.exe")
    stage = MAP_DIR.parent / "_aotearoa_wip_pack" / WIP_PREFIX
    print(f"  staging the WIP food in {stage}")
    if not DRY:
        shutil.rmtree(stage.parent, ignore_errors=True)
        (stage / "data").mkdir(parents=True)
        for name in ("config.cpp", "$PBOPREFIX$"):
            shutil.copy2(WIP_FOOD / name, stage / name)
        shutil.copytree(WIP_FOOD / "scripts", stage / "scripts")
        (mod_dir / "addons").mkdir(parents=True, exist_ok=True)
        (stage.parent / "include.txt").write_text("*.paa,*.c")
    for item in nz_food.ITEMS:
        run([exe, WIP_FOOD / "textures" / f"{item.key}.png", stage / "data" / f"{item.paa}.paa"])
    run([tool(tools, "AddonBuilder", "AddonBuilder.exe"), stage, mod_dir / "addons", "-clear",
         f"-prefix={WIP_PREFIX}", f"-include={stage.parent / 'include.txt'}", "-project=P:\\"])
    if not DRY:
        shutil.rmtree(stage.parent, ignore_errors=True)
        shutil.copy2(WIP_FOOD / "mod.cpp", mod_dir / "mod.cpp")
    return mod_dir / "addons" / f"{WIP_PREFIX}.pbo"


def stage_and_pack(tools: Path, out_addons: Path) -> Path:
    """Copy only the game files to a staging folder on the same drive, then pack that."""
    for need in (MAP_DIR / "world" / "aotearoa.wrp", MAP_DIR / "data" / "layers"):
        if not need.exists() and not DRY:
            sys.exit(f"Missing {need}. Export the world from Terrain Builder first (see docs/TERRAIN_BUILDER_GUIDE.md).")
    stage = MAP_DIR.parent / "_aotearoa_pack" / "aotearoa"
    print(f"  staging game files in {stage}")
    if not DRY:
        shutil.rmtree(stage.parent, ignore_errors=True)
        stage.mkdir(parents=True)
        for name in PACKED:
            src = MAP_DIR / name
            if src.is_dir():
                shutil.copytree(src, stage / name, copy_function=_link_or_copy,
                                ignore=lambda d, names: [n for n in names if _skipped(Path(d) / n)])
            elif src.exists():
                shutil.copy2(src, stage / name)
        out_addons.mkdir(parents=True, exist_ok=True)
        (stage.parent / "include.txt").write_text(COPY_DIRECT)
    run([tool(tools, "AddonBuilder", "AddonBuilder.exe"), stage, out_addons, "-clear", f"-prefix={PREFIX}",
         f"-include={stage.parent / 'include.txt'}", "-project=P:\\"])
    if not DRY:
        shutil.rmtree(stage.parent, ignore_errors=True)
    return out_addons / "aotearoa.pbo"


def _skipped(path: Path) -> bool:
    rel = path.relative_to(MAP_DIR).as_posix()
    return any(rel == "data/" + s or rel.startswith("data/" + s + "/") for s in SKIP_IN_DATA)


def _link_or_copy(src, dst):
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def sign(tools: Path, key: str, pbo: Path, mod_dir: Path) -> None:
    keys = MAP_DIR / "keys"
    private = keys / f"{key}.biprivatekey"
    if not private.exists():
        keys.mkdir(exist_ok=True)
        run([tool(tools, "DsUtils", "DSCreateKey.exe"), key], cwd=keys)
        print(f"  made {private}. Keep it private and back it up; it is git-ignored.")
    run([tool(tools, "DsUtils", "DSSignFile.exe"), private, pbo])
    if not DRY:
        (mod_dir / "keys").mkdir(exist_ok=True)
        shutil.copy2(keys / f"{key}.bikey", mod_dir / "keys")


def merge_dicts(base: dict, extra: dict) -> dict:
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            merge_dicts(base[k], v)
        else:
            base[k] = v
    return base


def build_mission(dest: Path, vanilla: Path | None, spawners: bool, mods: set[str], map_item: bool,
                  setpieces: bool = True) -> list[str]:
    """Vanilla Chernarus mission + generated files + merged configs. Returns warnings."""
    warnings = []
    gen = MAP_DIR / "mission" / MISSION
    if dest.exists():
        shutil.rmtree(dest)
    if vanilla and vanilla.exists():
        shutil.copytree(vanilla, dest)
    else:
        warnings.append("No vanilla dayzOffline.chernarusplus found, so the mission folder holds only the Aotearoa "
                        "files. Copy vanilla over it first (keep the Aotearoa files), or rerun with --vanilla-mission.")
        dest.mkdir(parents=True)
    for name in CHERNARUS_ONLY:
        (dest / name).unlink(missing_ok=True)
    for f in dest.glob(CHERNARUS_CLUSTERS):
        f.write_text('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<map>\n</map>\n', encoding="utf-8")
    (dest / "mapgroupdirt.xml").write_text('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<map>\n</map>\n',
                                           encoding="utf-8")
    (dest / "cfgundergroundtriggers.json").write_text('{\n    "Triggers": []\n}\n', encoding="utf-8")
    for f in dest.iterdir():
        # A Linux server is case sensitive, so vanilla's cfgEffectArea.json would stay beside ours.
        if f.name.lower() == "cfgeffectarea.json":
            f.unlink()
    shutil.copytree(gen, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*MERGED_AWAY))
    if not (dest / "areaflags.map").exists():
        warnings.append("No areaflags.map, so loot uses no area flags. Paint one for this map in the economy "
                        "editor (preview/loot_tiers_2048.png is the guide) and put it in mission/" + MISSION + ".")

    extra = json.loads((gen / "cfggameplay.worldsdata.json").read_text(encoding="utf-8"))
    spawner_files = []
    for model, spawner, what in MODEL_SPAWNERS:
        if (MAP_DIR / model).exists():
            spawner_files.append(spawner)
        else:
            (dest / spawner).unlink(missing_ok=True)
            warnings.append(f"No {model}, so the {what} are left out. Make it from docs/models/ "
                            "(docs/CUSTOM_MODELS.md, item 2) and pack again.")
    if (dest / "aotearoa" / "foodstash_spawner.json").exists():
        spawner_files.append("aotearoa/foodstash_spawner.json")
    if "traders" in mods:
        spawner_files.append("aotearoa/traders_spawner.json")
    else:
        (dest / "aotearoa" / "traders_spawner.json").unlink(missing_ok=True)
    if "expansion" in mods:
        shutil.copytree(MAP_DIR / "mission" / "mods" / "expansion" / "mpmissions" / MISSION, dest, dirs_exist_ok=True)
    if spawners:
        (dest / "aotearoa").mkdir(exist_ok=True)
        for f in ("towns_spawner.json", "pois_spawner.json"):
            shutil.copy2(MAP_DIR / "source" / "objects" / f, dest / "aotearoa" / f)
        spawner_files += ["aotearoa/towns_spawner.json", "aotearoa/pois_spawner.json"]
    if setpieces and (MAP_DIR / "source" / "objects" / SETPIECES).exists():
        (dest / "aotearoa").mkdir(exist_ok=True)
        shutil.copy2(MAP_DIR / "source" / "objects" / SETPIECES, dest / "aotearoa" / SETPIECES)
        spawner_files.append(f"aotearoa/{SETPIECES}")
    if spawner_files:
        extra["WorldsData"]["objectSpawnersArr"] = spawner_files
    gameplay = dest / "cfggameplay.json"
    if gameplay.exists():
        data = json.loads(gameplay.read_text(encoding="utf-8"))
    else:
        data = {}
        warnings.append("No cfggameplay.json in the vanilla mission; wrote one with only the Aotearoa settings.")
    gameplay.write_text(json.dumps(merge_dicts(data, extra), indent=4) + "\n", encoding="utf-8")

    core = dest / "cfgeconomycore.xml"
    block = re.sub(r"<!--.*?-->\s*", "", (gen / "cfgeconomycore.aotearoa.xml").read_text(encoding="utf-8"), flags=re.S)
    blocks = [("aotearoa_ce", block)]
    if map_item:
        shutil.copytree(MAPITEM / "ce", dest / "aotearoa_map_ce", dirs_exist_ok=True)
        blocks.append(("aotearoa_map_ce", '<ce folder="aotearoa_map_ce">\n    <file name="types.xml" type="types" />\n</ce>'))
    if core.exists():
        text = core.read_text(encoding="utf-8")
        for folder, blk in blocks:
            if f'folder="{folder}"' in text:
                continue
            if "</economycore>" not in text:
                warnings.append(f"cfgeconomycore.xml has no </economycore>; add the {folder} block by hand.")
                continue
            indented = "\n".join("\t" + ln for ln in blk.strip().splitlines())
            text = text.replace("</economycore>", indented + "\n</economycore>", 1)
        core.write_text(text, encoding="utf-8")
    else:
        warnings.append("No cfgeconomycore.xml in the mission; the New Zealand loot changes won't load until you "
                        "add the aotearoa_ce block from mission/dayzOffline.aotearoa/cfgeconomycore.aotearoa.xml.")
    return warnings


def _xml(path: Path):
    import xml.etree.ElementTree as ET

    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.parse(path, parser)


def _write_xml(tree, path: Path) -> None:
    import xml.etree.ElementTree as ET

    ET.indent(tree, space="    ")
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def _scale(el, tags, f) -> None:
    for tag in tags:
        node = el.find(tag)
        if node is not None and node.text and node.text.strip().lstrip("-").isdigit():
            v = int(node.text)
            if v > 0:
                node.text = str(max(1, round(v * f)))


# New Zealand changes to vanilla db/events.xml, applied before the difficulty factors. Animals:
# no wolves, bears, roe deer or foxes; far more sheep, and red deer, goats and wild pigs as the pests
# they are. Events: more of the wrecks, convoys, roadblocks and trains this map has groups for, and
# the police car wrecks switched on.
NZ_EVENTS = {
    "AnimalWolf": {"nominal": 0, "min": 0, "max": 0, "active": 0},
    "AnimalBear": {"nominal": 0, "min": 0, "max": 0, "active": 0},
    "AnimalRoeDeer": {"nominal": 0, "min": 0, "max": 0, "active": 0},
    "AmbientFox": {"nominal": 0, "max": 0, "active": 0},
    "AnimalSheep": {"nominal": 14, "max": 6},
    "AnimalDeer": {"nominal": 16},
    "AnimalGoat": {"nominal": 12},
    "AnimalCow": {"nominal": 10},
    "AnimalWildBoar": {"nominal": 10},
    "AmbientHare": {"max": 50},
    "StaticHeliCrash": {"nominal": 5},
    "StaticMilitaryConvoy": {"nominal": 8},
    "StaticPoliceSituation": {"nominal": 10},
    "StaticTrain": {"nominal": 4},
    "StaticPoliceCar": {"nominal": 12, "active": 1},
}


def apply_nz_events(mission: Path) -> list[str]:
    events = mission / "db" / "events.xml"
    if not events.exists():
        return ["no db/events.xml, so the New Zealand animal and event changes are not applied"]
    tree = _xml(events)
    done = 0
    for ev in tree.getroot().iter("event"):
        for tag, value in NZ_EVENTS.get(ev.get("name", ""), {}).items():
            node = ev.find(tag)
            if node is not None:
                node.text = str(value)
                done += 1
    _write_xml(tree, events)
    return [f"New Zealand events: {done} values changed on {len(NZ_EVENTS)} events (no wolves or bears)"]


def apply_difficulty(mission: Path, factors: dict) -> list[str]:
    """Scale loot, vehicle and infected amounts in the merged mission. Returns what changed."""
    done = []
    loot, veh, inf = factors["loot"], factors["vehicles"], factors["infected"]
    if loot != 1.0:
        n = 0
        for path in (mission / "db" / "types.xml", mission / "aotearoa_ce" / "types.xml"):
            if path.exists():
                tree = _xml(path)
                for t in tree.getroot().iter("type"):
                    _scale(t, ("nominal", "min"), loot)
                    n += 1
                _write_xml(tree, path)
        done.append(f"loot x{loot} on {n} item types")
    events = mission / "db" / "events.xml"
    if events.exists() and (veh != 1.0 or inf != 1.0):
        tree = _xml(events)
        nv = ni = 0
        for ev in tree.getroot().iter("event"):
            name = ev.get("name", "")
            if name.startswith("Vehicle") and veh != 1.0:
                _scale(ev, ("nominal", "min", "max"), veh)
                nv += 1
            elif name.startswith("Infected") and inf != 1.0:
                _scale(ev, ("nominal", "min", "max"), inf)
                ni += 1
        _write_xml(tree, events)
        done.append(f"vehicles x{veh} on {nv} events, infected x{inf} on {ni} events")
    glob = mission / "db" / "globals.xml"
    if glob.exists() and inf != 1.0:
        tree = _xml(glob)
        for var in tree.getroot().iter("var"):
            if var.get("name") == "ZombieMaxCount":
                var.set("value", str(round(int(var.get("value")) * inf)))
                done.append(f"ZombieMaxCount {var.get('value')}")
        _write_xml(tree, glob)
    return done


def drop_map_item(server: Path) -> None:
    """Without @AotearoaMap, take its item out of the starting gear and the Expansion market."""
    for path in (server / "mpmissions" / MISSION).glob("aotearoa_spawngear_*.json"):
        preset = json.loads(path.read_text(encoding="utf-8"))
        for group in preset.get("discreteUnsortedItemSets", []):
            group["complexChildrenTypes"] = [c for c in group["complexChildrenTypes"] if c["itemType"] != "AotearoaMap"]
        path.write_text(json.dumps(preset, indent=4) + "\n", encoding="utf-8")
    market = server / "profiles" / "ExpansionMod" / "Market" / "Aotearoa_Navigation.json"
    if market.exists():
        data = json.loads(market.read_text(encoding="utf-8"))
        data["Items"] = [i for i in data["Items"] if i["ClassName"] != "aotearoamap"]
        market.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")


def build_server(out: Path, mod_dir: Path, vanilla: Path | None, spawners: bool, factors: dict,
                 mods: set[str], map_dir: Path | None, setpieces: bool = True) -> list[str]:
    server = out / "server"
    print(f"  server folder {server}")
    if DRY:
        return []
    server.mkdir(parents=True, exist_ok=True)
    if mod_dir.exists():
        shutil.copytree(mod_dir, server / "@Aotearoa", dirs_exist_ok=True)
        if (mod_dir / "keys").exists():
            shutil.copytree(mod_dir / "keys", server / "keys", dirs_exist_ok=True)
    if map_dir and map_dir.exists():
        shutil.copytree(map_dir, server / MAPITEM_MOD, dirs_exist_ok=True)
        if (map_dir / "keys").exists():
            shutil.copytree(map_dir / "keys", server / "keys", dirs_exist_ok=True)
    map_item = bool(map_dir and map_dir.exists())
    warnings = build_mission(server / "mpmissions" / MISSION, vanilla, spawners, mods, map_item, setpieces)
    if map_dir and not map_item:
        warnings.append(f"No dist/{MAPITEM_MOD} yet, so the server runs without the map item. Run without --skip-pbo.")
    mod_src = MAP_DIR / "mission" / "mods"
    if mods & {"expansion", "traderplus"}:
        shutil.rmtree(server / "mod_support", ignore_errors=True)
        (server / "mod_support").mkdir()
        shutil.copy2(mod_src / "README.md", server / "mod_support" / "README.md")
    if "expansion" in mods:
        shutil.copytree(mod_src / "expansion" / "profiles", server / "profiles", dirs_exist_ok=True)
        shutil.copytree(mod_src / "expansion" / "snippets", server / "mod_support" / "expansion", dirs_exist_ok=True)
        warnings.append("Expansion: after the first start, paste the arrays in mod_support/expansion/ into "
                        "SafeZoneSettings.json and SpawnSettings.json (see mod_support/README.md).")
    if "traderplus" in mods:
        shutil.copytree(mod_src / "traderplus" / "snippets", server / "mod_support" / "traderplus", dirs_exist_ok=True)
        warnings.append("TraderPlus: paste the arrays in mod_support/traderplus/ into your TraderPlus configs "
                        "(see mod_support/README.md).")
    if not map_item:
        drop_map_item(server)
    for line in apply_nz_events(server / "mpmissions" / MISSION) + apply_difficulty(server / "mpmissions" / MISSION, factors):
        print(f"  {line}")
    if not mod_dir.exists():
        warnings.append("No dist/@Aotearoa yet, so the server folder has no mod. Run without --skip-pbo.")
    shutil.copy2(MAP_DIR / "mission" / "serverDZ.cfg", server / "serverDZ.cfg")
    shutil.copytree(MAP_DIR / "mission" / "server", server, dirs_exist_ok=True)
    if not map_item:
        for script in ("start_server.bat", "start_server.sh"):
            path = server / script
            path.write_text(path.read_text().replace(f";{MAPITEM_MOD}", ""))
    be = server / "profiles" / "BattlEye"
    be.mkdir(parents=True, exist_ok=True)
    shutil.move(str(server / "battleye" / "BEServer_x64.cfg"), be / "BEServer_x64.cfg")
    shutil.rmtree(server / "battleye", ignore_errors=True)
    if "CHANGE_ME" in (server / "serverDZ.cfg").read_text():
        warnings.append("Set passwordAdmin in dist/server/serverDZ.cfg before going public.")
    warnings.append("Set RConPassword in dist/server/profiles/BattlEye/BEServer_x64.cfg if you use RCon tools.")
    return warnings


def main() -> None:
    global DRY
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tools", type=Path)
    ap.add_argument("--vanilla-mission", type=Path)
    ap.add_argument("--out", type=Path, default=MAP_DIR / "dist")
    ap.add_argument("--key")
    ap.add_argument("--spawners", action="store_true")
    ap.add_argument("--setpieces-in-wrp", action="store_true")
    ap.add_argument("--difficulty", choices=sorted(DIFFICULTY), default="normal")
    ap.add_argument("--loot", type=float)
    ap.add_argument("--vehicles", type=float)
    ap.add_argument("--infected", type=float)
    ap.add_argument("--vanilla-loot", action="store_true")
    ap.add_argument("--traders", action="store_true")
    ap.add_argument("--expansion", action="store_true")
    ap.add_argument("--traderplus", action="store_true")
    ap.add_argument("--no-map-item", action="store_true")
    ap.add_argument("--wip", action="store_true")
    ap.add_argument("--skip-pbo", action="store_true")
    ap.add_argument("--zip", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    DRY = args.dry_run

    out = args.out
    mod_dir = out / "@Aotearoa"
    map_dir = None if args.no_map_item else out / MAPITEM_MOD
    if not args.skip_pbo:
        tools = find_tools(args.tools)
        if tools is None:
            sys.exit("Can't find DayZ Tools. Pass --tools \"C:\\...\\DayZ Tools\".")
        print(f"DayZ Tools: {tools}")
        print("[1/4] Branding images and town signs to .paa")
        convert_branding(tools)
        convert_textures(tools)
        convert_map_item(tools)
        print("[2/4] Packing aotearoa.pbo" + ("" if args.no_map_item else " and aotearoa_map.pbo"))
        if not DRY:
            shutil.rmtree(mod_dir, ignore_errors=True)
        pbo = stage_and_pack(tools, mod_dir / "addons")
        if not DRY:
            shutil.copy2(MAP_DIR / "mod" / "mod.cpp", mod_dir / "mod.cpp")
        map_pbo = None
        if map_dir:
            if not DRY:
                shutil.rmtree(map_dir, ignore_errors=True)
            map_pbo = pack_map_item(tools, map_dir)
        wip_pbo = None
        if args.wip:
            wip_dir = out / WIP_MOD
            if not DRY:
                shutil.rmtree(wip_dir, ignore_errors=True)
            wip_pbo = pack_wip_food(tools, wip_dir)
        print("[3/4] Signing")
        if args.key:
            sign(tools, args.key, pbo, mod_dir)
            if map_pbo:
                sign(tools, args.key, map_pbo, map_dir)
            if wip_pbo:
                sign(tools, args.key, wip_pbo, out / WIP_MOD)
        else:
            print("  skipped (no --key). Servers with verifySignatures = 2 need a signed PBO.")
    print("[4/4] Server folder")
    vanilla = find_vanilla(args.vanilla_mission)
    print(f"  vanilla mission: {vanilla or 'not found'}")
    factors = dict(DIFFICULTY[args.difficulty])
    if not args.vanilla_loot:
        density, points, vanilla_points = loot_density()
        factors["loot"] = round(factors["loot"] * min(1.0, max(0.3, density)), 2)
        print(f"  loot points: {points:,} ({density:.0%} of Chernarus's {vanilla_points:,}); loot scaled to match")
    for k in factors:
        if getattr(args, k) is not None:
            factors[k] = getattr(args, k)
    print(f"  difficulty {args.difficulty}: " + ", ".join(f"{k} x{v}" for k, v in factors.items()))
    mods = {m for m in ("traders", "expansion", "traderplus") if getattr(args, m)}
    if mods:
        mods.add("traders")
        print("  mod support: " + ", ".join(sorted(mods)))
    warnings = build_server(out, mod_dir, vanilla, args.spawners, factors, mods, map_dir,
                            setpieces=not args.setpieces_in_wrp)

    if args.zip and not DRY:
        for name, src in (("Aotearoa_mod", mod_dir), ("AotearoaMap_mod", out / MAPITEM_MOD),
                          ("Aotearoa_server", out / "server")):
            if src.exists():
                shutil.make_archive(str(out / name), "zip", src.parent, src.name)
                print(f"  wrote {out / (name + '.zip')}")
    print()
    for w in warnings:
        print("NOTE: " + w)
    print(f"Done. Output in {out}")


if __name__ == "__main__":
    main()
