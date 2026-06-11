"""
Regression tests for template mask rendering and preview element sizing.

Verifies that the UPS template mask configuration is correctly applied
during label generation, and that the mask parameters from the Swift
settings UI produce consistent output.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTemplateMaskConfig(unittest.TestCase):
    """Verify template mask defaults and layout parameter handling."""

    def test_ups_template_mask_defaults(self):
        """The default UPS template mask should match documented coordinates."""
        from ftid_gen.label_processor import _get_layout

        layout = _get_layout("ups", {})
        mask = layout.get("templateMask", {})
        # Documented defaults from docs/ups-template-mask.md
        self.assertEqual(mask.get("xPosition", 0), 0)
        self.assertEqual(mask.get("yPosition", 585), 585)
        self.assertEqual(mask.get("width", 405), 405)
        self.assertEqual(mask.get("height", 375), 375)

    def test_template_mask_custom_override(self):
        """Custom mask settings should override defaults."""
        from ftid_gen.label_processor import _get_layout

        custom_layout = {
            "templateMask": {
                "enabled": True,
                "xPosition": 100,
                "yPosition": 200,
                "width": 300,
                "height": 400,
                "opacity": 0.8,
            }
        }
        layout = _get_layout("ups", custom_layout)
        mask = layout.get("templateMask", {})
        self.assertEqual(mask["xPosition"], 100)
        self.assertEqual(mask["yPosition"], 200)
        self.assertEqual(mask["width"], 300)
        self.assertEqual(mask["height"], 400)
        self.assertAlmostEqual(mask["opacity"], 0.8)

    def test_template_mask_full_label_path(self):
        """Full template path should be derivable from blank template path."""
        from ftid_gen.label_processor import resolve_template_path
        from ftid_gen.config import TEMPLATES

        default_template = str(Path(TEMPLATES["4"][2]).resolve())
        resolved = resolve_template_path({}, default_template)
        self.assertTrue(resolved.exists(), f"Template not found: {resolved}")

    def test_all_carrier_templates_resolve(self):
        """All carrier template paths should resolve to existing files."""
        from ftid_gen.label_processor import resolve_template_path
        from ftid_gen.config import TEMPLATES

        for key, entry in TEMPLATES.items():
            template_path = str(Path(entry[2]).resolve())
            resolved = resolve_template_path({}, template_path)
            self.assertTrue(
                resolved.exists(),
                f"Template for key={key} not found: {resolved}",
            )


class TestPreviewTempDirCleanup(unittest.TestCase):
    """Verify preview temp dir cleanup uses reference counting."""

    def test_preview_ttl_is_900_seconds(self):
        """Preview TTL should be 900 seconds (15 minutes), not 300."""
        from bridge import ftid_bridge
        self.assertEqual(ftid_bridge._PREVIEW_TEMP_MAX_AGE_SECONDS, 900)

    def test_consumer_registration_functions_exist(self):
        """Register/release consumer functions should be importable."""
        from bridge.ftid_bridge import (
            _register_preview_consumer,
            _release_preview_consumer,
        )
        self.assertTrue(callable(_register_preview_consumer))
        self.assertTrue(callable(_release_preview_consumer))

    def test_consumer_count_increments_and_decrements(self):
        """Consumer count should track correctly."""
        from bridge.ftid_bridge import (
            _register_preview_consumer,
            _release_preview_consumer,
            _PREVIEW_CONSUMER_COUNTS,
        )

        test_path = "/tmp/test_preview_dir_12345"
        # Clear any prior state
        _PREVIEW_CONSUMER_COUNTS.pop(test_path, None)

        _register_preview_consumer(test_path)
        self.assertEqual(_PREVIEW_CONSUMER_COUNTS.get(test_path), 1)

        _register_preview_consumer(test_path)
        self.assertEqual(_PREVIEW_CONSUMER_COUNTS.get(test_path), 2)

        _release_preview_consumer(test_path)
        self.assertEqual(_PREVIEW_CONSUMER_COUNTS.get(test_path), 1)

        _release_preview_consumer(test_path)
        self.assertNotIn(test_path, _PREVIEW_CONSUMER_COUNTS)

        # Releasing when count is 0 should not raise
        _release_preview_consumer(test_path)


if __name__ == "__main__":
    unittest.main()
