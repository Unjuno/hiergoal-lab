# SPDX-License-Identifier: Apache-2.0
"""Independent, frozen controlled-recovery pilot; never performs inference.

The earlier v2.5 experiment remains byte-for-byte intact.  This pilot estimates
repair conditional on a successfully generated, independently verified source
artifact.  Its six tasks and twelve paired checkpoints are not a powered test
of general effectiveness.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random

from hiergoal.study_protocol import (
    ROOT, SOURCE_FILES as V25_SOURCE_FILES, canonical, digest, save,
    host_metadata, make_trial_task,
)
from hiergoal.study_scale import make_task as make_scale_task
from hiergoal.study_tasks import FAMILIES


SCHEMA = "hiergoal.controlled_recovery.v1"
PROTOCOL_REVISION = "recovery-v1.0"
ARMS = ("fixed", "adaptive")
TASK_SEED = 20261127
SCHEDULE_SEED = 20261127
REPEATS = 2
LIMITS = {
    "max_calls": 8,
    "max_replans": 1,
    "max_total_tokens": 64000,
    "max_output_tokens": 4096,
    "max_prompt_bytes": 48000,
    "request_timeout_seconds": 90,
    "trial_timeout_seconds": 600,
    "batch_timeout_seconds": 14400,
}
PREPARATION_LIMITS = {**LIMITS, "max_replans": 0}

# Source fingerprints include all reused code/protocol dependencies as well as
# the independent recovery engine, auditor, analysis, and new protocol itself.
# Missing files fail preparation; a partial implementation cannot launch.
SOURCE_FILES = tuple(dict.fromkeys((*V25_SOURCE_FILES,
    "hiergoal/recovery_protocol.py",
    "hiergoal/recovery_checkpoint.py",
    "hiergoal/recovery.py",
    "hiergoal/recovery_audit.py",
    "hiergoal/recovery_analysis.py",
    "hiergoal/recovery_launch.py",
    "docs/controlled_recovery_protocol_ja.md",
    ".github/workflows/controlled-recovery.yml",
)))

# These are the immutable records available when the pilot was designed.
# Freeze their names rather than scanning new result directories during replay.
BASELINE_MANIFESTS = (
    "experiments/method-study-v1/pilot-manifest.json",
    "experiments/method-study-v1/study-manifest.json",
    "experiments/method-study-v2/pilot-manifest.json",
    "experiments/method-study-v2/study-manifest.json",
    "experiments/method-study-v2/mechanism-manifest.json",
    "experiments/method-study-v2/scale-manifest.json",
    "experiments/method-study-v2/reliability-manifest.json",
    "experiments/method-study-v2.1/pilot-manifest.json",
    "experiments/method-study-v2.1/study-manifest.json",
    "experiments/method-study-v2.1/mechanism-manifest.json",
    "experiments/method-study-v2.1/scale-manifest.json",
    "experiments/method-study-v2.1/reliability-manifest.json",
    "experiments/method-study-live/pilot/run-45656888380-attempt-1/manifest.json",
    "experiments/method-study-live/mechanism/run-45658610566-attempt-1/manifest.json",
    "experiments/method-study-live/scale/run-45667519808-attempt-1/manifest.json",
    "experiments/method-study-live/scale/run-45703053665-attempt-1/manifest.json",
    "experiments/method-study-live/study/run-45729335900-attempt-1/manifest.json",
    "experiments/method-study-live/reliability/run-45732751285-attempt-1/manifest.json",
)


def make_task(spec: dict):
    """Reconstruct only the registered initial task, without private-state I/O."""
    if not isinstance(spec, dict):
        raise ValueError("Task specification must be an object")
    scale = spec.get("scale", {"size": "small", "depth": 3, "density": "sparse"})
    task = make_scale_task(spec["family"], spec["instance"],
                           split=spec.get("split", "heldout"),
                           seed=spec.get("seed", TASK_SEED),
                           scale=scale["size"], depth=scale["depth"],
                           density=scale["density"])
    checks = {
        "task_id": task.task_id,
        "root_sha256": digest(task.root_contract),
        "initial_public_spec_sha256": digest(task.public_spec()),
        "initial_environment_sha256": digest(task.public_spec()["environment"]),
    }
    for field, value in checks.items():
        if field in spec and spec[field] != value:
            raise ValueError("Task specification mismatch: " + field)
    return task


def task_specs() -> list[dict]:
    output = []
    for family in FAMILIES:
        for instance in range(2):
            spec = {"family": family, "instance": instance, "split": "heldout",
                    "seed": TASK_SEED,
                    "scale": {"size": "small", "depth": 3, "density": "sparse"},
                    "fault_kind": "forced_subgoal"}
            task = make_task(spec)
            spec.update(task_id=task.task_id,
                        root_sha256=digest(task.root_contract),
                        initial_public_spec_sha256=digest(task.public_spec()),
                        initial_environment_sha256=digest(task.public_spec()["environment"]),
                        planned_tree=task.topology_stats())
            output.append(spec)
    return output


def source_hashes() -> dict:
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in SOURCE_FILES}


def task_non_overlap(tasks: list[dict]) -> dict:
    """Check exact IDs, root/spec hashes, and reconstructed task environments.

    This establishes no exact replay of the archived task instances, not that
    the task families or fault mechanism are novel.
    """
    prior_ids, prior_roots, prior_specs, prior_environments = set(), set(), set(), set()
    hashes, count = {}, 0
    for filename in BASELINE_MANIFESTS:
        raw = (ROOT / filename).read_bytes()
        hashes[filename] = hashlib.sha256(raw).hexdigest()
        manifest = json.loads(raw)
        for prior in manifest["tasks"]:
            count += 1
            prior_ids.add(prior["task_id"])
            prior_roots.add(prior["root_sha256"])
            prior_specs.add(prior["initial_public_spec_sha256"])
            task = make_trial_task(prior, seed=prior.get("seed", manifest["task_seed"]))
            prior_environments.add(digest(task.public_spec()["environment"]))
    overlaps = []
    for spec in tasks:
        for field, previous in (("task_id", prior_ids), ("root_sha256", prior_roots),
                                ("initial_public_spec_sha256", prior_specs),
                                ("initial_environment_sha256", prior_environments)):
            if spec[field] in previous:
                overlaps.append({"task_id": spec["task_id"], "field": field})
    if overlaps:
        raise ValueError("Recovery pilot reuses archived task content: " + canonical(overlaps))
    return {"baseline_manifest_sha256": hashes, "archived_task_records": count,
            "archived_unique_task_ids": len(prior_ids), "exact_overlap_count": 0,
            "scope": "Exact task IDs, root/spec hashes and initial environment hashes; same task families are reused."}


def build_manifest(backend="openai", model="gpt-6-luna") -> dict:
    if backend not in ("openai", "oracle"):
        raise ValueError("Recovery pilot permits only openai or offline oracle")
    if model != "gpt-6-luna":
        raise ValueError("The frozen recovery pilot model is gpt-6-luna")
    tasks = task_specs()
    pairs = [{"pair_id": f"{task['task_id']}-r{repeat}",
              "task_id": task["task_id"], "repeat": repeat,
              "task": copy.deepcopy(task)}
             for task in tasks for repeat in range(1, REPEATS + 1)]
    rng = random.Random(SCHEDULE_SEED)
    rng.shuffle(pairs)
    # Exactly six fixed-first and six adaptive-first pairs, randomly assigned.
    orders = [list(ARMS)] * (len(pairs) // 2) + [list(reversed(ARMS))] * (len(pairs) // 2)
    rng.shuffle(orders)
    trials = []
    for pair, assigned_order in zip(pairs, orders):
        order = assigned_order[:]
        pair["arm_order"] = order
        for arm in order:
            trials.append({"trial_id": pair["pair_id"] + "-" + arm,
                           "pair_id": pair["pair_id"], "task_id": pair["task_id"],
                           "repeat": pair["repeat"], "arm": arm,
                           "task": copy.deepcopy(pair["task"])})
    value = {
        "schema_version": SCHEMA, "protocol_revision": PROTOCOL_REVISION,
        "profile": "controlled-recovery-pilot", "backend": backend,
        "model": model, "reasoning_effort": "low", "batch_size": 1,
        "endpoint": "https://api.openai.com/v1/responses",
        "task_seed": TASK_SEED, "schedule_seed": SCHEDULE_SEED,
        "randomness_note": "Task and schedule seeds do not seed provider sampling.",
        "tasks": tasks, "pairs": pairs, "trials": trials,
        "limits": copy.deepcopy(LIMITS),
        "preparation_limits": copy.deepcopy(PREPARATION_LIMITS),
        "preparation": {
            "slots": 12, "plan": "One model request per task/repeat before artifact generation.",
            "artifact": "Model-generated by flat execution with public feedback, no reference solution.",
            "qualification": "Public and hidden all-pass; hidden grade is never model feedback.",
            "selection": "One bounded preparation attempt per assigned slot; no reroll, replacement, or outcome-based selection.",
            "failure_status": "NOT_RUN_SOURCE_FAILURE",
            "cost": "Recorded separately once per pair, excluded from both identical repair budgets; report preparation plus repair totals.",
        },
        "treatment": {
            "fixed": "Use unchanged initial hierarchy instructions with public failure feedback.",
            "adaptive": "One instruction-revision request immediately after fork, charged to the same repair budget; rejected revision consumes its request and is retained.",
            "revision_scope": "Only the failed target leaf instruction and revision count may change.",
            "artifact_scope": "Both arms may replace any existing artifact field; locality is measured, not guaranteed by field filtering.",
            "fork": "Identical post-fault artifact, environment, root, initial plan and public feedback; empty repair history in both arms.",
            "hidden_inputs": "Never expose source artifact, preparation history, hidden grading feedback, or reference solution to repair prompts.",
        },
        "execution_policy": {
            "retry_failed_requests": False,
            "retry_preparation": False,
            "replace_missing_pairs": False,
            "audit_each_phase": True,
            "stop_on_transport_error": True,
            "stop_on_audit_failure": True,
            "stop_on_batch_timeout": True,
            "time_semantics": "Batch threshold is checked before each phase; phase threshold before requests and after responses. In-flight work can exceed these thresholds; actual elapsed time is retained. Workflow limit is 260 minutes.",
            "unknown_usage": "null total with known partial usage and counted request attempt",
            "budget_semantics": "Logical token usage includes all completed responses, including invalid or rejected actions; after-response overage fails the phase and is retained. Token thresholds are not a hard billing ceiling because input usage is learned after the response.",
            "maximum_request_attempts": 288,
        },
        "analysis": {
            "primary": "Independently graded recovery conditional on a qualified common checkpoint.",
            "pairing_unit": "Task/repeat checkpoint; repeats share task content and are not independent tasks.",
            "pilot_purpose": "Apparatus, accounting, provenance, ceiling and feasibility; no confirmatory efficacy PASS.",
            "minimum_effect_for_future_study": 0.10,
            "confidence_for_future_study": 0.95,
            "reported_denominators": ["6 assigned tasks", "12 preparation slots", "12 assigned pairs", "24 assigned treatment slots", "qualified complete pairs"],
            "preparation_failures": "Report yield and reasons separately; never classify as a treatment failure or silently remove from the assignment flow.",
            "missing_treatment": "Retain missing/uncertain assigned slots and pair incompleteness; do not impute recovery.",
            "optional_stopping": "None for treatment outcomes; only frozen infrastructure/integrity/time limits stop execution.",
            "scope": "Replanning procedure including diagnosis and instruction revision, not isolated text rewriting or hierarchy-versus-flat effectiveness.",
        },
        "task_non_overlap": task_non_overlap(tasks),
        "source_file_sha256": source_hashes(),
    }
    value["protocol_id"] = digest(value)
    return value


def validate_manifest(manifest: dict, *, current_sources=True) -> None:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA:
        raise ValueError("Invalid controlled recovery manifest")
    body = {key: value for key, value in manifest.items() if key != "protocol_id"}
    if manifest.get("protocol_id") != digest(body):
        raise ValueError("Recovery manifest changed after preparation")
    if current_sources:
        if manifest.get("source_file_sha256") != source_hashes():
            raise ValueError("Recovery source/evaluator changed after preparation")
        expected = build_manifest(manifest["backend"], manifest["model"])
        if expected != manifest:
            raise ValueError("Recovery manifest is not the complete frozen pilot")
