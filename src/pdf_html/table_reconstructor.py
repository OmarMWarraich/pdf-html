"""Table reconstruction.

Table regions are detected at extraction time (PyMuPDF Page.find_tables())
and carried on RawPage as TableRegion geometry. Here the page's spans are
assigned to cells by bbox, each cell runs the normal line/paragraph/list
pipeline scoped to its own width (headings suppressed), and the resulting
TableBlock is interleaved with the page's flow blocks at the table's
vertical position. Rows that continue across a page break (leading empty
first cell) are merged back into the previous page's trailing table.

A whitespace-gap heuristic fallback for the pdftotext extractor is planned.
"""

from __future__ import annotations

from collections.abc import Sequence

from .ast import (
    BBox,
    Block,
    ListBlock,
    Paragraph,
    Span,
    TableBlock,
    TableCell,
)
from .extractor import RawPage, TableRegion
from .list_parser import parse_lists
from .structure import classify_page
from .style_profiler import StyleProfile

# Tolerance (points) when testing whether a span center falls inside a table
# or cell bbox.
CELL_HIT_TOLERANCE_PT = 2.0


def _center(bbox: BBox) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _contains(bbox: BBox, x: float, y: float) -> bool:
    tol = CELL_HIT_TOLERANCE_PT
    return bbox[0] - tol <= x <= bbox[2] + tol and bbox[1] - tol <= y <= bbox[3] + tol


def _cell_index(region: TableRegion, x: float, y: float) -> tuple[int, int]:
    """Cell (row, col) containing point (x, y); nearest cell as fallback."""
    best: tuple[int, int] = (0, 0)
    best_dist = float("inf")
    for r, row in enumerate(region.rows):
        for c, cbbox in enumerate(row):
            if cbbox is None:
                continue
            if _contains(cbbox, x, y):
                return (r, c)
            mx, my = _center(cbbox)
            dist = (mx - x) ** 2 + (my - y) ** 2
            if dist < best_dist:
                best_dist = dist
                best = (r, c)
    return best


def _assign_spans(
    page: RawPage, regions: Sequence[TableRegion]
) -> tuple[list[Span], list[dict[tuple[int, int], list[Span]]]]:
    """Split page spans into flow spans and per-table {(row, col): spans}."""
    cell_spans: list[dict[tuple[int, int], list[Span]]] = [{} for _ in regions]
    flow: list[Span] = []
    for span in page.spans:
        cx, cy = _center(span.bbox)
        for idx, region in enumerate(regions):
            if _contains(region.bbox, cx, cy):
                cell_spans[idx].setdefault(_cell_index(region, cx, cy), []).append(span)
                break
        else:
            flow.append(span)
    return flow, cell_spans


def _flow_blocks(
    spans: list[Span], page: RawPage, profile: StyleProfile
) -> list[Block]:
    if not spans:
        return []
    synthetic = RawPage(
        number=page.number, width=page.width, height=page.height, spans=spans
    )
    return parse_lists(classify_page(synthetic, profile))


def _cell_blocks(
    spans: list[Span], cell_bbox: BBox, page: RawPage, profile: StyleProfile
) -> list[Block]:
    """Run the line/paragraph/list pipeline on one cell's spans.

    Spans are shifted to the cell origin so alignment cues use the cell
    width; heading tiers are suppressed — cell text is never a document
    heading, its size is still styled at render time via the runs.
    """
    if not spans:
        return []
    x0 = cell_bbox[0]
    shifted = [
        Span(
            text=s.text,
            bbox=(s.bbox[0] - x0, s.bbox[1], s.bbox[2] - x0, s.bbox[3]),
            style=s.style,
            direction=s.direction,
        )
        for s in spans
    ]
    synthetic = RawPage(
        number=page.number,
        width=cell_bbox[2] - cell_bbox[0],
        height=page.height,
        spans=shifted,
    )
    cell_profile = StyleProfile(
        body_size=profile.body_size,
        body_font=profile.body_font,
        heading_sizes=[],
        palette=profile.palette,
    )
    return parse_lists(classify_page(synthetic, cell_profile, single_column=True))


def _is_bold_cell(cell: TableCell) -> bool:
    """True when the cell holds only paragraphs whose text is entirely bold."""
    runs = []
    for block in cell.blocks:
        if not isinstance(block, Paragraph):
            return False
        runs.extend(block.runs)
    texted = [r for r in runs if r.text.strip()]
    return bool(texted) and all(r.style.bold for r in texted)


def _header_rows(region: TableRegion, rows: list[list[TableCell]]) -> int:
    """Keep the detector's header hint only when the row looks like one (bold)."""
    if region.header_rows < 1 or not rows:
        return 0
    non_empty = [cell for cell in rows[0] if cell.blocks]
    if not non_empty:
        return 0
    return 1 if all(_is_bold_cell(cell) for cell in non_empty) else 0


def _table_block(
    region: TableRegion,
    cell_spans: dict[tuple[int, int], list[Span]],
    page: RawPage,
    profile: StyleProfile,
) -> TableBlock:
    rows: list[list[TableCell]] = []
    for r, row in enumerate(region.rows):
        cells: list[TableCell] = []
        for c, cbbox in enumerate(row):
            spans = cell_spans.get((r, c), [])
            blocks = _cell_blocks(spans, cbbox, page, profile) if cbbox else []
            cells.append(TableCell(blocks=blocks))
        rows.append(cells)
    return TableBlock(rows=rows, header_rows=_header_rows(region, rows))


def reconstruct_page(page: RawPage, profile: StyleProfile) -> list[Block]:
    """Classify one page with table awareness.

    Tables become TableBlocks; the remaining spans go through the normal
    flow classification, segmented so blocks and tables keep document order.
    """
    regions = sorted(page.tables, key=lambda t: t.bbox[1])
    if not regions:
        return parse_lists(classify_page(page, profile))

    flow, cell_spans = _assign_spans(page, regions)
    # Segment flow spans by the table top edges so order is preserved.
    segments: list[list[Span]] = [[] for _ in range(len(regions) + 1)]
    for span in flow:
        cy = (span.bbox[1] + span.bbox[3]) / 2.0
        idx = next(
            (i for i, r in enumerate(regions) if cy < r.bbox[1]), len(regions)
        )
        segments[idx].append(span)

    blocks: list[Block] = []
    for i, region in enumerate(regions):
        blocks.extend(_flow_blocks(segments[i], page, profile))
        table = _table_block(region, cell_spans[i], page, profile)
        if any(cell.blocks for row in table.rows for cell in row):
            blocks.append(table)
    blocks.extend(_flow_blocks(segments[-1], page, profile))
    return blocks


def merge_continuation_tables(pages_blocks: list[list[Block]]) -> None:
    """Merge cross-page table fragments into the previous table, in place.

    A fragment is a table that opens a page with an empty first cell and the
    same column count as the table that closed the previous page — the
    signature of a row that continues across the page break.
    """
    prev: TableBlock | None = None
    for blocks in pages_blocks:
        first = blocks[0] if blocks else None
        if (
            prev is not None
            and isinstance(first, TableBlock)
            and first.rows
            and prev.rows
            and len(first.rows[0]) == len(prev.rows[-1])
            and not first.rows[0][0].blocks
        ):
            _merge_row(prev.rows[-1], first.rows[0])
            prev.rows.extend(first.rows[1:])
            blocks.pop(0)
        last = blocks[-1] if blocks else None
        prev = last if isinstance(last, TableBlock) else None


def _merge_row(target: list[TableCell], fragment: list[TableCell]) -> None:
    for tcell, fcell in zip(target, fragment, strict=True):
        incoming = list(fcell.blocks)
        # A continuation usually resumes mid list item: fold a leading plain
        # paragraph into the deepest trailing item of a trailing list.
        if (
            incoming
            and tcell.blocks
            and isinstance(tcell.blocks[-1], ListBlock)
            and isinstance(incoming[0], Paragraph)
            and tcell.blocks[-1].items
        ):
            item = tcell.blocks[-1].items[-1]
            while item.items:
                item = item.items[-1]
            item.runs.extend(incoming.pop(0).runs)
        tcell.blocks.extend(incoming)
