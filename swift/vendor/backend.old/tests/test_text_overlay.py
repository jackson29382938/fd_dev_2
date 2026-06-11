"""
Tests for label text overlay helpers.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ftid_gen.render.text_overlay import _split_city_state_zip


class TestSplitCityStateZip:
    """Tests for preserving ZIP codes in city/state/ZIP parsing."""

    def test_handles_multi_word_city(self):
        city, state, zip_code = _split_city_state_zip("Los Angeles CA 90001")

        assert city == "Los Angeles"
        assert state == "CA"
        assert zip_code == "90001"

    def test_uses_fallback_zip_for_partial_line(self):
        city, state, zip_code = _split_city_state_zip("Austin TX", fallback_zip="73301")

        assert city == "Austin"
        assert state == "TX"
        assert zip_code == "73301"
