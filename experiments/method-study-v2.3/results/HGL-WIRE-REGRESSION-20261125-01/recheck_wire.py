#!/usr/bin/env python3
"""Recheck archived v2.2 logical response inputs; no model requests."""
import argparse
import hashlib
import json
import zipfile
from collections import defaultdict
from pathlib import Path

from hiergoal.study_wire import canonical, expand_wire, response_format, wire_input


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_archive", type=Path)
    args = parser.parse_args()
    expected = json.loads(Path(__file__).with_name("summary.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(args.source_archive.read_bytes()).hexdigest() == expected["source_archive_sha256"]
    groups = defaultdict(lambda: [0, 0, 0])
    plans = invalid = 0
    failures = []
    with zipfile.ZipFile(args.source_archive) as archive:
        for name in archive.namelist():
            if name.startswith("method-study/plans/") and name.endswith(".json"):
                p = json.loads(archive.read(name))
                fmt = response_format("plan", p["request"])
                properties = fmt["schema"]["properties"]["instructions"]
                assert fmt["strict"] and set(properties["required"]) == set(p["request"]["gates"])
                assert all(v == {"type": "string"} for v in properties["properties"].values())
                plans += 1
                if p["error"]:
                    value = json.loads(p["record"]["text"])
                    assert any(not isinstance(v, str) for v in value["instructions"].values())
                    invalid += 1
            if not name.startswith("method-study/trials/") or not name.endswith("/trace.jsonl"):
                continue
            count = old = new = 0
            for line in archive.read(name).splitlines():
                e = json.loads(line)
                if e["type"] != "response":
                    continue
                role, p = e["role"], e["request"]
                logical = {"role": role, **p}
                compact = wire_input(role, p)
                assert canonical(expand_wire(compact)) == canonical(logical)
                a = len(canonical(logical).encode("utf-8"))
                b = len(canonical(compact).encode("utf-8"))
                assert b <= a
                for i, v in enumerate((1, a, b)):
                    groups[role][i] += v
                count += 1
                old += a
                new += b
            r = json.loads(archive.read(name.replace("trace.jsonl", "result.json")))
            if "Measured logical token allowance exceeded" in str(r.get("diagnostic")):
                failures.append({"trial_id": r["trial_id"], "responses": count,
                                 "original_input_json_bytes": old, "compact_input_json_bytes": new})
    assert plans == expected["plans_checked"] and invalid == expected["historical_plans_with_wrong_type_excluded_by_schema"]
    assert sum(g[0] for g in groups.values()) == expected["exact_roundtrips"]
    assert dict(groups) == {g["role"]: [g["responses"], g["original_input_json_bytes"], g["compact_input_json_bytes"]] for g in expected["groups"]}
    assert sorted(failures, key=lambda x: x["trial_id"]) == sorted(expected["budget_failure_cases"], key=lambda x: x["trial_id"])
    print("PASS: 586 exact wire round-trips; 18 plans; 3 historical wrong-type plans.")
    print("Live model, tokens and efficacy remain unverified.")


if __name__ == "__main__":
    main()
