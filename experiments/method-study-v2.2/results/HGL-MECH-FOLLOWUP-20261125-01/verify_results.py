#!/usr/bin/env python3
"""Recheck committed result tables only. No network/API; not raw trace replay."""
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def rows(name):
    with (ROOT / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def main():
    trials = rows("trials.csv")
    plans = rows("plan_recheck.csv")
    traces = rows("trace_integrity.csv")
    failures = rows("failures.csv")
    usage = rows("failure_call_usage.csv")
    groups = rows("arm_condition_summary.csv")
    summary = json.loads((ROOT / "summary.json").read_text(encoding="utf-8"))
    key = lambda r: (r["dataset"], r["trial_id"])
    assert len(trials) == len(traces) == 216
    assert len({key(r) for r in trials}) == 216
    assert {key(r) for r in trials} == {key(r) for r in traces}
    assert Counter((r["dataset"], r["status"]) for r in trials) == {
        ("method-study", "PASS"): 94, ("method-study", "FAIL"): 14,
        ("method-check", "PASS"): 108}
    assert len(failures) == 14 and len(usage) == 44
    assert {key(r) for r in failures} == {key(r) for r in trials if r["status"] == "FAIL"}
    assert Counter(r["termination_reason"] for r in failures) == {"InvalidAction": 12, "BudgetExhausted": 2}
    assert all(int(r["input_tokens"])+int(r["output_tokens"]) == int(r["total_tokens"]) for r in trials)
    assert all(r[k] == "True" for r in traces for k in ("hash_chain_ok", "final_hash_matches", "logical_usage_matches", "result_file_matches"))
    assert len(plans) == 36 and all(r[k] == "True" for r in plans for k in ("candidate_pass", "matches_recorded_plan", "matches_recorded_error", "root_unchanged", "unmodified_instructions_preserved"))
    assert sum(r["recorded_pass"] == "False" for r in plans) == 3
    assert sum(bool(r["changed_gates"]) for r in plans) == 3
    grouped = defaultdict(list)
    for row in trials:
        grouped[row["dataset"], row["arm"], row["condition"]].append(row)
    assert len(grouped) == len(groups) == 12
    for group in groups:
        rr = grouped[group["dataset"], group["arm"], group["condition"]]
        tokens = [int(r["total_tokens"]) for r in rr]
        assert len(rr) == int(group["n"]) == 18
        assert sum(r["status"] == "PASS" for r in rr) == int(group["pass"])
        assert sum(r["status"] == "FAIL" for r in rr) == int(group["fail"])
        assert statistics.median(tokens) == float(group["median_logical_tokens"])
        assert min(tokens) == int(group["min_logical_tokens"])
        assert max(tokens) == int(group["max_logical_tokens"])
        assert statistics.median(int(r["calls"]) for r in rr) == float(group["median_calls"])
    assert summary["model_calls_new"] == 0 and summary["efficacy_decision"] == "UNCERTAIN"
    assert all(c["passed"] for c in summary["checks"])
    print("PASS: committed tables internally consistent (216 trials, 36 plans, 14 failures).")
    print("Raw trace revalidation and end-to-end candidate efficacy NOT tested.")

if __name__ == "__main__":
    main()
