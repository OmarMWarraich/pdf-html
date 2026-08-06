"""Reading order and column detection.

Splits pages into columns via x-coordinate gap clustering on span bounding
boxes and orders blocks column-by-column (left column top-to-bottom, then
the next column).
"""

from __future__ import annotations

from collections.abc import Sequence

from .ast import BBox, Span
from .extractor import RawPage

# A vertical gap between span clusters wider than this fraction of the page
# width is treated as a column boundary.
MIN_COLUMN_GAP_FRACTION = 0.02

# Rounds for clustering span x0/x1 edges so tiny jitter does not split
# a column edge into singletons.
EDGE_ROUNDING_PT = 1.0

# Maximum gap between consecutive spans on the same visual line, as a
# multiple of the median span size on that page.
SAME_LINE_Y_TOLERANCE = 0.5


def _column_edges(spans: Sequence[Span], page_width: float) -> list[float]:
    """Cluster span x-edges into column boundaries, sorted left to right.

    Returns the x0 of each column (the split points). A single-column page
    returns a one-element list containing the leftmost span edge.
    """
    if not spans:
        return [0.0]
    min_gap = max(page_width * MIN_COLUMN_GAP_FRACTION, 12.0)
    # Collect covered x-intervals, merging overlaps.
    intervals = sorted(
        (round(s.bbox[0] / EDGE_ROUNDING_PT), round(s.bbox[2] / EDGE_ROUNDING_PT))
        for s in spans
    )
    merged: list[list[float]] = [[intervals[0][0], intervals[0][1]]]
    for x0, x1 in intervals[1:]:
        if x0 - merged[-1][1] <= min_gap:
            merged[-1][1] = max(merged[-1][1], x1)
        else:
            merged.append([x0, x1])
    return [m[0] for m in merged]


def _column_of(bbox: BBox, edges: Sequence[float]) -> int:
    """Index of the column whose left edge starts at or before bbox.x0."""
    x0 = bbox[0]
    idx = 0
    for i, edge in enumerate(edges):
        if edge <= x0 + EDGE_ROUNDING_PT:
            idx = i
        else:
            break
    return idx


def order_spans(page: RawPage) -> list[Span]:
    """Return spans in reading order: column-major, then top-to-bottom.

    Within a column, spans are sorted by vertical position; spans sharing a
    line (y overlap within tolerance) are ordered left to right.
    """
    if not page.spans:
        return []
    edges = _column_edges(page.spans, page.width)

    def key(span: Span) -> tuple[int, float, float]:
        col = _column_of(span.bbox, edges)
        x0, y0, _, _ = span.bbox
        return (col, round(y0, 1), x0)

    return sorted(page.spans, key=key)


def order_pages_spans(pages: Sequence[RawPage]) -> list[list[Span]]:
    """Apply order_spans to every page, preserving page order."""
    return [order_spans(p) for p in pages]

