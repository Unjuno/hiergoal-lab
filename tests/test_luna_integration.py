# SPDX-License-Identifier: Apache-2.0
"""Full Luna backend rehearsal with a fake Hermes executable, no API or key.

Covers actual CLI argument construction, JSONL events, token-based soft budget,
independent gates, bounded replanning, and final classification.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_hiergoal_controller import make_fake

ROOT = Path(__file__).resolve().parents[1]


class LunaSimulatedIntegration(unittest.TestCase):
    def invoke(self, budget="3", max_calls="10", add_paid_consent=True):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            fake_hermes = base / "mock-hermes"
            make_fake(fake_hermes, backend="luna")
            command = [
                sys.executable, "-m", "hiergoal.controller",
                "--hermes", str(fake_hermes), "--backend", "luna",
                "--output", str(base / "runs"), "--max-calls", max_calls,
                "--max-replans", "1", "--timeout-seconds", "40",
                "--pilot-budget-usd", budget, "--ack-unsandboxed",
            ]
            if add_paid_consent:
                command.append("--approve-paid-api")
            env = os.environ.copy()
            env["HOME"] = str(base)
            env.pop("OPENAI_API_KEY", None)
            env.pop("HERMES_HOME", None)
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                    text=True, timeout=80)
            run_dirs = list((base / "runs").glob("hiergoal-*")) if (base / "runs").exists() else []
            records = state = None
            if run_dirs:
                run_dir = run_dirs[0]
                if (run_dir / "records.json").exists():
                    records = json.loads((run_dir / "records.json").read_text(encoding="utf-8"))
                if (run_dir / "state.json").exists():
                    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
            return result, records, state

    def test_luna_complete_hierarchical_flow(self):
        process, records, state = self.invoke()
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(records["provider"], "openai-api")
        self.assertEqual(records["model"], "gpt-6-luna")
        self.assertIsNone(records["profile"])
        self.assertEqual(records["outcome"], "PASS")
        self.assertTrue(records["parent_acceptance_verified"])
        self.assertEqual(state["root"]["status"], "completed")
        self.assertEqual(state["replans"], 1)
        self.assertEqual(state["leaves"]["S1"]["status"], "superseded")
        self.assertTrue(records["token_usage_available"])
        self.assertGreater(records["estimated_visible_usd"], 0)
        self.assertTrue(all(call["token_usage_measured"] for call in records["calls"]))
        self.assertEqual(records["final_independent"]["tests_run"], 6)

    def test_soft_budget_stops_after_first_recorded_call(self):
        process, records, state = self.invoke(budget="0.000001")
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(records["outcome"], "UNCERTAIN")
        self.assertEqual(len(records["calls"]), 1)
        self.assertEqual(records["provider"], "openai-api")
        self.assertGreater(records["estimated_visible_usd"], 0)
        self.assertIn("budget reached", records["halt_reason"])
        self.assertIsNone(state)

    def test_paid_route_requires_explicit_consent(self):
        process, records, state = self.invoke(add_paid_consent=False)
        self.assertEqual(process.returncode, 2)
        self.assertIsNone(records)
        self.assertIn("--approve-paid-api", process.stderr)

    def test_call_budget_does_not_invoke_unbounded_steps(self):
        process, records, state = self.invoke(max_calls="1")
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(records["outcome"], "UNCERTAIN")
        self.assertEqual(len(records["calls"]), 1)
        self.assertIn("max-calls guard", records["halt_reason"])


if __name__ == "__main__":
    unittest.main()
