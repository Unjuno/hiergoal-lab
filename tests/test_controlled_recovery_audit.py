# SPDX-License-Identifier: Apache-2.0
"""Negative controls for controlled recovery evidence, not model effectiveness."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from hiergoal.recovery import run_phase
from hiergoal.recovery_audit import audit_phase
from hiergoal.recovery_checkpoint import make_checkpoint
from hiergoal.recovery_protocol import build_manifest, make_task
from hiergoal.study import OracleResponder
from hiergoal.study_api import TransportError
from hiergoal.study_protocol import canonical, digest, save


class RecoveryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = build_manifest(backend="oracle")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pair = next(pair for pair in self.manifest["pairs"] if pair["task"]["family"] == "code_repair")
        self.trials = {trial["arm"]: trial for trial in self.manifest["trials"]
                       if trial["pair_id"] == self.pair["pair_id"]}

    def source(self, backend=None):
        folder = self.root / "source"
        row = run_phase(folder, self.pair, self.manifest, backend or OracleResponder(), phase="prepare")
        return folder, row

    def repair(self, arm="adaptive", backend=None):
        _, source = self.source()
        checkpoint = make_checkpoint(make_task(self.pair["task"]), source["final_plan"], source["final_solution"],
                                     pair_id=self.pair["pair_id"], protocol_id=self.manifest["protocol_id"],
                                     source_trace_sha256=source["trace_final_sha256"])
        folder = self.root / arm
        row = run_phase(folder, self.trials[arm], self.manifest, backend or OracleResponder(),
                        phase="repair", checkpoint=checkpoint)
        return folder, row, checkpoint

    def rewrite(self, folder, edit):
        path = folder / "trace.jsonl"
        events = [json.loads(line) for line in path.read_text().splitlines()]
        edit(events)
        previous = "0" * 64
        for index, event in enumerate(events):
            event["sequence"], event["previous_sha256"] = index, previous
            event.pop("event_sha256", None)
            event["event_sha256"] = digest(event)
            previous = event["event_sha256"]
        path.write_text("".join(canonical(event) + "\n" for event in events))
        save(folder / "result.json", {**events[-1]["result"], "trace_final_sha256": previous})

    def test_source_and_adaptive_replay_without_trusting_pass(self):
        folder, row, checkpoint = self.repair()
        report = audit_phase(folder, self.trials["adaptive"], self.manifest, checkpoint)
        self.assertEqual(report["status"], "PASS", report)
        self.assertEqual(report["derived"]["calls"], 2)
        self.assertEqual(report["derived"]["replans"], 1)
        self.assertTrue(report["derived"]["locality_ok"])
        self.assertTrue(report["derived"]["instruction_diffs"][0])

    def test_rehashed_hidden_success_claim_cannot_override_failing_artifact(self):
        class NoRepair(OracleResponder):
            def respond(self, role, payload, *, max_output_tokens):
                record = super().respond(role, payload, max_output_tokens=max_output_tokens)
                if role == "execute":
                    record["text"] = canonical({"patch": payload["artifact"], "explanation": "Keep the faulty artifact unchanged."})
                return record
        folder, row, checkpoint = self.repair("fixed", NoRepair())
        self.assertEqual(row["status"], "FAIL")
        def forge(events):
            event = next(item for item in events if item["type"] == "termination")
            grades = copy.deepcopy(checkpoint["public_feedback"])
            for value in grades.values():
                value["passed"] = True
            event.update(type="grade", public_grades=grades, hidden_grades=grades,
                         passed=True, solution_sha256=row["final_artifact_sha256"])
            events[-1]["result"].update(status="PASS", success=True, diagnostic="INDEPENDENT_GRADING_PASS")
        self.rewrite(folder, forge)
        report = audit_phase(folder, self.trials["fixed"], self.manifest, checkpoint)
        self.assertEqual(report["status"], "FAIL", report)

    def test_rehashed_correct_source_in_prompt_is_detected(self):
        folder, _, checkpoint = self.repair()
        def leak(events):
            request = next(item for item in events if item["type"] == "request_started")
            request["payload"]["history"] = [{"artifact": checkpoint["source_solution"]}]
        self.rewrite(folder, leak)
        report = audit_phase(folder, self.trials["adaptive"], self.manifest, checkpoint)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("payload", str(report["errors"]))

    def test_rehashed_omitted_treatment_request_is_detected(self):
        folder, _, checkpoint = self.repair()
        def omit(events):
            request = next(item for item in events if item["type"] == "request_started")
            request["role"] = "execute"
        self.rewrite(folder, omit)
        report = audit_phase(folder, self.trials["adaptive"], self.manifest, checkpoint)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("Treatment", str(report["errors"]))

    def test_rehashed_state_change_not_in_response_is_detected(self):
        folder, _, checkpoint = self.repair()
        def alter(events):
            response = next(item for item in events if item["type"] == "response")
            response["state"]["solution"]["c01_base"] = "999"
        self.rewrite(folder, alter)
        report = audit_phase(folder, self.trials["adaptive"], self.manifest, checkpoint)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("state", str(report["errors"]))

    def test_transient_unrelated_change_remains_a_locality_failure(self):
        class TouchUnrelated(OracleResponder):
            count = 0
            def respond(self, role, payload, *, max_output_tokens):
                record = super().respond(role, payload, max_output_tokens=max_output_tokens)
                if role == "execute":
                    self.count += 1
                    if self.count == 1:
                        changed = json.loads(record["text"])
                        # The other component is unambiguously unrelated to the target.
                        failed = next(gate for gate, item in payload["public_feedback"].items()
                                      if not item["passed"])
                        unrelated = "c02_base" if failed.startswith("c01_") else "c01_base"
                        changed["patch"][unrelated] = "0"
                        record["text"] = canonical(changed)
                return record
        folder, row, checkpoint = self.repair("fixed", TouchUnrelated())
        self.assertEqual(row["status"], "PASS")
        report = audit_phase(folder, self.trials["fixed"], self.manifest, checkpoint)
        self.assertEqual(report["status"], "PASS", report)
        self.assertFalse(report["derived"]["locality_ok"])
        self.assertTrue(report["derived"]["unrelated_changed_fields"])

    def test_unknown_usage_is_not_zero_and_transport_is_replayable(self):
        class Broken(OracleResponder):
            def respond(self, role, payload, *, max_output_tokens):
                raise TransportError("Synthetic timeout", evidence={"http_status": 408})
        folder, row = self.source(Broken())
        self.assertIsNone(row["input_tokens"])
        self.assertEqual(row["calls"], 1)
        report = audit_phase(folder, self.pair, self.manifest)
        self.assertEqual(report["status"], "PASS", report)
        self.assertEqual(report["derived"]["status"], "UNCERTAIN")
        self.assertTrue(report["derived"]["stop_batch"])

    def test_overbudget_response_cannot_be_accepted_even_when_valid(self):
        class Expensive(OracleResponder):
            def respond(self, role, payload, *, max_output_tokens):
                record = super().respond(role, payload, max_output_tokens=max_output_tokens)
                record["input_tokens"] = record["usage"]["input_tokens"] = 65000
                return record
        folder, row = self.source(Expensive())
        self.assertEqual(row["status"], "FAIL")
        self.assertIsNone(row["final_plan"])
        report = audit_phase(folder, self.pair, self.manifest)
        self.assertEqual(report["status"], "PASS", report)
        self.assertGreater(report["derived"]["input_tokens"], self.manifest["preparation_limits"]["max_total_tokens"])

    def test_replan_discarded_by_budget_is_not_a_validator_rejection(self):
        class Expensive(OracleResponder):
            def respond(self, role, payload, *, max_output_tokens):
                record = super().respond(role, payload, max_output_tokens=max_output_tokens)
                record["input_tokens"] = record["usage"]["input_tokens"] = 65000
                return record
        folder, row, checkpoint = self.repair("adaptive", Expensive())
        report = audit_phase(folder, self.trials["adaptive"], self.manifest, checkpoint)
        self.assertEqual(report["status"], "PASS", report)
        self.assertEqual(report["derived"]["replan_attempts"], 1)
        self.assertEqual(report["derived"]["replan_rejections"], 0)
        self.assertEqual(report["derived"]["replan_budget_unapplied"], 1)
        self.assertEqual(report["derived"]["replan_unresolved"], 0)

    def test_checkpoint_from_another_repeat_is_rejected(self):
        folder, _, checkpoint = self.repair()
        checkpoint["pair_id"] += "-other"
        checkpoint["checkpoint_sha256"] = digest({k: v for k, v in checkpoint.items() if k != "checkpoint_sha256"})
        report = audit_phase(folder, self.trials["adaptive"], self.manifest, checkpoint)
        self.assertEqual(report["status"], "FAIL")

    def test_changed_call_count_cannot_be_hidden_by_rehashing(self):
        folder, _, checkpoint = self.repair()
        self.rewrite(folder, lambda events: events[-1]["result"].update(calls=0))
        report = audit_phase(folder, self.trials["adaptive"], self.manifest, checkpoint)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("calls", str(report["errors"]))

    def test_failed_source_slots_are_retained_without_treatment_failures(self):
        from hiergoal.recovery_analysis import collect

        class InvalidPlan(OracleResponder):
            def respond(self, role, payload, *, max_output_tokens):
                record = super().respond(role, payload, max_output_tokens=max_output_tokens)
                record["text"] = canonical({"instructions": {}})
                return record
        folder = self.root / "preparations" / self.pair["pair_id"]
        row = run_phase(folder, self.pair, self.manifest, InvalidPlan(), phase="prepare")
        self.assertEqual(row["status"], "FAIL")
        summary = collect(self.root, self.manifest)
        rows = json.loads((self.root / "results.json").read_text())
        assigned = [item for item in rows if item["pair_id"] == self.pair["pair_id"]]
        self.assertEqual(len(rows), 24)
        self.assertEqual([item["status"] for item in assigned], ["NOT_RUN_SOURCE_FAILURE"] * 2)
        self.assertEqual(summary["efficacy_decision"], "UNCERTAIN")
        self.assertIsNone(summary["confidence_interval"])
        self.assertEqual(summary["by_arm"]["fixed"]["valid_observed"], 0)
        self.assertEqual(summary["apparatus_decision"], "UNCERTAIN")

    def test_interruption_after_request_start_preserves_unknown_usage(self):
        from hiergoal.recovery_analysis import collect

        folder = self.root / "preparations" / self.pair["pair_id"]
        run_phase(folder, self.pair, self.manifest, OracleResponder(), phase="prepare")
        trace = folder / "trace.jsonl"
        events = trace.read_text().splitlines()
        trace.write_text("\n".join(events[:2]) + "\n")  # start, first request_started; process killed
        (folder / "result.json").unlink()
        summary = collect(self.root, self.manifest)
        rows = json.loads((self.root / "preparations.json").read_text())
        row = next(item for item in rows if item["pair_id"] == self.pair["pair_id"])
        self.assertEqual(row["status"], "UNCERTAIN")
        self.assertEqual(row["audit"], "FAIL")
        self.assertEqual(row["calls"], 1)
        self.assertIsNone(row["input_tokens"])
        self.assertEqual(row["known_input_tokens"], 0)
        self.assertEqual(summary["cost"]["calls_started"], 1)
        self.assertFalse(summary["cost"]["complete_usage"])

    def test_interruption_retains_prior_completed_usage_and_torn_tail(self):
        from hiergoal.recovery_analysis import collect

        folder = self.root / "preparations" / self.pair["pair_id"]
        run_phase(folder, self.pair, self.manifest, OracleResponder(), phase="prepare")
        trace = folder / "trace.jsonl"
        events = trace.read_text().splitlines()
        trace.write_text("\n".join(events[:4]) + '\n{"sequence":')
        (folder / "result.json").write_text('{"incomplete":')
        summary = collect(self.root, self.manifest)
        rows = json.loads((self.root / "preparations.json").read_text())
        row = next(item for item in rows if item["pair_id"] == self.pair["pair_id"])
        self.assertEqual(row["calls"], 2)
        self.assertEqual(row["known_input_tokens"], 100)
        self.assertEqual(row["known_output_tokens"], 100)
        self.assertEqual(row["prefix_status"], "invalid_or_torn_suffix")
        self.assertIsNone(row["input_tokens"])
        self.assertFalse(summary["cost"]["complete_usage"])


if __name__ == "__main__":
    unittest.main()
