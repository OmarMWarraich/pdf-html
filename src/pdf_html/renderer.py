"""HTML renderer.

Emits a single self-contained HTML5 file with one inline <style> block. CSS
variables are derived from the style profile (--body-size, --h1..h6,
--font-body, --accent). Semantic tags under an <article> root; text is
escaped (& < >); no <img> elements, ever.
"""
