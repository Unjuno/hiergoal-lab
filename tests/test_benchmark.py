# SPDX-License-Identifier: Apache-2.0
"""Benchmark orchestration tests that never invoke a real Hermes provider."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from hiergoal.benchmark import make_schedule, summarize_batch
from hiergoal.cases import CASE_IDS
from tests.test_hiergoal_controller import make_fake

ROOT = Path(__file__).resolve().parents[1]


class BenchmarkPlanTests(unittest.TestCase):
    def test_schedule_reproducible_and_balanced(self):
        first = make_schedule(list(CASE_IDS), 2, 31415)
        second = make_schedule(list(CASE_IDS), 2, 31415)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 8)
        self.assertEqual(
            sorted((task["case_id"], task["repetition"]) for task in first),
            sorted((case_id, repetition)
                   for case_id in CASE_IDS for repetition in (1, 2)),
        )

    def test_reject_duplicate_or_unknown_case(self):
        for ids in (["legacy", "legacy"], ["not-known"], []):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                make_schedule(ids, 2, 1)

    def test_default_is_plan_only_and_not_billed(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "benchmarks"
            result = subprocess.run([
                sys.executable, "-m", "hiergoal.benchmark",
                "--output", str(output),
            ], cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["mode"], "PLAN_ONLY; ZERO model calls")
            self.assertEqual(data["scheduled"], 8)
            self.assertFalse(output.exists())


class BenchmarkIntegrationTests(unittest.TestCase):
    def run_fake(self, cases="legacy,parser_ready", budget="2.0",
                 consent=True, ack=True):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fake = root / "mock-hermes"
            make_fake(fake, backend="luna")
            out = root / "benchmarks"
            command = [
                sys.executable, "-m", "hiergoal.benchmark",
                "--run", "--backend", "luna", "--cases", cases,
                "--repetitions", "1", "--hermes", str(fake),
                "--output", str(out), "--max-calls", "10",
                "--max-replans", "1", "--timeout-seconds", "30",
                "--total-soft-budget-usd", budget,
                "--per-case-soft-budget-usd", budget,
            ]
            if consent:
                command.append("--approve-paid-api")
            if ack:
                command.append("--ack-unsandboxed")
            env = os.environ.copy()
            env["HOME"] = str(root)
            env.pop("OPENAI_API_KEY", None)
            env.pop("HERMES_HOME", None)
            result = subprocess.run(command, cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=120)
            dirs = list(out.glob("benchmark-*")) if out.exists() else []
            summary = summarize_batch(dirs[0]) if len(dirs) == 1 else None
            return result, dirs, summary

    def test_full_batch_with_fake_hermes(self):
        result, dirs, summary = self.run_fake()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(summary["executed"], 2)
        self.assertEqual(summary["pass"], 2)
        self.assertEqual(summary["fail"], 0)
        self.assertEqual(summary["uncertain"], 0)
        self.assertEqual(summary["run_plan"]["scheduled"], 2)
        self.assertEqual(summary["engineering_target"], "NOT_APPLICABLE")
        self.assertEqual(summary["not_run"], 0)
        self.assertGreaterEqual(summary["observed_total_subgoals"], 6)
        self.assertEqual(summary["observed_total_subgoals"], summary["observed_completed_subgoals"])
        self.assertGreaterEqual(summary["observed_verified_milestones"], 4)
        self.assertGreaterEqual(summary["observed_replans"], 1)
        self.assertGreaterEqual(summary["verified_pass_after_replan"], 1)
        self.assertTrue(summary["token_telemetry_complete"])
        self.assertGreater(summary["estimated_visible_total_usd"], 0)
        self.assertTrue(all(item["verified_evidence"] for item in summary["per_case"]))
        self.assertEqual({row["case_id"] for row in summary["per_case"]},
                         {"legacy", "parser_ready"})

    def test_paid_batch_refuses_without_explicit_consent(self):
        result, dirs, summary = self.run_fake(consent=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--approve-paid-api", result.stderr)
        self.assertEqual(dirs, [])

    def test_paid_batch_refuses_without_os_risk_ack(self):
        result, dirs, summary = self.run_fake(ack=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--ack-unsandboxed", result.stderr)
        self.assertEqual(dirs, [])

    def test_aggregate_budget_causes_early_halt(self):
        result, dirs, summary = self.run_fake(budget="0.000001")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(dirs), 1)
        self.assertLess(summary["executed"], summary["run_plan"]["scheduled"])
        self.assertTrue(summary["uncertain"] or summary["not_run"])


if __name__ == "__main__":
    unittest.main()
