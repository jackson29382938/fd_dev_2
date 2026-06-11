"""
Tests for backend health diagnostics.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest

from ftid_gen.health_check import run_health_diagnostics


class TestHealthDiagnostics(unittest.TestCase):
    def test_health_diagnostics_returns_structured_result(self):
        result = run_health_diagnostics()
        self.assertIn("ok", result)
        self.assertIn("issues", result)
        self.assertIn("warnings", result)
        self.assertIn("checks", result)
        self.assertIsInstance(result["issues"], list)
        self.assertIsInstance(result["warnings"], list)


if __name__ == "__main__":
    unittest.main()
