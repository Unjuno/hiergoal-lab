# SPDX-License-Identifier: Apache-2.0
"""Offline task/oracle tests: no model calls, network, or submitted-code execution."""
import copy
import json
import unittest
from unittest.mock import patch

from hiergoal.study_tasks import FAMILIES, Task, make_task


def all_pass(verdict):
    return bool(verdict) and all(item["passed"] for item in verdict.values())


def delayed_schedule(task):
    """An independent, deliberately noncanonical serial scheduler for tests."""
    environment = task.public_spec()["environment"]
    cursor, finish, assignments = 8, {}, []
    for job in environment["jobs"]:
        earliest = [cursor, job["release"]]
        earliest.extend(finish[edge["before"]] + edge["lag"]
                        for edge in environment["precedence"] if edge["after"] == job["task_id"])
        start, resource = max(earliest), job["resources"][-1]
        while any(resource == block["resource"] and start < block["end"]
                  and block["start"] < start + job["duration"] for block in environment["unavailable"]):
            start += 1
        assignments.append({"task_id": job["task_id"], "resource": resource, "start": start})
        cursor = finish[job["task_id"]] = start + job["duration"]
    return {"assignments": list(reversed(assignments))}


class StudyTaskContracts(unittest.TestCase):
    def test_six_instances_per_split_have_distinct_reproducible_definitions(self):
        ids, definitions = set(), set()
        for family in FAMILIES:
            for split in ("dev", "heldout"):
                for instance in range(6):
                    with self.subTest(family=family, split=split, instance=instance):
                        first = make_task(family, instance, split)
                        second = make_task(family, instance, split)
                        self.assertEqual(first.public_spec(), second.public_spec())
                        self.assertEqual(first.reference_solution(), second.reference_solution())
                        self.assertNotIn(first.task_id, ids)
                        ids.add(first.task_id)
                        definition = json.dumps(first.public_spec(), sort_keys=True)
                        self.assertNotIn(definition, definitions)
                        definitions.add(definition)
                        self.assertEqual(first.root_contract["seed"], 1729)
                        self.assertEqual(first.family, family)
                        self.assertEqual(first.split, split)
                        self.assertEqual(set(first.gates), set(first.dependencies))
                        self.assertEqual(len(first.gates), 3)
        self.assertEqual(len(ids), 36)
        self.assertNotEqual(make_task("code_repair", 0, seed=1).public_spec(),
                            make_task("code_repair", 0, seed=2).public_spec())

    def test_initial_fails_reference_passes_both_checkers_and_update_is_recoverable(self):
        for family in FAMILIES:
            for split in ("dev", "heldout"):
                for instance in range(6):
                    with self.subTest(family=family, split=split, instance=instance):
                        task = make_task(family, instance, split)
                        self.assertFalse(all_pass(task.grade(task.initial_solution())))
                        solution, root = task.reference_solution(), task.root_contract
                        original = copy.deepcopy(solution)
                        self.assertTrue(all_pass(task.grade(solution)))
                        self.assertTrue(all_pass(task.grade(solution, hidden=True)))
                        returned, info = task.inject_fault(solution)
                        self.assertEqual(solution, original)
                        self.assertEqual(returned, original)
                        self.assertIsNot(returned, solution)
                        self.assertEqual(root, task.root_contract)
                        self.assertTrue(info["delivered"])
                        self.assertEqual(info["status"], "delivered")
                        self.assertFalse(task.grade(returned)[info["target_gate"]]["passed"])
                        self.assertNotEqual(info["environment_before"], info["environment_after"])
                        self.assertEqual(info["environment_after"], task.public_spec()["environment"])
                        self.assertEqual(task.public_spec()["environment_revision"], 1)
                        self.assertTrue(info["changed_fields"])
                        recovered = task.reference_solution()
                        self.assertTrue(all_pass(task.grade(recovered)))
                        self.assertTrue(all_pass(task.grade(recovered, hidden=True)))
                        self.assertNotEqual(recovered, original)
                        # Updates persist; grading the old artifact again cannot undo the event.
                        self.assertFalse(all_pass(task.grade(original)))

    def test_public_objects_and_fault_receipts_cannot_mutate_task_truth(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                task = make_task(family, 0)
                root, spec = task.root_contract, task.public_spec()
                changed_root = task.root_contract
                changed_root["gates"].clear()
                changed_root["dependencies"].clear()
                changed_spec = task.public_spec()
                changed_spec["environment"].clear()
                changed_spec["solution_shape"].clear()
                task.gates.clear()
                task.dependencies.clear()
                self.assertEqual(root, task.root_contract)
                self.assertEqual(spec, task.public_spec())
                original = task.reference_solution()
                returned, info = task.inject_fault(original)
                current = task.public_spec()
                info["environment_after"].clear()
                info["environment_before"].clear()
                if family == "code_repair":
                    returned["expressions"]["base"] = "999"
                elif family == "data_transform":
                    returned["rows"][0]["client"] = "CHANGED"
                else:
                    returned["assignments"][0]["start"] = -999
                self.assertNotEqual(returned, original)
                self.assertEqual(current, task.public_spec())
                self.assertEqual(root, task.root_contract)

    def test_only_public_all_pass_artifacts_can_trigger_an_update(self):
        for family in FAMILIES:
            task = make_task(family, 0)
            before = task.public_spec()
            with self.assertRaisesRegex(ValueError, "public all-pass"):
                task.inject_fault(task.initial_solution())
            self.assertEqual(before, task.public_spec())

    def test_paired_task_updates_do_not_depend_on_the_artifact(self):
        for family in FAMILIES:
            for instance in range(6):
                left = make_task(family, instance)
                right = make_task(family, instance)
                alternate = right.reference_solution()
                if family == "code_repair":
                    alternate = {"expressions": {
                        "base": "max(0, x - floor) * multiplier + y",
                        "adjusted": "min(cap, max(0, base + rate * z))",
                        "total": "adjusted + (bonus if z >= 0 else -bonus)",
                    }}
                elif family == "scheduling":
                    alternate = delayed_schedule(right)
                self.assertTrue(all_pass(right.grade(alternate, hidden=True)))
                _, left_info = left.inject_fault(left.reference_solution())
                _, right_info = right.inject_fault(alternate)
                self.assertEqual(left_info["environment_before"], right_info["environment_before"])
                self.assertEqual(left_info["environment_after"], right_info["environment_after"])
                self.assertEqual(left_info["changed_fields"], right_info["changed_fields"])
                if family != "data_transform":
                    self.assertFalse(right_info["delivered"])
                    self.assertEqual(right_info["status"], "perturbation_no_impact")
                    self.assertTrue(all_pass(right.grade(alternate, hidden=True)))

    def test_malformed_solutions_are_rejected_without_exceptions(self):
        malformed = [None, True, 17, "text", [], {}, {"unexpected": 1},
                     {"expressions": None}, {"expressions": {"base": "0"}},
                     {"rows": None, "aggregates": [], "report": ""},
                     {"rows": [], "aggregates": [None], "report": []},
                     {"assignments": [None]}, {"assignments": "not a list"}]
        for family in FAMILIES:
            task = make_task(family, 0)
            for candidate in malformed:
                with self.subTest(family=family, candidate=candidate):
                    before = copy.deepcopy(candidate)
                    for hidden in (False, True):
                        results = task.grade(candidate, hidden=hidden)
                        self.assertEqual(set(results), set(task.gates))
                        self.assertFalse(all_pass(results))
                        for result in results.values():
                            self.assertIs(type(result["passed"]), bool)
                            self.assertIs(type(result["message"]), str)
                    self.assertEqual(before, candidate)

    def test_factory_rejects_invalid_identifiers_and_types(self):
        for args in [("unknown", 0), ("code_repair", -1), ("code_repair", True),
                     ("code_repair", 1.0), ("code_repair", 0, "test")]:
            with self.assertRaises(ValueError):
                make_task(*args)
        with self.assertRaises(ValueError):
            make_task("code_repair", 0, seed=True)


class BoundedCodeRepair(unittest.TestCase):
    def test_unsafe_and_out_of_language_expressions_never_execute(self):
        task = make_task("code_repair", 0)
        rejected = [
            "__import__('os').system('false')", "open('/tmp/forbidden', 'w')", "x.__class__",
            "(lambda: 1)()", "[x for x in range(10)]", "[1][0]", "{'a': 1}",
            "x ** 100000", "x / 2", "2.0", "True", "'text'", "(a := 1)",
            "globals()", "getattr(x, '__class__')", "abs(x, y)", "min(x)", "max(x, y=y)",
            "sum(x, y)", "1000001", "1000000 * 1000000", "x // 0", "1 if x else 0",
            "not x", "x + (y > 0)", "-" * 100 + "1", "1 + " * 200 + "1",
        ]
        # AST parsing itself uses Python's parser; submitted syntax never goes to exec/eval.
        with patch("builtins.eval", side_effect=AssertionError("eval must never run")), \
             patch("builtins.exec", side_effect=AssertionError("exec must never run")):
            for expression in rejected:
                with self.subTest(expression=expression):
                    solution = task.reference_solution()
                    solution["expressions"]["base"] = expression
                    self.assertFalse(task.grade(solution)["base"]["passed"])
                    self.assertFalse(all_pass(task.grade(solution, hidden=True)))

    def test_alternative_expressions_and_boolean_control_flow_are_accepted(self):
        task = make_task("code_repair", 4)
        solution = {"expressions": {
            "base": "(x - floor) * multiplier + y if x > floor and not (x == floor) else y",
            "adjusted": "0 if base + rate * z < 0 else (cap if base + rate * z > cap else base + rate * z)",
            "total": "adjusted - bonus if z < 0 else adjusted + bonus",
        }}
        self.assertTrue(all_pass(task.grade(solution, hidden=True)))

    def test_public_pass_does_not_imply_private_probe_pass(self):
        task = make_task("code_repair", 1)
        spec_before = task.public_spec()
        overfit = task.reference_solution()
        overfit["expressions"]["base"] += " + (1 if x == -50 else 0)"
        self.assertTrue(all_pass(task.grade(overfit)))
        final = task.grade(overfit, hidden=True)
        self.assertFalse(final["base"]["passed"])
        self.assertNotIn("-50", json.dumps(final))
        self.assertEqual(spec_before, task.public_spec())
        self.assertTrue(all_pass(task.grade(overfit)))

    def test_public_spec_excludes_oracle_expressions_and_final_probe_sets(self):
        task = make_task("code_repair", 2)
        public = json.dumps(task.public_spec())
        for expression in task.reference_solution()["expressions"].values():
            self.assertNotIn(expression, public)
        self.assertNotIn("private_probes", public)
        self.assertNotIn("reference_solution", public)
        self.assertEqual(len(task.public_spec()["public_probes"]), 4)
        fields = set()
        for instance in range(12):
            another = make_task("code_repair", instance)
            _, info = another.inject_fault(another.reference_solution())
            fields.update(info["changed_fields"])
        self.assertEqual(fields, {"environment.coefficients.multiplier", "environment.coefficients.rate"})


class RecordTransformation(unittest.TestCase):
    def test_hand_computed_normalization_deduplication_signs_and_decimal_report(self):
        def record(ident, client, quantity, price, kind="sale", status="ok"):
            return {"record_id": ident, "client": client, "quantity": quantity,
                    "unit_price": price, "kind": kind, "status": status}

        source = [record(" a ", "acme", "02", "NaN"),
                  record(" a ", "acme ", " 02 ", " 1.05 ", " Sale "),
                  record("A", "duplicate", "9", "9.99"),
                  record("b", " Acme", "3", "0.55", "REFUND"),
                  record("c", "birch", "1", "0.25", "refund"),
                  record("v", "acme", "1", "8.00", status="void"),
                  record("u", "acme", "２", "1.00"),
                  record("z", "acme", "00", "1.00"),
                  record("n", "acme", "1", "-1.00"),
                  record("e", " ", "1", "1.00")]
        task = Task(make_task("data_transform", 0).root_contract, {"records": source})
        expected = {"rows": [
            {"record_id": "A", "client": "ACME", "kind": "sale", "quantity": 2, "unit_cents": 105, "net_cents": 210},
            {"record_id": "B", "client": "ACME", "kind": "refund", "quantity": 3, "unit_cents": 55, "net_cents": -165},
            {"record_id": "C", "client": "BIRCH", "kind": "refund", "quantity": 1, "unit_cents": 25, "net_cents": -25},
        ], "aggregates": [{"client": "ACME", "count": 2, "net_cents": 45},
                          {"client": "BIRCH", "count": 1, "net_cents": -25}],
            "report": "CLIENT COUNT NET\nACME 2 0.45\nBIRCH 1 -0.25\nTOTAL 3 0.20"}
        self.assertEqual(expected, task.reference_solution())
        self.assertTrue(all_pass(task.grade(expected)))
        self.assertTrue(all_pass(task.grade(expected, hidden=True)))
        self.assertEqual(source, task.public_spec()["environment"]["records"])

    def test_plausible_but_wrong_rows_groups_and_report_are_rejected(self):
        task = make_task("data_transform", 3)
        for field in ("rows", "aggregates", "report"):
            with self.subTest(field=field):
                solution = task.reference_solution()
                if field == "rows":
                    solution["rows"][0]["net_cents"] += 1
                elif field == "aggregates":
                    solution["aggregates"][0]["count"] += 1
                else:
                    solution["report"] += "\n"
                self.assertFalse(task.grade(solution)[field]["passed"])
                self.assertFalse(all_pass(task.grade(solution, hidden=True)))
        wrong_type = task.reference_solution()
        wrong_type["rows"][0]["quantity"] = True
        self.assertFalse(task.grade(wrong_type)["rows"]["passed"])

    def test_self_consistent_empty_artifacts_cannot_erase_public_source_truth(self):
        task = make_task("data_transform", 1)
        fake = {"rows": [], "aggregates": [], "report": "CLIENT COUNT NET\nTOTAL 0 0.00"}
        public = task.grade(fake)
        self.assertFalse(public["rows"]["passed"])
        self.assertFalse(all_pass(public))
        self.assertTrue(public["aggregates"]["passed"])
        self.assertTrue(public["report"]["passed"])
        final = task.grade(fake, hidden=True)
        self.assertTrue(all(not gate["passed"] for gate in final.values()))


class ConstrainedScheduling(unittest.TestCase):
    def test_distinct_valid_schedules_and_arbitrary_assignment_order_are_accepted(self):
        for split in ("dev", "heldout"):
            for instance in range(6):
                task = make_task("scheduling", instance, split)
                alternate = delayed_schedule(task)
                self.assertNotEqual(alternate, task.reference_solution())
                self.assertTrue(all_pass(task.grade(alternate)))
                self.assertTrue(all_pass(task.grade(alternate, hidden=True)))
                alternate["assignments"].reverse()
                self.assertTrue(all_pass(task.grade(alternate, hidden=True)))

    def test_capacity_calendar_and_precedence_use_feasibility_not_oracle_equality(self):
        root = make_task("scheduling", 0).root_contract
        environment = {"resources": ["R1", "R2"], "horizon": 12,
                       "jobs": [{"task_id": name, "duration": 2, "release": 0, "deadline": 12,
                                 "resources": ["R1", "R2"]} for name in ("A", "B")],
                       "precedence": [], "unavailable": []}
        task = Task(root, environment)
        touching = {"assignments": [{"task_id": "A", "resource": "R1", "start": 0},
                                     {"task_id": "B", "resource": "R1", "start": 2}]}
        self.assertTrue(all_pass(task.grade(touching, hidden=True)))
        overlapping = copy.deepcopy(touching)
        overlapping["assignments"][1]["start"] = 1
        self.assertFalse(task.grade(overlapping)["resources"]["passed"])
        environment["unavailable"] = [{"resource": "R1", "start": 2, "end": 4}]
        task = Task(root, environment)
        self.assertFalse(task.grade(touching, hidden=True)["resources"]["passed"])
        touching["assignments"][1]["start"] = 4
        self.assertTrue(all_pass(task.grade(touching, hidden=True)))
        environment["precedence"] = [{"before": "A", "after": "B", "lag": 1}]
        task = Task(root, environment)
        wrong_order = {"assignments": [{"task_id": "A", "resource": "R1", "start": 4},
                                       {"task_id": "B", "resource": "R2", "start": 0}]}
        verdict = task.grade(wrong_order, hidden=True)
        self.assertTrue(verdict["assignments"]["passed"])
        self.assertTrue(verdict["resources"]["passed"])
        self.assertFalse(verdict["precedence"]["passed"])

    def test_missing_duplicate_forbidden_resource_boolean_and_late_assignments_fail(self):
        task = make_task("scheduling", 0)
        malformed = []
        missing = task.reference_solution()
        missing["assignments"].pop()
        malformed.append(missing)
        duplicate = task.reference_solution()
        duplicate["assignments"][1] = copy.deepcopy(duplicate["assignments"][0])
        malformed.append(duplicate)
        for field, value in (("resource", "R9"), ("start", True), ("start", -1), ("start", 32)):
            solution = task.reference_solution()
            solution["assignments"][0][field] = value
            malformed.append(solution)
        for candidate in malformed:
            self.assertFalse(task.grade(candidate)["assignments"]["passed"])
            self.assertFalse(all_pass(task.grade(candidate, hidden=True)))


if __name__ == "__main__":
    unittest.main()
