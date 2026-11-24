# SPDX-License-Identifier: Apache-2.0
"""Semantic replay regressions found in the second nine-requirement audit."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from hiergoal.study import OracleResponder, audit_trial, plan_prompt, run_trial
from hiergoal.study_mechanisms import evidence_from_events, same_json
from hiergoal.study_protocol import build_manifest, canonical, digest, make_trial_task, save


def _run(directory, responder=None, *, profile="pilot", condition="normal",
         arm="hierarchy_adaptive", manifest=None):
    manifest = manifest or build_manifest(profile, backend="oracle", model="OFFLINE_ORACLE")
    trial = next(t for t in manifest["trials"] if t["family"] == "data_transform"
                 and t["arm"] == arm and t["condition"] == condition)
    task = make_trial_task(trial, manifest["task_seed"])
    result = run_trial(task, trial, manifest, responder or OracleResponder(), directory)
    trace = directory / "trials" / trial["trial_id"] / "trace.jsonl"
    return manifest, trial, result, trace


def _read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _rewrite(path, mutate):
    events = _read(path)
    mutate(events)
    previous = "0" * 64
    for index, event in enumerate(events):
        event["sequence"], event["previous_sha256"] = index, previous
        event.pop("event_sha256", None)
        event["event_sha256"] = digest(event)
        previous = event["event_sha256"]
    path.write_text("".join(canonical(event) + "\n" for event in events), encoding="utf-8")
    save(path.with_name("result.json"), {**events[-1]["result"], "trace_final_sha256": previous})


class TerminalAndSharedPlanReplayTests(unittest.TestCase):
    def test_unknown_or_uncertain_only_reason_cannot_manufacture_method_failure(self):
        for reason in ("FabricatedReason", "TransportError", "ApparatusError"):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                manifest, trial, result, trace = _run(directory)
                self.assertEqual(result["status"], "PASS")

                def corrupt(events):
                    index = next(i for i, event in enumerate(events) if event["type"] == "final_grade")
                    events[index] = {"root_sha256": events[index]["root_sha256"], "type": "termination",
                                     "status": "FAIL", "reason": reason, "diagnostic": "Fabricated method failure"}
                    events[-1]["result"].update(status="FAIL", success=False, diagnostic="Fabricated method failure")

                _rewrite(trace, corrupt)
                audited = audit_trial(directory, trial, manifest)
                self.assertEqual(audited["audit"], "FAIL", audited)
                self.assertEqual(audited["status"], "UNCERTAIN", audited)

    def test_invalid_initial_plan_cannot_be_superseded_by_a_reused_response(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest, trial, result, trace = _run(directory)
            self.assertEqual(result["status"], "PASS")

            def insert_reroll(events):
                index = next(i for i, event in enumerate(events) if event["type"] == "response" and event["role"] == "plan")
                good = copy.deepcopy(events[index])
                events[index]["record"]["text"] = '{"success":true}'
                good["reused_shared_plan"] = True
                good["logical_call"] += 1
                for later in events[index + 1:]:
                    if later["type"] == "response":
                        later["logical_call"] += 1
                events.insert(index + 1, good)
                terminal = events[-1]["result"]
                terminal["calls"] += 1
                for field in ("input_tokens", "output_tokens", "elapsed_seconds"):
                    terminal[field] += good["record"][field]

            _rewrite(trace, insert_reroll)
            audited = audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "FAIL", audited)
            self.assertEqual(audited["status"], "UNCERTAIN", audited)

    def test_failed_shared_plan_must_match_the_recorded_response(self):
        class BadPlan(OracleResponder):
            def respond(self, role, payload, **kwargs):
                record = super().respond(role, payload, **kwargs)
                if role == "plan":
                    record["text"] = '{"success":true}'
                return record

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest, trial, result, trace = _run(directory, BadPlan())
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(audit_trial(directory, trial, manifest)["audit"], "PASS")
            task = make_trial_task(trial, manifest["task_seed"])
            oracle = OracleResponder()
            oracle.task = task
            valid_record = oracle.respond("plan", plan_prompt(task), max_output_tokens=2048)

            def different_response(events):
                next(event for event in events if event["type"] == "response")["record"] = valid_record

            _rewrite(trace, different_response)
            audited = audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "FAIL", audited)
            self.assertEqual(audited["status"], "UNCERTAIN", audited)

    def test_real_shared_plan_reuse_still_passes_in_the_initial_slot(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest, first_trial, first, _ = _run(directory, arm="hierarchy_fixed")
            manifest, trial, result, trace = _run(directory, manifest=manifest)
            self.assertEqual(first["status"], "PASS")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(first_trial["task_id"], trial["task_id"])
            events = _read(trace)
            planning = [event for event in events if event["type"] == "response" and event["role"] == "plan"]
            self.assertEqual(len(planning), 1)
            self.assertIs(planning[0]["reused_shared_plan"], True)
            self.assertFalse(any(event["type"] == "request_started" and event["role"] == "plan" for event in events))
            self.assertEqual(audit_trial(directory, trial, manifest)["audit"], "PASS")


class StrictJsonEvidenceTests(unittest.TestCase):
    def test_comparison_preserves_json_types_and_ignores_only_object_key_order(self):
        self.assertTrue(same_json({"x": [1, True, 1.0], "y": None}, {"y": None, "x": [1, True, 1.0]}))
        for left, right in ((1, 1.0), (True, 1), (False, 0), ({"x": [1]}, {"x": [True]})):
            with self.subTest(left=left, right=right):
                self.assertFalse(same_json(left, right))

    def test_recorded_root_must_match_its_fingerprint_with_exact_json_types(self):
        for field, convert in (("seed", float), ("contract_version", bool)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                manifest, trial, result, trace = _run(directory)
                self.assertEqual(result["status"], "PASS")

                def alter_root(events):
                    events[0]["root_contract"][field] = convert(events[0]["root_contract"][field])
                    self.assertNotEqual(digest(events[0]["root_contract"]), events[0]["root_sha256"])

                _rewrite(trace, alter_root)
                audited = audit_trial(directory, trial, manifest)
                self.assertEqual(audited["audit"], "FAIL", audited)

        task = SimpleNamespace(root_contract={"seed": 1}, dependencies={}, gate_artifact_fields={})
        evidence = evidence_from_events([{"type": "initial", "root_contract": {"seed": 1.0}}], task)
        self.assertFalse(evidence["root_preserved"])
        self.assertEqual(evidence["root_changes"]["actual_changes"], 1)

    def test_rehashed_structured_snapshots_reject_equal_valued_type_changes(self):
        def initial_spec(events):
            events[0]["public_spec"]["seed"] = float(events[0]["public_spec"]["seed"])

        def request_feedback(events):
            for event in events:
                if event["type"] in ("request_started", "response") and event["role"] == "execute":
                    grade = next(iter(event["request"]["public_feedback"].values()))
                    grade["passed"] = int(grade["passed"])

        def patch_snapshot(events):
            event = next(event for event in events if event["type"] == "patch")
            row = event["after_solution"]["rows"][0]
            row["quantity"] = float(row["quantity"])

        def plan_snapshot(events):
            event = next(event for event in events if event["type"] == "checkpoint")
            next(iter(event["plan"]["leaves"].values()))["revision"] = False

        def fault_receipt(events):
            event = next(event for event in events if event["type"] == "fault")
            event["fault"]["environment_revision"] = float(event["fault"]["environment_revision"])

        def final_grades(events):
            event = next(event for event in events if event["type"] == "final_grade")
            next(iter(event["hidden_grades"].values()))["passed"] = 1

        for mutate in (initial_spec, request_feedback, patch_snapshot, plan_snapshot, fault_receipt, final_grades):
            with self.subTest(boundary=mutate.__name__), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                manifest, trial, result, trace = _run(directory, condition="fault")
                self.assertEqual(result["status"], "PASS")
                _rewrite(trace, mutate)
                self.assertEqual(audit_trial(directory, trial, manifest)["audit"], "FAIL")

    def test_result_file_cannot_use_boolean_alias_for_recorded_elapsed_time(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest, trial, result, trace = _run(directory)
            self.assertEqual(result["elapsed_seconds"], 0.0)
            result["elapsed_seconds"] = False
            save(trace.with_name("result.json"), result)
            self.assertEqual(audit_trial(directory, trial, manifest)["audit"], "FAIL")

    def test_real_unrelated_integer_to_float_then_restore_is_a_locality_violation(self):
        class ChangeUnrelatedType(OracleResponder):
            def __init__(self):
                super().__init__()
                self.executions, self.target, self.unrelated = 0, None, None

            def respond(self, role, payload, **kwargs):
                record = super().respond(role, payload, **kwargs)
                if role == "replan":
                    self.target = payload["leaf"]["checks"][0]
                if role == "execute":
                    self.executions += 1
                    if self.executions == 2:
                        reply = json.loads(record["text"])
                        component = self.target.split("_", 1)[0]
                        self.unrelated = next(key for key in reply["patch"]
                                              if key.endswith("_rows") and key.split("_", 1)[0] != component)
                        row = reply["patch"][self.unrelated][0]
                        row["quantity"] = float(row["quantity"])
                        record["text"] = canonical(reply)
                return record

        with tempfile.TemporaryDirectory() as folder:
            directory, responder = Path(folder), ChangeUnrelatedType()
            manifest, trial, result, trace = _run(directory, responder, profile="mechanism", condition="fault")
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["recovered"])
            audited = audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "PASS", audited)
            events = _read(trace)
            fault_index = next(i for i, event in enumerate(events) if event["type"] == "fault")
            repair_index = next(i for i in range(fault_index + 1, len(events)) if events[i]["type"] == "patch")
            checkpoint = next(event for event in events[repair_index + 1:] if event["type"] == "checkpoint")
            before = events[fault_index]["before_solution"][responder.unrelated]
            after = events[repair_index]["after_solution"][responder.unrelated]
            self.assertEqual(before, after)  # Python equality concealed the actual JSON type change.
            self.assertNotEqual(digest(before), digest(after))
            self.assertFalse(checkpoint["public_grades"][responder.unrelated]["passed"])
            locality = audited["mechanism_evidence"]["execution_locality"]
            self.assertEqual(locality["violations"], 1)
            self.assertEqual(locality["unrelated_artifact_fields_checked"] - locality["unrelated_artifact_fields_unchanged"], 1)


if __name__ == "__main__":
    unittest.main()
