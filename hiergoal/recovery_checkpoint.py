# SPDX-License-Identifier: Apache-2.0
"""Verified, replayable post-failure forks without leaking the source solution.

Checkpoints are archival evidence, not model payloads.  They contain the source
artifact so an independent auditor can replay the exact deterministic fault.
Only ``model_view`` (or equivalently reconstructed failed-state fields) may be
used to form a repair request.  No oracle is called by any helper in this file.
"""
from __future__ import annotations

import copy
import re

from hiergoal.recovery_protocol import make_task
from hiergoal.study_protocol import canonical, digest
from hiergoal.study_planning import validate_plan


SCHEMA = "hiergoal.recovery_checkpoint.v1"


def all_pass(grades):
    return (isinstance(grades, dict) and bool(grades)
            and all(isinstance(value, dict) and value.get("passed") is True
                    for value in grades.values()))


def _hash(value, name):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(name + " must be a SHA-256 hex digest")


def _task_spec(task):
    root = task.root_contract
    spec = {"family": root["family"], "instance": root["instance"],
            "split": root["split"], "seed": root["seed"],
            "scale": copy.deepcopy(root["scale"]), "fault_kind": "forced_subgoal",
            "task_id": task.task_id, "root_sha256": digest(root),
            "initial_public_spec_sha256": digest(task.public_spec()),
            "initial_environment_sha256": digest(task.public_spec()["environment"]),
            "planned_tree": task.topology_stats()}
    # make_task verifies every supplied fingerprint against an initial task.
    make_task(spec)
    return spec


def validate_initial_plan(plan, task):
    """Reject changes to structure, dependency relation, checks, IDs or revisions."""
    if not isinstance(plan, dict) or set(plan) != {"milestones", "leaves"}:
        raise ValueError("Checkpoint needs a normalized initial plan")
    leaves = plan.get("leaves")
    if not isinstance(leaves, dict) or not leaves:
        raise ValueError("Checkpoint needs initial leaves")
    instructions = {}
    for leaf in leaves.values():
        if not isinstance(leaf, dict) or not isinstance(leaf.get("checks"), list) or len(leaf["checks"]) != 1:
            raise ValueError("Malformed checkpoint leaf")
        gate = leaf["checks"][0]
        if not isinstance(gate, str) or gate in instructions:
            raise ValueError("Duplicate checkpoint gate")
        instructions[gate] = leaf.get("instruction")
    expected = validate_plan({"instructions": instructions}, task)
    if canonical(expected) != canonical(plan):
        raise ValueError("Checkpoint changed initial goal structure or instruction normalization")
    return expected


def make_checkpoint(task, plan, source_solution, *, pair_id, protocol_id,
                    source_trace_sha256=None):
    """Build a checkpoint on a fresh task; never mutate caller state.

    Both public and hidden source checks must pass.  A failed source artifact is
    a preparation failure; callers must not repair it using hidden feedback.
    """
    if not isinstance(pair_id, str) or not pair_id.strip():
        raise ValueError("Checkpoint requires a pair identifier")
    _hash(protocol_id, "protocol_id")
    if source_trace_sha256 is not None:
        _hash(source_trace_sha256, "source_trace_sha256")
    spec = _task_spec(task)
    if getattr(task, "_subgoal_faults", None) != 0:
        raise ValueError("Checkpoint source task already received a subgoal fault")
    fresh = make_task(spec)
    plan = validate_initial_plan(plan, fresh)
    before_public, before_hidden = fresh.grade(source_solution), fresh.grade(source_solution, hidden=True)
    if not all_pass(before_public) or not all_pass(before_hidden):
        raise ValueError("Checkpoint source must independently pass public and hidden grading")
    root = fresh.root_contract
    public_spec = fresh.public_spec()
    failed, receipt = fresh.inject_subgoal_fault(source_solution)
    feedback = fresh.grade(failed)
    if (not receipt.get("domain_fault_delivered") or all_pass(feedback)
            or receipt["target_gate"] not in feedback
            or feedback[receipt["target_gate"]]["passed"] is not False
            or digest(failed) == digest(source_solution)
            or canonical(fresh.public_spec()) != canonical(public_spec)
            or canonical(fresh.root_contract) != canonical(root)):
        raise ValueError("Checkpoint fault did not produce the registered local failure")
    owners = [leaf["id"] for leaf in plan["leaves"].values()
              if leaf["checks"] == [receipt["target_gate"]]]
    if len(owners) != 1:
        raise ValueError("Checkpoint target has no unique failed leaf")
    result = {
        "schema_version": SCHEMA, "protocol_id": protocol_id,
        "pair_id": pair_id, "task": spec,
        "root_contract": root, "root_sha256": digest(root),
        "public_spec": public_spec, "public_spec_sha256": digest(public_spec),
        "plan": plan, "plan_sha256": digest(plan),
        "source_solution": copy.deepcopy(source_solution),
        "source_solution_sha256": digest(source_solution),
        "source_public_grade": before_public,
        "source_hidden_grade": before_hidden,
        "source_trace_sha256": source_trace_sha256,
        "failed_solution": failed, "failed_solution_sha256": digest(failed),
        "public_feedback": feedback,
        "fault_receipt": receipt,
        "target_leaf_id": owners[0],
        "repair_history": [],
        "source_visibility": "archival_only_never_repair_prompt",
    }
    result["checkpoint_sha256"] = digest(result)
    return result


def restore_checkpoint(checkpoint, *, pair=None, protocol_id=None):
    """Verify hashes and replay fault/state; return a fresh independent fork."""
    if not isinstance(checkpoint, dict) or checkpoint.get("schema_version") != SCHEMA:
        raise ValueError("Invalid recovery checkpoint")
    if protocol_id is not None and checkpoint.get("protocol_id") != protocol_id:
        raise ValueError("Checkpoint belongs to another recovery protocol")
    if pair is not None:
        if checkpoint.get("pair_id") != pair["pair_id"]:
            raise ValueError("Checkpoint belongs to another assigned pair")
        if canonical(checkpoint.get("task")) != canonical(pair["task"]):
            raise ValueError("Checkpoint task differs from assigned task")
    body = {key: value for key, value in checkpoint.items() if key != "checkpoint_sha256"}
    if checkpoint.get("checkpoint_sha256") != digest(body):
        raise ValueError("Checkpoint fingerprint changed")
    source_task = make_task(checkpoint["task"])
    expected = make_checkpoint(source_task, checkpoint["plan"], checkpoint["source_solution"],
                               pair_id=checkpoint["pair_id"], protocol_id=checkpoint["protocol_id"],
                               source_trace_sha256=checkpoint["source_trace_sha256"])
    if canonical(expected) != canonical(checkpoint):
        raise ValueError("Checkpoint does not replay its registered source/fault/state")
    fork = make_task(checkpoint["task"])
    failed, receipt = fork.inject_subgoal_fault(checkpoint["source_solution"])
    if (canonical(failed) != canonical(checkpoint["failed_solution"])
            or canonical(receipt) != canonical(checkpoint["fault_receipt"])):
        raise ValueError("Checkpoint fork is not deterministic")
    # JSON serialization sorts IDs lexicographically (S1,S10,...).  Restore the
    # authoritative gate order rather than relying on serialized dictionary
    # insertion order when active_leaf selects the next pending subgoal.
    restored_plan = validate_initial_plan(checkpoint["plan"], fork)
    return fork, restored_plan, copy.deepcopy(failed)


def model_view(checkpoint):
    """Explicit allowlist: the correct pre-fault artifact is never included."""
    # Verify before selecting; checksums alone are not semantic verification.
    _, restored_plan, failed = restore_checkpoint(checkpoint)
    return {"root_contract": copy.deepcopy(checkpoint["root_contract"]),
            "task": copy.deepcopy(checkpoint["public_spec"]),
            "plan": restored_plan,
            "artifact": failed,
            "public_feedback": copy.deepcopy(checkpoint["public_feedback"]),
            "history": []}
