"""Pack Aotearoa into a ready-to-use mod and server folder.

Run it on the Windows machine with DayZ Tools, after the world is exported from Terrain Builder
(world/aotearoa.wrp and data/layers/ exist):

    python pack_mod.py
    python pack_mod.py --key aotearoa --zip

It writes dist/:

    dist/@Aotearoa/                      the client and server mod: addons/aotearoa.pbo, mod.cpp, keys/
    dist/server/                         drop this into your DayZ Server folder:
        @Aotearoa/, keys/, serverDZ.cfg, start_server.bat, start_server.sh,
        mpmissions/dayzOffline.aotearoa/ vanilla Chernarus mission with every Aotearoa file
                                         copied over it and cfggameplay.json / cfgeconomycore.xml merged

Steps it runs:
  1. converts the branding images in data/branding/, the sign textures in data/signs/ and the model
     textures in data/models/ to .paa with ImageToPAA
  2. packs config.cpp, config/, data/, structures/ and world/ into aotearoa.pbo with Addon Builder (prefix maps\\aotearoa)
  3. with --key NAME, makes a signing key (once) and signs the PBO
  4. builds the server folder, merging the mission files into a copy of vanilla dayzOffline.chernarusplus

Options:
  --tools DIR             DayZ Tools folder (found from the registry or the Steam default if not given)
  --vanilla-mission DIR   vanilla mpmissions/dayzOffline.chernarusplus (found in the DayZ Server install if not given)
  --key NAME              sign with keys/NAME.biprivatekey, creating it if needed
  --spawners              also load the town and site buildings from object spawner files. Only for a quick
                          test on a world without the Terrain Builder objects; otherwise every building doubles.
  --difficulty LEVEL      easy, normal (default, vanilla amounts) or hard; scales loot, vehicles and infected
  --loot/--vehicles/--infected X   fine-tune one of those by a factor (overrides the difficulty for it)
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
PACKED = ["config.cpp", "$PBOPREFIX$", "config", "data", "structures", "world"]
# Spawner files that need a custom model before they can load.
MODEL_SPAWNERS = [("structures/sign_town/sign_town.p3d", "aotearoa/signs_spawner.json", "town name signs"),
                  ("structures/sign_post/sign_post.p3d", "aotearoa/roadsigns_spawner.json", "road signs")]
SKIP_IN_DATA = ["branding/art"]
COPY_DIRECT = "*.paa,*.rvmat,*.wrp,*.png,*.jpg,*.shp,*.shx,*.dbf,*.cfg,*.hpp,*.txt"
BRANDING = [("logo_512.png", "logo_512_ca.paa"), ("icon_128.png", "icon_128_ca.paa"),
            ("icon_64.png", "icon_64_ca.paa"), ("loading_1.jpg", "loading_1_co.paa"),
            ("loading_2.jpg", "loading_2_co.paa"), ("map_picture.jpg", "map_picture_co.paa")]
STEAM_DIRS = [Path(r"C:\Program Files (x86)\Steam\steamapps\common"), Path(r"C:\Program Files\Steam\steamapps\common")]
MERGED_AWAY = ["cfggameplay.worldsdata.json", "cfgeconomycore.aotearoa.xml"]

# Factors on vanilla amounts: loot (types nominal/min), vehicles (events nominal/min/max), infected
# (Infected* events and ZombieMaxCount).
DIFFICULTY = {
    "easy": {"loot": 1.5, "vehicles": 1.5, "infected": 0.6},
    "normal": {"loot": 1.0, "vehicles": 1.0, "infected": 1.0},
    "hard": {"loot": 0.6, "vehicles": 0.6, "infected": 1.5},
}

DRY = False


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
    """Sign and model textures: cut-out post signs keep their alpha (_ca), the rest are colour maps (_co)."""
    exe = tool(tools, "ImageToPAA", "ImageToPAA.exe")
    jobs = [(p, "_co") for p in sorted((MAP_DIR / "data" / "signs").glob("sign_*.png"))]
    jobs += [(p, "_ca") for p in sorted((MAP_DIR / "data" / "signs").glob("post_*.png"))]
    jobs += [(p, "_co") for p in sorted((MAP_DIR / "data" / "models").glob("*.png"))]
    for png, suffix in jobs:
        run([exe, png, png.with_name(png.stem + suffix + ".paa")])
    print(f"  {len(jobs)} sign and model textures")


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


def build_mission(dest: Path, vanilla: Path | None, spawners: bool) -> list[str]:
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
    shutil.copytree(gen, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*MERGED_AWAY))

    extra = json.loads((gen / "cfggameplay.worldsdata.json").read_text(encoding="utf-8"))
    spawner_files = []
    for model, spawner, what in MODEL_SPAWNERS:
        if (MAP_DIR / model).exists():
            spawner_files.append(spawner)
        else:
            (dest / spawner).unlink(missing_ok=True)
            warnings.append(f"No {model}, so the {what} are left out. Make it from docs/models/ "
                            "(docs/CUSTOM_MODELS.md, item 2) and pack again.")
    if spawners:
        (dest / "aotearoa").mkdir(exist_ok=True)
        for f in ("towns_spawner.json", "pois_spawner.json"):
            shutil.copy2(MAP_DIR / "source" / "objects" / f, dest / "aotearoa" / f)
        spawner_files += ["aotearoa/towns_spawner.json", "aotearoa/pois_spawner.json"]
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
    if core.exists():
        text = core.read_text(encoding="utf-8")
        if 'folder="aotearoa_ce"' not in text:
            if "</economycore>" not in text:
                warnings.append("cfgeconomycore.xml has no </economycore>; add the aotearoa_ce block by hand.")
            else:
                indented = "\n".join("\t" + ln for ln in block.strip().splitlines())
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


def build_server(out: Path, mod_dir: Path, vanilla: Path | None, spawners: bool, factors: dict) -> list[str]:
    server = out / "server"
    print(f"  server folder {server}")
    if DRY:
        return []
    server.mkdir(parents=True, exist_ok=True)
    if mod_dir.exists():
        shutil.copytree(mod_dir, server / "@Aotearoa", dirs_exist_ok=True)
        if (mod_dir / "keys").exists():
            shutil.copytree(mod_dir / "keys", server / "keys", dirs_exist_ok=True)
    warnings = build_mission(server / "mpmissions" / MISSION, vanilla, spawners)
    for line in apply_difficulty(server / "mpmissions" / MISSION, factors):
        print(f"  {line}")
    if not mod_dir.exists():
        warnings.append("No dist/@Aotearoa yet, so the server folder has no mod. Run without --skip-pbo.")
    shutil.copy2(MAP_DIR / "mission" / "serverDZ.cfg", server / "serverDZ.cfg")
    shutil.copytree(MAP_DIR / "mission" / "server", server, dirs_exist_ok=True)
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
    ap.add_argument("--difficulty", choices=sorted(DIFFICULTY), default="normal")
    ap.add_argument("--loot", type=float)
    ap.add_argument("--vehicles", type=float)
    ap.add_argument("--infected", type=float)
    ap.add_argument("--skip-pbo", action="store_true")
    ap.add_argument("--zip", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    DRY = args.dry_run

    out = args.out
    mod_dir = out / "@Aotearoa"
    if not args.skip_pbo:
        tools = find_tools(args.tools)
        if tools is None:
            sys.exit("Can't find DayZ Tools. Pass --tools \"C:\\...\\DayZ Tools\".")
        print(f"DayZ Tools: {tools}")
        print("[1/4] Branding images and town signs to .paa")
        convert_branding(tools)
        convert_textures(tools)
        print("[2/4] Packing aotearoa.pbo")
        if not DRY:
            shutil.rmtree(mod_dir, ignore_errors=True)
        pbo = stage_and_pack(tools, mod_dir / "addons")
        if not DRY:
            shutil.copy2(MAP_DIR / "mod" / "mod.cpp", mod_dir / "mod.cpp")
        print("[3/4] Signing")
        if args.key:
            sign(tools, args.key, pbo, mod_dir)
        else:
            print("  skipped (no --key). Servers with verifySignatures = 2 need a signed PBO.")
    print("[4/4] Server folder")
    vanilla = find_vanilla(args.vanilla_mission)
    print(f"  vanilla mission: {vanilla or 'not found'}")
    factors = dict(DIFFICULTY[args.difficulty])
    for k in factors:
        if getattr(args, k) is not None:
            factors[k] = getattr(args, k)
    print(f"  difficulty {args.difficulty}: " + ", ".join(f"{k} x{v}" for k, v in factors.items()))
    warnings = build_server(out, mod_dir, vanilla, args.spawners, factors)

    if args.zip and not DRY:
        for name, src in (("Aotearoa_mod", mod_dir), ("Aotearoa_server", out / "server")):
            if src.exists():
                shutil.make_archive(str(out / name), "zip", src.parent, src.name)
                print(f"  wrote {out / (name + '.zip')}")
    print()
    for w in warnings:
        print("NOTE: " + w)
    print(f"Done. Output in {out}")


if __name__ == "__main__":
    main()
