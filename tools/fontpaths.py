"""The fonts every generator draws with, bundled in tools/fonts/ so the textures, maps and signs come
out the same on Windows, Linux and macOS (DejaVu: Bitstream Vera licence; Liberation: SIL OFL 1.1)."""

from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent / "fonts"


def path(name: str) -> str:
    return str(FONT_DIR / name)
