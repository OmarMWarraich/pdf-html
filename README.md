# pdf-html

Convert any text-based PDF into beautiful, self-contained HTML.

The HTML reproduces the typographic style of the source document — heading
hierarchy, emphasis, colors, alignment, and table layout — while carrying the
text **verbatim** and **dropping all images**. Structure is inferred
deterministically from font metadata and geometry (font size, weight, style,
color, bounding boxes); there is no NLP and no LLM in the core.

Ruled tables are detected with PyMuPDF's `find_tables()` and rebuilt as real
`<table>` elements: cell content keeps its inline styling, bullet lists inside
cells become nested `<ul>`/`<ol>`, bold-only first rows become `<th>` header
rows, and rows that continue across a page break are merged back into one row.

## Installation

Requires Python 3.10+.

```bash
# with uv (recommended)
uv pip install .

# or with pip
pip install .
```

For development (adds pytest and reportlab for fixture generation):

```bash
uv sync
```

## CLI Usage

```bash
pdf2html INPUT.pdf -o out.html [--extractor pymupdf|pdftotext]
    [--style auto|default] [--paginate] [--no-callouts] [--keep-headers]
    [--allow-scanned]
```

- `--style auto` (default) derives the CSS from the document's own fonts,
  sizes, and colors; `default` uses a clean built-in theme.
- `--paginate` wraps each PDF page in a `<section class="sheet">` (off by
  default — generic PDFs reflow better unpaginated).
- `--keep-headers` keeps repeated running headers/footers instead of
  stripping them.
- `--allow-scanned` converts scanned/image PDFs (pages with no text) instead
  of exiting non-zero with an OCR hint.

Example:

```bash
pdf2html report.pdf -o report.html
```

## Development Workflow

Feature-based commits (one commit = one feature or fix), message format
`feat|fix|docs|refactor|chore: ...`. Run the test suite with:

```bash
uv run pytest
```

Fixture PDFs (report, two-column paper, slide deck, brochure, ruled table)
live under tests/fixtures/ and are generated deterministically:

```bash
uv run python tests/fixtures/make_fixtures.py
```

## Contributing

- Python 3.10+, type hints throughout.
- PyMuPDF is the only hard runtime dependency; everything else is optional.
- Keep heuristics in small, pure, individually testable functions with tunable
  thresholds as module-level constants.
- Update README.md and TUTORIAL.md with any user-facing or CLI change.

## Releases

1. Bump `version` in pyproject.toml.
2. `uv build` — artifacts land in dist/.
3. `uv publish` (or `twine upload dist/*`) to push to PyPI.
