"""Repeated header/footer stripping (geometry-based).

Removes spans whose bounding box top edge falls within the top 10% of page
height, or whose bottom edge falls within the bottom 10% of page height, when
that span text (digits normalized to #) appears on >= 60% of all pages.
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


def repeated_boilerplate(pages: Sequence[RawPage]) -> set[str]:
    """Digit-normalized texts that qualify as repeated headers/footers."""
    if not pages:
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
    """Return new RawPages with repeated header/footer spans removed."""
    boilerplate = repeated_boilerplate(pages)
    if not boilerplate:
        return list(pages)
    stripped: list[RawPage] = []
    for page in pages:
        spans = [
            s
            for s in page.spans
            if not (
                _is_candidate(s.bbox, page.height)
                and normalize_text(s.text) in boilerplate
            )
        ]
        stripped.append(
            RawPage(
                number=page.number,
                width=page.width,
                height=page.height,
                spans=spans,
            )
        )
    return stripped

