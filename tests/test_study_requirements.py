# SPDX-License-Identifier: Apache-2.0
"""Mechanism negative controls; every responder and task remains offline."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import hiergoal.study as study
from hiergoal.study_mechanisms import (
    InvalidAction, evidence_from_events, replan_decision, validate_replan,
)
from hiergoal.study_protocol import build_manifest, canonical, digest, make_trial_task, save


def _grades(**values):
    return {gate: {"passed": passed, "message": "Independent public gate result"}
            for gate, passed in values.items()}


def _plan():
    return {"milestones": [{"id": "M1", "title": "Repair dependent outputs"},
                           {"id": "M2", "title": "Preserve independent output"}],
            "leaves": {
                "S1": {"id": "S1", "parent": "M1", "instruction": "Compute the source output",
                       "checks": ["a"], "depends_on": [], "revision": 0},
                "S2": {"id": "S2", "parent": "M1", "instruction": "Compute the dependent output",
                       "checks": ["b"], "depends_on": ["S1"], "revision": 0},
                "S3": {"id": "S3", "parent": "M2", "instruction": "Keep the independent output",
                       "checks": ["c"], "depends_on": [], "revision": 0},
            }}


class MechanismPolicyTests(unittest.TestCase):
    def test_local_revision_preserves_original_plan_and_unrelated_goal(self):
        plan, grades = _plan(), _grades(a=False, b=True, c=True)
        untouched = copy.deepcopy(plan)
        change = {"diagnosis": "  The source output no longer passes its public gate.  ",
                  "revised_instruction": "  Recompute the failed source output from the current input.  "}
        revised, diagnosis = validate_replan(plan, plan["leaves"]["S1"], grades, change)
        self.assertEqual(plan, untouched)
        self.assertEqual(revised["leaves"]["S3"], untouched["leaves"]["S3"])
        self.assertEqual(revised["milestones"], untouched["milestones"])
        self.assertEqual(revised["leaves"]["S1"]["revision"], 1)
        self.assertEqual(diagnosis, change["diagnosis"].strip())
        restored = copy.deepcopy(revised)
        restored["leaves"]["S1"] = copy.deepcopy(untouched["leaves"]["S1"])
        self.assertEqual(restored, untouched)

    def test_passed_leaf_extra_contract_fields_and_unchanged_instruction_are_rejected(self):
        plan = _plan()
        leaf = plan["leaves"]["S1"]
        valid = {"diagnosis": "A failed source gate was observed.",
                 "revised_instruction": "Recompute the source output using the new input."}
        cases = [(_grades(a=True, b=True, c=True), valid),
                 (_grades(a=False, b=True, c=True), {**valid, "root": "lower the objective"}),
                 (_grades(a=False, b=True, c=True), {**valid, "depends_on": []}),
                 (_grades(a=False, b=True, c=True), {**valid, "revised_instruction": leaf["instruction"]}),
                 (_grades(a=False, b=True, c=True), {**valid, "diagnosis": "bad"})]
        for grades, change in cases:
            with self.subTest(change=change, grades=grades), self.assertRaises(InvalidAction):
                validate_replan(plan, leaf, grades, change)

    def test_progress_gets_execution_opportunity_before_a_new_replan(self):
        leaf = _plan()["leaves"]["S1"]
        before = _grades(a=False, b=False, c=False)
        progress = replan_decision(before, _grades(a=False, b=False, c=True), leaf)
        self.assertFalse(progress["needed"])
        self.assertEqual(progress["reason"], "gate_progress")
        self.assertEqual(progress["progressed_gates"], ["c"])
        self.assertEqual(progress["failed_gates"], ["a", "b"])
        stalled = replan_decision(before, before, leaf)
        self.assertTrue(stalled["needed"])
        self.assertEqual(stalled["reason"], "stalled_failed_leaf")

    def test_delivered_fault_requires_actual_failed_active_leaf(self):
        leaf = _plan()["leaves"]["S1"]
        passed = _grades(a=True, b=True, c=True)
        failed = _grades(a=False, b=True, c=True)
        self.assertTrue(replan_decision(passed, failed, leaf, fault_delivered=True)["needed"])
        self.assertFalse(replan_decision(passed, passed, leaf, fault_delivered=True)["needed"])
        self.assertFalse(replan_decision(passed, failed, None, fault_delivered=True)["needed"])
        self.assertFalse(replan_decision(failed, _grades(a=True, b=False, c=True), leaf)["needed"])


class _EvidenceTask:
    root_contract = {"objective": "Satisfy the fixed source, dependent, and independent gates."}
    dependencies = {"a": [], "b": ["a"], "c": []}
    gate_artifact_fields = {"a": ["a"], "b": ["b"], "c": ["c"]}


def _evidence_events(*, changed_unrelated=False, extra_model_dependency=False):
    plan, passed, failed = _plan(), _grades(a=True, b=True, c=True), _grades(a=False, b=True, c=True)
    if extra_model_dependency:
        plan["leaves"]["S3"]["depends_on"] = ["S1"]
    changed, diagnosis = validate_replan(plan, plan["leaves"]["S1"], failed,
        {"diagnosis": "The source field was corrupted by the controlled perturbation.",
         "revised_instruction": "Recompute the corrupted source field and verify its dependents."})
    before = {"a": 1, "b": 2, "c": {"nested": [3]}}
    damaged = {**copy.deepcopy(before), "a": 0}
    repaired = copy.deepcopy(before)
    if changed_unrelated:
        repaired["c"] = {"nested": [9]}
    spec = {**_EvidenceTask.root_contract, "environment": {"revision": 0}}

    def checkpoint(current_plan, grades, states):
        return {"type": "checkpoint", "plan": current_plan, "public_grades": grades,
                "leaf_statuses": states,
                "milestone_statuses": {"M1": states["S2"], "M2": states["S3"]}}

    request = {"root_contract": _EvidenceTask.root_contract, "task": spec,
               "leaf": plan["leaves"]["S1"], "public_feedback": failed, "artifact": damaged}
    return [
        {"type": "initial", "root_contract": _EvidenceTask.root_contract, "public_spec": spec},
        {"type": "shared_plan", "plan": plan},
        checkpoint(plan, passed, {"S1": "completed", "S2": "completed", "S3": "completed"}),
        {"type": "fault", "before_solution": before, "after_solution": damaged,
         "before_spec": spec, "after_spec": spec, "before_grades": passed, "after_grades": failed,
         "delivered": True,
         "fault": {"kind": "forced_subgoal", "perturbation_type": "subgoal", "target_gate": "a",
                   "changed_fields": ["a"], "domain_fault_delivered": True}},
        checkpoint(plan, failed, {"S1": "pending", "S2": "pending", "S3": "completed"}),
        {"type": "replan_decision", **replan_decision(passed, failed, plan["leaves"]["S1"], fault_delivered=True)},
        {"type": "request_started", "role": "replan", "request": request},
        {"type": "response", "role": "replan", "request": request,
         "record": {"text": canonical({"diagnosis": diagnosis,
             "revised_instruction": changed["leaves"]["S1"]["instruction"]})}},
        {"type": "replan", "leaf_id": "S1", "diagnosis": diagnosis,
         "before_plan": plan, "after_plan": changed, "public_grades": failed},
        checkpoint(changed, failed, {"S1": "pending", "S2": "pending", "S3": "completed"}),
        {"type": "patch", "before_solution": damaged, "after_solution": repaired},
        checkpoint(changed, passed, {"S1": "completed", "S2": "completed", "S3": "completed"}),
        {"type": "final_grade", "public_spec": spec, "passed": True},
    ]


class MechanismEvidenceTests(unittest.TestCase):
    def test_fault_dependency_reverification_and_nonvacuous_locality_are_observed(self):
        evidence = evidence_from_events(_evidence_events(), _EvidenceTask())
        self.assertTrue(evidence["root_preserved"])
        self.assertTrue(evidence["final_grade_called"])
        self.assertTrue(evidence["final_grade_passed"])
        self.assertTrue(evidence["fault"]["forced"])
        self.assertTrue(evidence["fault"]["domain_delivered"])
        self.assertEqual(evidence["tree"]["goal_count"], 6)
        self.assertEqual(evidence["tree"]["max_depth_edges"], 2)
        self.assertEqual(evidence["dependencies"],
                         {"invalidation_events": 1, "invalidated_goals": 1, "reverified_goals": 1})
        self.assertEqual(evidence["replanning"]["attempted"], 1)
        self.assertEqual(evidence["replanning"]["accepted"], 1)
        self.assertEqual(evidence["replanning"]["unnecessary"], 0)
        self.assertEqual(evidence["replanning"]["unrelated_goals_checked"], 1)
        self.assertEqual(evidence["replanning"]["unrelated_goals_unchanged"], 1)
        self.assertEqual(evidence["execution_locality"],
                         {"unrelated_artifact_fields_checked": 1,
                          "unrelated_artifact_fields_unchanged": 1,
                          "violations": 0, "nonvacuous_events": 1})
        self.assertEqual(evidence["trace"]["failure_causes_recorded"], 1)
        self.assertEqual(evidence["trace"]["model_diagnoses_recorded"], 1)
        self.assertEqual(evidence["trace"]["post_fault_target_replans"], 1)

    def test_recovery_requires_an_accepted_post_fault_revision_of_the_actual_target(self):
        events = _evidence_events()
        fault = next(event for event in events if event["type"] == "fault")
        accepted = next(event for event in events if event["type"] == "replan")
        other = copy.deepcopy(accepted)
        other["leaf_id"] = "S2"
        other["public_grades"] = _grades(a=True, b=False, c=True)
        other["after_plan"] = copy.deepcopy(other["before_plan"])
        other["after_plan"]["leaves"]["S2"]["instruction"] = "Recompute the still-failing dependent output."
        other["after_plan"]["leaves"]["S2"]["revision"] += 1
        no_domain_fault = copy.deepcopy(fault)
        no_domain_fault["delivered"] = False
        no_domain_fault["fault"]["domain_fault_delivered"] = False
        rejected = {"type": "rejected", "role": "replan", "reason": "Invalid replan fields"}
        cases = {
            "only_before_fault": [accepted, fault],
            "other_leaf_after_fault": [fault, other],
            "only_rejected_after_fault": [fault, rejected],
            "no_substantive_domain_fault": [no_domain_fault, accepted],
            "self_report_without_acceptance": [fault, rejected,
                {"type": "result", "result": {"post_fault_target_replans": 99}}],
        }
        for name, observation in cases.items():
            with self.subTest(name=name):
                evidence = evidence_from_events(observation, _EvidenceTask())
                self.assertEqual(evidence["trace"]["post_fault_target_replans"], 0)

    def test_repairing_target_does_not_hide_unrelated_artifact_modification(self):
        evidence = evidence_from_events(_evidence_events(changed_unrelated=True), _EvidenceTask())
        self.assertEqual(evidence["replanning"]["unrelated_goals_unchanged"], 1)
        self.assertEqual(evidence["execution_locality"]["unrelated_artifact_fields_checked"], 1)
        self.assertEqual(evidence["execution_locality"]["unrelated_artifact_fields_unchanged"], 0)
        self.assertEqual(evidence["execution_locality"]["violations"], 1)

    def test_unnecessary_model_dependencies_cannot_remove_unrelated_controls(self):
        evidence = evidence_from_events(_evidence_events(extra_model_dependency=True), _EvidenceTask())
        self.assertEqual(evidence["replanning"]["unrelated_goals_checked"], 1)
        self.assertEqual(evidence["execution_locality"]["unrelated_artifact_fields_checked"], 1)

    def test_chain_has_zero_unrelated_evidence_instead_of_a_vacuous_success(self):
        task = _EvidenceTask()
        task.dependencies = {"a": [], "b": ["a"], "c": ["b"]}
        evidence = evidence_from_events(_evidence_events(), task)
        self.assertEqual(evidence["replanning"]["unrelated_goals_checked"], 0)
        self.assertEqual(evidence["execution_locality"]["nonvacuous_events"], 0)
        self.assertEqual(evidence["execution_locality"]["unrelated_artifact_fields_unchanged"], 0)

    def test_rejected_root_request_is_distinct_from_an_actual_root_change(self):
        task = _EvidenceTask()
        events = [{"type": "response", "role": "execute",
                   "request": {"root_contract": task.root_contract, "task": task.root_contract},
                   "record": {"text": '{"patch":{"root":"lower target"},"explanation":"Change root"}'}},
                  {"type": "rejected", "role": "execute"}]
        evidence = evidence_from_events(events, task)
        self.assertTrue(evidence["root_preserved"])
        self.assertEqual(evidence["root_changes"],
                         {"explicit_edit_requests": 1, "rejected_edit_requests": 1, "actual_changes": 0})
        self.assertFalse(evidence["final_grade_called"])
        self.assertIsNone(evidence["final_grade_passed"])

    def test_replan_without_a_need_decision_is_not_counted_as_necessary(self):
        events = [event for event in _evidence_events() if event["type"] != "replan_decision"]
        evidence = evidence_from_events(events, _EvidenceTask())
        self.assertEqual(evidence["replanning"]["unnecessary"], 1)


def _rewrite_chain(path, mutate):
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


def _run_one(directory, responder=None, *, corrupt_final_root=False, condition="normal", profile="pilot"):
    manifest = build_manifest(profile, backend="oracle", model="OFFLINE_ORACLE")
    trial = next(t for t in manifest["trials"] if t["family"] == "data_transform"
                 and t["arm"] == "hierarchy_adaptive" and t["condition"] == condition)
    task = make_trial_task(trial, manifest["task_seed"])
    if corrupt_final_root:
        original_grade = task.grade

        def changed_root(solution, *, hidden=False):
            result = original_grade(solution, hidden=hidden)
            if hidden:
                task._contract["objective"] = "Silently changed objective during final grading."
            return result

        task.grade = changed_root
    result = study.run_trial(task, trial, manifest, responder or study.OracleResponder(), directory)
    trace = directory / "trials" / trial["trial_id"] / "trace.jsonl"
    return manifest, trial, result, trace, task


class RequirementReplayRegressions(unittest.TestCase):
    def test_forced_artifact_recovery_alone_does_not_prove_an_accepted_target_replan(self):
        class RejectReplan(study.OracleResponder):
            def respond(self, role, payload, **kwargs):
                record = super().respond(role, payload, **kwargs)
                if role == "replan":
                    record["text"] = '{"root":"Replace the immutable objective."}'
                return record

        for responder, expected in ((study.OracleResponder(), 1), (RejectReplan(), 0)):
            with self.subTest(accepted_target_replans=expected), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                manifest, trial, result, _, _ = _run_one(
                    directory, responder, condition="fault", profile="mechanism")
                self.assertEqual(result["status"], "PASS", result)
                self.assertTrue(result["recovered"])
                audited = study.audit_trial(directory, trial, manifest)
                self.assertEqual(audited["audit"], "PASS", audited)
                evidence = audited["mechanism_evidence"]
                self.assertTrue(evidence["fault"]["forced"])
                self.assertTrue(evidence["fault"]["domain_delivered"])
                self.assertEqual(evidence["trace"]["post_fault_target_replans"], expected)
                self.assertEqual(result["replans"], expected)

    def test_replay_rejects_a_valid_execute_action_falsely_recorded_as_rejected(self):
        class Claiming(study.OracleResponder):
            def respond(self, role, payload, **kwargs):
                record = super().respond(role, payload, **kwargs)
                if role == "execute":
                    record["text"] = '{"success":true}'
                return record

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest, trial, result, trace, task = _run_one(directory, Claiming())
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(study.audit_trial(directory, trial, manifest)["audit"], "PASS")

            def false_rejection(events):
                for event in events:
                    if event["type"] == "response" and event["role"] == "execute":
                        event["record"]["text"] = canonical(
                            {"patch": task.initial_solution(), "explanation": "A valid no-op artifact replacement."})

            _rewrite_chain(trace, false_rejection)
            audited = study.audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "FAIL", audited)
            self.assertEqual(audited["status"], "UNCERTAIN", audited)

    def test_replay_rejects_a_valid_replan_falsely_recorded_as_rejected(self):
        class InvalidReplan(study.OracleResponder):
            def respond(self, role, payload, **kwargs):
                record = super().respond(role, payload, **kwargs)
                if role == "replan":
                    record["text"] = '{"root":"Replace the immutable root objective."}'
                return record

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest, trial, result, trace, _ = _run_one(directory, InvalidReplan(), condition="fault")
            self.assertEqual(result["status"], "PASS")
            self.assertGreater(result["rejected_actions"], 0)
            original = study.audit_trial(directory, trial, manifest)
            self.assertEqual(original["audit"], "PASS")
            self.assertTrue(original["mechanism_evidence"]["root_preserved"])
            self.assertEqual(original["mechanism_evidence"]["root_changes"],
                             {"explicit_edit_requests": 1, "rejected_edit_requests": 1, "actual_changes": 0})

            def false_rejection(events):
                for event in events:
                    if event["type"] == "response" and event["role"] == "replan":
                        event["record"]["text"] = canonical({
                            "diagnosis": "The authoritative input changed and its gate now fails.",
                            "revised_instruction": "Recompute this failed leaf from the updated authoritative input."})

            _rewrite_chain(trace, false_rejection)
            audited = study.audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "FAIL", audited)
            self.assertEqual(audited["status"], "UNCERTAIN", audited)

    def test_replan_result_must_change_the_leaf_named_in_its_request(self):
        class FirstNoop(study.OracleResponder):
            def __init__(self):
                super().__init__()
                self.executions = 0

            def respond(self, role, payload, **kwargs):
                record = super().respond(role, payload, **kwargs)
                if role == "execute":
                    self.executions += 1
                    if self.executions == 1:
                        record["text"] = canonical({"patch": self.task.initial_solution(),
                            "explanation": "The first accepted artifact attempt made no progress."})
                return record

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest, trial, result, trace, _ = _run_one(directory, FirstNoop())
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["replans"], 1)
            self.assertEqual(study.audit_trial(directory, trial, manifest)["audit"], "PASS")

            def wrong_target(events):
                index = next(i for i, event in enumerate(events) if event["type"] == "replan")
                event = events[index]
                original = event["leaf_id"]
                other = next(ident for ident, leaf in event["before_plan"]["leaves"].items()
                             if ident != original and any(
                                 event["public_grades"][gate]["passed"] is False for gate in leaf["checks"]))
                altered = copy.deepcopy(event["before_plan"])
                altered["leaves"][other]["instruction"] = event["after_plan"]["leaves"][original]["instruction"]
                altered["leaves"][other]["revision"] += 1
                event["leaf_id"], event["after_plan"] = other, altered
                for later in events[index + 1:]:
                    if later["type"] == "checkpoint":
                        later["plan"] = copy.deepcopy(altered)
                    elif later["type"] in ("request_started", "response") and later["role"] == "execute":
                        later["request"]["plan"] = copy.deepcopy(altered)
                        current = later["request"].get("current_leaf")
                        if current is not None:
                            later["request"]["current_leaf"] = copy.deepcopy(altered["leaves"][current["id"]])
                    elif later["type"] == "replan_decision" and later.get("leaf") is not None:
                        later["leaf"] = copy.deepcopy(altered["leaves"][later["leaf"]["id"]])

            _rewrite_chain(trace, wrong_target)
            audited = study.audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "FAIL", audited)
            self.assertEqual(audited["status"], "UNCERTAIN", audited)

    def test_replay_rejects_budget_exhaustion_with_unused_allowance(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest, trial, result, trace, _ = _run_one(directory)
            self.assertEqual(result["status"], "PASS")
            self.assertLess(result["calls"], manifest["limits"]["max_calls"])

            def unsupported_failure(events):
                index = next(i for i, event in enumerate(events) if event["type"] == "final_grade")
                event = events[index]
                replacement = {key: value for key, value in event.items()
                               if key in ("sequence", "previous_sha256", "root_sha256", "event_sha256")}
                replacement.update(type="termination", status="FAIL", reason="BudgetExhausted",
                                   diagnostic="Logical request allowance exhausted", wall_seconds=0.01)
                events[index] = replacement
                events[-1]["result"].update(status="FAIL", success=False,
                                           diagnostic="Logical request allowance exhausted")

            _rewrite_chain(trace, unsupported_failure)
            audited = study.audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "FAIL", audited)
            self.assertEqual(audited["status"], "UNCERTAIN", audited)

    def test_root_change_at_final_boundary_cannot_be_runtime_success(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, result, _, _ = _run_one(Path(folder), corrupt_final_root=True)
            self.assertNotEqual(result["status"], "PASS", result)
            self.assertFalse(result["invariant_ok"], result)


if __name__ == "__main__":
    unittest.main()
