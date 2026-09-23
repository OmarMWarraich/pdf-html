"""Repeated header/footer stripping (geometry-based).

Removes spans whose bounding box top edge falls within the top 10% of page
height, or whose bottom edge falls within the bottom 10% of page height, when
that span text (digits normalized to #) appears on >= 60% of all pages.

Also detects right-hand sidebars that contain legal boilerplate
(e.g. copyright notices) and removes them so they do not interleave with
main-column title/body text.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from .extractor import RawPage

# Vertical band at each page edge, as a fraction of page height, in which
# spans are header/footer candidates.
HEADER_FOOTER_PAGE_FRACTION = 0.10

# A candidate is stripped only when its digit-normalized text appears on at
# least this fraction of all pages.
MIN_PAGE_OCCURRENCE = 0.60

# Repetition is only meaningful when a document has more than one page;
# for a single page the ">= 60% of pages" rule would fire on real content
# (e.g. a report title sitting in the top band).
MIN_PAGES_FOR_STRIPPING = 2

# Fraction of page width considered the right-hand sidebar. Spans whose left
# edge sits to the right of (1 - RIGHT_SIDEBAR_FRACTION) * page_width are
# sidebar candidates.
RIGHT_SIDEBAR_FRACTION = 0.28

# Legal boilerplate triggers. If a right sidebar contains any of these,
# the whole sidebar is treated as page furniture.
_LEGAL_RE = re.compile(
    r"COPYRIGHT|ALL RIGHTS RESERVED|NO PART OF THIS|PUBLICATION MAY BE|"
    r"REPRODUCED|TRANSMITTED|PRIOR WRITTEN PERMISSION|INTERNAL REFERENCE CODE",
    re.IGNORECASE,
)

_DIGITS = re.compile(r"\d+")


def normalize_text(text: str) -> str:
    """Collapse whitespace and replace each digit run with # for comparison."""
    return _DIGITS.sub("#", " ".join(text.split()))


def _is_candidate(span_bbox: tuple[float, float, float, float], page_height: float) -> bool:
    """True when the bbox top edge is in the top band or the bottom edge is
    in the bottom band of the page."""
    band = page_height * HEADER_FOOTER_PAGE_FRACTION
    top_edge, bottom_edge = span_bbox[1], span_bbox[3]
    return top_edge <= band or bottom_edge >= page_height - band


def _legal_sidebar_spans(page: RawPage) -> set[int]:
    """Return the object ids of spans that form a right-hand legal sidebar.

    A legal sidebar is a cluster of spans in the right margin whose combined
    text matches legal boilerplate patterns. Removing these prevents copyright
    fragments from interleaving with the main title/body column.
    """
    threshold = page.width * (1 - RIGHT_SIDEBAR_FRACTION)
    sidebar = [s for s in page.spans if s.bbox[0] >= threshold]
    text = "".join(s.text for s in sidebar)
    if not _LEGAL_RE.search(text):
        return set()
    return {id(s) for s in sidebar}


def repeated_boilerplate(pages: Sequence[RawPage]) -> set[str]:
    """Digit-normalized texts that qualify as repeated headers/footers."""
    if len(pages) < MIN_PAGES_FOR_STRIPPING:
        return set()
    occurrences: dict[str, int] = {}
    for page in pages:
        seen_on_page: set[str] = set()
        for span in page.spans:
            if _is_candidate(span.bbox, page.height):
                seen_on_page.add(normalize_text(span.text))
        for text in seen_on_page:
            occurrences[text] = occurrences.get(text, 0) + 1
    threshold = MIN_PAGE_OCCURRENCE * len(pages)
    return {t for t, count in occurrences.items() if count >= threshold}


def strip_headers_footers(pages: Sequence[RawPage]) -> list[RawPage]:
    """Return new RawPages with repeated headers/footers and legal sidebars removed."""
    boilerplate = repeated_boilerplate(pages)
    stripped: list[RawPage] = []
    for page in pages:
        legal_sidebar = _legal_sidebar_spans(page)
        spans = []
        for s in page.spans:
            if id(s) in legal_sidebar:
                continue
            if (
                _is_candidate(s.bbox, page.height)
                and normalize_text(s.text) in boilerplate
            ):
                continue
            spans.append(s)
        stripped.append(
            RawPage(
                number=page.number,
                width=page.width,
                height=page.height,
                spans=spans,
                tables=page.tables,
            )
        )
    return stripped

