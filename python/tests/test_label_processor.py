"""
Tests for unified label layout helpers and compositor configuration.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ftid_gen.label_processor import (
    resolve_barcode_config,
    resolve_maxicode_config,
    resolve_template_path,
    resolve_zip_barcode_config,
    _template_mask_config,
)


class TestLayoutResolvers(unittest.TestCase):
    def test_resolve_barcode_config_defaults(self):
        config = resolve_barcode_config({})
        self.assertEqual(config["module_height"], 15.0)
        self.assertEqual(config["quiet_zone"], 6.5)
        self.assertEqual(config["width"], 970)

    def test_resolve_barcode_config_overrides(self):
        config = resolve_barcode_config({"barcode": {"module_height": 20.0, "width": 800}})
        self.assertEqual(config["module_height"], 20.0)
        self.assertEqual(config["width"], 800)

    def test_resolve_maxicode_config_defaults(self):
        config = resolve_maxicode_config({})
        self.assertEqual(config["width"], 312)
        self.assertEqual(config["y_offset"], -1144)

    def test_resolve_zip_barcode_config_defaults(self):
        config = resolve_zip_barcode_config({})
        self.assertEqual(config["width"], 720)
        self.assertEqual(config["height"], 170)

    def test_resolve_template_path_prefers_custom_when_present(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            custom = root / "custom_template.png"
            custom.write_bytes(b"png")
            default = root / "ups_temp_blank.png"
            default.write_bytes(b"png")
            resolved = resolve_template_path({"custom_template_path": str(custom)}, default)
            self.assertEqual(resolved, custom)

    def test_resolve_template_path_falls_back_to_default(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            default = root / "ups_temp_blank.png"
            default.write_bytes(b"png")
            missing = root / "missing.png"
            resolved = resolve_template_path({"custom_template_path": str(missing)}, default)
            self.assertEqual(resolved, default)


class TestTemplateMaskConfig(unittest.TestCase):
    def test_ups_defaults_match_documented_mask(self):
        config = _template_mask_config("FTID_UPS", {})
        self.assertTrue(config["enabled"])
        self.assertEqual(config["x_position"], 0)
        self.assertEqual(config["y_position"], 585)
        self.assertEqual(config["width"], 405)
        self.assertEqual(config["height"], 375)
        self.assertEqual(config["opacity"], 0.9)

    def test_usps_mask_disabled_by_default(self):
        config = _template_mask_config("FTID_USPS", {})
        self.assertFalse(config["enabled"])


if __name__ == "__main__":
    unittest.main()
