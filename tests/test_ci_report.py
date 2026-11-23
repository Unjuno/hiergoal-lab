# SPDX-License-Identifier: Apache-2.0
"""CI result collection regressions; fake Hermes only, no API requests."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hiergoal.ci_report import collect_results
from tests.test_hiergoal_controller import make_fake

ROOT = Path(__file__).resolve().parents[1]


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def ready(root, mode="smoke", **updates):
    state = {"mode": mode, "status": "COMPLETE", "cli_compatible": True,
             "connection_status": "PASS", "hermes_commit": "a" * 40,
             "git_commit": "b" * 40, "python_version": "3.14.0",
             "host_os": "Linux", "host_architecture": "x86_64"}
    state.update(updates)
    save(root / "ci-state.json", state)
    save(root / "smoke.json", {"status": "PASS", "reason_code": "API_RESPONSE_VERIFIED",
         "tokens_input": 12, "tokens_output": 4, "elapsed_seconds": 0.5,
         "estimated_visible_usd": 0.0000032, "terminal_result_seen": True,
         "hermes_exit_code": 0, "init_model": "gpt-6-luna"})


def incomplete_batch(root, *, malformed=False):
    batch = root / "raw" / "benchmarks" / "benchmark-example"
    run = batch / "individual" / "task-01" / "hiergoal-example"
    save(batch / "schedule.json", {"batch_id": "example", "backend": "luna",
         "model": "gpt-6-luna", "seed": 1729, "repetitions": 1, "status": "HALTED",
         "tasks": [{"index": 1, "case_id": "legacy", "repetition": 1,
                    "run_state": "RETURNED"}]})
    save(run / "records.json", {"backend": "luna", "case_id": "legacy", "outcome": "FAIL",
         "calls": [{"index": 1, "role": "plan", "status": "incomplete",
                    "tool_calls": None, "token_usage_measured": False}],
         "estimated_visible_usd": 0.0, "halt_reason": "DO_NOT_EXPORT_RAW_REASON"})
    if malformed:
        (run / "state.json").write_text("invalid json", encoding="utf-8")
    return run


class CIReportTests(unittest.TestCase):
    def test_absent_run_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "new-run"
            result = collect_results(root)
            self.assertEqual(result["workflow_conclusion"], "NOT_RUN")
            self.assertEqual(result["connection_status"], "NOT_RUN")
            self.assertEqual(result["experiment_status"], "NOT_RUN")
            self.assertTrue((root / "results" / "summary.md").is_file())
            self.assertFalse((root / "results" / "summary.json").exists())

    def test_check_success_does_not_claim_api_connection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save(root / "ci-state.json", {"mode": "check", "status": "COMPLETE",
                 "cli_compatible": True, "connection_status": "NOT_RUN"})
            result = collect_results(root)
            self.assertEqual(result["workflow_conclusion"], "PASS")
            self.assertEqual(result["connection_status"], "NOT_RUN")
            self.assertEqual(result["experiment_status"], "NOT_RUN")

    def test_smoke_success_is_separate_from_experiment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ready(root)
            step = root / "step-summary.md"
            result = collect_results(root, step)
            self.assertEqual(result["workflow_conclusion"], "PASS")
            self.assertEqual(result["connection_status"], "PASS")
            self.assertEqual(result["experiment_status"], "NOT_RUN")
            self.assertIn("API connection | PASS", step.read_text())
            self.assertFalse((root / "results" / "summary.json").exists())

    def test_missing_smoke_evidence_downgrades_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ready(root)
            (root / "smoke.json").unlink()
            result = collect_results(root)
            self.assertEqual(result["connection_status"], "UNCERTAIN")
            self.assertEqual(result["workflow_conclusion"], "UNCERTAIN")

    def test_unexpected_reply_downgrades_connection_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ready(root)
            smoke = json.loads((root / "smoke.json").read_text())
            smoke["status"] = "UNCERTAIN"
            save(root / "smoke.json", smoke)
            result = collect_results(root)
            self.assertEqual(result["connection_status"], "UNCERTAIN")
            self.assertEqual(result["workflow_conclusion"], "UNCERTAIN")

    def test_missing_key_has_actionable_safe_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save(root / "ci-state.json", {"mode": "smoke", "status": "ERROR",
                 "connection_status": "NOT_RUN", "diagnostic_code": "MISSING_OPENAI_API_KEY"})
            result = collect_results(root)
            self.assertEqual(result["workflow_conclusion"], "FAIL")
            text = (root / "results" / "summary.md").read_text()
            self.assertIn("MISSING_OPENAI_API_KEY", text)
            self.assertIn("GitHub Actions secrets", text)

    def test_missing_or_malformed_state_exports_records_only_fallback(self):
        for malformed in (False, True):
            with self.subTest(malformed=malformed), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                ready(root, "pilot")
                incomplete_batch(root, malformed=malformed)
                result = collect_results(root)
                self.assertEqual(result["workflow_conclusion"], "UNCERTAIN")
                self.assertEqual(result["experiment_status"], "UNCERTAIN")
                row = result["benchmark_summary"]["per_case"][0]
                self.assertEqual(row["model_calls"], 1)
                self.assertIsNone(row["tool_calls"])
                self.assertIsNone(row["elapsed_hermes_seconds"])
                self.assertIsNone(row["estimated_visible_usd"])
                report = json.loads((root / "results" / "report-task-01.json").read_text())
                self.assertEqual(report["verified_report_outcome"], "UNCERTAIN")
                self.assertNotIn("DO_NOT_EXPORT_RAW_REASON", json.dumps(result) + json.dumps(report))

    def test_exact_and_generic_secrets_are_redacted_everywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "unique-credential-for-report-redaction"
            unknown_key = "sk-proj-unconfigured_secret_1234567890"
            ready(root, diagnostic_code=secret, hermes_version=unknown_key,
                  stderr="RAW_STDERR_SHOULD_NOT_APPEAR", prompts=["SECRET_PROMPT"])
            with patch.dict(os.environ, {"OPENAI_API_KEY": secret}):
                result = collect_results(root)
            serialized = json.dumps(result) + "".join(path.read_text() for path in (root / "results").iterdir())
            for forbidden in (secret, unknown_key, "RAW_STDERR_SHOULD_NOT_APPEAR", "SECRET_PROMPT"):
                self.assertNotIn(forbidden, serialized)
            self.assertIn("[REDACTED]", serialized)

    def test_symlink_input_is_not_read_or_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            root.mkdir()
            outside = Path(tmp) / "private.json"
            save(outside, {"mode": "smoke", "status": "COMPLETE", "diagnostic_code": "PRIVATE_PAYLOAD"})
            (root / "ci-state.json").symlink_to(outside)
            result = collect_results(root)
            self.assertEqual(result["workflow_conclusion"], "UNCERTAIN")
            self.assertNotIn("PRIVATE_PAYLOAD", json.dumps(result))
            self.assertIn("CI_STATE_UNREADABLE", result["diagnostic_codes"])

    def test_symlinked_batch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            ready(root, "pilot")
            outside = Path(tmp) / "outside"
            outside.mkdir()
            base = root / "raw" / "benchmarks"
            base.mkdir(parents=True)
            (base / "benchmark-symlink").symlink_to(outside, target_is_directory=True)
            result = collect_results(root)
            self.assertEqual(result["workflow_conclusion"], "UNCERTAIN")
            self.assertIn("BENCHMARK_EVIDENCE_UNREADABLE", result["diagnostic_codes"])

    def test_malformed_ci_field_types_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save(root / "ci-state.json", {"status": {}, "connection_status": [], "mode": "smoke"})
            result = collect_results(root)
            self.assertEqual(result["workflow_conclusion"], "UNCERTAIN")

    def test_fake_hermes_batch_exports_verified_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = root / "mock-hermes"
            make_fake(fake, backend="luna")
            ready(root, "pilot")
            env = os.environ.copy()
            env.pop("OPENAI_API_KEY", None)
            process = subprocess.run([
                sys.executable, "-m", "hiergoal.benchmark", "--run", "--backend", "luna",
                "--cases", "legacy", "--repetitions", "1", "--hermes", str(fake),
                "--output", str(root / "raw" / "benchmarks"), "--max-calls", "10",
                "--max-replans", "1", "--timeout-seconds", "30", "--total-soft-budget-usd", "1",
                "--per-case-soft-budget-usd", "1", "--approve-paid-api", "--ack-unsandboxed",
            ], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = collect_results(root)
            self.assertEqual(result["workflow_conclusion"], "PASS")
            self.assertEqual(result["experiment_status"], "PASS")
            row = result["benchmark_summary"]["per_case"][0]
            self.assertTrue(row["verified_evidence"])
            self.assertGreater(row["tokens_input"], 0)
            self.assertGreater(row["tokens_output"], 0)
            self.assertTrue((root / "results" / "report-task-01.json").is_file())
            csv_text = (root / "results" / "attempts.csv").read_text()
            self.assertIn("hermes_invocations", csv_text)
            self.assertIn("legacy,1,PASS", csv_text)
            # Removing raw evidence must not leave stale successful reports.
            batch = next((root / "raw" / "benchmarks").glob("benchmark-*"))
            (batch / "schedule.json").unlink()
            result = collect_results(root)
            self.assertEqual(result["workflow_conclusion"], "UNCERTAIN")
            self.assertFalse((root / "results" / "report-task-01.json").exists())
            self.assertFalse((root / "results" / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
