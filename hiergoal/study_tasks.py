# SPDX-License-Identifier: Apache-2.0
"""Bounded, deterministic tasks for an offline-first mechanism study.

These tasks measure repair under a changed rule/source/calendar, not real-world
autonomy.  The immutable root contract requires the *current* environment to be
satisfied.  Public specifications never contain reference expressions or final
private probes.  ``reference_solution`` exists only for offline oracle/plumbing
checks and must never be passed to a live model.

The code domain interprets a small integer expression AST.  It never compiles,
executes, or evaluates submitted Python code and exposes no objects, imports,
filesystem, network, comprehensions, loops, or arbitrary function calls.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import random
import re
from decimal import Decimal
from typing import Any


FAMILIES = ("code_repair", "data_transform", "scheduling")
SPLITS = ("dev", "heldout")
_MAX_SOURCE = 512
_MAX_NODES = 128
_MAX_DEPTH = 32
_MAX_INTEGER = 1_000_000_000
_STAGES = ("base", "adjusted", "total")
_NAMES = {
    "base": {"x", "y", "floor", "multiplier"},
    "adjusted": {"base", "z", "rate", "cap"},
    "total": {"adjusted", "z", "bonus"},
}
_PRICE = re.compile(r"[0-9]{1,5}\.[0-9]{2}\Z")
_QUANTITY = re.compile(r"[0-9]{1,2}\Z")


def _result(passed: bool, good: str, bad: str) -> dict:
    return {"passed": bool(passed), "message": good if passed else bad}


def _all_pass(results: dict) -> bool:
    return bool(results) and all(item["passed"] for item in results.values())


def _integer(value: Any) -> int:
    if type(value) is not int or abs(value) > _MAX_INTEGER:
        raise ValueError("Expected a bounded integer")
    return value


def _same_json(left: Any, right: Any) -> bool:
    """JSON equality with strict types (Python's True == 1 is not accepted)."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(
            _same_json(left[key], value) for key, value in right.items()
        )
    if type(left) is list:
        return len(left) == len(right) and all(
            _same_json(a, b) for a, b in zip(left, right)
        )
    return type(left) in (str, int, bool, type(None)) and left == right


def _parse_expression(source: Any, names: set[str]) -> ast.Expression:
    if type(source) is not str or not source or len(source) > _MAX_SOURCE:
        raise ValueError("Invalid expression length")
    try:
        tree = ast.parse(source, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise ValueError("Invalid expression syntax") from exc
    if sum(1 for _ in ast.walk(tree)) > _MAX_NODES:
        raise ValueError("Expression has too many nodes")

    def check(node: ast.AST, depth: int = 0) -> None:
        if depth > _MAX_DEPTH:
            raise ValueError("Expression is too deep")
        children: list[ast.AST]
        if isinstance(node, ast.Expression):
            children = [node.body]
        elif isinstance(node, ast.Constant):
            if type(node.value) is not int or abs(node.value) > 1_000_000:
                raise ValueError("Only bounded integer literals are allowed")
            children = []
        elif isinstance(node, ast.Name):
            if node.id not in names or not isinstance(node.ctx, ast.Load):
                raise ValueError("Unknown name")
            children = []
        elif isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod)
        ):
            children = [node.left, node.right]
        elif isinstance(node, ast.UnaryOp) and isinstance(
            node.op, (ast.UAdd, ast.USub, ast.Not)
        ):
            children = [node.operand]
        elif isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            children = list(node.values)
        elif isinstance(node, ast.Compare) and all(isinstance(
            op, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
        ) for op in node.ops):
            children = [node.left, *node.comparators]
        elif isinstance(node, ast.IfExp):
            children = [node.test, node.body, node.orelse]
        elif isinstance(node, ast.Call):
            if (not isinstance(node.func, ast.Name)
                    or node.func.id not in {"min", "max", "abs"}
                    or node.keywords
                    or not (len(node.args) == 1 if node.func.id == "abs"
                            else 2 <= len(node.args) <= 4)):
                raise ValueError("Call is not allowed")
            children = list(node.args)
        else:
            raise ValueError("AST node is not allowed")
        for child in children:
            check(child, depth + 1)

    check(tree)
    return tree


def _interpret(tree: ast.Expression, values: dict[str, int]) -> int:
    """Evaluate only nodes already structurally validated by _parse_expression."""
    def boolean(value: Any) -> bool:
        if type(value) is not bool:
            raise ValueError("Conditions must be Boolean")
        return value

    def visit(node: ast.AST) -> int | bool:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant):
            return _integer(node.value)
        if isinstance(node, ast.Name):
            return _integer(values[node.id])
        if isinstance(node, ast.BinOp):
            left, right = _integer(visit(node.left)), _integer(visit(node.right))
            if isinstance(node.op, ast.Add):
                value = left + right
            elif isinstance(node.op, ast.Sub):
                value = left - right
            elif isinstance(node.op, ast.Mult):
                value = left * right
            elif isinstance(node.op, ast.FloorDiv):
                value = left // right
            elif isinstance(node.op, ast.Mod):
                value = left % right
            else:
                raise ValueError("Unsupported arithmetic")
            return _integer(value)
        if isinstance(node, ast.UnaryOp):
            value = visit(node.operand)
            if isinstance(node.op, ast.Not):
                return not boolean(value)
            value = _integer(value)
            return _integer(-value if isinstance(node.op, ast.USub) else value)
        if isinstance(node, ast.BoolOp):
            for child in node.values:
                value = boolean(visit(child))
                if isinstance(node.op, ast.And) and not value:
                    return False
                if isinstance(node.op, ast.Or) and value:
                    return True
            return isinstance(node.op, ast.And)
        if isinstance(node, ast.Compare):
            left = _integer(visit(node.left))
            for op, child in zip(node.ops, node.comparators):
                right = _integer(visit(child))
                if isinstance(op, ast.Eq):
                    valid = left == right
                elif isinstance(op, ast.NotEq):
                    valid = left != right
                elif isinstance(op, ast.Lt):
                    valid = left < right
                elif isinstance(op, ast.LtE):
                    valid = left <= right
                elif isinstance(op, ast.Gt):
                    valid = left > right
                else:
                    valid = left >= right
                if not valid:
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            return visit(node.body if boolean(visit(node.test)) else node.orelse)
        if isinstance(node, ast.Call):
            args = [_integer(visit(arg)) for arg in node.args]
            if node.func.id == "abs":
                return _integer(abs(args[0]))
            return _integer(min(args) if node.func.id == "min" else max(args))
        raise ValueError("Unsupported expression")

    return _integer(visit(tree))


def _code_truth(inputs: dict, environment: dict) -> dict[str, int]:
    rules = environment["coefficients"]
    base = max(0, inputs["x"] - rules["floor"]) * rules["multiplier"] + inputs["y"]
    adjusted = min(rules["cap"], max(0, base + rules["rate"] * inputs["z"]))
    total = adjusted + (rules["bonus"] if inputs["z"] >= 0 else -rules["bonus"])
    return {"base": base, "adjusted": adjusted, "total": total}


def _normalize_records(records: list[dict]) -> list[dict]:
    seen: set[str] = set()
    rows = []
    for raw in records:
        record_id = raw["record_id"].strip().upper()
        client = raw["client"].strip().upper()
        kind, status = raw["kind"].strip().lower(), raw["status"].strip().lower()
        quantity, price = raw["quantity"].strip(), raw["unit_price"].strip()
        if (status != "ok" or not record_id or not client
                or kind not in {"sale", "refund"}
                or not _QUANTITY.fullmatch(quantity) or not _PRICE.fullmatch(price)):
            continue
        count = int(quantity)
        if not 1 <= count <= 50 or record_id in seen:
            continue
        whole, fraction = price.split(".")
        unit = int(whole) * 100 + int(fraction)
        rows.append({"record_id": record_id, "client": client, "kind": kind,
                     "quantity": count, "unit_cents": unit,
                     "net_cents": count * unit * (1 if kind == "sale" else -1)})
        seen.add(record_id)
    return sorted(rows, key=lambda row: row["record_id"])


def _aggregate(rows: list[dict]) -> list[dict]:
    values: dict[str, list[int]] = {}
    for row in rows:
        pair = values.setdefault(row["client"], [0, 0])
        pair[0] += 1
        pair[1] += row["net_cents"]
    return [{"client": name, "count": values[name][0], "net_cents": values[name][1]}
            for name in sorted(values)]


def _money(cents: int) -> str:
    whole, fraction = divmod(abs(cents), 100)
    return f"{'-' if cents < 0 else ''}{whole}.{fraction:02d}"


def _render_report(aggregates: list[dict]) -> str:
    lines = ["CLIENT COUNT NET"]
    lines.extend(f"{row['client']} {row['count']} {_money(row['net_cents'])}"
                 for row in aggregates)
    lines.append(f"TOTAL {sum(row['count'] for row in aggregates)} "
                 f"{_money(sum(row['net_cents'] for row in aggregates))}")
    return "\n".join(lines)


def _independent_data_oracle(records: list[dict]) -> dict:
    """Separate final checker: decimal conversion and direct source aggregation."""
    selected: dict[str, dict] = {}
    totals: dict[str, int] = {}
    counts: dict[str, int] = {}
    for record in records:
        text = {key: value.strip() for key, value in record.items()}
        ident, client = text["record_id"].upper(), text["client"].upper()
        kind = text["kind"].lower()
        price, quantity = text["unit_price"], text["quantity"]
        valid_price = (price.count(".") == 1
                       and 1 <= len(price.split(".")[0]) <= 5
                       and len(price.split(".")[1]) == 2
                       and all(char in "0123456789" for char in price.replace(".", "")))
        valid_quantity = (1 <= len(quantity) <= 2
                          and all(char in "0123456789" for char in quantity))
        if (text["status"].lower() != "ok" or not ident or not client
                or kind not in ("sale", "refund") or not valid_price
                or not valid_quantity or not 1 <= int(quantity) <= 50
                or ident in selected):
            continue
        unit = int(Decimal(price) * 100)
        net = unit * int(quantity) * (-1 if kind == "refund" else 1)
        selected[ident] = {"record_id": ident, "client": client, "kind": kind,
                           "quantity": int(quantity), "unit_cents": unit, "net_cents": net}
        counts[client] = counts.get(client, 0) + 1
        totals[client] = totals.get(client, 0) + net
    groups = [{"client": name, "count": counts[name], "net_cents": totals[name]}
              for name in sorted(totals)]
    lines = ["CLIENT COUNT NET"]
    for name in sorted(totals):
        lines.append(f"{name} {counts[name]} {Decimal(totals[name]) / 100:.2f}")
    lines.append(f"TOTAL {len(selected)} {Decimal(sum(totals.values())) / 100:.2f}")
    return {"rows": [selected[key] for key in sorted(selected)],
            "aggregates": groups, "report": "\n".join(lines)}


def _rows_shape(rows: Any) -> bool:
    if type(rows) is not list or len(rows) > 100:
        return False
    fields = {"record_id", "client", "kind", "quantity", "unit_cents", "net_cents"}
    return all(type(row) is dict and set(row) == fields
               and all(type(row[key]) is str for key in ("record_id", "client", "kind"))
               and all(type(row[key]) is int and abs(row[key]) <= _MAX_INTEGER
                       for key in ("quantity", "unit_cents", "net_cents")) for row in rows)


def _groups_shape(groups: Any) -> bool:
    return (type(groups) is list and len(groups) <= 100
            and all(type(row) is dict and set(row) == {"client", "count", "net_cents"}
                    and type(row["client"]) is str
                    and all(type(row[key]) is int and abs(row[key]) <= _MAX_INTEGER
                            for key in ("count", "net_cents")) for row in groups))


class Task:
    """One trial's task and environment; create a fresh instance for each arm.

    Public dictionaries are defensive copies.  Mutating one cannot alter the
    immutable task objectives, and only ``inject_fault`` changes environment.
    The perturbation is independent of the submitted solution.  Its impact is
    measured, so solutions robust to the update are explicitly recorded.
    """

    def __init__(self, contract: dict, environment: dict, *, private_probes: list[dict] | None = None):
        self._contract = copy.deepcopy(contract)
        self._environment = copy.deepcopy(environment)
        self._private_probes = copy.deepcopy(private_probes or [])
        self._perturbations = 0

    @property
    def task_id(self) -> str:
        return self._contract["task_id"]

    @property
    def family(self) -> str:
        return self._contract["family"]

    @property
    def split(self) -> str:
        return self._contract["split"]

    @property
    def gates(self) -> dict[str, str]:
        return copy.deepcopy(self._contract["gates"])

    @property
    def dependencies(self) -> dict[str, list[str]]:
        return copy.deepcopy(self._contract["dependencies"])

    @property
    def root_contract(self) -> dict:
        return copy.deepcopy(self._contract)

    def public_spec(self) -> dict:
        spec = self.root_contract
        spec["environment"] = copy.deepcopy(self._environment)
        spec["environment_revision"] = self._perturbations
        if self.family == "code_repair":
            spec["public_probes"] = [
                {"input": copy.deepcopy(inputs), "expected": _code_truth(inputs, self._environment)}
                for inputs in self._contract["public_probe_inputs"]
            ]
        return spec

    def initial_solution(self) -> dict:
        if self.family == "code_repair":
            return {"expressions": {name: "0" for name in _STAGES}}
        if self.family == "data_transform":
            return {"rows": [], "aggregates": [], "report": ""}
        return {"assignments": [{"task_id": job["task_id"], "resource": job["resources"][0],
                                 "start": 0} for job in self._environment["jobs"]]}

    def reference_solution(self) -> dict:
        """Current-environment oracle, exclusively for offline tests."""
        if self.family == "code_repair":
            rules = self._environment["coefficients"]
            return {"expressions": {
                "base": f"max(0, x - {rules['floor']}) * {rules['multiplier']} + y",
                "adjusted": f"min({rules['cap']}, max(0, base + {rules['rate']} * z))",
                "total": f"adjusted + ({rules['bonus']} if z >= 0 else -{rules['bonus']})",
            }}
        if self.family == "data_transform":
            rows = _normalize_records(self._environment["records"])
            groups = _aggregate(rows)
            return {"rows": rows, "aggregates": groups, "report": _render_report(groups)}
        return self._schedule_oracle()

    def grade(self, solution: dict, *, hidden: bool = False) -> dict[str, dict]:
        if type(solution) is not dict:
            return {name: _result(False, "", "Solution must be a JSON object.") for name in self.gates}
        if self.family == "code_repair":
            return self._grade_code(solution, hidden=hidden)
        if self.family == "data_transform":
            return self._grade_data(solution, hidden=hidden)
        return self._grade_schedule(solution, hidden=hidden)

    def _grade_code(self, solution: dict, *, hidden: bool) -> dict[str, dict]:
        expressions = solution.get("expressions")
        if (set(solution) != {"expressions"} or type(expressions) is not dict
                or set(expressions) != set(_STAGES)):
            return {name: _result(False, "", "Expected exactly three named expressions.")
                    for name in self.gates}
        trees: dict[str, ast.Expression] = {}
        passed = {name: True for name in _STAGES}
        messages = {name: "All stage probes passed." for name in _STAGES}
        for name in _STAGES:
            try:
                trees[name] = _parse_expression(expressions[name], _NAMES[name])
            except ValueError:
                passed[name] = False
                messages[name] = "Expression violates the published bounded syntax."
        probes = self._contract["public_probe_inputs"] + (self._private_probes if hidden else [])
        for inputs in probes:
            values = {**inputs, **self._environment["coefficients"]}
            expected = _code_truth(inputs, self._environment)
            for name in _STAGES:
                if name not in trees:
                    continue
                try:
                    value = _interpret(trees[name], values)
                    values[name] = value
                    if value != expected[name]:
                        passed[name] = False
                        messages[name] = ("Final stage probes failed." if hidden
                                          else "Expression does not meet the public stage contract.")
                except (ValueError, ZeroDivisionError, KeyError, OverflowError, RecursionError):
                    passed[name] = False
                    messages[name] = "Expression or upstream stage did not produce a bounded integer."
        return {name: {"passed": passed[name], "message": messages[name]} for name in _STAGES}

    def _grade_data(self, solution: dict, *, hidden: bool) -> dict[str, dict]:
        if set(solution) != {"rows", "aggregates", "report"}:
            return {name: _result(False, "", "Expected rows, aggregates, and report only.")
                    for name in self.gates}
        rows, groups, report = solution["rows"], solution["aggregates"], solution["report"]
        rows_valid, groups_valid = _rows_shape(rows), _groups_shape(groups)
        rows_pass = rows_valid and _same_json(rows, _normalize_records(self._environment["records"]))
        groups_pass = rows_valid and groups_valid and _same_json(groups, _aggregate(rows))
        report_pass = groups_valid and type(report) is str and report == _render_report(groups)
        if hidden:
            expected = _independent_data_oracle(self._environment["records"])
            rows_pass = rows_pass and _same_json(rows, expected["rows"])
            groups_pass = groups_pass and _same_json(groups, expected["aggregates"])
            report_pass = report_pass and _same_json(report, expected["report"])
        return {
            "rows": _result(rows_pass, "Normalized rows passed.", "Rows do not satisfy source normalization."),
            "aggregates": _result(groups_pass, "Aggregates passed.", "Aggregates do not satisfy row/source totals."),
            "report": _result(report_pass, "Report passed.", "Report does not satisfy the required totals and format."),
        }

    def _schedule_assignments(self, solution: dict) -> dict[str, dict] | None:
        entries = solution.get("assignments")
        jobs = {job["task_id"]: job for job in self._environment["jobs"]}
        if set(solution) != {"assignments"} or type(entries) is not list or len(entries) != len(jobs):
            return None
        assignments = {}
        for entry in entries:
            if (type(entry) is not dict or set(entry) != {"task_id", "resource", "start"}
                    or type(entry["task_id"]) is not str or entry["task_id"] not in jobs
                    or entry["task_id"] in assignments or type(entry["resource"]) is not str
                    or type(entry["start"]) is not int):
                return None
            job = jobs[entry["task_id"]]
            if (entry["resource"] not in job["resources"]
                    or not job["release"] <= entry["start"]
                    or entry["start"] + job["duration"] > job["deadline"]
                    or not 0 <= entry["start"] < self._environment["horizon"]):
                return None
            assignments[entry["task_id"]] = entry
        return assignments

    def _grade_schedule(self, solution: dict, *, hidden: bool) -> dict[str, dict]:
        assignments = self._schedule_assignments(solution)
        shape = assignments is not None
        resources, precedence = shape, shape
        if assignments is not None:
            jobs = {job["task_id"]: job for job in self._environment["jobs"]}
            intervals = [(item["resource"], item["start"], item["start"] + jobs[ident]["duration"])
                         for ident, item in assignments.items()]
            for index, (resource, start, end) in enumerate(intervals):
                for other, left, right in intervals[index + 1:]:
                    if resource == other and start < right and left < end:
                        resources = False
                for block in self._environment["unavailable"]:
                    if resource == block["resource"] and start < block["end"] and block["start"] < end:
                        resources = False
            for edge in self._environment["precedence"]:
                before, after = edge["before"], edge["after"]
                if (assignments[after]["start"] < assignments[before]["start"]
                        + jobs[before]["duration"] + edge["lag"]):
                    precedence = False
            if hidden:
                # Independent final check expands integer slots instead of comparing intervals.
                occupied: set[tuple[str, int]] = set()
                blocked = {(block["resource"], slot) for block in self._environment["unavailable"]
                           for slot in range(block["start"], block["end"])}
                for job in self._environment["jobs"]:
                    assignment = assignments[job["task_id"]]
                    slots = {(assignment["resource"], slot)
                             for slot in range(assignment["start"], assignment["start"] + job["duration"])}
                    if occupied.intersection(slots) or blocked.intersection(slots):
                        resources = False
                    occupied.update(slots)
                finish = {job["task_id"]: assignments[job["task_id"]]["start"] + job["duration"]
                          for job in self._environment["jobs"]}
                precedence = precedence and all(
                    finish[edge["before"]] <= assignments[edge["after"]]["start"] - edge["lag"]
                    for edge in self._environment["precedence"]
                )
        return {
            "assignments": _result(shape, "Assignments and windows passed.", "Assignments, capabilities, or windows are invalid."),
            "resources": _result(resources, "Resource capacity and availability passed.", "Resource overlap or calendar violation."),
            "precedence": _result(precedence, "Precedence passed.", "Precedence or lag constraints are invalid."),
        }

    def _schedule_oracle(self) -> dict:
        # Jobs are generated in topological order with generous finite deadlines.
        assignments: list[dict] = []
        finish: dict[str, int] = {}
        durations = {job["task_id"]: job["duration"] for job in self._environment["jobs"]}
        for job in self._environment["jobs"]:
            earliest = max([job["release"], *[
                finish[edge["before"]] + edge["lag"]
                for edge in self._environment["precedence"] if edge["after"] == job["task_id"]
            ]])
            chosen = None
            for start in range(earliest, job["deadline"] - job["duration"] + 1):
                for resource in job["resources"]:
                    end = start + job["duration"]
                    busy = [(a["start"], a["start"] + durations[a["task_id"]])
                            for a in assignments if a["resource"] == resource]
                    busy += [(block["start"], block["end"])
                             for block in self._environment["unavailable"] if block["resource"] == resource]
                    if not any(start < right and left < end for left, right in busy):
                        chosen = {"task_id": job["task_id"], "resource": resource, "start": start}
                        break
                if chosen is not None:
                    break
            if chosen is None:
                raise RuntimeError("Generated scheduling instance has no greedy oracle schedule")
            assignments.append(chosen)
            finish[job["task_id"]] = chosen["start"] + job["duration"]
        return {"assignments": assignments}

    def inject_fault(self, solution: dict) -> tuple[dict, dict]:
        """Apply a persistent public environment update after public all-pass.

        The submitted artifact is never corrupted.  Both paired arms get the
        same update for the same initial task.  ``delivered`` requires observed
        pass-to-fail; a robust solution receives ``perturbation_no_impact``.
        """
        before_grade = self.grade(solution)
        if not _all_pass(before_grade):
            raise ValueError("An environment update requires a public all-pass solution")
        before = copy.deepcopy(self._environment)
        selector = self._contract["instance_seed"] + self._perturbations
        if self.family == "code_repair":
            coefficient, target = ("multiplier", "base") if selector % 2 == 0 else ("rate", "adjusted")
            self._environment["coefficients"][coefficient] += 1
            kind = "business_rule_update"
            changed = [f"environment.coefficients.{coefficient}"]
        elif self.family == "data_transform":
            records = self._environment["records"]
            current = _normalize_records(records)
            selected = current[selector % len(current)]
            for index, record in enumerate(records):
                if record["record_id"].strip().upper() == selected["record_id"]:
                    # Skip malformed earlier occurrences; perturb the selected source row.
                    if _normalize_records([record]):
                        unit = selected["unit_cents"] + 1 + selector % 9
                        record["unit_price"] = _money(unit)
                        break
            kind, target = "source_record_update", "rows"
            changed = [f"environment.records[{index}].unit_price"]
        else:
            canonical = self._schedule_oracle()["assignments"][0]
            job = self._environment["jobs"][0]
            slot = canonical["start"] + selector % job["duration"]
            index = len(self._environment["unavailable"])
            self._environment["unavailable"].append(
                {"resource": canonical["resource"], "start": slot, "end": slot + 1}
            )
            kind, target = "resource_calendar_update", "resources"
            changed = [f"environment.unavailable[{index}]"]
        self._perturbations += 1
        copied = copy.deepcopy(solution)
        after_grade = self.grade(copied)
        delivered = not _all_pass(after_grade)
        info = {
            "kind": kind, "changed_fields": changed, "target_gate": target,
            "delivered": delivered,
            "status": "delivered" if delivered else "perturbation_no_impact",
            "seed": self._contract["seed"], "instance_seed": self._contract["instance_seed"],
            "environment_revision": self._perturbations,
            "environment_before": before, "environment_after": copy.deepcopy(self._environment),
            "before_grade": before_grade, "after_grade": after_grade,
        }
        return copied, info


def make_task(family: str, instance: int, split: str = "heldout", seed: int = 1729) -> Task:
    """Generate reproducible, split-disjoint task instances without external I/O."""
    if family not in FAMILIES:
        raise ValueError(f"Unknown task family: {family}")
    if split not in SPLITS:
        raise ValueError(f"Unknown task split: {split}")
    if type(instance) is not int or instance < 0 or type(seed) is not int:
        raise ValueError("Instance must be a nonnegative integer and seed an integer")
    digest = hashlib.sha256(f"hiergoal-study-v1:{family}:{split}:{seed}:{instance}".encode()).hexdigest()
    instance_seed = int(digest[:16], 16)
    rng = random.Random(instance_seed)
    contract = {
        "task_id": f"{family}-{split}-{instance:03d}-{digest[:8]}",
        "family": family, "split": split, "seed": seed, "instance": instance,
        "instance_seed": instance_seed, "contract_version": 1,
        "objective": "Satisfy every gate against the currently published environment.",
        "environment_policy": "Rules, source records, or resource calendars may be updated. Recompute as needed against the latest public environment; task objectives and acceptance policy remain fixed.",
        "benchmark_scope": "Bounded mechanism benchmark; no evidence of real-world autonomy.",
    }
    if family == "code_repair":
        coefficients = {"floor": rng.randint(1, 5), "multiplier": rng.randint(2, 5),
                        "rate": rng.randint(1, 4), "cap": rng.randint(30, 80), "bonus": rng.randint(1, 7)}
        floor = coefficients["floor"]
        probes = [{"x": floor + 2, "y": 2, "z": 1},
                  {"x": floor - 1, "y": -3, "z": -2},
                  {"x": floor + 4, "y": 1, "z": 0},
                  {"x": floor + 10, "y": 10, "z": 5}]
        private = [{"x": -50, "y": 7, "z": -1}, {"x": 50, "y": -20, "z": -10},
                   {"x": floor, "y": -1, "z": 0}, {"x": floor + 1, "y": 0, "z": 2}]
        private += [{"x": rng.randint(-50, 50), "y": rng.randint(-20, 20), "z": rng.randint(-10, 10)}
                    for _ in range(8)]
        contract.update({
            "gates": {"base": "Compute max(0, x minus floor), multiply by multiplier, then add y.",
                      "adjusted": "Add rate times z to base, then clamp into the inclusive range zero through cap.",
                      "total": "Add bonus to adjusted if z is nonnegative; subtract bonus otherwise."},
            "dependencies": {"base": [], "adjusted": ["base"], "total": ["adjusted"]},
            "solution_shape": {"expressions": {name: "one Python integer expression string" for name in _STAGES}},
            "allowed_names": {name: sorted(_NAMES[name]) for name in _STAGES},
            "expression_language": {
                "operators": ["+", "-", "*", "//", "%", "unary + and -", "comparisons", "and", "or", "not", "A if condition else B"],
                "calls": {"abs": "one integer argument", "min": "two to four integer arguments", "max": "two to four integer arguments"},
                "limits": {"source_characters": _MAX_SOURCE, "ast_nodes": _MAX_NODES,
                           "ast_depth": _MAX_DEPTH, "literal_absolute_value": 1_000_000,
                           "integer_absolute_value": _MAX_INTEGER},
                "types": "Inputs, arithmetic, and outputs are integers (Boolean outputs forbidden). Conditions are Boolean comparisons/combinations. Division by zero fails. // and % use Python integer semantics.",
                "execution": "Interpreted AST whitelist; no eval, exec, attributes, subscripts, imports, loops, strings, floats, exponentiation, or arbitrary calls.",
            },
            "input_domain": {"x": [-50, 50], "y": [-20, 20], "z": [-10, 10]},
            "public_probe_inputs": probes,
            "final_check": "Additional private inputs in the published domain test the same rules; their inputs and outcomes are not shown during execution.",
        })
        return Task(contract, {"coefficients": coefficients}, private_probes=private)
    if family == "data_transform":
        clients = rng.sample(["ALDER", "BIRCH", "CEDAR", "ELM", "FIR", "MAPLE", "OAK", "PINE"], 3)
        records = []
        prefix = digest[:5].upper()
        for index in range(6):
            cents = rng.randint(101, 2499)
            records.append({"record_id": f" {prefix}-{index + 1:02d} ",
                            "client": f" {clients[index % 3].lower()} ",
                            "quantity": f" {rng.randint(1, 5)} ", "unit_price": f" {_money(cents)} ",
                            "kind": " ReFuNd " if index in (2, 4) else " Sale ", "status": " OK "})
        records.insert(0, {**records[0], "unit_price": "NaN"})
        records.extend([{**records[2], "client": "DUPLICATE", "quantity": "50", "unit_price": "999.99"},
                        {**records[3], "record_id": f"{prefix}-VOID", "status": " void "},
                        {**records[4], "record_id": f"{prefix}-BAD", "quantity": "2.5"},
                        {**records[5], "record_id": f"{prefix}-EMPTY", "client": " "}])
        contract.update({
            "gates": {"rows": "Normalize, filter, deduplicate, and sort source rows.",
                      "aggregates": "Aggregate normalized row counts and signed integer cents by client.",
                      "report": "Render exact sorted client totals and grand total."},
            "dependencies": {"rows": [], "aggregates": ["rows"], "report": ["aggregates"]},
            "solution_shape": {"rows": [{"record_id": "string", "client": "string", "kind": "sale or refund",
                                           "quantity": "integer", "unit_cents": "integer", "net_cents": "integer"}],
                               "aggregates": [{"client": "string", "count": "integer", "net_cents": "integer"}],
                               "report": "string"},
            "normalization_rules": [
                "Visit source records in the given order. Strip whitespace from every value; uppercase record_id and client; lowercase kind and status.",
                "Keep only status ok, nonempty record_id and client, kind sale or refund, quantity matching ASCII [0-9]{1,2} and integer 1..50, and unit_price matching ASCII [0-9]{1,5}.[0-9]{2} with a literal decimal point.",
                "Skip invalid records. Keep the first VALID record for each normalized record_id; invalid earlier records do not reserve an ID. Sort output rows by record_id using lexical order.",
                "unit_cents is exact decimal unit_price times 100. net_cents is quantity times unit_cents, negative for refund and positive for sale. Preserve kind and quantity in rows.",
                "Aggregate per normalized client, sorted lexically. count counts retained records, not items; net_cents sums signed row cents.",
            ],
            "report_format": "No trailing newline. First line CLIENT COUNT NET. Then one line per aggregate: <client> <count> <net amount with exactly two decimal places>. Last line TOTAL <retained record count> <grand net amount with exactly two decimal places>. Single spaces; negative signs only for negative amounts.",
            "arithmetic": "Exact integer cents, no binary floating point or rounding.",
            "final_check": "Independent source-to-output recomputation checks the same public records and rules; no secret source records are required.",
        })
        return Task(contract, {"records": records})
    resources = ["R1", "R2"] if instance_seed % 2 else ["R2", "R1"]
    names = [f"J{index + 1}" for index in range(5)]
    jobs = [{"task_id": name, "duration": rng.randint(1, 3), "release": rng.randint(0, 2),
             "deadline": 12 + index * 4,
             "resources": resources[:] if index in (0, 2, 4) else [resources[index % 2]]}
            for index, name in enumerate(names)]
    precedence = [{"before": names[a], "after": names[b], "lag": rng.randint(0, 1)}
                  for a, b in [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)]]
    contract.update({
        "gates": {"assignments": "Assign every job exactly once to a permitted resource within its time window.",
                  "resources": "Respect one-job resource capacity and every unavailable interval.",
                  "precedence": "Respect every predecessor finish time plus minimum lag."},
        "dependencies": {"assignments": [], "resources": ["assignments"],
                         "precedence": ["assignments", "resources"]},
        "solution_shape": {"assignments": [{"task_id": "string", "resource": "string", "start": "integer slot"}]},
        "scheduling_rules": [
            "Any feasible schedule is accepted. There is no canonical order, target schedule, or makespan objective. Assignment array order is irrelevant.",
            "Every job runs without interruption for its given duration on exactly one resource in its permitted resources list.",
            "Start at or after release; finish at or before deadline. Starts and durations are integer slots. One slot is 60 seconds.",
            "Intervals are half-open: [start, start + duration). Adjacent intervals are allowed; a job must never intersect a resource's unavailable intervals or another job on that resource.",
            "For every precedence edge, the after job starts at or after the before job finishes plus lag.",
        ],
        "final_check": "Independent occupied-slot and precedence checks validate the same public constraints, accepting every feasible schedule.",
    })
    environment = {"resources": sorted(resources), "jobs": jobs, "precedence": precedence,
                   "horizon": 32, "unavailable": [
                       {"resource": resources[0], "start": 3, "end": 4},
                       {"resource": resources[1], "start": 6, "end": 7},
                   ]}
    return Task(contract, environment)
