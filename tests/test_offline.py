# SPDX-License-Identifier: Apache-2.0
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_hermes import check_tests, diff_workspace
from stream_report import parse_events


class TestOffline(unittest.TestCase):
    def test_stream_success(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.jsonl"
            rows = [{"type": "system", "subtype": "init", "model": "gpt-6-luna", "session_id": "s1"},
                    {"type": "tool_use", "name": "terminal", "timestamp": 123},
                    {"type": "tool_result", "name": "terminal", "is_error": True},
                    {"type": "result", "exit_code": 0, "session_id": "s1",
                     "tokens": {"input": 1000, "output": 200, "total": 1200}}]
            path.write_text("\n".join(map(json.dumps, rows)), encoding="utf-8")
            report = parse_events(path)
            self.assertEqual(report["tool_calls"], 1)
            self.assertEqual(report["tool_failures"], 1)
            self.assertEqual(report["tokens_total"], 1200)
            self.assertTrue(report["terminal_result_seen"])

    def test_missing_final_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.jsonl"
            path.write_text('{"type":"text","text":"working"}\n', encoding="utf-8")
            self.assertFalse(parse_events(path)["terminal_result_seen"])

    def test_initial_fixture_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp) / "case"
            shutil.copytree(ROOT / "fixtures" / "ledger_release", work)
            self.assertFalse(check_tests(work, work / "tests")["ok"])

    def test_independent_evaluator_fails_initial_fixture(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp) / "case"
            shutil.copytree(ROOT / "fixtures" / "ledger_release", work)
            self.assertFalse(check_tests(work, ROOT / "evaluation")["ok"])
            self.assertFalse((work / "evaluation").exists())

    def test_workspace_diff(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp) / "case"
            shutil.copytree(ROOT / "fixtures" / "ledger_release", work)
            (work / "miniledger" / "summary.py").write_text("# replacement\n", encoding="utf-8")
            self.assertIn("replacement", diff_workspace(ROOT / "fixtures" / "ledger_release", work))


if __name__ == "__main__":
    unittest.main()
