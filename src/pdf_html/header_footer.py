"""Repeated header/footer stripping (geometry-based).

Removes spans whose bounding box top edge falls within the top 10% of page
height, or whose bottom edge falls within the bottom 10% of page height, when
that span text (digits normalized to #) appears on >= 60% of all pages.
"""
