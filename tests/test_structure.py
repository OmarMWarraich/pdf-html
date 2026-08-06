"""Structure detection + list parsing tests."""

from __future__ import annotations

import pymupdf
import pytest

from pdf_html.ast import Heading, ListBlock, Paragraph
from pdf_html.extractor import PyMuPDFExtractor
from pdf_html.list_parser import is_list_item, parse_lists, strip_marker
from pdf_html.ast import Span, SpanStyle
from pdf_html.structure import classify_document
from pdf_html.style_profiler import profile_styles


@pytest.fixture()
def structured(tmp_path):
    path = tmp_path / "struct.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 120), "Chapter One", fontsize=20, fontname="hebo")
    page.insert_text((72, 160), "First body paragraph line.", fontsize=11)
    page.insert_text((72, 173), "Second line of same paragraph.", fontsize=11)
    page.insert_text((72, 210), "• Top level item", fontsize=11)
    page.insert_text((100, 225), "◦ Nested item", fontsize=11)
    page.insert_text((72, 240), "1. Ordered one", fontsize=11)
    page.insert_text((72, 255), "2. Ordered two", fontsize=11)
    doc.save(path)
    doc.close()
    result = PyMuPDFExtractor().extract(str(path))
    profile = profile_styles(result.pages)
    return parse_lists(classify_document(result.pages, profile)[0])


def test_heading_classification(structured):
    assert isinstance(structured[0], Heading)
    assert structured[0].level == 1
    assert "".join(r.text for r in structured[0].runs) == "Chapter One"


def test_paragraph_merging(structured):
    para = structured[1]
    assert isinstance(para, Paragraph)
    text = "".join(r.text for r in para.runs)
    assert "First body paragraph line." in text
    assert "Second line of same paragraph." in text


def test_nested_unordered_list(structured):
    ul = next(b for b in structured if isinstance(b, ListBlock) and not b.ordered)
    assert len(ul.items) == 1
    assert ul.items[0].runs[0].text == "Top level item"
    assert len(ul.items[0].items) == 1
    assert ul.items[0].items[0].runs[0].text == "Nested item"


def test_ordered_list_split_from_bullets(structured):
    lists = [b for b in structured if isinstance(b, ListBlock)]
    assert len(lists) == 2  # marker-style change splits the block
    ol = lists[1]
    assert ol.ordered
    assert [it.runs[0].text for it in ol.items] == ["Ordered one", "Ordered two"]


def test_marker_recognition():
    assert is_list_item("• bullet")
    assert is_list_item("1. numbered")
    assert is_list_item("a) alpha")
    assert is_list_item("iv. roman")
    assert not is_list_item("plain text")
    assert not is_list_item("3.14 is pi")  # no trailing whitespace+content split


def test_strip_marker_keeps_text_verbatim():
    style = SpanStyle(font="Helvetica", size=11.0)
    runs = [Span(text="• Buy milk & eggs", bbox=(0, 0, 10, 10), style=style)]
    strip_marker(runs, "•")
    assert "".join(r.text for r in runs) == "Buy milk & eggs"
