# SPDX-License-Identifier: Apache-2.0
"""Proof that nested goals are observed from Hermes tool results, not prose."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stream_report import parse_events


class NativeTodoTelemetry(unittest.TestCase):
    def parse(self, events):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "trace.jsonl"
            file.write_text("\n".join(json.dumps(x) for x in events), encoding="utf-8")
            return parse_events(file)

    def test_nested_todo_verified_by_tool_result(self):
        todos = [
            {"id": "G", "content": "Long", "status": "in_progress"},
            {"id": "M", "content": "Mid", "status": "pending", "parent": "G"},
            {"id": "S", "content": "Short", "status": "pending", "parent": "M"},
        ]
        data = self.parse([
            {"type": "tool_use", "name": "todo_list", "input": {"todos": todos}},
            {"type": "tool_result", "name": "todo_list",
             "output": json.dumps({"todos": todos, "revision": 1}), "is_error": False},
            {"type": "result", "exit_code": 0, "tokens": {"input": 0, "output": 0}},
        ])
        self.assertEqual(data["native_todo_list_calls"], 1)
        self.assertEqual(data["nested_todo_writes_requested"], 1)
        self.assertTrue(data["verified_nested_todo_result_observed"])
        self.assertEqual(data["readable_todo_tool_results"], 1)

    def test_a_plan_description_does_not_count_as_nested_todo(self):
        data = self.parse([
            {"type": "text", "text": "I planned long, mid, and short goals."},
            {"type": "result", "exit_code": 0, "tokens": {"input": 0, "output": 0}},
        ])
        self.assertFalse(data["verified_nested_todo_result_observed"])
        self.assertEqual(data["native_todo_list_calls"], 0)

    def test_failed_todo_write_is_not_verified(self):
        data = self.parse([
            {"type": "tool_use", "name": "todo_list",
             "input": {"todos": [{"id": "S", "content": "task",
                                   "status": "pending", "parent": "G"}]}},
            {"type": "tool_result", "name": "todo_list", "output": "error", "is_error": True},
        ])
        self.assertEqual(data["nested_todo_writes_requested"], 1)
        self.assertFalse(data["verified_nested_todo_result_observed"])


if __name__ == "__main__":
    unittest.main()
