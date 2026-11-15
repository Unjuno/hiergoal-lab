# SPDX-License-Identifier: Apache-2.0
"""End-to-end runner tests using a fake binary; no OpenAI/Hermes API access."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_hermes.py"

FAKE_HERMES = r'''#!/usr/bin/env python3
import json, sys
from pathlib import Path

args = sys.argv[1:]
must_have = ["chat", "--provider", "--model", "--format", "stream-json",
             "--query-file", "--oneshot", "--in"]
if any(arg not in args for arg in must_have):
    sys.stderr.write("Bad Hermes invocation: " + repr(args))
    raise SystemExit(3)
q = Path(args[args.index("--query-file") + 1])
workspace = Path(args[args.index("--in") + 1])
if not q.is_file() or not workspace.is_dir():
    raise SystemExit(4)
if "--remove-test" in sys.argv:
    (workspace / "tests" / "test_visible.py").unlink()
print(json.dumps({"type": "system", "subtype": "init",
                  "model": args[args.index("--model") + 1],
                  "session_id": "mock-123", "timestamp": 1}))
print(json.dumps({"type": "tool_use", "name": "terminal",
                  "timestamp": 2}))
print(json.dumps({"type": "tool_result", "name": "terminal",
                  "is_error": False, "timestamp": 3}))
print(json.dumps({"type": "result", "session_id": "mock-123", "exit_code": 0,
                  "tokens": {"input": 100, "output": 50, "total": 150},
                  "duration_ms": 10, "timestamp": 4}))
'''


class RunnerIntegration(unittest.TestCase):
    def run_fake(self, tamper=False):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            fake = base / "fake-hermes"
            fake.write_text(FAKE_HERMES.replace("if \"--remove-test\" in sys.argv:",
                                               f"if {str(tamper)}:"), encoding="utf-8")
            fake.chmod(0o755)
            result = subprocess.run([
                sys.executable, str(RUNNER), "--hermes", str(fake),
                "--output", str(base / "runs"), "--timeout-seconds", "30",
                "--max-turns", "5",
            ], capture_output=True, text=True, timeout=55)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            summary_files = list((base / "runs").glob("*/summary.json"))
            self.assertEqual(len(summary_files), 1, result.stdout)
            return json.loads(summary_files[0].read_text(encoding="utf-8"))

    def test_fake_hermes_is_fail_not_false_success(self):
        summary = self.run_fake(tamper=False)
        self.assertEqual(summary["verdict"], "FAIL")
        self.assertTrue(summary["stream"]["terminal_result_seen"])
        self.assertEqual(summary["visible_tests_run"], 3)
        self.assertEqual(summary["independent_tests_run"], 6)
        self.assertTrue(summary["original_visible_tests_unchanged"])
        self.assertFalse(summary["independent_tests_pass"])

    def test_agent_removed_visible_tests_is_detected(self):
        summary = self.run_fake(tamper=True)
        self.assertFalse(summary["original_visible_tests_unchanged"])
        self.assertEqual(summary["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()
