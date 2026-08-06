"""PyMuPDF extractor tests: span metadata, image dropping, scanned detection."""

from __future__ import annotations

import pymupdf
import pytest

from pdf_html.extractor import (
    PyMuPDFExtractor,
    PdfToTextExtractor,
    _span_text_from_chars,
    style_from_flags,
    FLAG_BOLD,
    FLAG_ITALIC,
    FLAG_MONO,
    FLAG_SUPERSCRIPT,
)


@pytest.fixture()
def styled_pdf(tmp_path):
    path = tmp_path / "styled.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Bold Title", fontsize=20, fontname="hebo")
    page.insert_text((72, 140), "plain body", fontsize=11)
    doc.save(path)
    doc.close()
    return path


def test_extracts_spans_with_style(styled_pdf):
    result = PyMuPDFExtractor().extract(str(styled_pdf))
    spans = result.pages[0].spans
    by_text = {s.text: s for s in spans}
    title = by_text["Bold Title"]
    assert title.style.bold and title.style.size == pytest.approx(20.0)
    body = by_text["plain body"]
    assert not body.style.bold and body.style.size == pytest.approx(11.0)
    assert result.scanned_pages == []


def test_drops_spans_overlapping_images(tmp_path):
    path = tmp_path / "img.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 50))
    pix.set_rect(pix.irect, (200, 200, 200))
    page.insert_image(pymupdf.Rect(200, 200, 300, 250), pixmap=pix)
    page.insert_text((205, 225), "over image", fontsize=10)
    page.insert_text((72, 100), "safe text", fontsize=11)
    doc.save(path)
    doc.close()
    texts = [s.text for s in PyMuPDFExtractor().extract(str(path)).pages[0].spans]
    assert "safe text" in texts
    assert "over image" not in texts


def test_scanned_page_detection(tmp_path):
    path = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)
    doc.close()
    result = PyMuPDFExtractor().extract(str(path))
    assert result.is_scanned
    assert result.scanned_pages == [1]


def test_style_from_flags_bits():
    style = style_from_flags(
        FLAG_BOLD | FLAG_ITALIC | FLAG_MONO | FLAG_SUPERSCRIPT,
        font="Mono", size=9.0, color=0x112233,
    )
    assert style.bold and style.italic and style.mono and style.superscript
    assert not style.serif
    assert style.css_color == "#112233"


def test_pdftotext_fallback_not_implemented(tmp_path):
    with pytest.raises(NotImplementedError):
        PdfToTextExtractor().extract(str(tmp_path / "x.pdf"))


def test_span_text_from_chars_collapses_spaced_glyphs():
    """Decorative titles with explicit spaces between glyphs are rebuilt."""
    size = 24.0
    chars = [
        {"c": "C", "bbox": (0.0, 0.0, 10.0, 10.0)},
        {"c": " ", "bbox": (10.0, 0.0, 14.0, 10.0)},
        {"c": "E", "bbox": (14.0, 0.0, 24.0, 10.0)},
        {"c": " ", "bbox": (24.0, 0.0, 28.0, 10.0)},
        {"c": "R", "bbox": (28.0, 0.0, 38.0, 10.0)},
        {"c": " ", "bbox": (38.0, 0.0, 42.0, 10.0)},
        {"c": "T", "bbox": (42.0, 0.0, 52.0, 10.0)},
        {"c": " ", "bbox": (52.0, 0.0, 56.0, 10.0)},
        {"c": "I", "bbox": (56.0, 0.0, 64.0, 10.0)},
        {"c": " ", "bbox": (64.0, 0.0, 68.0, 10.0)},
        {"c": "F", "bbox": (68.0, 0.0, 78.0, 10.0)},
        {"c": " ", "bbox": (78.0, 0.0, 92.0, 10.0)},  # larger word gap
        {"c": "I", "bbox": (92.0, 0.0, 100.0, 10.0)},
    ]
    assert _span_text_from_chars(chars, size) == "CERTIF I"


def test_span_text_from_chars_preserves_normal_text():
    """Regular spans without decorative spacing are left untouched."""
    chars = [
        {"c": "H", "bbox": (0.0, 0.0, 8.0, 10.0)},
        {"c": "e", "bbox": (8.0, 0.0, 14.0, 10.0)},
        {"c": "l", "bbox": (14.0, 0.0, 18.0, 10.0)},
        {"c": "l", "bbox": (18.0, 0.0, 22.0, 10.0)},
        {"c": "o", "bbox": (22.0, 0.0, 28.0, 10.0)},
        {"c": " ", "bbox": (28.0, 0.0, 32.0, 10.0)},
        {"c": "w", "bbox": (32.0, 0.0, 40.0, 10.0)},
        {"c": "o", "bbox": (40.0, 0.0, 46.0, 10.0)},
        {"c": "r", "bbox": (46.0, 0.0, 50.0, 10.0)},
        {"c": "l", "bbox": (50.0, 0.0, 54.0, 10.0)},
        {"c": "d", "bbox": (54.0, 0.0, 60.0, 10.0)},
    ]
    assert _span_text_from_chars(chars, 12.0) == "Hello world"
