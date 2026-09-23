"""Generate the committed fixture PDFs deterministically (reportlab).

Run:  uv run python tests/fixtures/make_fixtures.py

Produces the fixtures per REQS.md §8:
  report.pdf      — multi-page report: running header/footer, h1/h2 headings,
                    body paragraphs, nested bullet + ordered lists.
  two_column.pdf  — two-column layout to exercise reading-order clustering.
  slides.pdf      — landscape slide deck: big titles, sparse bullets.
  brochure.pdf    — single-page marketing layout: colors, centered text.
  table.pdf       — ruled 2-column table (bold header row, bullets inside a
                    cell) with flow text before and after it.

EXPECTED_TEXT holds the exact strings drawn into each fixture so tests can
verify verbatim output. Every string uses explicit fonts and sizes so the
style profiler has real tiers to find.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

FIXTURE_DIR = Path(__file__).parent

PAGE_W, PAGE_H = A4  # 595.27 x 841.89 pt

# y coordinates are measured from the TOP of the page (PDF-native origin is
# bottom-left; the helpers below flip).
def _y(c: canvas.Canvas, top: float, page_h: float = PAGE_H) -> float:
    return page_h - top


def _draw(c: canvas.Canvas, x: float, top: float, text: str, font: str,
          size: float, page_h: float = PAGE_H,
          color: HexColor | None = None) -> None:
    c.setFont(font, size)
    c.setFillColor(color or HexColor("#000000"))
    c.drawString(x, _y(c, top, page_h), text)


# ---------------------------------------------------------------- report.pdf
REPORT_BODY_P1 = [
    "The quarterly results exceeded expectations across all regions.",
    "Revenue grew steadily while operating costs remained flat.",
]
REPORT_BULLETS = ["Expand the core product line", "Invest in customer support"]
# 'o' stands in for the circle bullet: reportlab's built-in 14 fonts cannot
# encode U+25E6 (◦), which would otherwise extract as 'I'.
REPORT_NESTED = ["Hire two regional leads"]
REPORT_ORDERED = ["Collect requirements", "Draft the proposal", "Review with stakeholders"]

EXPECTED_TEXT: dict[str, list[str]] = {
    "report.pdf": [
        "Annual Report", "Overview", *REPORT_BODY_P1,
        *REPORT_BULLETS, *REPORT_NESTED, *REPORT_ORDERED,
        "Financials", "Margins improved for the third consecutive quarter.",
    ],
    "two_column.pdf": [
        "Two Column Paper", "Abstract",
        "Left column first line.", "Left column second line.",
        "Right column first line.", "Right column second line.",
    ],
    "slides.pdf": [
        "Product Launch", "Why now", "Market timing is right",
        "Roadmap", "Q1 foundations", "Q2 launch",
    ],
    "brochure.pdf": [
        "Acme Widgets", "Quality you can trust", "Visit us today",
    ],
    "table.pdf": [
        "Course Outline", "Topic", "Outcomes",
        "Topic 1: Threats", "Learning outcomes:",
        "Define common threats.", "Classify threats by impact.",
        "Topic 2: Crypto", "Apply symmetric ciphers.",
        "Text after the table.",
    ],
}


def make_report(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    for page_no in (1, 2):
        _draw(c, 72, 30, f"Acme Corp — {page_no}", "Helvetica", 9)      # header
        _draw(c, 520, 815, f"{page_no}", "Helvetica", 9)               # footer
        if page_no == 1:
            _draw(c, 72, 90, "Annual Report", "Helvetica-Bold", 24)
            _draw(c, 72, 130, "Overview", "Helvetica-Bold", 16)
            top = 160
            for line in REPORT_BODY_P1:
                _draw(c, 72, top, line, "Helvetica", 11)
                top += 15
            top += 12
            for item in REPORT_BULLETS:
                _draw(c, 72, top, f"• {item}", "Helvetica", 11)
                top += 15
            for item in REPORT_NESTED:
                _draw(c, 100, top, f"o {item}", "Helvetica", 11)
                top += 15
            top += 12
            for n, item in enumerate(REPORT_ORDERED, start=1):
                _draw(c, 72, top, f"{n}. {item}", "Helvetica", 11)
                top += 15
        else:
            _draw(c, 72, 90, "Financials", "Helvetica-Bold", 16)
            _draw(c, 72, 120,
                  "Margins improved for the third consecutive quarter.",
                  "Helvetica", 11)
        c.showPage()
    c.save()


def make_two_column(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    _draw(c, 72, 80, "Two Column Paper", "Helvetica-Bold", 20)
    _draw(c, 72, 115, "Abstract", "Helvetica-Bold", 14)
    _draw(c, 72, 150, "Left column first line.", "Helvetica", 10)
    _draw(c, 72, 164, "Left column second line.", "Helvetica", 10)
    _draw(c, 320, 150, "Right column first line.", "Helvetica", 10)
    _draw(c, 320, 164, "Right column second line.", "Helvetica", 10)
    c.showPage()
    c.save()


def make_slides(path: Path) -> None:
    w, h = landscape(A4)
    c = canvas.Canvas(str(path), pagesize=(w, h))
    _draw(c, 60, 90, "Product Launch", "Helvetica-Bold", 36, page_h=h)
    _draw(c, 60, 150, "Why now", "Helvetica-Bold", 20, page_h=h)
    _draw(c, 60, 190, "Market timing is right", "Helvetica", 14, page_h=h)
    c.showPage()
    _draw(c, 60, 90, "Roadmap", "Helvetica-Bold", 36, page_h=h)
    _draw(c, 60, 150, "• Q1 foundations", "Helvetica", 18, page_h=h)
    _draw(c, 60, 180, "• Q2 launch", "Helvetica", 18, page_h=h)
    c.showPage()
    c.save()


def make_brochure(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    navy = HexColor("#1a4f8a")
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(PAGE_W / 2, _y(c, 120), "Acme Widgets")
    c.setFillColor(HexColor("#b03030"))
    c.setFont("Helvetica-Oblique", 16)
    c.drawCentredString(PAGE_W / 2, _y(c, 160), "Quality you can trust")
    c.setFillColor(HexColor("#000000"))
    c.setFont("Helvetica", 12)
    c.drawCentredString(PAGE_W / 2, _y(c, 700), "Visit us today")
    c.showPage()
    c.save()


def make_table(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    _draw(c, 72, 80, "Course Outline", "Helvetica-Bold", 16)
    # Ruled 2-column grid: header row + two body rows.
    tops = [110, 135, 200, 250]  # row edges, from page top
    xs = [72, 250, 520]
    c.setLineWidth(0.7)
    c.grid(xs, [_y(c, t) for t in tops])
    _draw(c, 78, 127, "Topic", "Helvetica-Bold", 11)
    _draw(c, 256, 127, "Outcomes", "Helvetica-Bold", 11)
    _draw(c, 78, 152, "Topic 1: Threats", "Helvetica", 11)
    _draw(c, 256, 152, "Learning outcomes:", "Helvetica-Bold", 11)
    _draw(c, 256, 168, "• Define common threats.", "Helvetica", 11)
    _draw(c, 256, 184, "• Classify threats by impact.", "Helvetica", 11)
    _draw(c, 78, 217, "Topic 2: Crypto", "Helvetica", 11)
    _draw(c, 256, 217, "• Apply symmetric ciphers.", "Helvetica", 11)
    _draw(c, 72, 290, "Text after the table.", "Helvetica", 11)
    c.showPage()
    c.save()


GENERATORS = {
    "report.pdf": make_report,
    "two_column.pdf": make_two_column,
    "slides.pdf": make_slides,
    "brochure.pdf": make_brochure,
    "table.pdf": make_table,
}


def main() -> None:
    for name, generator in GENERATORS.items():
        generator(FIXTURE_DIR / name)
        print(f"wrote {FIXTURE_DIR / name}")


if __name__ == "__main__":
    main()
