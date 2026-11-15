# SPDX-License-Identifier: Apache-2.0
"""Run ONE real Hermes Agent task. Paid calls occur only without --dry-run.

SECURITY: Hermes terminal/file tools are not OS-sandboxed by this harness.
Use a disposable VM/container or a dedicated low-privilege OS account, and
never run it against private repositories or production data.
"""
import argparse
import difflib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from stream_report import parse_events

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "ledger_release"
EVALUATOR = ROOT / "evaluation"

PROMPT = """You are Hermes Agent repairing the small Python project in this workspace.

IMMUTABLE USER GOAL: meet every requirement in README.md, without removing tests.
Create RESEARCH_PLAN.md BEFORE changing code. It must show three linked horizons:
LONG-TERM goal, MID-TERM milestones, SHORT-TERM executable subgoals. Each short-term
goal needs a checkable acceptance criterion and parent milestone.

Use Hermes' built-in todo_list tool to register an actual nested task tree,
not just prose: one LONG-TERM parent item, MID-TERM children, and SHORT-TERM
grandchildren with stable id/parent references. Set statuses honestly. After
each tested step, update todo_list (prefer merge=True). If a leaf fails,
mark it cancelled and register a revised leaf with the same parent. Keep only
one item in_progress. RESEARCH_PLAN.md is the durable human-readable record.

Execute the planned steps with the tools available to you, recording actual
command/test evidence in RESEARCH_PLAN.md. When an attempt fails or new evidence
invalidates a plan, revise the smallest affected subgoal and record the reason.
Keep the long-term user objective unchanged. Do not edit outside this directory,
install packages, use the network, read secrets or touch any Git remote.

Run visible tests with python -m unittest discover -s tests -v.
In the final response report achieved and unmet requirements with evidence.
A separate independent evaluator exists, but you cannot claim to pass it.
"""


def check_tests(workspace: Path, directory: Path, seconds: int = 30, minimum_tests: int = 1) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(workspace) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    command = [sys.executable, "-m", "unittest", "discover", "-s", str(directory), "-p", "test*.py", "-v"]
    try:
        result = subprocess.run(command, cwd=workspace, env=env,
                                text=True, capture_output=True, timeout=seconds)
        log = result.stdout + "\n" + result.stderr
        match = re.search(r"\bRan\s+(\d+)\s+tests?\s+in\b", log)
        tests_run = int(match.group(1)) if match else None
        return {"ok": result.returncode == 0 and tests_run is not None and tests_run >= minimum_tests,
                "returncode": result.returncode, "tests_run": tests_run,
                "minimum_tests": minimum_tests, "log": log[-20000:]}
    except (subprocess.TimeoutExpired, OSError) as error:
        return {"ok": False, "returncode": None, "tests_run": None, "minimum_tests": minimum_tests, "log": str(error)}


def diff_workspace(before: Path, after: Path) -> str:
    chunks = []
    for source in sorted(before.rglob("*")):
        if not source.is_file() or "__pycache__" in source.parts:
            continue
        rel = source.relative_to(before)
        updated = after / rel
        if source.suffix not in (".py", ".md"):
            continue
        old = source.read_text(encoding="utf-8").splitlines(keepends=True)
        new = updated.read_text(encoding="utf-8").splitlines(keepends=True) if updated.exists() else []
        chunks.extend(difflib.unified_diff(old, new, fromfile="original/" + str(rel),
                                           tofile="workspace/" + str(rel)))
    return "".join(chunks)


def run(args: argparse.Namespace) -> Path:
    if not args.dry_run and not shutil.which(args.hermes):
        raise RuntimeError("Hermes CLI is not installed or not on PATH. Run 'hermes doctor' after installing it.")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    directory = (args.output / ("ledger-release-" + run_id)).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    workspace = directory / "workspace"
    shutil.copytree(FIXTURE, workspace)
    prompt_file = directory / "query.txt"
    prompt_file.write_text(PROMPT, encoding="utf-8")
    pre = check_tests(workspace, FIXTURE / "tests", minimum_tests=3)
    (directory / "pretest.log").write_text(pre["log"], encoding="utf-8")
    if pre["tests_run"] is None or pre["tests_run"] < 3:
        raise RuntimeError("Pretest discovery failed: the immutable visible tests were not executed.")
    if pre["ok"]:
        raise RuntimeError("Fixture already passes visible tests: no repair task to benchmark.")

    command = [
        args.hermes, "chat", "--provider", "openai-api", "--model", args.model,
        "--reasoning", args.reasoning, "--toolsets", "file,terminal,todo",
        "--ignore-user-config", "--ignore-rules", "--source", "hiergoal-lab",
        "--in", str(workspace), "--format", "stream-json",
        "--max-turns", str(args.max_turns), "--query-file", str(prompt_file), "--oneshot",
    ]
    (directory / "invocation.json").write_text(
        json.dumps(command, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.dry_run:
        print("DRY RUN (no API call):", directory)
        print("Command:", json.dumps(command, ensure_ascii=False))
        return directory

    stream = directory / "hermes.stream.jsonl"
    diagnostics = directory / "hermes.stderr.log"
    start = time.monotonic()
    timed_out = False
    with stream.open("w", encoding="utf-8") as out, diagnostics.open("w", encoding="utf-8") as err:
        proc = subprocess.Popen(command, cwd=workspace, stdout=out, stderr=err)
        try:
            proc.wait(timeout=args.timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            # Request interruption first; if the gateway is detached, the backend
            # MAY still continue. Check the Hermes session status afterwards.
            try:
                proc.send_signal(signal.SIGINT if os.name != "nt" else signal.SIGTERM)
                proc.wait(timeout=10)
            except (subprocess.TimeoutExpired, OSError):
                proc.kill()
                proc.wait()
    seconds = round(time.monotonic() - start, 3)

    # Grade against original tests outside the editable workspace, not agent-edited copies.
    visible = check_tests(workspace, FIXTURE / "tests", minimum_tests=3)
    independent = check_tests(workspace, EVALUATOR, minimum_tests=6)
    original_tests_unchanged = (
        (workspace / "tests" / "test_visible.py").is_file()
        and (workspace / "tests" / "test_visible.py").read_bytes()
        == (FIXTURE / "tests" / "test_visible.py").read_bytes()
    )
    (directory / "visible_tests.log").write_text(visible["log"], encoding="utf-8")
    (directory / "independent_tests.log").write_text(independent["log"], encoding="utf-8")
    (directory / "changes.diff").write_text(diff_workspace(FIXTURE, workspace), encoding="utf-8")
    trace = parse_events(stream)
    plan = workspace / "RESEARCH_PLAN.md"
    plan_text = plan.read_text(encoding="utf-8") if plan.is_file() else ""
    has_horizons = all(term in plan_text.upper() for term in ("LONG", "MID", "SHORT"))
    inp, out = trace["tokens_input"], trace["tokens_output"]
    estimate = round((inp * 0.10 + out * 0.50) / 1000000, 8) if (
        isinstance(inp, int) and isinstance(out, int) and inp >= 0 and out >= 0) else None

    if timed_out or not trace["terminal_result_seen"] or trace["invalid_json_lines"]:
        verdict = "UNCERTAIN"
    elif (proc.returncode == 0 and trace["hermes_exit_code"] == 0
          and visible["ok"] and independent["ok"] and original_tests_unchanged):
        verdict = "PASS"
    else:
        verdict = "FAIL"

    summary = {
        "study": "single-case Hermes observational run; no comparator",
        "model_requested": args.model, "provider": "openai-api",
        "reasoning": args.reasoning, "task": "ledger-release",
        "verdict": verdict, "pretest_pass": pre["ok"],
        "visible_tests_pass": visible["ok"], "independent_tests_pass": independent["ok"],
        "visible_tests_run": visible["tests_run"], "independent_tests_run": independent["tests_run"],
        "original_visible_tests_unchanged": original_tests_unchanged,
        "plan_file_present": plan.exists(), "three_horizons_detected": has_horizons,
        "process_exit_code": proc.returncode, "timed_out": timed_out,
        "elapsed_seconds": seconds, "host_os": platform.platform(),
        "host_python": sys.version.split()[0], "host_arch": platform.machine(),
        "estimated_visible_model_cost_usd": estimate,
        "cost_warning": "Nominal standard Luna rates, not billed total or spending cap. Usage may exclude auxiliary calls; cache and long-context rates differ.",
        "timeout_warning": "Terminating the CLI may not cancel a detached Hermes gateway run; verify the session after timeout." if timed_out else None,
        "stream": trace,
    }
    (directory / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    return directory


def main():
    p = argparse.ArgumentParser(description="Run a real Hermes Agent task and independently grade it")
    p.add_argument("--hermes", default="hermes")
    p.add_argument("--model", default="gpt-6-luna")
    p.add_argument("--reasoning", default="low", choices=["none", "low", "medium", "high"])
    p.add_argument("--max-turns", type=int, default=20)
    p.add_argument("--timeout-seconds", type=int, default=900)
    p.add_argument("--output", type=Path, default=ROOT / "runs")
    p.add_argument("--dry-run", action="store_true", help="Only copy fixture and print Hermes command; no API use")
    args = p.parse_args()
    if args.max_turns < 1 or args.timeout_seconds < 15:
        p.error("--max-turns must be >=1, --timeout-seconds >=15")
    try:
        run_dir = run(args)
    except (RuntimeError, OSError) as exc:
        p.error(str(exc))
    print("Run directory:", run_dir)
    if not args.dry_run:
        print((run_dir / "summary.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
