"""Tests for the Excel importer batch processing and value normalization."""
import os
import sys
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ftid_gen.excel_importer import (
    ExcelImporter,
    _clean_import_text,
    _normalize_import_zip,
)


class TestImportValueCleaning(unittest.TestCase):
    def test_clean_import_text_strips_and_drops_nulls(self):
        self.assertEqual(_clean_import_text("  hello  "), "hello")
        self.assertEqual(_clean_import_text(None), "")
        self.assertEqual(_clean_import_text("nan"), "")
        self.assertEqual(_clean_import_text("None"), "")
        self.assertEqual(_clean_import_text(float("nan")), "")

    def test_clean_import_text_removes_float_suffix(self):
        self.assertEqual(_clean_import_text("10001.0"), "10001")
        self.assertEqual(_clean_import_text("1.5"), "1.5")

    def test_normalize_import_zip_pads_leading_zeros(self):
        self.assertEqual(_normalize_import_zip("1234"), "01234")
        self.assertEqual(_normalize_import_zip("90210"), "90210")
        self.assertEqual(_normalize_import_zip(""), "")

    def test_normalize_import_zip_handles_plus_four(self):
        self.assertEqual(_normalize_import_zip("1234-5678"), "01234-5678")
        self.assertEqual(_normalize_import_zip("90210-1234"), "90210-1234")


class TestProcessBatchSkippedRows(unittest.TestCase):
    MAPPINGS = {
        "tracking_number": "tracking",
        "sender_zip": "sender_zip",
        "receiver_zip": "receiver_zip",
    }

    def _make_importer(self):
        importer = ExcelImporter()
        address = {
            "name": "Test Person",
            "address": "1 Test St",
            "city": "Testville",
            "state": "TS",
            "zip_code": "10001",
        }
        patcher_addr = patch.object(
            ExcelImporter, "_generate_address_info", return_value=address
        )
        patcher_track = patch.object(
            ExcelImporter, "_generate_modified_tracking", return_value="1ZMODIFIED"
        )
        patcher_addr.start()
        patcher_track.start()
        self.addCleanup(patcher_addr.stop)
        self.addCleanup(patcher_track.stop)
        return importer

    def test_valid_rows_processed_without_skips(self):
        importer = self._make_importer()
        df = pd.DataFrame(
            {
                "tracking": ["1Z9999W99999999999"],
                "sender_zip": ["10001"],
                "receiver_zip": ["90210"],
            }
        )
        results = importer.process_batch(df, self.MAPPINGS)
        self.assertEqual(len(results), 1)
        self.assertEqual(importer.last_skipped_rows, [])

    def test_rows_with_missing_data_are_reported(self):
        importer = self._make_importer()
        df = pd.DataFrame(
            {
                "tracking": ["1Z9999W99999999999", ""],
                "sender_zip": ["10001", "10001"],
                "receiver_zip": ["90210", "90210"],
            }
        )
        results = importer.process_batch(df, self.MAPPINGS)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(importer.last_skipped_rows), 1)
        skipped = importer.last_skipped_rows[0]
        self.assertEqual(skipped["row_number"], 2)
        self.assertIn("tracking number", skipped["reason"])

    def test_skipped_rows_reset_between_batches(self):
        importer = self._make_importer()
        bad_df = pd.DataFrame(
            {"tracking": [""], "sender_zip": ["10001"], "receiver_zip": ["90210"]}
        )
        importer.process_batch(bad_df, self.MAPPINGS)
        self.assertEqual(len(importer.last_skipped_rows), 1)

        good_df = pd.DataFrame(
            {
                "tracking": ["1Z9999W99999999999"],
                "sender_zip": ["10001"],
                "receiver_zip": ["90210"],
            }
        )
        importer.process_batch(good_df, self.MAPPINGS)
        self.assertEqual(importer.last_skipped_rows, [])


if __name__ == "__main__":
    unittest.main()
