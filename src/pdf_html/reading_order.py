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


def _card_column_edges(spans: Sequence[Span], page_width: float) -> list[float]:
    """Detect card-style columns even when full-width body text exists.

    Looks at narrow spans (likely individual cards) and finds large gaps
    between their centers. Returns edges only when clear, wide gaps exist.
    """
    if not spans:
        return [0.0]
    # Focus on spans narrower than half the page; ignore full-width body text.
    centers = sorted(
        (s.bbox[0] + s.bbox[2]) / 2.0
        for s in spans
        if s.bbox[2] - s.bbox[0] < page_width * 0.45
    )
    if len(centers) < 2:
        return [0.0]

    # Find the median center-to-center gap; only gaps much larger than that
    # are treated as column boundaries.
    gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
    sorted_gaps = sorted(gaps)
    # Use the 80th percentile as the baseline so columns within a card are
    # clearly separated from gaps between cards.
    p80 = sorted_gaps[int(len(gaps) * 0.80)]
    threshold = max(p80 * 0.95, page_width * MIN_COLUMN_GAP_FRACTION * 2)

    split_indices = [i for i, g in enumerate(gaps) if g > threshold]
    if not split_indices:
        return [0.0]

    # Edges are midpoints between centers on either side of each large gap.
    edges: list[float] = [min(s.bbox[0] for s in spans)]
    for i in split_indices:
        edges.append((centers[i] + centers[i + 1]) / 2.0)
    return edges


def _column_of(bbox: BBox, edges: Sequence[float]) -> int:
    """Index of the column whose span center falls into.

    The center of the span is more reliable than x0 when columns are
    detected from narrow card content, because a card title may start near
    the left edge of the page but its center is clearly inside its column.
    """
    center = (bbox[0] + bbox[2]) / 2.0
    idx = 0
    for i, edge in enumerate(edges):
        if edge <= center + EDGE_ROUNDING_PT:
            idx = i
        else:
            break
    return idx


def order_spans(page: RawPage, *, single_column: bool = False) -> list[Span]:
    """Return spans in reading order: column-major, then top-to-bottom.

    Within a column, spans are sorted by vertical position; spans sharing a
    line (y overlap within tolerance) are ordered left to right. With
    *single_column* the column detection is skipped entirely — used for
    narrow regions such as table cells where gaps never mean columns.
    """
    if not page.spans:
        return []
    if single_column:
        edges: list[float] = [0.0]
    else:
        edges = _column_edges(page.spans, page.width)
        # If the global column detector sees only one column but the page also
        # contains a card-style grid, fall back to card-based edges.
        if len(edges) == 1:
            card_edges = _card_column_edges(page.spans, page.width)
            if len(card_edges) > 1:
                edges = card_edges

    def key(span: Span) -> tuple[int, float, float]:
        col = _column_of(span.bbox, edges)
        x0, y0, _, _ = span.bbox
        return (col, round(y0, 1), x0)

    return sorted(page.spans, key=key)


def order_pages_spans(pages: Sequence[RawPage]) -> list[list[Span]]:
    """Apply order_spans to every page, preserving page order."""
    return [order_spans(p) for p in pages]

