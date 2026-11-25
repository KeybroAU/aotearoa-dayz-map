"""Check every model the map uses against a listing of your P: drive.

Make the listing on the Windows machine with the DayZ Tools P: drive mounted:

    dir /s /b P:\\DZ\\*.p3d > models.txt

(or, from PowerShell: Get-ChildItem P:\\DZ -Recurse -Filter *.p3d | % FullName > models.txt)

then run

    python check_models.py models.txt

It reads the Terrain Builder files in source/objects/ and the object spawners, matches each
template or Land_ class to a .p3d of the same name, and lists the ones it can't find with the
closest names on your drive. --fix writes source/model_fixes.json with the best guesses, which
you can review and then apply with --apply.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from collections import Counter
from pathlib import Path

MAP_DIR = Path(__file__).resolve().parents[1]
OBJECTS_DIR = MAP_DIR / "source" / "objects"
FIXES = MAP_DIR / "source" / "model_fixes.json"
SKIP = {"aotearoa_water_50"}  # shipped with the mod, not on the P: drive


def model_key(name: str) -> str:
    name = name.strip().strip('"')
    return name[5:].lower() if name.lower().startswith("land_") else name.lower()


def used_models() -> Counter:
    used: Counter = Counter()
    for f in sorted(OBJECTS_DIR.glob("*_tb.txt")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                used[model_key(line.split(";", 1)[0])] += 1
    for f in sorted(OBJECTS_DIR.glob("*_spawner.json")):
        for obj in json.loads(f.read_text(encoding="utf-8")).get("Objects", []):
            used[model_key(obj["name"])] += 1
    return used


def drive_models(listing: Path) -> dict[str, str]:
    text = listing.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            lines = text.decode(enc).splitlines()
            break
        except UnicodeDecodeError:
            continue
    out = {}
    for line in lines:
        line = line.strip()
        if line.lower().endswith(".p3d"):
            stem = re.split(r"[\\/]", line)[-1][:-4].lower()
            out.setdefault(stem, line)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("listing", type=Path, help="text file of .p3d paths from your P: drive")
    ap.add_argument("--fix", action="store_true", help="write source/model_fixes.json with the best matches")
    ap.add_argument("--apply", action="store_true", help="rewrite source/objects/ using source/model_fixes.json")
    args = ap.parse_args()

    if args.apply:
        apply_fixes()
        return
    drive = drive_models(args.listing)
    if not drive:
        raise SystemExit(f"No .p3d paths in {args.listing}")
    used = used_models()
    missing = {m: n for m, n in used.items() if m not in drive and m not in SKIP}
    print(f"{len(drive)} models on the drive, {len(used)} used by the map, {len(missing)} not found\n")
    names = list(drive)
    fixes = {}
    for m, n in sorted(missing.items(), key=lambda kv: -kv[1]):
        close = difflib.get_close_matches(m, names, n=3, cutoff=0.6)
        print(f"  {m}  ({n} placed)")
        for c in close:
            print(f"      maybe {c}   {drive[c]}")
        if close:
            fixes[m] = close[0]
    if args.fix:
        FIXES.write_text(json.dumps(fixes, indent=1) + "\n")
        print(f"\nWrote {FIXES} ({len(fixes)} guesses). Check it, then run with --apply.")
    raise SystemExit(1 if missing else 0)


def apply_fixes() -> None:
    fixes = json.loads(FIXES.read_text())
    changed = 0
    for f in sorted(OBJECTS_DIR.glob("*_tb.txt")):
        lines = f.read_text(encoding="utf-8").splitlines()
        out = []
        for line in lines:
            tpl, _, rest = line.partition(";")
            key = model_key(tpl)
            if key in fixes:
                line = f'"{fixes[key]}";{rest}'
                changed += 1
            out.append(line)
        f.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\r\n")
    for f in sorted(OBJECTS_DIR.glob("*_spawner.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for obj in data.get("Objects", []):
            key = model_key(obj["name"])
            if key in fixes:
                obj["name"] = "Land_" + fixes[key][:1].upper() + fixes[key][1:]
                changed += 1
        f.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    print(f"Rewrote {changed} objects. Put the same names into the tables in tools/ so the next build keeps them.")


if __name__ == "__main__":
    main()
