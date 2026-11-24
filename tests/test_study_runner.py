# SPDX-License-Identifier: Apache-2.0
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hiergoal.study import (
    InvalidAction, OracleResponder, apply_patch, audit_trial, collect, object_reply,
    plan_prompt, prepare, run, run_trial, validate_plan,
)
from hiergoal.study_api import TransportError
from hiergoal.study_protocol import ARMS, build_manifest, canonical, digest, save, validate_manifest
from hiergoal.study_tasks import make_task


def trial_for(manifest, arm="hierarchy_adaptive", condition="fault", family="data_transform"):
    return next(t for t in manifest["trials"] if t["arm"] == arm and t["condition"] == condition and t["family"] == family)


def rewrite_chain(path, mutate):
    events = [json.loads(line) for line in path.read_text().splitlines()]
    mutate(events)
    previous = "0" * 64
    for index, event in enumerate(events):
        event["sequence"], event["previous_sha256"] = index, previous
        event.pop("event_sha256", None)
        event["event_sha256"] = digest(event)
        previous = event["event_sha256"]
    path.write_text("".join(canonical(e) + "\n" for e in events))
    result_path = path.with_name("result.json")
    result = json.loads(result_path.read_text())
    result["trace_final_sha256"] = previous
    save(result_path, result)


class StudyProtocolTests(unittest.TestCase):
    def test_schedule_and_dev_heldout_separation(self):
        pilot, study = build_manifest("pilot"), build_manifest("study")
        self.assertEqual(len(pilot["trials"]), 18)
        self.assertEqual(len(study["trials"]), 216)
        self.assertEqual(len(study["tasks"]), 12)
        self.assertTrue({t["task_id"] for t in pilot["tasks"]}.isdisjoint(t["task_id"] for t in study["tasks"]))
        blocks = {}
        for trial in study["trials"]:
            blocks.setdefault(trial["block_id"], []).append(trial["arm"])
        self.assertTrue(all(sorted(a) == sorted(ARMS) for a in blocks.values()))
        self.assertEqual(study, build_manifest("study"))

    def test_manifest_edit_or_source_edit_is_detected(self):
        manifest = build_manifest("pilot")
        validate_manifest(manifest)
        changed = copy.deepcopy(manifest)
        changed["trials"].pop()
        with self.assertRaises(ValueError):
            validate_manifest(changed)
        with patch("hiergoal.study_protocol.source_hashes", return_value={}):
            with self.assertRaises(ValueError):
                validate_manifest(manifest)

    def test_no_live_transport_in_prepare_or_collect(self):
        with tempfile.TemporaryDirectory() as tmp, patch("hiergoal.study.OpenAIResponder") as live:
            directory = Path(tmp) / "prepared"
            prepare(directory)
            collect(directory)
            live.assert_not_called()
            results = json.loads((directory / "results.json").read_text())
            self.assertTrue(all(r["status"] == "NOT_RUN" for r in results))
            with self.assertRaises(ValueError):
                run(directory)
            live.assert_not_called()


class StudyPlanTests(unittest.TestCase):
    def setUp(self):
        self.task = make_task("code_repair", 0, split="dev")
        oracle = OracleResponder()
        oracle.task = self.task
        self.document = object_reply(oracle.respond("plan", plan_prompt(self.task), max_output_tokens=2048))

    def test_valid_plan_and_frozen_root(self):
        plan = validate_plan(self.document, self.task)
        self.assertEqual(len(plan["leaves"]), 3)
        self.document["root"] = "different objective"
        with self.assertRaises(InvalidAction):
            validate_plan(self.document, self.task)

    def test_cycles_missing_gates_and_task_dependency_omissions(self):
        for change in ("cycle", "missing", "omitted"):
            with self.subTest(change=change):
                document = copy.deepcopy(self.document)
                leaves = [s for m in document["milestones"] for s in m["subgoals"]]
                if change == "cycle":
                    leaves[0]["depends_on"] = [leaves[-1]["id"]]
                elif change == "missing":
                    leaves[-1]["checks"] = leaves[0]["checks"]
                else:
                    leaves[-1]["depends_on"] = []
                with self.assertRaises(InvalidAction):
                    validate_plan(document, self.task)

    def test_patch_cannot_mutate_contract_or_claim_success(self):
        initial = self.task.initial_solution()
        for action in ({"success": True}, {"patch": {"root": "lower target"}, "explanation": "Change objective"},
                       {"patch": initial, "explanation": "valid note", "plan": {}}):
            with self.assertRaises(InvalidAction):
                apply_patch(initial, action)
        self.assertEqual(initial, self.task.initial_solution())


class StudyExecutionTests(unittest.TestCase):
    def test_all_cells_offline_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp, patch("hiergoal.study.OpenAIResponder") as live:
            directory = Path(tmp)
            manifest = prepare(directory, backend="oracle", model="OFFLINE_ORACLE")
            run(directory)
            live.assert_not_called()
            results = json.loads((directory / "results.json").read_text())
            self.assertEqual(len(results), 18)
            self.assertTrue(all(r["status"] == "PASS" and r["audit"] == "PASS" for r in results), results)
            self.assertTrue(all(r["actual_calls"] == 0 and r["simulated"] for r in results))
            self.assertEqual(len(list((directory / "plans").glob("*.json"))), 3)
            adaptive = [r for t, r in zip(manifest["trials"], results)
                        if t["arm"] == "hierarchy_adaptive" and t["condition"] == "fault" and r["fault_delivered"]]
            self.assertTrue(adaptive)
            self.assertTrue(all(r["replans"] > 0 and r["recovered"] for r in adaptive))
            with self.assertRaises(ValueError):
                run(directory)

    def _one(self, directory, arm="hierarchy_adaptive", responder=None):
        manifest = build_manifest("pilot", backend="oracle", model="OFFLINE_ORACLE")
        trial = trial_for(manifest, arm=arm)
        task = make_task(trial["family"], trial["instance"], split=trial["split"])
        result = run_trial(task, trial, manifest, responder or OracleResponder(), directory)
        return manifest, trial, result

    def test_fixed_retry_uses_new_environment_without_rewriting_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, trial, result = self._one(Path(tmp), arm="hierarchy_fixed")
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["fault_delivered"])
            self.assertEqual(result["replans"], 0)
            self.assertEqual(audit_trial(Path(tmp), trial, manifest)["audit"], "PASS")

    def test_claimed_success_cannot_pass(self):
        class Claiming(OracleResponder):
            def respond(self, role, payload, **kwargs):
                result = super().respond(role, payload, **kwargs)
                if role == "execute":
                    result["text"] = '{"success":true}'
                return result
        with tempfile.TemporaryDirectory() as tmp:
            manifest, trial, result = self._one(Path(tmp), responder=Claiming())
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["calls"], manifest["limits"]["max_calls"])
            self.assertEqual(result["rejected_actions"], 11)
            self.assertEqual(audit_trial(Path(tmp), trial, manifest)["audit"], "PASS")

    def test_untriggered_fault_is_retained(self):
        class Idle(OracleResponder):
            def respond(self, role, payload, **kwargs):
                result = super().respond(role, payload, **kwargs)
                if role == "execute":
                    result["text"] = canonical({"patch": self.task.initial_solution(), "explanation": "Unsuccessful repeat attempt"})
                return result
        with tempfile.TemporaryDirectory() as tmp:
            manifest, trial, result = self._one(Path(tmp), responder=Idle())
            self.assertEqual(result["status"], "FAIL")
            self.assertFalse(result["fault_triggered"])
            self.assertFalse(result["fault_delivered"])
            self.assertIsNone(result["recovered"])

    def test_transport_failure_is_uncertain(self):
        class Failed(OracleResponder):
            def respond(self, role, payload, **kwargs):
                raise TransportError("OFFLINE_SIMULATED_TIMEOUT")
        with tempfile.TemporaryDirectory() as tmp:
            _, _, result = self._one(Path(tmp), responder=Failed())
            self.assertEqual(result["status"], "UNCERTAIN")
            self.assertIsNone(result["success"])
            self.assertTrue(result["stop_batch"])
            self.assertEqual(result["calls"], 1)
            self.assertIsNone(result["input_tokens"])
            self.assertIsNone(result["output_tokens"])

    def test_tampering_cannot_preserve_pass_even_with_recomputed_hash_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            manifest, trial, result = self._one(directory)
            trace = directory / "trials" / trial["trial_id"] / "trace.jsonl"
            def corrupt(events):
                final = next(e for e in events if e["type"] == "final_grade")
                final["solution"] = {}
            rewrite_chain(trace, corrupt)
            audited = audit_trial(directory, trial, manifest)
            self.assertEqual(audited["status"], "UNCERTAIN")
            self.assertEqual(audited["audit"], "FAIL")

    def test_missing_trace_cannot_preserve_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            manifest, trial, result = self._one(directory)
            (directory / "trials" / trial["trial_id"] / "trace.jsonl").unlink()
            self.assertEqual(audit_trial(directory, trial, manifest)["status"], "UNCERTAIN")

    def test_interrupted_started_trial_is_uncertain_with_partial_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            manifest, trial, result = self._one(directory)
            trial_dir = directory / "trials" / trial["trial_id"]
            (trial_dir / "result.json").unlink()
            lines = (trial_dir / "trace.jsonl").read_text().splitlines()
            # Retain a verified prefix that ends during an actual request.
            last_start = max(i for i, line in enumerate(lines) if json.loads(line)["type"] == "request_started")
            (trial_dir / "trace.jsonl").write_text("\n".join(lines[:last_start + 1]) + "\n")
            partial = audit_trial(directory, trial, manifest)
            self.assertEqual(partial["status"], "UNCERTAIN")
            self.assertEqual(partial["pending_requests"], 1)
            self.assertGreater(partial["known_input_tokens"], 0)
            self.assertIsNone(partial["input_tokens"])

    def test_no_private_payload_reaches_live_interface(self):
        class Observing(OracleResponder):
            def respond(self, role, payload, **kwargs):
                serialized = canonical(payload)
                for forbidden in ("reference_solution", "hidden_grades", "private_probes", "_environment"):
                    if forbidden in serialized:
                        raise AssertionError("Private evaluator data in responder request")
                return super().respond(role, payload, **kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            _, _, result = self._one(Path(tmp), responder=Observing())
            self.assertEqual(result["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
