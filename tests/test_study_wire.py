# SPDX-License-Identifier: Apache-2.0
import json
import os
import unittest
from unittest.mock import patch

from hiergoal.study import OracleResponder, object_reply
from hiergoal.study_api import OpenAIResponder
from hiergoal.study_planning import plan_prompt, validate_plan
from hiergoal.study_protocol import canonical, make_trial_task, build_manifest
from hiergoal.study_wire import expand_wire, response_format, wire_input, wire_metadata
from test_study_api import FakeOpener, envelope


class WireRegressionTests(unittest.TestCase):
    def test_exact_roundtrip_and_type_sensitive_aliases(self):
        payload = {"root_contract": {"same": [1, 2], "changed": 1,
                                     "gates": {"a": "A"}, "dependencies": {"a": []}},
                   "task": {"same": [1, 2], "changed": True, "environment": {"x": 2}},
                   "gates": {"a": "A"}, "gate_dependencies": {"a": []},
                   "artifact": {"x": 4}}
        original = canonical(payload)
        for role in ("plan", "execute", "replan"):
            wire = wire_input(role, payload)
            self.assertEqual(wire["task_inherits_root_contract"], ["same"])
            self.assertIs(wire["task"]["changed"], True)
            self.assertEqual(wire["root_contract_aliases"],
                             {"gates": "gates", "gate_dependencies": "dependencies"})
            self.assertEqual(canonical(expand_wire(wire)), canonical({"role": role, **payload}))
            self.assertEqual(canonical(payload), original)

    def test_prescribed_and_freeform_plans_keep_existing_validation(self):
        for profile in ("pilot", "mechanism", "scale"):
            manifest = build_manifest(profile, "oracle")
            for spec in manifest["tasks"]:
                with self.subTest(profile=profile, task=spec["task_id"]):
                    task = make_trial_task(spec, manifest["task_seed"])
                    payload = plan_prompt(task)
                    wire = wire_input("plan", payload)
                    self.assertEqual(canonical(expand_wire(wire)), canonical({"role": "plan", **payload}))
                    fmt = response_format("plan", payload)
                    self.assertTrue(fmt["strict"])
                    self.assertFalse(fmt["schema"]["additionalProperties"])
                    if profile != "pilot":
                        instructions = fmt["schema"]["properties"]["instructions"]
                        self.assertEqual(set(instructions["required"]), set(task.gates))
                        self.assertFalse(instructions["additionalProperties"])
                        self.assertTrue(all(x == {"type": "string"} for x in instructions["properties"].values()))
                    else:
                        leaf = fmt["schema"]["properties"]["milestones"]["items"]["properties"]["subgoals"]["items"]
                        self.assertEqual(leaf["properties"]["instruction"], {"type": "string"})
                        self.assertFalse(leaf["additionalProperties"])
                    oracle = OracleResponder()
                    oracle.task = task
                    result = object_reply(oracle.respond("plan", payload, max_output_tokens=8192))
                    self.assertIsNotNone(validate_plan(result, task))

    def test_real_transport_wire_format_and_receipt_without_network(self):
        manifest = build_manifest("mechanism", "oracle")
        task = make_trial_task(manifest["tasks"][0], manifest["task_seed"])
        payload = plan_prompt(task)
        opener = FakeOpener(envelope())
        with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-test"}, clear=True):
            responder = OpenAIResponder("gpt-6-luna", approve_live=True, opener=opener)
            result = responder.respond("plan", payload, max_output_tokens=4096)
        body = json.loads(opener.requests[0][0].data)
        self.assertEqual(body["text"]["format"], response_format("plan", payload))
        self.assertEqual(body["input"], canonical(wire_input("plan", payload)))
        self.assertIn("task_inherits_root_contract", body["instructions"])
        self.assertEqual(result["wire_request"], wire_metadata("plan", payload))
        self.assertEqual(response_format("execute", payload), {"type": "json_object"})
        self.assertEqual(response_format("replan", payload), {"type": "json_object"})
        self.assertEqual(len(opener.requests), 1)


if __name__ == "__main__":
    unittest.main()
