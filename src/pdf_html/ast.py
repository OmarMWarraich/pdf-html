"""Document model (AST).

Document -> Page -> blocks (Heading, Paragraph, ListBlock, TableBlock,
Callout). Runs carry inline style (bold, italic, color, size, mono,
superscript) so the renderer can emit semantic tags; text is always verbatim.
"""
