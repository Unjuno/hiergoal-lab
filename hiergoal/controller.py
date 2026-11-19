# SPDX-License-Identifier: Apache-2.0
"""Real Hermes hierarchy controller using a restricted OpenCode ACP free-model provider.

Dry-run / offline integration tests do not invoke network inference. Real runs
require the community opencode-free-acp provider and an isolated Hermes profile.
No paid-provider fallback is configured by this project.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from hiergoal.core import (
    GATES, GATE_DESCRIPTIONS, ROOT_GOAL, PlanError,
    next_leaf, parse_object, replace_failed_leaf, update_rollups, validate_plan,
)
from scripts.stream_report import parse_events
from hiergoal.provenance import capture_provenance, protocol_manifest
from hiergoal.cases import CASE_IDS, CASE_DESCRIPTION, apply_case

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "ledger_release"
EVALUATION = ROOT / "evaluation"
PROVIDER = "opencode-free-acp"
PROFILE = "hiergoal-free"
DEFAULT_MODEL = "opencode/glm-5.3-flash-free"
# Exact allowlist from community opencode-free-acp v0.4.0; never infer free from a suffix.
LUNA_MODEL = "gpt-6-luna"
LUNA_INPUT_RATE_PER_MTOK = 0.10
LUNA_OUTPUT_RATE_PER_MTOK = 0.50

FREE_MODELS = (
    DEFAULT_MODEL,
    "opencode/deepseek-v4.1-flash-free",
    "opencode/mimo-v2.6-flash-free",
    "opencode/nemotron-3.5-super-vl-free",
    "opencode/nemotron-3.5-lightning-free",
    "opencode/beam-free",
    "opencode/big-pickle",
)

def resolve_route(args: argparse.Namespace) -> tuple[str, str | None, str]:
    """Pick an explicit, non-fallback inference route."""
    backend = getattr(args, "backend", "free")
    model = getattr(args, "model", None)
    if backend == "free":
        chosen = model or DEFAULT_MODEL
        if chosen not in FREE_MODELS:
            raise ValueError("Free backend requires an allowlisted free model")
        return (PROVIDER, PROFILE, chosen)
    if backend == "luna":
        chosen = model or LUNA_MODEL
        if chosen != LUNA_MODEL:
            raise ValueError("Luna backend only permits gpt-6-luna")
        return ("openai-api", None, chosen)
    raise ValueError("Unsupported backend")


def hermes_arguments(args: argparse.Namespace, workspace: Path, prompt_file: Path,
                     toolsets: str) -> list[str]:
    provider, profile, model = resolve_route(args)
    command = [args.hermes]
    if profile:
        command += ["-p", profile]
    command += ["chat", "--provider", provider, "--model", model]
    if provider == "openai-api":
        command += ["--reasoning", "low", "--ignore-user-config"]
    command += ["--toolsets", toolsets, "--ignore-rules",
                "--in", str(workspace), "--format", "stream-json",
                "--max-turns", str(args.max_turns),
                "--source", "hiergoal-lab",
                "--query-file", str(prompt_file), "--oneshot"]
    return command


def verify_free_profile() -> Path:
    """Fail closed unless the isolated Hermes profile has no paid fallback chain."""
    if os.environ.get("HERMES_HOME"):
        raise ExperimentStopped("Unset HERMES_HOME: the free-only profile is under ~/.hermes/profiles", uncertain=False)
    config = Path.home() / ".hermes" / "profiles" / PROFILE / "config.yaml"
    if not config.is_file():
        raise ExperimentStopped("Missing free-only profile. Run scripts/setup_opencode_free.sh", uncertain=False)
    source = config.read_text(encoding="utf-8")
    if "# HierGoal isolated free-only configuration" not in source:
        raise ExperimentStopped("Unrecognized profile config; refusing possible paid fallback", uncertain=False)
    if not re.search(r"(?m)^\s*provider:\s*opencode-free-acp\s*$", source):
        raise ExperimentStopped("Free profile provider is not opencode-free-acp", uncertain=False)
    if not re.search(r"(?m)^fallback_providers:[ \t]*\[[ \t]*\][ \t]*$", source):
        raise ExperimentStopped("Free profile must have fallback_providers: []", uncertain=False)
    for line in source.splitlines():
        if line.strip().startswith("fallback_providers:"):
            # String comparison avoids regex backtracking accepting an unsafe value.
            if line.strip() != "fallback_providers: []":
                raise ExperimentStopped("Unexpected nested fallback chain", uncertain=False)
    if re.search(r"(?m)^fallback_model\s*:", source):
        raise ExperimentStopped("Legacy paid fallback must be absent", uncertain=False)
    return config


class ExperimentStopped(RuntimeError):
    """A bounded run stopped before a verified completion."""
    def __init__(self, reason: str, uncertain: bool = True):
        super().__init__(reason)
        self.uncertain = uncertain


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def grade(workspace: Path, checks: list[str], seconds: int = 30) -> dict:
    """Run owner-controlled acceptance methods from outside the agent workspace."""
    if not checks or any(c not in GATES for c in checks):
        raise ValueError("Unknown or empty deterministic gate")
    names = ["test_release.IndependentAcceptance." + GATES[c] for c in checks]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(EVALUATION), str(workspace)])
    args = [sys.executable, "-m", "unittest", "-v", *names]
    try:
        result = subprocess.run(
            args, cwd=EVALUATION, env=env, timeout=seconds,
            capture_output=True, text=True
        )
        output = result.stdout + "\n" + result.stderr
        match = re.search(r"\bRan\s+(\d+)\s+tests?\s+in\b", output)
        count = int(match.group(1)) if match else None
        return {
            "passed": result.returncode == 0 and count == len(checks),
            "tests_run": count, "expected_tests": len(checks),
            "exit_code": result.returncode, "output": output[-12000:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"passed": False, "tests_run": None, "expected_tests": len(checks),
                "exit_code": None, "output": str(exc)}


def visible_grade(workspace: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(workspace), env.get("PYTHONPATH", "")])
    try:
        proc = subprocess.run([sys.executable, "-m", "unittest", "discover",
                               "-s", str(FIXTURE / "tests"), "-v"],
                              cwd=EVALUATION, env=env, capture_output=True, text=True,
                              timeout=30)
        result = proc.stdout + "\n" + proc.stderr
        match = re.search(r"\bRan\s+(\d+)\s+tests?\s+in\b", result)
        count = int(match.group(1)) if match else None
        return {"passed": proc.returncode == 0 and count == 3,
                "tests_run": count, "exit_code": proc.returncode, "output": result[-12000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"passed": False, "tests_run": None, "exit_code": None, "output": str(exc)}


def original_visible_tests_unchanged(workspace: Path) -> bool:
    candidate = workspace / "tests" / "test_visible.py"
    source = FIXTURE / "tests" / "test_visible.py"
    return candidate.is_file() and candidate.read_bytes() == source.read_bytes()


def build_plan_prompt() -> str:
    gate_text = json.dumps(GATE_DESCRIPTIONS, indent=2, ensure_ascii=False)
    return (
        "ROLE=PLANNER\nYou are creating an executable goal hierarchy for Hermes Agent.\n"
        "Do not use tools, edit files, or execute commands. Return a standalone JSON object only.\n"
        "The user's long-term goal is IMMUTABLE:\n" + ROOT_GOAL + "\n\n"
        "The owner supplies all independently verifiable acceptance gates below. "
        "Do not invent checks or omit any. Assign EACH gate to exactly ONE short-term leaf.\n"
        + gate_text + "\n"
        "JSON schema: {\"milestones\":[{\"id\":\"M1\",\"title\":\"...\","
        "\"subgoals\":[{\"id\":\"S1\",\"instruction\":\"...\","
        "\"checks\":[\"invalid_rows\"],\"depends_on\":[]}]}]}\n"
        "Create 2 to 4 mid-term milestones with unique M1..M4 IDs, and 3 to 8 "
        "short-term executable leaves with unique S1..S8 IDs. Each leaf must have "
        "a specific, self-contained coding instruction and dependency IDs. "
        "A dependency must refer to another leaf; dependencies must be acyclic. "
        "Do not include the root goal as an editable field. Return JSON, no markdown."
    )


def build_execute_prompt(state: dict, leaf: dict) -> str:
    milestone = next(m["title"] for m in state["milestones"] if m["id"] == leaf["parent"])
    checks = {c: GATE_DESCRIPTIONS[c] for c in leaf["checks"]}
    return (
        "ROLE=EXECUTE\nYou are the actual Hermes coding agent. Operate ONLY in "
        "the current workspace. An independent Python controller executes this "
        "leaf of an approved 3-level goal tree and will verify the result.\n"
        "IMMUTABLE LONG-TERM GOAL:\n" + state["root"]["goal"] + "\n"
        "MID-TERM MILESTONE: " + leaf["parent"] + " " + milestone + "\n"
        "CURRENT SHORT-TERM GOAL: " + leaf["id"] + " " + leaf["instruction"] + "\n"
        "DETERMINISTIC ACCEPTANCE CONTRACT: "
        + json.dumps(checks, ensure_ascii=False) + "\n"
        "DEPENDENCIES ALREADY COMPLETED: " + ", ".join(leaf["depends_on"]) + "\n"
        "Read README.md and relevant code; make the smallest correct code change. "
        "Do not modify or delete any tests, use the network, install packages, "
        "read secrets, touch Git remotes or edit outside this working directory. "
        "You can call terminal and file tools and run visible tests. "
        "If visible tests fail due to OTHER pending goals, report that rather than "
        "altering the immutable objective. Use native todo_list to record the "
        "current leaf, with its mid-term milestone parent, and mark work complete "
        "only after evidence. The controller, not your own assertion, decides "
        "whether this leaf passes. Give a concise factual completion summary."
    )


def build_replan_prompt(state: dict, leaf: dict, grade_result: dict) -> str:
    return (
        "ROLE=REPLAN\nNo tools or code edits. A deterministic evaluator rejected "
        "a short-term task. Revise ONLY that short-term instruction, without changing "
        "the user-owned long-term objective, its parent, dependencies, or acceptance gates.\n"
        "ROOT: " + state["root"]["goal"] + "\n"
        "FAILED LEAF: " + json.dumps(
            {k: leaf[k] for k in ("id", "parent", "instruction", "checks", "depends_on")},
            ensure_ascii=False
        ) + "\nEVALUATOR OUTPUT:\n" + grade_result["output"][-3500:] + "\n"
        "Return a standalone JSON object with exactly these two nonempty strings: "
        "{\"diagnosis\":\"specific failure cause\",\"revised_instruction\":\"specific "
        "alternative implementation strategy\"}. Do not return code fences."
    )


class Controller:
    def _acquire_lock(self) -> None:
        """Prevent two controllers from mutating one run concurrently (POSIX flock)."""
        self._lock_handle = (self.directory / ".controller.lock").open("a+")
        try:
            fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._lock_handle.close()
            self._lock_handle = None
            raise ExperimentStopped("Another controller currently owns this run", uncertain=True) from exc

    def close(self) -> None:
        handle = getattr(self, "_lock_handle", None)
        if handle is not None and not handle.closed:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()
        self._lock_handle = None

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.route_provider, self.route_profile, self.route_model = resolve_route(args)
        self._lock_handle = None
        if args.resume:
            self.directory = args.resume.resolve()
            self.workspace = self.directory / "workspace"
            if not self.workspace.is_dir() or not (self.directory / "state.json").is_file():
                raise ExperimentStopped("Resume directory has no valid state", uncertain=False)
            self._acquire_lock()
            self.state = json.loads((self.directory / "state.json").read_text(encoding="utf-8"))
            if self.state["root"]["goal"] != ROOT_GOAL:
                self.close()
                raise ExperimentStopped("Immutable goal does not match current protocol", uncertain=False)
            self.records = json.loads((self.directory / "records.json").read_text(encoding="utf-8"))
            if (self.records.get("provider"), self.records.get("model"), self.records.get("profile")) != (
                self.route_provider, self.route_model, self.route_profile
            ):
                self.close()
                raise ExperimentStopped("Cannot resume a run from another model/provider/profile", uncertain=False)
            if self.records.get("case_id", "legacy") != args.case:
                self.close()
                raise ExperimentStopped("Cannot resume with a different benchmark case", uncertain=False)
            if self.records.get("outcome") == "PASS":
                self.close()
                raise ExperimentStopped("This run is already complete; do not resume it", uncertain=False)
            prior_protocol = self.records.get("provenance", {}).get("protocol_id")
            if not prior_protocol or prior_protocol != protocol_manifest(ROOT)["protocol_id"]:
                self.close()
                raise ExperimentStopped(
                    "Experiment source or evaluator changed since this run began; "
                    "start a fresh run instead of mixing protocol versions.", uncertain=False
                )
            potentially_active = any(
                call.get("status") in ("started", "running", "incomplete")
                or call.get("timed_out") is True
                for call in self.records.get("calls", [])
            ) or any(leaf["status"] == "running" for leaf in self.state["leaves"].values())
            if potentially_active and not args.confirm_stopped:
                self.close()
                raise ExperimentStopped(
                    "An interrupted Hermes call may still be running. Verify it has stopped, "
                    "then explicitly pass --confirm-stopped when resuming.", uncertain=True
                )
            if potentially_active:
                for call in self.records.get("calls", []):
                    if call.get("status") in ("started", "running", "incomplete"):
                        call["status"] = "operator_confirmed_stopped"
                self.records.setdefault("recovery_notes", []).append(
                    "Operator confirmed prior invocation stopped before resumption."
                )
            for leaf in self.state["leaves"].values():
                if leaf["status"] == "running":
                    leaf["status"] = "pending"
        else:
            run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
            self.directory = (args.output / ("hiergoal-" + run_id)).resolve()
            self.directory.mkdir(parents=True, exist_ok=False)
            self._acquire_lock()
            self.workspace = self.directory / "workspace"
            shutil.copytree(FIXTURE, self.workspace)
            apply_case(self.workspace, args.case)
            self.state = None
            self.records = {"experiment": "hermes-hiergoal-v1",
                            "backend": getattr(args, "backend", "free"),
                            "case_id": args.case,
                            "case_description": CASE_DESCRIPTION[args.case],
                            "provider": self.route_provider,
                            "model": self.route_model, "profile": self.route_profile,
                            "mode": "controlled-hierarchical-single-case", "calls": [],
                            "provenance": capture_provenance(ROOT),
                            "estimated_visible_usd": (0.0 if self.route_provider == "openai-api" else None),
                            "token_usage_available": False,
                            "pricing": ("Indicative Standard Luna input $0.10/output $0.50 per 1M tokens; "
                                        "actual billing is not measured" if self.route_provider == "openai-api"
                                        else "OpenCode catalog lists this model as free; billing not observed"),
                            "timed_out": False, "outcome": "NOT_RUN", "halt_reason": None}
            pre = grade(self.workspace, list(GATES))
            save_json(self.directory / "initial_grading.json", pre)
            if pre["passed"] or pre["tests_run"] != len(GATES):
                self.close()
                raise ExperimentStopped("Initial fixture not reliably broken or grader failed", uncertain=False)
        self._save()

    def _save(self) -> None:
        if self.state is not None:
            save_json(self.directory / "state.json", self.state)
        save_json(self.directory / "records.json", self.records)

    def _record_gate(self, name: str, checks: list[str]) -> dict:
        outcome = grade(self.workspace, checks)
        save_json(self.directory / ("gate-" + name + ".json"), outcome)
        return outcome

    def _call_hermes(self, role: str, prompt: str, toolsets: str) -> dict:
        if len(self.records["calls"]) >= self.args.max_calls:
            raise ExperimentStopped("max-calls guard reached; no further requests")
        if (self.route_provider == "openai-api" and
                self.records["estimated_visible_usd"] >= self.args.pilot_budget_usd):
            raise ExperimentStopped("Estimated Luna budget guard reached")
        index = len(self.records["calls"]) + 1
        tag = "%02d-%s" % (index, role)
        prompt_path = self.directory / (tag + ".prompt.txt")
        stdout_path = self.directory / (tag + ".stream.jsonl")
        stderr_path = self.directory / (tag + ".stderr.txt")
        prompt_path.write_text(prompt, encoding="utf-8")
        # Free ACP needs its dedicated profile. Luna intentionally disables user
        # config and uses only the direct OpenAI API provider and .env credentials.
        command = hermes_arguments(self.args, self.workspace, prompt_path, toolsets)
        save_json(self.directory / (tag + ".invocation.json"), {"argv": command})
        # Write-ahead record: interrupted calls must count against max_calls
        # and must not be silently replayed on --resume.
        self.records["calls"].append({
            "index": index, "role": role, "status": "started",
            "tool_calls": None, "terminal_result_seen": False
        })
        self._save()
        elapsed = time.monotonic()
        timed_out = False
        with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
            try:
                proc = subprocess.Popen(command, cwd=self.workspace, stdout=out, stderr=err)
            except OSError as exc:
                self.records["calls"][-1]["status"] = "launch_failed"
                self.records["calls"][-1]["launch_error_type"] = type(exc).__name__
                self._save()
                raise ExperimentStopped(
                    "Hermes invocation could not be started; inspect executable and permissions",
                    uncertain=False
                ) from exc
            self.records["calls"][-1]["status"] = "running"
            self.records["calls"][-1]["pid"] = proc.pid
            self._save()
            try:
                proc.wait(timeout=self.args.timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    proc.send_signal(signal.SIGTERM)
                    proc.wait(timeout=8)
                except (subprocess.TimeoutExpired, OSError):
                    proc.kill()
                    proc.wait()
        duration = time.monotonic() - elapsed
        trace = parse_events(stdout_path)
        result_text = None
        for line in stdout_path.read_text(encoding="utf-8").splitlines():
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict) and message.get("type") == "result":
                result_text = message.get("text")
        inbound = trace["tokens_input"]
        outbound = trace["tokens_output"]
        # The ACP plugin reports usage=None; zero counts are not measured zero.
        # Billing is not inferred from missing or zero token counters.
        measured_tokens = (isinstance(inbound, int) and isinstance(outbound, int)
                           and inbound > 0 and outbound > 0)
        charge = None
        if self.route_provider == "openai-api" and measured_tokens:
            charge = round((
                inbound * LUNA_INPUT_RATE_PER_MTOK
                + outbound * LUNA_OUTPUT_RATE_PER_MTOK
            ) / 1000000, 8)
        entry = {"index": index, "role": role, "exit_code": proc.returncode,
                 "hermes_exit_code": trace["hermes_exit_code"],
                 "terminal_result_seen": trace["terminal_result_seen"],
                 "elapsed_seconds": round(duration, 3), "timed_out": timed_out,
                 "tokens_input": inbound if measured_tokens else None,
                 "tokens_output": outbound if measured_tokens else None,
                 "token_usage_measured": measured_tokens,
                 "estimated_visible_usd": charge, "tool_calls": trace["tool_calls"],
                 "nested_todo_observed": trace["verified_nested_todo_result_observed"],
                 "session_id": trace["session_id"], "invalid_json_lines": trace["invalid_json_lines"]}
        entry["status"] = ("finished" if trace["terminal_result_seen"]
                           and not timed_out and not trace["invalid_json_lines"]
                           else "incomplete")
        self.records["calls"][-1] = entry
        if self.route_provider == "openai-api" and charge is not None:
            self.records["estimated_visible_usd"] = round(
                self.records["estimated_visible_usd"] + charge, 8)
            self.records["token_usage_available"] = True
        if timed_out:
            self.records["timed_out"] = True
        self._save()
        if timed_out or not trace["terminal_result_seen"] or trace["invalid_json_lines"]:
            raise ExperimentStopped("Hermes timed out or returned an incomplete stream: " + tag)
        if proc.returncode != 0 or trace["hermes_exit_code"] != 0:
            raise ExperimentStopped("Hermes failed at " + tag + "; inspect stderr/stream", uncertain=False)
        if self.route_provider == "openai-api":
            if not measured_tokens:
                raise ExperimentStopped(
                    "Luna returned unmeasured tokens; stop before next billable request")
            if self.records["estimated_visible_usd"] >= self.args.pilot_budget_usd:
                raise ExperimentStopped(
                    "Estimated Luna pilot budget reached; no more requests")
        if not isinstance(result_text, str) or not result_text.strip():
            raise ExperimentStopped("Hermes provided no final response: " + tag)
        return {"text": result_text, "call": entry}

    def plan(self) -> None:
        payload = self._call_hermes("plan", build_plan_prompt(), "todo")
        try:
            self.state = validate_plan(parse_object(payload["text"]))
        except PlanError as exc:
            raise ExperimentStopped("Invalid model plan: " + str(exc), uncertain=False) from exc
        self.state["root"]["status"] = "active"
        self._save()

    def _replan_leaf(self, leaf: dict, grade_result: dict, *, cause: str) -> None:
        """Replace an evidence-failed leaf; retain the parent criteria and user-owned root."""
        leaf["status"] = "failed"
        leaf["history"].append({"action": "verification_failed",
                                "cause": cause, "checks": list(leaf["checks"])})
        update_rollups(self.state)
        self._save()
        if leaf["revision"] >= 1 or self.state["replans"] >= self.args.max_replans:
            raise ExperimentStopped("Gate failed after bounded replanning: " + leaf["id"],
                                    uncertain=False)
        message = self._call_hermes("replan-" + leaf["id"],
                                   build_replan_prompt(self.state, leaf, grade_result), "todo")
        try:
            revised = parse_object(message["text"])
            diagnosis = revised["diagnosis"]
            instruction = revised["revised_instruction"]
            if instruction.strip() == leaf["instruction"].strip():
                raise PlanError("Replanning instruction is unchanged")
            replace_failed_leaf(self.state, leaf["id"], instruction, diagnosis)
        except (KeyError, AttributeError, PlanError) as exc:
            raise ExperimentStopped("Invalid replan: " + str(exc), uncertain=False) from exc
        self._save()

    def _verify_parent_contracts(self) -> bool:
        """Re-run each parent's aggregate acceptance gates, not just child status."""
        for milestone in self.state["milestones"]:
            children = [leaf for leaf in self.state["leaves"].values()
                        if leaf["parent"] == milestone["id"]
                        and leaf["status"] != "superseded"]
            if not children or any(leaf["status"] != "completed" for leaf in children):
                raise ExperimentStopped("Parent has unfinished children: " + milestone["id"],
                                        uncertain=False)
            checks = list(dict.fromkeys(c for child in children for c in child["checks"]))
            result = self._record_gate("parent-" + milestone["id"], checks)
            milestone["verification"] = {
                "passed": result["passed"], "checks": checks,
                "tests_run": result["tests_run"],
                "evidence_file": "gate-parent-" + milestone["id"] + ".json",
            }
            milestone["status"] = "completed" if result["passed"] else "blocked"
            self._save()
            if result["passed"]:
                continue
            for child in children:
                diagnosis = self._record_gate("parent-" + milestone["id"] + "-diagnose-"
                                              + child["id"], child["checks"])
                if not diagnosis["passed"]:
                    self._replan_leaf(child, diagnosis,
                                      cause="parent_verification_detected_regression")
                    return False
            raise ExperimentStopped(
                "Parent gate failed though all child gates passed: " + milestone["id"],
                uncertain=True
            )
        update_rollups(self.state)
        self._save()
        return True

    def execute(self) -> None:
        if self.state is None:
            self.plan()
        while True:
            leaf = next_leaf(self.state)
            if leaf is None:
                if all(x["status"] == "completed" for x in self.state["leaves"].values()
                       if x["status"] != "superseded"):
                    if self._verify_parent_contracts():
                        break
                    continue
                raise ExperimentStopped("No executable leaf: goal tree is blocked", uncertain=False)
            before = self._record_gate(leaf["id"] + "-before", leaf["checks"])
            if before["passed"]:
                leaf["status"] = "completed"
                leaf["history"].append({
                    "action": "preverified", "gate_pass": True,
                    "evidence_file": "gate-" + leaf["id"] + "-before.json",
                })
                update_rollups(self.state)
                self._save()
                continue
            leaf["attempts"] += 1
            leaf["status"] = "running"
            self._save()
            self._call_hermes("execute-" + leaf["id"],
                              build_execute_prompt(self.state, leaf), "file,terminal,todo")
            after = self._record_gate(leaf["id"] + "-after", leaf["checks"])
            leaf["history"].append({"action": "executed", "gate_pass": after["passed"],
                                    "attempt": leaf["attempts"],
                                    "evidence_file": "gate-" + leaf["id"] + "-after.json"})
            if after["passed"]:
                leaf["status"] = "completed"
                update_rollups(self.state)
                self._save()
                continue
            self._replan_leaf(leaf, after, cause="leaf_verification_failed")

    def finish(self) -> dict:
        full = self._record_gate("final-independent", list(GATES))
        visible = visible_grade(self.workspace)
        save_json(self.directory / "final-visible.json", visible)
        unchanged = original_visible_tests_unchanged(self.workspace)
        self.records["final_independent"] = {"passed": full["passed"], "tests_run": full["tests_run"]}
        self.records["final_visible"] = {"passed": visible["passed"], "tests_run": visible["tests_run"]}
        self.records["original_visible_tests_unchanged"] = unchanged
        parent_verified = all(
            milestone["status"] == "completed"
            and isinstance(milestone.get("verification"), dict)
            and milestone["verification"].get("passed") is True
            and milestone["verification"].get("tests_run")
                == len(milestone["verification"].get("checks", []))
            for milestone in self.state["milestones"]
        )
        accepted = full["passed"] and visible["passed"] and unchanged and parent_verified
        self.records["parent_acceptance_verified"] = parent_verified
        self.records["outcome"] = "PASS" if accepted else "FAIL"
        self.state["root"]["status"] = "completed" if accepted else "blocked"
        self._save()
        return self.records

    def abort(self, error: ExperimentStopped) -> None:
        self.records["outcome"] = "UNCERTAIN" if error.uncertain else "FAIL"
        self.records["halt_reason"] = str(error)
        if self.state:
            self.state["root"]["status"] = "blocked"
        self._save()


def run(args: argparse.Namespace) -> int:
    try:
        route_provider, route_profile, route_model = resolve_route(args)
    except ValueError as exc:
        print("Invalid route:", exc, file=sys.stderr)
        return 2
    if args.dry_run:
        with tempfile.TemporaryDirectory() as tmp:
            temporary_workspace = Path(tmp) / "workspace"
            shutil.copytree(FIXTURE, temporary_workspace)
            apply_case(temporary_workspace, args.case)
            initial = grade(temporary_workspace, list(GATES))
        if initial["passed"] or initial["tests_run"] != len(GATES):
            print("ERROR: selected case is not a valid failing test case", file=sys.stderr)
            return 2
        print("DRY RUN PASS: source fixture fails the independent tests.")
        print("Validated case:", args.case, CASE_DESCRIPTION[args.case])
        print("Configured provider:", route_provider, "model:", route_model,
              "profile:", route_profile or "isolated defaults")
        print("No Hermes / OpenCode / OpenAI inference calls made.")
        print("No Hermes / OpenCode model calls made.")
        return 0
    if not args.ack_unsandboxed:
        print("Refusing real run without --ack-unsandboxed. Hermes terminal tools "
              "can access local files outside workspace; use a disposable OS environment.",
              file=sys.stderr)
        return 2
    if not shutil.which(args.hermes):
        print("Hermes CLI not found; install it before the real run.", file=sys.stderr)
        return 2
    if route_provider == "openai-api" and not args.approve_paid_api:
        print("Luna uses paid OpenAI API credits. Pass --approve-paid-api explicitly.",
              file=sys.stderr)
        return 2
    if route_provider == PROVIDER:
        try:
            verify_free_profile()
        except ExperimentStopped as exc:
            print("Refusing to run:", exc, file=sys.stderr)
            return 2
    # The provider validates access and actual model availability at runtime.
    # Offline fake-Hermes integration exercises this path without OpenCode.
    controller = None
    try:
        controller = Controller(args)
        controller.execute()
        result = controller.finish()
    except ExperimentStopped as exc:
        if controller is not None:
            controller.abort(exc)
            result = controller.records
        else:
            print("Setup failed:", exc, file=sys.stderr)
            return 2
    finally:
        if controller is not None:
            controller.close()
    print(json.dumps({"directory": str(controller.directory),
                      "outcome": result["outcome"],
                      "calls": len(result["calls"]),
                      "replans": controller.state["replans"] if controller.state else None,
                      "model": result["model"], "provider": result["provider"],
                      "estimated_visible_usd": result["estimated_visible_usd"],
                      "halt_reason": result["halt_reason"]}, ensure_ascii=False, indent=2))
    return 0 if result["outcome"] == "PASS" else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Hierarchical real Hermes experiment")
    parser.add_argument("--hermes", default="hermes", help="Hermes binary path")
    parser.add_argument("--backend", choices=["free", "luna"], default="free",
                        help="free=OpenCode ACP; luna=direct paid OpenAI API")
    parser.add_argument("--case", choices=CASE_IDS, default="legacy",
                        help="Benchmark starting defect profile; same goal and gates")
    parser.add_argument("--model", default=None,
                        help="Model identifier; defaults to route-specific model")
    parser.add_argument("--approve-paid-api", action="store_true",
                        help="Explicit consent for paid OpenAI Luna API calls")
    parser.add_argument("--pilot-budget-usd", type=float, default=3.0,
                        help="Soft stop on observed Luna token charges (not a billing cap)")
    parser.add_argument("--max-calls", type=int, default=12)
    parser.add_argument("--max-turns", type=int, default=18)
    parser.add_argument("--max-replans", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--output", type=Path, default=ROOT / "runs")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--confirm-stopped", action="store_true",
                        help="After verifying an interrupted Hermes invocation is stopped, allow resume")
    parser.add_argument("--ack-unsandboxed", action="store_true",
                        help="Acknowledge terminal/file tools are not OS-sandboxed")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if (args.max_calls < 1 or args.max_turns < 1 or args.max_replans < 0
            or args.timeout_seconds < 15 or args.pilot_budget_usd <= 0):
        parser.error("Invalid bounds")
    sys.exit(run(args))


if __name__ == "__main__":
    main()
