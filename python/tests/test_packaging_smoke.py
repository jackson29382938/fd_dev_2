"""
Packaging smoke tests: verify bundled backend resources exist.

These tests simulate what a release build validation script would check
before packaging the macOS app bundle. They verify that all required
backend files are present and that the Python import chain works end-to-end.
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


class TestBundledBackendResources(unittest.TestCase):
    """Verify that every file the bundled backend needs is present."""

    def setUp(self):
        # Ensure config loads correctly (sets up BASE_DIR, OUTPUT_DIR, etc.)
        from ftid_gen import config
        self.base_dir = config.BASE_DIR
        self.output_dir = config.OUTPUT_DIR

    def test_base_dir_exists(self):
        self.assertTrue(self.base_dir.is_dir(), f"BASE_DIR missing: {self.base_dir}")

    def test_template_images_exist(self):
        from ftid_gen.config import TEMPLATES
        for key, entry in TEMPLATES.items():
            template_path = self.base_dir / entry[2]
            self.assertTrue(
                template_path.exists(),
                f"Template image missing for {key}: {template_path}",
            )

    def test_font_files_exist(self):
        from ftid_gen.config import FONT_MAIN, FONT_BOLD, FONT_ARIAL
        for font_path in (FONT_MAIN, FONT_BOLD, FONT_ARIAL):
            self.assertTrue(font_path.exists(), f"Font missing: {font_path}")

    def test_zipcodes_file_exists(self):
        from ftid_gen.config import ZIPCODE_FILE
        self.assertTrue(ZIPCODE_FILE.exists(), f"ZIP code data missing: {ZIPCODE_FILE}")

    def test_output_dir_is_writable(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.assertTrue(os.access(self.output_dir, os.W_OK))

    def test_python_import_chain(self):
        """Every backend module should import without error."""
        import importlib
        modules = [
            "ftid_gen.config",
            "ftid_gen.address_utils",
            "ftid_gen.data_storage",
            "ftid_gen.label_processor",
            "ftid_gen.settings_manager",
            "ftid_gen.health_check",
            "ftid_gen.excel_importer",
            "ftid_gen.tracking_utils",
            "ftid_gen.tracking_fetcher",
            "ftid_gen.tracking_models",
            "ftid_gen.render.barcodes",
            "ftid_gen.render.text_overlay",
            "bridge.ftid_bridge",
        ]
        for mod_name in modules:
            with self.subTest(module=mod_name):
                importlib.import_module(mod_name)

    def test_maxicode_pure_import(self):
        """The pure-Python MaxiCode encoder should be importable."""
        from maxicode.pure_maxicode import generate_maxicode_image, encode_maxicode
        self.assertTrue(callable(generate_maxicode_image))
        self.assertTrue(callable(encode_maxicode))

    def test_name_lists_nonempty(self):
        """Name lists should be populated with at least 1000 entries each."""
        from ftid_gen.config import FIRST_NAMES, LAST_NAMES
        self.assertGreaterEqual(len(FIRST_NAMES), 1000)
        self.assertGreaterEqual(len(LAST_NAMES), 1000)
        self.assertEqual(len(FIRST_NAMES), len(set(FIRST_NAMES)), "Duplicate first names")
        self.assertEqual(len(LAST_NAMES), len(set(LAST_NAMES)), "Duplicate last names")

    def test_health_check_runs(self):
        """Health diagnostics should execute without raising."""
        from ftid_gen.health_check import run_health_diagnostics
        result = run_health_diagnostics()
        self.assertIn("ok", result)
        self.assertIn("issues", result)
        self.assertIn("warnings", result)
        self.assertIn("checks", result)

    def test_optional_integrations_reported(self):
        """Health check should report optional integration status."""
        from ftid_gen.health_check import run_health_diagnostics
        result = run_health_diagnostics()
        checks = result["checks"]
        optional_keys = [k for k in checks if k.startswith("optional.")]
        self.assertGreaterEqual(
            len(optional_keys), 4,
            f"Expected at least 4 optional integration checks, got {len(optional_keys)}: {optional_keys}",
        )


if __name__ == "__main__":
    unittest.main()
