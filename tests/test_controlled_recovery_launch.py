# SPDX-License-Identifier: Apache-2.0
"""Negative authorization and publication tests; no model or network calls."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hiergoal import recovery_launch as launch
from hiergoal.study_protocol import digest, save


CODE = "1" * 40
HEAD = "2" * 40


def example_manifest():
    value = {"backend": "openai", "model": "gpt-6-luna", "reasoning_effort": "low",
             "tasks": [{} for _ in range(6)], "pairs": [{} for _ in range(12)],
             "trials": [{} for _ in range(24)],
             "limits": {"max_calls": 8, "max_total_tokens": 64000},
             "preparation_limits": {"max_calls": 8, "max_total_tokens": 64000}}
    value["protocol_id"] = digest(value)
    return value


def validate_digest(manifest):
    body = {key: value for key, value in manifest.items() if key != "protocol_id"}
    if manifest.get("protocol_id") != digest(body):
        raise ValueError("Manifest changed")


def example_event():
    return {"ref": "refs/heads/main", "before": CODE, "after": HEAD,
            "forced": False, "deleted": False,
            "repository": {"full_name": launch.REPOSITORY},
            "sender": {"login": launch.OWNER}}


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.event = example_manifest(), example_event()
        self.validator = patch.object(launch, "validate_protocol", side_effect=validate_digest)
        self.validator.start()
        self.addCleanup(self.validator.stop)

    def authorize(self, **kwargs):
        arguments = {"event_name": "push", "actor": launch.OWNER,
                     "repository": launch.REPOSITORY, "ref": "refs/heads/main",
                     "run_attempt": "1", "head_commit": HEAD, "parents": [CODE],
                     "changes": [("A", launch.LAUNCH_PATH)],
                     "request": launch.expected_request(self.manifest, CODE)}
        arguments.update(kwargs)
        return launch.authorize(self.manifest, self.event, **arguments)

    def test_exact_separate_authorized_launch_is_live(self):
        result = self.authorize()
        self.assertTrue(result["live"])
        self.assertEqual(result["source_commit"], CODE)
        self.assertEqual(result["execution_commit"], HEAD)
        self.assertEqual(result["max_logical_calls"], 288)

    def test_ordinary_code_push_stays_offline(self):
        self.assertFalse(self.authorize(changes=[("M", "hiergoal/recovery.py")], request=None)["live"])

    def test_dispatch_is_offline_by_default_and_explicit_run_is_live(self):
        self.assertFalse(self.authorize(event_name="workflow_dispatch")["live"])
        self.event["inputs"] = {"mode": "run"}
        value = self.authorize(event_name="workflow_dispatch")
        self.assertTrue(value["live"])
        self.assertEqual(value["source_commit"], HEAD)

    def test_launch_request_replay_is_rejected(self):
        for kwargs in ({"run_attempt": "2"}, {"prior_launch_seen": True},
                       {"changes": [("M", launch.LAUNCH_PATH)]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.authorize(**kwargs)

    def test_code_cannot_change_in_launch_commit(self):
        with self.assertRaises(ValueError):
            self.authorize(changes=[("A", launch.LAUNCH_PATH), ("M", "hiergoal/recovery.py")])

    def test_source_commit_and_parent_binding(self):
        for kwargs in ({"parents": ["3" * 40]}, {"parents": [CODE, "3" * 40]},
                       {"head_commit": "3" * 40}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.authorize(**kwargs)
        request = launch.expected_request(self.manifest, "3" * 40)
        with self.assertRaises(ValueError):
            self.authorize(request=request)

    def test_wrong_actor_sender_repository_and_ref_are_rejected(self):
        for kwargs in ({"actor": "someone"}, {"repository": "someone/hiergoal-lab"},
                       {"ref": "refs/heads/feature"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.authorize(**kwargs)
        self.event["sender"]["login"] = "someone"
        with self.assertRaises(ValueError):
            self.authorize()

    def test_force_push_cannot_launch(self):
        self.event["forced"] = True
        with self.assertRaises(ValueError):
            self.authorize()

    def test_manifest_tampering_is_rejected(self):
        self.manifest["limits"]["max_total_tokens"] += 1
        with self.assertRaises(ValueError):
            self.authorize()

    def test_request_tampering_and_extra_fields_are_rejected(self):
        mutations = {"approved": False, "allow_paid_api": False,
                     "protocol_id": "0" * 64, "limits_sha256": "0" * 64,
                     "max_trials": 25, "max_logical_calls": 999,
                     "user_request": "unrelated request", "extra": True}
        for key, value in mutations.items():
            request = launch.expected_request(self.manifest, CODE)
            request[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.authorize(request=request)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source, self.destination = self.root / "source", self.root / "public"
        self.source.mkdir()
        self.manifest = example_manifest()
        self.validator = patch.object(launch, "validate_protocol", side_effect=validate_digest)
        self.validator.start()
        self.addCleanup(self.validator.stop)
        self.identity = {"run_id": "12345", "attempt": "1", "commit": HEAD}
        save(self.source / "manifest.json", self.manifest)
        save(self.source / "host.json", {"git_commit": HEAD})
        save(self.source / "authorization.json", {
            "schema_version": launch.AUTH_SCHEMA, "live": True, "allow_paid_api": True,
            "approved_by": launch.OWNER, "protocol_id": self.manifest["protocol_id"],
            "execution_commit": HEAD, "limits_sha256": launch.limits_fingerprint(self.manifest)})
        save(self.source / "trials" / "task-r1-fixed" / "result.json", {"status": "PASS"})
        trace = self.source / "trials" / "task-r1-fixed" / "trace.jsonl"
        trace.write_text('{"type":"response","text":"untrusted model text"}\n', encoding="utf-8")

    def export(self):
        return launch.export_public(self.source, self.destination, **self.identity)

    def test_roundtrip_preserves_full_response_evidence(self):
        receipt = self.export()
        self.assertEqual(receipt["file_count"], 5)
        self.assertEqual((self.source / "trials/task-r1-fixed/trace.jsonl").read_bytes(),
                         (self.destination / "trials/task-r1-fixed/trace.jsonl").read_bytes())
        self.assertEqual(launch.verify_public(self.destination, **self.identity), receipt)

    def test_modified_evidence_fails_checksum(self):
        self.export()
        save(self.destination / "trials/task-r1-fixed/result.json", {"status": "FAIL"})
        with self.assertRaises(ValueError):
            launch.verify_public(self.destination, **self.identity)

    def test_extra_executable_is_rejected_even_with_allowed_data(self):
        (self.source / "execute.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.export()

    def test_paths_and_symlinks_cannot_escape_allowlist(self):
        for path in ("../manifest.json", "/manifest.json", "trials/../trace.jsonl",
                     "trials/.hidden/result.json", "trials/a/execute.sh", ".env"):
            with self.subTest(path=path):
                self.assertFalse(launch.allowed_path(path))
        (self.source / "summary.json").symlink_to(self.source / "manifest.json")
        with self.assertRaises(ValueError):
            self.export()

    def test_identity_cannot_be_reassigned(self):
        self.export()
        with self.assertRaises(ValueError):
            launch.verify_public(self.destination, run_id="12346", attempt="1", commit=HEAD)

    def test_source_host_or_authorization_mismatch_fails(self):
        save(self.source / "host.json", {"git_commit": CODE})
        with self.assertRaises(ValueError):
            self.export()
        save(self.source / "host.json", {"git_commit": HEAD})
        authorization = json.loads((self.source / "authorization.json").read_text())
        authorization["live"] = False
        save(self.source / "authorization.json", authorization)
        with self.assertRaises(ValueError):
            self.export()

    def test_size_and_secret_shaped_content_fail_closed(self):
        with patch.object(launch, "MAX_FILE_BYTES", 10), self.assertRaises(ValueError):
            self.export()
        (self.source / "summary.md").write_text("sk-" + "a" * 30, encoding="utf-8")
        with self.assertRaises(ValueError):
            self.export()

    def test_malformed_jsonl_is_not_exported(self):
        (self.source / "trials/task-r1-fixed/trace.jsonl").write_text("not JSON\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.export()

    def test_existing_publication_is_never_overwritten(self):
        self.export()
        with self.assertRaises(ValueError):
            self.export()


if __name__ == "__main__":
    unittest.main()
