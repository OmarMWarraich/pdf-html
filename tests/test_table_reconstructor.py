"""Table reconstruction tests: detection, cell content, order, merging."""

from __future__ import annotations

from pathlib import Path

import pytest

from pdf_html.ast import (
    Heading,
    ListBlock,
    ListItem,
    Paragraph,
    Span,
    SpanStyle,
    TableBlock,
    TableCell,
)
from pdf_html.cli import main as cli_main
from pdf_html.extractor import PyMuPDFExtractor
from pdf_html.style_profiler import profile_styles
from pdf_html.table_reconstructor import (
    merge_continuation_tables,
    reconstruct_page,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _blocks(name: str = "table.pdf") -> list:
    result = PyMuPDFExtractor().extract(str(FIXTURES / name))
    profile = profile_styles(result.pages)
    return reconstruct_page(result.pages[0], profile)


def _cell_text(cell: TableCell) -> str:
    parts: list[str] = []

    def walk_items(items: list[ListItem]) -> None:
        for item in items:
            parts.extend(r.text for r in item.runs)
            walk_items(item.items)

    for block in cell.blocks:
        if isinstance(block, ListBlock):
            walk_items(block.items)
        else:
            parts.extend(r.text for r in block.runs)
    return " ".join(parts)


@pytest.fixture(scope="module")
def table_blocks():
    return _blocks()


def test_table_detected(table_blocks):
    tables = [b for b in table_blocks if isinstance(b, TableBlock)]
    assert len(tables) == 1
    table = tables[0]
    assert len(table.rows) == 3
    assert all(len(row) == 2 for row in table.rows)


def test_bold_first_row_becomes_header(table_blocks):
    table = next(b for b in table_blocks if isinstance(b, TableBlock))
    assert table.header_rows == 1
    assert "Topic" in _cell_text(table.rows[0][0])
    assert "Outcomes" in _cell_text(table.rows[0][1])


def test_cell_bullets_become_list(table_blocks):
    table = next(b for b in table_blocks if isinstance(b, TableBlock))
    outcome_cell = table.rows[1][1]
    lists = [b for b in outcome_cell.blocks if isinstance(b, ListBlock)]
    assert len(lists) == 1
    texts = [" ".join(r.text for r in item.runs) for item in lists[0].items]
    assert texts == ["Define common threats.", "Classify threats by impact."]
    # No document headings inside cells, ever.
    assert not any(isinstance(b, Heading) for b in outcome_cell.blocks)


def test_cell_text_verbatim_and_row_order(table_blocks):
    table = next(b for b in table_blocks if isinstance(b, TableBlock))
    assert "Topic 1: Threats" in _cell_text(table.rows[1][0])
    assert "Learning outcomes:" in _cell_text(table.rows[1][1])
    assert "Topic 2: Crypto" in _cell_text(table.rows[2][0])
    assert "Apply symmetric ciphers." in _cell_text(table.rows[2][1])


def test_flow_blocks_keep_document_order(table_blocks):
    kinds = [type(b) for b in table_blocks]
    table_at = kinds.index(TableBlock)
    heading_at = next(
        i for i, b in enumerate(table_blocks) if isinstance(b, Heading)
    )
    trailing_at = next(
        i
        for i, b in enumerate(table_blocks)
        if isinstance(b, Paragraph)
        and "Text after the table." in "".join(r.text for r in b.runs)
    )
    assert heading_at < table_at < trailing_at


def _span(text: str) -> Span:
    return Span(text=text, bbox=(0, 0, 10, 10), style=SpanStyle(size=11.0))


def test_merge_continuation_folds_fragment_into_previous_table():
    prev = TableBlock(
        rows=[
            [
                TableCell(blocks=[Paragraph(runs=[_span("Topic 8")])]),
                TableCell(
                    blocks=[
                        ListBlock(
                            items=[ListItem(runs=[_span("including AI, quantum")])]
                        )
                    ]
                ),
            ]
        ]
    )
    fragment = TableBlock(
        rows=[
            [
                TableCell(),
                TableCell(
                    blocks=[Paragraph(runs=[_span("and scalable protocols.")])]
                ),
            ]
        ]
    )
    pages_blocks = [[prev], [fragment, Paragraph(runs=[_span("after")])]]
    merge_continuation_tables(pages_blocks)

    assert pages_blocks[1] and not isinstance(pages_blocks[1][0], TableBlock)
    assert len(prev.rows) == 1
    item_text = " ".join(r.text for r in prev.rows[0][1].blocks[0].items[0].runs)
    assert item_text == "including AI, quantum and scalable protocols."


def test_merge_requires_empty_first_cell():
    prev = TableBlock(rows=[[TableCell(blocks=[Paragraph(runs=[_span("a")])])]])
    fresh = TableBlock(rows=[[TableCell(blocks=[Paragraph(runs=[_span("b")])])]])
    pages_blocks = [[prev], [fresh]]
    merge_continuation_tables(pages_blocks)
    assert pages_blocks[1] == [fresh]
    assert len(prev.rows) == 1


def test_cli_renders_html_table(tmp_path):
    out = tmp_path / "out.html"
    rc = cli_main([str(FIXTURES / "table.pdf"), "-o", str(out)])
    assert rc == 0
    html = out.read_text(encoding="utf-8")
    assert "<table>" in html and "<th>" in html and "<td>" in html
    assert "Define common threats." in html
    assert "Classify threats by impact." in html
    assert html.index("Course Outline") < html.index("<table>")
    assert html.index("</table>") < html.index("Text after the table.")
