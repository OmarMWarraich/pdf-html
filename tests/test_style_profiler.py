"""Style profiler tests: body size, heading tiers, palette."""

from __future__ import annotations

import pymupdf
import pytest

from pdf_html.extractor import PyMuPDFExtractor
from pdf_html.style_profiler import (
    SIZE_TIER_MERGE_EPSILON_PT,
    StyleProfile,
    profile_styles,
)


@pytest.fixture()
def tiered(tmp_path):
    path = tmp_path / "tiers.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 80), "H One", fontsize=22, fontname="hebo")
    page.insert_text((72, 120), "H Two", fontsize=16, fontname="hebo")
    # Same tier within merge epsilon -> should NOT create h3.
    page.insert_text((72, 150), "H Two Again", fontsize=16.4, fontname="hebo")
    for i in range(6):  # enough body text to dominate the histogram
        page.insert_text((72, 200 + i * 15), f"Body line {i} with real words.", fontsize=11)
    doc.save(path)
    doc.close()
    return PyMuPDFExtractor().extract(str(path))


def test_body_size_is_modal(tiered):
    profile = profile_styles(tiered.pages)
    assert profile.body_size == pytest.approx(11.0)


def test_heading_tiers_merged_within_epsilon(tiered):
    profile = profile_styles(tiered.pages)
    # 16.0 and 16.4 land in the same tier; the tier count is what matters.
    assert len(profile.heading_sizes) == 2
    assert profile.heading_sizes[0] == pytest.approx(22.0)
    assert 16.0 - SIZE_TIER_MERGE_EPSILON_PT <= profile.heading_sizes[1] <= 16.4


def test_heading_level_mapping(tiered):
    profile = profile_styles(tiered.pages)
    assert profile.heading_level(22.0) == 1
    assert profile.heading_level(16.0) == 2
    assert profile.heading_level(16.4) == 2  # within epsilon
    assert profile.heading_level(11.0) is None


def test_empty_document():
    assert profile_styles([]) == StyleProfile()


def test_epsilon_constant_matches_spec():
    assert SIZE_TIER_MERGE_EPSILON_PT == pytest.approx(0.5)
