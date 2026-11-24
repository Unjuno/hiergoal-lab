# SPDX-License-Identifier: Apache-2.0
"""Synthetic analysis checks only: these tests make no model/API calls.

Fixtures labeled ``openai`` exercise the decision algorithm, not empirical
research.  Their outcomes must never be presented as observed model success.
"""
import copy
import json
import random
import unittest

from hiergoal.study_analysis import AnalysisError, analyze, render_markdown


ARMS = ("flat_retry", "hierarchy_fixed", "hierarchy_adaptive")
FAMILIES = ("code_repair", "data_transform", "scheduling")


def make_manifest(*, instances=4, repeats=3, backend="openai", profile="study"):
    trials = []
    for family in FAMILIES:
        count = instances[family] if isinstance(instances, dict) else instances
        for instance in range(count):
            task_id = f"{family}-{instance}"
            for condition in ("normal", "fault"):
                for repeat in range(1, repeats + 1):
                    block_id = f"{task_id}-{condition}-{repeat}"
                    for arm in ARMS:
                        trials.append({
                            "trial_id": f"{block_id}-{arm}", "block_id": block_id,
                            "task_id": task_id, "family": family,
                            "split": "dev" if profile == "pilot" else "heldout",
                            "instance": instance, "condition": condition,
                            "arm": arm, "repeat": repeat,
                        })
    return {
        "schema_version": "hiergoal.study.v1", "backend": backend,
        "profile": profile, "protocol_id": "SYNTHETIC-UNIT-TEST-ONLY",
        "model": "synthetic-test-fixture-not-a-model-run", "trials": trials,
        "analysis": {"minimum_effect": 0.10, "confidence": 0.95,
                     "bootstrap_samples": 128, "seed": 20261125,
                     "sign_flip_samples": 511},
    }


def make_results(manifest, success=None):
    if success is None:
        success = lambda trial: trial["condition"] == "normal" or trial["arm"] == "hierarchy_adaptive"
    results = []
    for trial in manifest["trials"]:
        passed = bool(success(trial))
        delivered = trial["condition"] == "fault"
        results.append({
            "trial_id": trial["trial_id"], "status": "PASS" if passed else "FAIL",
            "success": passed, "fault_delivered": delivered,
            "recovered": passed if delivered else None,
            "invariant_ok": True, "protocol_ok": True,
            "backend": manifest["backend"], "protocol_id": manifest["protocol_id"],
            "simulated": manifest["backend"] != "openai", "fault_assigned": delivered,
            "calls": 3, "input_tokens": 100, "output_tokens": 20,
            "actual_calls": 2 if manifest["backend"] == "openai" else 0,
            "actual_input_tokens": 80 if manifest["backend"] == "openai" else 0,
            "actual_output_tokens": 15 if manifest["backend"] == "openai" else 0,
            "elapsed_seconds": 2.5, "wall_seconds": 1.0,
            "patch_actions": 2, "replans": int(trial["arm"] == "hierarchy_adaptive"),
            "diagnostic": "synthetic unit-test record",
        })
    return results


def find_trial(manifest, *, arm="hierarchy_adaptive", condition="fault", instance=0, repeat=1,
               family="code_repair"):
    return next(trial for trial in manifest["trials"] if
                trial["arm"] == arm and trial["condition"] == condition
                and trial["instance"] == instance and trial["repeat"] == repeat
                and trial["family"] == family)


class StudyAnalysisTests(unittest.TestCase):
    def test_synthetic_advantage_exercises_both_primary_pass_criteria(self):
        manifest = make_manifest()
        summary = analyze(manifest, make_results(manifest))
        self.assertEqual(summary["decision"], "PASS")
        self.assertEqual(summary["design"]["scheduled_trials"], 216)
        self.assertEqual(summary["design"]["task_clusters"], 12)
        self.assertEqual(summary["overall"]["status_counts"], {
            "PASS": 144, "FAIL": 72, "UNCERTAIN": 0, "NOT_RUN": 0})
        self.assertEqual(summary["feasibility"]["decision"], "PASS")
        for contrast in summary["primary_contrasts"]:
            self.assertEqual(contrast["assigned_condition"], "fault")
            self.assertEqual(contrast["scheduled_pairs"], 36)
            self.assertEqual(contrast["task_clusters"], 12)
            self.assertEqual(contrast["estimate"], 1)
            self.assertEqual((contrast["ci"]["lower"], contrast["ci"]["upper"]), (1, 1))
            self.assertEqual(contrast["ci"]["confidence"], 0.975)
            self.assertEqual(contrast["test"]["p_raw"], 1 / 4096)
            self.assertEqual(contrast["test"]["p_holm"], 2 / 4096)
            self.assertEqual(contrast["test"]["draws"], 4096)
            self.assertEqual(contrast["test"]["null_difference"], 0)
            self.assertIn("conditional", contrast["test"]["validity"])
        json.dumps(summary, allow_nan=False)

    def test_null_and_one_unresolved_comparator_fail_the_joint_margin_claim(self):
        manifest = make_manifest()
        for success in (
            lambda trial: True,
            lambda trial: trial["condition"] == "normal" or trial["arm"] != "flat_retry",
        ):
            with self.subTest(success=success):
                summary = analyze(manifest, make_results(manifest, success))
                self.assertEqual(summary["decision"], "FAIL")
                fixed = summary["primary_contrasts"][0]
                self.assertEqual(fixed["estimate"], 0)
                self.assertEqual(fixed["ci"]["upper"], 0)
                self.assertEqual(fixed["test"]["p_raw"], 1)

    def test_holm_uses_step_down_correction(self):
        manifest = make_manifest()
        def success(trial):
            return (trial["condition"] == "normal" or trial["arm"] == "hierarchy_adaptive"
                    or (trial["arm"] == "hierarchy_fixed" and trial["instance"] % 2 == 1))
        summary = analyze(manifest, make_results(manifest, success))
        fixed, flat = summary["primary_contrasts"]
        self.assertEqual(fixed["test"]["p_raw"], 1 / 64)
        self.assertEqual(fixed["test"]["p_holm"], 1 / 64)
        self.assertEqual(flat["test"]["p_raw"], 1 / 4096)
        self.assertEqual(flat["test"]["p_holm"], 2 / 4096)

    def test_exact_sign_flip_includes_rational_ties(self):
        manifest = make_manifest()
        def success(trial):
            if trial["condition"] == "normal":
                return True
            if trial["family"] != "code_repair":
                return False
            difference = (-2, -1, 1, 2)[trial["instance"]]
            return (trial["repeat"] <= abs(difference)
                    and (trial["arm"] == "hierarchy_adaptive") == (difference > 0))
        summary = analyze(manifest, make_results(manifest, success))
        for contrast in summary["primary_contrasts"]:
            self.assertAlmostEqual(contrast["estimate"], 0)
            self.assertEqual(contrast["test"]["nonzero_task_differences"], 4)
            self.assertEqual(contrast["test"]["p_raw"], 10 / 16)

    def test_uncertain_and_absent_trials_remain_in_all_denominators(self):
        manifest = make_manifest()
        results = make_results(manifest)
        adaptive_id = find_trial(manifest)["trial_id"]
        fixed_id = find_trial(manifest, arm="hierarchy_fixed")["trial_id"]
        results = [row for row in results if row["trial_id"] != fixed_id]
        uncertain = next(row for row in results if row["trial_id"] == adaptive_id)
        uncertain.update(status="UNCERTAIN", success=None, recovered=None)
        summary = analyze(manifest, results)
        self.assertEqual(summary["decision"], "UNCERTAIN")
        self.assertEqual(summary["overall"]["expected"], 216)
        self.assertEqual(summary["overall"]["recorded"], 215)
        self.assertEqual(summary["overall"]["observed"], 214)
        self.assertEqual(summary["overall"]["missing"], 2)
        self.assertEqual(summary["overall"]["status_counts"]["UNCERTAIN"], 1)
        self.assertEqual(summary["overall"]["status_counts"]["NOT_RUN"], 1)
        self.assertEqual(summary["unrecorded_trial_ids"], [fixed_id])
        fixed, flat = summary["primary_contrasts"]
        self.assertAlmostEqual(fixed["sensitivity"]["lower"], 34 / 36)
        self.assertAlmostEqual(flat["sensitivity"]["lower"], 35 / 36)
        for contrast in (fixed, flat):
            self.assertEqual(contrast["sensitivity"]["upper"], 1)
            self.assertEqual(contrast["observed_pairs"], 35)
            self.assertEqual(contrast["scheduled_pairs"], 36)
            self.assertEqual(contrast["task_clusters"], 12)
            self.assertEqual(contrast["complete_task_clusters"], 11)
            self.assertIsNone(contrast["estimate"])
            self.assertIsNone(contrast["ci"])
            self.assertIsNone(contrast["test"])
        self.assertIsNone(summary["overall"]["success_rate"])
        self.assertEqual(summary["overall"]["success_rate_bounds"]["lower"], 143 / 216)
        self.assertEqual(summary["overall"]["success_rate_bounds"]["upper"], 145 / 216)

    def test_missing_normal_trial_blocks_decision_even_when_primary_data_complete(self):
        manifest = make_manifest()
        missing_id = find_trial(manifest, condition="normal")["trial_id"]
        results = [row for row in make_results(manifest) if row["trial_id"] != missing_id]
        summary = analyze(manifest, results)
        self.assertEqual(summary["decision"], "UNCERTAIN")
        self.assertTrue(all(contrast["ci"] is not None for contrast in summary["primary_contrasts"]))
        self.assertIn("missing_outcomes", summary["eligibility_blockers"])

    def test_no_results_is_explicitly_unrun_and_renderable(self):
        manifest = make_manifest()
        summary = analyze(manifest, [])
        self.assertEqual(summary["overall"]["status_counts"]["NOT_RUN"], 216)
        self.assertEqual(summary["overall"]["missing"], 216)
        self.assertIsNone(summary["overall"]["costs"]["input_tokens"]["median"])
        self.assertEqual(summary["decision"], "UNCERTAIN")
        self.assertEqual(summary["feasibility"]["decision"], "UNCERTAIN")
        for contrast in summary["primary_contrasts"]:
            self.assertEqual(contrast["sensitivity"]["lower"], -1)
            self.assertEqual(contrast["sensitivity"]["upper"], 1)
        markdown = render_markdown(summary)
        self.assertIn("Unrecorded scheduled trials: 216", markdown)
        self.assertIn("identification bounds, not confidence intervals", markdown)

    def test_prepared_not_run_placeholders_cannot_pass_feasibility(self):
        manifest = make_manifest()
        for flag in (None, True):
            with self.subTest(invariant_flag=flag):
                results = [{"trial_id": trial["trial_id"], "status": "NOT_RUN", "success": None,
                            "invariant_ok": flag, "protocol_ok": flag}
                           for trial in manifest["trials"]]
                summary = analyze(manifest, results)
                self.assertEqual(summary["overall"]["recorded"], 216)
                self.assertEqual(summary["overall"]["observed"], 0)
                self.assertEqual(summary["feasibility"]["decision"], "UNCERTAIN")
                self.assertEqual(summary["decision"], "UNCERTAIN")
                self.assertIn("do not imply execution", render_markdown(summary))

    def test_duplicate_and_unknown_results_are_rejected(self):
        manifest = make_manifest()
        results = make_results(manifest)
        with self.assertRaisesRegex(AnalysisError, "Duplicate result trial_id"):
            analyze(manifest, results + [results[0]])
        unknown = dict(results[0], trial_id="not-scheduled")
        with self.assertRaisesRegex(AnalysisError, "Unknown result trial_id"):
            analyze(manifest, [unknown])

    def test_duplicate_manifest_ids_and_unpaired_blocks_are_rejected(self):
        manifest = make_manifest()
        manifest["trials"].append(dict(manifest["trials"][0]))
        with self.assertRaisesRegex(AnalysisError, "Duplicate manifest trial_id"):
            analyze(manifest, [])
        manifest = make_manifest()
        manifest["trials"].pop()
        with self.assertRaisesRegex(AnalysisError, "exactly one trial from each arm"):
            analyze(manifest, [])

    def test_mismatched_block_covariates_are_rejected(self):
        manifest = make_manifest()
        fault = find_trial(manifest)
        normal = find_trial(manifest, condition="normal")
        fault["block_id"] = normal["block_id"]
        with self.assertRaisesRegex(AnalysisError, "Mismatched assignments within block"):
            analyze(manifest, [])

    def test_one_instance_cannot_be_renamed_into_multiple_clusters(self):
        manifest = make_manifest()
        task = find_trial(manifest)["task_id"]
        clones = [dict(trial, task_id="fake-independent-task",
                       trial_id="clone-" + trial["trial_id"], block_id="clone-" + trial["block_id"])
                  for trial in manifest["trials"] if trial["task_id"] == task]
        manifest["trials"].extend(clones)
        with self.assertRaisesRegex(AnalysisError, "multiple task clusters"):
            analyze(manifest, [])

    def test_result_covariates_never_reassign_trials(self):
        manifest = make_manifest()
        results = make_results(manifest)
        trial_id = find_trial(manifest)["trial_id"]
        next(row for row in results if row["trial_id"] == trial_id).update(
            arm="flat_retry", condition="normal", task_id="invented-cluster")
        summary = analyze(manifest, results)
        self.assertEqual(summary["decision"], "UNCERTAIN")
        self.assertEqual(summary["design"]["task_clusters"], 12)
        self.assertEqual(summary["primary_contrasts"][0]["estimate"], 1)
        self.assertEqual(len(summary["validation"]["issues"]), 3)

    def test_status_is_the_outcome_authority_and_conflicting_success_invalidates(self):
        manifest = make_manifest()
        results = make_results(manifest)
        next(row for row in results if row["status"] == "FAIL")["success"] = True
        summary = analyze(manifest, results)
        self.assertEqual(summary["overall"]["status_counts"]["FAIL"], 72)
        self.assertEqual(summary["primary_contrasts"][0]["estimate"], 1)
        self.assertEqual(summary["decision"], "UNCERTAIN")
        self.assertIn("success_status_mismatch", {item["code"] for item in summary["validation"]["issues"]})

    def test_repeats_and_acceptance_gates_cannot_create_independent_tasks(self):
        def success(trial):
            return (trial["condition"] == "normal"
                    or (trial["arm"] == "hierarchy_adaptive" and trial["instance"] % 2 == 0))
        summaries = []
        for repeats in (3, 9):
            manifest = make_manifest(repeats=repeats)
            results = make_results(manifest, success)
            for row in results:
                row["individual_gates"] = [True] * 100
            summaries.append(analyze(manifest, results))
        for first, second in zip(summaries[0]["primary_contrasts"], summaries[1]["primary_contrasts"]):
            self.assertEqual(first["task_clusters"], 12)
            self.assertEqual(second["task_clusters"], 12)
            self.assertEqual(first["ci"], second["ci"])
            self.assertEqual(first["test"], second["test"])
        self.assertFalse(summaries[1]["confirmatory_eligible"])

    def test_family_weighting_is_explicit_even_for_unbalanced_descriptive_design(self):
        manifest = make_manifest(instances={"code_repair": 4, "data_transform": 2, "scheduling": 1})
        def success(trial):
            return (trial["condition"] == "normal"
                    or (trial["family"] == "code_repair" and trial["arm"] == "hierarchy_adaptive"))
        summary = analyze(manifest, make_results(manifest, success))
        self.assertAlmostEqual(summary["primary_contrasts"][0]["estimate"], 1 / 3)
        self.assertEqual(summary["design"]["task_clusters"], 7)
        self.assertEqual(summary["decision"], "UNCERTAIN")

    def test_fault_delivery_never_filters_the_primary_itt_set(self):
        manifest = make_manifest()
        results = make_results(manifest)
        before = analyze(manifest, results)
        for row in results:
            row["fault_delivered"] = False
            row["recovered"] = None
        after = analyze(manifest, results)
        self.assertEqual(before["primary_contrasts"], after["primary_contrasts"])
        self.assertEqual(after["overall"]["expected"], 216)
        self.assertEqual(sum(row["delivered"] for row in after["recovery"]), 0)
        self.assertEqual(sum(row["not_delivered"] for row in after["recovery"]), 108)

    def test_simulations_and_pilots_cannot_be_empirical_efficacy_passes(self):
        for backend in ("oracle", "scripted"):
            with self.subTest(backend=backend):
                manifest = make_manifest(backend=backend)
                summary = analyze(manifest, make_results(manifest))
                self.assertEqual(summary["decision"], "UNCERTAIN")
                self.assertEqual(summary["evidence_kind"], "simulated_software_validation")
                self.assertEqual(summary["feasibility"]["decision"], "PASS")
                self.assertIn("Software-validation results only", render_markdown(summary))
        manifest = make_manifest(instances=1, repeats=1, profile="pilot")
        summary = analyze(manifest, make_results(manifest))
        self.assertEqual(summary["design"]["scheduled_trials"], 18)
        self.assertEqual(summary["decision"], "UNCERTAIN")
        self.assertIn("pilot_is_exploratory", summary["eligibility_blockers"])

    def test_relabeling_simulated_records_cannot_create_a_model_success_claim(self):
        manifest = make_manifest(backend="oracle")
        results = make_results(manifest)
        manifest["backend"] = "openai"
        summary = analyze(manifest, results)
        self.assertEqual(summary["decision"], "UNCERTAIN")
        self.assertIn("result_provenance_conflict", {item["code"] for item in summary["validation"]["issues"]})

    def test_engineering_invariant_and_protocol_failures_are_separate_from_effect(self):
        manifest = make_manifest()
        for field, feasibility in (("invariant_ok", "FAIL"), ("protocol_ok", "UNCERTAIN")):
            with self.subTest(field=field):
                results = make_results(manifest)
                results[0][field] = False
                summary = analyze(manifest, results)
                self.assertEqual(summary["decision"], "UNCERTAIN")
                self.assertEqual(summary["feasibility"]["decision"], feasibility)
                self.assertEqual(summary["primary_contrasts"][0]["estimate"], 1)

    def test_a_declared_failed_audit_blocks_complete_observation_claims(self):
        manifest = make_manifest()
        results = make_results(manifest)
        results[0]["audit"] = "FAIL"
        summary = analyze(manifest, results)
        self.assertEqual(summary["decision"], "UNCERTAIN")
        self.assertEqual(summary["feasibility"]["decision"], "UNCERTAIN")
        self.assertIn("completed_record_failed_audit", {item["code"] for item in summary["validation"]["issues"]})

    def test_cost_measurement_missingness_and_wall_time_are_explicit(self):
        manifest = make_manifest()
        manifest["execution_context"] = {"cpu": "unit-test hardware", "batch_size": 1,
                                          "cpu_clock_mhz_observed_range": [1000, 2000]}
        results = make_results(manifest)
        results[0]["input_tokens"] = None
        results[1]["elapsed_seconds"] = None
        summary = analyze(manifest, results)
        costs = summary["overall"]["costs"]
        self.assertEqual(costs["input_tokens"]["n_measured"], 215)
        self.assertEqual(costs["input_tokens"]["n_missing"], 1)
        self.assertEqual(costs["input_tokens"]["min"], 100)
        self.assertEqual(costs["total_tokens"]["n_measured"], 215)
        self.assertEqual(costs["total_tokens"]["median"], 120)
        self.assertEqual(costs["wall_seconds"]["median"], 1)
        self.assertEqual(costs["elapsed_seconds"]["median"], 2.5)
        markdown = render_markdown(summary)
        self.assertIn("Logical response seconds", markdown)
        self.assertIn("Trial wall seconds", markdown)
        self.assertIn("unit-test hardware", markdown)
        self.assertIn("Actual calls", markdown)

    def test_larger_cluster_count_uses_seeded_plus_one_monte_carlo(self):
        manifest = make_manifest(instances=7)
        first = analyze(manifest, make_results(manifest))
        second = analyze(manifest, make_results(manifest))
        for contrast in first["primary_contrasts"]:
            test = contrast["test"]
            self.assertEqual(test["task_clusters"], 21)
            self.assertEqual(test["method"], "monte_carlo_task_sign_flip_plus_one")
            self.assertEqual(test["draws"], 511)
            self.assertGreaterEqual(test["p_raw"], 1 / 512)
            self.assertIsNotNone(test["monte_carlo_standard_error"])
        self.assertEqual(first["primary_contrasts"], second["primary_contrasts"])

    def test_order_does_not_change_inference_and_inputs_are_not_mutated(self):
        manifest = make_manifest()
        results = make_results(manifest)
        originals = copy.deepcopy((manifest, results))
        expected = analyze(manifest, results)
        self.assertEqual((manifest, results), originals)
        random.Random(32).shuffle(manifest["trials"])
        random.Random(81).shuffle(results)
        self.assertEqual(analyze(manifest, results), expected)

    def test_malformed_values_are_rejected_instead_of_silently_coerced(self):
        for field, value in (("calls", True), ("input_tokens", -1), ("elapsed_seconds", float("nan")),
                             ("protocol_ok", "true"), ("status", "SUCCESS")):
            with self.subTest(field=field):
                manifest = make_manifest()
                results = make_results(manifest)
                results[0][field] = value
                with self.assertRaises(AnalysisError):
                    analyze(manifest, results)
        for field, value in (("bootstrap_samples", 0), ("confidence", 1.0), ("minimum_effect", 1.1)):
            with self.subTest(field=field):
                manifest = make_manifest()
                manifest["analysis"][field] = value
                with self.assertRaises(AnalysisError):
                    analyze(manifest, [])


if __name__ == "__main__":
    unittest.main()
