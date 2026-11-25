# SPDX-License-Identifier: Apache-2.0
"""Transport diagnostics use synthetic HTTP errors only; no real API request."""
import io
import json
import os
import unittest
import urllib.error
from datetime import datetime
from email.message import Message
from unittest.mock import patch

from hiergoal.study_api import OpenAIResponder, TransportError
from hiergoal.study_wire import wire_metadata


SECRET = "sk-offline-test-credential"
PAYLOAD = {"root_contract": {"objective": "preserve this goal"}, "instruction": "Return JSON."}


class RecordedBody(io.BytesIO):
    def __init__(self, value):
        super().__init__(value)
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


class ErrorOpener:
    def __init__(self, error):
        self.error, self.requests = error, []

    def open(self, request, timeout):
        self.requests.append(request)
        raise self.error


def http_error(body, *, status=400, headers=None):
    header_map = Message()
    for name, value in (headers or {}).items():
        header_map[name] = value
    stream = RecordedBody(body if isinstance(body, bytes) else json.dumps(body).encode())
    error = urllib.error.HTTPError("https://api.openai.com/v1/responses", status,
                                   "untrusted error message " + SECRET, header_map, stream)
    return error, stream


class HTTPDiagnosticTests(unittest.TestCase):
    def invoke(self, error):
        opener = ErrorOpener(error)
        with patch.dict(os.environ, {"OPENAI_API_KEY": SECRET}, clear=True):
            responder = OpenAIResponder("gpt-6-luna", approve_live=True, opener=opener)
            with self.assertRaises(TransportError) as caught:
                responder.respond("replan", PAYLOAD, max_output_tokens=8192)
        self.assertEqual(len(opener.requests), 1, "Transport diagnostics must not retry")
        self.assertNotIn(SECRET, str(caught.exception))
        self.assertNotIn(SECRET, json.dumps(caught.exception.evidence))
        return caught.exception

    def test_400_preserves_structured_reason_and_request_context(self):
        error, stream = http_error({"error": {"type": "invalid_request_error", "code": "invalid_value",
                                             "param": "text.format", "message": "raw prompt " + SECRET}},
                                   headers={"x-request-id": "req_offline-123", "Authorization": "Bearer " + SECRET})
        failure = self.invoke(error)
        evidence = failure.evidence
        self.assertEqual(str(failure), "OPENAI_HTTP_400")
        self.assertEqual({k: evidence[k] for k in ("http_status", "error_type", "error_code", "error_param", "request_id")},
                         {"http_status": 400, "error_type": "invalid_request_error", "error_code": "invalid_value",
                          "error_param": "text.format", "request_id": "req_offline-123"})
        self.assertEqual(evidence["wire_request"], wire_metadata("replan", PAYLOAD))
        for field in ("request_started_at_utc", "request_finished_at_utc"):
            self.assertTrue(evidence[field].endswith("Z"))
            self.assertIsNotNone(datetime.fromisoformat(evidence[field]).tzinfo)
        self.assertGreaterEqual(evidence["elapsed_seconds"], 0)
        self.assertNotIn("raw prompt", json.dumps(evidence))
        self.assertNotIn("Authorization", json.dumps(evidence))
        self.assertEqual(stream.read_sizes, [16_385])
        self.assertTrue(stream.closed)

    def test_429_keeps_bounded_rate_limit_fields_without_retry(self):
        error, _ = http_error({"error": {"type": "rate_limit_error", "code": "rate_limit_exceeded"}}, status=429,
                              headers={"Retry-After": "2.5", "x-ratelimit-limit-requests": "500",
                                       "x-ratelimit-remaining-requests": "0", "x-ratelimit-limit-tokens": "1000000",
                                       "x-ratelimit-remaining-tokens": "123", "x-private-header": SECRET})
        failure = self.invoke(error)
        self.assertEqual(str(failure), "OPENAI_HTTP_429")
        self.assertEqual(failure.evidence["retry_after_seconds"], 2.5)
        self.assertEqual(failure.evidence["rate_limits"], {"x-ratelimit-limit-requests": 500,
                         "x-ratelimit-remaining-requests": 0, "x-ratelimit-limit-tokens": 1000000,
                         "x-ratelimit-remaining-tokens": 123})
        self.assertNotIn("x-private-header", json.dumps(failure.evidence))

    def test_credentials_free_text_and_unbounded_identifiers_are_dropped(self):
        for fields in ({"type": SECRET, "code": "sk-proj-other-credential", "param": "text.format\nsecret"},
                       {"type": ["invalid_request_error"], "code": {"secret": SECRET}, "param": "x" * 161},
                       {"type": "free text error", "code": 123, "param": None}):
            with self.subTest(fields=fields):
                error, _ = http_error({"error": {**fields, "message": SECRET, "raw_body": SECRET}},
                                      headers={"x-request-id": "request-" + SECRET})
                evidence = self.invoke(error).evidence
                for key in ("error_type", "error_code", "error_param", "request_id", "message", "raw_body"):
                    self.assertNotIn(key, evidence)

    def test_oversized_body_is_bounded_and_not_partially_trusted(self):
        body = json.dumps({"error": {"type": "invalid_request_error", "message": "x" * 20_000}}).encode()
        error, stream = http_error(body)
        evidence = self.invoke(error).evidence
        self.assertEqual(evidence["error_body_status"], "oversized")
        self.assertNotIn("error_type", evidence)
        self.assertEqual(stream.read_sizes, [16_385])
        self.assertLess(len(json.dumps(evidence)), 2000)

    def test_non_json_or_unstructured_error_keeps_original_status(self):
        for body in (b"<html>unstructured response</html>", b"\xff", ["unstructured"], {"error": "unstructured"}):
            with self.subTest(body=body):
                error, _ = http_error(body)
                failure = self.invoke(error)
                self.assertEqual(str(failure), "OPENAI_HTTP_400")
                self.assertEqual(failure.evidence["http_status"], 400)
                self.assertNotIn("error_type", failure.evidence)
                self.assertNotIn("unstructured", json.dumps(failure.evidence))

    def test_invalid_retry_and_limit_values_are_not_exported(self):
        for value in ("NaN", "Infinity", "1e309", "-1", "86401", "Sun, 01 Jan 2023 00:00:00 GMT"):
            with self.subTest(value=value):
                error, _ = http_error({}, headers={"Retry-After": value, "x-ratelimit-limit-tokens": "99999999999999",
                                                  "x-ratelimit-remaining-requests": "-1"})
                evidence = self.invoke(error).evidence
                self.assertNotIn("retry_after_seconds", evidence)
                self.assertNotIn("rate_limits", evidence)

    def test_error_body_read_failure_does_not_replace_http_status(self):
        class BrokenBody(io.BytesIO):
            def read(self, size=-1):
                raise OSError("private diagnostic " + SECRET)
        error, _ = http_error({})
        error.fp = BrokenBody()
        # HTTPError delegates read through its file wrapper.
        error.file = error.fp
        failure = self.invoke(error)
        self.assertEqual(str(failure), "OPENAI_HTTP_400")
        self.assertEqual(failure.evidence["error_body_status"], "unreadable_or_non_json")
        self.assertNotIn("private diagnostic", json.dumps(failure.evidence))

    def test_non_http_diagnostic_compatibility_and_optional_evidence(self):
        failure = self.invoke(TimeoutError("private diagnostic " + SECRET))
        self.assertEqual(str(failure), "OPENAI_TRANSPORT_OR_JSON_ERROR:TimeoutError")
        self.assertEqual(failure.evidence["wire_request"], wire_metadata("replan", PAYLOAD))
        self.assertNotIn("http_status", failure.evidence)
        self.assertNotIn("private diagnostic", json.dumps(failure.evidence))
        legacy = TransportError("legacy diagnostic")
        self.assertEqual(str(legacy), "legacy diagnostic")
        self.assertIsNone(legacy.evidence)


if __name__ == "__main__":
    unittest.main()
