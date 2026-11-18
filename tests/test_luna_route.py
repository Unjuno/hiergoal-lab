# SPDX-License-Identifier: Apache-2.0
"""Luna route selection cannot silently replace free ACP or make an unapproved paid call."""
import os
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from hiergoal.controller import (DEFAULT_MODEL, LUNA_MODEL, hermes_arguments,
                                 resolve_route)

ROOT = Path(__file__).resolve().parents[1]


def opts(**params):
    data = {"backend": "free", "model": None, "hermes": "hermes",
            "max_turns": 18, "pilot_budget_usd": 3}
    data.update(params)
    return Namespace(**data)


class LunaBackendSafety(unittest.TestCase):
    def test_free_default_keeps_named_profile(self):
        provider, profile, model = resolve_route(opts())
        self.assertEqual((provider, profile, model),
                         ("opencode-free-acp", "hiergoal-free", DEFAULT_MODEL))
        command = hermes_arguments(opts(), Path("/tmp/work"), Path("/tmp/prompt"), "todo")
        self.assertEqual(command[:5], ["hermes", "-p", "hiergoal-free", "chat", "--provider"])
        self.assertNotIn("--ignore-user-config", command)

    def test_luna_route_uses_direct_api_and_isolated_config(self):
        args = opts(backend="luna")
        self.assertEqual(resolve_route(args), ("openai-api", None, LUNA_MODEL))
        cmd = hermes_arguments(args, Path("/tmp/work"), Path("/tmp/prompt"), "file,terminal,todo")
        self.assertEqual(cmd[:4], ["hermes", "chat", "--provider", "openai-api"])
        self.assertIn("--ignore-user-config", cmd)
        self.assertIn("gpt-6-luna", cmd)
        self.assertNotIn("hiergoal-free", cmd)

    def test_luna_does_not_accept_different_model(self):
        with self.assertRaisesRegex(ValueError, "only permits"):
            resolve_route(opts(backend="luna", model="other"))

    def test_free_does_not_accept_paid_model(self):
        with self.assertRaisesRegex(ValueError, "allowlisted"):
            resolve_route(opts(backend="free", model="gpt-6-luna"))

    def test_luna_requires_explicit_paid_approval_before_hermes(self):
        result = subprocess.run([
            sys.executable, "-m", "hiergoal.controller",
            "--backend", "luna", "--hermes", sys.executable, "--ack-unsandboxed",
        ], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--approve-paid-api", result.stderr)

    def test_luna_dry_run_has_no_model_call(self):
        result = subprocess.run([
            sys.executable, "-m", "hiergoal.controller", "--dry-run", "--backend", "luna",
        ], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("openai-api", result.stdout)
        self.assertIn("No Hermes / OpenCode / OpenAI inference calls", result.stdout)


if __name__ == "__main__":
    unittest.main()
