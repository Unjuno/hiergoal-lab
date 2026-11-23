# SPDX-License-Identifier: Apache-2.0
"""Export allowlisted CI evidence; never copy prompts, traces, stderr or homes.

This module makes no inference requests. The live process must have stopped
before collection. Missing or unreadable evidence is reported as unknown.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import re
import stat
import statistics
from pathlib import Path

from hiergoal.benchmark import summarize_batch
from hiergoal.cases import CASE_IDS
from hiergoal.report import compile_report

OUTCOMES = {"PASS", "FAIL", "UNCERTAIN", "NOT_RUN"}
STATE_FIELDS = (
    "mode", "status", "diagnostic_code", "cli_compatible", "hermes_commit",
    "soft_budget_usd", "started_at", "finished_at", "elapsed_seconds",
    "hermes_version", "python_version", "host_os", "host_architecture",
    "runner_image", "git_commit", "host_processor", "cpu_logical_count",
    "cpu_observed_mhz_range", "memory_total_bytes", "runner_os",
)
LIMIT_FIELDS = (
    "max_calls", "max_turns", "max_replans", "call_timeout_seconds",
    "batch_timeout_seconds", "seed", "per_case_soft_budget_usd",
    "hermes_execution_timeout_seconds", "smoke_execution_timeout_seconds",
)
SMOKE_FIELDS = (
    "status", "reason_code", "tokens_input", "tokens_output", "elapsed_seconds",
    "estimated_visible_usd", "terminal_result_seen", "hermes_exit_code", "init_model",
)
REPORT_FIELDS = (
    "schema_version", "study", "source", "experiment", "case_id", "provider",
    "model", "profile", "declared_outcome", "verified_report_outcome",
    "evidence_issues", "milestone_count", "parent_acceptance_evidence_verified",
    "leaf_acceptance_evidence_verified", "acceptance_gate_coverage_verified",
    "leaf_count_including_superseded", "terminal_leaves_completed", "replans",
    "hermes_calls_claimed", "hermes_calls_with_readable_streams",
    "observed_tool_calls", "elapsed_hermes_seconds",
    "token_usage_measured_on_all_calls", "estimated_visible_usd",
)
PROVENANCE_FIELDS = (
    "protocol_id", "git_commit", "timestamp_utc", "host_os",
    "host_architecture", "python_version",
)
ATTEMPT_FIELDS = (
    "index", "case_id", "repetition", "status", "model_calls", "tool_calls",
    "replans", "subgoals_total", "subgoals_completed_status", "milestones_total",
    "milestones_verified", "preverified_leaves", "elapsed_hermes_seconds",
    "estimated_visible_usd", "token_usage_measured", "verified_evidence",
    "tokens_input", "tokens_output",
)
SUMMARY_FIELDS = (
    "schema_version", "experiment", "benchmark_id", "backend", "model",
    "seed_for_task_order_only", "executed", "not_run", "pass", "fail",
    "uncertain", "observed_pass_fraction", "engineering_target",
    "engineering_target_definition", "median_hermes_seconds", "range_hermes_seconds",
    "median_tool_calls", "observed_replans", "verified_pass_after_replan",
    "observed_completed_subgoals", "observed_total_subgoals",
    "observed_verified_milestones", "estimated_visible_total_usd",
    "token_telemetry_complete",
)
CSV_FIELDS = (
    "index", "case_id", "repetition", "status", "hermes_invocations",
    "tokens_input", "tokens_output", "tool_calls", "replans",
    "elapsed_hermes_seconds", "estimated_visible_usd", "verified_evidence",
)
PARSE_ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError)
REMEDIATION = {
    "MISSING_OPENAI_API_KEY": "Add OPENAI_API_KEY to this repository's GitHub Actions secrets, then run the API smoke mode.",
    "PAID_OPT_IN_REQUIRED": "Select the paid API opt-in when dispatching a live experiment.",
    "HERMES_CLI_INCOMPATIBLE": "Review the pinned Hermes installation and required chat flags; rerun check mode before live inference.",
    "CI_RUNNER_ERROR": "Review the installation and runner steps; use check mode to isolate local setup from API access.",
    "HERMES_OR_API_ERROR": "Check the API project's model access, key and quota, then rerun smoke mode. Raw API errors are not published.",
    "NON_DIRECT_API_ENDPOINT": "Use the direct https://api.openai.com/v1 endpoint for this experiment.",
    "MISSING_USAGE_TELEMETRY": "Review the pinned Hermes stream format and token usage collection before another paid run.",
    "BATCH_HALTED_REVIEW_EVIDENCE": "Inspect the per-attempt reports. Retain failed and uncertain attempts when interpreting the experiment.",
    "BATCH_WALL_TIME_LIMIT": "The batch reached its wall-time limit; unfinished attempts remain unclassified.",
}


def _number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _counter(value) -> bool:
    return type(value) is int and value >= 0


def _outcome(value, default="UNCERTAIN") -> str:
    return value if isinstance(value, str) and value in OUTCOMES else default


def _scalar(value):
    if value is None or isinstance(value, (str, bool)) or _number(value):
        return _redact(value)[:512] if isinstance(value, str) else value
    if isinstance(value, list) and len(value) <= 64:
        return [_scalar(item) for item in value if not isinstance(item, (dict, list))]
    return None


def _select(value: dict, names: tuple) -> dict:
    return {name: _scalar(value[name]) for name in names if name in value}


def _no_symlinks(path: Path) -> None:
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError("SYMLINK_REFUSED")


def _object(path: Path) -> dict | None:
    _no_symlinks(path)
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("INVALID_INPUT_FILE")
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("EXPECTED_JSON_OBJECT")
    return value


def _check_evidence_tree(directory: Path) -> None:
    """The legacy readers may open evidence names; validate their inputs first."""
    _no_symlinks(directory)
    for base, dirs, files in os.walk(directory, followlinks=False):
        # Neither the evaluator nor the exporter reads the generated workspace.
        dirs[:] = [name for name in dirs if name != "workspace"]
        for name in [*dirs, *files]:
            path = Path(base) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not (
                stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)
            ):
                raise ValueError("UNSAFE_EVIDENCE_PATH")
            if stat.S_ISREG(info.st_mode) and info.st_size > 64 * 1024 * 1024:
                raise ValueError("OVERSIZED_EVIDENCE_FILE")
        if "state.json" in files:
            try:
                state = _object(Path(base) / "state.json") or {}
            except PARSE_ERRORS:
                # The per-attempt fallback still exports records-only diagnostics.
                continue
            milestones, leaves = state.get("milestones", []), state.get("leaves", {})
            if not isinstance(milestones, list) or not isinstance(leaves, dict):
                raise ValueError("INVALID_STATE_SHAPE")
            for node in [*milestones, *leaves.values()]:
                if not isinstance(node, dict) or not re.fullmatch(
                    r"[A-Za-z0-9_-]{1,80}", str(node.get("id", ""))
                ):
                    raise ValueError("INVALID_EVIDENCE_NODE_ID")


def _redact(value):
    secrets = sorted({v for k, v in os.environ.items() if len(v) >= 8 and
                      re.search(r"(?:API_KEY|TOKEN|SECRET|PASSWORD)$", k)},
                     key=len, reverse=True)

    def clean(text: str) -> str:
        for secret in secrets:
            text = text.replace(secret, "[REDACTED]")
        text = re.sub(r"\b(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{8,}|"
                      r"gh[pousr]_[A-Za-z0-9_]{10,}|github_pat_[A-Za-z0-9_]{10,})",
                      "[REDACTED]", text)
        text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}",
                      "Bearer [REDACTED]", text)
        return text

    def visit(item):
        if isinstance(item, str):
            return clean(item)
        if isinstance(item, dict):
            return {clean(str(k)): visit(v) for k, v in item.items()}
        if isinstance(item, list):
            return [visit(v) for v in item]
        return item
    return visit(value)


def _write(path: Path, content: str, *, append: bool = False) -> None:
    _no_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags, 0o600), "w", encoding="utf-8") as stream:
        stream.write(_redact(content))


def _write_json(path: Path, data: dict) -> None:
    _write(path, json.dumps(_redact(data), indent=2, ensure_ascii=False,
                           allow_nan=False) + "\n")


def _call_metrics(records: dict | None) -> dict:
    calls = records.get("calls") if records else None
    valid = isinstance(calls, list) and all(isinstance(call, dict) for call in calls)
    count = len(calls) if valid else None
    known = bool(valid and calls)
    measured = known and all(call.get("token_usage_measured") is True
                             and _counter(call.get("tokens_input"))
                             and _counter(call.get("tokens_output")) for call in calls)
    metrics = {"model_calls": count, "token_usage_measured": bool(measured)}
    for source, target in (("tool_calls", "tool_calls"),
                           ("elapsed_seconds", "elapsed_hermes_seconds"),
                           ("tokens_input", "tokens_input"),
                           ("tokens_output", "tokens_output")):
        validator = _number if source == "elapsed_seconds" else _counter
        complete = known and all(validator(call.get(source)) for call in calls)
        if source.startswith("tokens_"):
            complete = complete and measured
        metrics[target] = round(sum(call[source] for call in calls), 8) if complete else None
    charge = records.get("estimated_visible_usd") if records else None
    metrics["estimated_visible_usd"] = charge if measured and _number(charge) else None
    return metrics


def _collect_batch(batch: Path) -> tuple[dict, list[tuple[int, dict]], list[str]]:
    diagnostics, reports = [], []
    _check_evidence_tree(batch)
    schedule = _object(batch / "schedule.json")
    tasks = schedule.get("tasks") if schedule else None
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 20:
        raise ValueError("INVALID_SCHEDULE")
    ids = set()
    for task in tasks:
        if (not isinstance(task, dict) or type(task.get("index")) is not int
                or not 1 <= task["index"] <= 20 or task["index"] in ids
                or task.get("case_id") not in CASE_IDS
                or type(task.get("repetition")) is not int
                or not 1 <= task["repetition"] <= 5):
            raise ValueError("INVALID_SCHEDULE_TASK")
        ids.add(task["index"])
    try:
        original = summarize_batch(batch)
    except PARSE_ERRORS:
        original = {"engineering_target": "UNCERTAIN", "per_case": []}
        diagnostics.append("BATCH_SUMMARY_UNREADABLE")
    summary = _select(original, SUMMARY_FIELDS)
    summary["run_plan"] = _select(original.get("run_plan", {}),
                                   ("distinct_cases", "repetitions", "scheduled"))
    summary["run_plan"].update({"scheduled": len(tasks),
                                "distinct_cases": len({t["case_id"] for t in tasks})})
    prior = {row["index"]: row for row in original.get("per_case", [])}
    entries = []
    for task in tasks:
        index = task["index"]
        attempted = task.get("run_state") in ("STARTED", "RETURNED")
        candidates = list((batch / "individual" / f"task-{index:02d}").glob("hiergoal-*/records.json"))
        row = _select(prior.get(index, {}), ATTEMPT_FIELDS)
        row.update({"index": index, "case_id": task["case_id"], "repetition": task["repetition"]})
        records = None
        if len(candidates) == 1:
            try:
                records = _object(candidates[0])
                compiled = compile_report(candidates[0].parent)
                report = _select(compiled, REPORT_FIELDS)
                report["provenance"] = _select(compiled.get("provenance", {}), PROVENANCE_FIELDS)
                report["calls"] = [_select(call, ("index", "role", "terminal_result_seen",
                    "recorded_tool_calls", "hermes_exit_code", "elapsed_seconds",
                    "token_usage_measured", "nested_todo_observed"))
                    for call in compiled.get("calls", []) if isinstance(call, dict)]
                report["evidence_fingerprints"] = [_select(item, ("name", "sha256", "size_bytes"))
                    for item in compiled.get("evidence_fingerprints", []) if isinstance(item, dict)]
                if not records or records.get("case_id") != task["case_id"] or records.get("backend") != schedule.get("backend"):
                    raise ValueError("RECORD_ROUTE_MISMATCH")
                row["status"] = report["verified_report_outcome"]
            except PARSE_ERRORS:
                report = {"declared_outcome": _outcome(records.get("outcome")) if records else "UNCERTAIN",
                          "verified_report_outcome": "UNCERTAIN",
                          "evidence_issues": ["incomplete_or_invalid_run_evidence"]}
                row["status"] = "UNCERTAIN"
        else:
            row["status"] = "UNCERTAIN" if attempted or candidates else "NOT_RUN"
            report = {"verified_report_outcome": row["status"],
                      "evidence_issues": ["missing_or_ambiguous_run"] if row["status"] != "NOT_RUN" else []}
        row.update(_call_metrics(records))
        if row["status"] == "NOT_RUN":
            row["model_calls"] = 0
        row["verified_evidence"] = row["status"] == "PASS" and not report.get("evidence_issues")
        report.update({"case_id": task["case_id"], "index": index,
                       "repetition": task["repetition"], "call_metrics": _call_metrics(records)})
        reports.append((index, report))
        entries.append(row)
    observed = [row for row in entries if row["status"] != "NOT_RUN"]
    summary.update({"per_case": entries, "executed": len(observed),
                    "not_run": len(entries) - len(observed)})
    for status in ("PASS", "FAIL", "UNCERTAIN"):
        summary[status.lower()] = sum(row["status"] == status for row in observed)
    summary["observed_pass_fraction"] = summary["pass"] / len(observed) if observed else None
    summary["token_telemetry_complete"] = bool(observed) and all(row["token_usage_measured"] for row in observed)
    charges = [row["estimated_visible_usd"] for row in observed]
    summary["estimated_visible_total_usd"] = round(sum(charges), 8) if charges and all(_number(x) for x in charges) else None
    for field, median_name in (("elapsed_hermes_seconds", "median_hermes_seconds"),
                                ("tool_calls", "median_tool_calls")):
        values = [row[field] for row in observed if _number(row[field])]
        summary[median_name] = statistics.median(values) if values else None
        if field == "elapsed_hermes_seconds":
            summary["range_hermes_seconds"] = [min(values), max(values)] if values else None
    if summary["uncertain"] or summary["not_run"] or diagnostics:
        summary["engineering_target"] = "UNCERTAIN" if len(tasks) == 8 else "NOT_APPLICABLE"
    return summary, reports, diagnostics


def _cell(value) -> str:
    return "unknown" if value is None else str(value).replace("|", "\\|").replace("\n", " ").replace("<", "&lt;").replace(">", "&gt;")


def _markdown(result: dict, summary: dict | None) -> str:
    lines = ["# Hermes live experiment", "", "| Assessment | Result |", "|---|---|",
             *[f"| {label} | {_cell(result.get(key))} |" for label, key in (
                 ("Workflow", "workflow_conclusion"), ("Infrastructure", "infrastructure_status"),
                 ("API connection", "connection_status"), ("Experiment", "experiment_status"),
                 ("Mode", "mode"), ("Diagnostic", "diagnostic_code"),
                 ("Hermes revision", "hermes_commit"))], ""]
    code = result.get("diagnostic_code")
    remediation = REMEDIATION.get(code) if isinstance(code, str) else None
    if remediation:
        lines += [remediation, ""]
    smoke = result.get("smoke")
    if smoke:
        lines += ["## API probe", "", "| Measurement | Value |", "|---|---|",
                  *[f"| {label} | {_cell(smoke.get(key))} |" for label, key in (
                      ("Observed model", "init_model"), ("Input tokens", "tokens_input"),
                      ("Output tokens", "tokens_output"), ("Elapsed seconds", "elapsed_seconds"),
                      ("Estimated USD", "estimated_visible_usd"))], ""]
    lines += ["## Execution conditions", "", "| Condition | Value |", "|---|---|",
              *[f"| {label} | {_cell(result.get(key))} |" for label, key in (
                  ("Source commit", "git_commit"), ("Runner image", "runner_image"),
                  ("OS", "host_os"), ("Architecture", "host_architecture"),
                  ("Python", "python_version"), ("CPU", "host_processor"),
                  ("Logical CPUs", "cpu_logical_count"), ("Observed clock range (MHz)", "cpu_observed_mhz_range"),
                  ("Memory (bytes)", "memory_total_bytes"))],
              "", "Tasks execute sequentially. Hosted CPU clock and provider-side hardware are not controlled.", ""]
    if summary:
        lines += ["## Experimental observations", "", "| Attempt | Case | Result | Hermes invocations | Input tokens | Output tokens | Tools | Hermes seconds | Estimated USD |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for row in summary.get("per_case", []):
            lines.append("| " + " | ".join(_cell(row.get(key)) for key in (
                "index", "case_id", "status", "model_calls", "tokens_input", "tokens_output",
                "tool_calls", "elapsed_hermes_seconds", "estimated_visible_usd")) + " |")
        lines += ["", f"Engineering target: {_cell(summary.get('engineering_target'))}.", ""]
    lines += ["Connection success and experimental success are separate assessments. A CLI check makes no model requests.",
              "Hermes invocations are not API-request counts. The soft spending guard uses the nominal token rates in the pinned source; USD values are estimates, not billing receipts or hard caps.",
              "Combined observed estimate including the API probe (USD): " + _cell(result.get("estimated_visible_total_usd_including_smoke")) + ".",
              "Unknown counters remain unknown. This is a single-method preliminary experiment; it does not establish superiority."]
    if result["diagnostic_codes"]:
        lines += ["", "Diagnostic codes: " + ", ".join(_cell(x) for x in result["diagnostic_codes"])]
    return "\n".join(lines) + "\n"


def collect_results(run_root: Path, summary_path: Path | None = None) -> dict:
    """Return and persist conservative results, including failed pre-plan runs."""
    root = Path(os.path.abspath(run_root))
    _no_symlinks(root)
    output = root / "results"
    _no_symlinks(output)
    diagnostics = []
    try:
        state = _object(root / "ci-state.json") or {}
    except PARSE_ERRORS:
        state = {}
        diagnostics.append("CI_STATE_UNREADABLE")
    result = _select(state, STATE_FIELDS)
    result.update({"schema_version": "1.0", "mode": state.get("mode") if state.get("mode") in ("check", "smoke", "pilot", "benchmark") else None})
    result["limits"] = _select(state.get("limits", {}) if isinstance(state.get("limits"), dict) else {}, LIMIT_FIELDS)
    try:
        smoke_raw = _object(root / "smoke.json") or {}
    except PARSE_ERRORS:
        smoke_raw = {}
        diagnostics.append("SMOKE_EVIDENCE_UNREADABLE")
    smoke = _select(smoke_raw, SMOKE_FIELDS)
    result["smoke"] = smoke or None
    connection = _outcome(state.get("connection_status", "NOT_RUN"))
    if connection == "PASS" and not (smoke.get("status") == "PASS"
                                     and smoke.get("terminal_result_seen") is True and smoke.get("hermes_exit_code") == 0
                                     and _counter(smoke.get("tokens_input")) and smoke["tokens_input"] > 0
                                     and _counter(smoke.get("tokens_output")) and smoke["tokens_output"] > 0):
        connection = "UNCERTAIN"
        diagnostics.append("CONNECTION_EVIDENCE_INCOMPLETE")
    result["connection_status"] = connection
    summary = None
    reports = []
    try:
        batches_root = root / "raw" / "benchmarks"
        _no_symlinks(batches_root)
        batches = sorted(batches_root.glob("benchmark-*")) if batches_root.exists() else []
        if len(batches) == 1:
            summary, reports, batch_notes = _collect_batch(batches[0])
            diagnostics += batch_notes
        elif len(batches) > 1:
            diagnostics.append("AMBIGUOUS_BENCHMARK_BATCH")
    except PARSE_ERRORS:
        diagnostics.append("BENCHMARK_EVIDENCE_UNREADABLE")
    state_status = state.get("status") if isinstance(state.get("status"), str) else None
    infrastructure = {"COMPLETE": "PASS", "ERROR": "FAIL", "TIMEOUT": "UNCERTAIN", "STARTED": "UNCERTAIN"}.get(state_status, "NOT_RUN")
    if state and infrastructure == "NOT_RUN":
        infrastructure = "UNCERTAIN"
    experiment = "NOT_RUN"
    if summary:
        if summary.get("uncertain") or summary.get("not_run") or not summary.get("executed"):
            experiment = "UNCERTAIN"
        elif summary.get("engineering_target") in ("PASS", "FAIL"):
            experiment = summary["engineering_target"]
        else:
            experiment = "FAIL" if summary.get("fail") else "PASS"
    elif result["mode"] in ("pilot", "benchmark") and state.get("status") != "STARTED":
        experiment = "UNCERTAIN"
    conclusion = infrastructure
    if infrastructure == "PASS":
        if result["mode"] == "check":
            conclusion = "PASS" if state.get("cli_compatible") is True else "UNCERTAIN"
        elif connection != "PASS":
            conclusion = "FAIL" if connection == "FAIL" else "UNCERTAIN"
        elif result["mode"] == "smoke":
            conclusion = _outcome(smoke.get("status"))
        elif result["mode"] in ("pilot", "benchmark"):
            conclusion = experiment
        else:
            conclusion = "UNCERTAIN"
    if diagnostics and conclusion == "PASS":
        conclusion = "UNCERTAIN"
    if summary and summary.get("executed") and not summary.get("token_telemetry_complete"):
        diagnostics.append("TOKEN_TELEMETRY_INCOMPLETE")
        if conclusion == "PASS":
            conclusion = "UNCERTAIN"
    if not state and (diagnostics or summary or smoke):
        conclusion = infrastructure = "UNCERTAIN"
    total = None
    smoke_cost = smoke.get("estimated_visible_usd")
    if (_number(smoke_cost) and _counter(smoke.get("tokens_input"))
            and smoke["tokens_input"] > 0 and _counter(smoke.get("tokens_output"))
            and smoke["tokens_output"] > 0):
        if result["mode"] == "smoke":
            total = smoke_cost
        elif summary and _number(summary.get("estimated_visible_total_usd")):
            total = round(smoke_cost + summary["estimated_visible_total_usd"], 8)
    result.update({"workflow_conclusion": conclusion, "infrastructure_status": infrastructure,
                   "experiment_status": experiment, "diagnostic_codes": diagnostics,
                   "benchmark_summary": summary, "estimated_visible_total_usd_including_smoke": total})
    result = _redact(result)
    if output.exists():
        for old in output.iterdir():
            if old.name == "summary.json" or re.fullmatch(r"report-task-\d{2}\.json", old.name):
                _no_symlinks(old)
                if old.is_file():
                    old.unlink()
    _write_json(output / "ci-result.json", result)
    if summary is not None:
        _write_json(output / "summary.json", summary)
    for index, report in reports:
        _write_json(output / f"report-task-{index:02d}.json", report)
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for row in summary.get("per_case", []) if summary else []:
        item = {key: row.get(key) for key in CSV_FIELDS}
        item["hermes_invocations"] = row.get("model_calls")
        writer.writerow(item)
    _write(output / "attempts.csv", csv_buffer.getvalue())
    markdown = _redact(_markdown(result, summary))
    _write(output / "summary.md", markdown)
    if summary_path:
        _write(Path(os.path.abspath(summary_path)), markdown, append=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Export CI evidence; no API calls")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--summary-path", type=Path, default=os.environ.get("GITHUB_STEP_SUMMARY"))
    args = parser.parse_args()
    result = collect_results(args.run_root, args.summary_path)
    print(json.dumps({key: result[key] for key in ("workflow_conclusion", "connection_status", "experiment_status")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
