# SPDX-License-Identifier: Apache-2.0
import io
import json
import os
import unittest
from unittest.mock import patch

from hiergoal.study_api import OpenAIResponder, TransportError


class FakeOpener:
    def __init__(self, payload):
        self.payload, self.requests = payload, []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if isinstance(self.payload, Exception):
            raise self.payload
        return io.BytesIO(json.dumps(self.payload).encode())


def envelope(**overrides):
    return {"model": "gpt-6-luna", "id": "resp_test", "status": "completed",
            "usage": {"input_tokens": 123, "output_tokens": 45},
            "output": [{"type": "reasoning", "summary": []},
                       {"type": "message", "content": [{"type": "output_text", "text": '{"patch":{}}'}]}],
            **overrides}


class StudyAPITests(unittest.TestCase):
    def test_explicit_opt_in_and_key_are_both_required(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                OpenAIResponder("gpt-6-luna")
            with self.assertRaises(ValueError):
                OpenAIResponder("gpt-6-luna", approve_live=True)

    def test_wire_request_and_usage_without_network(self):
        opener = FakeOpener(envelope())
        with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-test-secret"}, clear=True):
            responder = OpenAIResponder("gpt-6-luna", approve_live=True, opener=opener)
            result = responder.respond("execute", {"root_contract": {"goal": "test"}}, max_output_tokens=2048)
        request, timeout = opener.requests[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
        self.assertEqual(body["reasoning"], {"effort": "low"})
        self.assertEqual(body["text"], {"format": {"type": "json_object"}})
        self.assertFalse(body["store"])
        self.assertEqual(body["max_output_tokens"], 2048)
        self.assertEqual(result["input_tokens"], 123)
        self.assertEqual(result["output_tokens"], 45)
        self.assertFalse(result["simulated"])
        self.assertNotIn("offline-test-secret", json.dumps(result))
        self.assertNotIn("offline-test-secret", json.dumps(body))

    def test_missing_usage_or_wrong_model_cannot_succeed(self):
        for changes in ({"usage": None}, {"usage": {"input_tokens": True, "output_tokens": 0}},
                        {"model": "other-model"}, {"status": "queued"}):
            with self.subTest(changes=changes), patch.dict(os.environ, {"OPENAI_API_KEY": "test"}, clear=True):
                responder = OpenAIResponder("gpt-6-luna", approve_live=True, opener=FakeOpener(envelope(**changes)))
                with self.assertRaises(TransportError):
                    responder.respond("execute", {}, max_output_tokens=100)

    def test_incomplete_response_usage_is_preserved(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}, clear=True):
            result = OpenAIResponder("gpt-6-luna", approve_live=True,
                                     opener=FakeOpener(envelope(status="incomplete"))).respond(
                                         "execute", {}, max_output_tokens=100)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["output_tokens"], 45)

    def test_model_version_cannot_change_within_a_study(self):
        opener = FakeOpener(envelope(model="gpt-6-luna-snapshot-a"))
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}, clear=True):
            responder = OpenAIResponder("gpt-6-luna", approve_live=True, opener=opener)
            responder.respond("plan", {}, max_output_tokens=100)
            opener.payload = envelope(model="gpt-6-luna-snapshot-b")
            with self.assertRaises(TransportError):
                responder.respond("execute", {}, max_output_tokens=100)

    def test_network_error_is_not_retried_and_does_not_export_error_text(self):
        opener = FakeOpener(TimeoutError("authorization=should-never-be-recorded"))
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}, clear=True):
            responder = OpenAIResponder("gpt-6-luna", approve_live=True, opener=opener)
            with self.assertRaises(TransportError) as caught:
                responder.respond("execute", {}, max_output_tokens=100)
        self.assertEqual(len(opener.requests), 1)
        self.assertNotIn("authorization", str(caught.exception))

    def test_custom_endpoint_is_rejected_before_request(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test", "OPENAI_BASE_URL": "https://example.invalid"}, clear=True):
            with self.assertRaises(ValueError):
                OpenAIResponder("gpt-6-luna", approve_live=True)


if __name__ == "__main__":
    unittest.main()
