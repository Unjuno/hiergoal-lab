# SPDX-License-Identifier: Apache-2.0
"""Mandatory transition evidence; every responder and mutation is offline."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hiergoal.study as study
from hiergoal.study_api import TransportError
from hiergoal.study_protocol import ARMS, FAMILIES, PROFILES, build_manifest, canonical, digest, make_trial_task, save


def _run(directory, *, profile="mechanism", arm="hierarchy_adaptive", condition="fault",
         family="data_transform", responder=None, manifest=None):
    manifest = manifest or build_manifest(profile, backend="oracle", model="OFFLINE_ORACLE")
    trial = next(t for t in manifest["trials"] if t["family"] == family and t["arm"] == arm
                 and t["condition"] == condition and t["repeat"] == 1 and t["instance"] == 0)
    task = make_trial_task(trial, manifest["task_seed"])
    result = study.run_trial(task, trial, manifest, responder or study.OracleResponder(), directory)
    trace = directory / "trials" / trial["trial_id"] / "trace.jsonl"
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    return manifest, trial, result, trace, events, task


def _rewrite(trace, events):
    previous = "0" * 64
    for index, event in enumerate(events):
        event["sequence"], event["previous_sha256"] = index, previous
        event.pop("event_sha256", None)
        event["event_sha256"] = digest(event)
        previous = event["event_sha256"]
    trace.write_text("".join(canonical(event) + "\n" for event in events), encoding="utf-8")
    save(trace.with_name("result.json"), {**events[-1]["result"], "trace_final_sha256": previous})


class MandatoryTransitionEvidenceTests(unittest.TestCase):
    def test_deleting_duplicating_or_reordering_any_checkpoint_is_rejected(self):
        # Covers initial flat/shared-plan boundaries, patches, fault/sham, and
        # accepted replans. Rehashing prevents a checksum failure from masking
        # a missing semantic sequence check.
        for arm in ("flat_retry", "hierarchy_adaptive"):
            for condition in ("normal", "fault"):
                with tempfile.TemporaryDirectory() as folder:
                    directory = Path(folder)
                    manifest, trial, result, trace, baseline, _ = _run(
                        directory, arm=arm, condition=condition)
                    self.assertEqual(result["status"], "PASS")
                    self.assertEqual(study.audit_trial(directory, trial, manifest)["audit"], "PASS")
                    for index, event in enumerate(baseline):
                        if event["type"] != "checkpoint":
                            continue
                        for mutation in ("delete", "duplicate", "move_after_next"):
                            with self.subTest(arm=arm, condition=condition, index=index, mutation=mutation):
                                changed = copy.deepcopy(baseline)
                                if mutation == "delete":
                                    changed.pop(index)
                                elif mutation == "duplicate":
                                    changed.insert(index + 1, copy.deepcopy(changed[index]))
                                else:
                                    changed[index], changed[index + 1] = changed[index + 1], changed[index]
                                _rewrite(trace, changed)
                                audited = study.audit_trial(directory, trial, manifest)
                                self.assertEqual(audited["audit"], "FAIL", audited)
                                self.assertEqual(audited["status"], "UNCERTAIN", audited)

    def test_all_profiles_families_arms_and_conditions_have_complete_transition_sequences(self):
        for profile in PROFILES:
            manifest = build_manifest(profile, backend="oracle", model="OFFLINE_ORACLE")
            with tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                for family in FAMILIES:
                    for arm in ARMS:
                        for condition in ("normal", "fault"):
                            with self.subTest(profile=profile, family=family, arm=arm, condition=condition):
                                _, trial, result, _, _, _ = _run(directory, manifest=manifest,
                                    profile=profile, family=family, arm=arm, condition=condition)
                                self.assertEqual(result["status"], "PASS", result)
                                audited = study.audit_trial(directory, trial, manifest)
                                self.assertEqual(audited["audit"], "PASS", audited)

    def test_transport_and_response_budget_stops_remain_auditable(self):
        for role_to_stop in ("plan", "execute", "replan"):
            for reason in ("transport", "tokens"):
                with self.subTest(role=role_to_stop, reason=reason), tempfile.TemporaryDirectory() as folder:
                    manifest = build_manifest("mechanism", backend="oracle", model="OFFLINE_ORACLE")

                    class Stop(study.OracleResponder):
                        def respond(self, role, payload, **kwargs):
                            if role == role_to_stop and reason == "transport":
                                raise TransportError("OFFLINE_TEST_INTERRUPTION")
                            record = super().respond(role, payload, **kwargs)
                            if role == role_to_stop and reason == "tokens":
                                record["input_tokens"] = manifest["limits"]["max_total_tokens"] + 1
                                record["usage"]["input_tokens"] = record["input_tokens"]
                            return record

                    directory = Path(folder)
                    _, trial, result, _, _, _ = _run(directory, manifest=manifest, responder=Stop())
                    self.assertEqual(result["status"], "UNCERTAIN" if reason == "transport" else "FAIL")
                    self.assertEqual(study.audit_trial(directory, trial, manifest)["audit"], "PASS")

    def test_apparatus_interruption_during_checkpoint_cannot_claim_complete_protocol(self):
        for checkpoint_number in (1, 2):
            with self.subTest(checkpoint=checkpoint_number), tempfile.TemporaryDirectory() as folder:
                directory, calls = Path(folder), 0
                original = study.statuses

                def interrupted(plan, grades):
                    nonlocal calls
                    calls += 1
                    if calls == checkpoint_number:
                        raise ArithmeticError("OFFLINE_TEST_CHECKPOINT_ERROR")
                    return original(plan, grades)

                with patch("hiergoal.study.statuses", side_effect=interrupted):
                    manifest, trial, result, trace, events, _ = _run(directory)
                self.assertEqual(result["status"], "UNCERTAIN")
                self.assertFalse(result["protocol_ok"])
                self.assertEqual(study.audit_trial(directory, trial, manifest)["audit"], "PASS")
                events[-1]["result"]["protocol_ok"] = True
                _rewrite(trace, events)
                self.assertEqual(study.audit_trial(directory, trial, manifest)["audit"], "FAIL")

    def test_final_grading_rejects_an_unconsumed_recorded_response(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest, trial, result, trace, events, task = _run(
                directory, profile="pilot", arm="flat_retry", condition="normal")
            self.assertEqual(result["status"], "PASS")
            final_index = next(i for i, event in enumerate(events) if event["type"] == "final_grade")
            final = events[final_index]
            action = next(event["action"] for event in events if event["type"] == "patch")
            history = [{"action": action, "public_feedback": final["public_grades"]}]
            request = study.action_prompt("execute", task, final["solution"], final["public_grades"],
                                         None, None, history)
            responder = study.OracleResponder()
            responder.task = task
            record = responder.respond("execute", request, max_output_tokens=2048)
            record["text"] = canonical({"patch": task.initial_solution(),
                "explanation": "This unconsumed action would corrupt the final valid artifact."})
            root_hash = events[0]["root_sha256"]
            events[final_index:final_index] = [
                {"type": "request_started", "role": "execute", "request": request, "root_sha256": root_hash},
                {"type": "response", "role": "execute", "request": request, "record": record,
                 "reused_shared_plan": False, "logical_call": result["calls"] + 1, "root_sha256": root_hash},
            ]
            terminal = events[-1]["result"]
            terminal["calls"] += 1
            terminal["input_tokens"] += record["input_tokens"]
            terminal["output_tokens"] += record["output_tokens"]
            _rewrite(trace, events)
            audited = study.audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "FAIL", audited)
            self.assertEqual(audited["status"], "UNCERTAIN", audited)


if __name__ == "__main__":
    unittest.main()
