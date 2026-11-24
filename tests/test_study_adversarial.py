# SPDX-License-Identifier: Apache-2.0
"""Adversarial replay and malformed-response checks; all responders are offline."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hiergoal.study import OracleResponder, audit_trial, run_trial
from hiergoal.study_protocol import build_manifest, canonical, digest, save
from hiergoal.study_tasks import make_task


def rewrite_consistent_chain(path, mutate):
    """Rehash deliberate semantic corruption; a hash-only check must not suffice."""
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    mutate(events)
    previous = "0" * 64
    for index, event in enumerate(events):
        event["sequence"], event["previous_sha256"] = index, previous
        event.pop("event_sha256", None)
        event["event_sha256"] = digest(event)
        previous = event["event_sha256"]
    path.write_text("".join(canonical(event) + "\n" for event in events), encoding="utf-8")
    save(path.with_name("result.json"), {**events[-1]["result"], "trace_final_sha256": previous})


def run_one(directory, responder=None, *, family="data_transform", arm="hierarchy_adaptive", condition="fault"):
    manifest = build_manifest("pilot", backend="oracle", model="OFFLINE_ORACLE")
    trial = next(t for t in manifest["trials"] if t["family"] == family
                 and t["arm"] == arm and t["condition"] == condition)
    task = make_task(family, trial["instance"], trial["split"], seed=manifest["task_seed"])
    result = run_trial(task, trial, manifest, responder or OracleResponder(), directory)
    trace = directory / "trials" / trial["trial_id"] / "trace.jsonl"
    return manifest, trial, result, trace


class AdversarialTraceTests(unittest.TestCase):
    def assert_corruption_rejected(self, mutate):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest, trial, result, trace = run_one(directory)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(audit_trial(directory, trial, manifest)["audit"], "PASS")
            rewrite_consistent_chain(trace, mutate)
            audited = audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "FAIL", audited)
            self.assertEqual(audited["status"], "UNCERTAIN", audited)

    def test_rehashed_stale_environment_in_request_and_response_is_rejected(self):
        def stale(events):
            initial = events[0]["public_spec"]
            changed = False
            for event in events:
                if event["type"] == "fault":
                    changed = True
                if changed and event["type"] in ("request_started", "response"):
                    event["request"]["task"] = copy.deepcopy(initial)
        self.assert_corruption_rejected(stale)

    def test_rehashed_stale_artifact_in_request_is_rejected(self):
        def stale(events):
            initial = events[0]["solution"]
            changed = False
            for event in events:
                if event["type"] == "fault":
                    changed = True
                if changed and event["type"] in ("request_started", "response"):
                    event["request"]["artifact"] = copy.deepcopy(initial)
        self.assert_corruption_rejected(stale)

    def test_rehashed_extra_final_private_grade_is_rejected(self):
        def duplicate(events):
            index = next(i for i, event in enumerate(events) if event["type"] == "final_grade")
            events.insert(index, copy.deepcopy(events[index]))
        self.assert_corruption_rejected(duplicate)

    def test_rehashed_terminal_artifact_and_environment_fingerprints_are_verified(self):
        for field in ("final_artifact_sha256", "final_environment_sha256"):
            with self.subTest(field=field):
                self.assert_corruption_rejected(
                    lambda events: events[-1]["result"].update({field: "0" * 64})
                )

    def test_rehashed_physical_api_counts_and_usage_are_verified(self):
        for field in ("actual_calls", "actual_input_tokens", "actual_output_tokens"):
            with self.subTest(field=field):
                self.assert_corruption_rejected(
                    lambda events: events[-1]["result"].update({field: 19})
                )

    def test_rehashed_elapsed_response_time_is_verified(self):
        self.assert_corruption_rejected(
            lambda events: events[-1]["result"].update(elapsed_seconds=123.5)
        )

    def test_rehashed_replan_request_must_identify_the_active_failed_leaf(self):
        def wrong_leaf(events):
            plan = next(event["plan"] for event in events if event["type"] == "shared_plan")
            for event in events:
                if event["type"] in ("request_started", "response") and event["role"] == "replan":
                    current = event["request"]["leaf"]["id"]
                    another = next(leaf for ident, leaf in plan["leaves"].items() if ident != current)
                    event["request"]["leaf"] = copy.deepcopy(another)
        self.assert_corruption_rejected(wrong_leaf)

    def test_rehashed_replan_attempts_and_rejections_are_recomputed(self):
        for field, wrong in (("replan_attempts", 0), ("rejected_actions", 1)):
            with self.subTest(field=field):
                self.assert_corruption_rejected(
                    lambda events: events[-1]["result"].update({field: wrong})
                )

    def test_flat_trace_cannot_be_relabelled_as_a_hierarchical_treatment(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest, flat_trial, result, trace = run_one(directory, arm="flat_retry", condition="normal")
            self.assertEqual(result["status"], "PASS")
            hierarchical_trial = next(t for t in manifest["trials"] if t["family"] == flat_trial["family"]
                                      and t["condition"] == "normal" and t["arm"] == "hierarchy_fixed")

            def relabel(events):
                events[0]["trial"] = copy.deepcopy(hierarchical_trial)
                events[-1]["result"]["trial_id"] = hierarchical_trial["trial_id"]

            rewrite_consistent_chain(trace, relabel)
            trace.parent.rename(directory / "trials" / hierarchical_trial["trial_id"])
            audited = audit_trial(directory, hierarchical_trial, manifest)
            self.assertEqual(audited["audit"], "FAIL", audited)
            self.assertEqual(audited["status"], "UNCERTAIN", audited)

    def test_rehashed_model_response_cannot_be_replaced_with_a_success_claim(self):
        def claim(events):
            response = next(event for event in events if event["type"] == "response"
                            and event["role"] == "execute")
            response["record"]["text"] = '{"success":true}'
        self.assert_corruption_rejected(claim)

    def test_runtime_final_grader_is_called_once_and_never_sent_to_responder(self):
        class CheckingOracle(OracleResponder):
            def __init__(self):
                super().__init__()
                self.final_calls = 0

            def respond(self, role, payload, **kwargs):
                if self.final_calls:
                    raise AssertionError("A model request followed private grading")
                text = canonical(payload)
                for private in ("hidden_grades", "private_probes", "reference_solution"):
                    if private in text:
                        raise AssertionError("Private oracle material reached responder")
                return super().respond(role, payload, **kwargs)

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest = build_manifest("pilot", backend="oracle", model="OFFLINE_ORACLE")
            trial = next(t for t in manifest["trials"] if t["family"] == "code_repair"
                         and t["arm"] == "hierarchy_adaptive" and t["condition"] == "fault")
            task = make_task("code_repair", trial["instance"], trial["split"])
            responder = CheckingOracle()
            original_grade = task.grade

            def counted_grade(solution, *, hidden=False):
                if hidden:
                    responder.final_calls += 1
                return original_grade(solution, hidden=hidden)

            task.grade = counted_grade
            result = run_trial(task, trial, manifest, responder, directory)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(responder.final_calls, 1)

    def test_upstream_update_invalidates_descendant_completion_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, result, trace = run_one(Path(folder))
            self.assertEqual(result["status"], "PASS")
            events = [json.loads(line) for line in trace.read_text().splitlines()]
            index = next(i for i, event in enumerate(events) if event["type"] == "fault")
            grades = events[index]["after_grades"]
            self.assertFalse(grades["rows"]["passed"])
            self.assertTrue(grades["aggregates"]["passed"])
            self.assertTrue(grades["report"]["passed"])
            checkpoint = next(event for event in events[index + 1:] if event["type"] == "checkpoint")
            self.assertEqual(set(checkpoint["leaf_statuses"].values()), {"pending"})
            replan = next(event for event in events[index + 1:] if event["type"] == "replan")
            gate = replan["before_plan"]["leaves"][replan["leaf_id"]]["checks"][0]
            self.assertFalse(replan["public_grades"][gate]["passed"])


class AdversarialModelOutputTests(unittest.TestCase):
    def test_success_after_trial_wall_time_limit_cannot_pass(self):
        clock = [0.0]

        class LateOracle(OracleResponder):
            def respond(self, role, payload, **kwargs):
                record = super().respond(role, payload, **kwargs)
                if role == "execute":
                    clock[0] = 1500.0
                return record

        with tempfile.TemporaryDirectory() as folder, patch("hiergoal.study.time.monotonic", side_effect=lambda: clock[0]):
            _, _, result, _ = run_one(Path(folder), LateOracle(), arm="flat_retry", condition="normal")
            self.assertEqual(result["status"], "FAIL", result)
            self.assertFalse(result["success"])

    def test_unhashable_gate_identifier_is_model_failure_not_apparatus_failure(self):
        class BadPlan(OracleResponder):
            def respond(self, role, payload, **kwargs):
                record = super().respond(role, payload, **kwargs)
                if role == "plan":
                    value = json.loads(record["text"])
                    value["milestones"][0]["subgoals"][0]["checks"] = [{}]
                    record["text"] = canonical(value)
                return record

        with tempfile.TemporaryDirectory() as folder:
            manifest, trial, result, _ = run_one(Path(folder), BadPlan())
            self.assertEqual(result["status"], "FAIL")
            self.assertFalse(result["stop_batch"])
            self.assertTrue(result["protocol_ok"])
            self.assertEqual(audit_trial(Path(folder), trial, manifest)["audit"], "PASS")

    def test_lone_unicode_surrogate_is_rejected_without_stopping_the_batch(self):
        class BadText(OracleResponder):
            def respond(self, role, payload, **kwargs):
                record = super().respond(role, payload, **kwargs)
                if role == "execute":
                    record["text"] = '{"patch":{"report":"\\ud800"},"explanation":"Malformed Unicode attempt"}'
                return record

        with tempfile.TemporaryDirectory() as folder:
            manifest, trial, result, _ = run_one(Path(folder), BadText())
            self.assertEqual(result["status"], "FAIL")
            self.assertFalse(result["stop_batch"])
            self.assertTrue(result["protocol_ok"])
            self.assertEqual(audit_trial(Path(folder), trial, manifest)["audit"], "PASS")

    def test_trimmed_local_instruction_has_replayable_model_evidence(self):
        class WhitespaceReplan(OracleResponder):
            def respond(self, role, payload, **kwargs):
                record = super().respond(role, payload, **kwargs)
                if role == "replan":
                    value = json.loads(record["text"])
                    value = {key: "  " + text + "  " for key, text in value.items()}
                    record["text"] = canonical(value)
                return record

        with tempfile.TemporaryDirectory() as folder:
            manifest, trial, result, _ = run_one(Path(folder), WhitespaceReplan())
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(audit_trial(Path(folder), trial, manifest)["audit"], "PASS")


if __name__ == "__main__":
    unittest.main()
