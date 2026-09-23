"""Document model (AST).

Document -> Page -> blocks (Heading, Paragraph, ListBlock, TableBlock,
Callout). Runs carry inline style (bold, italic, color, size, mono,
superscript) so the renderer can emit semantic tags; text is always verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

# Axis-aligned bounding box in PDF user-space points: (x0, y0, x1, y1).
BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class SpanStyle:
    """Inline style metadata for a span or run, from PDF font metadata."""

    font: str = ""
    size: float = 0.0
    bold: bool = False
    italic: bool = False
    mono: bool = False
    serif: bool = False
    superscript: bool = False
    color: int = 0  # sRGB int, 0xRRGGBB

    @property
    def css_color(self) -> str:
        """Return the color as a #rrggbb CSS string."""
        return f"#{self.color & 0xFFFFFF:06x}"


@dataclass(frozen=True)
class Span:
    """A contiguous run of same-styled text as extracted from the PDF."""

    text: str
    bbox: BBox
    style: SpanStyle
    # Writing direction of the containing line (usually (1, 0)).
    direction: tuple[float, float] = (1.0, 0.0)


# A Run is a Span that survived page analysis into the document tree.
Run = Span


@dataclass
class Heading:
    level: int  # 1..6
    runs: list[Run] = field(default_factory=list)


@dataclass
class Paragraph:
    runs: list[Run] = field(default_factory=list)
    align: str = "left"  # left | center | right | justify


@dataclass
class ListItem:
    runs: list[Run] = field(default_factory=list)
    items: list["ListItem"] = field(default_factory=list)  # nested children


@dataclass
class ListBlock:
    ordered: bool = False
    items: list[ListItem] = field(default_factory=list)


@dataclass
class TableCell:
    """One table cell; holds fully classified blocks (paragraphs, lists, ...)."""

    blocks: list["Block"] = field(default_factory=list)


@dataclass
class TableBlock:
    rows: list[list[TableCell]] = field(default_factory=list)
    header_rows: int = 0


@dataclass
class Callout:
    runs: list[Run] = field(default_factory=list)
    kind: str = "note"


Block = Union[Heading, Paragraph, ListBlock, TableBlock, Callout]


@dataclass
class Page:
    number: int  # 1-based
    width: float
    height: float
    blocks: list[Block] = field(default_factory=list)


@dataclass
class DocumentMeta:
    title: str = ""
    body_size: float = 0.0
    body_font: str = ""
    heading_sizes: list[float] = field(default_factory=list)  # h1..h6 tiers
    palette: list[int] = field(default_factory=list)  # sRGB ints


@dataclass
class Document:
    meta: DocumentMeta = field(default_factory=DocumentMeta)
    pages: list[Page] = field(default_factory=list)
    scanned_pages: list[int] = field(default_factory=list)  # 1-based numbers

    @property
    def is_scanned(self) -> bool:
        """True when every page lacks extractable text."""
        return bool(self.pages) and len(self.scanned_pages) == len(self.pages)

