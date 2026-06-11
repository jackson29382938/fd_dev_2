"""Tests for SettingsManager persistence behavior."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ftid_gen.settings_manager import SettingsManager


class TestSettingsPersistence(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.settings_path = Path(self.tmpdir.name) / "ftid_settings.json"

    def test_set_persists_value_to_disk(self):
        manager = SettingsManager(str(self.settings_path))
        manager.set("from_address.zip_code", "90210")

        on_disk = json.loads(self.settings_path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["from_address"]["zip_code"], "90210")

    def test_save_leaves_no_temp_file(self):
        manager = SettingsManager(str(self.settings_path))
        manager.set("from_address.zip_code", "10001")

        leftovers = [
            name for name in os.listdir(self.tmpdir.name) if name.endswith(".tmp")
        ]
        self.assertEqual(leftovers, [])

    def test_corrupt_settings_backed_up_and_defaults_loaded(self):
        self.settings_path.write_text("{not valid json", encoding="utf-8")

        manager = SettingsManager(str(self.settings_path))

        backup = self.settings_path.with_suffix(".json.corrupt")
        self.assertTrue(backup.exists())
        self.assertEqual(backup.read_text(encoding="utf-8"), "{not valid json")
        # Defaults should be usable after recovery
        self.assertIsNotNone(manager.get("from_address.zip_code"))

    def test_missing_keys_merged_from_defaults(self):
        self.settings_path.write_text(
            json.dumps({"from_address": {"zip_code": "33101"}}), encoding="utf-8"
        )

        manager = SettingsManager(str(self.settings_path))

        self.assertEqual(manager.get("from_address.zip_code"), "33101")
        # Keys absent from the stored file should come from defaults
        self.assertIsNotNone(manager.get("ui.theme"))


if __name__ == "__main__":
    unittest.main()
