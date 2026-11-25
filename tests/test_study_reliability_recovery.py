# SPDX-License-Identifier: Apache-2.0
"""Finite v2.4 recovery rules. Synthetic receipts never represent model runs."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hiergoal.study import OracleResponder, audit_trial, run_trial
from hiergoal.study_analysis import AnalysisError, RECOVERY_RULE, analyze, render_markdown
from hiergoal.study_protocol import FAMILIES, build_manifest, make_trial_task, profile_limits, validate_manifest
from test_study_analysis import (
    attach_synthetic_replay_evidence, criteria_by_id,
    freeze_synthetic_finite_thresholds, make_manifest, make_results, synthetic_failure,
)


def synthetic_case(profile="reliability", backend="openai"):
    manifest = make_manifest(instances=4 if profile == "reliability" else 2,
                             repeats=10 if profile == "reliability" else 3,
                             profile=profile, backend=backend)
    manifest["protocol_revision"] = "v2.4"
    results = attach_synthetic_replay_evidence(
        manifest, make_results(manifest, lambda _: True), forced=True)
    freeze_synthetic_finite_thresholds(manifest)
    config = manifest["analysis"]["finite_diagnostics"]
    config["reliability"]["recovery_rule"] = RECOVERY_RULE
    config["applicability"] = {
        "minimum_family_recovery": 0.80,
        "minimum_assigned_fault_trials_per_family": 6,
        "required_fault_kind": "forced_subgoal",
    }
    return manifest, results


def adaptive_fault_rows(manifest, results, family="code_repair", instance=None):
    ids = {trial["trial_id"] for trial in manifest["trials"]
           if trial["arm"] == "hierarchy_adaptive" and trial["condition"] == "fault"
           and trial["family"] == family and (instance is None or trial["instance"] == instance)}
    return [row for row in results if row["trial_id"] in ids]


class RecoveryReliabilityTests(unittest.TestCase):
    def test_v24_reliability_composes_all_twelve_tasks_with_matching_repair_budget(self):
        manifest = build_manifest("reliability", backend="oracle", model="OFFLINE_ORACLE")
        validate_manifest(manifest)
        self.assertEqual(manifest["protocol_revision"], "v2.5")
        self.assertEqual(len(manifest["tasks"]), 12)
        self.assertEqual(len(manifest["trials"]), 720)
        self.assertEqual(manifest["limits"], profile_limits("mechanism"))
        self.assertTrue(all(task["fault_kind"] == "forced_subgoal" and
                            task["scale"] == {"size": "small", "depth": 3, "density": "sparse"}
                            for task in manifest["tasks"]))
        self.assertEqual({task["source_instance"] for task in manifest["tasks"]}, {0, 1, 2, 3})
        study = build_manifest("study", backend="oracle", model="OFFLINE_ORACLE")
        self.assertEqual(len(study["trials"]), 216)
        self.assertTrue(all(task["fault_kind"] == "environment" and "scale" not in task for task in study["tasks"]))
        self.assertEqual(study["analysis"]["minimum_effect"], 0.10)
        self.assertEqual(study["limits"]["max_calls"], 12)

    def test_real_oracle_recovery_is_audited_in_new_reliability_tasks_for_each_family(self):
        manifest = build_manifest("reliability", backend="oracle", model="OFFLINE_ORACLE")
        with tempfile.TemporaryDirectory() as temporary, patch(
                "hiergoal.study.OpenAIResponder", side_effect=AssertionError("No live transport")) as live:
            for family in FAMILIES:
                trial = next(row for row in manifest["trials"] if row["family"] == family
                             and row["arm"] == "hierarchy_adaptive" and row["condition"] == "fault"
                             and row["source_instance"] == 3 and row["repeat"] == 10)
                result = run_trial(make_trial_task(trial), trial, manifest, OracleResponder(), Path(temporary))
                audited = audit_trial(Path(temporary), trial, manifest)
                self.assertEqual(result["status"], "PASS", result)
                self.assertEqual(audited["audit"], "PASS", audited)
                self.assertTrue(audited["simulated"])
                self.assertTrue(audited["recovered"])
                evidence = audited["mechanism_evidence"]
                self.assertTrue(evidence["fault"]["forced"])
                self.assertTrue(evidence["fault"]["domain_delivered"])
                self.assertGreater(evidence["trace"]["post_fault_target_replans"], 0)
                self.assertGreater(evidence["execution_locality"]["unrelated_artifact_fields_checked"], 0)
            live.assert_not_called()

    def test_nine_direct_repairs_pass_but_eight_fail_the_same_ten_trial_cell(self):
        for failures, expected in ((1, "PASS"), (2, "FAIL")):
            with self.subTest(failures=failures):
                manifest, results = synthetic_case()
                for row in adaptive_fault_rows(manifest, results, instance=0)[:failures]:
                    synthetic_failure(row)
                    # A legitimate pre-fault budget failure still counts as an assigned failure.
                    row.update(fault_triggered=False, fault_delivered=False, recovered=None)
                    row["mechanism_evidence"]["fault"].update(triggered=False, delivered=False,
                        forced=False, domain_delivered=False)
                    row["mechanism_evidence"].update(final_grade_called=False, final_grade_passed=None)
                    row["mechanism_evidence"]["trace"]["post_fault_target_replans"] = 0
                summary = analyze(manifest, results)
                finite = summary["repeat_stability"]["finite_repeatability"]
                self.assertEqual(summary["validation"]["issues"], [])
                self.assertEqual(finite["decision"], expected)
                self.assertEqual(criteria_by_id(summary)["R9"]["status"], expected)
                self.assertEqual(finite["scientific_sufficiency_status"], "UNCERTAIN")

    def test_final_artifact_passes_without_target_revisions_are_not_stable_repairs(self):
        manifest, results = synthetic_case()
        for row in adaptive_fault_rows(manifest, results):
            row["mechanism_evidence"]["trace"]["post_fault_target_replans"] = 0
        summary = analyze(manifest, results)
        self.assertEqual(summary["overall"]["status_counts"]["PASS"], 720)
        self.assertEqual(summary["repeat_stability"]["finite_repeatability"]["decision"], "FAIL")
        self.assertEqual(criteria_by_id(summary)["R4"]["status"], "FAIL")
        cell = next(row for row in summary["repeat_stability"]["finite_repeatability"]["by_task_condition"]
                    if row["family"] == "code_repair" and row["condition"] == "fault")
        self.assertEqual((cell["successes"], cell["final_acceptance_successes"]), (0, 10))
        self.assertIn("Final artifact success alone", render_markdown(summary))

    def test_missing_delivery_or_revision_receipts_prevent_positive_rules(self):
        for defect in ("delivery", "revision", "missing_trial", "oracle"):
            with self.subTest(defect=defect):
                manifest, results = synthetic_case(backend="oracle" if defect == "oracle" else "openai")
                target = adaptive_fault_rows(manifest, results)[0]
                if defect == "delivery":
                    target.update(fault_delivered=False, recovered=None)
                    target["mechanism_evidence"]["fault"].update(delivered=False, domain_delivered=False)
                elif defect == "revision":
                    target["mechanism_evidence"]["trace"].pop("post_fault_target_replans")
                elif defect == "missing_trial":
                    results.remove(target)
                summary = analyze(manifest, results)
                self.assertEqual(criteria_by_id(summary)["R9"]["status"], "UNCERTAIN")
                self.assertEqual(criteria_by_id(summary)["R4"]["status"], "UNCERTAIN")

    def test_family_rule_requires_each_family_and_preserves_coverage_separately(self):
        for failures, expected in ((1, "PASS"), (2, "FAIL"), (6, "FAIL")):
            with self.subTest(failures=failures):
                manifest, results = synthetic_case(profile="mechanism")
                for row in adaptive_fault_rows(manifest, results)[:failures]:
                    synthetic_failure(row)
                summary = analyze(manifest, results)
                r4 = criteria_by_id(summary)["R4"]
                self.assertEqual(r4["engineering_status"], "PASS")
                self.assertEqual(r4["status"], expected)
                family = r4["evidence"]["finite_applicability"]["by_family"][0]
                self.assertEqual((family["scheduled"], family["successful_recoveries"]), (6, 6 - failures))
        self.assertIn("Finite task-family recovery applicability", render_markdown(summary))

    def test_all_failed_families_are_coverage_pass_but_applicability_fail(self):
        manifest, results = synthetic_case(profile="mechanism")
        for row in results:
            synthetic_failure(row)
        r4 = criteria_by_id(analyze(manifest, results))["R4"]
        self.assertEqual(r4["engineering_status"], "PASS")
        self.assertEqual(r4["status"], "FAIL")

    def test_environment_only_or_insufficient_family_schedule_cannot_pass_applicability(self):
        for defect in ("environment", "few_trials"):
            with self.subTest(defect=defect):
                manifest, results = synthetic_case(profile="mechanism")
                if defect == "environment":
                    for row in manifest["trials"]:
                        row["fault_kind"] = "environment"
                else:
                    removed = {row["trial_id"] for row in manifest["trials"] if row["instance"] == 1}
                    manifest["trials"] = [row for row in manifest["trials"] if row["trial_id"] not in removed]
                    results = [row for row in results if row["trial_id"] not in removed]
                self.assertEqual(criteria_by_id(analyze(manifest, results))["R4"]["status"], "UNCERTAIN")

    def test_legacy_no_rule_keeps_historical_final_acceptance_interpretation(self):
        manifest = make_manifest(repeats=10, profile="reliability")
        manifest["protocol_revision"] = "v2.3"
        results = attach_synthetic_replay_evidence(manifest, make_results(manifest, lambda _: True))
        freeze_synthetic_finite_thresholds(manifest)
        for row in results:
            row.update(fault_delivered=False, recovered=None)
            row["mechanism_evidence"]["fault"].update(delivered=False, domain_delivered=False)
        summary = analyze(manifest, results)
        self.assertEqual(summary["repeat_stability"]["finite_repeatability"]["decision"], "PASS")
        self.assertNotIn("recovery_rule", summary["repeat_stability"]["finite_repeatability"])
        self.assertNotIn("finite_applicability", criteria_by_id(summary)["R4"]["evidence"])

    def test_unknown_frozen_rule_is_rejected(self):
        manifest, results = synthetic_case()
        manifest["analysis"]["finite_diagnostics"]["reliability"]["recovery_rule"] = "accept_self_report"
        with self.assertRaisesRegex(AnalysisError, "recovery_rule"):
            analyze(manifest, results)


if __name__ == "__main__":
    unittest.main()
