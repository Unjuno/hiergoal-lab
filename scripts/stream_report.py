# SPDX-License-Identifier: Apache-2.0
"""Parse Hermes --format stream-json. Never confuse tokens with actual billing."""
import argparse
import json
from pathlib import Path


def parse_events(path: Path) -> dict:
    n = bad = 0
    init = final = None
    calls = []
    failures = 0
    todo_calls = 0
    nested_todo_writes_requested = 0
    nested_todo_result_observed = False
    todo_results_readable = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if not isinstance(event, dict):
            bad += 1
            continue
        n += 1
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            init = event
        elif kind == "tool_use":
            calls.append({"name": event.get("name", "unknown"),
                          "timestamp": event.get("timestamp")})
            if event.get("name") == "todo_list":
                todo_calls += 1
                payload = event.get("input")
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        payload = None
                if isinstance(payload, dict) and isinstance(payload.get("todos"), list):
                    if any(isinstance(t, dict) and bool(t.get("parent"))
                           for t in payload["todos"]):
                        nested_todo_writes_requested += 1
        elif kind == "tool_result":
            failures += bool(event.get("is_error", False))
            if event.get("name") == "todo_list" and not event.get("is_error", False):
                payload = event.get("output")
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        payload = None
                if isinstance(payload, dict) and isinstance(payload.get("todos"), list):
                    todo_results_readable += 1
                    items = [x for x in payload["todos"] if isinstance(x, dict)]
                    ids = {str(x.get("id")) for x in items}
                    nested_todo_result_observed |= any(
                        bool(x.get("parent")) and str(x["parent"]) in ids
                        for x in items
                    )
        elif kind == "result":
            final = event
    tokens = (final or {}).get("tokens") or {}
    return {
        "events": n,
        "invalid_json_lines": bad,
        "init_model": (init or {}).get("model"),
        "session_id": (final or {}).get("session_id") or (init or {}).get("session_id"),
        "terminal_result_seen": final is not None,
        "hermes_exit_code": (final or {}).get("exit_code"),
        "hermes_reported_duration_ms": (final or {}).get("duration_ms"),
        "tool_calls": len(calls),
        "tool_timeline": calls,
        "tool_failures": failures,
        "native_todo_list_calls": todo_calls,
        "nested_todo_writes_requested": nested_todo_writes_requested,
        "readable_todo_tool_results": todo_results_readable,
        "verified_nested_todo_result_observed": nested_todo_result_observed,
        "tokens_input": tokens.get("input"),
        "tokens_output": tokens.get("output"),
        "tokens_total": tokens.get("total"),
        "tokens_cache_read": tokens.get("cache_read"),
        "tokens_cache_write": tokens.get("cache_write"),
        "error": (final or {}).get("error"),
        "replay_gap": bool((final or {}).get("replay_gap")),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("path", type=Path)
    args = p.parse_args()
    print(json.dumps(parse_events(args.path), ensure_ascii=False, indent=2))
