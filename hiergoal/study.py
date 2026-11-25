# SPDX-License-Identifier: Apache-2.0
"""Prepare, run, and replay a bounded comparative goal-control study.

Default/preparation/check/collection paths never instantiate live transport.
The oracle exists only to test the apparatus; its outputs are not observations
of an LLM. The responder sees JSON data, never a Task or a reference solution.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import time
from pathlib import Path

from hiergoal.study_api import OpenAIResponder, TransportError
from hiergoal.study_wire import wire_metadata
from hiergoal.study_protocol import (
    ARMS, SCHEMA, PROFILES, build_manifest, canonical, digest, host_metadata, save, make_trial_task,
    validate_manifest,
)
from hiergoal.study_tasks import make_task
from hiergoal.study_mechanisms import InvalidAction, validate_replan, replan_decision, evidence_from_events, same_json
from hiergoal.study_planning import validate_plan, plan_prompt, statuses, active_leaf, milestone_statuses


class BudgetExhausted(RuntimeError):
    def __init__(self, message, *, evidence=None):
        super().__init__(message)
        self.evidence = evidence


def object_reply(record: dict) -> dict:
    if record.get("status") != "completed":
        raise InvalidAction("Response did not complete within its output allowance")
    try:
        value = json.loads(record["text"], parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, KeyError, TypeError, RecursionError):
        raise InvalidAction("Response must be one JSON object") from None
    if not isinstance(value, dict):
        raise InvalidAction("Response must be one JSON object")
    try:
        canonical(value).encode("utf-8")
    except (UnicodeError, ValueError, RecursionError):
        raise InvalidAction("Response contains invalid Unicode or non-JSON values") from None
    return value


def text_field(value, name, maximum=1200) -> str:
    if not isinstance(value, str) or not 5 <= len(value.strip()) <= maximum:
        raise InvalidAction(f"{name} must contain 5..{maximum} characters")
    return value.strip()


def apply_patch(solution: dict, action: dict) -> dict:
    if set(action) != {"patch", "explanation"}:
        raise InvalidAction("Only patch and explanation are allowed; root/plan/grader are immutable")
    text_field(action["explanation"], "explanation")
    patch = action["patch"]
    if not isinstance(patch, dict) or not patch or not set(patch).issubset(solution):
        raise InvalidAction("Patch must replace existing top-level artifact fields")
    if len(canonical(patch).encode("utf-8")) > 40000:
        raise InvalidAction("Patch exceeds artifact size limit")
    return {**copy.deepcopy(solution), **copy.deepcopy(patch)}


class Trace:
    def __init__(self, path: Path, root_hash: str):
        self.path, self.root_hash, self.previous, self.sequence = path, root_hash, "0" * 64, 0
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise ValueError("Refusing to overwrite an existing trace")

    def add(self, kind, **fields):
        value = {"sequence": self.sequence, "previous_sha256": self.previous,
                 "root_sha256": self.root_hash, "type": kind, **copy.deepcopy(fields)}
        value["event_sha256"] = digest(value)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(canonical(value) + "\n")
            stream.flush()
        self.previous = value["event_sha256"]
        self.sequence += 1


class OracleResponder:
    """Apparatus test only. Never selectable as a live model's fallback."""
    kind = "oracle"

    def __init__(self):
        self.task = None

    def respond(self, role, payload, *, max_output_tokens):
        if self.task is None:
            raise ValueError("Offline oracle requires explicit task binding")
        if role == "plan":
            if hasattr(self.task, "hierarchy_spec"):
                reply = {"instructions": {gate: "Satisfy current requirement: " + description
                                          for gate, description in self.task.gates.items()}}
                return {"text": canonical(reply), "input_tokens": 100, "output_tokens": 100,
                        "elapsed_seconds": 0.0, "response_id": None, "model": "OFFLINE_ORACLE",
                        "status": "completed", "simulated": True,
                        "usage": {"input_tokens": 100, "output_tokens": 100}}
            gates = list(self.task.gates)
            owners = {g: "S" + str(i + 1) for i, g in enumerate(gates)}
            members = [{"id": owners[g], "instruction": "Satisfy current requirement: " + self.task.gates[g],
                        "checks": [g], "depends_on": [owners[d] for d in self.task.dependencies.get(g, [])]}
                       for g in gates]
            reply = {"milestones": [
                {"id": "M1", "title": "Prepare valid intermediate artifacts", "subgoals": members[:-1]},
                {"id": "M2", "title": "Complete the independently verified result", "subgoals": members[-1:]},
            ]}
        elif role == "replan":
            reply = {"diagnosis": "Authoritative environment changed or current gate rejected artifact.",
                     "revised_instruction": "Recompute the failed requirement from the current authoritative environment. "
                                            + payload["leaf"]["instruction"][:900]}
        else:
            reply = {"patch": self.task.reference_solution(),
                     "explanation": "Offline reference artifact for testing the apparatus only."}
        return {"text": canonical(reply), "input_tokens": 100, "output_tokens": 100,
                "elapsed_seconds": 0.0, "response_id": None, "model": "OFFLINE_ORACLE",
                "status": "completed", "simulated": True,
                "usage": {"input_tokens": 100, "output_tokens": 100}}


def request_record(backend, role, payload, limits, on_start=None):
    size = len(canonical(payload).encode("utf-8"))
    if size > limits["max_prompt_bytes"]:
        raise BudgetExhausted("Prompt byte limit reached", evidence={
            "kind": "prompt_bytes", "observed": size, "limit": limits["max_prompt_bytes"],
            "role": role, "blocked_request": payload})
    if on_start:
        on_start(role, payload)
    record = backend.respond(role, copy.deepcopy(payload), max_output_tokens=limits["max_output_tokens"])
    if any(type(record.get(k)) is not int or record[k] < 0 for k in ("input_tokens", "output_tokens")):
        raise TransportError("Missing usage from responder")
    return record


def prepare_plan(task, trial, manifest, backend, directory, on_start=None):
    """No condition or treatment label enters this shared, cached planning request."""
    key = f"{trial['task_id']}-r{trial['repeat']}"
    path = directory / "plans" / (key + ".json")
    if path.exists():
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("protocol_id") != manifest["protocol_id"] or value.get("key") != key:
            raise ValueError("Shared plan belongs to another protocol")
        return value, True
    payload = plan_prompt(task)
    value = {"protocol_id": manifest["protocol_id"], "key": key,
             "request": payload, "record": None, "plan": None, "error": None}
    try:
        value["record"] = request_record(backend, "plan", payload, manifest["limits"], on_start)
        value["plan"] = validate_plan(object_reply(value["record"]), task)
    except InvalidAction as exc:
        value["error"] = {"status": "FAIL", "diagnostic": str(exc), "reason": "InvalidAction"}
    except TransportError as exc:
        value["error"] = {"status": "UNCERTAIN", "diagnostic": str(exc)}
        if exc.evidence is not None:
            value["error"]["transport_evidence"] = copy.deepcopy(exc.evidence)
    except BudgetExhausted as exc:
        value["error"] = {"status": "FAIL", "diagnostic": str(exc), "reason": "BudgetExhausted", "budget": exc.evidence}
    save(path, value)  # Also persist a failed plan: no selective reroll.
    return value, False


def inject_trial_fault(task, solution, trial):
    kind = trial.get("fault_kind", "environment")
    before_spec, before_grades, before_solution = task.public_spec(), task.grade(solution), copy.deepcopy(solution)
    if kind == "forced_subgoal":
        updated, receipt = task.inject_subgoal_fault(solution)
    elif kind == "environment":
        updated, receipt = task.inject_fault(solution)
    else:
        raise ValueError("Unsupported frozen fault intervention")
    grades = task.grade(updated)
    introduced = (all(g["passed"] for g in before_grades.values()) and not all(g["passed"] for g in grades.values()))
    changed = digest(before_spec) != digest(task.public_spec()) or digest(before_solution) != digest(updated)
    delivered = bool(changed and introduced and receipt.get("domain_fault_delivered", receipt.get("delivered", True)))
    if kind == "forced_subgoal" and (not delivered or digest(before_spec) != digest(task.public_spec())):
        raise ValueError("Forced subgoal intervention did not preserve environment and fail a domain gate")
    return updated, receipt, grades, delivered, introduced


def action_prompt(role, task, solution, grades, plan, leaf, history):
    if role == "plan":
        return plan_prompt(task)
    common = {"root_contract": task.root_contract, "task": task.public_spec(),
              "artifact": solution, "public_feedback": grades, "history": history[-4:]}
    if role == "replan":
        return {**common, "leaf": copy.deepcopy(leaf),
                "instruction": 'Return JSON {"diagnosis":"specific observed cause",'
                               '"revised_instruction":"different executable local instruction"}. '
                               'Revise ONLY this failed leaf instruction; keep root, parent, gates and dependencies.'}
    if role != "execute":
        raise ValueError("Unknown responder role")
    return {**common, "gates": task.gates, "gate_dependencies": task.dependencies,
            "instruction": (
                'Return JSON {"patch":{"existing_top_level_artifact_field": "replacement value"},'
                '"explanation":"brief change rationale"}. You may replace any artifact fields in '
                'every method. Use the current authoritative environment and all feedback to choose '
                'a repair. The evaluator, not self-reported success, decides completion. '
                'If current_leaf is present, prioritize that instruction and its dependencies; '
                'otherwise choose the next repair directly from the root task and feedback. '
                'Do not include root, plan, or grading changes. No external tools are available.'),
            "current_leaf": copy.deepcopy(leaf), "plan": copy.deepcopy(plan)}


def validate_budget_evidence(event, counts, limits, task, solution, plan, history, elapsed):
    evidence = event.get("budget")
    if not isinstance(evidence, dict):
        raise ValueError("Budget exhaustion has no measured evidence")
    kind, observed, limit = evidence.get("kind"), evidence.get("observed"), evidence.get("limit")
    if isinstance(observed, bool) or not isinstance(observed, (float, int)) or not math.isfinite(observed):
        raise ValueError("Invalid budget observation")
    grades = task.grade(solution)
    needs_work = not all(g["passed"] for g in grades.values())
    if kind == "calls":
        valid = limit == limits["max_calls"] and observed == counts["calls"] and observed >= limit and needs_work
    elif kind in ("tokens_before", "tokens_after"):
        valid = (limit == limits["max_total_tokens"] and counts["input_tokens"] is not None
                 and counts["output_tokens"] is not None
                 and observed == counts["input_tokens"] + counts["output_tokens"]
                 and (observed > limit if kind.endswith("after") else observed >= limit and needs_work))
    elif kind in ("time_before", "time_after"):
        wall = event.get("wall_seconds")
        valid = (limit == limits["trial_timeout_seconds"] and isinstance(wall, (int, float))
                 and not isinstance(wall, bool) and math.isfinite(wall)
                 and observed <= max(wall, elapsed) + 1e-6
                 and (observed > limit if kind.endswith("after") else observed >= limit and needs_work))
    elif kind == "prompt_bytes":
        role, payload = evidence.get("role"), evidence.get("blocked_request")
        expected = action_prompt(role, task, solution, grades, plan, active_leaf(plan, grades), history)
        valid = (limit == limits["max_prompt_bytes"] and same_json(payload, expected) and
                 observed == len(canonical(payload).encode("utf-8")) and observed > limit)
    else:
        valid = False
    if not valid:
        raise ValueError("Budget exhaustion contradicts measured execution")


def run_trial(task, trial, manifest, backend, directory: Path) -> dict:
    trial_dir = directory / "trials" / trial["trial_id"]
    root_hash = digest(task.root_contract)
    trace = Trace(trial_dir / "trace.jsonl", root_hash)
    limits, arm = manifest["limits"], trial["arm"]
    started = time.monotonic()
    result = {"trial_id": trial["trial_id"], "status": "UNCERTAIN", "success": None,
              "protocol_id": manifest["protocol_id"], "backend": backend.kind,
              "fault_assigned": trial["condition"] == "fault", "fault_triggered": False,
              "fault_kind": trial.get("fault_kind", "environment"),
              "fault_delivered": False, "recovered": None,
              "invariant_ok": True, "protocol_ok": True,
              "calls": 0, "input_tokens": 0, "output_tokens": 0,
              "actual_calls": 0, "actual_input_tokens": 0, "actual_output_tokens": 0,
              "elapsed_seconds": 0.0, "patch_actions": 0, "replans": 0,
              "replan_attempts": 0, "rejected_actions": 0, "diagnostic": "",
              "simulated": backend.kind != "openai", "observed_models": []}
    solution, plan, history = task.initial_solution(), None, []
    grades = task.grade(solution)
    checkpoint_done, need_replan, transport_failure = False, False, False
    pending_request = {}
    trace.add("initial", trial=trial, protocol_id=manifest["protocol_id"],
              root_contract=task.root_contract, public_spec=task.public_spec(), solution=solution,
              public_grades=grades, simulated=result["simulated"])

    def request_started(role, payload):
        pending_request.update(role=role, request=copy.deepcopy(payload), reused=False)
        trace.add("request_started", role=role, request=payload)
        if role == "replan":
            result["replan_attempts"] += 1

    def ensure_root():
        if digest(task.root_contract) != root_hash:
            result["invariant_ok"] = False
            raise TransportError("Immutable root changed")

    def charge(record, role, payload, *, reused=False):
        pending_request.clear()
        result["calls"] += 1
        result["input_tokens"] += record["input_tokens"]
        result["output_tokens"] += record["output_tokens"]
        result["elapsed_seconds"] += record["elapsed_seconds"]
        if record["model"] not in result["observed_models"]:
            result["observed_models"].append(record["model"])
        if not reused and backend.kind == "openai":
            result["actual_calls"] += 1
            result["actual_input_tokens"] += record["input_tokens"]
            result["actual_output_tokens"] += record["output_tokens"]
        trace.add("response", role=role, request=payload, record=record,
                  reused_shared_plan=reused, logical_call=result["calls"])
        if result["input_tokens"] + result["output_tokens"] > limits["max_total_tokens"]:
            raise BudgetExhausted("Measured logical token allowance exceeded on last response", evidence={
                "kind": "tokens_after", "observed": result["input_tokens"] + result["output_tokens"], "limit": limits["max_total_tokens"]})
        if (time.monotonic() - started > limits["trial_timeout_seconds"] or
                result["elapsed_seconds"] > limits["trial_timeout_seconds"]):
            raise BudgetExhausted("Trial time allowance exceeded on last response", evidence={
                "kind": "time_after", "observed": max(time.monotonic() - started, result["elapsed_seconds"]), "limit": limits["trial_timeout_seconds"]})
        ensure_root()

    def check_budget():
        if result["calls"] >= limits["max_calls"]:
            raise BudgetExhausted("Logical request allowance exhausted", evidence={
                "kind": "calls", "observed": result["calls"], "limit": limits["max_calls"]})
        if result["input_tokens"] + result["output_tokens"] >= limits["max_total_tokens"]:
            raise BudgetExhausted("Measured logical token allowance exhausted", evidence={
                "kind": "tokens_before", "observed": result["input_tokens"] + result["output_tokens"], "limit": limits["max_total_tokens"]})
        elapsed = max(time.monotonic() - started, result["elapsed_seconds"])
        if elapsed >= limits["trial_timeout_seconds"]:
            raise BudgetExhausted("Trial time allowance exhausted", evidence={
                "kind": "time_before", "observed": elapsed, "limit": limits["trial_timeout_seconds"]})

    def checkpoint():
        trace.add("checkpoint", solution_sha256=digest(solution),
                  environment_sha256=digest(task.public_spec()), public_grades=grades,
                  leaf_statuses=statuses(plan, grades), milestone_statuses=milestone_statuses(plan, grades),
                  root_status="awaiting_final_verification" if all(g["passed"] for g in grades.values()) else "active",
                  plan=plan)

    def decide(before_grades, leaf, *, failure_introduced=False, source="patch"):
        choice = replan_decision(before_grades, grades, leaf, fault_delivered=failure_introduced)
        trace.add("replan_decision", source=source, leaf=leaf, leaf_id=leaf["id"] if leaf else None,
                  before_grades=before_grades, after_grades=grades, public_grades=grades,
                  failure_introduced=failure_introduced, **choice,
                  solution_sha256=digest(solution), environment_sha256=digest(task.public_spec()))
        return choice["needed"]

    try:
        if backend.kind == "oracle":
            backend.task = task
        if arm != "flat_retry":
            shared, reused = prepare_plan(task, trial, manifest, backend, directory, request_started)
            if shared["record"] is not None:
                charge(shared["record"], "plan", shared["request"], reused=reused)
            trace.add("shared_plan", key=shared["key"], plan=shared["plan"], error=shared["error"])
            if shared["error"]:
                result.update(shared["error"])
                transport_failure = shared["error"]["status"] == "UNCERTAIN"
                if transport_failure and reused:
                    pending_request.update(role="plan", request=shared["request"], reused=True)
                if transport_failure:
                    raise TransportError(shared["error"]["diagnostic"],
                                         evidence=shared["error"].get("transport_evidence"))
                if shared["error"].get("reason") == "BudgetExhausted":
                    raise BudgetExhausted(shared["error"]["diagnostic"], evidence=shared["error"]["budget"])
                raise InvalidAction(shared["error"]["diagnostic"])
            plan = copy.deepcopy(shared["plan"])
        checkpoint()
        while True:
            ensure_root()
            if all(g["passed"] for g in grades.values()):
                if not checkpoint_done:
                    before_spec, before_grades = task.public_spec(), copy.deepcopy(grades)
                    checkpoint_done = True
                    if trial["condition"] == "fault":
                        result["fault_triggered"] = True
                        before = copy.deepcopy(solution)
                        solution, fault, grades, delivered, introduced = inject_trial_fault(task, solution, trial)
                        ensure_root()
                        result["fault_delivered"] = delivered
                        trace.add("fault", before_solution=before, after_solution=solution,
                                  before_spec=before_spec, after_spec=task.public_spec(),
                                  before_grades=before_grades, after_grades=grades,
                                  fault=fault, delivered=delivered, fault_kind=trial.get("fault_kind", "environment"),
                                  public_failure_introduced=introduced)
                        need_replan = decide(before_grades, active_leaf(plan, grades), failure_introduced=introduced, source="fault")
                    else:
                        trace.add("sham_checkpoint", public_spec=before_spec, public_grades=grades)
                    checkpoint()
                    if not all(g["passed"] for g in grades.values()):
                        continue
                final = task.grade(solution, hidden=True)
                ensure_root()
                passed = all(g["passed"] for g in final.values())
                trace.add("final_grade", solution=solution, public_spec=task.public_spec(),
                          public_grades=grades, hidden_grades=final, passed=passed)
                result.update(status="PASS" if passed else "FAIL",
                              diagnostic="Independent final grading passed" if passed else "Final withheld grading failed")
                break
            check_budget()
            leaf = active_leaf(plan, grades)
            if plan is not None and leaf is None:
                raise TransportError("No executable leaf despite an incomplete root")
            if arm == "hierarchy_adaptive" and need_replan and result["replan_attempts"] < limits["max_replans"]:
                payload = action_prompt("replan", task, solution, grades, plan, leaf, history)
                record = request_record(backend, "replan", payload, limits, request_started)
                charge(record, "replan", payload)
                need_replan = False
                try:
                    change = object_reply(record)
                    before = copy.deepcopy(plan)
                    plan, diagnosis = validate_replan(plan, leaf, grades, change)
                    result["replans"] += 1
                    trace.add("replan", leaf_id=leaf["id"], diagnosis=diagnosis,
                              before_plan=before, after_plan=plan, public_grades=grades,
                              solution_sha256=digest(solution), environment_sha256=digest(task.public_spec()))
                    checkpoint()
                except InvalidAction as exc:
                    result["rejected_actions"] += 1
                    trace.add("rejected", role="replan", reason=str(exc))
                    history.append({"role": "replan", "feedback": str(exc)})
                continue
            payload = action_prompt("execute", task, solution, grades, plan, leaf, history)
            record = request_record(backend, "execute", payload, limits, request_started)
            charge(record, "execute", payload)
            try:
                action = object_reply(record)
                before = copy.deepcopy(solution)
                before_grades = copy.deepcopy(grades)
                solution = apply_patch(solution, action)
                result["patch_actions"] += 1
                grades = task.grade(solution)
                ensure_root()
                trace.add("patch", action=action, before_solution=before, after_solution=solution)
                checkpoint()
                history.append({"action": action, "public_feedback": grades})
                # An accepted patch may invalidate an earlier dependency. Decide
                # against the same post-patch leaf that the next iteration will use.
                need_replan = decide(before_grades, active_leaf(plan, grades))
            except InvalidAction as exc:
                result["rejected_actions"] += 1
                trace.add("rejected", role="execute", reason=str(exc))
                history.append({"feedback": str(exc)})
                need_replan = False
    except (InvalidAction, BudgetExhausted) as exc:
        result.update(status="FAIL", diagnostic=str(exc))
        trace.add("termination", status="FAIL", reason=type(exc).__name__,
                  diagnostic=str(exc), wall_seconds=time.monotonic() - started,
                  budget=exc.evidence if isinstance(exc, BudgetExhausted) else None)
    except TransportError as exc:
        result.update(status="UNCERTAIN", diagnostic=str(exc))
        transport_failure = True
        evidence = {}
        if exc.evidence is not None:
            result["transport_evidence"] = copy.deepcopy(exc.evidence)
            evidence["transport_evidence"] = copy.deepcopy(exc.evidence)
        trace.add("termination", status="UNCERTAIN", reason="TransportError", diagnostic=str(exc), **evidence)
    except Exception as exc:
        # An apparatus exception is NOT evidence of method failure. Do not log
        # arbitrary exception text (which could include transport credentials).
        result.update(status="UNCERTAIN", diagnostic="APPARATUS_ERROR:" + type(exc).__name__, protocol_ok=False)
        transport_failure = True
        trace.add("termination", status="UNCERTAIN", reason="ApparatusError", diagnostic=result["diagnostic"])
    if pending_request:
        # An issued request with an unknown outcome is counted, never shown as
        # zero-cost. Preserve measured partial usage separately from the null total.
        result["calls"] += 1
        result["known_input_tokens"] = result["input_tokens"]
        result["known_output_tokens"] = result["output_tokens"]
        result["input_tokens"] = result["output_tokens"] = None
        if backend.kind == "openai" and not pending_request["reused"]:
            result["actual_calls"] += 1
            result["known_actual_input_tokens"] = result["actual_input_tokens"]
            result["known_actual_output_tokens"] = result["actual_output_tokens"]
            result["actual_input_tokens"] = result["actual_output_tokens"] = None
        trace.add("request_failed", **pending_request, diagnostic=result["diagnostic"])
    if digest(task.root_contract) != root_hash:
        result.update(invariant_ok=False, status="UNCERTAIN", diagnostic="Immutable root changed", protocol_ok=False)
        transport_failure = True
    result["success"] = True if result["status"] == "PASS" else False if result["status"] == "FAIL" else None
    result["recovered"] = result["success"] if result["fault_delivered"] else None
    result["wall_seconds"] = time.monotonic() - started
    result["stop_batch"] = transport_failure
    result["final_artifact_sha256"] = digest(solution)
    result["final_environment_sha256"] = digest(task.public_spec())
    trace.add("result", result=result)
    result["trace_final_sha256"] = trace.previous
    save(trial_dir / "result.json", result)
    return result


def audit_trial(directory: Path, trial: dict, manifest: dict) -> dict:
    """Replay owned artifacts with the grader; a self-reported PASS is insufficient."""
    result_path = directory / "trials" / trial["trial_id"] / "result.json"
    if not result_path.exists():
        began = result_path.with_name("trace.jsonl").exists()
        partial = incomplete_usage(result_path.with_name("trace.jsonl"), manifest["backend"]) if began else {}
        return {"trial_id": trial["trial_id"], "status": "UNCERTAIN" if began else "NOT_RUN", "success": None,
                "diagnostic": "Started but interrupted before a complete result" if began else "Trial not started",
                "protocol_ok": False if began else None, "invariant_ok": None,
                "input_tokens": None, "output_tokens": None,
                "actual_input_tokens": None, "actual_output_tokens": None,
                "audit": "INCOMPLETE" if began else "NOT_RUN", **partial}
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        events = [json.loads(line) for line in result_path.with_name("trace.jsonl").read_text(encoding="utf-8").splitlines()]
        task = make_trial_task(trial, manifest["task_seed"])
        solution, plan, previous = task.initial_solution(), None, "0" * 64
        root_hash, final_pass, checkpoint_seen = digest(task.root_contract), False, False
        counts = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "patch_actions": 0, "replans": 0,
                  "actual_calls": 0, "actual_input_tokens": 0, "actual_output_tokens": 0}
        fault_seen, delivered, terminal, latest_reply, pending = False, False, None, None, None
        final_seen, response_consumed, elapsed, termination = False, True, 0.0, None
        replan_attempts, rejected_actions, shared_plan_count = 0, 0, 0
        observed_models = []
        history, decision_context, authorized_replan = [], None, None
        required_events = []
        allowed_events = {"initial", "request_started", "response", "shared_plan", "patch", "checkpoint",
                          "fault", "sham_checkpoint", "replan", "replan_decision", "request_failed", "final_grade", "result", "rejected", "termination"}
        for index, event in enumerate(events):
            content = {k: v for k, v in event.items() if k != "event_sha256"}
            if (type(event["sequence"]) is not int or event["sequence"] != index or event["previous_sha256"] != previous or
                event["event_sha256"] != digest(content) or event["root_sha256"] != root_hash):
                raise ValueError("Broken trace chain or root invariant")
            previous = event["event_sha256"]
            kind = event["type"]
            # Checkpoints are part of the evidence contract, not optional
            # snapshots. Match the runner's transition order before consuming
            # the event so deletion, duplication, or reordering cannot erase
            # state changes while retaining a successful replay receipt.
            checkpoint_required = bool(required_events and required_events[0] == "checkpoint")
            if required_events:
                if kind == required_events[0]:
                    required_events.pop(0)
                elif kind == "termination" and event.get("reason") == "ApparatusError":
                    # A failing apparatus may stop while constructing the next
                    # snapshot. Its UNCERTAIN outcome must remain collectable.
                    required_events.clear()
                    decision_context = None
                else:
                    raise ValueError("Missing or reordered mandatory transition evidence")
            if kind == "checkpoint" and not checkpoint_required:
                raise ValueError("Unexpected or duplicated state checkpoint")
            if kind not in allowed_events or (final_seen and kind != "result"):
                raise ValueError("Unexpected event after final grading")
            if termination is not None and kind not in ("request_failed", "result"):
                raise ValueError("Work continued after terminal stop")
            if index == 0 and kind != "initial":
                raise ValueError("Missing initial evidence")
            if kind == "initial":
                if (index != 0 or not same_json(event["trial"], trial) or event["protocol_id"] != manifest["protocol_id"]
                        or not same_json(event["root_contract"], task.root_contract)
                        or not same_json(event["solution"], solution)
                        or not same_json(event["public_spec"], task.public_spec())
                        or not same_json(event["public_grades"], task.grade(solution))):
                    raise ValueError("Initial evidence mismatch")
                if trial["arm"] == "flat_retry":
                    required_events = ["checkpoint"]
            elif kind == "request_started":
                if not response_consumed or decision_context is not None:
                    raise ValueError("Earlier response or replan decision was not processed")
                limits = manifest["limits"]
                if (counts["calls"] >= limits["max_calls"]
                        or counts["input_tokens"] is None or counts["output_tokens"] is None
                        or counts["input_tokens"] + counts["output_tokens"] >= limits["max_total_tokens"]
                        or elapsed >= limits["trial_timeout_seconds"]):
                    raise ValueError("Request started after its measured allowance was exhausted")
                if len(canonical(event["request"]).encode("utf-8")) > limits["max_prompt_bytes"]:
                    raise ValueError("Request started above its prompt byte allowance")
                if (pending is not None or not same_json(event["request"].get("root_contract"), task.root_contract)
                        or not same_json(event["request"].get("task"), task.public_spec())):
                    raise ValueError("Overlapping request or changed root")
                if event["role"] not in ("plan", "execute", "replan"):
                    raise ValueError("Unexpected request role")
                if event["role"] == "plan" and (trial["arm"] == "flat_retry" or counts["calls"] != 0 or shared_plan_count != 0):
                    raise ValueError("Unexpected initial planning request")
                expected_prompt = action_prompt(event["role"], task, solution, task.grade(solution), plan,
                                                active_leaf(plan, task.grade(solution)), history)
                if not same_json(event["request"], expected_prompt):
                    raise ValueError("Responder context differs from the frozen prompt and observed history")
                if event["role"] != "plan":
                    if trial["arm"] != "flat_retry" and (plan is None or shared_plan_count != 1):
                        raise ValueError("Hierarchical execution requires its shared validated plan")
                    if (not same_json(event["request"].get("artifact"), solution)
                            or not same_json(event["request"].get("public_feedback"), task.grade(solution))):
                        raise ValueError("Responder received stale artifact or feedback")
                    if event["role"] == "execute" and (not same_json(event["request"].get("plan"), plan)
                            or not same_json(event["request"].get("current_leaf"), active_leaf(plan, task.grade(solution)))):
                        raise ValueError("Responder received a different treatment plan")
                    if event["role"] == "replan" and (trial["arm"] != "hierarchy_adaptive"
                            or not same_json(event["request"].get("leaf"), active_leaf(plan, task.grade(solution)))):
                        raise ValueError("Replanning the wrong or unauthorized leaf")
                    if event["role"] == "replan" and (authorized_replan != event["request"]["leaf"]["id"] or replan_attempts >= manifest["limits"]["max_replans"]):
                        raise ValueError("Replan is unnecessary or exceeds its allowance")
                if event["role"] == "replan":
                    replan_attempts += 1
                authorized_replan = None
                pending = {"role": event["role"], "request": event["request"]}
            elif kind == "response":
                if (not same_json(event["request"].get("root_contract"), task.root_contract)
                        or not same_json(event["request"].get("task"), task.public_spec())):
                    raise ValueError("Prompt root changed")
                if event["reused_shared_plan"]:
                    if (event["role"] != "plan" or pending is not None or not response_consumed
                            or latest_reply is not None or counts["calls"] != 0 or shared_plan_count != 0):
                        raise ValueError("A shared response must occupy the sole initial planning slot")
                elif not same_json(pending, {"role": event["role"], "request": event["request"]}):
                    raise ValueError("Response has no matching request")
                pending, latest_reply = None, event
                response_consumed = False
                record = event["record"]
                if (manifest["backend"] == "openai" and manifest.get("protocol_revision") in ("v2.3", "v2.4", "v2.5")
                        and not same_json(record.get("wire_request"), wire_metadata(event["role"], event["request"]))):
                    raise ValueError("Wire input or response format receipt mismatch")
                if record["model"] not in observed_models:
                    observed_models.append(record["model"])
                counts["calls"] += 1
                for name in ("input_tokens", "output_tokens"):
                    if type(record[name]) is not int or record[name] < 0:
                        raise ValueError("Invalid usage")
                    counts[name] += record[name]
                elapsed += record["elapsed_seconds"]
                if manifest["backend"] == "openai" and not event["reused_shared_plan"]:
                    counts["actual_calls"] += 1
                    counts["actual_input_tokens"] += record["input_tokens"]
                    counts["actual_output_tokens"] += record["output_tokens"]
                if record["simulated"] is not (manifest["backend"] != "openai"):
                    raise ValueError("Simulated/live evidence mismatch")
            elif kind == "shared_plan":
                shared_plan_count += 1
                if trial["arm"] == "flat_retry" or shared_plan_count != 1:
                    raise ValueError("Flat arm unexpectedly has a goal tree")
                if event["key"] != f"{trial['task_id']}-r{trial['repeat']}":
                    raise ValueError("Unexpected shared plan key")
                plan = copy.deepcopy(event["plan"])
                response_consumed = True
                shared_path = directory / "plans" / (event["key"] + ".json")
                shared = json.loads(shared_path.read_text(encoding="utf-8"))
                if (shared["protocol_id"] != manifest["protocol_id"]
                        or not same_json(shared["plan"], plan)
                        or not same_json(shared["error"], event["error"])
                        or not same_json(shared["request"], plan_prompt(task))):
                    raise ValueError("Shared planning evidence mismatch")
                if shared["record"] is not None:
                    if (latest_reply is None or latest_reply["role"] != "plan"
                            or not same_json(shared["record"], latest_reply["record"])
                            or not same_json(shared["request"], latest_reply["request"])):
                        raise ValueError("Shared plan response differs from the recorded planning response")
                elif latest_reply is not None:
                    raise ValueError("Shared plan discarded a recorded planning response")
                if plan is not None:
                    if latest_reply is None or latest_reply["role"] != "plan" or not same_json(plan, validate_plan(object_reply(latest_reply["record"]), task)):
                        raise ValueError("Initial plan does not match model output")
                    # Canonical trace JSON sorts dictionary keys (S1,S10,...,S2).
                    # Reconstruct the validated execution order from the original
                    # response and frozen task instead of replaying that key order.
                    plan = validate_plan(object_reply(latest_reply["record"]), task)
                    required_events = ["checkpoint"]
                elif event["error"] and event["error"]["status"] == "FAIL" and shared["record"] is not None:
                    try:
                        validate_plan(object_reply(shared["record"]), task)
                    except InvalidAction:
                        pass
                    else:
                        raise ValueError("Valid planning response incorrectly classified as failed")
            elif kind == "patch":
                if response_consumed or latest_reply is None or latest_reply["role"] != "execute" or not same_json(event["action"], object_reply(latest_reply["record"])):
                    raise ValueError("Patch does not match the model output")
                response_consumed = True
                if not same_json(event["before_solution"], solution):
                    raise ValueError("Stale artifact")
                before_grades = task.grade(solution)
                solution = apply_patch(solution, event["action"])
                if not same_json(solution, event["after_solution"]):
                    raise ValueError("Patch replay mismatch")
                counts["patch_actions"] += 1
                after_grades = task.grade(solution)
                history.append({"action": event["action"], "public_feedback": after_grades})
                decision_context = {"source": "patch", "before_grades": before_grades,
                                    "leaf": copy.deepcopy(active_leaf(plan, after_grades)), "failure_introduced": False}
                required_events = ["checkpoint", "replan_decision"]
            elif kind == "checkpoint":
                if (event["solution_sha256"] != digest(solution) or event["environment_sha256"] != digest(task.public_spec()) or
                    not same_json(event["public_grades"], task.grade(solution)) or not same_json(event["plan"], plan) or
                    not same_json(event["leaf_statuses"], statuses(plan, task.grade(solution))) or
                    not same_json(event["milestone_statuses"], milestone_statuses(plan, task.grade(solution))) or
                    event["root_status"] != ("awaiting_final_verification" if all(g["passed"] for g in task.grade(solution).values()) else "active")):
                    raise ValueError("Unreproducible or stale verification")
            elif kind == "fault":
                if fault_seen or trial["condition"] != "fault" or not all(g["passed"] for g in task.grade(solution).values()):
                    raise ValueError("Invalid fault checkpoint")
                before_spec = task.public_spec()
                if (not same_json(event["before_solution"], solution) or not same_json(event["before_spec"], before_spec)
                        or not same_json(event["before_grades"], task.grade(solution))):
                    raise ValueError("Fault pre-state mismatch")
                before_grades = task.grade(solution)
                solution, fault, after_grades, delivered, introduced = inject_trial_fault(task, solution, trial)
                if (not same_json(event["after_solution"], solution) or not same_json(event["after_spec"], task.public_spec())
                        or not same_json(event["fault"], fault) or event["delivered"] is not delivered
                        or not same_json(event["after_grades"], task.grade(solution))):
                    raise ValueError("Fault replay mismatch")
                if event["fault_kind"] != trial.get("fault_kind", "environment") or event["public_failure_introduced"] is not introduced:
                    raise ValueError("Fault kind or impact changed")
                decision_context = {"source": "fault", "before_grades": before_grades,
                                    "leaf": copy.deepcopy(active_leaf(plan, after_grades)), "failure_introduced": introduced}
                fault_seen, checkpoint_seen = True, True
                required_events = ["replan_decision", "checkpoint"]
            elif kind == "replan_decision":
                if decision_context is None:
                    raise ValueError("Replan decision has no fresh observation")
                grades = task.grade(solution)
                for key, value in decision_context.items():
                    if not same_json(event.get(key), value):
                        raise ValueError("Replan decision context mismatch")
                choice = replan_decision(decision_context["before_grades"], grades,
                                         decision_context["leaf"], fault_delivered=decision_context["failure_introduced"])
                if (any(not same_json(event.get(key), value) for key, value in choice.items()) or
                    not same_json(event["after_grades"], grades) or not same_json(event["public_grades"], grades) or
                    event["solution_sha256"] != digest(solution) or event["environment_sha256"] != digest(task.public_spec())):
                    raise ValueError("Replan necessity was not derived from current evidence")
                leaf = decision_context["leaf"]
                if event["leaf_id"] != (leaf["id"] if leaf else None):
                    raise ValueError("Replan decision identified a different leaf")
                authorized_replan = leaf["id"] if choice["needed"] else None
                decision_context = None
            elif kind == "sham_checkpoint":
                if (checkpoint_seen or trial["condition"] != "normal" or not all(g["passed"] for g in task.grade(solution).values())
                        or not same_json(event["public_spec"], task.public_spec())
                        or not same_json(event["public_grades"], task.grade(solution))):
                    raise ValueError("Invalid sham checkpoint")
                checkpoint_seen = True
                required_events = ["checkpoint"]
            elif kind == "replan":
                if trial["arm"] != "hierarchy_adaptive" or not same_json(event["before_plan"], plan):
                    raise ValueError("Unauthorized plan change")
                if (latest_reply is None or latest_reply["role"] != "replan" or
                    event["leaf_id"] != latest_reply["request"]["leaf"]["id"] or
                    event["leaf_id"] != active_leaf(plan, task.grade(solution))["id"]):
                    raise ValueError("Replan changed a different leaf than the requested active goal")
                leaf = plan["leaves"][event["leaf_id"]]
                if all(task.grade(solution)[g]["passed"] for g in leaf["checks"]):
                    raise ValueError("Unnecessary replan lacks failure evidence")
                if response_consumed or latest_reply is None or latest_reply["role"] != "replan":
                    raise ValueError("Replan does not match model output")
                change = object_reply(latest_reply["record"])
                expected, diagnosis = validate_replan(plan, leaf, task.grade(solution), change)
                response_consumed = True
                if not same_json(expected, event["after_plan"]) or diagnosis != event["diagnosis"]:
                    raise ValueError("Replan changed unrelated goals or acceptance rules")
                if (event["solution_sha256"] != digest(solution) or event["environment_sha256"] != digest(task.public_spec())
                        or not same_json(event["public_grades"], task.grade(solution))):
                    raise ValueError("Replan used stale evidence")
                plan = expected
                counts["replans"] += 1
                required_events = ["checkpoint"]
            elif kind == "request_failed":
                if not event["reused"] and not same_json(pending, {"role": event["role"], "request": event["request"]}):
                    raise ValueError("Failed request lacks matching start")
                counts["calls"] += 1
                counts["input_tokens"] = counts["output_tokens"] = None
                if manifest["backend"] == "openai" and not event["reused"]:
                    counts["actual_calls"] += 1
                    counts["actual_input_tokens"] = counts["actual_output_tokens"] = None
                pending = None
            elif kind == "final_grade":
                if final_seen:
                    raise ValueError("Repeated hidden grading")
                if not response_consumed or pending is not None or decision_context is not None:
                    raise ValueError("Final grading preceded completion of the recorded action")
                if trial["arm"] != "flat_retry" and (plan is None or shared_plan_count != 1):
                    raise ValueError("Hierarchical completion lacks its shared validated plan")
                final_seen = True
                hidden = task.grade(solution, hidden=True)
                public = task.grade(solution)
                final_pass = all(g["passed"] for g in hidden.values()) and all(g["passed"] for g in public.values())
                if (not checkpoint_seen or not same_json(event["solution"], solution)
                        or not same_json(event["public_spec"], task.public_spec())
                        or not same_json(event["hidden_grades"], hidden) or not same_json(event["public_grades"], public)
                        or event["passed"] is not final_pass):
                    raise ValueError("Independent final grade mismatch")
            elif kind == "result":
                if index != len(events) - 1:
                    raise ValueError("Evidence recorded after terminal result")
                terminal = event["result"]
            elif kind == "termination":
                if termination is not None:
                    raise ValueError("Multiple termination reasons")
                expected_status = {"BudgetExhausted": "FAIL", "InvalidAction": "FAIL",
                                   "TransportError": "UNCERTAIN", "ApparatusError": "UNCERTAIN"}.get(event["reason"])
                if expected_status is None or event["status"] != expected_status:
                    raise ValueError("Unknown termination reason or unsupported terminal status")
                if event["reason"] == "ApparatusError" and result["protocol_ok"] is not False:
                    raise ValueError("Apparatus failure must invalidate the execution protocol")
                if event["reason"] == "TransportError" and not same_json(
                        event.get("transport_evidence"), result.get("transport_evidence")):
                    raise ValueError("Transport diagnostic receipt differs from terminal result")
                termination = event
                if event["reason"] == "BudgetExhausted":
                    validate_budget_evidence(event, counts, manifest["limits"], task, solution, plan, history, elapsed)
                elif event["reason"] == "InvalidAction":
                    if shared_plan_count != 1 or plan is not None or shared["error"] is None or shared["error"].get("reason") != "InvalidAction":
                        raise ValueError("Model failure has no invalid initial plan evidence")
            elif kind == "rejected":
                if response_consumed or latest_reply is None or latest_reply["role"] != event["role"]:
                    raise ValueError("Rejection has no matching model reply")
                try:
                    reply = object_reply(latest_reply["record"])
                    if event["role"] == "execute":
                        apply_patch(solution, reply)
                    elif event["role"] == "replan":
                        validate_replan(plan, active_leaf(plan, task.grade(solution)), task.grade(solution), reply)
                    else:
                        raise ValueError("Unexpected rejection role")
                except InvalidAction as exc:
                    if event["reason"] != str(exc):
                        raise ValueError("Rejection reason differs from actual validation")
                else:
                    raise ValueError("A valid response was incorrectly rejected")
                response_consumed = True
                rejected_actions += 1
                history.append({"role": "replan", "feedback": event["reason"]} if event["role"] == "replan" else {"feedback": event["reason"]})
        if (terminal is None or pending is not None or decision_context is not None
                or not same_json(result, {**terminal, "trace_final_sha256": previous})):
            raise ValueError("Missing or changed terminal result")
        if any(not same_json(result[k], v) for k, v in counts.items()):
            raise ValueError("Accounting mismatch")
        if not same_json(result["observed_models"], observed_models) or (manifest["backend"] == "openai" and len(observed_models) > 1):
            raise ValueError("Model changed within a trial")
        # Count issued requests even if transport fails or their response exceeds
        # the remaining allowance; those attempts still consumed exposure.
        if (not same_json(result["replan_attempts"], replan_attempts) or
            not same_json(result["rejected_actions"], rejected_actions) or
            result["replan_attempts"] > manifest["limits"]["max_replans"]):
            raise ValueError("Replan/rejection accounting mismatch")
        if (result["final_artifact_sha256"] != digest(solution) or
            result["final_environment_sha256"] != digest(task.public_spec()) or
            abs(result["elapsed_seconds"] - elapsed) > 1e-8):
            raise ValueError("Final artifact/environment or logical time mismatch")
        if result["fault_delivered"] is not delivered or result["fault_triggered"] is not fault_seen:
            raise ValueError("Fault accounting mismatch")
        expected_success = True if result["status"] == "PASS" else False if result["status"] == "FAIL" else None
        if result["success"] is not expected_success or result["recovered"] is not (expected_success if delivered else None):
            raise ValueError("Success/recovery accounting mismatch")
        if final_seen and result["status"] != ("PASS" if final_pass else "FAIL"):
            raise ValueError("Terminal result contradicts independent final grading")
        if not final_seen and (termination is None or termination["status"] != result["status"] or termination["diagnostic"] != result["diagnostic"]):
            raise ValueError("No evidence for terminal outcome")
        if result["status"] == "PASS" and (not final_pass or not result["invariant_ok"] or not result["protocol_ok"]):
            raise ValueError("Unsupported PASS")
        if result["status"] == "PASS" and (counts["input_tokens"] is None or counts["output_tokens"] is None or counts["calls"] > manifest["limits"]["max_calls"] or counts["input_tokens"] + counts["output_tokens"] > manifest["limits"]["max_total_tokens"]):
            raise ValueError("PASS outside the resource contract")
        if result["status"] == "PASS" and max(result["wall_seconds"], elapsed) > manifest["limits"]["trial_timeout_seconds"]:
            raise ValueError("PASS after the trial deadline")
        result["audit"] = "PASS"
        result["mechanism_evidence"] = evidence_from_events(events, task)
        return result
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        return {"trial_id": trial["trial_id"], "status": "UNCERTAIN", "success": None,
                "diagnostic": "EVIDENCE_AUDIT_FAILED:" + type(exc).__name__,
                "protocol_ok": False, "invariant_ok": False, "audit": "FAIL"}


def incomplete_usage(path: Path, backend: str) -> dict:
    """Preserve the verified prefix's partial usage after a process/job abort.

    These are known lower totals, never a bill or a recovered task result. A
    pending request may have consumed additional unknown tokens.
    """
    previous, sequence, started, replies, known_input, known_output = "0" * 64, 0, 0, 0, 0, 0
    actual_input, actual_output, pending = 0, 0, 0
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            body = {k: v for k, v in event.items() if k != "event_sha256"}
            if event["sequence"] != sequence or event["previous_sha256"] != previous or event["event_sha256"] != digest(body):
                break
            previous, sequence = event["event_sha256"], sequence + 1
            if event["type"] == "request_started":
                started, pending = started + 1, pending + 1
            elif event["type"] == "response":
                record = event["record"]
                if any(type(record[k]) is not int or record[k] < 0 for k in ("input_tokens", "output_tokens")):
                    break
                replies += 1
                known_input += record["input_tokens"]
                known_output += record["output_tokens"]
                if not event["reused_shared_plan"]:
                    pending -= 1
                    actual_input += record["input_tokens"]
                    actual_output += record["output_tokens"]
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return {"known_completed_calls": replies, "known_input_tokens": known_input,
            "known_output_tokens": known_output, "pending_requests": max(0, pending),
            "actual_calls": started if backend == "openai" else 0,
            "known_actual_input_tokens": actual_input if backend == "openai" else 0,
            "known_actual_output_tokens": actual_output if backend == "openai" else 0}


def collect(directory: Path) -> dict:
    from hiergoal.study_analysis import analyze, render_markdown
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    validate_manifest(manifest)
    results = [audit_trial(directory, trial, manifest) for trial in manifest["trials"]]
    context = json.loads((directory / "host.json").read_text(encoding="utf-8"))
    summary = analyze({**manifest, "execution_context": context}, results)
    save(directory / "results.json", results)
    save(directory / "summary.json", summary)
    (directory / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
    columns = ["trial_id", "family", "instance", "condition", "repeat", "arm", "status", "success",
               "fault_triggered", "fault_delivered", "recovered", "calls", "input_tokens", "output_tokens",
               "actual_calls", "actual_input_tokens", "actual_output_tokens", "elapsed_seconds",
               "patch_actions", "replans", "invariant_ok", "protocol_ok", "audit", "diagnostic"]
    with (directory / "trials.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for trial, result in zip(manifest["trials"], results):
            writer.writerow({**trial, **result})
    return summary


def prepare(directory: Path, profile="pilot", backend="openai", model="gpt-6-luna") -> dict:
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("Output directory is not empty; choose a fresh path")
    manifest = build_manifest(profile, backend, model)
    save(directory / "manifest.json", manifest)
    save(directory / "host.json", host_metadata())
    return manifest


def run(directory: Path, *, execute=False, approve_paid_api=False, responder=None) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    validate_manifest(manifest)
    if (directory / "execution.json").exists():
        raise ValueError("Execution already started; collect existing evidence, never silently rerun")
    if manifest["backend"] == "openai":
        if not execute or not approve_paid_api:
            raise ValueError("Live execution requires --execute --approve-paid-api")
        if responder is not None:
            raise ValueError("An injected responder cannot be labeled as live model evidence")
        backend = OpenAIResponder(manifest["model"], approve_live=True,
                                  timeout=manifest["limits"]["request_timeout_seconds"])
    else:
        backend = responder or OracleResponder()
        if backend.kind != manifest["backend"]:
            raise ValueError("Responder must match the prepared backend")
    policy = manifest["execution_policy"]
    execution = {"status": "RUNNING", "protocol_id": manifest["protocol_id"],
                 "backend": backend.kind, "completed": 0, "stop_reason": None,
                 "api_error_trial_ids": [], "continued_api_error_trial_ids": []}
    # Atomic exclusive creation prevents two drivers from starting the same study.
    with (directory / "execution.json").open("x", encoding="utf-8") as stream:
        stream.write(canonical(execution) + "\n")
    start = time.monotonic()
    try:
        for trial in manifest["trials"]:
            if time.monotonic() - start > manifest["limits"]["batch_timeout_seconds"]:
                execution["stop_reason"] = "BATCH_TIME_ALLOWANCE"
                break
            task = make_trial_task(trial, manifest["task_seed"])
            result = run_trial(task, trial, manifest, backend, directory)
            execution["completed"] += 1
            # Detect apparatus regressions before paying for another trial.
            audited = audit_trial(directory, trial, manifest)
            if audited.get("audit") != "PASS":
                execution["stop_reason"] = "AUDIT_FAILED"
                save(directory / "execution.json", execution)
                break
            if result["stop_batch"]:
                isolated_http_400 = (
                    result["status"] == "UNCERTAIN"
                    and result["diagnostic"] in policy["continue_diagnostics"]
                    and result["protocol_ok"] is True and result["invariant_ok"] is True)
                if isolated_http_400:
                    # Count affected trials, including reuse of a failed shared
                    # initial plan. This is a total budget, never reset by PASS.
                    execution["api_error_trial_ids"].append(trial["trial_id"])
                    if len(execution["api_error_trial_ids"]) >= policy["max_http_400_trial_errors"]:
                        execution["stop_reason"] = "HTTP_400_TRIAL_ERROR_LIMIT"
                        save(directory / "execution.json", execution)
                        break
                    if execution["completed"] < len(manifest["trials"]):
                        execution["continued_api_error_trial_ids"].append(trial["trial_id"])
                else:
                    execution["stop_reason"] = result["diagnostic"]
                    save(directory / "execution.json", execution)
                    break
            save(directory / "execution.json", execution)
        execution["status"] = "COMPLETED" if execution["completed"] == len(manifest["trials"]) else "STOPPED"
    finally:
        save(directory / "execution.json", execution)
        summary = collect(directory)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Method study; defaults never call any API")
    parser.add_argument("command", choices=("prepare", "check", "run", "collect"), nargs="?", default="prepare")
    parser.add_argument("--output", type=Path, default=Path("runs/method-study"))
    parser.add_argument("--profile", choices=PROFILES, default="pilot")
    parser.add_argument("--model", default="gpt-6-luna")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approve-paid-api", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            manifest = prepare(args.output, args.profile, model=args.model)
            print(f"Prepared {len(manifest['trials'])} trials; NO API REQUESTS. Protocol {manifest['protocol_id']}")
        elif args.command == "check":
            prepare(args.output, args.profile, backend="oracle", model="OFFLINE_ORACLE")
            run(args.output)
            results = json.loads((args.output / "results.json").read_text())
            passed = all(r.get("status") == "PASS" and r.get("audit") == "PASS" for r in results)
            print(f"OFFLINE APPARATUS CHECK: {'PASS' if passed else 'FAIL'}; {len(results)} simulated trials; NO API REQUESTS")
            raise SystemExit(0 if passed else 1)
        elif args.command == "collect":
            collect(args.output)
            print("Replayed recorded evidence and regenerated summary; NO API REQUESTS")
        else:
            run(args.output, execute=args.execute, approve_paid_api=args.approve_paid_api)
            print("Execution finished; inspect summary.md and all trial statuses")
    except (OSError, ValueError, TransportError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
