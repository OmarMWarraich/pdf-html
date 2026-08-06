"""Layout-aware text extraction.

Defines the TextExtractor ABC (extension point) and the default
PyMuPDFExtractor, which uses page.get_text("dict") to capture per-span
size/flags/color/bbox. A dependency-free pdftotext fallback is planned.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pymupdf

from .ast import BBox, Page, Span, SpanStyle

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


class PyMuPDFExtractor(TextExtractor):
    """Default extractor: page.get_text("dict") -> spans with style metadata."""

    def extract(self, pdf_path: str) -> ExtractionResult:
        result = ExtractionResult(title="")
        with pymupdf.open(pdf_path) as doc:
            result.title = doc.metadata.get("title", "") or ""
            for page in doc:
                image_rects = self._image_rects(page)
                spans = self._page_spans(page, image_rects)
                number = page.number + 1
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
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:  # 0 = text; 1 = image (dropped)
                continue
            for line in block.get("lines", []):
                direction = tuple(line.get("dir", (1.0, 0.0)))
                for raw in line.get("spans", []):
                    if not raw.get("text", "").strip():
                        continue
                    bbox: BBox = tuple(raw["bbox"])  # type: ignore[assignment]
                    if image_rects and _overlaps_any(bbox, image_rects):
                        continue  # text painted over an image is dropped too
                    spans.append(
                        Span(
                            text=raw["text"],
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


def extract_to_document(result: ExtractionResult) -> "Document":
    """Adapt an ExtractionResult into the AST Document shell.

    Pages carry no blocks yet; structure detection fills those in later.
    """
    from .ast import Document, DocumentMeta

    doc = Document(meta=DocumentMeta(title=result.title))
    doc.scanned_pages = list(result.scanned_pages)
    for raw in result.pages:
        doc.pages.append(
            Page(number=raw.number, width=raw.width, height=raw.height)
        )
    return doc

