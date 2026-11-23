# SPDX-License-Identifier: Apache-2.0
"""CI smoke acceptance, paid boundaries and actual subprocess orchestration."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hiergoal.ci import SMOKE_REPLY, execute, inspect_smoke, metadata
from hiergoal.ci_report import collect_results
from tests.test_hiergoal_controller import make_fake

ROOT = Path(__file__).resolve().parents[1]


class SmokeEvidenceTests(unittest.TestCase):
    def inspect(self, *, exit_code=0, text=SMOKE_REPLY, tokens=None, error=None, replay=False, tool=False):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stream.jsonl"
            events = [{"type": "system", "subtype": "init", "model": "gpt-6-luna"}]
            if tool:
                events.append({"type": "tool_use", "name": "terminal"})
            events.append({"type": "result", "exit_code": exit_code, "text": text,
                           "tokens": tokens if tokens is not None else {"input": 100, "output": 10},
                           "error": error, "replay_gap": replay})
            path.write_text("\n".join(json.dumps(event) for event in events))
            return inspect_smoke(path, exit_code, 1.0)

    def test_complete_smoke_and_measured_usage(self):
        result = self.inspect()
        self.assertEqual(result["status"], "PASS")
        self.assertGreater(result["estimated_visible_usd"], 0)

    def test_non_text_response_is_not_success_or_crash(self):
        for text in (None, [], {}, 1, "not the requested marker"):
            with self.subTest(text=text):
                self.assertEqual(self.inspect(text=text)["status"], "UNCERTAIN")

    def test_missing_malformed_and_boolean_tokens_are_unknown(self):
        for tokens in ({}, {"input": True, "output": True}, [], [1], "bad"):
            with self.subTest(tokens=tokens):
                result = self.inspect(tokens=tokens)
                self.assertEqual(result["status"], "UNCERTAIN")
                self.assertIsNone(result["estimated_visible_usd"])

    def test_api_errors_trace_gaps_and_tool_calls_never_pass(self):
        self.assertEqual(self.inspect(exit_code=1)["status"], "FAIL")
        self.assertEqual(self.inspect(error="do not publish this provider body")["status"], "FAIL")
        self.assertEqual(self.inspect(replay=True)["status"], "UNCERTAIN")
        self.assertEqual(self.inspect(tool=True)["status"], "UNCERTAIN")


class CIRunnerTests(unittest.TestCase):
    def test_key_and_opt_in_required_before_paid_launch(self):
        for consent in (False, True):
            with self.subTest(consent=consent), tempfile.TemporaryDirectory() as tmp:
                args = argparse.Namespace(output=Path(tmp), mode="smoke", hermes="hermes",
                                          soft_budget_usd=1, approve_paid_api=consent)
                state = metadata("smoke", 1)
                with patch("hiergoal.ci.check_cli", return_value=(True, "Hermes fake")), \
                     patch("hiergoal.ci.supervised") as invoke, \
                     patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
                    self.assertEqual(execute(args, state), 2)
                    invoke.assert_not_called()
                self.assertEqual(state["diagnostic_code"], "MISSING_OPENAI_API_KEY" if consent else "PAID_OPT_IN_REQUIRED")

    @unittest.skipUnless(sys.platform.startswith("linux"), "The hosted CI adapter requires Linux")
    def test_fake_pilot_through_ci_wrapper_and_exporter(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            real = base / "synthetic-hermes"
            impl = base / "fixture-hermes"
            make_fake(impl, backend="luna")
            real.write_text(
                "#!/usr/bin/env python3\nimport json, os, sys\nfrom pathlib import Path\n"
                "from runpy import run_path\n"
                "args = sys.argv[1:]\n"
                "if args == ['--version']:\n print('Hermes Agent synthetic'); sys.exit(0)\n"
                "if args == ['chat', '--help']:\n print('--provider --model --reasoning --ignore-user-config --ignore-rules --toolsets --source --in --format --max-turns --query-file --oneshot'); sys.exit(0)\n"
                "if args == ['gateway', 'stop', '--yes']:\n sys.exit(0)\n"
                "prompt = Path(args[args.index('--query-file') + 1]).read_text()\n"
                "if prompt.startswith('Reply with exactly HIERGOAL_API_OK'):\n"
                " assert args[args.index('--toolsets') + 1] == ''\n"
                " assert args[args.index('--source') + 1] == 'tool'\n"
                " print(json.dumps({'type':'system','subtype':'init','model':'gpt-6-luna'}))\n"
                " print(json.dumps({'type':'result','exit_code':0,'text':'HIERGOAL_API_OK','tokens':{'input':100,'output':10}})); sys.exit(0)\n"
                f"run_path({str(impl)!r}, run_name='__main__')\n", encoding="utf-8")
            real.chmod(0o755)
            output = base / "ci"
            env = os.environ.copy()
            env.update(OPENAI_API_KEY="synthetic-no-network-key", OPENAI_BASE_URL="https://api.openai.com/v1")
            command = [sys.executable, "-m", "hiergoal.ci", "--mode", "pilot",
                       "--output", str(output), "--hermes", str(real), "--approve-paid-api"]
            proc = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            result = collect_results(output)
            self.assertEqual(result["workflow_conclusion"], "PASS")
            self.assertEqual(result["connection_status"], "PASS")
            self.assertEqual(result["benchmark_summary"]["executed"], 1)
            self.assertEqual(result["benchmark_summary"]["pass"], 1)
            self.assertEqual(result["benchmark_summary"]["engineering_target"], "NOT_APPLICABLE")
            receipts = list((output / "private/homes").glob("*/ci-cleanup.json"))
            self.assertGreaterEqual(len(receipts), 2)
            self.assertTrue(all(json.loads(p.read_text())["cleanup_confirmed"] for p in receipts))
            repeated = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(repeated.returncode, 2)
            self.assertIn("already executed", repeated.stderr)


if __name__ == "__main__":
    unittest.main()
