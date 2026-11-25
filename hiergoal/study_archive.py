# SPDX-License-Identifier: Apache-2.0
"""Publish only audited, structured experiment results; never raw model content."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
from collections import Counter
from pathlib import Path

from hiergoal.study_analysis import (
    EVIDENCE_BOOLEAN_FIELDS, EVIDENCE_INTEGER_FIELDS, INTEGER_METRICS,
    analyze, render_markdown,
)
from hiergoal.study_protocol import PROFILES, canonical, save, validate_manifest

RECEIPT = "publication.json"
DATA_FILES = {"manifest.json", "host.json", "results.json", "summary.json",
              "summary.md", "trials.csv", "execution.json"}
STATUS = {"PASS", "FAIL", "UNCERTAIN", "NOT_RUN"}
AUDIT = {"PASS", "FAIL", "INCOMPLETE", "NOT_RUN"}
STEP_OUTCOMES = {"success", "failure", "cancelled", "skipped"}
BOOL_FIELDS = ("success", "fault_assigned", "fault_triggered", "fault_delivered",
               "recovered", "invariant_ok", "protocol_ok", "simulated", "stop_batch")
COUNTS = (*INTEGER_METRICS, "known_completed_calls", "known_input_tokens",
          "known_output_tokens", "known_actual_input_tokens", "known_actual_output_tokens",
          "pending_requests")
HASH_FIELDS = ("final_artifact_sha256", "final_environment_sha256", "trace_final_sha256")
HOST_FIELDS = ("timestamp_utc", "git_commit", "working_tree_dirty", "python",
               "platform", "cpu", "cpu_clock_mhz_observed_range", "logical_cpus",
               "memory_bytes", "batch_size", "model_hardware")
CSV_COLUMNS = ("trial_id", "family", "instance", "condition", "repeat", "arm",
               "status", "success", "audit", "diagnostic", "fault_triggered",
               "fault_delivered", "recovered", *COUNTS, "elapsed_seconds",
               "wall_seconds", "invariant_ok", "protocol_ok", *HASH_FIELDS)


def render_trials_csv(trials, results):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for trial, record in zip(trials, results):
        writer.writerow({**trial, **record})
    return stream.getvalue()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(profile, run_id, attempt, commit):
    require(profile in PROFILES, "Unknown profile")
    require(re.fullmatch(r"[1-9][0-9]{0,19}", str(run_id)) is not None, "Invalid run ID")
    require(re.fullmatch(r"[1-9][0-9]{0,9}", str(attempt)) is not None, "Invalid attempt")
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "Invalid source commit")
    return {"profile": profile, "run_id": str(run_id), "run_attempt": str(attempt),
            "source_commit": commit}


def scalar(value, kind):
    if value is None:
        return None
    if kind == "bool":
        require(type(value) is bool, "Invalid boolean result field")
    elif kind == "int":
        require(type(value) is int and value >= 0, "Invalid integer result field")
    else:
        require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
                "Invalid numeric result field")
    return value


def diagnostic_code(value):
    """No arbitrary exception strings or model-supplied text enter Git."""
    if not isinstance(value, str):
        return "UNSPECIFIED"
    fixed = {
        "Independent final grading passed": "FINAL_GRADE_PASS",
        "Final withheld grading failed": "FINAL_GRADE_FAIL",
        "Trial not started": "NOT_RUN",
        "Started but interrupted before a complete result": "INTERRUPTED",
        "Measured logical token allowance exceeded on last response": "TOKEN_BUDGET_AFTER",
        "Measured logical token allowance exhausted": "TOKEN_BUDGET_BEFORE",
        "Logical request allowance exhausted": "CALL_BUDGET",
        "Prompt byte limit reached": "PROMPT_BYTE_BUDGET",
        "Trial time allowance exceeded on last response": "TIME_BUDGET_AFTER",
        "Trial time allowance exhausted": "TIME_BUDGET_BEFORE",
        "instruction must contain 5..1200 characters": "INVALID_PLAN_INSTRUCTION",
        "Response did not complete within its output allowance": "INCOMPLETE_RESPONSE",
        "Response must be one JSON object": "INVALID_JSON",
        "BATCH_TIME_ALLOWANCE": "BATCH_TIME_ALLOWANCE",
        "Immutable root changed": "ROOT_INVARIANT",
        "OPENAI_TRANSPORT_OR_JSON_ERROR:TimeoutError": "API_TIMEOUT",
    }
    if value in fixed:
        return fixed[value]
    if re.fullmatch(r"OPENAI_HTTP_[0-9]{3}", value):
        return value
    for prefix, code in (("EVIDENCE_AUDIT_FAILED:", "AUDIT_FAILED"),
                         ("APPARATUS_ERROR:", "APPARATUS_ERROR"),
                         ("OPENAI_TRANSPORT_OR_JSON_ERROR:", "API_TRANSPORT_ERROR")):
        if value.startswith(prefix):
            return code
    return "OTHER_RECORDED_DIAGNOSTIC"


def public_evidence(value):
    if value is None:
        return None
    require(isinstance(value, dict), "Invalid mechanism evidence")
    result = {key: scalar(value[key], "bool") for key in EVIDENCE_BOOLEAN_FIELDS if key in value}
    for group, fields in EVIDENCE_INTEGER_FIELDS.items():
        if group not in value or value[group] is None:
            continue
        raw = value[group]
        require(isinstance(raw, dict), "Invalid mechanism counters")
        extra = ("max_depth",) if group == "tree" else (("root_state_transitions",) if group == "trace" else ())
        result[group] = {key: scalar(raw[key], "int") for key in (*fields, *extra) if key in raw}
        if group == "tree" and "dependency_density" in raw:
            result[group]["dependency_density"] = scalar(raw["dependency_density"], "number")
    if value.get("fault") is not None:
        raw = value["fault"]
        require(isinstance(raw, dict), "Invalid fault counters")
        result["fault"] = {key: scalar(raw[key], "bool") for key in
                           ("triggered", "delivered", "no_impact", "forced", "domain_delivered") if key in raw}
    return result


def public_result(record, trial, manifest):
    require(record.get("trial_id") == trial["trial_id"], "Result assignment mismatch")
    require(record.get("status") in STATUS and record.get("audit") in AUDIT, "Invalid outcome")
    result = {key: record[key] for key in ("trial_id", "status", "audit")}
    for key in BOOL_FIELDS:
        if key in record:
            result[key] = scalar(record[key], "bool")
    for key in COUNTS:
        if key in record:
            result[key] = scalar(record[key], "int")
    for key in ("elapsed_seconds", "wall_seconds"):
        if key in record:
            result[key] = scalar(record[key], "number")
    for key in ("backend", "protocol_id"):
        if key in record:
            require(record[key] == manifest[key], "Result provenance mismatch")
            result[key] = manifest[key]
    if "fault_kind" in record:
        require(record["fault_kind"] == trial.get("fault_kind", "environment"), "Fault kind mismatch")
        result["fault_kind"] = record["fault_kind"]
    for key in HASH_FIELDS:
        if key in record:
            require(isinstance(record[key], str) and re.fullmatch(r"[0-9a-f]{64}", record[key]),
                    "Invalid result hash")
            result[key] = record[key]
    if "mechanism_evidence" in record:
        result["mechanism_evidence"] = public_evidence(record["mechanism_evidence"])
    if "observed_models" in record:
        observed = record["observed_models"]
        require(isinstance(observed, list), "Invalid observed models")
        model = manifest["model"]
        result["observed_models"] = [
            value for value in observed if isinstance(value, str)
            and len(value) <= 150 and re.fullmatch(r"[A-Za-z0-9_.:-]+", value)
            and (value == model or value.startswith(model + "-"))]
        result["omitted_model_identifiers"] = len(observed) - len(result["observed_models"])
    result["diagnostic"] = diagnostic_code(record.get("diagnostic"))
    return result


def export_run(source, destination, *, profile, run_id, attempt, commit, live_outcome, collection_outcome):
    ident = identity(profile, run_id, attempt, commit)
    require(live_outcome in STEP_OUTCOMES and collection_outcome in STEP_OUTCOMES, "Invalid step outcome")
    require(not destination.exists() or not any(destination.iterdir()), "Refusing to overwrite publication")
    destination.mkdir(parents=True, exist_ok=True)
    receipt = {"schema": "hiergoal.publication.v1", **ident,
               "live_step": live_outcome, "collection_step": collection_outcome,
               "scope": "audited structured results; raw prompts, traces, responses and artifacts excluded",
               "state": "NO_COLLECTED_RESULTS", "complete_audited_execution": False,
               "scheduled_trials": None, "outcomes": None, "files": {}}
    required = {"manifest.json", "host.json", "results.json", "summary.json"}
    if collection_outcome == "success" and all((source / name).is_file() for name in required):
        manifest = read_json(source / "manifest.json")
        validate_manifest(manifest)
        require(manifest["backend"] == "openai" and manifest["profile"] == profile, "Not the requested live manifest")
        raw_host = read_json(source / "host.json")
        host = {k: raw_host[k] for k in HOST_FIELDS if k in raw_host}
        require(host.get("git_commit") == commit and host.get("working_tree_dirty") is False, "Run source not clean or mismatched")
        raw = read_json(source / "results.json")
        trials = manifest["trials"]
        require(isinstance(raw, list) and len(raw) == len(trials), "Missing collected rows")
        results = [public_result(record, trial, manifest) for record, trial in zip(raw, trials)]
        summary = analyze({**manifest, "execution_context": host}, results)
        # Redaction must not change the statistical analysis or discard any
        # counters used by the analysis. Fail closed if schemas drift.
        require(canonical(summary) == canonical(read_json(source / "summary.json")),
                "Public projection changed the collected analysis")
        save(destination / "manifest.json", manifest)
        save(destination / "host.json", host)
        save(destination / "results.json", results)
        save(destination / "summary.json", summary)
        (destination / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
        with (destination / "trials.csv").open("w", encoding="utf-8", newline="") as stream:
            stream.write(render_trials_csv(trials, results))
        if (source / "execution.json").is_file():
            execution = read_json(source / "execution.json")
            require(execution.get("protocol_id") == manifest["protocol_id"]
                    and execution.get("backend") == "openai", "Execution provenance mismatch")
            require(execution.get("status") in ("RUNNING", "STOPPED", "COMPLETED"), "Invalid execution state")
            count = scalar(execution.get("completed"), "int")
            require(count is not None and count <= len(trials), "Invalid execution count")
            save(destination / "execution.json", {
                "status": execution["status"], "protocol_id": manifest["protocol_id"],
                "backend": "openai", "completed": count,
                "stop_reason": diagnostic_code(execution["stop_reason"]) if execution.get("stop_reason") else None,
            })
        outcomes = Counter(record["status"] for record in results)
        receipt.update(state="COLLECTED", protocol_id=manifest["protocol_id"],
                       protocol_revision=manifest.get("protocol_revision"), scheduled_trials=len(trials),
                       outcomes={key: outcomes[key] for key in sorted(STATUS)},
                       complete_audited_execution=all(record["status"] in ("PASS", "FAIL") and record["audit"] == "PASS" for record in results),
                       files={p.name: file_hash(p) for p in sorted(destination.iterdir())})
    save(destination / RECEIPT, receipt)
    verify(destination, **ident_for_verify(ident))
    return receipt


def ident_for_verify(ident):
    return dict(profile=ident["profile"], run_id=ident["run_id"],
                attempt=ident["run_attempt"], commit=ident["source_commit"])


def verify(destination, *, profile, run_id, attempt, commit):
    """Verify cross-file consistency; checksums alone do not authenticate evidence.

    The trusted workflow must still run the trace replayer before export. This
    second job checks the frozen source identity and recomputes all public
    decisions, so a receipt or rendered summary cannot override its result rows.
    """
    ident = identity(profile, run_id, attempt, commit)
    receipt = read_json(destination / RECEIPT)
    require(isinstance(receipt, dict) and receipt.get("schema") == "hiergoal.publication.v1"
            and all(receipt.get(k) == v for k, v in ident.items()), "Publication identity mismatch")
    require(receipt.get("live_step") in STEP_OUTCOMES
            and receipt.get("collection_step") in STEP_OUTCOMES, "Invalid publication step outcome")
    require(type(receipt.get("complete_audited_execution")) is bool, "Invalid completion flag")
    files = receipt.get("files")
    require(isinstance(files, dict) and set(files).issubset(DATA_FILES), "Unexpected publication file")
    require(all(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha)
                for sha in files.values()), "Invalid publication checksum")
    paths = list(destination.iterdir())
    require({p.name for p in paths} == {RECEIPT, *files}
            and all(p.is_file() and not p.is_symlink() for p in paths), "Unexpected archive contents")
    require(all(file_hash(destination / name) == sha for name, sha in files.items()), "Publication checksum mismatch")
    if receipt.get("state") == "COLLECTED":
        require(receipt["collection_step"] == "success", "Collected publication requires successful collection")
        require(DATA_FILES - {"execution.json"} <= set(files), "Missing public result files")
        manifest = read_json(destination / "manifest.json")
        validate_manifest(manifest)
        results = read_json(destination / "results.json")
        require(manifest["profile"] == profile and manifest["backend"] == "openai"
                and manifest["protocol_id"] == receipt.get("protocol_id")
                and manifest.get("protocol_revision") == receipt.get("protocol_revision"),
                "Publication manifest mismatch")
        host = read_json(destination / "host.json")
        require(isinstance(host, dict) and set(host).issubset(HOST_FIELDS)
                and host.get("git_commit") == commit and host.get("working_tree_dirty") is False,
                "Publication source not clean or mismatched")
        require(isinstance(results, list) and all(isinstance(record, dict) for record in results),
                "Invalid public result rows")
        require(type(receipt.get("scheduled_trials")) is int and receipt["scheduled_trials"] > 0,
                "Invalid scheduled trial count")
        require(len(results) == len(manifest["trials"]) == receipt["scheduled_trials"], "Publication coverage mismatch")
        for record, trial in zip(results, manifest["trials"]):
            # Validate result types, hashes and source/fault identity using the
            # same projection boundary as export, without changing the rows.
            public_result(record, trial, manifest)
        counts = Counter(r["status"] for r in results)
        outcomes = receipt.get("outcomes")
        require(isinstance(outcomes, dict) and set(outcomes) == STATUS
                and all(type(value) is int and value >= 0 for value in outcomes.values())
                and outcomes == {k: counts[k] for k in sorted(STATUS)}, "Publication outcome mismatch")
        complete = all(r["status"] in ("PASS", "FAIL") and r["audit"] == "PASS" for r in results)
        require(receipt["complete_audited_execution"] is complete, "Publication completion mismatch")
        summary = analyze({**manifest, "execution_context": host}, results)
        require(canonical(read_json(destination / "summary.json")) == canonical(summary),
                "Publication analysis mismatch")
        require((destination / "summary.md").read_text(encoding="utf-8") == render_markdown(summary),
                "Publication rendered analysis mismatch")
        with (destination / "trials.csv").open(encoding="utf-8", newline="") as stream:
            require(stream.read() == render_trials_csv(manifest["trials"], results),
                    "Publication trial table mismatch")
        if "execution.json" in files:
            execution = read_json(destination / "execution.json")
            require(isinstance(execution, dict) and execution.get("protocol_id") == manifest["protocol_id"]
                    and execution.get("backend") == "openai", "Execution provenance mismatch")
            require(execution.get("status") in ("RUNNING", "STOPPED", "COMPLETED"), "Invalid execution state")
            count = scalar(execution.get("completed"), "int")
            require(count is not None and count <= len(results)
                    and (execution["status"] != "COMPLETED" or count == len(results)),
                    "Invalid execution count")
    else:
        require(receipt.get("state") == "NO_COLLECTED_RESULTS" and not files
                and receipt["complete_audited_execution"] is False
                and receipt.get("scheduled_trials") is None and receipt.get("outcomes") is None
                and receipt.get("protocol_id") is None and receipt.get("protocol_revision") is None,
                "Invalid receipt-only publication")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("export", "verify"))
    parser.add_argument("--source", type=Path, default=Path("runs/method-study"))
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--live-outcome", choices=sorted(STEP_OUTCOMES), default="skipped")
    parser.add_argument("--collection-outcome", choices=sorted(STEP_OUTCOMES), default="skipped")
    args = parser.parse_args()
    ident = dict(profile=args.profile, run_id=args.run_id, attempt=args.attempt, commit=args.commit)
    if args.command == "export":
        receipt = export_run(args.source, args.destination, **ident,
                             live_outcome=args.live_outcome, collection_outcome=args.collection_outcome)
    else:
        receipt = verify(args.destination, **ident)
    print("Public experiment record:", receipt["state"],
          "complete audited execution:", receipt["complete_audited_execution"])


if __name__ == "__main__":
    main()
