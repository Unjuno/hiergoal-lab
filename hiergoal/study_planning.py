# SPDX-License-Identifier: Apache-2.0
"""Validated goal trees and dependency-preserving plans at bounded scale."""
from __future__ import annotations

import copy
import re

from hiergoal.study_mechanisms import InvalidAction


def _text(value, field):
    if not isinstance(value, str) or not 5 <= len(value.strip()) <= 1200:
        raise InvalidAction(f"{field} must contain 5..1200 characters")
    return value.strip()


def transitive_dependencies(graph):
    result, visiting = {}, set()
    def visit(node):
        if node not in graph or node in visiting:
            raise InvalidAction("Cyclic or dangling dependency")
        if node in result:
            return result[node]
        visiting.add(node)
        ancestors = set()
        for parent in graph[node]:
            ancestors.add(parent)
            ancestors.update(visit(parent))
        visiting.remove(node)
        result[node] = ancestors
        return ancestors
    for node in graph:
        visit(node)
    return result


def _validate_structure(plan, task):
    leaves, groups = plan["leaves"], plan["milestones"]
    group_index = {group["id"]: group for group in groups}
    if len(group_index) != len(groups) or not leaves:
        raise InvalidAction("Duplicate or empty goal hierarchy")
    depth = {"G0": 0}
    visiting = set()
    def group_depth(gid):
        if gid in depth:
            return depth[gid]
        if gid not in group_index or gid in visiting:
            raise InvalidAction("Cyclic or dangling hierarchy parent")
        visiting.add(gid)
        depth[gid] = group_depth(group_index[gid].get("parent", "G0")) + 1
        visiting.remove(gid)
        return depth[gid]
    for gid in group_index:
        group_depth(gid)
        if not any(leaf["parent"] == gid for leaf in leaves.values()) and not any(g.get("parent") == gid for g in groups):
            raise InvalidAction("Empty hierarchy group")
    for leaf in leaves.values():
        if leaf["parent"] not in group_index:
            raise InvalidAction("Leaf has no intermediate goal")
        group_depth(leaf["parent"])
    owners = {leaf["checks"][0]: leaf["id"] for leaf in leaves.values()}
    if set(owners) != set(task.gates) or len(owners) != len(leaves):
        raise InvalidAction("Every gate needs exactly one executable leaf")
    actual = transitive_dependencies({sid: leaf["depends_on"] for sid, leaf in leaves.items()})
    required = transitive_dependencies(task.dependencies)
    for gate, sid in owners.items():
        if actual[sid] != {owners[dep] for dep in required[gate]}:
            raise InvalidAction("Plan changed the authoritative dependency relation")
    expected_depth = getattr(task, "hierarchy_spec", {}).get("depth_levels")
    if expected_depth is not None and max(depth[leaf["parent"]] + 1 for leaf in leaves.values()) != expected_depth - 1:
        raise InvalidAction("Plan does not have the prescribed hierarchy depth")
    return plan


def validate_plan(value, task):
    if not isinstance(value, dict):
        raise InvalidAction("Plan must be a JSON object")
    skeleton = getattr(task, "hierarchy_spec", None)
    if skeleton is not None:
        if set(value) != {"instructions"} or not isinstance(value["instructions"], dict) or set(value["instructions"]) != set(task.gates):
            raise InvalidAction("Supply exactly one instruction per prescribed gate")
        owners = {gate: "S" + str(index + 1) for index, gate in enumerate(task.gates)}
        leaves = {
            owners[gate]: {"id": owners[gate], "parent": skeleton["gate_parents"][gate],
                           "instruction": _text(value["instructions"][gate], "instruction"),
                           "checks": [gate], "depends_on": [owners[dep] for dep in task.dependencies[gate]],
                           "revision": 0} for gate in task.gates
        }
        return _validate_structure({"milestones": copy.deepcopy(skeleton["groups"]), "leaves": leaves}, task)
    if set(value) != {"milestones"} or not isinstance(value["milestones"], list) or not 2 <= len(value["milestones"]) <= 4:
        raise InvalidAction("Only 2..4 milestones may be proposed; root is immutable")
    milestones, leaves, used_gates = [], {}, set()
    for item in value["milestones"]:
        if not isinstance(item, dict) or set(item) != {"id", "title", "subgoals"}:
            raise InvalidAction("Invalid milestone fields")
        mid = item["id"]
        if not isinstance(mid, str) or not re.fullmatch(r"M[1-4]", mid) or any(g["id"] == mid for g in milestones):
            raise InvalidAction("Milestone IDs must be unique M1..M4")
        milestones.append({"id": mid, "parent": "G0", "title": _text(item["title"], "title")})
        if not isinstance(item["subgoals"], list) or not item["subgoals"]:
            raise InvalidAction("Empty milestone")
        for raw in item["subgoals"]:
            if not isinstance(raw, dict) or set(raw) != {"id", "instruction", "checks", "depends_on"}:
                raise InvalidAction("Invalid subgoal fields")
            sid, checks, deps = raw["id"], raw["checks"], raw["depends_on"]
            if not isinstance(sid, str) or not re.fullmatch(r"S[1-8]", sid) or sid in leaves:
                raise InvalidAction("Subgoal IDs must be unique S1..S8")
            if not isinstance(checks, list) or len(checks) != 1 or not isinstance(checks[0], str) or checks[0] not in task.gates or checks[0] in used_gates:
                raise InvalidAction("Assign each known gate to exactly one leaf")
            if not isinstance(deps, list) or any(not isinstance(dep, str) for dep in deps) or len(set(deps)) != len(deps):
                raise InvalidAction("Invalid dependencies")
            leaves[sid] = {"id": sid, "parent": mid, "instruction": _text(raw["instruction"], "instruction"),
                           "checks": checks[:], "depends_on": deps[:], "revision": 0}
            used_gates.update(checks)
    if not 3 <= len(leaves) <= 8:
        raise InvalidAction("Base tasks require 3..8 leaves")
    return _validate_structure({"milestones": milestones, "leaves": leaves}, task)


def plan_prompt(task):
    skeleton = getattr(task, "hierarchy_spec", None)
    instruction = (
        'Return JSON {"instructions":{"gate_id":"task-specific executable instruction",...}}. '
        'Supply each gate exactly once. The owner prescribes the grouping tree and dependency graph '
        'to prescribe component count, hierarchy depth and direct-edge burden; deeper trees add '
        'certification gates. Create instructions within that fixed '
        'structure; do not change any goal, parent, gate, or dependency.'
    ) if skeleton is not None else (
        'Return JSON {"milestones":[{"id":"M1","title":"...",'
        '"subgoals":[{"id":"S1","instruction":"...","checks":["gate_id"],'
        '"depends_on":[]}]}]}. Use 2..4 milestones M1..M4 and exactly one '
        'leaf per gate, unique S1..S8. Preserve EXACTLY the authoritative dependency '
        'relation; do not add dependencies between otherwise independent goals. '
        'Give executable task-specific instructions, never edit root or acceptance rules.'
    )
    return {"root_contract": task.root_contract, "task": task.public_spec(), "gates": task.gates,
            "gate_dependencies": task.dependencies,
            "instruction": instruction + " Every instruction and milestone title must be a plain JSON string of 5..1200 characters after trimming, never an object or array. Express certification steps as plain-text executable instructions, not certificate artifact objects. The environment may change; objectives refer to current authoritative state."}


def statuses(plan, grades):
    if plan is None:
        return {}
    output = {}
    def done(sid):
        if sid not in output:
            leaf = plan["leaves"][sid]
            passed = all(grades[c]["passed"] for c in leaf["checks"])
            dependencies = all(done(dep) == "completed" for dep in leaf["depends_on"])
            output[sid] = "completed" if passed and dependencies else "pending"
        return output[sid]
    for sid in plan["leaves"]:
        done(sid)
    return output


def active_leaf(plan, grades):
    if plan is None:
        return None
    state = statuses(plan, grades)
    return next((leaf for leaf in plan["leaves"].values() if state[leaf["id"]] != "completed"
                 and all(state[dep] == "completed" for dep in leaf["depends_on"])), None)


def milestone_statuses(plan, grades):
    if plan is None:
        return {}
    leaves, result = statuses(plan, grades), {}
    groups = {item["id"]: item for item in plan["milestones"]}
    def done(gid):
        if gid not in result:
            child_leaves = [leaf["id"] for leaf in plan["leaves"].values() if leaf["parent"] == gid]
            child_groups = [other for other, group in groups.items() if group.get("parent", "G0") == gid]
            passed = all(leaves[sid] == "completed" for sid in child_leaves) and all(done(other) == "completed" for other in child_groups)
            result[gid] = "completed" if (child_leaves or child_groups) and passed else "pending"
        return result[gid]
    for gid in groups:
        done(gid)
    return result
