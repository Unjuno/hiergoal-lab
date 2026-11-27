# SPDX-License-Identifier: Apache-2.0
"""End-to-end readiness tests. No credentials, network or persistent fake results.

Exercise the frozen production CLI and Responses adapter against local envelopes.
All outputs that resemble live evidence exist ONLY in TemporaryDirectory; never
copy them to experiments/ or upload them as empirical records.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from hiergoal import recovery, recovery_launch as launch
from hiergoal.recovery_audit import audit_all
from hiergoal.recovery_protocol import make_task, validate_manifest
from hiergoal.study import OracleResponder
from hiergoal.study_protocol import ROOT, canonical, save
from hiergoal.study_wire import expand_wire, response_format


ARCHIVED_MANIFEST = ROOT / (
    "experiments/controlled-recovery/run-45917876892-attempt-1/manifest.json"
)


class LocalResponses:
    """In-memory fake HTTP opener, never contacts any endpoint."""
    def __init__(self, manifest, *, fail_at=None, invalid_first_plan=False):
        self.manifest = manifest
        self.tasks = {spec["task_id"]: spec for spec in manifest["tasks"]}
        self.requests = []
        self.fail_at = fail_at
        self.invalid_first_plan = invalid_first_plan

    def open(self, request, timeout):
        assert request.full_url == self.manifest["endpoint"]
        assert request.get_method() == "POST"
        assert timeout == self.manifest["limits"]["request_timeout_seconds"]
        body = json.loads(request.data)
        assert body["model"] == self.manifest["model"]
        assert body["store"] is False
        assert body["reasoning"] == {"effort": self.manifest["reasoning_effort"]}
        logical = expand_wire(json.loads(body["input"]))
        role = logical.pop("role")
        task_id = logical["root_contract"]["task_id"]
        assert body["text"]["format"] == response_format(role, logical)
        assert 0 < body["max_output_tokens"] <= self.manifest["limits"]["max_output_tokens"]
        self.requests.append((role, task_id))
        index = len(self.requests)
        if index == self.fail_at:
            raise urllib.error.HTTPError(
                request.full_url, 503, "local test outage",
                {"x-request-id": "req_offline_fixture"},
                io.BytesIO(b'{"error":{"type":"server_error","code":"test_outage"}}'),
            )
        oracle = OracleResponder()
        oracle.task = make_task(self.tasks[task_id])
        record = oracle.respond(role, logical, max_output_tokens=body["max_output_tokens"])
        text = record["text"]
        if self.invalid_first_plan and index == 1:
            text = '{"instructions":{}}'
        return io.BytesIO(canonical({
            "id": "resp_OFFLINE_FIXTURE_" + str(index),
            "model": self.manifest["model"],
            "status": "completed",
            "usage": record["usage"],
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": text},
            ]}],
        }).encode("utf-8"))


class ControlledRecoveryReadinessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="recovery-offline-fixture-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.public = self.root / "mock-publication"
        self.capture = io.StringIO()
        self.addCleanup(self.capture.close)
        # The placeholder is local test data, never a provider credential.
        self.env = patch.dict(os.environ, {
            "OPENAI_API_KEY": "OFFLINE_FIXTURE_NOT_A_CREDENTIAL",
            "OPENAI_BASE_URL": "https://api.openai.com/v1",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        for target in ("socket.socket.connect", "socket.socket.connect_ex",
                       "socket.create_connection"):
            guard = patch(target, side_effect=AssertionError("Offline test forbids sockets"))
            guard.start()
            self.addCleanup(guard.stop)

    def cli(self, command, *extra):
        with contextlib.redirect_stdout(self.capture):
            return recovery.main([command, "--output", str(self.source), *extra])

    def load(self, name):
        return json.loads((self.source / name).read_text(encoding="utf-8"))

    def prepare(self):
        with patch("hiergoal.study_api.urllib.request.build_opener",
                   side_effect=AssertionError("Prepare must never construct a transport")):
            self.assertEqual(self.cli("prepare"), 0)
        manifest = self.load("manifest.json")
        validate_manifest(manifest)
        self.assertEqual(manifest, json.loads(ARCHIVED_MANIFEST.read_text(encoding="utf-8")),
                         "Readiness checks must preserve the frozen pilot")
        commit = self.load("host.json")["git_commit"]
        # Simulate authorization locally, not a GitHub event or a live dispatch.
        authorization = launch.authorize(
            manifest, {"repository": {"full_name": launch.REPOSITORY},
                       "sender": {"login": launch.OWNER}, "inputs": {"mode": "run"}},
            event_name="workflow_dispatch", actor=launch.OWNER,
            repository=launch.REPOSITORY, ref="refs/heads/main", run_attempt="1",
            head_commit=commit, parents=[], changes=[],
        )
        save(self.source / "authorization.json", authorization)
        return manifest

    def run_fixture(self, manifest, **options):
        opener = LocalResponses(manifest, **options)
        with patch("hiergoal.study_api.urllib.request.build_opener", return_value=opener):
            code = self.cli("run", "--execute", "--approve-paid-api")
        with patch("hiergoal.study_api.urllib.request.build_opener",
                   side_effect=AssertionError("Collect must never construct a transport")):
            self.assertEqual(self.cli("collect"), 0)
        return code, opener, self.load("summary.json")

    def verify_archive(self, manifest, expected_status):
        identity = {"run_id": "9000000001", "attempt": "1",
                    "commit": self.load("host.json")["git_commit"]}
        receipt = launch.export_public(self.source, self.public, **identity)
        self.assertEqual(receipt, launch.verify_public(self.public, **identity))
        replay = audit_all(self.public, manifest)
        self.assertEqual(replay["status"], expected_status, replay["errors"])
        self.assertEqual(replay, self.load("audits.json"))
        self.assertNotIn("OFFLINE_FIXTURE_NOT_A_CREDENTIAL",
                         canonical(receipt))
        for path in self.public.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"OFFLINE_FIXTURE_NOT_A_CREDENTIAL", path.read_bytes())
        return receipt

    def test_full_frozen_cli_transport_replay_and_archive(self):
        manifest = self.prepare()
        code, opener, summary = self.run_fixture(manifest)
        self.assertEqual(code, 0)
        self.assertEqual(summary["apparatus_decision"], "PASS")
        self.assertEqual(summary["efficacy_decision"], "UNCERTAIN")
        self.assertEqual(summary["preparation"]["verified_source_pass"], 12)
        self.assertEqual(summary["paired"]["complete_pairs"], 12)
        self.assertEqual(summary["evidence"]["valid_repair_traces"], 24)
        self.assertEqual(summary["cost"]["calls_started"], len(opener.requests))
        self.assertEqual(len(opener.requests), 60)
        self.assertEqual([role for role, _ in opener.requests].count("replan"), 12)
        self.assertEqual(summary["cost"]["known_tokens"], 12000)
        self.assertTrue(summary["cost"]["complete_usage"])
        self.assertEqual(summary["evidence"]["root_unchanged_trials"], 24)
        rows = self.load("results.json")
        for pair in manifest["pairs"]:
            matched = [r for r in rows if r["pair_id"] == pair["pair_id"]]
            self.assertEqual(len(matched), 2)
            for field in ("checkpoint_sha256", "initial_plan_sha256", "initial_artifact_sha256"):
                self.assertIsNotNone(matched[0][field])
                self.assertEqual(matched[0][field], matched[1][field])
        self.verify_archive(manifest, "PASS")
        # Publication must fail if a recorded result is later changed.
        (self.public / "summary.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            launch.verify_public(self.public, run_id="9000000001", attempt="1",
                                 commit=self.load("host.json")["git_commit"])

    def test_transport_failure_preserves_completed_pair_and_unknown_usage(self):
        manifest = self.prepare()
        code, opener, summary = self.run_fixture(manifest, fail_at=6)
        self.assertEqual(code, 1)
        self.assertEqual(len(opener.requests), 6)
        self.assertEqual(self.load("execution.json")["state"], "STOPPED")
        self.assertEqual(summary["paired"]["complete_pairs"], 1)
        self.assertEqual(summary["paired"]["incomplete"], 11)
        self.assertEqual(summary["cost"]["calls_started"], 6)
        self.assertEqual(summary["cost"]["known_tokens"], 1000)
        self.assertFalse(summary["cost"]["complete_usage"])
        self.assertEqual(summary["efficacy_decision"], "UNCERTAIN")
        second = self.load("preparations.json")[1]
        self.assertEqual(second["status"], "UNCERTAIN")
        self.assertIsNone(second["input_tokens"])
        self.assertIsNone(second["output_tokens"])
        self.verify_archive(manifest, "INCOMPLETE")

    def test_failed_preparation_is_not_rerolled_or_scored_as_repair_failure(self):
        manifest = self.prepare()
        code, opener, summary = self.run_fixture(manifest, invalid_first_plan=True)
        self.assertEqual(code, 1)
        self.assertEqual(len(opener.requests), 56)
        self.assertEqual(self.load("execution.json")["state"], "COMPLETED")
        self.assertEqual(summary["preparation"]["verified_source_pass"], 11)
        self.assertEqual(summary["paired"]["complete_pairs"], 11)
        self.assertEqual(summary["paired"]["source_failure"], 1)
        first = manifest["pairs"][0]["pair_id"]
        rows = [r for r in self.load("results.json") if r["pair_id"] == first]
        self.assertEqual([r["status"] for r in rows], ["NOT_RUN_SOURCE_FAILURE"] * 2)
        self.verify_archive(manifest, "INCOMPLETE")

    def test_prepare_collect_and_unapproved_run_never_open_transport(self):
        with patch("hiergoal.study_api.urllib.request.build_opener",
                   side_effect=AssertionError("No transport permitted")) as factory:
            self.assertEqual(self.cli("prepare"), 0)
            self.assertEqual(self.cli("collect"), 0)
            self.assertEqual(self.load("summary.json")["cost"]["calls_started"], 0)
            with contextlib.redirect_stderr(self.capture), self.assertRaises(SystemExit):
                self.cli("run")
            factory.assert_not_called()
        self.assertFalse((self.source / "execution.json").exists())


if __name__ == "__main__":
    unittest.main()
