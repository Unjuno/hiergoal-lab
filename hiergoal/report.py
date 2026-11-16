# SPDX-License-Identifier: Apache-2.0
"""Build a conservative, non-raw research report from local Hermes run records.

This is not an anti-tamper attestation: source files can be modified by the
local experiment operator. It independently checks that a claimed PASS has
the expected grading evidence and parseable terminal Hermes events.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from scripts.stream_report import parse_events


class EvidenceError(ValueError):
    pass


def _load_object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError("Could not read valid JSON: " + path.name) from exc
    if not isinstance(value, dict):
        raise EvidenceError("Expected object in " + path.name)
    return value


def _fingerprint(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return {"name": path.name, "sha256": digest.hexdigest(), "size_bytes": path.stat().st_size}


def compile_report(run_directory: Path) -> dict:
    """Only whitelist report fields. Never include prompt text, trace bodies or stderr."""
    directory = run_directory.resolve()
    state = _load_object(directory / "state.json")
    records = _load_object(directory / "records.json")
    status = str(records.get("outcome", "UNCERTAIN"))
    if status not in ("PASS", "FAIL", "UNCERTAIN", "NOT_RUN"):
        status = "UNCERTAIN"
    issues = []
    evidence = []
    gate_files = sorted(directory.glob("gate-*.json"))
    for path in gate_files:
        evidence.append(_fingerprint(path))
    for filename in ("initial_grading.json", "final-visible.json", "state.json", "records.json"):
        candidate = directory / filename
        if candidate.is_file():
            evidence.append(_fingerprint(candidate))
    raw_calls = records.get("calls")
    if not isinstance(raw_calls, list):
        raise EvidenceError("calls must be a list")
    checked_calls = []
    for i, item in enumerate(raw_calls, 1):
        if not isinstance(item, dict) or item.get("index") != i:
            issues.append("invalid_call_index")
            continue
        role = item.get("role")
        if not isinstance(role, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", role):
            issues.append("invalid_call_role")
            continue
        basename = f"{i:02d}-{role}"
        stream = directory / (basename + ".stream.jsonl")
        if not stream.is_file():
            issues.append("missing_hermes_stream")
            continue
        evidence.append(_fingerprint(stream))
        info = parse_events(stream)
        if not info["terminal_result_seen"]:
            issues.append("missing_terminal_event")
        if info["invalid_json_lines"]:
            issues.append("invalid_jsonl")
        if info["hermes_exit_code"] != 0 or item.get("exit_code") != 0:
            issues.append("nonzero_agent_exit")
        checked_calls.append({
            "index": i,
            "role": role,
            "terminal_result_seen": info["terminal_result_seen"],
            "recorded_tool_calls": info["tool_calls"],
            "hermes_exit_code": info["hermes_exit_code"],
            "elapsed_seconds": item.get("elapsed_seconds"),
            "token_usage_measured": bool(item.get("token_usage_measured", False)),
            "nested_todo_observed": bool(item.get("nested_todo_observed", False)),
        })
    if len(checked_calls) != len(raw_calls):
        issues.append("unverified_hermes_calls")
    root = state.get("root") if isinstance(state.get("root"), dict) else {}
    milestones = state.get("milestones") if isinstance(state.get("milestones"), list) else []
    leaves = state.get("leaves") if isinstance(state.get("leaves"), dict) else {}
    terminal_leaves = [item for item in leaves.values()
                       if isinstance(item, dict) and item.get("status") != "superseded"]
    final_gate = records.get("final_independent") if isinstance(records.get("final_independent"), dict) else {}
    visible = records.get("final_visible") if isinstance(records.get("final_visible"), dict) else {}
    final_file = directory / "gate-final-independent.json"
    visible_file = directory / "final-visible.json"
    gate_file_ok = final_file.is_file() and _load_object(final_file).get("passed") is True
    visible_file_ok = visible_file.is_file() and _load_object(visible_file).get("passed") is True

    if status == "PASS":
        if not (
            root.get("status") == "completed"
            and len(milestones) >= 2
            and terminal_leaves
            and all(leaf.get("status") == "completed" for leaf in terminal_leaves)
            and final_gate.get("passed") is True
            and final_gate.get("tests_run") == 6
            and visible.get("passed") is True
            and visible.get("tests_run") == 3
            and records.get("original_visible_tests_unchanged") is True
            and gate_file_ok and visible_file_ok
        ):
            issues.append("pass_claim_missing_acceptance_evidence")
    declared = status
    result = "UNCERTAIN" if issues else status
    report = {
        "schema_version": "1.0",
        "study": "hierarchical Hermes goal execution, single-case observation",
        "source": "local run records + SHA256 fingerprints; not a signed attestation",
        "experiment": str(records.get("experiment", "unknown")),
        "provider": str(records.get("provider", "unknown")),
        "model": str(records.get("model", "unknown")),
        "profile": str(records.get("profile", "unknown")),
        "provenance": {
            key: records.get("provenance", {}).get(key)
            for key in ("protocol_id", "git_commit", "timestamp_utc",
                        "host_os", "host_architecture", "python_version")
        },
        "declared_outcome": declared,
        "verified_report_outcome": result,
        "evidence_issues": sorted(set(issues)),
        "milestone_count": len(milestones),
        "leaf_count_including_superseded": len(leaves),
        "terminal_leaves_completed": sum(item.get("status") == "completed" for item in terminal_leaves),
        "replans": state.get("replans"),
        "hermes_calls_claimed": len(raw_calls),
        "hermes_calls_with_readable_streams": len(checked_calls),
        "observed_tool_calls": sum(item["recorded_tool_calls"] for item in checked_calls),
        "elapsed_hermes_seconds": round(sum(
            float(item["elapsed_seconds"]) for item in checked_calls
            if isinstance(item["elapsed_seconds"], (int, float))
        ), 3),
        "token_usage_measured_on_all_calls": bool(checked_calls) and all(
            item["token_usage_measured"] for item in checked_calls
        ),
        "estimated_visible_usd": records.get("estimated_visible_usd"),
        "caveat": (
            "Provider free-model eligibility and billing are not verified by this report. "
            "It does not prove a performance improvement or causal attribution. "
            "Raw traces need manual privacy review before publication."
        ),
        "calls": checked_calls,
        "evidence_fingerprints": evidence,
    }
    return report


def main() -> None:
    cli = argparse.ArgumentParser(description="Produce a redacted research report (no API calls)")
    cli.add_argument("run_directory", type=Path)
    cli.add_argument("--output", type=Path, help="Path to JSON report; defaults to run_dir/report-public.json")
    args = cli.parse_args()
    try:
        report = compile_report(args.run_directory)
    except EvidenceError as exc:
        cli.error(str(exc))
    destination = args.output or args.run_directory / "report-public.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "report": str(destination),
        "declared_outcome": report["declared_outcome"],
        "verified_report_outcome": report["verified_report_outcome"],
        "evidence_issues": report["evidence_issues"]
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
