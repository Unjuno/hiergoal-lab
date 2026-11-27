# SPDX-License-Identifier: Apache-2.0
"""Independent semantic replay of the controlled recovery pilot.

The chain authenticates continuity, not the truth of a model's claims.  Every
accepted artifact is regraded and every revision is reconstructed from the
recorded response.  This module never instantiates an API responder.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

from hiergoal.study import action_prompt, apply_patch, object_reply
from hiergoal.study_mechanisms import InvalidAction, validate_replan
from hiergoal.study_planning import (
    active_leaf, milestone_statuses, plan_prompt, statuses, validate_plan,
)
from hiergoal.study_protocol import canonical, digest
from hiergoal.study_wire import wire_metadata


def _equal(left, right):
    return canonical(left) == canonical(right)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _all_pass(grades):
    return bool(grades) and all(item["passed"] is True for item in grades.values())


def _snapshot(task, solution, plan):
    grades = task.grade(solution)
    return {
        "solution": copy.deepcopy(solution), "plan": copy.deepcopy(plan),
        "public_grades": grades, "leaf_statuses": statuses(plan, grades),
        "milestone_statuses": milestone_statuses(plan, grades),
        "root_status": "awaiting_final_verification" if _all_pass(grades) else "active",
        "environment_sha256": digest(task.public_spec()),
        "root_sha256": digest(task.root_contract),
    }


def _normalize_plan(plan, task):
    if plan is None:
        return None
    by_gate = {leaf["checks"][0]: leaf for leaf in plan["leaves"].values()}
    _require(set(by_gate) == set(task.gates), "Plan gate ownership changed")
    raw = {"instructions": {gate: by_gate[gate]["instruction"] for gate in task.gates}}
    restored = validate_plan(raw, task)
    for gate in task.gates:
        leaf = by_gate[gate]
        restored["leaves"][leaf["id"]]["revision"] = leaf["revision"]
    _require(_equal(plan, restored), "Plan structure is not the prescribed hierarchy")
    return restored


def _read_events(path, root_hash):
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    _require(bool(events), "Missing trace events")
    previous = "0" * 64
    for index, event in enumerate(events):
        _require(type(event) is dict, "Trace event must be an object")
        _require(event.get("sequence") == index and type(event.get("sequence")) is int,
                 "Trace sequence mismatch")
        _require(event.get("previous_sha256") == previous, "Trace predecessor mismatch")
        _require(event.get("root_sha256") == root_hash, "Trace root changed")
        claimed = event.get("event_sha256")
        _require(claimed == digest({k: v for k, v in event.items() if k != "event_sha256"}),
                 "Trace checksum mismatch")
        previous = claimed
    return events


def _validate_record(record, manifest, role, payload, allowance, observed_model):
    _require(type(record) is dict, "Missing response record")
    for key in ("input_tokens", "output_tokens"):
        _require(type(record.get(key)) is int and record[key] >= 0, "Invalid response usage")
    _require(record["input_tokens"] > 0, "Zero response input usage")
    usage = record.get("usage")
    _require(type(usage) is dict and all(usage.get(k) == record[k]
              and type(usage.get(k)) is int for k in ("input_tokens", "output_tokens")),
             "Response usage envelope differs")
    _require(record["output_tokens"] <= allowance, "Response exceeded its output allowance")
    _require(_number(record.get("elapsed_seconds")), "Invalid request elapsed time")
    _require(record.get("status") in ("completed", "incomplete"), "Invalid response status")
    if manifest["backend"] == "openai":
        model = record.get("model")
        _require(record.get("simulated") is False, "Simulated response in live run")
        _require(type(model) is str and (model == manifest["model"] or
                 model.startswith(manifest["model"] + "-")), "Unexpected model")
        _require(observed_model is None or observed_model == model, "Observed model changed")
        _require(type(record.get("response_id")) is str and bool(record["response_id"]),
                 "Live response has no provider response identifier")
        _require(_equal(record.get("wire_request"), wire_metadata(role, payload)),
                 "Wire request does not match the logged logical request")
        return model
    _require(record.get("simulated") is True and record.get("model") == "OFFLINE_ORACLE",
             "Offline record lacks an explicit oracle label")
    return observed_model


def audit_phase(directory, trial_or_pair, manifest, checkpoint=None):
    """Audit one preparation or repair, returning failures instead of executing data."""
    directory = Path(directory)
    try:
        derived = _audit_phase(directory, trial_or_pair, manifest, checkpoint)
        return {"status": "PASS", "errors": [], "derived": derived}
    except (OSError, ValueError, TypeError, KeyError, IndexError, RecursionError) as exc:
        return {"status": "FAIL", "errors": [type(exc).__name__ + ": " + str(exc)],
                "derived": None}


def incomplete_phase_usage(directory, spec, manifest):
    """Retain bounded lower-bound accounting from a verified trace prefix.

    A killed process may have issued a billed request after request_started and
    before result.json.  Absence of a result must therefore never mean zero
    requests or complete usage.  This function does not turn a prefix into a
    semantically audited trial.  Invalid/torn suffixes remain explicitly unknown.
    """
    directory = Path(directory)
    phase = "repair" if "trial_id" in spec else "prepare"
    identifier = spec["trial_id"] if phase == "repair" else spec["pair_id"]
    previous, verified, calls, inputs, outputs = "0" * 64, 0, 0, 0, 0
    pending, prefix_status = None, "verified_prefix"
    replan_attempts, replan_rejections, replans, replan_budget = 0, 0, 0, 0
    try:
        lines = (directory / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if not line:
                continue
            event = json.loads(line)
            _require(type(event) is dict and event.get("sequence") == verified,
                     "Invalid partial sequence")
            _require(event.get("root_sha256") == spec["task"]["root_sha256"], "Invalid partial root")
            _require(event.get("previous_sha256") == previous and event.get("event_sha256") ==
                     digest({k: v for k, v in event.items() if k != "event_sha256"}), "Invalid partial checksum")
            if verified == 0:
                _require(event.get("type") == "start" and event.get("protocol_id") == manifest["protocol_id"]
                         and event.get("identifier") == identifier, "Wrong partial phase identity")
            kind = event["type"]
            if kind == "request_started":
                _require(pending is None and event.get("call_index") == calls + 1,
                         "Invalid partial request order")
                calls += 1
                pending = event
                replan_attempts += event.get("role") == "replan"
            elif kind == "response":
                _require(pending is not None and event.get("role") == pending.get("role"),
                         "Invalid partial response order")
                record = event.get("record")
                _require(type(record) is dict and all(type(record.get(k)) is int and record[k] >= 0
                          for k in ("input_tokens", "output_tokens")), "Invalid partial usage")
                inputs += record["input_tokens"]
                outputs += record["output_tokens"]
                if pending["role"] == "replan":
                    outcome = event.get("outcome", {}).get("type")
                    replan_rejections += outcome == "rejected"
                    replans += outcome == "replan"
                    replan_budget += outcome == "budget_exceeded"
                pending = None
            elif kind == "request_failed":
                _require(pending is not None and event.get("role") == pending.get("role"),
                         "Invalid partial failed request")
                pending = None
            previous, verified = event["event_sha256"], verified + 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        prefix_status = "invalid_or_torn_suffix"
    return {
        "phase": phase, "identifier": identifier, "pair_id": spec["pair_id"],
        "task_id": spec["task_id"], "arm": spec.get("arm") if phase == "repair" else None,
        "status": "UNCERTAIN", "diagnostic": "INCOMPLETE_TRACE", "success": None,
        "calls": calls if verified else None, "known_calls": calls,
        "input_tokens": None, "output_tokens": None,
        "known_input_tokens": inputs if verified else None,
        "known_output_tokens": outputs if verified else None,
        "usage_complete": False, "accounting_scope": "Verified prefix only; suffix/outstanding request usage is unknown.",
        "verified_prefix_events": verified, "prefix_status": prefix_status,
        "replan_attempts": replan_attempts if verified else None,
        "replans": replans if verified else None,
        "replan_rejections": replan_rejections if verified else None,
        "replan_budget_unapplied": replan_budget if verified else None,
        "replan_unresolved": replan_attempts - replans - replan_rejections - replan_budget if verified else None,
        "wall_seconds": None, "stop_batch": True,
    }


def _audit_phase(directory, spec, manifest, checkpoint):
    from hiergoal.recovery_protocol import make_task
    from hiergoal.recovery_checkpoint import restore_checkpoint

    phase = "repair" if "trial_id" in spec else "prepare"
    identifier = spec["trial_id"] if phase == "repair" else spec["pair_id"]
    arm = spec.get("arm") if phase == "repair" else None
    limits = manifest["limits"] if phase == "repair" else manifest["preparation_limits"]
    if phase == "repair":
        _require(checkpoint is not None, "Repair has no source checkpoint")
        _require(checkpoint.get("pair_id") == spec["pair_id"], "Repair checkpoint belongs to another pair")
        _require(_equal(checkpoint.get("task"), spec["task"]), "Repair checkpoint belongs to another task")
        task, plan, solution = restore_checkpoint(checkpoint, protocol_id=manifest["protocol_id"])
        plan = _normalize_plan(plan, task)
        checkpoint_hash = checkpoint["checkpoint_sha256"]
    else:
        task, plan = make_task(spec["task"]), None
        solution = task.initial_solution()
        checkpoint_hash = None
    _require(task.task_id == spec["task_id"], "Task identity mismatch")
    root_hash, environment_hash = digest(task.root_contract), digest(task.public_spec())
    initial_solution, initial_plan = copy.deepcopy(solution), copy.deepcopy(plan)
    history, observed_model, response_ids = [], None, []
    counts = {"calls": 0, "input_tokens": 0, "output_tokens": 0,
              "replan_attempts": 0, "replans": 0, "rejected_actions": 0,
              "patch_actions": 0}
    elapsed, last_wall, pending = 0.0, 0.0, None
    terminal_status, terminal_reason, final_grade = None, None, None
    unknown_usage, force_stop, invalid_plan, exceeded = False, False, False, False
    state_count, transitions, milestone_transitions = 1, 0, 0
    changed_unrelated, locality_observations = set(), 0
    changed_fields, instruction_diffs = [], []
    replan_rejections, replan_budget_unapplied = 0, 0
    receipt = (checkpoint or {}).get("fault_receipt", (checkpoint or {}).get("fault", {}))
    unrelated_gates = receipt.get("unrelated_component_gates", [])
    unrelated = task.artifact_projection(initial_solution, unrelated_gates) if unrelated_gates else {}
    events = _read_events(directory / "trace.jsonl", root_hash)
    start = events[0]
    _require(start.get("type") == "start", "Trace must start with a start event")
    for key, expected in {"phase": phase, "identifier": identifier, "pair_id": spec["pair_id"],
                          "protocol_id": manifest["protocol_id"], "arm": arm,
                          "task": spec["task"], "checkpoint_sha256": checkpoint_hash}.items():
        _require(_equal(start.get(key), expected), "Start " + key + " mismatch")
    _require(_equal(start.get("state"), _snapshot(task, solution, plan)), "Initial state mismatch")
    result_event = None
    for index, event in enumerate(events[1:], 1):
        kind = event.get("type")
        _require(result_event is None, "Events after result")
        _require(digest(task.root_contract) == root_hash and digest(task.public_spec()) == environment_hash,
                 "Task root or environment changed")
        grades = task.grade(solution)
        if kind == "request_started":
            _require(pending is None and terminal_status is None and final_grade is None,
                     "Request after termination or concurrent request")
            _require(not invalid_plan and not exceeded, "Request after terminal model failure")
            _require(not (plan is not None and _all_pass(grades)), "Request after completion")
            _require(counts["calls"] < limits["max_calls"], "Call cap exceeded before request")
            _require(counts["input_tokens"] + counts["output_tokens"] < limits["max_total_tokens"],
                     "Token cap exceeded before request")
            role = ("plan" if phase == "prepare" and plan is None else
                    "replan" if phase == "repair" and arm == "adaptive" and counts["calls"] == 0
                    else "execute")
            expected_payload = (plan_prompt(task) if role == "plan" else
                                action_prompt(role, task, solution, grades,
                                              plan if phase == "repair" else None,
                                              active_leaf(plan, grades) if phase == "repair" else None,
                                              history))
            _require(event.get("role") == role, "Treatment role or replan timing mismatch")
            if role == "replan":
                _require(expected_payload["leaf"]["id"] == checkpoint["target_leaf_id"],
                         "Revision did not target the injected failed subgoal")
            _require(_equal(event.get("payload"), expected_payload), "Request payload mismatch or leaked history")
            _require(len(canonical(expected_payload).encode("utf-8")) <= limits["max_prompt_bytes"],
                     "Prompt exceeds frozen byte limit")
            allowance = min(limits["max_output_tokens"], limits["max_total_tokens"]
                            - counts["input_tokens"] - counts["output_tokens"])
            _require(event.get("max_output_tokens") == allowance, "Output limit changed")
            _require(event.get("call_index") == counts["calls"] + 1, "Call index mismatch")
            wall = event.get("wall_seconds")
            _require(_number(wall) and last_wall <= wall < limits["trial_timeout_seconds"],
                     "Request violates phase timeout or monotonic time")
            last_wall = wall
            counts["calls"] += 1
            if role == "replan":
                counts["replan_attempts"] += 1
            pending = event
        elif kind == "response":
            _require(pending is not None and terminal_status is None, "Response without a request")
            role, record = pending["role"], event["record"]
            _require(event.get("role") == role, "Response role mismatch")
            observed_model = _validate_record(record, manifest, role, pending["payload"],
                                              pending["max_output_tokens"], observed_model)
            if manifest["backend"] == "openai":
                _require(record["response_id"] not in response_ids, "Provider response reused within a phase")
                response_ids.append(record["response_id"])
            counts["input_tokens"] += record["input_tokens"]
            counts["output_tokens"] += record["output_tokens"]
            elapsed += record["elapsed_seconds"]
            wall = event.get("wall_seconds")
            _require(_number(wall) and wall >= last_wall, "Nonmonotonic response time")
            last_wall = wall
            before = _snapshot(task, solution, plan)
            action, reason = None, None
            if counts["input_tokens"] + counts["output_tokens"] > limits["max_total_tokens"]:
                outcome_type, exceeded = "budget_exceeded", True
                reason = "TOKEN_BUDGET_AFTER"
            elif wall > limits["trial_timeout_seconds"]:
                outcome_type, exceeded = "budget_exceeded", True
                reason = "TIME_BUDGET_AFTER"
            else:
                try:
                    action = object_reply(record)
                    if role == "plan":
                        plan = validate_plan(action, task)
                        outcome_type = "plan"
                    elif role == "replan":
                        plan, _ = validate_replan(plan, active_leaf(plan, grades), grades, action)
                        counts["replans"] += 1
                        outcome_type = "replan"
                    else:
                        solution = apply_patch(solution, action)
                        counts["patch_actions"] += 1
                        history.append({"action": action, "public_feedback": task.grade(solution)})
                        outcome_type = "patch"
                except InvalidAction as exc:
                    outcome_type, reason = "rejected", str(exc)
                    counts["rejected_actions"] += 1
                    if role == "replan":
                        replan_rejections += 1
                    history.append({"feedback": reason})
                    invalid_plan = role == "plan"
            expected_outcome = {"type": outcome_type, "action": action, "reason": reason}
            if role == "replan" and outcome_type == "budget_exceeded":
                replan_budget_unapplied += 1
            _require(_equal(event.get("outcome"), expected_outcome), "Response outcome is not reproducible")
            after = _snapshot(task, solution, plan)
            _require(_equal(event.get("state"), after), "Recorded state does not match applied action")
            state_count += 1
            transitions += sum(before["leaf_statuses"].get(k) != v for k, v in after["leaf_statuses"].items())
            milestone_transitions += sum(before["milestone_statuses"].get(k) != v
                                         for k, v in after["milestone_statuses"].items())
            changed_fields.append(sorted(k for k in solution if not _equal(before["solution"][k], solution[k])))
            if before["plan"] is not None and plan is not None:
                instruction_diffs.append([{"leaf_id": k, "before": before["plan"]["leaves"][k]["instruction"],
                                           "after": value["instruction"]}
                                          for k, value in plan["leaves"].items()
                                          if not _equal(before["plan"]["leaves"][k], value)])
            if outcome_type == "patch":
                locality_observations += len(unrelated)
                changed_unrelated.update(k for k, value in unrelated.items() if not _equal(solution[k], value))
            pending = None
        elif kind == "request_failed":
            _require(pending is not None and terminal_status is None, "Failed request has no pending request")
            _require(event.get("role") == pending["role"], "Failed request role mismatch")
            _require(type(event.get("diagnostic")) is str, "Failed request lacks diagnostic")
            unknown_usage, force_stop = True, True
            pending = None
        elif kind == "grade":
            _require(pending is None and terminal_status is None and final_grade is None and plan is not None,
                     "Grade at an invalid phase boundary")
            _require(not exceeded and not invalid_plan and not unknown_usage, "Grade after a terminal failure")
            _require(_all_pass(grades), "Hidden grading before all public checks passed")
            hidden = task.grade(solution, hidden=True)
            passed = _all_pass(hidden)
            expected_grade = {"public_grades": grades, "hidden_grades": hidden,
                              "passed": passed, "solution_sha256": digest(solution)}
            for key, value in expected_grade.items():
                _require(_equal(event.get(key), value), "Final grading differs: " + key)
            final_grade = expected_grade
            terminal_status = "PASS" if passed else "FAIL"
        elif kind == "termination":
            _require(pending is None and terminal_status is None and final_grade is None,
                     "Duplicate or premature termination")
            status, reason = event.get("status"), event.get("reason")
            _require(status in ("FAIL", "UNCERTAIN"), "Invalid termination status")
            _require(type(event.get("diagnostic")) is str and _number(event.get("wall_seconds")),
                     "Invalid termination evidence")
            _require(event["wall_seconds"] >= last_wall, "Nonmonotonic termination time")
            budget = event.get("budget") or {}
            if status == "UNCERTAIN":
                _require(reason in ("TRANSPORT_ERROR", "APPARATUS_ERROR"), "Unknown uncertain termination")
                _require(unknown_usage or reason == "APPARATUS_ERROR", "Unexplained uncertain termination")
                force_stop = True
            elif reason == "INVALID_PLAN":
                _require(invalid_plan, "Invalid-plan termination without rejected planning response")
            elif reason in ("CALL_BUDGET_BEFORE", "TOKEN_BUDGET_BEFORE", "TIME_BUDGET_BEFORE",
                            "PROMPT_BUDGET_BEFORE", "TOKEN_BUDGET_AFTER", "TIME_BUDGET_AFTER"):
                diagnostic = event["diagnostic"]
                _require(diagnostic == reason, "Budget diagnostic/reason mismatch")
                if diagnostic == "TOKEN_BUDGET_AFTER":
                    _require(exceeded and counts["input_tokens"] + counts["output_tokens"] > limits["max_total_tokens"],
                             "Token-after failure without measured overshoot")
                    observed, limit = counts["input_tokens"] + counts["output_tokens"], limits["max_total_tokens"]
                elif diagnostic == "TIME_BUDGET_AFTER":
                    _require(exceeded and last_wall > limits["trial_timeout_seconds"],
                             "Time-after failure without measured overshoot")
                    observed, limit = last_wall, limits["trial_timeout_seconds"]
                elif diagnostic == "CALL_BUDGET_BEFORE":
                    _require(counts["calls"] >= limits["max_calls"], "Unjustified call budget failure")
                    observed, limit = counts["calls"], limits["max_calls"]
                elif diagnostic == "TOKEN_BUDGET_BEFORE":
                    _require(counts["input_tokens"] + counts["output_tokens"] >= limits["max_total_tokens"],
                             "Unjustified token budget failure")
                    observed, limit = counts["input_tokens"] + counts["output_tokens"], limits["max_total_tokens"]
                elif diagnostic == "TIME_BUDGET_BEFORE":
                    _require(event["wall_seconds"] >= limits["trial_timeout_seconds"],
                             "Unjustified time budget failure")
                    observed, limit = budget.get("observed"), limits["trial_timeout_seconds"]
                    _require(_number(observed) and limit <= observed <= event["wall_seconds"],
                             "Invalid time-before measurement")
                elif diagnostic == "PROMPT_BUDGET_BEFORE":
                    role = "plan" if phase == "prepare" and plan is None else (
                        "replan" if phase == "repair" and arm == "adaptive" and counts["calls"] == 0 else "execute")
                    payload = (plan_prompt(task) if role == "plan" else
                               action_prompt(role, task, solution, grades,
                                             plan if phase == "repair" else None,
                                             active_leaf(plan, grades) if phase == "repair" else None, history))
                    _require(len(canonical(payload).encode("utf-8")) > limits["max_prompt_bytes"],
                             "Unjustified prompt budget failure")
                    observed, limit = len(canonical(payload).encode("utf-8")), limits["max_prompt_bytes"]
                    _require(budget.get("role") == role and _equal(budget.get("payload"), payload),
                             "Prompt limit lacks the exact blocked request")
                else:
                    raise ValueError("Unknown budget termination")
                _require(_equal(budget.get("observed"), observed) and _equal(budget.get("limit"), limit),
                         "Budget measurements do not replay")
            else:
                raise ValueError("Unverifiable termination reason")
            terminal_status, terminal_reason = status, event["diagnostic"]
        elif kind == "result":
            _require(index == len(events) - 1 and pending is None and terminal_status is not None,
                     "Result without a terminal decision")
            result_event = event["result"]
        else:
            raise ValueError("Unknown or misordered trace event: " + str(kind))
    _require(result_event is not None, "Trace has no final result")
    derived = {
        "phase": phase, "identifier": identifier, "pair_id": spec["pair_id"],
        "task_id": spec["task_id"], "arm": arm, "status": terminal_status,
        **counts, "known_input_tokens": counts["input_tokens"],
        "known_output_tokens": counts["output_tokens"], "invariant_ok": True,
        "elapsed_seconds": elapsed,
        "success": True if terminal_status == "PASS" else False if terminal_status == "FAIL" else None,
        "simulated": manifest["backend"] == "oracle", "stop_batch": force_stop,
        "final_solution": solution, "final_plan": plan,
        "final_artifact_sha256": digest(solution), "final_plan_sha256": digest(plan),
        "final_environment_sha256": environment_hash,
    }
    if unknown_usage:
        derived["input_tokens"] = derived["output_tokens"] = None
    for key, value in derived.items():
        _require(_equal(result_event.get(key), value), "Result does not replay: " + key)
    _require(_number(result_event.get("wall_seconds")) and result_event["wall_seconds"] >= last_wall,
             "Invalid final wall time")
    if terminal_reason is not None:
        _require(result_event.get("diagnostic") == terminal_reason, "Termination/result diagnostic mismatch")
    elif final_grade is not None:
        _require(result_event.get("diagnostic") == ("INDEPENDENT_GRADING_PASS" if final_grade["passed"] else "HIDDEN_GRADING_FAIL"),
                 "Grade/result diagnostic mismatch")
    saved = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    _require(_equal(saved, {**result_event, "trace_final_sha256": events[-1]["event_sha256"]}),
             "Saved result differs from terminal trace")
    derived.update({"elapsed_api_seconds": elapsed, "wall_seconds": result_event["wall_seconds"],
                    "trace_final_sha256": events[-1]["event_sha256"],
                    "root_unchanged": True, "state_snapshots": state_count,
                    "leaf_transitions": transitions, "milestone_transitions": milestone_transitions,
                    "unrelated_field_observations": locality_observations,
                    "unrelated_changed_fields": sorted(changed_unrelated),
                    "locality_ok": not changed_unrelated if phase == "repair" else None,
                    "artifact_field_changes": changed_fields, "instruction_diffs": instruction_diffs,
                    "initial_artifact_sha256": digest(initial_solution),
                    "initial_plan_sha256": digest(initial_plan),
                    "checkpoint_sha256": checkpoint_hash, "observed_model": observed_model})
    derived["response_ids"] = response_ids
    derived["replan_rejections"] = replan_rejections
    derived["replan_budget_unapplied"] = replan_budget_unapplied
    derived["replan_unresolved"] = counts["replan_attempts"] - counts["replans"] - replan_rejections - replan_budget_unapplied
    return derived


def audit_all(output, manifest):
    """Audit preparations first, then bind each repair to that exact source."""
    from hiergoal.recovery_protocol import validate_manifest
    from hiergoal.recovery_checkpoint import restore_checkpoint

    output = Path(output)
    validate_manifest(manifest)
    preparations, trials, checkpoints = {}, {}, {}
    for pair in manifest["pairs"]:
        ident = pair["pair_id"]
        folder = output / "preparations" / ident
        if not (folder / "trace.jsonl").exists():
            orphan = (folder / "result.json").exists() or (output / "checkpoints" / (ident + ".json")).exists()
            preparations[ident] = {"status": "FAIL" if orphan else "NOT_RUN",
                                   "errors": ["Preparation evidence exists without its trace"] if orphan else [],
                                   "derived": None}
            continue
        report = audit_phase(folder, pair, manifest)
        preparations[ident] = report
        path = output / "checkpoints" / (ident + ".json")
        if report["status"] != "PASS" or report["derived"]["status"] != "PASS":
            if path.exists():
                report.update(status="FAIL", errors=["Checkpoint exists without a verified source PASS"])
            continue
        try:
            checkpoint = json.loads(path.read_text(encoding="utf-8"))
            restore_checkpoint(checkpoint, pair=pair, protocol_id=manifest["protocol_id"])
            _require(checkpoint.get("source_trace_sha256") == report["derived"]["trace_final_sha256"],
                     "Checkpoint source trace differs")
            _require(_equal(checkpoint.get("source_solution"), report["derived"]["final_solution"]),
                     "Checkpoint source artifact differs")
            _require(_equal(checkpoint.get("plan"), report["derived"]["final_plan"]),
                     "Checkpoint source plan differs")
            checkpoints[ident] = checkpoint
        except (OSError, ValueError, TypeError, KeyError) as exc:
            report.update(status="FAIL", errors=["Source checkpoint: " + str(exc)])
    for trial in manifest["trials"]:
        ident, pair_id = trial["trial_id"], trial["pair_id"]
        folder = output / "trials" / ident
        if not (folder / "trace.jsonl").exists():
            orphan = (folder / "result.json").exists()
            trials[ident] = {"status": "FAIL" if orphan else "NOT_RUN",
                             "errors": ["Repair result exists without its trace"] if orphan else [], "derived": None}
        elif pair_id not in checkpoints:
            trials[ident] = {"status": "FAIL", "errors": ["Repair source did not pass independent audit"],
                             "derived": None}
        else:
            trials[ident] = audit_phase(folder, trial, manifest, checkpoints[pair_id])
    reports = [*preparations.values(), *trials.values()]
    global_errors = []
    execution_path = output / "execution.json"
    execution_state = None
    if execution_path.exists():
        try:
            execution = json.loads(execution_path.read_text(encoding="utf-8"))
            _require(execution.get("protocol_id") == manifest["protocol_id"] and
                     execution.get("backend") == manifest["backend"], "Execution identity mismatch")
            execution_state = execution.get("state")
            _require(execution_state in ("RUNNING", "COMPLETED", "STOPPED"), "Invalid execution state")
            stopped = False
            for pair in manifest["pairs"]:
                preparation = preparations[pair["pair_id"]]
                arm_reports = [trials[pair["pair_id"] + "-" + arm] for arm in pair["arm_order"]]
                if stopped:
                    _require(all(report["status"] == "NOT_RUN" for report in [preparation, *arm_reports]),
                             "Execution continued after a frozen stop or missing earlier phase")
                    continue
                if preparation["status"] != "PASS":
                    stopped = True
                    _require(all(report["status"] == "NOT_RUN" for report in arm_reports),
                             "Repair issued after unaudited preparation")
                    continue
                source = preparation["derived"]
                if source["stop_batch"]:
                    stopped = True
                    _require(all(report["status"] == "NOT_RUN" for report in arm_reports),
                             "Repair issued after source transport failure")
                    continue
                if source["status"] == "FAIL":
                    _require(all(report["status"] == "NOT_RUN" for report in arm_reports),
                             "Failed source was rerun or used for repair")
                    continue
                for report in arm_reports:
                    if stopped:
                        _require(report["status"] == "NOT_RUN", "Repair continued after a frozen stop")
                    elif report["status"] != "PASS" or report["derived"]["stop_batch"]:
                        stopped = True
            if execution_state == "COMPLETED":
                _require(not stopped, "Execution claims completion despite missing/stopped phases")
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            global_errors.append(str(exc))
    if manifest["backend"] == "openai":
        models, response_ids = set(), []
        for report in reports:
            if report["status"] == "PASS":
                derived = report["derived"]
                if derived.get("observed_model") is not None:
                    models.add(derived["observed_model"])
                response_ids.extend(derived.get("response_ids", []))
        if len(models) > 1:
            global_errors.append("Provider model version changed between phases")
        if len(response_ids) != len(set(response_ids)):
            global_errors.append("Provider response identifier reused between phases")
    status = "FAIL" if any(x["status"] == "FAIL" for x in reports) else (
        "PASS" if all(x["status"] == "PASS" for x in reports) else "INCOMPLETE")
    if global_errors:
        status = "FAIL"
    elif status == "PASS" and execution_state != "COMPLETED":
        status = "INCOMPLETE"
    return {"status": status, "errors": global_errors, "execution_state": execution_state,
            "preparations": preparations, "trials": trials}
