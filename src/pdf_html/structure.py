"""Block classification from geometry and font cues.

Classifies lines/blocks as heading, list_item, table, callout, or paragraph,
and merges consecutive lines into paragraphs when size/font match and the
vertical gap stays below ~1.4x line height.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from .ast import Block, Heading, Paragraph, Span
from .extractor import RawPage
from .list_parser import LIST_MARKER, is_list_item, strip_marker
from .reading_order import order_spans
from .style_profiler import StyleProfile

# Lines whose vertical gap is below this multiple of the previous line
# height merge into the same paragraph.
PARAGRAPH_GAP_MULTIPLIER = 1.4

# A "short line" heading cue: at most this many characters.
HEADING_MAX_CHARS = 120

# Alignment cue tolerance (points) for comparing left/right edges.
ALIGN_TOLERANCE_PT = 6.0

# Within a single visual line, consecutive spans separated horizontally by
# more than this multiple of the line height are treated as separate lines.
# This prevents slide titles and right-aligned descriptions from merging.
SAME_LINE_HORIZONTAL_SPLIT_THRESHOLD = 2.0

# When merging lines into a paragraph, require that the next line horizontally
# overlap the accumulated paragraph by at least this fraction of the shorter
# of the two widths. This prevents side-by-side cards (e.g. slide grids) from
# collapsing into a single paragraph.
PARAGRAPH_HORIZONTAL_OVERLAP_FRACTION = 0.15


@dataclass
class Line:
    """Spans grouped onto one visual line."""

    spans: list[Span] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)

    @property
    def x0(self) -> float:
        return min(s.bbox[0] for s in self.spans)

    @property
    def y0(self) -> float:
        return min(s.bbox[1] for s in self.spans)

    @property
    def y1(self) -> float:
        return max(s.bbox[3] for s in self.spans)

    @property
    def x1(self) -> float:
        return max(s.bbox[2] for s in self.spans)

    @property
    def height(self) -> float:
        return max(self.y1 - self.y0, 1e-6)

    @property
    def max_size(self) -> float:
        return max(s.style.size for s in self.spans)

    @property
    def is_bold(self) -> bool:
        return all(s.style.bold for s in self.spans if s.text.strip())


def group_lines(spans: Sequence[Span]) -> list[Line]:
    """Group already-ordered spans into visual lines by y-overlap.

    Within a line, spans that are far apart horizontally are split into
    separate lines so that slide layouts (e.g. a title plus a right-aligned
    description) do not collapse into a single paragraph.
    """
    lines: list[Line] = []
    for span in spans:
        if (
            lines
            and abs(span.bbox[1] - lines[-1].y0) <= lines[-1].height * 0.5
        ):
            lines[-1].spans.append(span)
        else:
            lines.append(Line(spans=[span]))

    result: list[Line] = []
    for line in lines:
        line.spans.sort(key=lambda s: s.bbox[0])
        split_lines: list[Line] = [Line(spans=[line.spans[0]])]
        for span in line.spans[1:]:
            prev = split_lines[-1].spans[-1]
            gap = span.bbox[0] - prev.bbox[2]
            if gap > line.height * SAME_LINE_HORIZONTAL_SPLIT_THRESHOLD:
                split_lines.append(Line(spans=[span]))
            else:
                split_lines[-1].spans.append(span)
        result.extend(split_lines)
    return result


def is_heading(line: Line, profile: StyleProfile) -> int | None:
    """Return the heading level for *line*, or None.

    Primary cue: font-size tier above body. Reinforcing cues (bold, short
    line, no trailing period) are required so that a lone large glyph inside
    body text does not promote the whole line.
    """
    level = profile.heading_level(line.max_size)
    if level is None:
        return None
    text = line.text.strip()
    if not text or len(text) > HEADING_MAX_CHARS:
        return None
    if text.endswith(".") and len(text.split()) > 3:
        return None  # reads like a sentence, not a heading
    return level


def _paragraph_align(line: Line, page_width: float) -> str:
    """Best-effort alignment cue from the line's geometry."""
    left_gap = line.x0
    right_gap = page_width - line.x1
    if abs(left_gap - right_gap) <= ALIGN_TOLERANCE_PT * 4 and left_gap > ALIGN_TOLERANCE_PT * 2:
        return "center"
    if right_gap <= ALIGN_TOLERANCE_PT and left_gap > ALIGN_TOLERANCE_PT * 4:
        return "right"
    return "left"


def classify_page(page: RawPage, profile: StyleProfile) -> list[Block]:
    """Turn one page of raw spans into structured blocks.

    Headings, paragraphs, and list items are handled here; tables and
    callouts are detected by their own modules (planned). List items are
    emitted as Paragraph blocks marked by list_parser.parse_lists afterwards.
    """
    blocks: list[Block] = []
    lines = group_lines(order_spans(page))
    current: Paragraph | None = None

    def flush() -> None:
        nonlocal current
        if current is not None and any(r.text.strip() for r in current.runs):
            blocks.append(current)
        current = None

    prev_line: Line | None = None
    for line in lines:
        if not line.text.strip():
            prev_line = line
            continue

        level = is_heading(line, profile)
        if level is not None:
            flush()
            blocks.append(Heading(level=level, runs=list(line.spans)))
            prev_line = line
            continue

        if is_list_item(line.text):
            flush()
            marker = LIST_MARKER.match(line.text)
            assert marker is not None
            runs = list(line.spans)
            strip_marker(runs, marker.group(1))
            para = Paragraph(runs=runs)
            para.align = "list"  # resolved into ListBlocks by list_parser
            para.marker = marker.group(1)  # type: ignore[attr-defined]
            blocks.append(para)
            prev_line = line
            continue

        def _horizontal_overlap(a: Line, b: Line) -> float:
            """Overlap fraction relative to the shorter line width."""
            overlap = min(a.x1, b.x1) - max(a.x0, b.x0)
            short = min(a.x1 - a.x0, b.x1 - b.x0)
            return overlap / short if short > 0 else 0.0

        gap_ok = (
            prev_line is not None
            and (line.y0 - prev_line.y1) < prev_line.height * (PARAGRAPH_GAP_MULTIPLIER - 1.0) + prev_line.height * 0.4
        )
        same_style = (
            prev_line is not None
            and abs(line.max_size - prev_line.max_size) <= 0.5
        )
        if current is not None and gap_ok and same_style and _horizontal_overlap(prev_line, line) >= PARAGRAPH_HORIZONTAL_OVERLAP_FRACTION:
            current.runs.extend(line.spans)
        else:
            flush()
            current = Paragraph(runs=list(line.spans))
            current.align = _paragraph_align(line, page.width)
        prev_line = line

    flush()
    return blocks


def classify_document(
    pages: Sequence[RawPage], profile: StyleProfile
) -> list[list[Block]]:
    """Classify every page; list items are still flat Paragraphs at this point."""
    return [classify_page(page, profile) for page in pages]

