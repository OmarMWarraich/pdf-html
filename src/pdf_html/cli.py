"""Command-line interface.

pdf-html INPUT.pdf -o out.html [--extractor pymupdf|pdftotext]
    [--style auto|default] [--paginate] [--no-tables] [--no-callouts]
    [--keep-headers] [--allow-scanned]
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .ast import Document, DocumentMeta, Page
from .extractor import PdfToTextExtractor, PyMuPDFExtractor, TextExtractor
from .header_footer import strip_headers_footers
from .renderer import render_html
from .style_profiler import profile_styles
from .table_reconstructor import merge_continuation_tables, reconstruct_page

EXIT_OK = 0
EXIT_SCANNED = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-html",
        description=(
            "Convert a text-based PDF into a single self-contained HTML file. "
            "Text is verbatim; images are dropped; style is inferred from "
            "font metadata and geometry."
        ),
    )
    parser.add_argument("input", help="Path to the input PDF.")
    parser.add_argument(
        "-o", "--output", required=True, help="Path of the HTML file to write."
    )
    parser.add_argument(
        "--extractor",
        choices=["pymupdf", "pdftotext"],
        default="pymupdf",
        help="Text extractor backend (default: pymupdf).",
    )
    parser.add_argument(
        "--style",
        choices=["auto", "default"],
        default="auto",
        help=(
            "'auto' derives CSS from the document's fonts/sizes/colors; "
            "'default' uses a clean built-in theme (default: auto)."
        ),
    )
    parser.add_argument(
        "--paginate",
        action="store_true",
        help="Wrap each PDF page in a <section class='sheet'> (off by default).",
    )
    parser.add_argument(
        "--no-tables",
        action="store_true",
        help=(
            "Disable table reconstruction; table text flows as regular "
            "paragraphs in reading order (tables are on by default)."
        ),
    )
    parser.add_argument(
        "--no-callouts",
        action="store_true",
        help="Disable callout detection (accepted; callouts not yet implemented).",
    )
    parser.add_argument(
        "--keep-headers",
        action="store_true",
        help="Keep repeated running headers/footers instead of stripping them.",
    )
    parser.add_argument(
        "--allow-scanned",
        action="store_true",
        help="Convert scanned/image PDFs instead of exiting non-zero.",
    )
    return parser


def _extractor(name: str) -> TextExtractor:
    if name == "pdftotext":
        return PdfToTextExtractor()  # TODO: planned, raises NotImplementedError
    return PyMuPDFExtractor()


def convert(args: argparse.Namespace) -> Document:
    """Run the full pipeline for parsed CLI args and return the AST."""
    result = _extractor(args.extractor).extract(args.input)

    if result.scanned_pages and not args.allow_scanned:
        print(
            f"error: {len(result.scanned_pages)} of {len(result.pages)} page(s) "
            "contain no extractable text — this looks like a scanned PDF.\n"
            "hint: pre-run OCR (e.g. `ocrmypdf in.pdf out.pdf`) or pass "
            "--allow-scanned to convert anyway.",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_SCANNED)

    pages = result.pages if args.keep_headers else strip_headers_footers(result.pages)
    profile = profile_styles(pages)
    if args.no_tables:
        for page in pages:
            page.tables = []  # reconstruct_page falls back to flow classification

    # TODO: callout detection (--no-callouts) once callout_detector lands.
    doc = Document(
        meta=DocumentMeta(
            title=result.title,
            body_size=profile.body_size,
            body_font=profile.body_font,
            heading_sizes=profile.heading_sizes,
            palette=profile.palette,
        ),
        scanned_pages=list(result.scanned_pages),
    )
    pages_blocks = [reconstruct_page(raw, profile) for raw in pages]
    merge_continuation_tables(pages_blocks)
    for raw, blocks in zip(pages, pages_blocks, strict=True):
        doc.pages.append(
            Page(
                number=raw.number,
                width=raw.width,
                height=raw.height,
                blocks=blocks,
            )
        )
    return doc


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    doc = convert(args)
    html_text = render_html(doc, style=args.style, paginate=args.paginate)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html_text)
    print(f"wrote {args.output} ({len(doc.pages)} page(s))")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

