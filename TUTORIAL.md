# pdf-html Tutorial

A step-by-step guide to converting PDFs into styled, self-contained HTML.

## 1. Install the CLI

```bash
# with uv (recommended)
uv pip install .

# or with pip
pip install .
```

Verify the install:

```bash
pdf2html --help
```

## 2. Convert your first PDF

```bash
pdf2html my-document.pdf -o my-document.html
```

Open `my-document.html` in any browser. The output is a single self-contained
HTML5 file — no external assets — that mirrors the source document's fonts,
heading scale, and colors, with the text carried over verbatim and all images
dropped. Ruled tables are rebuilt as real `<table>` elements — including
bullet lists inside cells and rows that continue across page breaks.

## 3. Useful options

Use the built-in theme instead of the document's own style:

```bash
pdf2html my-document.pdf -o out.html --style default
```

Keep repeated running headers/footers:

```bash
pdf2html my-document.pdf -o out.html --keep-headers
```

Preserve page boundaries as `<section class="sheet">` wrappers:

```bash
pdf2html my-document.pdf -o out.html --paginate
```

## 4. Real examples

Convert the bundled fixture documents (after `uv sync`):

```bash
uv run pdf2html tests/fixtures/report.pdf -o /tmp/report.html
uv run pdf2html tests/fixtures/two_column.pdf -o /tmp/two_column.html
```

## 5. Troubleshooting

**"scanned PDF" error / non-zero exit.** The PDF has pages with no extractable
text (image-only scans). Pre-run OCR with a tool such as `ocrmypdf`, or pass
`--allow-scanned` to convert anyway (those pages will be empty).

**Headings at the wrong level.** Heading levels are inferred from document-wide
font-size tiers. Documents that use font weight alone (no size change) for
headings may flatten the hierarchy — text content is never affected.

**Text looks correct but styling is off.** Heuristic failures only affect
styling, never text content. If the document's typography is highly
unconventional, try `--style default` for a clean built-in theme.

**A table came out as loose paragraphs.** Table detection needs ruling lines
(the PyMuPDF `find_tables()` "lines" strategy). Borderless, whitespace-only
tables are not reconstructed yet — their text still appears, in reading
order, as regular paragraphs.
