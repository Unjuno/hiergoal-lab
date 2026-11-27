# SPDX-License-Identifier: Apache-2.0
"""Protocol/fork adversarial tests; reference artifacts are offline only."""
from __future__ import annotations

import copy
import json
import unittest
from collections import Counter
from unittest.mock import patch

from hiergoal import recovery_protocol as protocol
from hiergoal.recovery_checkpoint import (
    make_checkpoint, model_view, restore_checkpoint, validate_initial_plan,
)
from hiergoal.study_protocol import canonical, digest
from hiergoal.study_planning import active_leaf, validate_plan


def initial_plan(task):
    return validate_plan({"instructions": {
        gate: "Satisfy the current authoritative requirement: " + description
        for gate, description in task.gates.items()}}, task)


def checkpoint(family="code_repair", **overrides):
    spec = next(spec for spec in protocol.task_specs() if spec["family"] == family)
    task = protocol.make_task(spec)
    options = {"pair_id": spec["task_id"] + "-r1", "protocol_id": "a" * 64,
               "source_trace_sha256": "b" * 64, **overrides}
    return make_checkpoint(task, initial_plan(task), task.reference_solution(), **options)


def rehash(value):
    value["checkpoint_sha256"] = digest({key: item for key, item in value.items()
                                        if key != "checkpoint_sha256"})
    return value


class RecoveryProtocolTests(unittest.TestCase):
    def test_six_new_tasks_have_no_exact_archived_overlap(self):
        tasks = protocol.task_specs()
        self.assertEqual(len(tasks), 6)
        self.assertEqual(Counter(task["family"] for task in tasks),
                         {family: 2 for family in protocol.FAMILIES})
        self.assertEqual(len({task["root_sha256"] for task in tasks}), 6)
        evidence = protocol.task_non_overlap(tasks)
        self.assertEqual(evidence["exact_overlap_count"], 0)
        self.assertEqual(len(evidence["baseline_manifest_sha256"]), 18)
        self.assertGreater(evidence["archived_task_records"], 100)

    @patch.object(protocol, "source_hashes", return_value={"frozen.py": "f" * 64})
    def test_schedule_complete_paired_reproducible_and_balanced(self, _):
        value = protocol.build_manifest(backend="oracle")
        self.assertEqual(value, protocol.build_manifest(backend="oracle"))
        self.assertEqual(len(value["pairs"]), 12)
        self.assertEqual(len(value["trials"]), 24)
        self.assertEqual(Counter(pair["arm_order"][0] for pair in value["pairs"]),
                         {"fixed": 6, "adaptive": 6})
        self.assertEqual(Counter(trial["arm"] for trial in value["trials"]),
                         {"fixed": 12, "adaptive": 12})
        for pair in value["pairs"]:
            trials = [item for item in value["trials"] if item["pair_id"] == pair["pair_id"]]
            self.assertEqual([item["arm"] for item in trials], pair["arm_order"])
            self.assertEqual(trials[0]["task"], trials[1]["task"])
        protocol.validate_manifest(value)

    @patch.object(protocol, "source_hashes", return_value={"frozen.py": "f" * 64})
    def test_rehashed_schedule_or_budget_changes_rejected(self, _):
        for mutate in (
            lambda value: value["trials"].pop(),
            lambda value: value["limits"].update(max_calls=9),
            lambda value: value["pairs"][0].update(arm_order=["fixed", "fixed"]),
        ):
            value = protocol.build_manifest(backend="oracle")
            mutate(value)
            value["protocol_id"] = digest({key: item for key, item in value.items()
                                           if key != "protocol_id"})
            with self.assertRaisesRegex(ValueError, "complete frozen pilot"):
                protocol.validate_manifest(value)

    @patch.object(protocol, "source_hashes", return_value={"frozen.py": "f" * 64})
    def test_changed_source_or_unhashed_manifest_rejected(self, _):
        value = protocol.build_manifest(backend="oracle")
        value["backend"] = "openai"
        with self.assertRaisesRegex(ValueError, "changed after preparation"):
            protocol.validate_manifest(value)
        value = protocol.build_manifest(backend="oracle")
        with patch.object(protocol, "source_hashes", return_value={"frozen.py": "e" * 64}):
            with self.assertRaisesRegex(ValueError, "source/evaluator"):
                protocol.validate_manifest(value)

    def test_unregistered_model_backend_and_mismatched_task_rejected(self):
        with self.assertRaises(ValueError):
            protocol.build_manifest(backend="simulated_live")
        with self.assertRaises(ValueError):
            protocol.build_manifest(model="different-model")
        spec = protocol.task_specs()[0]
        spec["root_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "root_sha256"):
            protocol.make_task(spec)


class RecoveryCheckpointTests(unittest.TestCase):
    def test_all_families_roundtrip_identical_independent_forks(self):
        for family in protocol.FAMILIES:
            with self.subTest(family=family):
                saved = json.loads(canonical(checkpoint(family)))
                pair = {"pair_id": saved["pair_id"], "task": saved["task"]}
                a, plan_a, artifact_a = restore_checkpoint(saved, pair=pair, protocol_id="a" * 64)
                b, plan_b, artifact_b = restore_checkpoint(saved, pair=pair, protocol_id="a" * 64)
                self.assertIsNot(a, b)
                self.assertEqual(plan_a, plan_b)
                self.assertEqual(artifact_a, artifact_b)
                self.assertEqual(a.grade(artifact_a), saved["public_feedback"])
                self.assertEqual(a.root_contract, saved["root_contract"])
                self.assertEqual(a.public_spec(), saved["public_spec"])
                self.assertEqual(active_leaf(plan_a, a.grade(artifact_a))["id"], saved["target_leaf_id"])
                self.assertFalse(a.grade(artifact_a)[saved["fault_receipt"]["target_gate"]]["passed"])
                self.assertEqual(a._subgoal_faults, 1)
                a._subgoal_faults += 1
                self.assertEqual(b._subgoal_faults, 1)
                plan_a["milestones"][0]["title"] = "changed"
                self.assertNotEqual(plan_a, plan_b)
                artifact_a.clear()
                self.assertTrue(artifact_b)

    def test_source_task_is_not_mutated_and_model_view_hides_source(self):
        task = protocol.make_task(protocol.task_specs()[0])
        plan, solution = initial_plan(task), task.reference_solution()
        before = canonical([task.public_spec(), plan, solution])
        saved = make_checkpoint(task, plan, solution, pair_id="pair", protocol_id="a" * 64)
        self.assertEqual(before, canonical([task.public_spec(), plan, solution]))
        self.assertEqual(task._subgoal_faults, 0)
        view = model_view(saved)
        self.assertEqual(set(view), {"root_contract", "task", "plan", "artifact", "public_feedback", "history"})
        self.assertEqual(view["history"], [])
        self.assertNotEqual(view["artifact"], saved["source_solution"])
        for forbidden in ("source_solution", "source_hidden_grade", "source_public_grade", "fault_receipt"):
            self.assertNotIn(forbidden, view)

    def test_bad_source_or_previously_mutated_environment_rejected(self):
        task = protocol.make_task(protocol.task_specs()[0])
        with self.assertRaisesRegex(ValueError, "public and hidden"):
            make_checkpoint(task, initial_plan(task), task.initial_solution(), pair_id="pair", protocol_id="a" * 64)
        source = task.reference_solution()
        task.inject_subgoal_fault(source)
        with self.assertRaisesRegex(ValueError, "already received"):
            make_checkpoint(task, initial_plan(task), source, pair_id="pair", protocol_id="a" * 64)
        task = protocol.make_task(protocol.task_specs()[0])
        source = task.reference_solution()
        task.inject_fault(source)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            make_checkpoint(task, initial_plan(task), source, pair_id="pair", protocol_id="a" * 64)

    def test_hidden_source_failure_does_not_become_a_checkpoint(self):
        task = protocol.make_task(protocol.task_specs()[0])
        grade = type(task).grade
        def reject_hidden(instance, artifact, *, hidden=False):
            value = grade(instance, artifact, hidden=hidden)
            if hidden:
                value[next(iter(value))] = {"passed": False, "message": "Hidden failure"}
            return value
        with patch.object(type(task), "grade", reject_hidden):
            with self.assertRaisesRegex(ValueError, "public and hidden"):
                make_checkpoint(task, initial_plan(task), task.reference_solution(),
                                pair_id="pair", protocol_id="a" * 64)

    def test_root_feedback_fault_receipt_or_history_forgery_rejected_even_rehashed(self):
        mutations = (
            lambda value: value["root_contract"].update(objective="Altered objective"),
            lambda value: value["public_spec"]["environment"].update(components={}),
            lambda value: value["public_feedback"][value["fault_receipt"]["target_gate"]].update(passed=True),
            lambda value: value["fault_receipt"].update(target_gate="unknown_gate"),
            lambda value: value["repair_history"].append({"patch": value["source_solution"]}),
            lambda value: value["failed_solution"].update(value["source_solution"]),
        )
        for mutate in mutations:
            saved = checkpoint()
            mutate(saved)
            rehash(saved)
            with self.assertRaises(ValueError):
                restore_checkpoint(saved)

    def test_plan_topology_checks_and_revisions_are_immutable(self):
        task = protocol.make_task(protocol.task_specs()[0])
        for field, replacement in (("checks", ["unknown"]), ("revision", 1),
                                   ("parent", "G0"), ("depends_on", ["S1"])):
            plan = initial_plan(task)
            plan["leaves"]["S1"][field] = replacement
            with self.assertRaises(ValueError):
                validate_initial_plan(plan, task)

    def test_pair_protocol_checksum_and_trace_identifier_checked(self):
        saved = checkpoint()
        with self.assertRaisesRegex(ValueError, "another recovery protocol"):
            restore_checkpoint(saved, protocol_id="c" * 64)
        with self.assertRaisesRegex(ValueError, "another assigned pair"):
            restore_checkpoint(saved, pair={"pair_id": "other", "task": saved["task"]})
        pair = {"pair_id": saved["pair_id"], "task": copy.deepcopy(saved["task"])}
        pair["task"]["seed"] += 1
        with self.assertRaisesRegex(ValueError, "assigned task"):
            restore_checkpoint(saved, pair=pair)
        saved["target_leaf_id"] = "S999"
        with self.assertRaisesRegex(ValueError, "fingerprint changed"):
            restore_checkpoint(saved)
        with self.assertRaisesRegex(ValueError, "source_trace_sha256"):
            checkpoint(source_trace_sha256="not-a-hash")

    def test_non_delivering_fault_rejected(self):
        task = protocol.make_task(protocol.task_specs()[0])
        def no_fault(_, solution):
            return copy.deepcopy(solution), {"domain_fault_delivered": False}
        with patch.object(type(task), "inject_subgoal_fault", no_fault):
            with self.assertRaisesRegex(ValueError, "registered local failure"):
                make_checkpoint(task, initial_plan(task), task.reference_solution(),
                                pair_id="pair", protocol_id="a" * 64)


if __name__ == "__main__":
    unittest.main()
