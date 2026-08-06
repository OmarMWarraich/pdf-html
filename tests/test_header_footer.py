"""Header/footer stripping tests: geometry bands + repetition threshold."""

from __future__ import annotations

import pymupdf
import pytest

from pdf_html.extractor import PyMuPDFExtractor
from pdf_html.header_footer import (
    HEADER_FOOTER_PAGE_FRACTION,
    MIN_PAGE_OCCURRENCE,
    normalize_text,
    repeated_boilerplate,
    strip_headers_footers,
)


def _make_doc(tmp_path, pages: int, *, with_boilerplate: bool = True):
    path = tmp_path / "hf.pdf"
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page(width=612, height=792)
        if with_boilerplate:
            page.insert_text((72, 40), f"Draft {i + 1}", fontsize=9)
            page.insert_text((300, 770), f"Page {i + 1}", fontsize=9)
        page.insert_text((72, 300), "Real body content.", fontsize=11)
    doc.save(path)
    doc.close()
    return PyMuPDFExtractor().extract(str(path))


def test_normalize_text_replaces_digits():
    assert normalize_text("Page 12 of 34") == "Page # of #"
    assert normalize_text("  extra   spaces ") == "extra spaces"


def test_strips_repeated_headers_and_footers(tmp_path):
    result = _make_doc(tmp_path, 3)
    assert repeated_boilerplate(result.pages) == {"Draft #", "Page #"}
    stripped = strip_headers_footers(result.pages)
    texts = [s.text for p in stripped for s in p.spans]
    assert texts == ["Real body content."] * 3


def test_single_page_document_is_untouched(tmp_path):
    """A lone title in the top band is content, not a running header."""
    result = _make_doc(tmp_path, 1)
    stripped = strip_headers_footers(result.pages)
    texts = [s.text for p in stripped for s in p.spans]
    assert "Draft 1" in texts and "Real body content." in texts


def test_infrequent_candidate_is_kept(tmp_path):
    """Appearing on fewer than 60% of pages keeps the span."""
    path = tmp_path / "rare.pdf"
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 300), "Body.", fontsize=11)
        if i == 0:  # only 1 of 3 pages -> below the 60% threshold
            page.insert_text((72, 40), "One-off note", fontsize=9)
    doc.save(path)
    doc.close()
    result = PyMuPDFExtractor().extract(str(path))
    stripped = strip_headers_footers(result.pages)
    texts = [s.text for p in stripped for s in p.spans]
    assert "One-off note" in texts


def test_threshold_constants_match_spec():
    assert HEADER_FOOTER_PAGE_FRACTION == pytest.approx(0.10)
    assert MIN_PAGE_OCCURRENCE == pytest.approx(0.60)
