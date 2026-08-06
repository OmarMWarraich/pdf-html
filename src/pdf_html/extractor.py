"""Layout-aware text extraction.

Defines the TextExtractor ABC (extension point) and the default
PyMuPDFExtractor, which uses page.get_text("dict") to capture per-span
size/flags/color/bbox. A dependency-free pdftotext fallback is planned.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pymupdf

from .ast import BBox, Page, Span, SpanStyle

if TYPE_CHECKING:
    from .ast import Document

# Spans whose text is a run of single letters separated by whitespace are
# usually decorative glyphs (e.g. titles with extra letter spacing). Collapse
# those artificial spaces back into words when at least this many consecutive
# single-letter tokens appear.
SPACED_GLYPH_MIN_TOKENS = 5

# When a span looks like decorative spaced glyphs, a gap between surrounding
# non-whitespace characters larger than this fraction of the font size is
# treated as a word boundary; smaller gaps have their space collapsed.
SPACED_GLYPH_WORD_GAP_THRESHOLD = 0.35

# PyMuPDF span flag bits (see pymupdf docs for TEXT_FONT_* constants).
FLAG_SUPERSCRIPT = 1
FLAG_ITALIC = 2
FLAG_SERIF = 4
FLAG_MONO = 8
FLAG_BOLD = 16


@dataclass
class RawPage:
    """Spans extracted from one page, before reading-order analysis."""

    number: int  # 1-based
    width: float
    height: float
    spans: list[Span] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Result of extracting an entire PDF."""

    title: str
    pages: list[RawPage] = field(default_factory=list)
    scanned_pages: list[int] = field(default_factory=list)  # 1-based

    @property
    def is_scanned(self) -> bool:
        """True when every page lacks extractable text spans."""
        return bool(self.pages) and len(self.scanned_pages) == len(self.pages)


class TextExtractor(ABC):
    """Extension point: turn a PDF into per-page spans with style metadata."""

    @abstractmethod
    def extract(self, pdf_path: str) -> ExtractionResult:
        """Extract spans from *pdf_path*; images are never included."""


def style_from_flags(
    flags: int, *, font: str, size: float, color: int
) -> SpanStyle:
    """Build a SpanStyle from a PyMuPDF span flags bitmask."""
    return SpanStyle(
        font=font,
        size=size,
        bold=bool(flags & FLAG_BOLD),
        italic=bool(flags & FLAG_ITALIC),
        mono=bool(flags & FLAG_MONO),
        serif=bool(flags & FLAG_SERIF),
        superscript=bool(flags & FLAG_SUPERSCRIPT),
        color=color,
    )


def _overlaps_any(bbox: BBox, rects: list[pymupdf.Rect]) -> bool:
    """True when *bbox* intersects any rect in *rects*."""
    rect = pymupdf.Rect(bbox)
    return any(rect.intersects(r) for r in rects)


def _looks_spaced_glyphs(text: str) -> bool:
    """True when *text* looks like decorative single-glyph spacing."""
    min_repeats = SPACED_GLYPH_MIN_TOKENS - 1
    pattern = re.compile(r"\w(?:\s+\w){" + str(min_repeats) + r",}")
    return bool(pattern.search(text))


def _span_text_from_chars(chars: list[dict], size: float) -> str:
    """Build span text from raw character dicts.

    Decorative headings sometimes store each glyph with explicit spaces. When
    a span matches the spaced-glyph pattern, collapse artificial spaces whose
    surrounding non-whitespace characters are close together, and preserve
    larger gaps as word boundaries.
    """
    if not chars:
        return ""

    raw_text = "".join(c["c"] for c in chars)
    if not _looks_spaced_glyphs(raw_text):
        return raw_text

    threshold = size * SPACED_GLYPH_WORD_GAP_THRESHOLD
    parts: list[str] = []
    for i, char_info in enumerate(chars):
        char = char_info["c"]
        if char.strip() == "":
            prev_idx = next(
                (j for j in range(i - 1, -1, -1) if chars[j]["c"].strip()), None
            )
            next_idx = next(
                (j for j in range(i + 1, len(chars)) if chars[j]["c"].strip()), None
            )
            if prev_idx is None or next_idx is None:
                parts.append(char)
                continue
            prev_char = chars[prev_idx]["c"]
            next_char = chars[next_idx]["c"]
            if not (prev_char.isalnum() and next_char.isalnum()):
                parts.append(" ")
                continue
            gap = chars[next_idx]["bbox"][0] - chars[prev_idx]["bbox"][2]
            if gap > threshold:
                parts.append(" ")
            # else: collapse the artificial space
        else:
            parts.append(char)
    return "".join(parts)


class PyMuPDFExtractor(TextExtractor):
    """Default extractor: page.get_text("rawdict") -> spans with style metadata."""

    def extract(self, pdf_path: str) -> ExtractionResult:
        result = ExtractionResult(title="")
        with pymupdf.open(pdf_path) as doc:
            assert doc.metadata is not None
            result.title = doc.metadata.get("title", "") or ""
            for page in doc:
                image_rects = self._image_rects(page)
                spans = self._page_spans(page, image_rects)
                number = page.number + 1 # type: ignore
                if not spans:
                    result.scanned_pages.append(number)
                result.pages.append(
                    RawPage(
                        number=number,
                        width=page.rect.width,
                        height=page.rect.height,
                        spans=spans,
                    )
                )
        return result

    @staticmethod
    def _image_rects(page: pymupdf.Page) -> list[pymupdf.Rect]:
        rects: list[pymupdf.Rect] = []
        for img in page.get_images(full=True):
            rects.extend(page.get_image_rects(img[0]))
        return rects

    @staticmethod
    def _page_spans(
        page: pymupdf.Page, image_rects: list[pymupdf.Rect]
    ) -> list[Span]:
        spans: list[Span] = []
        text_page: dict = page.get_text("rawdict")  # type: ignore[assignment]
        for block in text_page.get("blocks", []):
            if block.get("type") != 0:  # 0 = text; 1 = image (dropped)
                continue
            for line in block.get("lines", []):
                direction = tuple(line.get("dir", (1.0, 0.0)))
                for raw in line.get("spans", []):
                    text = _span_text_from_chars(
                        raw.get("chars", []), raw.get("size", 0.0)
                    )
                    if not text.strip():
                        continue
                    bbox: BBox = tuple(raw["bbox"])  # type: ignore[assignment]
                    if image_rects and _overlaps_any(bbox, image_rects):
                        continue  # text painted over an image is dropped too
                    spans.append(
                        Span(
                            text=text,
                            bbox=bbox,
                            style=style_from_flags(
                                raw.get("flags", 0),
                                font=raw.get("font", ""),
                                size=raw.get("size", 0.0),
                                color=raw.get("color", 0),
                            ),
                            direction=direction,  # type: ignore[arg-type]
                        )
                    )
        return spans


class PdfToTextExtractor(TextExtractor):
    """Dependency-free pdftotext fallback (reduced fidelity).

    Planned — not yet implemented.
    """

    def extract(self, pdf_path: str) -> ExtractionResult:  # noqa: ARG002
        raise NotImplementedError(
            "PdfToTextExtractor is planned but not implemented yet; "
            "use --extractor pymupdf."
        )


def extract_to_document(result: ExtractionResult) -> Document:
    """Adapt an ExtractionResult into the AST Document shell.

    Pages carry no blocks yet; structure detection fills those in later.
    """
    from .ast import Document, DocumentMeta  # noqa: PLC0415

    doc = Document(meta=DocumentMeta(title=result.title))
    doc.scanned_pages = list(result.scanned_pages)
    for raw in result.pages:
        doc.pages.append(
            Page(number=raw.number, width=raw.width, height=raw.height)
        )
    return doc

