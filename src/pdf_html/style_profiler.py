"""Document-wide style profiling.

Builds a character-weighted font-size histogram: the modal size is the body
size; larger tiers map to h1..h6 (tiers merged within ~0.5pt). Also records
the dominant body font family and color palette for CSS derivation.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from .ast import Span
from .extractor import RawPage

# Size tiers closer than this (in points) are merged into one heading level.
SIZE_TIER_MERGE_EPSILON_PT = 0.5

# Maximum number of heading levels emitted (h1..h6).
MAX_HEADING_LEVELS = 6

# Colors that account for less than this fraction of sampled characters are
# dropped from the palette (keeps CSS tight).
PALETTE_MIN_CHAR_FRACTION = 0.02

# Maximum palette size (most frequent colors first, black always kept if
# present).
PALETTE_MAX_COLORS = 6


@dataclass
class StyleProfile:
    """Typographic fingerprint of a document."""

    body_size: float = 0.0
    body_font: str = ""
    # Heading tiers strictly above body size, largest first; index 0 -> h1.
    heading_sizes: list[float] = field(default_factory=list)
    # Dominant non-trivial colors as sRGB ints, most frequent first.
    palette: list[int] = field(default_factory=list)

    def heading_level(self, size: float) -> int | None:
        """Map a font size to a heading level (1-based), or None if body-or-smaller."""
        for i, tier in enumerate(self.heading_sizes):
            if abs(size - tier) <= SIZE_TIER_MERGE_EPSILON_PT:
                return i + 1
        return None


def _size_histogram(pages: Sequence[RawPage]) -> Counter[float]:
    """Character-count-weighted histogram of font sizes, rounded to 0.1pt."""
    hist: Counter[float] = Counter()
    for page in pages:
        for span in page.spans:
            hist[round(span.style.size, 1)] += max(len(span.text.strip()), 1)
    return hist


def _merge_tiers(sizes: Sequence[float]) -> list[float]:
    """Merge sizes within SIZE_TIER_MERGE_EPSILON_PT into single tiers.

    Comparison is against the smallest member absorbed into the current
    tier (not the tier's first/largest member), so a run like 16.4, 16.0
    stays one tier while a genuinely smaller size starts a new one.
    """
    tiers: list[float] = []
    floor: list[float] = []
    for size in sorted(sizes, reverse=True):
        if floor and floor[-1] - size <= SIZE_TIER_MERGE_EPSILON_PT:
            floor[-1] = size  # extend the current tier downward
            continue
        tiers.append(size)
        floor.append(size)
    return tiers


def profile_styles(pages: Sequence[RawPage]) -> StyleProfile:
    """Profile the document: body size, heading tiers, body font, palette."""
    spans: list[Span] = [s for page in pages for s in page.spans]
    if not spans:
        return StyleProfile()

    hist = _size_histogram(pages)
    body_size = hist.most_common(1)[0][0]
    heading_sizes = _merge_tiers(
        [size for size in hist if size > body_size + SIZE_TIER_MERGE_EPSILON_PT]
    )[:MAX_HEADING_LEVELS]

    # Dominant font among body-sized text.
    font_counts: Counter[str] = Counter()
    for span in spans:
        if abs(round(span.style.size, 1) - body_size) <= SIZE_TIER_MERGE_EPSILON_PT:
            font_counts[span.style.font] += max(len(span.text.strip()), 1)
    body_font = font_counts.most_common(1)[0][0] if font_counts else ""

    # Color palette across all text, dropping rare colors.
    color_counts: Counter[int] = Counter()
    total_chars = 0
    for span in spans:
        weight = max(len(span.text.strip()), 1)
        color_counts[span.style.color & 0xFFFFFF] += weight
        total_chars += weight
    min_count = max(1, int(total_chars * PALETTE_MIN_CHAR_FRACTION))
    palette = [
        color
        for color, count in color_counts.most_common()
        if count >= min_count
    ][:PALETTE_MAX_COLORS]

    return StyleProfile(
        body_size=body_size,
        body_font=body_font,
        heading_sizes=heading_sizes,
        palette=palette,
    )

