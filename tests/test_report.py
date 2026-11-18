# SPDX-License-Identifier: Apache-2.0
"""Offline evidence-review tests. Zero model calls."""
import json
import tempfile
import unittest
from pathlib import Path

from hiergoal.report import compile_report, EvidenceError


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def good_case(directory):
    first = ["invalid_rows", "blank_rows", "decimal_exactness"]
    second = ["half_even", "refund_sort", "cli"]
    state = {
        "root": {"id": "G0", "status": "completed"},
        "milestones": [
            {"id": "M1", "status": "completed",
             "verification": {"passed": True, "tests_run": 3, "checks": first,
                              "evidence_file": "gate-parent-M1.json"}},
            {"id": "M2", "status": "completed",
             "verification": {"passed": True, "tests_run": 3, "checks": second,
                              "evidence_file": "gate-parent-M2.json"}},
        ],
        "leaves": {
            "S1": {"id": "S1", "status": "completed", "checks": first,
                   "history": [{"action": "executed", "gate_pass": True,
                                "evidence_file": "gate-S1-after.json"}]},
            "S2": {"id": "S2", "status": "completed", "checks": second,
                   "history": [{"action": "preverified", "gate_pass": True,
                                "evidence_file": "gate-S2-before.json"}]},
        },
        "replans": 1,
    }
    records = {
        "experiment": "demo", "provider": "opencode-free-acp",
        "model": "opencode/glm-5.3-flash-free",
        "profile": "hiergoal-free",
        "outcome": "PASS", "original_visible_tests_unchanged": True,
        "parent_acceptance_verified": True,
        "final_independent": {"passed": True, "tests_run": 6},
        "final_visible": {"passed": True, "tests_run": 3},
        "estimated_visible_usd": None,
        "calls": [{"index": 1, "role": "plan", "exit_code": 0,
                   "elapsed_seconds": 3, "token_usage_measured": False,
                   "nested_todo_observed": False}],
    }
    save(directory / "state.json", state)
    save(directory / "records.json", records)
    save(directory / "gate-final-independent.json", {"passed": True, "tests_run": 6})
    save(directory / "final-visible.json", {"passed": True, "tests_run": 3})
    for name in ("gate-parent-M1.json", "gate-parent-M2.json",
                 "gate-S1-after.json", "gate-S2-before.json"):
        save(directory / name, {"passed": True, "tests_run": 3,
                                "expected_tests": 3})
    save(directory / "01-plan.stream.jsonl", {
        "type": "result", "exit_code": 0, "text": "Completed",
        "tokens": {"input": 0, "output": 0}
    })


class PublicReportTests(unittest.TestCase):
    def test_complete_case_preserves_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            good_case(directory)
            result = compile_report(directory)
            self.assertEqual(result["verified_report_outcome"], "PASS")
            self.assertEqual(result["hermes_calls_with_readable_streams"], 1)
            self.assertIsNone(result["estimated_visible_usd"])
            self.assertFalse(result["token_usage_measured_on_all_calls"])
            self.assertNotIn("Completed", json.dumps(result))

    def test_missing_parent_evidence_downgrades_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            good_case(directory)
            (directory / "gate-parent-M2.json").unlink()
            result = compile_report(directory)
            self.assertEqual(result["verified_report_outcome"], "UNCERTAIN")
            self.assertIn("pass_claim_missing_acceptance_evidence", result["evidence_issues"])
            self.assertFalse(result["parent_acceptance_evidence_verified"])

    def test_missing_leaf_evidence_downgrades_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            good_case(directory)
            (directory / "gate-S1-after.json").unlink()
            result = compile_report(directory)
            self.assertEqual(result["verified_report_outcome"], "UNCERTAIN")
            self.assertFalse(result["leaf_acceptance_evidence_verified"])

    def test_missing_trace_downgrades_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            good_case(directory)
            (directory / "01-plan.stream.jsonl").unlink()
            result = compile_report(directory)
            self.assertEqual(result["verified_report_outcome"], "UNCERTAIN")
            self.assertIn("missing_hermes_stream", result["evidence_issues"])

    def test_false_pass_downgraded_by_evaluator(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            good_case(directory)
            save(directory / "gate-final-independent.json", {"passed": False, "tests_run": 6})
            result = compile_report(directory)
            self.assertEqual(result["verified_report_outcome"], "UNCERTAIN")
            self.assertIn("pass_claim_missing_acceptance_evidence", result["evidence_issues"])

    def test_malformed_metadata_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            save(directory / "state.json", {"root": {}})
            (directory / "records.json").write_text("not-json", encoding="utf-8")
            with self.assertRaises(EvidenceError):
                compile_report(directory)


if __name__ == "__main__":
    unittest.main()
