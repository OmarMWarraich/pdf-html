"""Layout-aware text extraction.

Defines the TextExtractor ABC (extension point) and the default
PyMuPDFExtractor, which uses page.get_text("dict") to capture per-span
size/flags/color/bbox. A dependency-free pdftotext fallback is planned.
"""
