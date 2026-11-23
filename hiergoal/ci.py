# SPDX-License-Identifier: Apache-2.0
"""Bounded GitHub Actions entry point: real CLI check, API smoke, then experiment.

No inference in check mode. Other modes require an explicit paid opt-in and
OPENAI_API_KEY. Raw evidence and isolated Hermes homes never enter artifacts.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from hiergoal.benchmark import store
from hiergoal.controller import (
    LUNA_MODEL, LUNA_INPUT_RATE_PER_MTOK, LUNA_OUTPUT_RATE_PER_MTOK,
    hermes_arguments,
)
from scripts.stream_report import parse_events
from scripts.ci_hermes import cleanup_home

ROOT = Path(__file__).resolve().parents[1]
SMOKE_REPLY = "HIERGOAL_API_OK"
REQUIRED_FLAGS = (
    "--provider", "--model", "--reasoning", "--ignore-user-config",
    "--ignore-rules", "--toolsets", "--source", "--in", "--format",
    "--max-turns", "--query-file", "--oneshot",
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def metadata(mode: str, budget: float) -> dict:
    pin = json.loads((ROOT / "ci/hermes.json").read_text(encoding="utf-8"))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, timeout=5)
    result = {
        "mode": mode, "status": "STARTED", "execution_started": False,
        "diagnostic_code": "NOT_STARTED", "cli_compatible": False,
        "connection_status": "NOT_RUN", "hermes_commit": pin["commit"],
        "soft_budget_usd": budget, "started_at": now(),
        "git_commit": commit.stdout.strip() if commit.returncode == 0 else None,
        "python_version": platform.python_version(), "host_os": platform.system(),
        "host_architecture": platform.machine(), "host_processor": platform.processor(),
        "cpu_logical_count": os.cpu_count(), "runner_os": os.getenv("RUNNER_OS"),
        "runner_image": os.getenv("ImageOS", "unknown") + "/" + os.getenv("ImageVersion", "unknown"),
        "limits": {"max_calls": 12, "max_turns": 18, "max_replans": 2,
                   "call_timeout_seconds": 600, "hermes_execution_timeout_seconds": 540,
                   "smoke_execution_timeout_seconds": 120, "seed": 1729,
                   "batch_timeout_seconds": 18000 if mode == "benchmark" else 7200,
                   "per_case_soft_budget_usd": min(1.5, budget)},
    }
    try:
        cpuinfo = Path("/proc/cpuinfo").read_text(encoding="utf-8")
        model = re.search(r"(?m)^model name\s*:\s*(.+)$", cpuinfo)
        if model:
            result["host_processor"] = model.group(1).strip()
        clocks = [float(x) for x in re.findall(r"(?m)^cpu MHz\s*:\s*([0-9.]+)$", cpuinfo)]
        result["cpu_observed_mhz_range"] = [min(clocks), max(clocks)] if clocks else None
        result["memory_total_bytes"] = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (OSError, ValueError):
        pass
    return result


def check_cli(binary: str, private_dir: Path) -> tuple[bool, str | None]:
    """Check the actual installed Hermes, without credentials or model requests."""
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    env["HERMES_HOME"] = str(private_dir / "cli-check-home")
    private_dir.mkdir(parents=True, exist_ok=True)
    try:
        version = subprocess.run([binary, "--version"], env=env, capture_output=True,
                                 text=True, timeout=45)
        help_result = subprocess.run([binary, "chat", "--help"], env=env,
                                     capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False, None
    lines = version.stdout.splitlines()
    label = lines[0][:160] if lines else None
    valid = (version.returncode == help_result.returncode == 0
             and all(flag in help_result.stdout for flag in REQUIRED_FLAGS))
    return valid, label


def inspect_smoke(path: Path, exit_code: int, elapsed: float) -> dict:
    """Only return measured numeric fields and static diagnostic codes."""
    result = {"status": "UNCERTAIN", "reason_code": "INCOMPLETE_STREAM",
              "tokens_input": None, "tokens_output": None,
              "elapsed_seconds": round(elapsed, 3), "estimated_visible_usd": None,
              "terminal_result_seen": False, "hermes_exit_code": None,
              "init_model": None}
    try:
        trace = parse_events(path)
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        terminal = [event for event in events if isinstance(event, dict) and event.get("type") == "result"]
    except (OSError, ValueError, TypeError, AttributeError):
        return result
    result["terminal_result_seen"] = trace["terminal_result_seen"]
    result["hermes_exit_code"] = trace["hermes_exit_code"]
    result["init_model"] = trace["init_model"] if trace["init_model"] == LUNA_MODEL else None
    incoming, outgoing = trace["tokens_input"], trace["tokens_output"]
    measured = (type(incoming) is int and incoming > 0
                and type(outgoing) is int and outgoing > 0)
    if measured:
        result.update(tokens_input=incoming, tokens_output=outgoing,
                      estimated_visible_usd=round((incoming * LUNA_INPUT_RATE_PER_MTOK
                                                   + outgoing * LUNA_OUTPUT_RATE_PER_MTOK) / 1_000_000, 8))
    if exit_code in (124, 137, 143):
        result["reason_code"] = "SMOKE_TIMEOUT_OR_CANCELED"
    elif exit_code != 0 or trace["hermes_exit_code"] not in (None, 0) or trace["error"]:
        result.update(status="FAIL", reason_code="HERMES_OR_API_ERROR")
    elif not terminal or trace["invalid_json_lines"] or trace["replay_gap"]:
        result["reason_code"] = "INCOMPLETE_STREAM"
    elif not measured:
        result["reason_code"] = "MISSING_USAGE_TELEMETRY"
    elif trace["init_model"] != LUNA_MODEL:
        result["reason_code"] = "MODEL_MISMATCH"
    elif trace["tool_calls"]:
        result["reason_code"] = "UNEXPECTED_TOOL_CALL"
    elif trace["hermes_exit_code"] != 0:
        result["reason_code"] = "MISSING_TERMINAL_EXIT_CODE"
    elif not isinstance(terminal[-1].get("text"), str) or terminal[-1]["text"].strip() != SMOKE_REPLY:
        result["reason_code"] = "UNEXPECTED_SMOKE_REPLY"
    else:
        result.update(status="PASS", reason_code="VERIFIED_API_RESPONSE")
    return result


def supervised(command: list[str], directory: Path, env: dict, timeout: int) -> tuple[int, float]:
    """Leave raw output private; allow descendants time to clean up on timeout."""
    directory.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with (directory / "stdout.txt").open("w", encoding="utf-8") as out, \
         (directory / "stderr.txt").open("w", encoding="utf-8") as err:
        proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=out, stderr=err,
                                start_new_session=True)
        canceled = None

        def interrupted(signum, _frame):
            nonlocal canceled
            canceled = canceled or signum

        handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGINT)}
        try:
            while proc.poll() is None and not canceled and time.monotonic() - started < timeout:
                try:
                    proc.wait(timeout=0.25)
                except subprocess.TimeoutExpired:
                    pass
            if canceled or proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=35)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=5)
                code = 128 + canceled if canceled else 124
            else:
                code = proc.returncode
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
    return code, time.monotonic() - started


def cleanup(binary: str, run_root: Path) -> bool:
    """Final fallback for interrupted wrappers. Each home belongs to this run."""
    ok = True
    for home in sorted((run_root / "private" / "homes").glob("*")):
        if home.is_symlink() or not home.is_dir():
            ok = False
            continue
        try:
            receipt = home / "ci-cleanup.json"
            if not receipt.is_symlink() and json.loads(receipt.read_text()).get("cleanup_confirmed") is True:
                continue
        except (OSError, ValueError, AttributeError):
            pass
        receipt = cleanup_home(Path(binary), home)
        ok = ok and receipt.get("cleanup_confirmed") is True
    if not ok:
        state_path = run_root / "ci-state.json"
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state.update(status="TIMEOUT", diagnostic_code="GATEWAY_CLEANUP_UNCONFIRMED")
            store(state_path, state)
        except (OSError, ValueError, AttributeError):
            pass
    return ok


def execute(args: argparse.Namespace, state: dict) -> int:
    root = args.output.resolve()
    state["execution_started"] = True
    state["python_version"] = platform.python_version()
    store(root / "ci-state.json", state)
    started = time.monotonic()
    try:
        state["cli_compatible"], state["hermes_version"] = check_cli(args.hermes, root / "private")
        if not state["cli_compatible"]:
            state.update(status="ERROR", diagnostic_code="HERMES_CLI_INCOMPATIBLE")
            return 2
        if args.mode == "check":
            state.update(status="COMPLETE", diagnostic_code="NO_INFERENCE_REQUESTED")
            return 0
        if not args.approve_paid_api:
            state.update(status="ERROR", diagnostic_code="PAID_OPT_IN_REQUIRED")
            return 2
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            state.update(status="ERROR", diagnostic_code="MISSING_OPENAI_API_KEY")
            return 2
        if os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/") != "https://api.openai.com/v1":
            state.update(status="ERROR", diagnostic_code="NON_DIRECT_API_ENDPOINT")
            return 2
        env = os.environ.copy()
        env.update(HIERGOAL_REAL_HERMES=str(Path(args.hermes).resolve()),
                   HIERGOAL_CI_HOMES=str(root / "private" / "homes"),
                   HIERGOAL_HERMES_TIMEOUT_SECONDS="120",
                   OPENAI_BASE_URL="https://api.openai.com/v1", TERMINAL_ENV="local",
                   HERMES_GATEWAY_NO_SUPERVISE="1")
        wrapper = ROOT / "scripts/ci_hermes.py"
        smoke_dir = root / "raw" / "smoke"
        smoke_dir.mkdir(parents=True, exist_ok=True)
        prompt = smoke_dir / "prompt.txt"
        prompt.write_text("Reply with exactly " + SMOKE_REPLY + ". Do not use tools.\n", encoding="utf-8")
        command_args = argparse.Namespace(hermes=str(wrapper), backend="luna", model=LUNA_MODEL, max_turns=1)
        command = hermes_arguments(command_args, smoke_dir, prompt, "")
        code, elapsed = supervised(command, smoke_dir, env, 160)
        smoke = inspect_smoke(smoke_dir / "stdout.txt", code, elapsed)
        store(root / "smoke.json", smoke)
        state["connection_status"] = smoke["status"]
        store(root / "ci-state.json", state)
        if smoke["status"] != "PASS":
            state.update(status="TIMEOUT" if code == 124 else "ERROR", diagnostic_code=smoke["reason_code"])
            return 1
        if args.mode == "smoke":
            state.update(status="COMPLETE", diagnostic_code="VERIFIED_API_RESPONSE")
            return 0
        remaining = args.soft_budget_usd - smoke["estimated_visible_usd"]
        if remaining <= 0:
            state.update(status="ERROR", diagnostic_code="SOFT_BUDGET_EXHAUSTED_AFTER_SMOKE")
            return 1
        env["HIERGOAL_HERMES_TIMEOUT_SECONDS"] = "540"
        command = [sys.executable, "-m", "hiergoal.benchmark", "--run", "--backend", "luna",
                   "--hermes", str(wrapper), "--approve-paid-api", "--ack-unsandboxed",
                   "--output", str(root / "raw" / "benchmarks"),
                   "--total-soft-budget-usd", str(remaining),
                   "--per-case-soft-budget-usd", str(min(1.5, remaining)),
                   "--max-calls", "12", "--max-turns", "18", "--max-replans", "2",
                   "--timeout-seconds", "600", "--seed", "1729"]
        if args.mode == "pilot":
            command += ["--cases", "legacy", "--repetitions", "1"]
        else:
            command += ["--repetitions", "2"]
        code, _ = supervised(command, root / "raw" / "batch-process", env,
                             state["limits"]["batch_timeout_seconds"])
        state["controller_exit_code"] = code
        if code in (124, 137, 143):
            state.update(status="TIMEOUT", diagnostic_code="BATCH_WALL_TIME_LIMIT_OR_CANCELED")
        elif code:
            state.update(status="ERROR", diagnostic_code="BATCH_HALTED_REVIEW_EVIDENCE")
        else:
            state.update(status="COMPLETE", diagnostic_code="BATCH_RETURNED_CHECK_EMPIRICAL_RESULT")
        return 0 if code == 0 else 1
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        # Never log exception messages: API errors may contain credentials or prompts.
        state.update(status="ERROR", diagnostic_code="CI_RUNNER_ERROR")
        return 2
    finally:
        state.update(finished_at=now(), elapsed_seconds=round(time.monotonic() - started, 3))
        store(root / "ci-state.json", state)


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--mode", choices=("check", "smoke", "pilot", "benchmark"), default="check")
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--hermes", default=os.getenv("HIERGOAL_REAL_HERMES", "hermes"))
    cli.add_argument("--soft-budget-usd", type=float, default=1.0)
    cli.add_argument("--approve-paid-api", action="store_true")
    cli.add_argument("--prepare", action="store_true")
    cli.add_argument("--cleanup", action="store_true")
    args = cli.parse_args()
    if not math.isfinite(args.soft_budget_usd) or not 0 < args.soft_budget_usd <= 12:
        cli.error("soft-budget-usd must be finite and between 0 (exclusive) and 12")
    args.output = args.output.resolve()
    args.hermes = shutil.which(args.hermes) or args.hermes
    if args.cleanup:
        raise SystemExit(0 if cleanup(args.hermes, args.output) else 1)
    path = args.output / "ci-state.json"
    if args.prepare or not path.exists():
        if path.exists():
            cli.error("This output already has a CI state; use a new run directory")
        state = metadata(args.mode, args.soft_budget_usd)
        store(path, state)
    else:
        state = json.loads(path.read_text(encoding="utf-8"))
        if (state.get("execution_started") or state.get("mode") != args.mode
                or state.get("soft_budget_usd") != args.soft_budget_usd):
            cli.error("Existing CI state has different inputs or was already executed")
    if args.prepare:
        return
    code = execute(args, state)
    print(json.dumps({"mode": args.mode, "status": state["status"],
                      "diagnostic_code": state["diagnostic_code"],
                      "connection_status": state["connection_status"]}))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
