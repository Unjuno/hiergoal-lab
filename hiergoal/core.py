# SPDX-License-Identifier: Apache-2.0
"""Validated three-level goal tree. No model text may redefine the root."""
from __future__ import annotations
import json
import re
from typing import Any

ROOT_GOAL = (
    "Repair the ledger package to satisfy the published specification and all "
    "independent acceptance tests, without editing or removing any tests."
)

# The experiment owner, not the model, defines the deterministic acceptance gates.
GATES = {
    "invalid_rows": "test_invalid_rows",
    "blank_rows": "test_blanks",
    "decimal_exactness": "test_exact_decimal",
    "half_even": "test_half_even_rounding",
    "refund_sort": "test_refunds_trim_and_sort",
    "cli": "test_cli",
}
GATE_DESCRIPTIONS = {
    "invalid_rows": "reject missing/invalid/nonfinite values and blank clients",
    "blank_rows": "ignore empty CSV records",
    "decimal_exactness": "sum decimal payments without float error",
    "half_even": "format final net with decimal HALF_EVEN rounding",
    "refund_sort": "respect refunds, trim clients, and sort output",
    "cli": "run the module as a CLI and emit correct JSON",
}
MAX_LEAVES = 8


class PlanError(ValueError):
    pass


def parse_object(text: str) -> dict:
    text = text.strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        lines = text.splitlines()
        if len(lines) > 2 and lines[-1].strip() == fence:
            text = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanError("Model reply is not a standalone JSON object") from exc
    if not isinstance(value, dict):
        raise PlanError("Expected a JSON object")
    return value


def _title(value: Any, field: str) -> str:
    if not isinstance(value, str) or not (5 <= len(value.strip()) <= 240):
        raise PlanError(field + " must have 5..240 characters")
    return value.strip()


def validate_plan(document: dict) -> dict:
    """Reject missing coverage, duplicates, cycles and an invalid goal hierarchy."""
    raw = document.get("milestones")
    if not isinstance(raw, list) or not 2 <= len(raw) <= 4:
        raise PlanError("Plan must have 2..4 mid-term milestones")
    milestones = []
    leaves = {}
    seen_checks = []
    milestone_ids = set()
    for milestone in raw:
        if not isinstance(milestone, dict):
            raise PlanError("Invalid milestone")
        mid = milestone.get("id")
        if not isinstance(mid, str) or not re.fullmatch(r"M[1-4]", mid) or mid in milestone_ids:
            raise PlanError("Milestone IDs must be unique M1..M4")
        milestone_ids.add(mid)
        members = milestone.get("subgoals")
        if not isinstance(members, list) or not 1 <= len(members) <= 5:
            raise PlanError("Each milestone needs 1..5 short-term subgoals")
        milestones.append({"id": mid, "title": _title(milestone.get("title"), "milestone title"),
                           "status": "pending"})
        for item in members:
            if not isinstance(item, dict):
                raise PlanError("Invalid subgoal")
            sid = item.get("id")
            if not isinstance(sid, str) or not re.fullmatch(r"S[1-8]", sid) or sid in leaves:
                raise PlanError("Short-term IDs must be unique S1..S8")
            checks = item.get("checks")
            if not isinstance(checks, list) or not checks or any(
                not isinstance(check, str) or check not in GATES for check in checks
            ) or len(set(checks)) != len(checks):
                raise PlanError("Subgoal checks must be distinct known gate IDs")
            seen_checks += checks
            deps = item.get("depends_on", [])
            if not isinstance(deps, list) or any(not isinstance(dep, str) for dep in deps):
                raise PlanError("depends_on must be an array of subgoal IDs")
            if len(set(deps)) != len(deps):
                raise PlanError("Duplicate dependency")
            leaves[sid] = {
                "id": sid, "parent": mid, "instruction": _title(item.get("instruction"), "instruction"),
                "checks": checks, "depends_on": deps, "status": "pending",
                "attempts": 0, "revision": 0, "history": []
            }
    if not 3 <= len(leaves) <= MAX_LEAVES:
        raise PlanError("Plan must have 3..8 short-term goals")
    if len(seen_checks) != len(GATES) or set(seen_checks) != set(GATES):
        raise PlanError("Every acceptance gate must be assigned exactly once")
    for leaf in leaves.values():
        if leaf["id"] in leaf["depends_on"]:
            raise PlanError("Self-dependency")
        if any(dep not in leaves for dep in leaf["depends_on"]):
            raise PlanError("Dangling dependency")
    color = {}
    def visit(sid: str) -> None:
        if color.get(sid) == 1:
            raise PlanError("Circular subgoal dependency")
        if color.get(sid) == 2:
            return
        color[sid] = 1
        for dep in leaves[sid]["depends_on"]:
            visit(dep)
        color[sid] = 2
    for sid in leaves:
        visit(sid)
    return {"root": {"id": "G0", "goal": ROOT_GOAL, "status": "pending"},
            "milestones": milestones, "leaves": leaves, "replans": 0}


def next_leaf(state: dict) -> dict | None:
    for leaf in state["leaves"].values():
        if leaf["status"] == "pending" and all(
            state["leaves"][dep]["status"] == "completed" for dep in leaf["depends_on"]
        ):
            return leaf
    return None


def update_rollups(state: dict) -> None:
    for milestone in state["milestones"]:
        relevant = [leaf for leaf in state["leaves"].values()
                    if leaf["parent"] == milestone["id"] and leaf["status"] != "superseded"]
        milestone["status"] = ("completed" if relevant and all(
            leaf["status"] == "completed" for leaf in relevant
        ) else "active" if any(leaf["status"] in ("running", "completed") for leaf in relevant)
          else "pending")
    state["root"]["status"] = ("completed" if all(
        x["status"] == "completed" for x in state["milestones"]
    ) else "active")


def replace_failed_leaf(state: dict, failed_id: str, instruction: str, diagnosis: str) -> dict:
    old = state["leaves"][failed_id]
    if old["status"] != "failed" or old["revision"] >= 1:
        raise PlanError("Only a first failed attempt can be replanned")
    name = failed_id + "r1"
    if name in state["leaves"]:
        raise PlanError("Duplicate revised leaf")
    new = {
        "id": name, "parent": old["parent"], "instruction": _title(instruction, "revised instruction"),
        "checks": old["checks"][:], "depends_on": old["depends_on"][:],
        "status": "pending", "attempts": 0, "revision": 1, "history": [],
        "replaces": failed_id, "diagnosis": _title(diagnosis, "diagnosis")
    }
    old["status"] = "superseded"
    state["leaves"][name] = new
    for leaf in state["leaves"].values():
        if leaf["status"] == "pending":
            leaf["depends_on"] = [name if dep == failed_id else dep
                                  for dep in leaf["depends_on"]]
    state["replans"] += 1
    update_rollups(state)
    return new
