# SPDX-License-Identifier: Apache-2.0
"""Incremental scale execution survives canonical trace serialization.

These responders are offline fixtures.  They repair the current leaf's fields
only, so several independent branches remain runnable after each patch.  An
oracle that replaces the entire solution cannot expose the S2/S13 replay bug.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import hiergoal.study as study
from hiergoal.study_protocol import build_manifest, canonical, digest, make_trial_task, save


class IncrementalOracle(study.OracleResponder):
    def respond(self, role, payload, **kwargs):
        record = super().respond(role, payload, **kwargs)
        if role == "execute":
            gate = payload["current_leaf"]["checks"][0]
            fields = self.task.gate_artifact_fields[gate]
            reference = self.task.reference_solution()
            record["text"] = canonical({
                "patch": {field: reference[field] for field in fields},
                "explanation": "Offline incremental fixture repairs the active gate only.",
            })
        return record


def _run(directory, manifest, *, family="data_transform", size="medium",
         depth=3, density="sparse", arm="hierarchy_fixed", condition="normal"):
    trial = next(t for t in manifest["trials"] if t["family"] == family
                 and t["scale"] == {"size": size, "depth": depth, "density": density}
                 and t["arm"] == arm and t["condition"] == condition and t["repeat"] == 1)
    task = make_trial_task(trial, manifest["task_seed"])
    result = study.run_trial(task, trial, manifest, IncrementalOracle(), directory)
    trace = directory / "trials" / trial["trial_id"] / "trace.jsonl"
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    return trial, result, trace, events


def _rewrite(trace, events):
    """Make the chain and terminal receipt agree, leaving semantic checks to reject it."""
    previous = "0" * 64
    for index, event in enumerate(events):
        event["sequence"], event["previous_sha256"] = index, previous
        event.pop("event_sha256", None)
        event["event_sha256"] = digest(event)
        previous = event["event_sha256"]
    trace.write_text("".join(canonical(event) + "\n" for event in events), encoding="utf-8")
    save(trace.with_name("result.json"), {**events[-1]["result"], "trace_final_sha256": previous})


class IncrementalPlanOrderTests(unittest.TestCase):
    def test_incremental_medium_and_large_traces_replay_after_json_roundtrip(self):
        manifest = build_manifest("scale", backend="oracle", model="OFFLINE_ORACLE")
        cases = (
            ("data_transform", "medium", 3, "sparse", 16),
            ("code_repair", "large", 3, "sparse", 32),
            ("scheduling", "large", 5, "dense", 48),
        )
        for family, size, depth, density, leaves in cases:
            with self.subTest(family=family, size=size, depth=depth), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                trial, result, _, events = _run(directory, manifest, family=family,
                    size=size, depth=depth, density=density)
                self.assertEqual(result["status"], "PASS", result)
                self.assertGreater(result["patch_actions"], 1)
                shared = next(e for e in events if e["type"] == "shared_plan")
                # The trace has actually been read back through sorted JSON;
                # do not accidentally test the original in-memory dictionary.
                keys = list(shared["plan"]["leaves"])
                self.assertEqual(len(keys), leaves)
                self.assertEqual(keys, sorted(keys))
                self.assertNotEqual(keys, ["S" + str(i) for i in range(1, leaves + 1)])
                requested = [e["request"]["current_leaf"]["id"] for e in events
                             if e["type"] == "request_started" and e["role"] == "execute"]
                self.assertTrue(any(int(sid[1:]) >= 10 for sid in requested))
                if family == "data_transform":
                    decision = next(e for e in events if e["type"] == "replan_decision")
                    self.assertEqual(decision["leaf_id"], "S2")
                    # Lexical key iteration would select S13 in this same
                    # observed post-patch state; the replay must reproduce S2.
                    wrong = study.active_leaf(shared["plan"], decision["after_grades"])
                    self.assertEqual(wrong["id"], "S13")
                audited = study.audit_trial(directory, trial, manifest)
                self.assertEqual(audited["audit"], "PASS", audited)
                self.assertEqual(audited["status"], "PASS", audited)
                self.assertTrue(audited["mechanism_evidence"]["final_grade_passed"])

    def test_incremental_reused_shared_plan_and_forced_recovery_replay(self):
        manifest = build_manifest("scale", backend="oracle", model="OFFLINE_ORACLE")
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            first, first_result, _, _ = _run(directory, manifest)
            self.assertEqual(first_result["status"], "PASS", first_result)
            self.assertEqual(study.audit_trial(directory, first, manifest)["audit"], "PASS")
            trial, result, _, events = _run(directory, manifest,
                arm="hierarchy_adaptive", condition="fault")
            self.assertEqual(result["status"], "PASS", result)
            response = next(e for e in events if e["type"] == "response" and e["role"] == "plan")
            self.assertTrue(response["reused_shared_plan"])
            self.assertTrue(result["fault_delivered"])
            self.assertTrue(result["recovered"])
            self.assertGreater(result["replans"], 0)
            audited = study.audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "PASS", audited)
            self.assertTrue(audited["mechanism_evidence"]["root_preserved"])
            self.assertGreater(audited["mechanism_evidence"]["trace"]["post_fault_target_replans"], 0)

    def test_rehashed_wrong_leaf_is_rejected_instead_of_accepting_any_ready_leaf(self):
        manifest = build_manifest("scale", backend="oracle", model="OFFLINE_ORACLE")
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            trial, result, trace, events = _run(directory, manifest)
            self.assertEqual(result["status"], "PASS", result)
            self.assertEqual(study.audit_trial(directory, trial, manifest)["audit"], "PASS")
            shared = next(e for e in events if e["type"] == "shared_plan")
            decision = next(e for e in events if e["type"] == "replan_decision")
            self.assertEqual(decision["leaf_id"], "S2")
            decision["leaf"] = copy.deepcopy(shared["plan"]["leaves"]["S13"])
            decision["leaf_id"] = "S13"
            _rewrite(trace, events)
            audited = study.audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "FAIL", audited)
            self.assertEqual(audited["status"], "UNCERTAIN", audited)

    def test_reconstruction_does_not_hide_a_forged_shared_plan(self):
        manifest = build_manifest("scale", backend="oracle", model="OFFLINE_ORACLE")
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            trial, result, trace, events = _run(directory, manifest)
            self.assertEqual(result["status"], "PASS", result)
            self.assertEqual(study.audit_trial(directory, trial, manifest)["audit"], "PASS")
            shared_event = next(e for e in events if e["type"] == "shared_plan")
            shared_path = directory / "plans" / (shared_event["key"] + ".json")
            shared = json.loads(shared_path.read_text(encoding="utf-8"))
            forged = "This plausible instruction was never present in the model response."
            shared_event["plan"]["leaves"]["S2"]["instruction"] = forged
            shared["plan"]["leaves"]["S2"]["instruction"] = forged
            save(shared_path, shared)
            _rewrite(trace, events)
            # The shared file and trace now agree and their hashes are valid.
            # Rebuilding a good plan must not erase this model-output mismatch.
            audited = study.audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "FAIL", audited)
            self.assertEqual(audited["status"], "UNCERTAIN", audited)


if __name__ == "__main__":
    unittest.main()
