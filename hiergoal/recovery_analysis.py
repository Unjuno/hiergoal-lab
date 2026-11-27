# SPDX-License-Identifier: Apache-2.0
"""Descriptive analysis for a six-task controlled-recovery apparatus pilot."""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

from hiergoal.study_protocol import save


def _distribution(values):
    values = [value for value in values if type(value) in (int, float)]
    return {"n": len(values), "median": statistics.median(values) if values else None,
            "range": [min(values), max(values)] if values else None}


def _counts(rows):
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return counts


def _arm_summary(rows):
    observed = [row for row in rows if row.get("audit") == "PASS" and row["status"] in ("PASS", "FAIL")]
    success = sum(row["status"] == "PASS" for row in observed)
    tokens = [row["input_tokens"] + row["output_tokens"] for row in observed
              if type(row.get("input_tokens")) is int and type(row.get("output_tokens")) is int]
    return {
        "assigned": len(rows), "attempted": sum(row.get("calls") is not None for row in rows),
        "valid_observed": len(observed), "successful": success,
        "recovery_rate_observed": success / len(observed) if observed else None,
        "statuses": _counts(rows),
        "calls": _distribution([row.get("calls") for row in observed]),
        "tokens": _distribution(tokens),
        "wall_seconds": _distribution([row.get("wall_seconds") for row in observed]),
        "replan_attempts": sum(row.get("replan_attempts") or 0 for row in rows),
        "replans_accepted": sum(row.get("replans") or 0 for row in rows),
        "replans_rejected": sum(row.get("replan_rejections") or 0 for row in rows),
        "replans_budget_unapplied": sum(row.get("replan_budget_unapplied") or 0 for row in rows),
        "replans_unresolved": sum(row.get("replan_unresolved") or 0 for row in rows),
        "cost_scope": "Repair phase only; source generation is reported separately.",
    }


def collect(output, manifest=None):
    """Re-audit evidence and write complete, missingness-preserving pilot outputs."""
    from hiergoal.recovery_audit import audit_all, incomplete_phase_usage

    output = Path(output)
    if manifest is None:
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    audit = audit_all(output, manifest)
    def retained_result(folder, specification):
        path = folder / "result.json"
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            if (type(result) is not dict or result.get("status") not in ("PASS", "FAIL", "UNCERTAIN")
                    or "calls" not in result):
                raise ValueError("Malformed retained result")
            return result
        except (OSError, ValueError, TypeError):
            if (folder / "trace.jsonl").exists() or path.exists():
                return incomplete_phase_usage(folder, specification, manifest)
            return None

    preparations, rows = [], []
    for pair in manifest["pairs"]:
        ident = pair["pair_id"]
        row = retained_result(output / "preparations" / ident, pair) or {
            "identifier": ident, "pair_id": ident, "task_id": pair["task_id"],
            "phase": "prepare", "status": "NOT_RUN", "calls": None,
            "input_tokens": None, "output_tokens": None,
            "known_input_tokens": None, "known_output_tokens": None,
        }
        if audit["preparations"][ident]["status"] == "FAIL":
            row = incomplete_phase_usage(output / "preparations" / ident, pair, manifest)
        row["audit"] = audit["preparations"][ident]["status"]
        preparations.append(row)
    preparation_by_id = {row["pair_id"]: row for row in preparations}
    for trial in manifest["trials"]:
        ident, pair_id = trial["trial_id"], trial["pair_id"]
        folder = output / "trials" / ident
        source = preparation_by_id[pair_id]
        source_failed = source["status"] == "FAIL" and source["audit"] == "PASS"
        row = retained_result(folder, trial)
        if row is None:
            row = {"identifier": ident, "trial_id": ident, "pair_id": pair_id,
                   "task_id": trial["task_id"], "phase": "repair", "arm": trial["arm"],
                   "status": "NOT_RUN_SOURCE_FAILURE" if source_failed else "NOT_RUN_BATCH_STOP",
                   "calls": None, "input_tokens": None, "output_tokens": None,
                   "known_input_tokens": None, "known_output_tokens": None,
                   "success": None, "replan_attempts": None, "replans": None,
                   "wall_seconds": None}
        if audit["trials"][ident]["status"] == "FAIL":
            row = incomplete_phase_usage(folder, trial, manifest)
        row["family"], row["repeat"] = trial["task"]["family"], trial["repeat"]
        row["audit"] = audit["trials"][ident]["status"]
        derived = audit["trials"][ident].get("derived") or {}
        for field in ("checkpoint_sha256", "initial_artifact_sha256", "initial_plan_sha256",
                      "root_unchanged", "locality_ok", "unrelated_field_observations",
                      "unrelated_changed_fields", "state_snapshots", "leaf_transitions",
                      "milestone_transitions", "observed_model", "replan_rejections", "replan_unresolved",
                      "replan_budget_unapplied"):
            row[field] = derived.get(field, row.get(field))
        rows.append(row)
    by_pair = {}
    for row in rows:
        by_pair.setdefault(row["pair_id"], {})[row["arm"]] = row
    paired = {"both_recover": 0, "adaptive_only": 0, "fixed_only": 0, "neither": 0,
              "incomplete": 0, "source_failure": 0, "complete_pairs": 0,
              "assigned_pairs": len(manifest["pairs"])}
    paired_by_task = {}
    for ident, arms in by_pair.items():
        if preparation_by_id[ident]["status"] == "FAIL":
            paired["source_failure"] += 1
        valid = all(arm in arms and arms[arm]["audit"] == "PASS" and arms[arm]["status"] in ("PASS", "FAIL")
                    for arm in ("fixed", "adaptive"))
        if not valid:
            paired["incomplete"] += 1
            continue
        fixed, adaptive = arms["fixed"]["status"] == "PASS", arms["adaptive"]["status"] == "PASS"
        category = "both_recover" if fixed and adaptive else "adaptive_only" if adaptive else "fixed_only" if fixed else "neither"
        paired[category] += 1
        paired["complete_pairs"] += 1
        paired_by_task.setdefault(arms["fixed"]["task_id"], []).append(int(adaptive) - int(fixed))
    paired["observed_difference_percentage_points"] = (
        100 * (paired["adaptive_only"] - paired["fixed_only"]) / paired["complete_pairs"]
        if paired["complete_pairs"] else None)
    paired["task_mean_differences"] = {task: statistics.mean(values) for task, values in paired_by_task.items()}
    by_arm = {arm: _arm_summary([row for row in rows if row["arm"] == arm]) for arm in ("fixed", "adaptive")}
    by_family = {family: {arm: _arm_summary([row for row in rows if row["family"] == family and row["arm"] == arm])
                          for arm in ("fixed", "adaptive")}
                 for family in sorted({trial["task"]["family"] for trial in manifest["trials"]})}
    valid_repairs = [row for row in rows if row["audit"] == "PASS"]
    all_ready = (all(row["status"] == "PASS" and row["audit"] == "PASS" for row in preparations)
                 and paired["complete_pairs"] == len(manifest["pairs"]))
    preparation_known = sum((row.get("known_input_tokens") or 0) + (row.get("known_output_tokens") or 0)
                            for row in preparations)
    repair_known = sum((row.get("known_input_tokens") or 0) + (row.get("known_output_tokens") or 0) for row in rows)
    unknown_cost = any(row.get("usage_complete") is False or
                       (row.get("calls") is not None and row.get("input_tokens") is None)
                       for row in [*rows, *preparations])
    host_path = output / "host.json"
    host = json.loads(host_path.read_text(encoding="utf-8")) if host_path.exists() else None
    summary = {
        "schema_version": "hiergoal.controlled_recovery_summary.v1",
        "protocol_id": manifest["protocol_id"], "backend": manifest["backend"], "model": manifest["model"],
        "profile": "controlled_recovery_pilot", "simulated": manifest["backend"] == "oracle",
        "measurement_conditions": {"host": host, "model": manifest["model"],
                                   "observed_models": sorted({row["observed_model"] for row in rows if row.get("observed_model")}),
                                   "reasoning_effort": manifest["reasoning_effort"],
                                   "batch_size": manifest["batch_size"], "limits": manifest["limits"],
                                   "provider_hardware": "Provider-managed and not observable"},
        "unique_tasks": len(manifest["tasks"]), "scheduled_pairs": len(manifest["pairs"]),
        "scheduled_trials": len(manifest["trials"]),
        "preparation": {"assigned": len(preparations), "statuses": _counts(preparations),
                        "verified_source_pass": sum(row["status"] == "PASS" and row["audit"] == "PASS" for row in preparations),
                        "known_tokens": preparation_known,
                        "calls_started": sum(row.get("calls") or 0 for row in preparations),
                        "tokens": _distribution([row["input_tokens"] + row["output_tokens"]
                                                  for row in preparations if row.get("input_tokens") is not None]),
                        "wall_seconds": _distribution([row.get("wall_seconds") for row in preparations])},
        "by_arm": by_arm, "by_family": by_family, "paired": paired,
        "audit_status": audit["status"],
        "apparatus_decision": "FAIL" if audit["status"] == "FAIL" else "PASS" if all_ready and audit["status"] == "PASS" else "UNCERTAIN",
        "efficacy_decision": "UNCERTAIN",
        "efficacy_reason": "A six-task apparatus pilot is not a powered confirmatory effectiveness study.",
        "confidence_interval": None,
        "confidence_interval_reason": "No confirmatory interval from 12 dependent repetitions / 6 tasks; an all-tie bootstrap is not an equivalence proof.",
        "ceiling_observed": by_arm["fixed"]["valid_observed"] == len(manifest["pairs"])
                            and by_arm["fixed"]["successful"] == len(manifest["pairs"]),
        "evidence": {"valid_repair_traces": len(valid_repairs),
                     "source_trace_audits": {status: sum(x["status"] == status for x in audit["preparations"].values())
                                             for status in ("PASS", "FAIL", "NOT_RUN")},
                     "repair_trace_audits": {status: sum(x["status"] == status for x in audit["trials"].values())
                                             for status in ("PASS", "FAIL", "NOT_RUN")},
                     "root_unchanged_trials": sum(row.get("root_unchanged") is True for row in valid_repairs),
                     "locality_preserved_trials": sum(row.get("locality_ok") is True for row in valid_repairs),
                     "locality_violating_trials": sum(row.get("locality_ok") is False for row in valid_repairs),
                     "unrelated_field_observations": sum(row.get("unrelated_field_observations") or 0 for row in valid_repairs),
                     "state_snapshots": sum(row.get("state_snapshots") or 0 for row in valid_repairs),
                     "leaf_transitions": sum(row.get("leaf_transitions") or 0 for row in valid_repairs),
                     "milestone_transitions": sum(row.get("milestone_transitions") or 0 for row in valid_repairs)},
        "cost": {"known_tokens": preparation_known + repair_known, "preparation_known_tokens": preparation_known,
                 "repair_known_tokens": repair_known, "complete_usage": not unknown_cost,
                 "calls_started": sum(row.get("calls") or 0 for row in [*preparations, *rows]),
                 "billing_dollars": None,
                 "note": "Observed tokens and requests; not an invoice. Preparation is charged once, separately from repair budgets."},
        "limitations": ["Task parameters are unused, but task families and graders are reused.",
                        "The estimand is repair conditional on successful blinded model-generated preparation.",
                        "Adaptive adds one diagnosis-plus-instruction revision; the components are not separately identified.",
                        "No scale/depth generalization, trigger specificity, broad subtree restructuring, or Hermes integration is tested.",
                        "Repeated gate/field observations are not independent tasks.",
                        "A valid hash chain and semantic replay do not constitute provider-signed proof of API provenance."],
    }
    save(output / "audits.json", audit)
    save(output / "results.json", rows)
    save(output / "preparations.json", preparations)
    save(output / "summary.json", summary)
    fields = ["identifier", "pair_id", "task_id", "family", "repeat", "arm", "status", "audit", "success",
              "calls", "input_tokens", "output_tokens", "known_input_tokens", "known_output_tokens", "wall_seconds",
              "replan_attempts", "replans", "replan_rejections", "replan_budget_unapplied", "replan_unresolved", "rejected_actions", "patch_actions", "checkpoint_sha256",
              "initial_artifact_sha256", "initial_plan_sha256", "root_unchanged", "locality_ok",
              "unrelated_field_observations", "final_artifact_sha256", "trace_final_sha256", "diagnostic"]
    with (output / "trials.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    (output / "summary.md").write_text(_markdown(summary), encoding="utf-8")
    return summary


def _markdown(summary):
    def measured(value):
        return "NA" if value["median"] is None else f"{value['median']} [{value['range'][0]}, {value['range'][1]}]"

    label = "OFFLINE ORACLE — apparatus only" if summary["simulated"] else "LIVE API PILOT"
    lines = ["# Controlled recovery pilot", "", f"**{label}**", "",
             f"Protocol: `{summary['protocol_id']}`", "",
             f"Apparatus: **{summary['apparatus_decision']}**. Effectiveness: **UNCERTAIN**.", "",
             f"{summary['unique_tasks']} distinct tasks; {summary['scheduled_pairs']} matched pair slots; "
             f"{summary['scheduled_trials']} repair slots.", "",
             f"Verified preparation yield: {summary['preparation']['verified_source_pass']}/{summary['preparation']['assigned']}.", "",
             "Measurements below are medians [minimum, maximum] over valid observed repair trials.", "",
             "| Arm | Assigned | Valid observed | Recovered | Recovery rate | Calls | Tokens | Wall seconds |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for arm, row in summary["by_arm"].items():
        rate = f"{100 * row['recovery_rate_observed']:.1f}%" if row["recovery_rate_observed"] is not None else "NA"
        lines.append(f"| {arm} | {row['assigned']} | {row['valid_observed']} | {row['successful']} | {rate} | "
                     f"{measured(row['calls'])} | {measured(row['tokens'])} | {measured(row['wall_seconds'])} |")
    conditions = summary["measurement_conditions"]
    host = conditions["host"] or {}
    lines.extend(["", f"Model: {conditions['model']}; reasoning: {conditions['reasoning_effort']}; "
                  f"batch: {conditions['batch_size']}. Controller host: {host.get('cpu', 'unrecorded')}; "
                  f"observed MHz range: {host.get('cpu_clock_mhz_observed_range', 'unrecorded')}; "
                  f"Python: {host.get('python', 'unrecorded')}. Model hardware is provider-managed and unobservable."])
    paired = summary["paired"]
    lines.extend(["", "## Matched outcomes", "",
                  f"Both recover: {paired['both_recover']}; adaptive only: {paired['adaptive_only']}; "
                  f"fixed only: {paired['fixed_only']}; neither: {paired['neither']}; incomplete: {paired['incomplete']}.", "",
                  f"Observed adaptive minus fixed: {paired['observed_difference_percentage_points']} percentage points.", "",
                  "No confirmatory confidence interval or equivalence claim is made from this pilot.", "",
                  "## Accounting and integrity", "",
                  f"Known source-generation tokens: {summary['cost']['preparation_known_tokens']}; "
                  f"known repair tokens: {summary['cost']['repair_known_tokens']}; "
                  f"requests started: {summary['cost']['calls_started']}.", "",
                  f"Audit: {summary['audit_status']}; root preserved in {summary['evidence']['root_unchanged_trials']} audited repairs; "
                  f"artifact locality violations in {summary['evidence']['locality_violating_trials']} audited repairs.", "",
                  f"Ceiling observed in fixed arm: {summary['ceiling_observed']}.", "",
                  "## Limits", ""])
    lines.extend("- " + item for item in summary["limitations"])
    return "\n".join(lines) + "\n"
