# SPDX-License-Identifier: Apache-2.0
"""Small, reproducible LIVE benchmark of the Issue #156054 research prototype.

A case means a fresh workspace + a real Hermes goal-planning sequence, unless
the operator explicitly passes a mock Hermes binary in an offline test.
No inference is sent without --run. Luna requires two independent consent flags.
No baseline is provided; this estimates observed functionality, not causality.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import statistics
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from hiergoal.cases import CASE_IDS, CASE_DESCRIPTION
from hiergoal.report import compile_report

ROOT = Path(__file__).resolve().parents[1]


def make_schedule(case_ids: list[str], repetitions: int, seed: int) -> list[dict]:
    if not case_ids or len(set(case_ids)) != len(case_ids) or any(c not in CASE_IDS for c in case_ids):
        raise ValueError("Unique known cases are required")
    if repetitions < 1 or repetitions > 5:
        raise ValueError("Repetitions must be 1..5")
    schedule = [
        {"case_id": case, "repetition": rep}
        for rep in range(1, repetitions + 1)
        for case in case_ids
    ]
    random.Random(seed).shuffle(schedule)
    for index, task in enumerate(schedule, 1):
        task["index"] = index
    return schedule


def _load_json(path: Path) -> dict | None:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def summarize_batch(batch_dir: Path) -> dict:
    batch = _load_json(batch_dir / "schedule.json")
    if not batch or not isinstance(batch.get("tasks"), list):
        raise ValueError("Invalid/missing batch schedule")
    entries = []
    for task in batch["tasks"]:
        i, case_id, repetition = task["index"], task["case_id"], task["repetition"]
        output_dir = batch_dir / "individual" / ("task-%02d" % i)
        candidates = list(output_dir.glob("hiergoal-*/records.json")) if output_dir.exists() else []
        if len(candidates) != 1:
            attempted = task.get("run_state") in ("STARTED", "RETURNED")
            entries.append({
                "index": i, "case_id": case_id, "repetition": repetition,
                "status": "UNCERTAIN" if attempted or len(candidates) > 1 else "NOT_RUN",
                "model_calls": 0, "tool_calls": None, "replans": None,
                "subgoals_total": None, "subgoals_completed_status": None,
                "milestones_total": None, "milestones_verified": None,
                "preverified_leaves": None,
                "elapsed_hermes_seconds": None, "estimated_visible_usd": None,
                "token_usage_measured": False, "verified_evidence": False,
            })
            continue
        run = candidates[0].parent
        rec = _load_json(run / "records.json")
        if not rec or rec.get("case_id") != case_id or rec.get("backend") != batch.get("backend"):
            status = "UNCERTAIN"
            rep = None
        else:
            try:
                rep = compile_report(run)
                status = rep["verified_report_outcome"]
            except (ValueError, OSError, TypeError, KeyError):
                rep, status = None, "UNCERTAIN"
        calls = rec.get("calls", []) if rec and isinstance(rec.get("calls"), list) else []
        seconds = sum(float(c.get("elapsed_seconds", 0))
                      for c in calls if isinstance(c.get("elapsed_seconds"), (int, float)))
        tools = sum(int(c.get("tool_calls", 0))
                    for c in calls if isinstance(c.get("tool_calls"), int))
        state = _load_json(run / "state.json")
        leaves = state.get("leaves") if isinstance(state, dict) else None
        milestones = state.get("milestones") if isinstance(state, dict) else None
        active_leaves = [leaf for leaf in leaves.values() if isinstance(leaf, dict)
                         and leaf.get("status") != "superseded"] if isinstance(leaves, dict) else []
        milestone_list = [m for m in milestones if isinstance(m, dict)] if isinstance(milestones, list) else []
        entries.append({
            "index": i, "case_id": case_id, "repetition": repetition,
            "status": status,
            "model_calls": len(calls),
            "tool_calls": tools,
            "replans": state.get("replans") if isinstance(state, dict) else None,
            "subgoals_total": len(active_leaves) if isinstance(leaves, dict) else None,
            "subgoals_completed_status": sum(
                leaf.get("status") == "completed" for leaf in active_leaves
            ) if isinstance(leaves, dict) else None,
            "milestones_total": len(milestone_list) if isinstance(milestones, list) else None,
            "milestones_verified": sum(
                m.get("status") == "completed"
                and isinstance(m.get("verification"), dict)
                and m["verification"].get("passed") is True
                for m in milestone_list
            ) if isinstance(milestones, list) else None,
            "preverified_leaves": sum(
                any(isinstance(event, dict) and event.get("action") == "preverified"
                    for event in leaf.get("history", []))
                for leaf in active_leaves
            ) if isinstance(leaves, dict) else None,
            "elapsed_hermes_seconds": round(seconds, 3),
            "estimated_visible_usd": rec.get("estimated_visible_usd") if rec else None,
            "token_usage_measured": bool(calls) and all(
                c.get("token_usage_measured") is True for c in calls
            ),
            "verified_evidence": status == "PASS" and rep is not None
                                 and not rep.get("evidence_issues"),
        })
    observed = [x for x in entries if x["status"] in ("PASS", "FAIL", "UNCERTAIN")]
    passed = [x for x in observed if x["status"] == "PASS"]
    seconds = [x["elapsed_hermes_seconds"] for x in observed
               if isinstance(x["elapsed_hermes_seconds"], (int, float))]
    tool_counts = [x["tool_calls"] for x in observed if isinstance(x["tool_calls"], int)]
    spend = [x["estimated_visible_usd"] for x in observed
             if isinstance(x["estimated_visible_usd"], (int, float))]
    original_design = (
        len(entries) == 8 and batch.get("repetitions") == 2
        and sorted((row["case_id"], row["repetition"]) for row in entries)
        == sorted((case_id, repetition) for case_id in CASE_IDS
                  for repetition in (1, 2))
    )
    if not original_design:
        engineering_target = "NOT_APPLICABLE"
    elif len(observed) != 8 or any(row["status"] == "UNCERTAIN" for row in observed):
        engineering_target = "UNCERTAIN"
    elif len(passed) >= 6 and all(row["verified_evidence"] for row in passed):
        engineering_target = "PASS"
    else:
        engineering_target = "FAIL"
    return {
        "schema_version": "1.0",
        "experiment": "Hermes hierarchical goals, 4 defect profiles, no comparator",
        "benchmark_id": batch.get("batch_id"),
        "backend": batch.get("backend"),
        "model": batch.get("model"),
        "seed_for_task_order_only": batch.get("seed"),
        "run_plan": {"distinct_cases": len({x["case_id"] for x in entries}),
                     "repetitions": batch.get("repetitions"), "scheduled": len(entries)},
        "executed": len(observed),
        "not_run": sum(x["status"] == "NOT_RUN" for x in entries),
        "pass": len(passed),
        "fail": sum(x["status"] == "FAIL" for x in observed),
        "uncertain": sum(x["status"] == "UNCERTAIN" for x in observed),
        "observed_pass_fraction": (len(passed) / len(observed) if observed else None),
        "engineering_target": engineering_target,
        "engineering_target_definition": ("For preregistered 4 cases x 2 repeats: "
                                          "at least 6 evidence-verified passes, "
                                          "all 8 classifiable; not a statistical claim."),
        "median_hermes_seconds": (statistics.median(seconds) if seconds else None),
        "range_hermes_seconds": ([min(seconds), max(seconds)] if seconds else None),
        "median_tool_calls": (statistics.median(tool_counts) if tool_counts else None),
        "observed_replans": sum(x["replans"] for x in observed
                                if isinstance(x["replans"], int)),
        "verified_pass_after_replan": sum(
            x["status"] == "PASS" and isinstance(x["replans"], int)
            and x["replans"] > 0 for x in observed
        ),
        "observed_completed_subgoals": sum(x["subgoals_completed_status"] for x in observed
                                           if isinstance(x["subgoals_completed_status"], int)),
        "observed_total_subgoals": sum(x["subgoals_total"] for x in observed
                                       if isinstance(x["subgoals_total"], int)),
        "observed_verified_milestones": sum(x["milestones_verified"] for x in observed
                                            if isinstance(x["milestones_verified"], int)),
        "estimated_visible_total_usd": (round(sum(spend), 8)
            if len(spend) == len(observed) and observed else None),
        "token_telemetry_complete": bool(observed) and all(
            x["token_usage_measured"] for x in observed
        ),
        "per_case": entries,
        "interpretation": (
            "Preliminary descriptive single-method benchmark: 4 deterministic "
            "defect profiles. No flat-goal comparator, no statistical superiority "
            "claim, no inference randomness seed guarantee. Billing estimate is "
            "not a receipt or a hard cap. Raw traces are not included."
        ),
    }


def store(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def start_batch(args: argparse.Namespace, tasks: list[dict]) -> int:
    if args.backend == "luna" and not args.approve_paid_api:
        raise ValueError("Luna is paid; explicit --approve-paid-api is required")
    if not args.ack_unsandboxed:
        raise ValueError("Real execution requires --ack-unsandboxed and an isolated OS environment")
    if not shutil.which(args.hermes):
        raise ValueError("Hermes CLI not found on PATH")
    batch_dir = (args.output / (
        "benchmark-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-" + uuid.uuid4().hex[:6]
    )).resolve()
    batch_dir.mkdir(parents=True, exist_ok=False)
    route_model = "gpt-6-luna" if args.backend == "luna" else "opencode/glm-5.3-flash-free"
    metadata = {
        "batch_id": batch_dir.name, "backend": args.backend,
        "model": route_model, "seed": args.seed,
        "repetitions": args.repetitions, "tasks": tasks,
        "total_soft_budget_usd": args.total_soft_budget_usd,
        "per_case_soft_budget_usd": args.per_case_soft_budget_usd,
        "status": "STARTED",
    }
    store(batch_dir / "schedule.json", metadata)
    visible_spend = 0.0
    halt_reason = None

    for task in tasks:
        case_id, i = task["case_id"], task["index"]
        if args.backend == "luna" and visible_spend >= args.total_soft_budget_usd:
            halt_reason = "Estimated aggregate spending guard reached before next task"
            break
        remaining = max(0.000001, args.total_soft_budget_usd - visible_spend)
        limit = min(args.per_case_soft_budget_usd, remaining)
        target_dir = batch_dir / "individual" / ("task-%02d" % i)
        command = [
            sys.executable, "-m", "hiergoal.controller",
            "--hermes", args.hermes, "--backend", args.backend,
            "--case", case_id, "--output", str(target_dir),
            "--max-calls", str(args.max_calls),
            "--max-turns", str(args.max_turns),
            "--max-replans", str(args.max_replans),
            "--timeout-seconds", str(args.timeout_seconds),
            "--pilot-budget-usd", str(limit),
            "--ack-unsandboxed",
        ]
        if args.backend == "luna":
            command.append("--approve-paid-api")
        task["run_state"] = "STARTED"
        store(batch_dir / "schedule.json", metadata)
        target_dir.mkdir(parents=True, exist_ok=True)
        with (target_dir / "controller.stdout.txt").open("w") as out, \
             (target_dir / "controller.stderr.txt").open("w") as err:
            proc = subprocess.run(command, cwd=ROOT, stdout=out, stderr=err)
        task["controller_exit_code"] = proc.returncode
        task["run_state"] = "RETURNED"
        store(batch_dir / "schedule.json", metadata)

        snapshot = summarize_batch(batch_dir)
        store(batch_dir / "summary.json", snapshot)
        row = next(x for x in snapshot["per_case"] if x["index"] == i)
        charge = row["estimated_visible_usd"]
        if args.backend == "luna":
            if not isinstance(charge, (int, float)) or not row["token_usage_measured"]:
                halt_reason = "Missing token-cost telemetry; refusing further paid tasks"
                break
            visible_spend = round(visible_spend + charge, 8)
        # A nonzero exit can be a genuine task FAIL, or infrastructure failure.
        # Stop on any UNCERTAIN to avoid unintentionally burning the full budget.
        if row["status"] not in ("PASS", "FAIL"):
            halt_reason = "Last task unverified; review the raw run before continuing"
            break

    metadata["status"] = "HALTED" if halt_reason else "FINISHED"
    metadata["halt_reason"] = halt_reason
    metadata["estimated_visible_spend_usd"] = visible_spend if args.backend == "luna" else None
    store(batch_dir / "schedule.json", metadata)
    summary = summarize_batch(batch_dir)
    store(batch_dir / "summary.json", summary)
    print(json.dumps({
        "batch_dir": str(batch_dir),
        "state": metadata["status"],
        "halt_reason": halt_reason,
        "scheduled": summary["run_plan"]["scheduled"],
        "executed": summary["executed"],
        "pass": summary["pass"], "fail": summary["fail"],
        "uncertain": summary["uncertain"],
        "estimated_visible_spend_usd": metadata["estimated_visible_spend_usd"],
    }, ensure_ascii=False, indent=2))
    return 1 if halt_reason else 0


def main() -> None:
    cli = argparse.ArgumentParser(description="Single-method empirical Hermes benchmark; no inference by default")
    cli.add_argument("--run", action="store_true", help="Start the actual batch")
    cli.add_argument("--summarize", type=Path, help="Only analyze existing local batch; no calls")
    cli.add_argument("--backend", choices=["luna", "free"], default="luna")
    cli.add_argument("--cases", default=",".join(CASE_IDS), help="Comma-separated case IDs")
    cli.add_argument("--repetitions", type=int, default=2)
    cli.add_argument("--seed", type=int, default=1729, help="Task order only, not model sampling")
    cli.add_argument("--hermes", default="hermes")
    cli.add_argument("--output", type=Path, default=ROOT / "runs" / "benchmarks")
    cli.add_argument("--approve-paid-api", action="store_true")
    cli.add_argument("--ack-unsandboxed", action="store_true")
    cli.add_argument("--total-soft-budget-usd", type=float, default=6.0)
    cli.add_argument("--per-case-soft-budget-usd", type=float, default=1.5)
    cli.add_argument("--max-calls", type=int, default=12)
    cli.add_argument("--max-turns", type=int, default=18)
    cli.add_argument("--max-replans", type=int, default=2)
    cli.add_argument("--timeout-seconds", type=int, default=600)
    args = cli.parse_args()
    if args.summarize:
        result = summarize_batch(args.summarize)
        store(args.summarize / "summary.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    cases = [value.strip() for value in args.cases.split(",") if value.strip()]
    try:
        tasks = make_schedule(cases, args.repetitions, args.seed)
        if (not math.isfinite(args.total_soft_budget_usd)
                or not math.isfinite(args.per_case_soft_budget_usd)
                or args.total_soft_budget_usd <= 0
                or args.per_case_soft_budget_usd <= 0
                or args.max_calls < 1 or args.max_turns < 1
                or args.max_replans < 0 or args.timeout_seconds < 15):
            raise ValueError("Invalid safety/resource bounds")
        if not args.run:
            print(json.dumps({
                "mode": "PLAN_ONLY; ZERO model calls",
                "backend": args.backend,
                "repetitions": args.repetitions,
                "cases": cases,
                "scheduled": len(tasks),
                "seed_for_task_order_only": args.seed,
                "tasks": tasks,
                "notice": "Use --run and explicit consent to start the paid batch. "
                          "USD estimates are not billing limits.",
            }, ensure_ascii=False, indent=2))
            return
        exit_code = start_batch(args, tasks)
        raise SystemExit(exit_code)
    except ValueError as exc:
        cli.error(str(exc))


if __name__ == "__main__":
    main()
