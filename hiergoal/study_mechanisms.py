# SPDX-License-Identifier: Apache-2.0
"""Pure mechanism checks and evidence derived from a semantically replayed trace.

``evidence_from_events`` is an observer, not a standalone trace authenticator.
The replay engine calls it only after checking every event against the immutable
task and the recorded model response. It never treats a model diagnosis as a
verified cause, and a zero comparison count is absence of evidence.
"""
from __future__ import annotations

import copy
import json

from hiergoal.study_protocol import digest


class InvalidAction(ValueError):
    """The responder proposed an action outside the fixed artifact protocol."""


def _text(value, name: str) -> str:
    if not isinstance(value, str) or not 5 <= len(value.strip()) <= 1200:
        raise InvalidAction(f"{name} must contain 5..1200 characters")
    return value.strip()


def validate_replan(plan: dict, leaf: dict, grades: dict, change: dict) -> tuple[dict, str]:
    """Return a copied plan with one failed leaf instruction revised.

    Parentage, dependencies, acceptance gates, all other instructions, and the
    caller's plan stay unchanged. ``diagnosis`` is model text, not causal proof.
    """
    if (not isinstance(plan, dict) or not isinstance(leaf, dict)
            or leaf.get("id") not in plan.get("leaves", {})
            or plan["leaves"][leaf["id"]] != leaf):
        raise InvalidAction("Replan requires the current failed leaf")
    checks = leaf.get("checks")
    if (not isinstance(checks, list) or not checks
            or any(gate not in grades or type(grades[gate].get("passed")) is not bool
                   for gate in checks)):
        raise InvalidAction("Replan lacks valid gate failure evidence")
    if all(grades[gate]["passed"] for gate in checks):
        raise InvalidAction("Unnecessary replan lacks failure evidence")
    if not isinstance(change, dict) or set(change) != {"diagnosis", "revised_instruction"}:
        raise InvalidAction("Replan may change only diagnosis and the failed instruction")
    diagnosis = _text(change["diagnosis"], "diagnosis")
    instruction = _text(change["revised_instruction"], "revised_instruction")
    if instruction == leaf["instruction"]:
        raise InvalidAction("Replan did not revise the instruction")
    revised = copy.deepcopy(plan)
    revised["leaves"][leaf["id"]]["instruction"] = instruction
    revised["leaves"][leaf["id"]]["revision"] += 1
    return revised, diagnosis


def replan_decision(before_grades: dict, after_grades: dict, leaf: dict | None,
                    *, fault_delivered: bool = False) -> dict:
    """Operational replan policy, using public gate outcomes only.

    A newly delivered failure authorizes a replan. Otherwise an accepted action
    that passes any previously failing gate gets another execution opportunity;
    a still-failing active leaf with no such progress authorizes a replan. This
    is a preregistered gate-level policy, not proof of optimal plan necessity.
    """
    failed = sorted(gate for gate, value in after_grades.items() if value["passed"] is False)
    progressed = sorted(gate for gate, value in after_grades.items()
                        if value["passed"] is True
                        and gate in before_grades and before_grades[gate]["passed"] is False)
    if leaf is None:
        needed, reason = False, "no_active_leaf"
    elif all(after_grades[gate]["passed"] for gate in leaf["checks"]):
        needed, reason = False, "active_leaf_passed"
    elif fault_delivered:
        needed, reason = True, "delivered_fault"
    elif progressed:
        needed, reason = False, "gate_progress"
    else:
        needed, reason = True, "stalled_failed_leaf"
    return {"needed": needed, "reason": reason,
            "failed_gates": failed, "progressed_gates": progressed}


def _related_gates(dependencies: dict, target: str) -> set[str]:
    """Target, its authoritative ancestors, and its authoritative descendants."""
    reverse = {gate: set() for gate in dependencies}
    for gate, parents in dependencies.items():
        for parent in parents:
            reverse.setdefault(parent, set()).add(gate)

    def reachable(graph, start):
        found, pending = set(), [start]
        while pending:
            node = pending.pop()
            if node in found:
                continue
            found.add(node)
            pending.extend(graph.get(node, []))
        return found

    return reachable(dependencies, target) | reachable(reverse, target)


def _owners(plan: dict | None) -> dict[str, str]:
    return {gate: ident for ident, leaf in (plan or {}).get("leaves", {}).items()
            for gate in leaf["checks"]}


def _tree(plan: dict | None) -> dict:
    leaves = (plan or {}).get("leaves", {})
    groups = (plan or {}).get("milestones", [])
    parents = {group["id"]: group.get("parent", "G0") for group in groups}
    parents.update({ident: leaf["parent"] for ident, leaf in leaves.items()})

    def depth(ident):
        seen, count = set(), 0
        while ident in parents:
            if ident in seen:
                raise ValueError("Cyclic goal parentage in audited plan")
            seen.add(ident)
            count += 1
            ident = parents[ident]
        return count

    count = len(leaves)
    edges = sum(len(leaf["depends_on"]) for leaf in leaves.values())
    maximum = max((depth(ident) for ident in parents), default=0)
    return {"goal_count": 1 + len(groups) + count, "leaf_count": count,
            "max_depth_edges": maximum, "max_depth": maximum,
            "dependency_edges": edges,
            "dependency_density": 2 * edges / (count * (count - 1)) if count > 1 else 0.0}


def evidence_from_events(events: list[dict], task) -> dict:
    """Derive counters from events whose semantics the caller already replayed.

    Replan attempts count issued ``request_started`` events, including interrupted
    requests; accepted/rejected counts describe consumed responses. Locality
    counts comparisons, not unique goals. Artifact locality compares each repair
    after a delivered fault with the pre-fault artifact; fields shared with any
    related gate are excluded. All counts are exact deterministic integers.
    """
    contract, dependencies = task.root_contract, task.dependencies
    root_hash = digest(contract)
    plan = None
    evidence = {
        "trace_replayed": True,
        "root_preserved": True,
        "root_changes": {"explicit_edit_requests": 0, "rejected_edit_requests": 0, "actual_changes": 0},
        "final_grade_called": False, "final_grade_passed": None,
        "tree": _tree(None),
        "trace": {"checkpoint_events": 0, "root_state_transitions": 0, "leaf_state_transitions": 0,
                  "milestone_state_transitions": 0, "accepted_replans_with_failure_evidence": 0,
                  "post_fault_target_replans": 0,
                  "failure_causes_recorded": 0, "model_diagnoses_recorded": 0},
        "replanning": {"attempted": 0, "accepted": 0, "rejected": 0, "unnecessary": 0,
                       "parent_preserved_events": 0, "unrelated_goals_checked": 0,
                       "unrelated_goals_unchanged": 0, "decision_events": 0,
                       "needed_decisions": 0, "deferred_progress_decisions": 0},
        "execution_locality": {"unrelated_artifact_fields_checked": 0,
                               "unrelated_artifact_fields_unchanged": 0,
                               "violations": 0, "nonvacuous_events": 0},
        "dependencies": {"invalidation_events": 0, "invalidated_goals": 0, "reverified_goals": 0},
        "fault": {"triggered": False, "delivered": False, "no_impact": False,
                  "forced": False, "domain_delivered": False},
    }
    prior_leaves, prior_milestones, prior_root, invalidated = {}, {}, None, set()
    baseline, unrelated_fields = None, set()
    fault_target = None
    latest_decision, latest_root_edit = None, False
    changed_roots = set()
    artifact_fields = getattr(task, "gate_artifact_fields", {})
    reserved_root_keys = {"root", "root_contract", "objective", "gates", "dependencies", "acceptance_rules"}

    def observe_root(value):
        if value != contract:
            evidence["root_preserved"] = False
            changed_roots.add(digest(value))

    def observe_spec(spec):
        if isinstance(spec, dict) and all(key in spec for key in contract):
            observe_root({key: spec[key] for key in contract})

    for event in events:
        kind = event["type"]
        if event.get("root_sha256", root_hash) != root_hash:
            evidence["root_preserved"] = False
        if "root_contract" in event:
            observe_root(event["root_contract"])
        for key in ("public_spec", "before_spec", "after_spec"):
            if key in event:
                observe_spec(event[key])
        if kind in ("request_started", "response"):
            observe_root(event["request"]["root_contract"])
            observe_spec(event["request"].get("task"))

        if kind == "shared_plan":
            plan = event["plan"]
            evidence["tree"] = _tree(plan)
            if latest_root_edit and (event.get("error") or {}).get("status") == "FAIL":
                evidence["root_changes"]["rejected_edit_requests"] += 1
            latest_root_edit = False
        elif kind == "replan_decision":
            latest_decision = event
            evidence["replanning"]["decision_events"] += 1
            evidence["replanning"]["needed_decisions"] += int(event["needed"])
            evidence["replanning"]["deferred_progress_decisions"] += int(event["reason"] == "gate_progress")
        elif kind == "request_started":
            if event["role"] == "replan":
                counters = evidence["replanning"]
                counters["attempted"] += 1
                leaf, grades = event["request"].get("leaf"), event["request"].get("public_feedback", {})
                failed_leaf = bool(leaf and any(grades.get(gate, {}).get("passed") is False
                                               for gate in leaf.get("checks", [])))
                authorized = latest_decision is not None and latest_decision.get("needed") is True
                counters["unnecessary"] += int(not failed_leaf or not authorized)
            if event["role"] != "plan":
                latest_decision = None
        elif kind == "response":
            latest_root_edit = False
            try:
                reply = json.loads(event["record"]["text"])
            except (ValueError, TypeError, KeyError, RecursionError):
                reply = None
            if isinstance(reply, dict):
                patch = reply.get("patch")
                latest_root_edit = bool(set(reply) & reserved_root_keys or
                                        isinstance(patch, dict) and set(patch) & reserved_root_keys)
            evidence["root_changes"]["explicit_edit_requests"] += int(latest_root_edit)
        elif kind == "rejected":
            evidence["root_changes"]["rejected_edit_requests"] += int(latest_root_edit)
            latest_root_edit = False
            if event["role"] == "replan":
                evidence["replanning"]["rejected"] += 1
        elif kind == "checkpoint":
            plan = event["plan"]
            current, milestones = event["leaf_statuses"], event["milestone_statuses"]
            evidence["trace"]["checkpoint_events"] += 1
            current_root = event.get("root_status")
            if current_root is not None:
                evidence["trace"]["root_state_transitions"] += int(prior_root is not None and prior_root != current_root)
                prior_root = current_root
            evidence["trace"]["leaf_state_transitions"] += sum(
                value != prior_leaves[ident] for ident, value in current.items() if ident in prior_leaves)
            evidence["trace"]["milestone_state_transitions"] += sum(
                value != prior_milestones[ident] for ident, value in milestones.items() if ident in prior_milestones)
            owners, newly_invalidated = _owners(plan), set()
            for gate, ident in owners.items():
                if prior_leaves.get(ident) == "completed" and current.get(ident) == "pending":
                    if any(current.get(owners.get(parent)) != "completed"
                           for parent in dependencies.get(gate, [])):
                        newly_invalidated.add(ident)
                if ident in invalidated and current.get(ident) == "completed":
                    evidence["dependencies"]["reverified_goals"] += 1
                    invalidated.remove(ident)
            evidence["dependencies"]["invalidation_events"] += int(bool(newly_invalidated))
            evidence["dependencies"]["invalidated_goals"] += len(newly_invalidated)
            invalidated.update(newly_invalidated)
            prior_leaves, prior_milestones = current, milestones
        elif kind == "fault":
            fault = event["fault"]
            counters = evidence["fault"]
            counters["triggered"] = True
            counters["delivered"] |= bool(event["delivered"])
            counters["no_impact"] |= not bool(event["delivered"])
            counters["forced"] |= fault.get("perturbation_type") == "subgoal" or fault.get("kind") == "forced_subgoal"
            counters["domain_delivered"] |= bool(fault.get("domain_fault_delivered", event["delivered"]))
            fault_target = (fault.get("target_gate") if event["delivered"]
                            and fault.get("domain_fault_delivered", event["delivered"]) else None)
            if fault.get("kind") and fault.get("target_gate") and fault.get("changed_fields"):
                evidence["trace"]["failure_causes_recorded"] += 1
            if event["delivered"] and fault.get("target_gate") in dependencies:
                related = _related_gates(dependencies, fault["target_gate"])
                unrelated = set(dependencies) - related
                touched_fields = {field for gate in related for field in artifact_fields.get(gate, [])}
                unrelated_fields = {field for gate in unrelated for field in artifact_fields.get(gate, [])} - touched_fields
                baseline = event["before_solution"]
            else:
                baseline, unrelated_fields = None, set()
        elif kind == "patch" and baseline is not None and unrelated_fields:
            counters = evidence["execution_locality"]
            counters["nonvacuous_events"] += 1
            for field in unrelated_fields:
                unchanged = (field in baseline and field in event["after_solution"]
                             and baseline[field] == event["after_solution"][field])
                counters["unrelated_artifact_fields_checked"] += 1
                counters["unrelated_artifact_fields_unchanged"] += int(unchanged)
                counters["violations"] += int(not unchanged)
        elif kind == "replan":
            before, after = event["before_plan"], event["after_plan"]
            leaf = before["leaves"][event["leaf_id"]]
            target = leaf["checks"][0]
            counters = evidence["replanning"]
            counters["accepted"] += 1
            counters["parent_preserved_events"] += int(
                before.get("milestones") == after.get("milestones")
                and set(before["leaves"]) == set(after["leaves"])
                and all(value["parent"] == after["leaves"][ident]["parent"]
                        for ident, value in before["leaves"].items()))
            owners = _owners(before)
            for gate in set(dependencies) - _related_gates(dependencies, target):
                if gate in owners:
                    ident = owners[gate]
                    counters["unrelated_goals_checked"] += 1
                    counters["unrelated_goals_unchanged"] += int(
                        before["leaves"][ident] == after["leaves"].get(ident))
            evidence["trace"]["accepted_replans_with_failure_evidence"] += int(
                any(event["public_grades"][gate]["passed"] is False for gate in leaf["checks"]))
            evidence["trace"]["post_fault_target_replans"] += int(
                fault_target is not None and fault_target in leaf["checks"])
            evidence["trace"]["model_diagnoses_recorded"] += int(bool(event.get("diagnosis")))
            plan = after
        elif kind == "final_grade":
            evidence["final_grade_called"] = True
            evidence["final_grade_passed"] = bool(event["passed"])
    evidence["root_changes"]["actual_changes"] = len(changed_roots)
    return evidence
