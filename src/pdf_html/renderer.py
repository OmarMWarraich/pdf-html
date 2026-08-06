"""HTML renderer.

Emits a single self-contained HTML5 file with one inline <style> block. CSS
variables are derived from the style profile (--body-size, --h1..h6,
--font-body, --accent). Semantic tags under an <article> root; text is
escaped (& < >); no <img> elements, ever.
"""

from __future__ import annotations

import html
from collections.abc import Sequence

from .ast import (
    Block,
    Callout,
    Document,
    Heading,
    ListBlock,
    ListItem,
    Paragraph,
    Run,
    TableBlock,
)

# Built-in theme used by --style default (auto derives from the document).
DEFAULT_BODY_SIZE_PT = 11.0
DEFAULT_BODY_FONT = "Georgia, 'Times New Roman', serif"

# Cap auto-derived sizes so presentation-deck fonts do not overwhelm the
# default light web page. Relative scaling is preserved; only absolute
# extremes are clamped.
MAX_BODY_SIZE_PT = 16.0
MAX_HEADING_SIZES_PT = [22.0, 18.0, 16.0, 14.0]


def _escape(text: str) -> str:
    """Escape & < > for HTML text content; text stays verbatim otherwise."""
    return html.escape(text, quote=False)


# Luminance threshold above which a color is considered "light". PDF slides
# frequently use white/light text against a dark background image; since this
# package drops images, that text would disappear on the default light page.
LIGHT_COLOR_LUMINANCE_THRESHOLD = 0.82
LIGHT_COLOR_FALLBACK = "#2a2a2a"


def _visible_color(color: int) -> str:
    """Return a CSS #rrggbb string that remains visible on the default light background.

    Colors with a relative luminance above LIGHT_COLOR_LUMINANCE_THRESHOLD are
    remapped to LIGHT_COLOR_FALLBACK; otherwise the original color is preserved.
    This is a purely presentational adjustment: the underlying text is unchanged.
    """
    rgb = color & 0xFFFFFF
    r = (rgb >> 16) & 0xFF
    g = (rgb >> 8) & 0xFF
    b = rgb & 0xFF
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    if luminance > LIGHT_COLOR_LUMINANCE_THRESHOLD:
        return LIGHT_COLOR_FALLBACK
    return f"#{rgb:06x}"


def _render_run(run: Run, body_size: float, body_color: int) -> str:
    """Render one inline run with semantic tags for its style."""
    text = _escape(run.text)
    style = run.style
    if style.superscript:
        text = f"<sup>{text}</sup>"
    if style.mono:
        text = f"<code>{text}</code>"
    if style.italic:
        text = f"<em>{text}</em>"
    if style.bold:
        text = f"<strong>{text}</strong>"
    css: list[str] = []
    if style.color & 0xFFFFFF != body_color & 0xFFFFFF and style.color != 0:
        css.append(f"color: {_visible_color(style.color)}")
    if body_size and style.size and abs(style.size - body_size) > 0.5:
        css.append(f"font-size: {style.size / body_size:.2f}em")
    if css:
        text = f'<span style="{"; ".join(css)}">{text}</span>'
    return text


def _render_runs(runs: Sequence[Run], body_size: float, body_color: int) -> str:
    return "".join(_render_run(r, body_size, body_color) for r in runs)


def _render_list(block: ListBlock, body_size: float, body_color: int) -> str:
    tag = "ol" if block.ordered else "ul"

    def item_html(item: ListItem) -> str:
        inner = _render_runs(item.runs, body_size, body_color)
        if item.items:
            nested = ListBlock(ordered=block.ordered, items=item.items)
            inner += _render_list(nested, body_size, body_color)
        return f"<li>{inner}</li>"

    items = "".join(item_html(i) for i in block.items)
    return f"<{tag}>{items}</{tag}>"


def _render_block(block: Block, body_size: float, body_color: int) -> str:
    if isinstance(block, Heading):
        level = min(max(block.level, 1), 6)
        return f"<h{level}>{_render_runs(block.runs, body_size, body_color)}</h{level}>"
    if isinstance(block, Paragraph):
        align = f' class="align-{block.align}"' if block.align in {"center", "right"} else ""
        return f"<p{align}>{_render_runs(block.runs, body_size, body_color)}</p>"
    if isinstance(block, ListBlock):
        return _render_list(block, body_size, body_color)
    if isinstance(block, TableBlock):
        rows: list[str] = []
        for r, row in enumerate(block.rows):
            cell_tag = "th" if r < block.header_rows else "td"
            cells = "".join(f"<{cell_tag}>{_escape(c)}</{cell_tag}>" for c in row)
            rows.append(f"<tr>{cells}</tr>")
        return f"<table>{''.join(rows)}</table>"
    if isinstance(block, Callout):
        return (
            f'<aside class="callout callout-{html.escape(block.kind)}">'
            f"{_render_runs(block.runs, body_size, body_color)}</aside>"
        )
    raise TypeError(f"unknown block type: {type(block)!r}")


def _css(doc: Document, style: str) -> str:
    """Build the single inline stylesheet from the document profile."""
    meta = doc.meta
    if style == "auto" and meta.body_size:
        body_size = min(meta.body_size, MAX_BODY_SIZE_PT)
        body_font = f"'{meta.body_font}', serif" if meta.body_font else DEFAULT_BODY_FONT
        heading_sizes = [
            min(size, MAX_HEADING_SIZES_PT[i])
            for i, size in enumerate(meta.heading_sizes[:4])
        ]
        palette = meta.palette
    else:
        body_size = DEFAULT_BODY_SIZE_PT
        body_font = DEFAULT_BODY_FONT
        heading_sizes = [body_size * f for f in (2.0, 1.6, 1.35, 1.2, 1.1, 1.0)]
        palette = []

    accent = f"#{palette[1]:06x}" if len(palette) > 1 else "#1a4f8a"
    rules = [
        ":root {",
        f"  --body-size: {body_size:.1f}pt;",
        f"  --font-body: {body_font};",
        f"  --accent: {accent};",
    ]
    for i, size in enumerate(heading_sizes[:6], start=1):
        rules.append(f"  --h{i}: {size:.1f}pt;")
    rules.append("}")
    rules.append("article { font-family: var(--font-body); font-size: var(--body-size); "
                 "max-width: 46rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }")
    for i, size in enumerate(heading_sizes[:6], start=1):
        rules.append(f"h{i} {{ font-size: var(--h{i}); color: var(--accent); }}")
    rules.append(".align-center { text-align: center; }")
    rules.append(".align-right { text-align: right; }")
    rules.append(".callout { border-left: 3px solid var(--accent); padding: .5rem 1rem; "
                 "background: color-mix(in srgb, var(--accent) 8%, transparent); }")
    rules.append("table { border-collapse: collapse; } th, td { padding: .25rem .75rem; }")
    rules.append("section.sheet { page-break-after: always; border-bottom: 1px dashed #ccc; }")
    return "\n".join(rules)


def render_html(
    doc: Document, *, style: str = "auto", paginate: bool = False
) -> str:
    """Render the document AST to a single self-contained HTML5 string."""
    body_size = doc.meta.body_size or DEFAULT_BODY_SIZE_PT
    body_color = doc.meta.palette[0] if doc.meta.palette else 0

    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_escape(doc.meta.title) or 'Document'}</title>",
        f"<style>\n{_css(doc, style)}\n</style>",
        "</head>",
        "<body>",
        "<article>",
    ]
    for page in doc.pages:
        if paginate:
            parts.append(f'<section class="sheet" data-page="{page.number}">')
        for block in page.blocks:
            parts.append(_render_block(block, body_size, body_color))
        if paginate:
            parts.append("</section>")
    parts.extend(["</article>", "</body>", "</html>", ""])
    return "\n".join(parts)

