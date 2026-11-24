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
import re
import time
from pathlib import Path

from hiergoal.study_api import OpenAIResponder, TransportError
from hiergoal.study_protocol import (
    ARMS, SCHEMA, build_manifest, canonical, digest, host_metadata, save,
    validate_manifest,
)
from hiergoal.study_tasks import make_task


class InvalidAction(ValueError):
    pass


class BudgetExhausted(RuntimeError):
    pass


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


def validate_plan(value: dict, task) -> dict:
    if set(value) != {"milestones"} or not isinstance(value["milestones"], list):
        raise InvalidAction("Only milestones may be proposed; root is immutable")
    if not 2 <= len(value["milestones"]) <= 4:
        raise InvalidAction("Use 2..4 milestones")
    leaves, milestones, owners = {}, [], {}
    for item in value["milestones"]:
        if not isinstance(item, dict) or set(item) != {"id", "title", "subgoals"}:
            raise InvalidAction("Invalid milestone fields")
        mid = item["id"]
        if not isinstance(mid, str) or not re.fullmatch(r"M[1-4]", mid) or any(m["id"] == mid for m in milestones):
            raise InvalidAction("Milestone IDs must be unique M1..M4")
        milestones.append({"id": mid, "title": text_field(item["title"], "title")})
        if not isinstance(item["subgoals"], list) or not item["subgoals"]:
            raise InvalidAction("Empty milestone")
        for raw in item["subgoals"]:
            if not isinstance(raw, dict) or set(raw) != {"id", "instruction", "checks", "depends_on"}:
                raise InvalidAction("Invalid subgoal fields")
            sid = raw["id"]
            if not isinstance(sid, str) or not re.fullmatch(r"S[1-8]", sid) or sid in leaves:
                raise InvalidAction("Subgoal IDs must be unique S1..S8")
            checks, deps = raw["checks"], raw["depends_on"]
            if not isinstance(checks, list) or len(checks) != 1 or not isinstance(checks[0], str) or checks[0] not in task.gates or checks[0] in owners:
                raise InvalidAction("Assign each known gate to exactly one leaf")
            if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps) or len(set(deps)) != len(deps):
                raise InvalidAction("Invalid dependencies")
            leaves[sid] = {"id": sid, "parent": mid,
                           "instruction": text_field(raw["instruction"], "instruction"),
                           "checks": checks[:], "depends_on": deps[:], "revision": 0}
            owners[checks[0]] = sid
    if set(owners) != set(task.gates) or not 3 <= len(leaves) <= 8:
        raise InvalidAction("Missing gate coverage")
    visiting, visited = set(), set()
    def ancestors(sid):
        if sid not in leaves or sid in visiting:
            raise InvalidAction("Cyclic or dangling dependency")
        visiting.add(sid)
        result = set()
        for dep in leaves[sid]["depends_on"]:
            result.add(dep)
            result.update(ancestors(dep))
        visiting.remove(sid)
        visited.add(sid)
        return result
    for sid in leaves:
        reachable = ancestors(sid)
        gate = leaves[sid]["checks"][0]
        if any(owners[dep] not in reachable for dep in task.dependencies.get(gate, [])):
            raise InvalidAction("Plan omitted an authoritative task dependency")
    return {"milestones": milestones, "leaves": leaves}


def plan_prompt(task) -> dict:
    return {"root_contract": task.root_contract, "task": task.public_spec(),
            "gates": task.gates, "gate_dependencies": task.dependencies,
            "instruction": (
                'Return JSON {"milestones":[{"id":"M1","title":"...",'
                '"subgoals":[{"id":"S1","instruction":"...","checks":["gate_id"],'
                '"depends_on":[]}]}]}. Use 2..4 milestones M1..M4 and exactly one '
                'leaf per gate, unique S1..S8. Preserve gate dependency ordering. '
                'Give executable task-specific instructions, never edit root or acceptance rules. '
                'The environment may change; objectives refer to the current authoritative state.'
            )}


def statuses(plan, grades) -> dict:
    if plan is None:
        return {}
    output = {}
    def done(sid):
        if sid not in output:
            leaf = plan["leaves"][sid]
            passed = all(grades[c]["passed"] for c in leaf["checks"])
            dependencies = all(done(d) == "completed" for d in leaf["depends_on"])
            output[sid] = "completed" if passed and dependencies else "pending"
        return output[sid]
    for sid in plan["leaves"]:
        done(sid)
    return output


def active_leaf(plan, grades):
    if plan is None:
        return None
    state = statuses(plan, grades)
    return next((leaf for leaf in plan["leaves"].values()
                 if state[leaf["id"]] != "completed" and
                 all(state[d] == "completed" for d in leaf["depends_on"])), None)


def milestone_statuses(plan, grades):
    if plan is None:
        return {}
    children = statuses(plan, grades)
    return {mid["id"]: ("completed" if all(children[leaf["id"]] == "completed"
                      for leaf in plan["leaves"].values() if leaf["parent"] == mid["id"])
                      else "pending") for mid in plan["milestones"]}


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
    if len(canonical(payload).encode("utf-8")) > limits["max_prompt_bytes"]:
        raise BudgetExhausted("Prompt byte limit reached")
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
        value["error"] = {"status": "FAIL", "diagnostic": str(exc)}
    except TransportError as exc:
        value["error"] = {"status": "UNCERTAIN", "diagnostic": str(exc)}
    except BudgetExhausted as exc:
        value["error"] = {"status": "FAIL", "diagnostic": str(exc)}
    save(path, value)  # Also persist a failed plan: no selective reroll.
    return value, False


def run_trial(task, trial, manifest, backend, directory: Path) -> dict:
    trial_dir = directory / "trials" / trial["trial_id"]
    root_hash = digest(task.root_contract)
    trace = Trace(trial_dir / "trace.jsonl", root_hash)
    limits, arm = manifest["limits"], trial["arm"]
    started = time.monotonic()
    result = {"trial_id": trial["trial_id"], "status": "UNCERTAIN", "success": None,
              "protocol_id": manifest["protocol_id"], "backend": backend.kind,
              "fault_assigned": trial["condition"] == "fault", "fault_triggered": False,
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
            raise BudgetExhausted("Measured logical token allowance exceeded on last response")
        if (time.monotonic() - started > limits["trial_timeout_seconds"] or
                result["elapsed_seconds"] > limits["trial_timeout_seconds"]):
            raise BudgetExhausted("Trial time allowance exceeded on last response")

    def check_budget():
        if result["calls"] >= limits["max_calls"]:
            raise BudgetExhausted("Logical request allowance exhausted")
        if result["input_tokens"] + result["output_tokens"] >= limits["max_total_tokens"]:
            raise BudgetExhausted("Measured logical token allowance exhausted")
        if time.monotonic() - started >= limits["trial_timeout_seconds"]:
            raise BudgetExhausted("Trial time allowance exhausted")

    def checkpoint():
        trace.add("checkpoint", solution_sha256=digest(solution),
                  environment_sha256=digest(task.public_spec()), public_grades=grades,
                  leaf_statuses=statuses(plan, grades), milestone_statuses=milestone_statuses(plan, grades),
                  root_status="awaiting_final_verification" if all(g["passed"] for g in grades.values()) else "active",
                  plan=plan)

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
                raise TransportError(shared["error"]["diagnostic"]) if transport_failure else InvalidAction(shared["error"]["diagnostic"])
            plan = copy.deepcopy(shared["plan"])
        checkpoint()
        while True:
            if digest(task.root_contract) != root_hash:
                result["invariant_ok"] = False
                raise TransportError("Immutable root changed")
            if all(g["passed"] for g in grades.values()):
                if not checkpoint_done:
                    before_spec, before_grades = task.public_spec(), copy.deepcopy(grades)
                    checkpoint_done = True
                    if trial["condition"] == "fault":
                        result["fault_triggered"] = True
                        before = copy.deepcopy(solution)
                        solution, fault = task.inject_fault(solution)
                        grades = task.grade(solution)
                        delivered = (digest(before_spec) != digest(task.public_spec()) and
                                     all(g["passed"] for g in before_grades.values()) and
                                     not all(g["passed"] for g in grades.values()))
                        result["fault_delivered"] = delivered
                        trace.add("fault", before_solution=before, after_solution=solution,
                                  before_spec=before_spec, after_spec=task.public_spec(),
                                  before_grades=before_grades, after_grades=grades,
                                  fault=fault, delivered=delivered)
                        need_replan = delivered
                    else:
                        trace.add("sham_checkpoint", public_spec=before_spec, public_grades=grades)
                    checkpoint()
                    if not all(g["passed"] for g in grades.values()):
                        continue
                final = task.grade(solution, hidden=True)
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
                payload = {"root_contract": task.root_contract, "task": task.public_spec(),
                           "leaf": copy.deepcopy(leaf), "public_feedback": grades,
                           "artifact": solution, "history": history[-4:],
                           "instruction": 'Return JSON {"diagnosis":"specific observed cause",'
                                          '"revised_instruction":"different executable local instruction"}. '
                                          'Revise ONLY this failed leaf instruction; keep root, parent, gates and dependencies.'}
                record = request_record(backend, "replan", payload, limits, request_started)
                charge(record, "replan", payload)
                result["replan_attempts"] += 1
                need_replan = False
                try:
                    change = object_reply(record)
                    if set(change) != {"diagnosis", "revised_instruction"}:
                        raise InvalidAction("Replan may change only diagnosis and the failed instruction")
                    diagnosis = text_field(change["diagnosis"], "diagnosis")
                    instruction = text_field(change["revised_instruction"], "revised_instruction")
                    if instruction == leaf["instruction"]:
                        raise InvalidAction("Replan did not revise the instruction")
                    before = copy.deepcopy(plan)
                    leaf["instruction"], leaf["revision"] = instruction, leaf["revision"] + 1
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
            payload = {"root_contract": task.root_contract, "task": task.public_spec(),
                       "gates": task.gates, "gate_dependencies": task.dependencies,
                       "artifact": solution, "public_feedback": grades, "history": history[-4:],
                       "instruction": (
                           'Return JSON {"patch":{"existing_top_level_artifact_field": "replacement value"},'
                           '"explanation":"brief change rationale"}. You may replace any artifact fields in '
                           'every method. Use the current authoritative environment and all feedback to choose '
                           'a repair. The evaluator, not self-reported success, decides completion. '
                           'If current_leaf is present, prioritize that instruction and its dependencies; '
                           'otherwise choose the next repair directly from the root task and feedback. '
                           'Do not include root, plan, or grading changes. No external tools are available.'),
                       "current_leaf": copy.deepcopy(leaf), "plan": copy.deepcopy(plan)}
            record = request_record(backend, "execute", payload, limits, request_started)
            charge(record, "execute", payload)
            try:
                action = object_reply(record)
                before = copy.deepcopy(solution)
                solution = apply_patch(solution, action)
                result["patch_actions"] += 1
                grades = task.grade(solution)
                trace.add("patch", action=action, before_solution=before, after_solution=solution)
                checkpoint()
                history.append({"action": action, "public_feedback": grades})
                need_replan = bool(leaf and not all(grades[g]["passed"] for g in leaf["checks"]))
            except InvalidAction as exc:
                result["rejected_actions"] += 1
                trace.add("rejected", role="execute", reason=str(exc))
                history.append({"feedback": str(exc)})
                need_replan = False
            if result["input_tokens"] + result["output_tokens"] > limits["max_total_tokens"]:
                raise BudgetExhausted("Measured logical token allowance exceeded on last response")
    except (InvalidAction, BudgetExhausted) as exc:
        result.update(status="FAIL", diagnostic=str(exc))
        trace.add("termination", status="FAIL", reason=type(exc).__name__,
                  diagnostic=str(exc), wall_seconds=time.monotonic() - started)
    except TransportError as exc:
        result.update(status="UNCERTAIN", diagnostic=str(exc))
        transport_failure = True
        trace.add("termination", status="UNCERTAIN", reason="TransportError", diagnostic=str(exc))
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
        task = make_task(trial["family"], trial["instance"], split=trial["split"], seed=manifest["task_seed"])
        solution, plan, previous = task.initial_solution(), None, "0" * 64
        root_hash, final_pass, checkpoint_seen = digest(task.root_contract), False, False
        counts = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "patch_actions": 0, "replans": 0,
                  "actual_calls": 0, "actual_input_tokens": 0, "actual_output_tokens": 0}
        fault_seen, delivered, terminal, latest_reply, pending = False, False, None, None, None
        final_seen, response_consumed, elapsed, termination = False, True, 0.0, None
        replan_attempts, rejected_actions, shared_plan_count = 0, 0, 0
        observed_models = []
        allowed_events = {"initial", "request_started", "response", "shared_plan", "patch", "checkpoint",
                          "fault", "sham_checkpoint", "replan", "request_failed", "final_grade", "result", "rejected", "termination"}
        for index, event in enumerate(events):
            content = {k: v for k, v in event.items() if k != "event_sha256"}
            if (event["sequence"] != index or event["previous_sha256"] != previous or
                event["event_sha256"] != digest(content) or event["root_sha256"] != root_hash):
                raise ValueError("Broken trace chain or root invariant")
            previous = event["event_sha256"]
            kind = event["type"]
            if kind not in allowed_events or (final_seen and kind != "result"):
                raise ValueError("Unexpected event after final grading")
            if index == 0 and kind != "initial":
                raise ValueError("Missing initial evidence")
            if kind == "initial":
                if index != 0 or event["trial"] != trial or event["protocol_id"] != manifest["protocol_id"] or event["root_contract"] != task.root_contract or event["solution"] != solution or event["public_spec"] != task.public_spec() or event["public_grades"] != task.grade(solution):
                    raise ValueError("Initial evidence mismatch")
            elif kind == "request_started":
                if pending is not None or event["request"].get("root_contract") != task.root_contract or event["request"].get("task") != task.public_spec():
                    raise ValueError("Overlapping request or changed root")
                if event["role"] not in ("plan", "execute", "replan"):
                    raise ValueError("Unexpected request role")
                if event["role"] != "plan":
                    if trial["arm"] != "flat_retry" and (plan is None or shared_plan_count != 1):
                        raise ValueError("Hierarchical execution requires its shared validated plan")
                    if event["request"].get("artifact") != solution or event["request"].get("public_feedback") != task.grade(solution):
                        raise ValueError("Responder received stale artifact or feedback")
                    if event["role"] == "execute" and (event["request"].get("plan") != plan or event["request"].get("current_leaf") != active_leaf(plan, task.grade(solution))):
                        raise ValueError("Responder received a different treatment plan")
                    if event["role"] == "replan" and (trial["arm"] != "hierarchy_adaptive" or event["request"].get("leaf") != active_leaf(plan, task.grade(solution))):
                        raise ValueError("Replanning the wrong or unauthorized leaf")
                pending = {"role": event["role"], "request": event["request"]}
            elif kind == "response":
                if event["request"].get("root_contract") != task.root_contract or event["request"].get("task") != task.public_spec():
                    raise ValueError("Prompt root changed")
                if event["reused_shared_plan"]:
                    if event["role"] != "plan" or pending is not None:
                        raise ValueError("Only shared planning may be reused")
                elif pending != {"role": event["role"], "request": event["request"]}:
                    raise ValueError("Response has no matching request")
                pending, latest_reply = None, event
                response_consumed = False
                record = event["record"]
                if record["model"] not in observed_models:
                    observed_models.append(record["model"])
                if event["role"] == "replan":
                    replan_attempts += 1
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
                if bool(record["simulated"]) != (manifest["backend"] != "openai"):
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
                if shared["protocol_id"] != manifest["protocol_id"] or shared["plan"] != plan or shared["error"] != event["error"] or shared["request"] != plan_prompt(task):
                    raise ValueError("Shared planning evidence mismatch")
                if plan is not None:
                    if latest_reply is None or latest_reply["role"] != "plan" or plan != validate_plan(object_reply(latest_reply["record"]), task):
                        raise ValueError("Initial plan does not match model output")
                    if shared["protocol_id"] != manifest["protocol_id"] or shared["plan"] != plan or shared["record"] != latest_reply["record"] or shared["request"] != plan_prompt(task):
                        raise ValueError("Shared plan evidence differs across paired arms")
                elif event["error"] and event["error"]["status"] == "FAIL" and shared["record"] is not None:
                    try:
                        validate_plan(object_reply(shared["record"]), task)
                    except InvalidAction:
                        pass
                    else:
                        raise ValueError("Valid planning response incorrectly classified as failed")
            elif kind == "patch":
                if response_consumed or latest_reply is None or latest_reply["role"] != "execute" or event["action"] != object_reply(latest_reply["record"]):
                    raise ValueError("Patch does not match the model output")
                response_consumed = True
                if event["before_solution"] != solution:
                    raise ValueError("Stale artifact")
                solution = apply_patch(solution, event["action"])
                if solution != event["after_solution"]:
                    raise ValueError("Patch replay mismatch")
                counts["patch_actions"] += 1
            elif kind == "checkpoint":
                if (event["solution_sha256"] != digest(solution) or event["environment_sha256"] != digest(task.public_spec()) or
                    event["public_grades"] != task.grade(solution) or event["plan"] != plan or
                    event["leaf_statuses"] != statuses(plan, task.grade(solution)) or
                    event["milestone_statuses"] != milestone_statuses(plan, task.grade(solution)) or
                    event["root_status"] != ("awaiting_final_verification" if all(g["passed"] for g in task.grade(solution).values()) else "active")):
                    raise ValueError("Unreproducible or stale verification")
            elif kind == "fault":
                if fault_seen or trial["condition"] != "fault" or not all(g["passed"] for g in task.grade(solution).values()):
                    raise ValueError("Invalid fault checkpoint")
                before_spec = task.public_spec()
                if event["before_solution"] != solution or event["before_spec"] != before_spec or event["before_grades"] != task.grade(solution):
                    raise ValueError("Fault pre-state mismatch")
                solution, fault = task.inject_fault(solution)
                delivered = digest(before_spec) != digest(task.public_spec()) and not all(g["passed"] for g in task.grade(solution).values())
                if event["after_solution"] != solution or event["after_spec"] != task.public_spec() or event["fault"] != fault or event["delivered"] != delivered or event["after_grades"] != task.grade(solution):
                    raise ValueError("Fault replay mismatch")
                fault_seen, checkpoint_seen = True, True
            elif kind == "sham_checkpoint":
                if checkpoint_seen or trial["condition"] != "normal" or not all(g["passed"] for g in task.grade(solution).values()) or event["public_spec"] != task.public_spec() or event["public_grades"] != task.grade(solution):
                    raise ValueError("Invalid sham checkpoint")
                checkpoint_seen = True
            elif kind == "replan":
                if trial["arm"] != "hierarchy_adaptive" or event["before_plan"] != plan:
                    raise ValueError("Unauthorized plan change")
                leaf = plan["leaves"][event["leaf_id"]]
                if all(task.grade(solution)[g]["passed"] for g in leaf["checks"]):
                    raise ValueError("Unnecessary replan lacks failure evidence")
                expected = copy.deepcopy(plan)
                revised = event["after_plan"]["leaves"][event["leaf_id"]]
                if response_consumed or latest_reply is None or latest_reply["role"] != "replan":
                    raise ValueError("Replan does not match model output")
                change = object_reply(latest_reply["record"])
                if (set(change) != {"diagnosis", "revised_instruction"} or
                    text_field(change["diagnosis"], "diagnosis") != event["diagnosis"] or
                    text_field(change["revised_instruction"], "instruction") != revised["instruction"]):
                    raise ValueError("Replan does not match model output")
                response_consumed = True
                expected["leaves"][leaf["id"]]["instruction"] = text_field(revised["instruction"], "instruction")
                expected["leaves"][leaf["id"]]["revision"] += 1
                if expected != event["after_plan"] or revised["instruction"] == leaf["instruction"]:
                    raise ValueError("Replan changed unrelated goals or acceptance rules")
                if event["solution_sha256"] != digest(solution) or event["environment_sha256"] != digest(task.public_spec()) or event["public_grades"] != task.grade(solution):
                    raise ValueError("Replan used stale evidence")
                plan = expected
                counts["replans"] += 1
            elif kind == "request_failed":
                if not event["reused"] and pending != {"role": event["role"], "request": event["request"]}:
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
                if trial["arm"] != "flat_retry" and (plan is None or shared_plan_count != 1):
                    raise ValueError("Hierarchical completion lacks its shared validated plan")
                final_seen = True
                hidden = task.grade(solution, hidden=True)
                public = task.grade(solution)
                final_pass = all(g["passed"] for g in hidden.values()) and all(g["passed"] for g in public.values())
                if not checkpoint_seen or event["solution"] != solution or event["public_spec"] != task.public_spec() or event["hidden_grades"] != hidden or event["public_grades"] != public or event["passed"] != final_pass:
                    raise ValueError("Independent final grade mismatch")
            elif kind == "result":
                if index != len(events) - 1:
                    raise ValueError("Evidence recorded after terminal result")
                terminal = event["result"]
            elif kind == "termination":
                if termination is not None:
                    raise ValueError("Multiple termination reasons")
                termination = event
            elif kind == "rejected":
                if response_consumed or latest_reply is None or latest_reply["role"] != event["role"]:
                    raise ValueError("Rejection has no matching model reply")
                response_consumed = True
                rejected_actions += 1
        if terminal is None or pending is not None or result != {**terminal, "trace_final_sha256": previous}:
            raise ValueError("Missing or changed terminal result")
        if any(result[k] != v for k, v in counts.items()):
            raise ValueError("Accounting mismatch")
        if result["observed_models"] != observed_models or (manifest["backend"] == "openai" and len(observed_models) > 1):
            raise ValueError("Model changed within a trial")
        # A response that exceeds its resource limit is not processed as an
        # attempted replan. The terminal allowance event explains that one reply.
        unused_replan = int(bool(termination and termination["reason"] == "BudgetExhausted" and
                                 latest_reply and latest_reply["role"] == "replan" and not response_consumed))
        if (result["replan_attempts"] != replan_attempts - unused_replan or
            result["rejected_actions"] != rejected_actions or
            result["replan_attempts"] > manifest["limits"]["max_replans"]):
            raise ValueError("Replan/rejection accounting mismatch")
        if (result["final_artifact_sha256"] != digest(solution) or
            result["final_environment_sha256"] != digest(task.public_spec()) or
            abs(result["elapsed_seconds"] - elapsed) > 1e-8):
            raise ValueError("Final artifact/environment or logical time mismatch")
        if result["fault_delivered"] != delivered or result["fault_triggered"] != fault_seen:
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
    execution = {"status": "RUNNING", "protocol_id": manifest["protocol_id"],
                 "backend": backend.kind, "completed": 0, "stop_reason": None}
    # Atomic exclusive creation prevents two drivers from starting the same study.
    with (directory / "execution.json").open("x", encoding="utf-8") as stream:
        stream.write(canonical(execution) + "\n")
    start = time.monotonic()
    try:
        for trial in manifest["trials"]:
            if time.monotonic() - start > manifest["limits"]["batch_timeout_seconds"]:
                execution["stop_reason"] = "BATCH_TIME_ALLOWANCE"
                break
            task = make_task(trial["family"], trial["instance"], split=trial["split"], seed=manifest["task_seed"])
            result = run_trial(task, trial, manifest, backend, directory)
            execution["completed"] += 1
            save(directory / "execution.json", execution)
            if result["stop_batch"]:
                execution["stop_reason"] = result["diagnostic"]
                break
        execution["status"] = "COMPLETED" if execution["completed"] == len(manifest["trials"]) else "STOPPED"
    finally:
        save(directory / "execution.json", execution)
        summary = collect(directory)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Method study; defaults never call any API")
    parser.add_argument("command", choices=("prepare", "check", "run", "collect"), nargs="?", default="prepare")
    parser.add_argument("--output", type=Path, default=Path("runs/method-study"))
    parser.add_argument("--profile", choices=("pilot", "study"), default="pilot")
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
