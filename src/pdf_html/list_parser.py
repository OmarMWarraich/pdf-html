"""Nested list parsing.

Nesting is indent-based (x-offset of the text bbox relative to the marker);
glyph style only chooses ul vs ol per level. Markers are stripped and item
text stays verbatim.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from .ast import Block, ListBlock, ListItem, Paragraph, Span

# Bullet glyphs, decimal/alpha/roman enumerations. Broad on purpose: the
# geometric indent (handled here) — not the glyph — decides nesting.
LIST_MARKER = re.compile(
    r"^\s*(?P<marker>"
    r"[•◦▪·–—\-*o]"
    r"|\d{1,3}[.)]"
    r"|[a-zA-Z][.)]"
    r"|[ivxlIVXL]+[.)]"
    r")\s+"
)

_ORDERED_MARKER = re.compile(r"^\s*(\d{1,3}[.)]|[a-zA-Z][.)]|[ivxlIVXL]+[.)])\s*$")

# Indents within this many points are treated as the same nesting level.
INDENT_TOLERANCE_PT = 6.0


def is_list_item(text: str) -> bool:
    """True when *text* begins with a recognized list marker."""
    return LIST_MARKER.match(text) is not None


def marker_is_ordered(marker: str) -> bool:
    """True when the marker implies an ordered list (1. / a) / iv.)."""
    return _ORDERED_MARKER.match(marker) is not None


def strip_marker(runs: list[Span], marker: str) -> None:
    """Remove *marker* (plus following whitespace) from the run texts, in place.

    Text content other than the marker stays verbatim.
    """
    remaining = len(marker)
    idx = 0
    while idx < len(runs) and remaining > 0:
        text = runs[idx].text
        if len(text) <= remaining:
            remaining -= len(text)
            runs.pop(idx)
        else:
            runs[idx] = Span(
                text=text[remaining:], bbox=runs[idx].bbox, style=runs[idx].style,
                direction=runs[idx].direction,
            )
            remaining = 0
    # Also drop leading whitespace left after the marker.
    if runs:
        first = runs[0]
        stripped = first.text.lstrip()
        if stripped != first.text:
            runs[0] = Span(
                text=stripped, bbox=first.bbox, style=first.style,
                direction=first.direction,
            )


def _item_indent(para: Paragraph) -> float:
    """Left edge of the item text (after marker stripping)."""
    return min(r.bbox[0] for r in para.runs)


def parse_lists(blocks: Sequence[Block]) -> list[Block]:
    """Fold consecutive list-marked Paragraphs into (nested) ListBlocks.

    Nesting is inferred from the x-indent of each item's text bbox relative
    to the previous items; glyph style only decides ul vs ol per level.
    """
    out: list[Block] = []
    i = 0
    while i < len(blocks):
        block = blocks[i]
        if not (isinstance(block, Paragraph) and block.align == "list"):
            out.append(block)
            i += 1
            continue

        # Collect the consecutive run of list paragraphs with the same
        # marker style; a bullet->numbered switch starts a new block.
        j = i
        group: list[Paragraph] = []
        group_ordered: bool | None = None
        while j < len(blocks):
            nxt = blocks[j]
            if not (isinstance(nxt, Paragraph) and nxt.align == "list"):
                break
            ordered = (
                marker_is_ordered(_marker_text(nxt)) if nxt.runs else False
            )
            if group_ordered is None:
                group_ordered = ordered
            indent = _item_indent(nxt)
            # A marker-style change at the same indent ends the block;
            # deeper/shallower indents stay (nested items may switch style).
            if ordered != group_ordered and group and abs(indent - _item_indent(group[0])) <= INDENT_TOLERANCE_PT:
                break
            group.append(nxt)
            j += 1
        out.append(_build_list(group))
        i = j
    return out


def _marker_text(para: Paragraph) -> str:
    """Return the marker recorded on the Paragraph at classification time."""
    return getattr(para, "marker", "")


def _build_list(group: Sequence[Paragraph]) -> ListBlock:
    """Build a nested ListBlock from a flat run of list paragraphs."""
    # Indent levels: distinct left edges, sorted, merged within tolerance.
    edges = sorted({_item_indent(p) for p in group})
    levels: list[float] = []
    for edge in edges:
        if not levels or edge - levels[-1] > INDENT_TOLERANCE_PT:
            levels.append(edge)

    def level_of(para: Paragraph) -> int:
        x = _item_indent(para)
        level = 0
        for k, edge in enumerate(levels):
            if x >= edge - INDENT_TOLERANCE_PT:
                level = k
        return level

    first = group[0]
    ordered = marker_is_ordered(_marker_text(first)) if first.runs else False
    root = ListBlock(ordered=ordered)
    # Stack of (level, ListItem whose `items` collects deeper children).
    stack: list[tuple[int, ListItem]] = []
    for para in group:
        item = ListItem(runs=list(para.runs))
        level = level_of(para)
        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack:
            stack[-1][1].items.append(item)
        else:
            root.items.append(item)
        stack.append((level, item))
    return root

