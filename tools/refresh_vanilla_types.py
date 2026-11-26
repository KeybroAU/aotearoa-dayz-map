"""Copy the vanilla types.xml entries that economy.NZ_TYPES changes and nz_food.ITEMS retexture into tools/vanilla_types.xml.

    python refresh_vanilla_types.py [--xml path/to/types.xml]

Downloads Bohemia's Chernarus types.xml from GitHub unless --xml points at a copy (for example
mpmissions/dayzOffline.chernarusplus/db/types.xml from the server). Run it after a DayZ update.
"""

from __future__ import annotations

import argparse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import economy
import nz_food

URL = ("https://raw.githubusercontent.com/BohemiaInteractive/DayZ-Central-Economy/master/"
       "dayzOffline.chernarusplus/db/types.xml")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml", type=Path)
    args = ap.parse_args()
    if args.xml:
        text = args.xml.read_text(encoding="utf-8")
    else:
        with urllib.request.urlopen(URL, timeout=60) as r:
            text = r.read().decode("utf-8")
    vanilla = {e.get("name"): e for e in ET.fromstring(text).iter("type")}
    names = set(economy.NZ_TYPES) | set(nz_food.replaced())
    missing = sorted(names - set(vanilla))
    if missing:
        raise SystemExit(f"Not in vanilla types.xml: {', '.join(missing)}")
    root = ET.Element("types")
    for name in sorted(names):
        root.append(vanilla[name])
    ET.indent(root, space="    ")
    economy.VANILLA_TYPES.write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
        f"<!-- The vanilla entries tools/economy.py changes, from {URL}.\n"
        "     Rebuild with tools/refresh_vanilla_types.py. -->\n" + ET.tostring(root, encoding="unicode") + "\n",
        encoding="utf-8")
    print(f"Wrote {economy.VANILLA_TYPES}: {len(names)} entries")


if __name__ == "__main__":
    main()
