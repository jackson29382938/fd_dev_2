"""Tests for the bridge's persistent --serve protocol."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "python" / "bridge" / "ftid_bridge.py"


class TestServeProtocol(unittest.TestCase):
    def _run_serve(self, request_lines):
        with tempfile.TemporaryDirectory() as state_dir:
            env = dict(os.environ)
            env["FTID_STATE_DIR"] = state_dir
            env["FTID_OUTPUT_DIR"] = state_dir
            env["FTID_NONINTERACTIVE"] = "1"
            proc = subprocess.run(
                [sys.executable, str(BRIDGE), "--serve"],
                input="\n".join(request_lines) + "\n",
                capture_output=True,
                text=True,
                env=env,
                cwd=state_dir,
                timeout=120,
            )
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        return [json.loads(line) for line in lines]

    def test_ready_handshake_then_responses_in_order(self):
        responses = self._run_serve(
            [
                json.dumps({"id": 1, "action": "settings_get", "payload": {}}),
                json.dumps({"id": 2, "action": "settings_get", "payload": {}}),
            ]
        )
        self.assertGreaterEqual(len(responses), 3)
        handshake = responses[0]
        self.assertIsNone(handshake["id"])
        self.assertTrue(handshake["ok"])

        self.assertEqual(responses[1]["id"], 1)
        self.assertTrue(responses[1]["ok"])
        self.assertEqual(responses[2]["id"], 2)
        self.assertTrue(responses[2]["ok"])

    def test_unknown_action_and_malformed_line_keep_server_alive(self):
        responses = self._run_serve(
            [
                json.dumps({"id": 7, "action": "does_not_exist", "payload": {}}),
                "{this is not json",
                json.dumps({"id": 8, "action": "settings_get", "payload": {}}),
            ]
        )
        by_id = {r["id"]: r for r in responses}

        self.assertFalse(by_id[7]["ok"])
        self.assertIn("Unknown action", by_id[7]["error"])

        malformed = [r for r in responses if r["id"] is None and not r["ok"]]
        self.assertEqual(len(malformed), 1)
        self.assertIn("Malformed request", malformed[0]["error"])

        # The server must survive the malformed line and answer request 8.
        self.assertTrue(by_id[8]["ok"])


if __name__ == "__main__":
    unittest.main()
