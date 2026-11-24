# SPDX-License-Identifier: Apache-2.0
"""Frozen, engine-independent method experiment; no inference on import."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "hiergoal.study.v1"
ARMS = ("flat_retry", "hierarchy_fixed", "hierarchy_adaptive")
FAMILIES = ("code_repair", "data_transform", "scheduling")
CONDITIONS = ("normal", "fault")
ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "hiergoal/study_protocol.py", "hiergoal/study_tasks.py", "hiergoal/study_api.py",
    "hiergoal/study.py", "hiergoal/study_analysis.py",
    "docs/method_study_ja.md", ".github/workflows/method-study.yml",
)
LIMITS = {
    "max_calls": 12, "max_replans": 3, "max_output_tokens": 2048,
    "max_total_tokens": 64000, "max_prompt_bytes": 48000,
    "request_timeout_seconds": 90, "trial_timeout_seconds": 1200,
    "batch_timeout_seconds": 18000,
}


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                    allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def source_hashes() -> dict:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in SOURCE_FILES}


def build_manifest(profile="pilot", backend="openai", model="gpt-6-luna",
                   schedule_seed=1729) -> dict:
    from hiergoal.study_tasks import make_task
    if profile not in ("pilot", "study") or backend not in ("openai", "oracle", "scripted"):
        raise ValueError("Unknown study profile/backend")
    if not isinstance(model, str) or not model.strip() or len(model) > 100:
        raise ValueError("Invalid model identifier")
    split, instances, repeats = (("dev", 1, 1) if profile == "pilot"
                                else ("heldout", 4, 3))
    tasks, blocks = {}, []
    for family in FAMILIES:
        for instance in range(instances):
            task = make_task(family, instance, split=split, seed=1729)
            tasks[task.task_id] = {
                "task_id": task.task_id, "family": family, "instance": instance,
                "split": split, "seed": 1729, "root_sha256": digest(task.root_contract),
                "initial_public_spec_sha256": digest(task.public_spec()),
            }
            for repeat in range(1, repeats + 1):
                for condition in CONDITIONS:
                    blocks.append({**tasks[task.task_id], "repeat": repeat,
                                   "condition": condition,
                                   "block_id": f"{task.task_id}-{condition}-r{repeat}"})
    rng = random.Random(schedule_seed)
    rng.shuffle(blocks)
    trials = []
    for block in blocks:
        arms = list(ARMS)
        rng.shuffle(arms)
        for arm in arms:
            trials.append({**block, "arm": arm,
                           "trial_id": f"{block['block_id']}-{arm}"})
    manifest = {
        "schema_version": SCHEMA, "profile": profile, "backend": backend,
        "model": model, "reasoning_effort": "low", "endpoint": "https://api.openai.com/v1/responses",
        "schedule_seed": schedule_seed, "task_seed": 1729,
        "randomness_note": "Schedule/task seeds are not model sampling seeds.",
        "limits": copy.deepcopy(LIMITS), "tasks": list(tasks.values()), "trials": trials,
        "analysis": {"minimum_effect": 0.10, "confidence": 0.95,
                     "bootstrap_samples": 5000, "seed": 20261125},
        "planning": "Shared once per task/repeat, blinded to condition; logically charged to each hierarchical arm.",
        "source_file_sha256": source_hashes(),
    }
    manifest["protocol_id"] = digest(manifest)
    return manifest


def validate_manifest(manifest: dict, *, current_sources=True) -> None:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA:
        raise ValueError("Invalid study manifest")
    payload = {k: v for k, v in manifest.items() if k != "protocol_id"}
    if manifest.get("protocol_id") != digest(payload):
        raise ValueError("Manifest changed after preparation")
    if current_sources and manifest.get("source_file_sha256") != source_hashes():
        raise ValueError("Source/evaluator/protocol changed after preparation; prepare a new study")
    # The generator is the only accepted protocol in this version. This also checks
    # missing cells, duplicated trials, modified budgets, and task fingerprints.
    if current_sources:
        expected = build_manifest(manifest["profile"], manifest["backend"],
                                  manifest["model"], manifest["schedule_seed"])
        if expected != manifest:
            raise ValueError("Unsupported or incomplete study schedule")


def host_metadata() -> dict:
    cpu, mhz, memory_bytes, dirty = None, [], None, None
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
            if line.startswith("cpu MHz"):
                mhz.append(float(line.split(":", 1)[1]))
    except (OSError, ValueError):
        pass
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                memory_bytes = int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, timeout=5).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                    capture_output=True, text=True, timeout=5).stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        commit = None
    return {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": commit, "working_tree_dirty": dirty, "python": sys.version.split()[0],
            "platform": platform.platform(), "cpu": cpu,
            "cpu_clock_mhz_observed_range": [min(mhz), max(mhz)] if mhz else None,
            "logical_cpus": os.cpu_count(), "memory_bytes": memory_bytes,
            "batch_size": 1, "model_hardware": "Provider-managed; not observable"}
