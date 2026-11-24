# SPDX-License-Identifier: Apache-2.0
"""Offline substantive, topology, and negative-control checks for scale tasks."""
import copy
import itertools
import json
import unittest
from unittest.mock import patch

from hiergoal.study_scale import (
    DEPTH_LEVELS, DENSITIES, SCALE_LEVELS, SCALE_SETTINGS, make_task, topology_stats,
)
from hiergoal.study_tasks import FAMILIES


def all_pass(grades):
    return bool(grades) and all(value["passed"] for value in grades.values())


def independent_descendants(dependencies, target):
    """Follow outgoing edges independently of the production closure routine."""
    outgoing = {gate: set() for gate in dependencies}
    for gate, parents in dependencies.items():
        for parent in parents:
            outgoing[parent].add(gate)
    found, frontier = set(), [target]
    while frontier:
        gate = frontier.pop()
        if gate not in found:
            found.add(gate)
            frontier.extend(outgoing[gate])
    return found


def alternative_solution(task):
    """Build noncanonical valid code and schedules without the task oracle logic."""
    solution = task.reference_solution()
    if task.family == "code_repair":
        for cid in task.public_spec()["environment"]["components"]:
            solution[f"{cid}_base"] = "(x-floor)*multiplier+y if x>floor else y"
            solution[f"{cid}_adjusted"] = "0 if base+rate*z<0 else (cap if base+rate*z>cap else base+rate*z)"
            solution[f"{cid}_total"] = "adjusted-bonus if z<0 else adjusted+bonus"
    elif task.family == "scheduling":
        for cid, environment in task.public_spec()["environment"]["components"].items():
            cursor, finish, entries = 8, {}, []
            for job in environment["jobs"]:
                start = max([cursor, job["release"], *[
                    finish[edge["before"]] + edge["lag"]
                    for edge in environment["precedence"] if edge["after"] == job["task_id"]
                ]])
                resource = job["resources"][-1]
                while any(resource == block["resource"] and start < block["end"]
                          and block["start"] < start + job["duration"]
                          for block in environment["unavailable"]):
                    start += 1
                entries.append({"task_id": job["task_id"], "resource": resource, "start": start})
                cursor = finish[job["task_id"]] = start + job["duration"]
            solution[f"{cid}_assignments"] = list(reversed(entries))
    return solution


class ScaleContracts(unittest.TestCase):
    def test_all_factor_combinations_have_executable_recoverable_substantive_gates(self):
        # 3 domains x 3 sizes x 3 depths x 2 densities x 2 disjoint splits.
        identities = set()
        for family, size, depth, density, split in itertools.product(
            FAMILIES, SCALE_LEVELS, DEPTH_LEVELS, DENSITIES, ("dev", "heldout")
        ):
            with self.subTest(family=family, size=size, depth=depth, density=density, split=split):
                task = make_task(family, 0, split, scale=size, depth=depth, density=density)
                self.assertNotIn(task.task_id, identities)
                identities.add(task.task_id)
                self.assertFalse(all_pass(task.grade(task.initial_solution())))
                solution, root, specification = task.reference_solution(), task.root_contract, task.public_spec()
                self.assertTrue(all_pass(task.grade(solution)))
                self.assertTrue(all_pass(task.grade(solution, hidden=True)))
                broken, receipt = task.inject_subgoal_fault(solution)
                affected = independent_descendants(task.dependencies, receipt["target_gate"])
                unrelated = set(task.gates) - affected
                self.assertTrue(affected)
                self.assertTrue(unrelated)
                self.assertEqual(set(receipt["affected_gates"]), affected)
                self.assertEqual(set(receipt["unaffected_gates"]), unrelated)
                self.assertEqual(set(g for g, item in task.grade(broken).items() if not item["passed"]), affected)
                self.assertTrue(receipt["delivered"])
                self.assertTrue(receipt["domain_fault_delivered"])
                self.assertEqual(receipt["kind"], "forced_subgoal")
                self.assertEqual(receipt["environment_before"], receipt["environment_after"])
                self.assertEqual(root, task.root_contract)
                self.assertEqual(specification, task.public_spec())
                self.assertEqual(solution, task.reference_solution())
                self.assertTrue(receipt["unaffected_artifacts_unchanged"])
                self.assertEqual(task.artifact_projection(solution, sorted(unrelated)),
                                 task.artifact_projection(broken, sorted(unrelated)))
                self.assertTrue(all(task.grade(broken)[gate]["passed"] for gate in unrelated))
                # Repair only the corrupted domain field; no certificate shortcut.
                for field in receipt["changed_fields"]:
                    broken[field] = copy.deepcopy(solution[field])
                self.assertTrue(all_pass(task.grade(broken, hidden=True)))
                returned, update = task.inject_fault(solution)
                self.assertEqual(returned, solution)
                self.assertIsNot(returned, solution)
                self.assertTrue(update["domain_fault_delivered"])
                self.assertTrue(update["delivered"])
                self.assertFalse(task.grade(returned)[update["target_gate"]]["passed"])
                before, after = update["environment_before"], update["environment_after"]
                cid = update["target_component"]
                self.assertNotEqual(before["components"][cid], after["components"][cid])
                self.assertEqual([component for component in before["components"]
                                  if before["components"][component] != after["components"][component]], [cid])
                self.assertEqual(after["component_revisions"][cid], 1)
                self.assertEqual(root, task.root_contract)
                repaired = task.reference_solution()
                unrelated = update["unrelated_component_gates"]
                self.assertTrue(unrelated)
                self.assertEqual(task.artifact_projection(solution, unrelated),
                                 task.artifact_projection(repaired, unrelated))
                self.assertTrue(all(task.grade(returned)[gate]["passed"] for gate in unrelated))
                self.assertTrue(all_pass(task.grade(repaired)))
                self.assertTrue(all_pass(task.grade(repaired, hidden=True)))
        self.assertEqual(len(identities), 108)

    def test_reproducibility_and_shared_component_prefixes_across_scale_factors(self):
        for family in FAMILIES:
            first = make_task(family, 3, scale="small", depth=3, density="sparse")
            same = make_task(family, 3, scale="small", depth=3, density="sparse")
            larger = make_task(family, 3, scale="large", depth=5, density="dense")
            self.assertEqual(first.public_spec(), same.public_spec())
            self.assertEqual(first.reference_solution(), same.reference_solution())
            self.assertNotEqual(first.task_id, larger.task_id)
            for cid, contract in first.root_contract["component_contracts"].items():
                self.assertEqual(contract, larger.root_contract["component_contracts"][cid])
                self.assertEqual(first.public_spec()["environment"]["components"][cid],
                                 larger.public_spec()["environment"]["components"][cid])
            self.assertNotEqual(first.public_spec(), make_task(family, 3, seed=42).public_spec())

    def test_public_mutation_cannot_change_contract_environment_or_grader(self):
        task = make_task("data_transform", 2, depth=5)
        contract, spec, hierarchy, ownership = task.root_contract, task.public_spec(), task.hierarchy_spec, task.gate_artifact_fields
        task.root_contract["component_contracts"].clear()
        task.public_spec()["environment"]["components"].clear()
        task.gates.clear()
        task.dependencies.clear()
        task.hierarchy_spec["groups"].clear()
        task.gate_artifact_fields.clear()
        task.gate_artifact_paths.clear()
        task.scale_config.clear()
        self.assertEqual(contract, task.root_contract)
        self.assertEqual(spec, task.public_spec())
        self.assertEqual(hierarchy, task.hierarchy_spec)
        self.assertEqual(ownership, task.gate_artifact_fields)
        self.assertTrue(all_pass(task.grade(task.reference_solution(), hidden=True)))
        broken, receipt = task.inject_subgoal_fault(task.reference_solution())
        current = task.public_spec()
        receipt["environment_before"].clear()
        receipt["environment_after"].clear()
        broken.clear()
        self.assertEqual(current, task.public_spec())

    def test_malformed_artifacts_are_rejected_without_mutation_or_exceptions(self):
        for family in FAMILIES:
            task = make_task(family, 0)
            values = [None, True, 0, "bad", [], {}, {"gates": []}, task.initial_solution()]
            for candidate in values:
                original = copy.deepcopy(candidate)
                for hidden in (False, True):
                    grades = task.grade(candidate, hidden=hidden)
                    self.assertFalse(all_pass(grades))
                    self.assertEqual(set(grades), set(task.gates))
                    self.assertTrue(all(type(value["passed"]) is bool and type(value["message"]) is str
                                        for value in grades.values()))
                self.assertEqual(original, candidate)
            bad = task.reference_solution()
            first = next(iter(bad))
            for value in (None, True, [], {}, {"passed": True}):
                candidate = copy.deepcopy(bad)
                candidate[first] = value
                self.assertFalse(all_pass(task.grade(candidate, hidden=True)))

    def test_factory_rejects_unbounded_or_wrongly_typed_parameters(self):
        invalid = [
            {"family": "unknown"}, {"instance": -1}, {"instance": True},
            {"instance": 0.0}, {"split": "test"}, {"seed": True},
            {"scale": "enormous"}, {"scale": []}, {"depth": 2},
            {"depth": 1000}, {"depth": True}, {"depth": 3.0},
            {"density": "complete_unbounded"}, {"density": None},
        ]
        for changed in invalid:
            arguments = {"family": "code_repair", "instance": 0, **changed}
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                make_task(**arguments)
        task = make_task("code_repair", 0)
        before = task.public_spec()
        for inject in (task.inject_fault, task.inject_subgoal_fault):
            with self.assertRaisesRegex(ValueError, "public all-pass"):
                inject(task.initial_solution())
            self.assertEqual(task.public_spec(), before)


class ScaleStructure(unittest.TestCase):
    def test_stats_are_recomputed_from_graph_and_tree_instead_of_scale_labels(self):
        for size, depth, density in itertools.product(SCALE_LEVELS, DEPTH_LEVELS, DENSITIES):
            task = make_task("data_transform", 1, scale=size, depth=depth, density=density)
            groups = task.hierarchy_spec["groups"]
            gate_parents = task.hierarchy_spec["gate_parents"]
            # Breadth-first depth computation independent from production recursion.
            distances, frontier = {"G0": 0}, ["G0"]
            while frontier:
                parent = frontier.pop(0)
                for group in groups:
                    if group["parent"] == parent:
                        distances[group["id"]] = distances[parent] + 1
                        frontier.append(group["id"])
            actual_depth = max(distances[parent] + 1 for parent in gate_parents.values())
            actual_edges = {(parent, gate) for gate, parents in task.dependencies.items() for parent in parents}
            stats = task.topology_stats()
            self.assertEqual(stats["leaf_count"], len(task.gates))
            self.assertEqual(stats["goal_count"], 1 + len(groups) + len(task.gates))
            self.assertEqual(stats["max_depth"], actual_depth)
            self.assertEqual(stats["max_depth"], depth - 1)
            self.assertEqual(stats["dependency_edges"], len(actual_edges))
            count = len(task.gates)
            self.assertEqual(stats["dependency_density"], len(actual_edges) / (count * (count - 1) / 2))
            self.assertEqual(stats["component_count"], SCALE_LEVELS[size])
            self.assertEqual(stats["independent_branch_count"], SCALE_LEVELS[size])
            self.assertEqual(stats["domain_gate_count"], 3 * SCALE_LEVELS[size])
            self.assertEqual(stats["certification_gate_count"], (depth - 2) * SCALE_LEVELS[size])
            self.assertEqual(stats["leaf_count"], (depth + 1) * SCALE_LEVELS[size])
            self.assertEqual(stats, task.root_contract["topology"])
            for parent, gate in actual_edges:
                self.assertEqual(parent.split("_")[0], gate.split("_")[0])
            # Every group has its own executable certification leaf.
            certificate_parents = [gate_parents[gate] for gate in task.root_contract["certification_gates"]]
            self.assertCountEqual(certificate_parents, [group["id"] for group in groups])

    def test_depth_size_and_direct_edge_density_vary_with_declared_design(self):
        self.assertEqual(len(SCALE_SETTINGS), 7)
        leaves = [make_task("code_repair", 0, scale=size).topology_stats()["leaf_count"]
                  for size in SCALE_LEVELS]
        self.assertEqual(leaves, [8, 16, 32])
        depths = [make_task("code_repair", 0, depth=depth).topology_stats()["max_depth"]
                  for depth in DEPTH_LEVELS]
        self.assertEqual(depths, [2, 3, 4])
        sparse = make_task("code_repair", 0, density="sparse")
        dense = make_task("code_repair", 0, density="dense")
        self.assertEqual(set(sparse.gates), set(dense.gates))
        self.assertGreater(dense.topology_stats()["dependency_edges"], sparse.topology_stats()["dependency_edges"])
        self.assertGreater(dense.topology_stats()["dependency_density"], sparse.topology_stats()["dependency_density"])
        # The disclosure matters: added direct edges need not add reachability.
        for gate in sparse.gates:
            self.assertEqual(independent_descendants(sparse.dependencies, gate),
                             independent_descendants(dense.dependencies, gate))
        self.assertNotEqual(sparse.reference_solution()["c01_certify_1"],
                            dense.reference_solution()["c01_certify_1"])

    def test_malformed_hierarchies_and_dependencies_are_not_counted_as_valid(self):
        task = make_task("data_transform", 0, depth=4)
        for change in ("cycle", "missing_parent", "duplicate_group", "missing_gate", "false_depth", "empty_group"):
            hierarchy = task.hierarchy_spec
            if change == "cycle":
                hierarchy["groups"][0]["parent"] = hierarchy["groups"][1]["id"]
            elif change == "missing_parent":
                hierarchy["groups"][0]["parent"] = "UNKNOWN"
            elif change == "duplicate_group":
                hierarchy["groups"].append(hierarchy["groups"][0])
            elif change == "missing_gate":
                hierarchy["gate_parents"].pop(next(iter(task.gates)))
            elif change == "false_depth":
                hierarchy["depth_levels"] += 1
            else:
                hierarchy["groups"].append({"id": "EMPTY", "parent": "G0", "title": "Empty group"})
            with self.subTest(change=change), self.assertRaises(ValueError):
                topology_stats(hierarchy, task.dependencies)
        for prerequisites in (["unknown"], ["c01_rows"], ["c01_aggregates"], [True], [None]):
            dependencies = task.dependencies
            dependencies["c01_rows"] = prerequisites
            with self.subTest(prerequisites=prerequisites), self.assertRaises(ValueError):
                topology_stats(task.hierarchy_spec, dependencies)


class ScaleAcceptanceAndFaults(unittest.TestCase):
    def test_certificates_cannot_replace_domain_work_or_forge_dependencies(self):
        for family in FAMILIES:
            task = make_task(family, 4, depth=5, density="dense")
            initial, reference = task.initial_solution(), task.reference_solution()
            for gate in task.root_contract["certification_gates"]:
                initial[gate] = copy.deepcopy(reference[gate])
            grades = task.grade(initial)
            self.assertFalse(all_pass(grades))
            self.assertFalse(any(grades[gate]["passed"] for gate in task.root_contract["certification_gates"]))
            gate = task.root_contract["certification_gates"][0]
            for value in (
                True, {"passed": True},
                {"environment_revision": False, "checked_gates": reference[gate]["checked_gates"]},
                {"environment_revision": 0, "checked_gates": []},
                {"environment_revision": 0, "checked_gates": ["unknown"]},
                {**reference[gate], "success": True},
            ):
                candidate = copy.deepcopy(reference)
                candidate[gate] = value
                self.assertFalse(task.grade(candidate)[gate]["passed"])

    def test_alternate_code_and_schedules_are_accepted_and_domain_no_impact_is_retained(self):
        for family in ("code_repair", "scheduling"):
            for instance in range(4):
                task = make_task(family, instance, depth=5, density="dense")
                canonical = task.reference_solution()
                alternate = alternative_solution(task)
                self.assertNotEqual(canonical, alternate)
                self.assertTrue(all_pass(task.grade(alternate, hidden=True)))
                before = copy.deepcopy(alternate)
                returned, receipt = task.inject_fault(alternate)
                self.assertEqual(returned, before)
                self.assertEqual(alternate, before)
                self.assertFalse(receipt["domain_fault_delivered"])
                self.assertFalse(receipt["delivered"])
                self.assertEqual(receipt["status"], "perturbation_no_impact")
                self.assertTrue(receipt["certification_invalidated"])
                self.assertTrue(all(value["passed"] for value in receipt["raw_domain_after_grade"].values()))
                current = task.reference_solution()
                for gate in task.root_contract["certification_gates"]:
                    returned[gate] = copy.deepcopy(current[gate])
                self.assertTrue(all_pass(task.grade(returned, hidden=True)))

    def test_paired_fault_environments_do_not_depend_on_submitted_artifacts(self):
        for family in FAMILIES:
            left, right = make_task(family, 7), make_task(family, 7)
            _, first = left.inject_fault(left.reference_solution())
            _, second = right.inject_fault(alternative_solution(right))
            for field in ("environment_before", "environment_after", "target_gate", "changed_fields"):
                self.assertEqual(first[field], second[field])
            forced_left, forced_right = make_task(family, 7), make_task(family, 7)
            a, first = forced_left.inject_subgoal_fault(forced_left.reference_solution())
            b, second = forced_right.inject_subgoal_fault(alternative_solution(forced_right))
            self.assertEqual(first["target_gate"], second["target_gate"])
            self.assertTrue(first["delivered"])
            self.assertTrue(second["delivered"])
            self.assertFalse(all_pass(forced_left.grade(a)))
            self.assertFalse(all_pass(forced_right.grade(b)))

    def test_forced_schedule_fault_targets_same_job_after_equivalent_array_reordering(self):
        left, right = make_task("scheduling", 0), make_task("scheduling", 0)
        original = left.reference_solution()
        reordered = copy.deepcopy(original)
        for field, entries in reordered.items():
            if field.endswith("_assignments"):
                entries.reverse()
        self.assertNotEqual(original, reordered)
        self.assertTrue(all_pass(left.grade(original, hidden=True)))
        self.assertTrue(all_pass(right.grade(reordered, hidden=True)))
        root, specification = left.root_contract, left.public_spec()
        damaged_left, receipt_left = left.inject_subgoal_fault(original)
        damaged_right, receipt_right = right.inject_subgoal_fault(reordered)
        self.assertEqual(receipt_left["target_gate"], receipt_right["target_gate"])
        self.assertEqual(receipt_left["target_entity"], receipt_right["target_entity"])
        self.assertEqual(receipt_left["target_field"], receipt_right["target_field"])
        cid = receipt_left["target_component"]
        artifact_field = receipt_left["target_gate"]
        expected_job = specification["environment"]["components"][cid]["jobs"][0]["task_id"]
        self.assertEqual(receipt_left["target_entity"],
                         {"component": cid, "kind": "job", "task_id": expected_job})
        self.assertEqual(receipt_left["target_field"],
                         {"artifact_field": artifact_field, "field": "start"})
        for task, before, after, receipt in (
            (left, original, damaged_left, receipt_left),
            (right, reordered, damaged_right, receipt_right),
        ):
            before_jobs = {entry["task_id"]: entry for entry in before[artifact_field]}
            after_jobs = {entry["task_id"]: entry for entry in after[artifact_field]}
            self.assertEqual({job for job in before_jobs if before_jobs[job] != after_jobs[job]},
                             {expected_job})
            self.assertEqual(after_jobs[expected_job], {**before_jobs[expected_job], "start": -1})
            self.assertTrue(receipt["domain_fault_delivered"])
            self.assertFalse(task.grade(after)[artifact_field]["passed"])
            self.assertEqual(root, task.root_contract)
            self.assertEqual(specification, task.public_spec())
            self.assertEqual(receipt["environment_before"], receipt["environment_after"])
            self.assertTrue(receipt["unaffected_artifacts_unchanged"])
            self.assertEqual(task.artifact_projection(before, receipt["unrelated_component_gates"]),
                             task.artifact_projection(after, receipt["unrelated_component_gates"]))

    def test_code_reuses_bounded_interpreter_and_private_probes_stay_private(self):
        task = make_task("code_repair", 2, depth=5)
        for source in (
            "__import__('os').system('false')", "open('/tmp/forbidden', 'w')",
            "x.__class__", "(lambda: 1)()", "[x for x in range(9)]", "x**9999",
            "x//0", "True", "1000000*1000000", "1 if x else 0",
        ):
            solution = task.reference_solution()
            solution["c01_base"] = source
            with patch("builtins.eval", side_effect=AssertionError("eval must not run")), \
                 patch("builtins.exec", side_effect=AssertionError("exec must not run")):
                self.assertFalse(task.grade(solution)["c01_base"]["passed"])
                self.assertFalse(all_pass(task.grade(solution, hidden=True)))
            self.assertTrue(task.grade(solution)["c02_base"]["passed"])
        public = json.dumps(task.public_spec())
        self.assertNotIn("private_probes", public)
        self.assertNotIn("reference_solution", public)
        for field, expression in task.reference_solution().items():
            if field in task.root_contract["domain_gates"]:
                self.assertNotIn(expression, public)
        overfit = task.reference_solution()
        overfit["c01_base"] += " + (1 if x == -50 else 0)"
        self.assertTrue(all_pass(task.grade(overfit)))
        self.assertFalse(task.grade(overfit, hidden=True)["c01_base"]["passed"])
        self.assertTrue(task.grade(overfit, hidden=True)["c02_base"]["passed"])


if __name__ == "__main__":
    unittest.main()
