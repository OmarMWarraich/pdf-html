"""PyMuPDF extractor tests: span metadata, image dropping, scanned detection."""

from __future__ import annotations

import pymupdf
import pytest

from pdf_html.extractor import (
    PyMuPDFExtractor,
    PdfToTextExtractor,
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
