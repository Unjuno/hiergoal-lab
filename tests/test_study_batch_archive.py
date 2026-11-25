# SPDX-License-Identifier: Apache-2.0
"""Offline publication checks for bounded HTTP 400 trial continuation."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from hiergoal.study import prepare, collect
from hiergoal.study_analysis import analyze
from hiergoal.study_archive import public_execution, diagnostic_code, export_run, verify, RECEIPT, file_hash
from hiergoal.study_protocol import save


POLICY = {"continue_diagnostics": ["OPENAI_HTTP_400"], "max_http_400_trial_errors": 3,
          "retry_failed_requests": False, "audit_each_trial": True}


def result(ident, status="PASS", diagnostic="FINAL_GRADE_PASS"):
    return {"trial_id": ident, "status": status,
            "audit": "NOT_RUN" if status == "NOT_RUN" else "PASS",
            "diagnostic": diagnostic, "protocol_ok": status != "NOT_RUN",
            "invariant_ok": status != "NOT_RUN", "stop_batch": status == "UNCERTAIN"}


class BatchArchiveTests(unittest.TestCase):
    def fixture(self):
        manifest = {"protocol_id": "p", "protocol_revision": "v2.5", "backend": "openai",
                    "execution_policy": copy.deepcopy(POLICY),
                    "trials": [{"trial_id": f"t{i}"} for i in range(6)]}
        rows = [result("t0", "UNCERTAIN", "OPENAI_HTTP_400"), result("t1"),
                result("t2", "UNCERTAIN", "OPENAI_HTTP_400"), result("t3", "FAIL", "TOKEN_BUDGET_AFTER"),
                result("t4", "UNCERTAIN", "OPENAI_HTTP_400"), result("t5", "NOT_RUN", "NOT_RUN")]
        execution = {"protocol_id": "p", "backend": "openai", "status": "STOPPED", "completed": 5,
                     "stop_reason": "HTTP_400_TRIAL_ERROR_LIMIT", "api_error_trial_ids": ["t0", "t2", "t4"],
                     "continued_api_error_trial_ids": ["t0", "t2"]}
        return manifest, rows, execution

    def test_total_limit_survives_interleaved_nonerrors(self):
        manifest, rows, execution = self.fixture()
        self.assertEqual(public_execution(execution, manifest, rows), execution)

    def test_unknown_duplicate_reordered_omitted_or_third_continued_id_rejected(self):
        changes = [
            ("api_error_trial_ids", ["t0", "t2", "unknown"]),
            ("api_error_trial_ids", ["t0", "t0", "t4"]),
            ("api_error_trial_ids", ["t2", "t0", "t4"]),
            ("api_error_trial_ids", ["t0", "t2"]),
            ("continued_api_error_trial_ids", ["t0", "t2", "t4"]),
            ("continued_api_error_trial_ids", ["t0", "t1"]),
            ("continued_api_error_trial_ids", ["t2", "t0"]),
            ("continued_api_error_trial_ids", None),
        ]
        for field, value in changes:
            with self.subTest(field=field, value=value):
                manifest, rows, execution = self.fixture()
                execution[field] = value
                with self.assertRaises(ValueError):
                    public_execution(execution, manifest, rows)

    def test_changed_continuation_policy_is_rejected(self):
        for field, value in [("max_http_400_trial_errors", 4), ("continue_diagnostics", ["OPENAI_HTTP_422"]),
                             ("retry_failed_requests", True), ("audit_each_trial", False)]:
            with self.subTest(field=field):
                manifest, rows, execution = self.fixture()
                manifest["execution_policy"][field] = value
                with self.assertRaises(ValueError):
                    public_execution(execution, manifest, rows)

    def test_fatal_audit_or_other_transport_cannot_be_crossed(self):
        for update in [{"audit": "FAIL", "diagnostic": "AUDIT_FAILED"},
                       {"diagnostic": "OPENAI_HTTP_401"}, {"diagnostic": "OPENAI_HTTP_422"},
                       {"protocol_ok": False}, {"invariant_ok": False}, {"stop_batch": False}]:
            with self.subTest(update=update):
                manifest, rows, execution = self.fixture()
                rows[0].update(update)
                with self.assertRaises(ValueError):
                    public_execution(execution, manifest, rows)

    def test_stopped_audit_failure_is_publishable_without_error_ids(self):
        manifest, rows, execution = self.fixture()
        rows = [result("t0", "UNCERTAIN", "AUDIT_FAILED")] + [result(f"t{i}", "NOT_RUN", "NOT_RUN") for i in range(1, 6)]
        rows[0].update(audit="FAIL", protocol_ok=False, invariant_ok=False)
        execution.update(completed=1, stop_reason="AUDIT_FAILED", api_error_trial_ids=[], continued_api_error_trial_ids=[])
        self.assertEqual(public_execution(execution, manifest, rows), execution)

    def test_cannot_run_beyond_third_error_or_claim_unobserved_limit(self):
        manifest, rows, execution = self.fixture()
        rows[5] = result("t5")
        execution.update(completed=6, status="COMPLETED")
        with self.assertRaises(ValueError):
            public_execution(execution, manifest, rows)
        manifest, rows, execution = self.fixture()
        rows[4] = result("t4")
        execution.update(api_error_trial_ids=["t0", "t2"])
        with self.assertRaises(ValueError):
            public_execution(execution, manifest, rows)

    def test_final_scheduled_error_is_not_listed_as_continued(self):
        manifest, rows, execution = self.fixture()
        manifest["trials"] = manifest["trials"][:2]
        rows = [result("t0"), result("t1", "UNCERTAIN", "OPENAI_HTTP_400")]
        execution.update(completed=2, status="COMPLETED", stop_reason=None,
                         api_error_trial_ids=["t1"], continued_api_error_trial_ids=[])
        self.assertEqual(public_execution(execution, manifest, rows), execution)
        execution["continued_api_error_trial_ids"] = ["t1"]
        with self.assertRaises(ValueError):
            public_execution(execution, manifest, rows)

    def test_incomplete_next_trial_remains_publishable(self):
        manifest, rows, execution = self.fixture()
        execution.update(status="RUNNING", completed=1, stop_reason=None,
                         api_error_trial_ids=["t0"], continued_api_error_trial_ids=["t0"])
        rows = rows[:1] + [result(f"t{i}", "NOT_RUN", "NOT_RUN") for i in range(1, 6)]
        rows[1].update(status="UNCERTAIN", audit="INCOMPLETE", diagnostic="INTERRUPTED")
        self.assertEqual(public_execution(execution, manifest, rows), execution)
        rows[2] = result("t2")
        with self.assertRaises(ValueError):
            public_execution(execution, manifest, rows)

    def test_legacy_execution_remains_supported(self):
        manifest, rows, execution = self.fixture()
        manifest.update(protocol_revision="v2.4")
        manifest.pop("execution_policy")
        execution.pop("api_error_trial_ids")
        execution.pop("continued_api_error_trial_ids")
        self.assertEqual(public_execution(execution, manifest, rows), execution)

    def test_safe_diagnostic_projection_is_idempotent(self):
        for raw in ["APPARATUS_ERROR:ValueError", "OPENAI_TRANSPORT_OR_JSON_ERROR:TimeoutError",
                    "OPENAI_TRANSPORT_OR_JSON_ERROR:URLError", "EVIDENCE_AUDIT_FAILED:ValueError",
                    "HTTP_400_TRIAL_ERROR_LIMIT", "OPENAI_HTTP_400", "Immutable root changed",
                    "untrusted secret content"]:
            code = diagnostic_code(raw)
            self.assertEqual(diagnostic_code(code), code)

    def test_export_keeps_continuation_and_rejects_rehashed_forgery(self):
        """Synthetic collected rows test publication only; no transport is used."""
        with tempfile.TemporaryDirectory() as tmp:
            source, public = Path(tmp) / "source", Path(tmp) / "public"
            manifest = prepare(source)
            self.assertEqual(manifest["execution_policy"], POLICY)
            host = json.loads((source / "host.json").read_text())
            host.update(git_commit="a" * 40, working_tree_dirty=False)
            save(source / "host.json", host)
            collect(source)
            rows = json.loads((source / "results.json").read_text())
            first_id = rows[0]["trial_id"]
            rows[0] = {**result(first_id, "UNCERTAIN", "OPENAI_HTTP_400"), "success": None,
                       "input_tokens": None, "output_tokens": None, "actual_input_tokens": None,
                       "actual_output_tokens": None, "known_input_tokens": 17, "known_output_tokens": 4}
            save(source / "results.json", rows)
            save(source / "summary.json", analyze({**manifest, "execution_context": host}, rows))
            execution = {"protocol_id": manifest["protocol_id"], "backend": "openai", "status": "STOPPED",
                         "completed": 1, "stop_reason": "BATCH_TIME_ALLOWANCE", "api_error_trial_ids": [first_id],
                         "continued_api_error_trial_ids": [first_id]}
            save(source / "execution.json", execution)
            ident = dict(profile="pilot", run_id="12345", attempt="1", commit="a" * 40)
            receipt = export_run(source, public, **ident, live_outcome="success", collection_outcome="success")
            self.assertFalse(receipt["complete_audited_execution"])
            self.assertEqual(receipt["outcomes"]["UNCERTAIN"], 1)
            self.assertEqual(json.loads((public / "execution.json").read_text()), execution)
            projected = json.loads((public / "results.json").read_text())[0]
            self.assertIsNone(projected["input_tokens"])
            self.assertEqual(projected["known_input_tokens"], 17)
            self.assertEqual(verify(public, **ident), receipt)
            execution["continued_api_error_trial_ids"] = []
            save(public / "execution.json", execution)
            receipt["files"]["execution.json"] = file_hash(public / "execution.json")
            save(public / RECEIPT, receipt)
            with self.assertRaises(ValueError):
                verify(public, **ident)
            # Removing the whole execution file and its checksum must not
            # erase the continuation decision while keeping observed rows.
            (public / "execution.json").unlink()
            receipt["files"].pop("execution.json")
            save(public / RECEIPT, receipt)
            with self.assertRaises(ValueError):
                verify(public, **ident)


if __name__ == "__main__":
    unittest.main()
