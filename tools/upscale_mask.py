"""Upscale source/mask_4096.png to the 25600 mask Terrain Builder wants, without regenerating.

    python upscale_mask.py [size]
"""

import sys

import numpy as np
from PIL import Image

import generate_terrain as g


def main() -> None:
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 25600
    rgb = np.asarray(Image.open(g.SOURCE_DIR / "mask_4096.png").convert("RGB")).astype(int)
    lut = np.array([s[1] for s in g.SURFACES])
    idx = np.argmin(((rgb[..., None, :] - lut[None, None]) ** 2).sum(-1), axis=-1).astype(np.uint8)
    path = g.SOURCE_DIR / f"mask_{size}.png"
    Image.fromarray(g.mask_to_rgb(g.upscale_mask(idx, size))).save(path)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
