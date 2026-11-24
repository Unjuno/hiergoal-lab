# SPDX-License-Identifier: Apache-2.0
"""Offline reproduction of the v2.1 live pilot's upstream regression."""
import json
import tempfile
import unittest
from pathlib import Path

from hiergoal.study import OracleResponder, audit_trial, run_trial
from hiergoal.study_protocol import build_manifest, canonical, make_trial_task
from test_study_runner import rewrite_chain


class PartialNestedRepair(OracleResponder):
    """Use a valid complete artifact, then a valid but destructive nested replacement."""

    def __init__(self):
        super().__init__()
        self.executions = 0

    def respond(self, role, payload, **kwargs):
        record = super().respond(role, payload, **kwargs)
        if role == "execute":
            self.executions += 1
            if self.executions == 2:
                self.assert_target = payload["current_leaf"]["checks"]
                adjusted = self.task.reference_solution()["expressions"]["adjusted"]
                record["text"] = canonical({
                    "patch": {"expressions": {"adjusted": adjusted}},
                    "explanation": "Replace the adjusted expression after the rate update.",
                })
        return record


class UpstreamRegressionTests(unittest.TestCase):
    def test_newly_regressed_upstream_leaf_is_authorized_and_replayed(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest = build_manifest("pilot", backend="oracle", model="OFFLINE_ORACLE")
            trial = next(t for t in manifest["trials"] if t["family"] == "code_repair"
                         and t["arm"] == "hierarchy_adaptive" and t["condition"] == "fault")
            responder = PartialNestedRepair()
            task = make_trial_task(trial, manifest["task_seed"])
            result = run_trial(task, trial, manifest, responder, directory)
            self.assertEqual(responder.assert_target, ["adjusted"])
            self.assertEqual(result["status"], "PASS", result)
            self.assertTrue(result["fault_delivered"])
            self.assertEqual(result["replans"], 2)
            trace = directory / "trials" / trial["trial_id"] / "trace.jsonl"
            events = [json.loads(line) for line in trace.read_text().splitlines()]
            requests = [e["request"]["leaf"] for e in events
                        if e["type"] == "request_started" and e["role"] == "replan"]
            self.assertEqual([leaf["checks"] for leaf in requests], [["adjusted"], ["base"]])
            audited = audit_trial(directory, trial, manifest)
            self.assertEqual(audited["audit"], "PASS", audited)
            self.assertEqual(audited["status"], "PASS", audited)
            self.assertEqual(audited["mechanism_evidence"]["replanning"]["unnecessary"], 0)
            decisions = [e for e in events if e["type"] == "replan_decision" and e["needed"]]
            self.assertEqual([e["leaf_id"] for e in decisions], [leaf["id"] for leaf in requests])

            # Retain the independent auditor: a rehashed stale authorization
            # must not become valid simply because the final artifact passes.
            def stale_decision(recorded):
                needed = [e for e in recorded if e["type"] == "replan_decision" and e["needed"]]
                needed[-1]["leaf"] = requests[0]
                needed[-1]["leaf_id"] = requests[0]["id"]

            rewrite_chain(trace, stale_decision)
            self.assertEqual(audit_trial(directory, trial, manifest)["status"], "UNCERTAIN")
            self.assertEqual(audit_trial(directory, trial, manifest)["audit"], "FAIL")
