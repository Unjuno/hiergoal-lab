# SPDX-License-Identifier: Apache-2.0
"""The suite reviewer must use frozen traces rather than favorable summaries."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hiergoal.study import OracleResponder, prepare, run_trial
from hiergoal.study_protocol import canonical, digest, make_trial_task, save
from hiergoal.study_suite import review, render_markdown


class RequirementSuiteTests(unittest.TestCase):
    def test_missing_profiles_never_become_positive_evidence(self):
        with patch("hiergoal.study.OpenAIResponder", side_effect=AssertionError("No live transport")):
            report = review({})
        self.assertEqual(len(report["criteria"]), 9)
        self.assertEqual(report["engineering_decision"], "UNCERTAIN")
        self.assertEqual(report["empirical_decision"], "UNCERTAIN")
        self.assertEqual({item["code"] for item in report["input_issues"]}, {"MISSING_PROFILE"})
        self.assertIn("R9", render_markdown(report))

    def test_favorable_summary_without_executed_traces_is_replaced_by_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "mechanism"
            prepare(directory, "mechanism", "oracle", "OFFLINE_ORACLE")
            save(directory / "summary.json", {"decision": "PASS", "requirement_evidence": {
                "criteria": [{"id": "R" + str(i), "engineering_status": "PASS", "empirical_status": "PASS"}
                             for i in range(1, 10)]}})
            with patch("hiergoal.study.OpenAIResponder", side_effect=AssertionError("No live transport")):
                report = review({"mechanism": directory})
            self.assertEqual(report["engineering_decision"], "UNCERTAIN")
            self.assertEqual(report["empirical_decision"], "UNCERTAIN")
            self.assertEqual(report["profiles"]["mechanism"]["outcomes"]["NOT_RUN"], 108)
            self.assertEqual(json.loads((directory / "summary.json").read_text())["overall"]["missing"], 108)

    def test_a_favorable_profile_cannot_be_relabelled_or_run_with_changed_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "data"
            manifest = prepare(directory, "mechanism", "oracle", "OFFLINE_ORACLE")
            report = review({"scale": directory})
            self.assertIn({"profile": "scale", "code": "SOURCE_OR_REPLAY_INVALID"}, report["input_issues"])
            manifest["source_file_sha256"]["hiergoal/study.py"] = "0" * 64
            save(directory / "manifest.json", manifest)
            report = review({"mechanism": directory})
            self.assertIn({"profile": "mechanism", "code": "SOURCE_OR_REPLAY_INVALID"}, report["input_issues"])
            self.assertEqual(report["profiles"], {})
            self.assertEqual(report["empirical_decision"], "UNCERTAIN")

    def test_incompatible_models_are_not_combined_as_one_suite(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = {}
            for profile, model in (("mechanism", "ORACLE_A"), ("scale", "ORACLE_B")):
                paths[profile] = Path(temporary) / profile
                prepare(paths[profile], profile, "oracle", model)
            report = review(paths)
            self.assertIn({"profile": None, "code": "INCOMPATIBLE_PROFILE_CONTEXTS"}, report["input_issues"])
            self.assertEqual(report["empirical_decision"], "UNCERTAIN")

    def test_malformed_model_provenance_cannot_crash_the_suite_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest = prepare(directory, "mechanism", "oracle", "OFFLINE_ORACLE")
            trial = next(row for row in manifest["trials"]
                         if row["arm"] == "flat_retry" and row["condition"] == "normal")
            run_trial(make_trial_task(trial), trial, manifest, OracleResponder(), directory)
            trace = directory / "trials" / trial["trial_id"] / "trace.jsonl"
            events = [json.loads(line) for line in trace.read_text().splitlines()]
            malformed = {"unexpected": "object identifier"}
            for event in events:
                if event["type"] == "response":
                    event["record"]["model"] = malformed
            events[-1]["result"]["observed_models"] = [malformed]
            previous = "0" * 64
            for event in events:
                event["previous_sha256"] = previous
                event.pop("event_sha256", None)
                event["event_sha256"] = digest(event)
                previous = event["event_sha256"]
            trace.write_text("".join(canonical(event) + "\n" for event in events))
            save(trace.with_name("result.json"), {**events[-1]["result"], "trace_final_sha256": previous})
            report = review({"mechanism": directory})
            self.assertIn({"profile": "mechanism", "code": "SOURCE_OR_REPLAY_INVALID"}, report["input_issues"])
            self.assertEqual(report["profiles"], {})
            self.assertEqual(report["engineering_decision"], "UNCERTAIN")


if __name__ == "__main__":
    unittest.main()
