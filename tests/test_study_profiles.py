# SPDX-License-Identifier: Apache-2.0
"""Offline integration of frozen profiles, composite faults, replay, and reports."""
import copy
import json
import tempfile
import unittest
from collections import Counter, defaultdict
from pathlib import Path
from unittest.mock import patch

from hiergoal.study import OracleResponder, audit_trial, run_trial
from hiergoal.study_analysis import analyze, render_markdown
from hiergoal.study_mechanisms import InvalidAction
from hiergoal.study_planning import _validate_structure, validate_plan
from hiergoal.study_protocol import (
    ARMS, CONDITIONS, FAMILIES, PROFILES, build_manifest, digest, make_trial_task,
    validate_manifest,
)


def recorded_trial(directory, manifest, trial):
    """Run a real task/controller/replay path using only the offline oracle."""
    task = make_trial_task(trial, manifest["task_seed"])
    original_root = task.root_contract
    result = run_trial(task, trial, manifest, OracleResponder(), directory)
    audited = audit_trial(directory, trial, manifest)
    trace_path = directory / "trials" / trial["trial_id"] / "trace.jsonl"
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    return task, original_root, result, audited, events


class StudyProfileIntegration(unittest.TestCase):
    def test_all_five_profiles_have_complete_unique_paired_schedules(self):
        # Counts are protocol expectations, not sample-size adequacy claims.
        expected = {
            "pilot": (3, 18, 1),
            "study": (12, 216, 3),
            "mechanism": (6, 108, 3),
            "scale": (21, 252, 2),
            "reliability": (12, 720, 10),
        }
        self.assertEqual(set(PROFILES), set(expected))
        with patch("hiergoal.study.OpenAIResponder", side_effect=AssertionError("No live transport")) as live:
            for profile, (tasks_expected, trials_expected, repeats_expected) in expected.items():
                with self.subTest(profile=profile):
                    manifest = build_manifest(profile, backend="oracle", model="OFFLINE_ORACLE")
                    validate_manifest(manifest)
                    self.assertEqual(len(manifest["tasks"]), tasks_expected)
                    self.assertEqual(len(manifest["trials"]), trials_expected)
                    self.assertEqual(len({task["task_id"] for task in manifest["tasks"]}), tasks_expected)
                    self.assertEqual(len({trial["trial_id"] for trial in manifest["trials"]}), trials_expected)
                    identities = {(task["family"], task["split"], task["instance"])
                                  for task in manifest["tasks"]}
                    self.assertEqual(len(identities), tasks_expected)
                    self.assertEqual({task["family"] for task in manifest["tasks"]}, set(FAMILIES))
                    tasks = {task["task_id"]: task for task in manifest["tasks"]}
                    blocks, repetitions = defaultdict(list), defaultdict(set)
                    for trial in manifest["trials"]:
                        self.assertIn(trial["task_id"], tasks)
                        self.assertTrue(all(trial[key] == value for key, value in tasks[trial["task_id"]].items()))
                        blocks[trial["block_id"]].append(trial)
                        repetitions[(trial["task_id"], trial["condition"], trial["arm"])].add(trial["repeat"])
                    self.assertEqual(len(blocks), trials_expected // len(ARMS))
                    self.assertTrue(all(Counter(row["arm"] for row in members) == Counter(ARMS)
                                        for members in blocks.values()))
                    self.assertEqual(len(repetitions), tasks_expected * len(CONDITIONS) * len(ARMS))
                    self.assertTrue(all(repeats == set(range(1, repeats_expected + 1))
                                        for repeats in repetitions.values()))
                    for entry in manifest["tasks"]:
                        task = make_trial_task(entry, manifest["task_seed"])
                        self.assertEqual(task.task_id, entry["task_id"])
                        self.assertEqual(digest(task.root_contract), entry["root_sha256"])
                        self.assertEqual(digest(task.public_spec()), entry["initial_public_spec_sha256"])
                        self.assertEqual(entry["fault_kind"], "forced_subgoal" if profile in ("mechanism", "scale")
                                         else "environment")
                        if "planned_tree" in entry:
                            self.assertEqual(entry["planned_tree"], task.topology_stats())
            live.assert_not_called()

    def test_forced_domain_faults_replay_with_nonempty_locality_controls_in_all_families(self):
        manifest = build_manifest("mechanism", backend="oracle", model="OFFLINE_ORACLE")
        audited_results = []
        with tempfile.TemporaryDirectory() as temporary, \
             patch("hiergoal.study.OpenAIResponder", side_effect=AssertionError("No live transport")) as live:
            directory = Path(temporary)
            for family in FAMILIES:
                trial = next(row for row in manifest["trials"]
                             if row["family"] == family and row["arm"] == "hierarchy_adaptive"
                             and row["condition"] == "fault" and row["repeat"] == 1
                             and row["source_instance"] == 0)
                with self.subTest(family=family):
                    task, root, result, audited, events = recorded_trial(directory, manifest, trial)
                    self.assertEqual(result["status"], "PASS", result)
                    self.assertEqual(audited["audit"], "PASS", audited)
                    self.assertEqual(audited["status"], "PASS", audited)
                    self.assertTrue(result["fault_delivered"])
                    self.assertTrue(result["recovered"])
                    self.assertTrue(result["invariant_ok"])
                    self.assertTrue(result["simulated"])
                    self.assertGreater(result["calls"], 0)
                    self.assertEqual(result["actual_calls"], 0)
                    self.assertEqual(audited["actual_calls"], 0)
                    self.assertEqual(result["actual_input_tokens"], 0)
                    self.assertEqual(result["actual_output_tokens"], 0)
                    self.assertEqual(root, task.root_contract)
                    self.assertTrue(all(event["root_sha256"] == digest(root) for event in events))

                    faults = [event for event in events if event["type"] == "fault"]
                    self.assertEqual(len(faults), 1)
                    fault = faults[0]
                    target = fault["fault"]["target_gate"]
                    self.assertEqual(fault["fault_kind"], "forced_subgoal")
                    self.assertIn(target, root["domain_gates"])
                    self.assertNotIn(target, root["certification_gates"])
                    self.assertTrue(fault["before_grades"][target]["passed"])
                    self.assertFalse(fault["after_grades"][target]["passed"])
                    self.assertFalse(fault["fault"]["raw_domain_after_grade"][target]["passed"])
                    self.assertEqual(fault["before_spec"], fault["after_spec"])
                    self.assertNotEqual(fault["before_solution"], fault["after_solution"])
                    self.assertTrue(fault["fault"]["unrelated_component_gates"])
                    self.assertTrue(all(fault["after_grades"][gate]["passed"]
                                        for gate in fault["fault"]["unrelated_component_gates"]))

                    evidence = audited["mechanism_evidence"]
                    self.assertTrue(evidence["trace_replayed"])
                    self.assertTrue(evidence["root_preserved"])
                    self.assertEqual(evidence["root_changes"]["actual_changes"], 0)
                    self.assertTrue(evidence["fault"]["forced"])
                    self.assertTrue(evidence["fault"]["domain_delivered"])
                    self.assertTrue(evidence["final_grade_called"])
                    self.assertTrue(evidence["final_grade_passed"])
                    self.assertGreater(evidence["trace"]["post_fault_target_replans"], 0)
                    replanning = evidence["replanning"]
                    self.assertGreater(replanning["accepted"], 0)
                    self.assertEqual(replanning["unnecessary"], 0)
                    self.assertEqual(replanning["parent_preserved_events"], replanning["accepted"])
                    self.assertGreater(replanning["unrelated_goals_checked"], 0)
                    self.assertEqual(replanning["unrelated_goals_checked"], replanning["unrelated_goals_unchanged"])
                    locality = evidence["execution_locality"]
                    self.assertGreater(locality["nonvacuous_events"], 0)
                    self.assertGreater(locality["unrelated_artifact_fields_checked"], 0)
                    self.assertEqual(locality["unrelated_artifact_fields_checked"], locality["unrelated_artifact_fields_unchanged"])
                    self.assertEqual(locality["violations"], 0)
                    dependency = evidence["dependencies"]
                    self.assertGreater(dependency["invalidation_events"], 0)
                    self.assertGreater(dependency["invalidated_goals"], 0)
                    self.assertEqual(dependency["invalidated_goals"], dependency["reverified_goals"])
                    self.assertGreater(evidence["trace"]["root_state_transitions"], 0)
                    self.assertGreater(evidence["trace"]["milestone_state_transitions"], 0)
                    audited_results.append(audited)
            live.assert_not_called()

        # Successful oracle traces remain software evidence, even with genuine
        # domain corruption and nonvacuous recovery controls.
        summary = analyze(manifest, audited_results)
        self.assertEqual(summary["validation"]["status"], "PASS")
        self.assertEqual(summary["overall"]["observed_success_rate"], 1.0)
        self.assertEqual(summary["evidence_kind"], "simulated_software_validation")
        self.assertEqual(summary["decision"], "UNCERTAIN")
        self.assertFalse(summary["confirmatory_eligible"])
        self.assertIn("simulated_backend_not_empirical_model_evidence", summary["eligibility_blockers"])
        self.assertTrue(all(item["empirical_status"] == "UNCERTAIN"
                            for item in summary["requirement_evidence"]["criteria"]))
        self.assertTrue(all(item["ci"] is None and item["test"] is None
                            for item in summary["descriptive_contrasts"]))
        rendered = render_markdown(summary)
        self.assertIn("Software-validation results only", rendered)
        self.assertIn("do not measure empirical model success", rendered)

    def test_largest_scale_trace_has_measured_tree_counts_and_recoverable_dependencies(self):
        manifest = build_manifest("scale", backend="oracle", model="OFFLINE_ORACLE")
        trial = next(row for row in manifest["trials"]
                     if row["family"] == "data_transform" and row["arm"] == "hierarchy_adaptive"
                     and row["condition"] == "fault" and row["repeat"] == 1
                     and row["scale"] == {"size": "large", "depth": 5, "density": "dense"})
        with tempfile.TemporaryDirectory() as temporary, \
             patch("hiergoal.study.OpenAIResponder", side_effect=AssertionError("No live transport")) as live:
            task, _, result, audited, events = recorded_trial(Path(temporary), manifest, trial)
            self.assertEqual(result["status"], "PASS", result)
            self.assertEqual(audited["audit"], "PASS", audited)
            self.assertEqual(audited["actual_calls"], 0)
            plan = next(event["plan"] for event in events if event["type"] == "shared_plan")
            self.assertEqual(len(plan["leaves"]), 48)
            self.assertEqual(len(plan["milestones"]), 24)
            self.assertEqual(sum(len(leaf["depends_on"]) for leaf in plan["leaves"].values()), 120)
            measured = audited["mechanism_evidence"]["tree"]
            self.assertEqual(measured["goal_count"], 1 + len(plan["milestones"]) + len(plan["leaves"]))
            self.assertEqual(measured["goal_count"], 73)
            self.assertEqual(measured["leaf_count"], 48)
            self.assertEqual(measured["max_depth_edges"], 4)
            self.assertEqual(measured["dependency_edges"], 120)
            self.assertAlmostEqual(measured["dependency_density"], 2 * 120 / (48 * 47))
            self.assertEqual(measured["max_depth_edges"], task.topology_stats()["max_depth"])
            self.assertGreater(audited["mechanism_evidence"]["dependencies"]["reverified_goals"], 0)
            self.assertGreater(audited["mechanism_evidence"]["execution_locality"]["unrelated_artifact_fields_checked"], 0)
            live.assert_not_called()

    def test_authoritative_plan_validator_rejects_unrelated_cross_branch_edges(self):
        manifest = build_manifest("mechanism", backend="oracle", model="OFFLINE_ORACLE")
        task = make_trial_task(manifest["tasks"][0], manifest["task_seed"])
        document = {"instructions": {gate: "Verify the current requirement: " + description
                                     for gate, description in task.gates.items()}}
        plan = validate_plan(document, task)
        owners = {leaf["checks"][0]: leaf["id"] for leaf in plan["leaves"].values()}
        first_gate = next(gate for gate in task.gates if gate.startswith("c01_"))
        unrelated_gate = next(gate for gate in task.gates if gate.startswith("c02_"))
        changed = copy.deepcopy(plan)
        changed["leaves"][owners[unrelated_gate]]["depends_on"].append(owners[first_gate])
        # This is acyclic but changes independence, so cycle checks alone would
        # incorrectly allow the model to erase the unrelated negative control.
        with self.assertRaisesRegex(InvalidAction, "authoritative dependency"):
            _validate_structure(changed, task)
        self.assertEqual(plan, validate_plan(document, task))
        with self.assertRaises(InvalidAction):
            validate_plan({**document, "dependencies": {unrelated_gate: [first_gate]}}, task)


if __name__ == "__main__":
    unittest.main()
