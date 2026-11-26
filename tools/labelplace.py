"""Map label placement that keeps names from overlapping each other, symbols and the image edge.

Each label is tried at several positions round its point (right, left, above, below, then the
diagonals, then further out); the first position clear of everything placed so far wins, or the least
crowded one if none is clear. Place the most important labels first.
"""

from __future__ import annotations

from PIL import ImageDraw, ImageFont

Line = tuple[str, ImageFont.ImageFont, tuple]  # text, font, fill


class Placer:
    def __init__(self, draw: ImageDraw.ImageDraw, size: tuple[int, int], pad: float = 2.0, stroke: int = 2):
        self.d, self.size, self.pad, self.stroke = draw, size, pad, stroke
        self.boxes: list[tuple[float, float, float, float]] = []
        self.symbols: list[tuple[float, float, float, float]] = []
        self.forced: list[str] = []
        self.dropped: list[str] = []

    def reserve(self, box: tuple[float, float, float, float]) -> None:
        """Keep labels off a symbol or other drawn feature (a label over a symbol costs a tenth of one over a label)."""
        self.symbols.append(box)

    def _parts(self, lines: list[Line], x: float, y: float, align: str, valign: str, gap: float = 1.0) -> list:
        heights = []
        for text, f, _ in lines:
            b = self.d.textbbox((0, 0), text, font=f, anchor="la", stroke_width=self.stroke)
            heights.append(b[3] - b[1])
        total = sum(heights) + gap * (len(lines) - 1)
        top = {"top": y, "middle": y - total / 2, "bottom": y - total}[valign]
        anchor = {"left": "la", "right": "ra", "centre": "ma"}[align]
        parts = []
        for (text, f, fill), h in zip(lines, heights):
            parts.append((text, f, fill, (x, top), anchor))
            top += h + gap
        return parts

    def candidates(self, lines: list[Line], x: float, y: float, r: float, gap: float) -> list[list]:
        out = []
        for step in (1.0, 2.2, 3.5):
            g = gap * step
            dd = (r + g) * 0.72
            out += [self._parts(lines, x + r + g, y, "left", "middle"),
                    self._parts(lines, x - r - g, y, "right", "middle"),
                    self._parts(lines, x, y - r - g, "centre", "bottom"),
                    self._parts(lines, x, y + r + g, "centre", "top"),
                    self._parts(lines, x + dd, y - dd, "left", "bottom"),
                    self._parts(lines, x + dd, y + dd, "left", "top"),
                    self._parts(lines, x - dd, y - dd, "right", "bottom"),
                    self._parts(lines, x - dd, y + dd, "right", "top")]
        return out

    def _boxes(self, parts: list) -> list[tuple[float, float, float, float]]:
        p = self.pad
        out = []
        for text, f, _, xy, anchor in parts:
            b = self.d.textbbox(xy, text, font=f, anchor=anchor, stroke_width=self.stroke)
            out.append((b[0] - p, b[1] - p, b[2] + p, b[3] + p))
        return out

    @staticmethod
    def _overlap(boxes, others) -> float:
        area = 0.0
        for b in boxes:
            for o in others:
                ix, iy = min(b[2], o[2]) - max(b[0], o[0]), min(b[3], o[3]) - max(b[1], o[1])
                if ix > 0 and iy > 0:
                    area += ix * iy
        return area

    def _cost(self, boxes) -> float:
        w, h = self.size
        outside = sum((max(0, -b[0]) + max(0, b[2] - w)) * (b[3] - b[1]) + (max(0, -b[1]) + max(0, b[3] - h)) * (b[2] - b[0])
                      for b in boxes)
        return outside * 40 + self._overlap(boxes, self.boxes) * 10 + self._overlap(boxes, self.symbols)

    def place(self, options: list[list], stroke: int | None = None, optional: bool = False, **text_kw) -> None:
        """Draw the first option (a list of parts) that overlaps nothing, else the least overlapping.
        An optional label with no clear spot is left off."""
        best, best_cost = None, None
        for parts in options:
            boxes = self._boxes(parts)
            cost = self._cost(boxes)
            if cost == 0:
                best = (parts, boxes)
                break
            if best_cost is None or cost < best_cost:
                best, best_cost = (parts, boxes), cost
        parts, boxes = best
        if best_cost and self._overlap(boxes, self.boxes):
            if optional:
                self.dropped.append(parts[0][0])
                return
            self.forced.append(parts[0][0])
        for text, f, fill, xy, anchor in parts:
            self.d.text(xy, text, font=f, anchor=anchor, fill=fill,
                        stroke_width=self.stroke if stroke is None else stroke, **text_kw)
        self.boxes += boxes

    def label(self, lines: list[Line], x: float, y: float, r: float = 0.0, gap: float = 4.0,
              first: list | None = None, stroke: int | None = None, optional: bool = False, **text_kw) -> None:
        options = ([first] if first else []) + self.candidates(lines, x, y, r, gap)
        self.place(options, stroke=stroke, optional=optional, **text_kw)
