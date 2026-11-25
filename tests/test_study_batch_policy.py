# SPDX-License-Identifier: Apache-2.0
"""Offline batch continuation, bounded errors, and diagnostic preservation."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hiergoal.study import OracleResponder, audit_trial, prepare, run
from hiergoal.study_api import TransportError
from hiergoal.study_protocol import save


class FailingRequests(OracleResponder):
    def __init__(self, failures, diagnostic="OPENAI_HTTP_400", *, fail_plans=False):
        super().__init__()
        self.failures = set(failures)
        self.diagnostic = diagnostic
        self.fail_plans = fail_plans
        self.requests = 0
        self.failed_requests = 0

    def respond(self, role, payload, **kwargs):
        if role == ("plan" if self.fail_plans else "execute"):
            self.requests += 1
            if self.requests in self.failures:
                self.failed_requests += 1
                evidence = {"http_status": 400, "error_code": "synthetic_bad_request",
                            "request_id": "offline-test-request"}
                raise TransportError(self.diagnostic, evidence=evidence)
        return super().respond(role, payload, **kwargs)


class BatchPolicyTests(unittest.TestCase):
    def execute(self, directory, backend):
        manifest = prepare(directory, backend="oracle", model="OFFLINE_ORACLE")
        with patch("hiergoal.study.OpenAIResponder", side_effect=AssertionError("No API")):
            run(directory, responder=backend)
        return manifest, json.loads((directory / "execution.json").read_text()), json.loads((directory / "results.json").read_text())

    def test_one_http400_does_not_discard_remaining_schedule_or_unknown_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            backend = FailingRequests({1})
            manifest, execution, results = self.execute(directory, backend)
            failed = [r for r in results if r["status"] == "UNCERTAIN"]
            self.assertEqual(len(failed), 1)
            self.assertEqual(backend.failed_requests, 1)
            self.assertEqual(execution["completed"], 18)
            self.assertEqual(execution["status"], "COMPLETED")
            self.assertIsNone(execution["stop_reason"])
            self.assertEqual(execution["api_error_trial_ids"], [failed[0]["trial_id"]])
            self.assertEqual(execution["continued_api_error_trial_ids"], execution["api_error_trial_ids"])
            self.assertEqual(failed[0]["audit"], "PASS")
            self.assertIsNone(failed[0]["input_tokens"])
            self.assertIsNone(failed[0]["success"])
            self.assertEqual(failed[0]["transport_evidence"]["error_code"], "synthetic_bad_request")
            self.assertEqual(sum(r["status"] == "PASS" for r in results), 17)
            self.assertEqual(manifest["execution_policy"]["max_http_400_trial_errors"], 3)

    def test_third_http400_stops_without_reset_after_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, execution, results = self.execute(Path(tmp), FailingRequests({1, 4, 7}))
            self.assertEqual(execution["stop_reason"], "HTTP_400_TRIAL_ERROR_LIMIT")
            self.assertEqual(len(execution["api_error_trial_ids"]), 3)
            self.assertEqual(execution["continued_api_error_trial_ids"], execution["api_error_trial_ids"][:2])
            self.assertLess(execution["completed"], len(results))
            self.assertTrue(any(r["status"] == "PASS" for r in results[:execution["completed"]]))
            self.assertTrue(all(r["status"] == "NOT_RUN" for r in results[execution["completed"]:]))

    def test_cached_failed_plan_preserves_receipt_without_reroll(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = FailingRequests({1}, fail_plans=True)
            _, execution, results = self.execute(Path(tmp), backend)
            affected = [r for r in results if r.get("diagnostic") == "OPENAI_HTTP_400"]
            self.assertEqual(len(affected), 3)
            self.assertEqual(backend.failed_requests, 1)
            self.assertEqual(len(execution["api_error_trial_ids"]), 3)
            self.assertTrue(all(r["audit"] == "PASS" for r in affected))
            self.assertTrue(all(r["transport_evidence"]["request_id"] == "offline-test-request" for r in affected))

    def test_other_errors_still_stop_immediately(self):
        for diagnostic in ("OPENAI_HTTP_401", "OPENAI_HTTP_403", "OPENAI_HTTP_429", "OFFLINE_SIMULATED_TIMEOUT"):
            with self.subTest(diagnostic=diagnostic), tempfile.TemporaryDirectory() as tmp:
                _, execution, _ = self.execute(Path(tmp), FailingRequests({1}, diagnostic))
                self.assertEqual(execution["completed"], 1)
                self.assertEqual(execution["stop_reason"], diagnostic)
                self.assertEqual(execution["continued_api_error_trial_ids"], [])

    def test_audit_failure_stops_before_next_trial(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            prepare(directory, backend="oracle", model="OFFLINE_ORACLE")
            with patch("hiergoal.study.audit_trial", return_value={"audit": "FAIL", "status": "UNCERTAIN"}), \
                 patch("hiergoal.study.collect", return_value={}):
                run(directory, responder=OracleResponder())
            execution = json.loads((directory / "execution.json").read_text())
            self.assertEqual(execution["completed"], 1)
            self.assertEqual(execution["stop_reason"], "AUDIT_FAILED")

    def test_transport_receipt_change_cannot_pass_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            manifest, _, results = self.execute(directory, FailingRequests({1}))
            result = next(r for r in results if r["status"] == "UNCERTAIN")
            trial = next(t for t in manifest["trials"] if t["trial_id"] == result["trial_id"])
            path = directory / "trials" / trial["trial_id"] / "result.json"
            original = json.loads(path.read_text())
            changed = copy.deepcopy(original)
            changed["transport_evidence"]["error_code"] = "altered_code"
            save(path, changed)
            self.assertEqual(audit_trial(directory, trial, manifest)["audit"], "FAIL")


if __name__ == "__main__":
    unittest.main()
