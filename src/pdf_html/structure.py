"""Block classification from geometry and font cues.

Classifies lines/blocks as heading, list_item, table, callout, or paragraph,
and merges consecutive lines into paragraphs when size/font match and the
vertical gap stays below ~1.4x line height.
"""
