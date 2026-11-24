# SPDX-License-Identifier: Apache-2.0
"""Budget-boundary negative controls; all responders are explicitly offline."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hiergoal.study as study
from hiergoal.study_api import TransportError
from hiergoal.study_protocol import build_manifest, canonical, digest, make_trial_task, save


def _manifest():
    return build_manifest("pilot", backend="oracle", model="OFFLINE_ORACLE")


def _run(directory, responder, *, manifest=None, arm="hierarchy_adaptive", condition="fault"):
    manifest = manifest or _manifest()
    trial = next(t for t in manifest["trials"] if t["family"] == "data_transform"
                 and t["arm"] == arm and t["condition"] == condition)
    task = make_trial_task(trial, manifest["task_seed"])
    result = study.run_trial(task, trial, manifest, responder, directory)
    trace = directory / "trials" / trial["trial_id"] / "trace.jsonl"
    return manifest, trial, result, trace


def _events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _rewrite(path, mutate):
    events = _events(path)
    mutate(events)
    previous = "0" * 64
    for index, event in enumerate(events):
        event["sequence"], event["previous_sha256"] = index, previous
        event.pop("event_sha256", None)
        event["event_sha256"] = digest(event)
        previous = event["event_sha256"]
    path.write_text("".join(canonical(event) + "\n" for event in events), encoding="utf-8")
    save(path.with_name("result.json"), {**events[-1]["result"], "trace_final_sha256": previous})


class _Claiming(study.OracleResponder):
    def respond(self, role, payload, **kwargs):
        record = super().respond(role, payload, **kwargs)
        if role == "execute":
            record["text"] = '{"success":true}'
        return record


class ReplanAttemptAccountingTests(unittest.TestCase):
    def test_issued_replan_counts_even_when_its_response_exceeds_tokens_or_time(self):
        for resource in ("tokens", "time"):
            with self.subTest(resource=resource), tempfile.TemporaryDirectory() as folder:
                directory, manifest = Path(folder), _manifest()

                class OverBudget(study.OracleResponder):
                    def respond(self, role, payload, **kwargs):
                        record = super().respond(role, payload, **kwargs)
                        if role == "replan":
                            if resource == "tokens":
                                record["input_tokens"] = manifest["limits"]["max_total_tokens"]
                                record["usage"]["input_tokens"] = record["input_tokens"]
                            else:
                                record["elapsed_seconds"] = manifest["limits"]["trial_timeout_seconds"] + 1.0
                        return record

                manifest, trial, result, trace = _run(directory, OverBudget(), manifest=manifest)
                self.assertEqual(result["status"], "FAIL", result)
                self.assertEqual(result["replan_attempts"], 1)
                self.assertEqual(result["replans"], 0)
                self.assertEqual(result["rejected_actions"], 0)
                self.assertEqual(result["calls"], 3)
                self.assertEqual(result["actual_calls"], 0)
                termination = next(event for event in _events(trace) if event["type"] == "termination")
                self.assertEqual(termination["budget"]["kind"], resource + "_after")
                audited = study.audit_trial(directory, trial, manifest)
                self.assertEqual(audited["audit"], "PASS", audited)
                self.assertEqual(audited["mechanism_evidence"]["replanning"]["attempted"], 1)

    def test_transport_failed_replan_is_an_attempt_with_unknown_usage(self):
        class FailedReplan(study.OracleResponder):
            def respond(self, role, payload, **kwargs):
                if role == "replan":
                    raise TransportError("OFFLINE_SIMULATED_REPLAN_TIMEOUT")
                return super().respond(role, payload, **kwargs)

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest, trial, result, trace = _run(directory, FailedReplan())
            self.assertEqual(result["status"], "UNCERTAIN")
            self.assertTrue(result["stop_batch"])
            self.assertEqual(result["replan_attempts"], 1)
            self.assertEqual(result["calls"], 3)
            self.assertIsNone(result["input_tokens"])
            self.assertIsNone(result["output_tokens"])
            self.assertGreater(result["known_input_tokens"], 0)
            self.assertEqual(sum(event["type"] == "request_failed" for event in _events(trace)), 1)
            audited = study.audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "PASS", audited)
            self.assertEqual(audited["mechanism_evidence"]["replanning"]["attempted"], 1)

    def test_exact_logical_time_limit_allows_completion_but_no_further_request(self):
        for finishes in (False, True):
            with self.subTest(finishes=finishes), tempfile.TemporaryDirectory() as folder:
                directory, manifest = Path(folder), _manifest()

                class AtLimit(study.OracleResponder):
                    def respond(self, role, payload, **kwargs):
                        record = super().respond(role, payload, **kwargs)
                        if role == "execute":
                            record["elapsed_seconds"] = manifest["limits"]["trial_timeout_seconds"]
                            if not finishes:
                                record["text"] = '{"success":true}'
                        return record

                manifest, trial, result, trace = _run(directory, AtLimit(), manifest=manifest, condition="normal")
                self.assertEqual(result["calls"], 2, result)
                self.assertEqual(result["status"], "PASS" if finishes else "FAIL", result)
                if not finishes:
                    termination = next(event for event in _events(trace) if event["type"] == "termination")
                    self.assertEqual(termination["budget"]["kind"], "time_before")
                    self.assertEqual(termination["budget"]["observed"], manifest["limits"]["trial_timeout_seconds"])
                self.assertEqual(study.audit_trial(directory, trial, manifest)["audit"], "PASS")


class RequestBudgetReplayTests(unittest.TestCase):
    def test_rehashed_failed_trace_cannot_issue_an_extra_request_past_call_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest, trial, result, trace = _run(directory, _Claiming(), condition="normal")
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["calls"], manifest["limits"]["max_calls"])
            self.assertEqual(study.audit_trial(directory, trial, manifest)["audit"], "PASS")

            def extra_call(events):
                stop = next(i for i, event in enumerate(events) if event["type"] == "termination")
                start = max(i for i, event in enumerate(events[:stop]) if event["type"] == "request_started")
                cycle = copy.deepcopy(events[start:stop])
                self.assertEqual([event["type"] for event in cycle], ["request_started", "response", "rejected"])
                response = cycle[1]
                response["logical_call"] += 1
                events[stop:stop] = cycle
                terminal = events[-1]["result"]
                terminal["calls"] += 1
                terminal["rejected_actions"] += 1
                for field in ("input_tokens", "output_tokens"):
                    terminal[field] += response["record"][field]
                terminal["elapsed_seconds"] += response["record"]["elapsed_seconds"]
                next(event for event in events if event["type"] == "termination")["budget"]["observed"] += 1

            _rewrite(trace, extra_call)
            audited = study.audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "FAIL", audited)
            self.assertEqual(audited["status"], "UNCERTAIN", audited)

    def test_rehashed_failed_trace_cannot_continue_at_token_or_logical_time_limit(self):
        for resource in ("tokens", "time"):
            with self.subTest(resource=resource), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                manifest, trial, result, trace = _run(directory, _Claiming(), condition="normal")
                self.assertEqual(result["status"], "FAIL")
                self.assertEqual(study.audit_trial(directory, trial, manifest)["audit"], "PASS")

                def exhausted_before_next_request(events):
                    index = next(i for i, event in enumerate(events)
                                 if event["type"] == "response" and event["role"] == "execute")
                    record = events[index]["record"]
                    prior = [event["record"] for event in events[:index] if event["type"] == "response"]
                    if resource == "tokens":
                        previous = sum(item["input_tokens"] + item["output_tokens"] for item in prior)
                        updated = manifest["limits"]["max_total_tokens"] - previous - record["output_tokens"]
                        delta = updated - record["input_tokens"]
                        record["input_tokens"] = updated
                        record["usage"]["input_tokens"] = updated
                        events[-1]["result"]["input_tokens"] += delta
                    else:
                        updated = manifest["limits"]["trial_timeout_seconds"] - sum(item["elapsed_seconds"] for item in prior)
                        delta = updated - record["elapsed_seconds"]
                        record["elapsed_seconds"] = updated
                        events[-1]["result"]["elapsed_seconds"] += delta

                _rewrite(trace, exhausted_before_next_request)
                audited = study.audit_trial(directory, trial, manifest)
                self.assertEqual(audited["audit"], "FAIL", audited)
                self.assertEqual(audited["status"], "UNCERTAIN", audited)

    def test_failed_trace_with_an_oversized_but_correct_prompt_is_rejected(self):
        class LongArtifact(study.OracleResponder):
            def respond(self, role, payload, **kwargs):
                record = super().respond(role, payload, **kwargs)
                if role == "execute":
                    record["text"] = canonical({"patch": {"report": "x" * 30000},
                        "explanation": "This accepted artifact still fails the independent report gate."})
                return record

        def issue_without_byte_guard(backend, role, payload, limits, on_start=None):
            # Deliberately generate an impossible trace: the request is otherwise
            # exactly the frozen prompt. Independent replay must detect this fault.
            if on_start:
                on_start(role, payload)
            return backend.respond(role, copy.deepcopy(payload), max_output_tokens=limits["max_output_tokens"])

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            with patch("hiergoal.study.request_record", side_effect=issue_without_byte_guard):
                manifest, trial, result, trace = _run(directory, LongArtifact(), arm="flat_retry", condition="normal")
            self.assertEqual(result["status"], "FAIL")
            oversized = [event for event in _events(trace) if event["type"] == "request_started"
                         and len(canonical(event["request"]).encode("utf-8")) > manifest["limits"]["max_prompt_bytes"]]
            self.assertTrue(oversized)
            audited = study.audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "FAIL", audited)
            self.assertEqual(audited["status"], "UNCERTAIN", audited)


if __name__ == "__main__":
    unittest.main()
