"""End-to-end pipeline tests over the committed fixture PDFs.

Verifies the Definition of Done: the pipeline runs on every fixture without
regressions and the text output stays verbatim.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from pdf_html.ast import Heading, ListBlock, Paragraph
from pdf_html.cli import main as cli_main
from pdf_html.extractor import PyMuPDFExtractor
from pdf_html.header_footer import strip_headers_footers
from pdf_html.list_parser import parse_lists
from pdf_html.renderer import render_html
from pdf_html.structure import classify_document
from pdf_html.style_profiler import profile_styles

FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(FIXTURES))
from make_fixtures import EXPECTED_TEXT, GENERATORS  # noqa: E402


def _render_fixture(name: str) -> str:
    result = PyMuPDFExtractor().extract(str(FIXTURES / name))
    pages = strip_headers_footers(result.pages)
    profile = profile_styles(pages)
    from pdf_html.ast import Document, DocumentMeta, Page

    doc = Document(
        meta=DocumentMeta(
            title=result.title,
            body_size=profile.body_size,
            body_font=profile.body_font,
            heading_sizes=profile.heading_sizes,
            palette=profile.palette,
        )
    )
    for raw, blocks in zip(pages, classify_document(pages, profile), strict=True):
        doc.pages.append(Page(raw.number, raw.width, raw.height, parse_lists(blocks)))
    return render_html(doc)


@pytest.mark.parametrize("fixture", sorted(GENERATORS))
def test_fixtures_exist(fixture):
    assert (FIXTURES / fixture).exists(), (
        f"missing fixture {fixture} — run: uv run python tests/fixtures/make_fixtures.py"
    )


@pytest.mark.parametrize("fixture", sorted(GENERATORS))
def test_pipeline_runs_on_fixture(fixture):
    html = _render_fixture(fixture)
    assert html.startswith("<!DOCTYPE html>")
    assert "<img" not in html
    assert "</html>" in html


@pytest.mark.parametrize("fixture", sorted(GENERATORS))
def test_text_is_verbatim(fixture):
    """Every source string must appear in the HTML (escaped where needed)."""
    import html as html_mod

    html_out = _render_fixture(fixture)
    for text in EXPECTED_TEXT[fixture]:
        escaped = html_mod.escape(text, quote=False)
        assert escaped in html_out, f"{text!r} missing from {fixture} output"


def test_report_structure():
    result = PyMuPDFExtractor().extract(str(FIXTURES / "report.pdf"))
    pages = strip_headers_footers(result.pages)
    profile = profile_styles(result.pages)
    blocks = parse_lists(classify_document(pages, profile)[0])

    # Running header/footer stripped from the 2-page report.
    all_text = "".join(s.text for p in pages for s in p.spans)
    assert "Acme Corp" not in all_text

    headings = [b for b in blocks if isinstance(b, Heading)]
    assert [h.level for h in headings][:2] == [1, 2]
    lists = [b for b in blocks if isinstance(b, ListBlock)]
    assert any(not lst.ordered for lst in lists)
    assert any(lst.ordered for lst in lists)


def test_two_column_reading_order():
    result = PyMuPDFExtractor().extract(str(FIXTURES / "two_column.pdf"))
    profile = profile_styles(result.pages)
    blocks = parse_lists(classify_document(result.pages, profile)[0])
    paras = [b for b in blocks if isinstance(b, Paragraph)]
    text = " ".join("".join(r.text for r in p.runs) for p in paras)
    left = text.index("Left column second line.")
    right = text.index("Right column first line.")
    assert left < right  # left column fully precedes right column


def test_cli_end_to_end(tmp_path, capsys):
    out = tmp_path / "out.html"
    rc = cli_main([str(FIXTURES / "report.pdf"), "-o", str(out)])
    assert rc == 0
    content = out.read_text(encoding="utf-8")
    assert "<h1>" in content and "<ul>" in content and "<ol>" in content
    assert "Acme Corp" not in content  # header stripped by default


def test_cli_keep_headers(tmp_path):
    out = tmp_path / "out.html"
    rc = cli_main([str(FIXTURES / "report.pdf"), "-o", str(out), "--keep-headers"])
    assert rc == 0
    assert "Acme Corp" in out.read_text(encoding="utf-8")


def test_cli_rejects_scanned_pdf(tmp_path, capsys):
    import pymupdf

    blank = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(blank)
    doc.close()

    with pytest.raises(SystemExit) as exc:
        cli_main([str(blank), "-o", str(tmp_path / "x.html")])
    assert exc.value.code != 0
    assert "ocrmypdf" in capsys.readouterr().err

    rc = cli_main([str(blank), "-o", str(tmp_path / "x.html"), "--allow-scanned"])
    assert rc == 0
