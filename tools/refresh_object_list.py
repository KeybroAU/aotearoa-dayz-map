"""Rebuild tools/dayz_classes.txt and tools/dayz_models.txt from Sam's DayZ Object Finder.

    python refresh_object_list.py [--json dayz_objects.json]

Downloads https://samsobjectfinder.com/data/dayz_objects.json (about 20 MB) unless --json points at a copy.
check_map.py uses the two lists to make sure every spawner class and Terrain Builder template exists in DayZ.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

URL = "https://samsobjectfinder.com/data/dayz_objects.json"
TOOLS = Path(__file__).resolve().parent
CLASSES = TOOLS / "dayz_classes.txt"
MODELS = TOOLS / "dayz_models.txt"
NOTE = "# Base game plus Livonia, Sakhal and Takistan. Refresh with tools/refresh_object_list.py.\n"


def template(cls: str) -> str:
    for prefix in ("Land_", "StaticObj_"):
        if cls.startswith(prefix):
            return cls[len(prefix):].lower()
    return cls.lower()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    if args.json:
        data = json.loads(args.json.read_text(encoding="utf-8"))
    else:
        req = urllib.request.Request(URL, headers={"User-Agent": "aotearoa-dayz-map"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.load(r)
    classes = sorted({o["objectName"] for o in data if o.get("modelType") == "Config"})
    models = {o["objectName"][:-4].lower() for o in data if o["objectName"].lower().endswith(".p3d")}
    models |= {template(c) for c in classes}
    CLASSES.write_text(f"# From Sam's DayZ Object Finder ({URL}), config class names.\n" + NOTE
                       + "\n".join(classes) + "\n", encoding="utf-8")
    MODELS.write_text(f"# From Sam's DayZ Object Finder ({URL}), model (p3d) names, for Terrain Builder templates.\n"
                      + NOTE + "\n".join(sorted(models)) + "\n", encoding="utf-8")
    print(f"{len(classes)} classes, {len(models)} models")


if __name__ == "__main__":
    main()
