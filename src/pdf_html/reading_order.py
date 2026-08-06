"""Reading order and column detection.

Splits pages into columns via x-coordinate gap clustering on span bounding
boxes and orders blocks column-by-column (left column top-to-bottom, then
the next column).
"""
