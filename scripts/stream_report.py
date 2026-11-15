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
        elif kind == "tool_result":
            failures += bool(event.get("is_error", False))
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
