"""Reading-order tests: column clustering and column-major ordering."""

from __future__ import annotations

import pymupdf

from pdf_html.extractor import PyMuPDFExtractor
from pdf_html.reading_order import order_spans


def test_two_column_reading_order(tmp_path):
    path = tmp_path / "cols.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 200), "L1", fontsize=11)
    page.insert_text((72, 215), "L2", fontsize=11)
    page.insert_text((330, 200), "R1", fontsize=11)
    page.insert_text((330, 215), "R2", fontsize=11)
    doc.save(path)
    doc.close()

    result = PyMuPDFExtractor().extract(str(path))
    seq = [s.text for s in order_spans(result.pages[0])]
    assert seq == ["L1", "L2", "R1", "R2"]


def test_single_column_top_to_bottom(tmp_path):
    path = tmp_path / "single.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 300), "middle", fontsize=11)
    page.insert_text((72, 100), "top", fontsize=11)
    page.insert_text((72, 500), "bottom", fontsize=11)
    doc.save(path)
    doc.close()

    result = PyMuPDFExtractor().extract(str(path))
    seq = [s.text for s in order_spans(result.pages[0])]
    assert seq == ["top", "middle", "bottom"]


def test_indented_list_page_is_not_a_card_grid(tmp_path):
    """Narrow lead-ins + wide wrapped body lines must stay one column.

    Regression: the card-column fallback used to split bullet lead-ins from
    their descriptions, reordering the page column-major.
    """
    path = tmp_path / "list.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    for i in range(4):
        y = 120 + i * 60
        page.insert_text((90, y), "•", fontsize=11)
        page.insert_text((108, y), f"Item {i}.", fontsize=11)
        page.insert_text((190, y), f"Wide description for item {i} of the list.", fontsize=11)
        page.insert_text((108, y + 15), f"Wrapped continuation line {i} spanning most of the page width here.", fontsize=11)
    doc.save(path)
    doc.close()

    result = PyMuPDFExtractor().extract(str(path))
    seq = [s.text for s in order_spans(result.pages[0])]
    # Strict top-to-bottom order: every item's texts precede the next item's.
    positions = [seq.index(f"Item {i}.") for i in range(4)]
    assert positions == sorted(positions)
    for i in range(4):
        assert seq.index(f"Item {i}.") < seq.index(
            f"Wrapped continuation line {i} spanning most of the page width here."
        )
