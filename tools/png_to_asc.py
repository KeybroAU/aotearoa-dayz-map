"""Convert source/heightmap_4096.png back to an ESRI ASCII grid for Terrain Builder.

Needs only numpy and Pillow, and no network:  python png_to_asc.py [output.asc]
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

SOURCE_DIR = Path(__file__).resolve().parent.parent / "source"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else SOURCE_DIR / "heightmap_4096.asc"
    meta = json.loads((SOURCE_DIR / "heightmap.json").read_text())
    raw = np.asarray(Image.open(SOURCE_DIR / "heightmap_4096.png")).astype(np.float64)
    h = meta["png_black_m"] + raw / 65535.0 * (meta["png_white_m"] - meta["png_black_m"])
    with out.open("w", newline="\n") as f:
        f.write(f"ncols {h.shape[1]}\nnrows {h.shape[0]}\nxllcorner {meta['easting']}\n"
                f"yllcorner {meta['northing']}\ncellsize {meta['cell_size_m']:g}\nNODATA_value -9999\n")
        for row in h:
            f.write(" ".join(f"{v:.2f}" for v in row))
            f.write("\n")
    print(f"Wrote {out} ({h.min():.1f} .. {h.max():.1f} m)")


if __name__ == "__main__":
    main()
