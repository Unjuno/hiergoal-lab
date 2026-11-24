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


def attach_synthetic_replay_evidence(manifest, results, *, forced=False, nonvacuous=True):
    """Exercise report rules with explicit synthetic receipts, not real traces."""
    manifest.update(schema_version="hiergoal.study.v2", evidence_contract="all-nine-v2",
                    limits={"max_replans": 3})
    assignments = {trial["trial_id"]: trial for trial in manifest["trials"]}
    for trial in manifest["trials"]:
        trial["fault_kind"] = "forced_subgoal" if forced else "environment"
    for row in results:
        trial = assignments[row["trial_id"]]
        hierarchy = trial["arm"] != "flat_retry"
        fault = trial["condition"] == "fault"
        replan = int(trial["arm"] == "hierarchy_adaptive" and fault)
        checked = 2 * replan if nonvacuous else 0
        row.update(audit="PASS", fault_triggered=fault, replans=replan, replan_attempts=replan)
        row["mechanism_evidence"] = {
            "trace_replayed": True, "root_preserved": True,
            "final_grade_called": True, "final_grade_passed": row["success"],
            "tree": {"goal_count": 7 if hierarchy else 1, "leaf_count": 4 if hierarchy else 0,
                     "max_depth_edges": 2 if hierarchy else 0, "dependency_edges": 2 if hierarchy else 0,
                     "dependency_density": 1 / 3 if hierarchy else 0},
            "trace": {"checkpoint_events": 3, "leaf_state_transitions": 4 if hierarchy else 0,
                      "milestone_state_transitions": 2 if hierarchy else 0,
                      "accepted_replans_with_failure_evidence": replan,
                      "post_fault_target_replans": replan,
                      "failure_causes_recorded": int(fault), "model_diagnoses_recorded": replan},
            "root_changes": {"explicit_edit_requests": 0, "rejected_edit_requests": 0, "actual_changes": 0},
            "replanning": {"attempted": replan, "accepted": replan, "rejected": 0, "unnecessary": 0,
                           "parent_preserved_events": replan, "unrelated_goals_checked": checked,
                           "unrelated_goals_unchanged": checked, "decision_events": replan,
                           "needed_decisions": replan, "deferred_progress_decisions": 0},
            "execution_locality": {"unrelated_artifact_fields_checked": checked,
                                   "unrelated_artifact_fields_unchanged": checked,
                                   "violations": 0, "nonvacuous_events": replan if nonvacuous else 0},
            "dependencies": {"invalidation_events": replan, "invalidated_goals": 2 * replan,
                             "reverified_goals": 2 * replan},
            "fault": {"triggered": fault, "delivered": row["fault_delivered"], "no_impact": False,
                      "forced": forced and fault, "domain_delivered": fault},
        }
    return results


def criteria_by_id(summary):
    return {item["id"]: item for item in summary["requirement_evidence"]["criteria"]}


def freeze_synthetic_finite_thresholds(manifest):
    manifest["analysis"]["finite_diagnostics"] = {
        "scale": {"minimum_setting_success": 0.80, "maximum_paired_drop": 0.10,
                  "baseline": {"size": "small", "depth": 3, "density": "sparse"},
                  "stress": {"size": "large", "depth": 5, "density": "dense"}},
        "reliability": {"required_repeats": 10, "minimum_task_condition_success": 0.90},
    }


def synthetic_scale_case(backend="openai"):
    manifest = make_manifest(instances=7, repeats=2, profile="scale", backend=backend)
    settings = (("small", 3, "sparse"), ("medium", 3, "sparse"), ("large", 3, "sparse"),
                ("small", 4, "sparse"), ("small", 5, "sparse"), ("small", 3, "dense"), ("large", 5, "dense"))
    for trial in manifest["trials"]:
        size, depth, density = settings[trial["instance"]]
        trial["scale"] = {"size": size, "depth": depth, "density": density}
        trial["source_instance"] = 0
    results = attach_synthetic_replay_evidence(manifest, make_results(manifest, lambda trial: True), forced=True)
    assignments = {trial["trial_id"]: trial for trial in manifest["trials"]}
    for row in results:
        trial = assignments[row["trial_id"]]
        if trial["arm"] == "flat_retry":
            continue
        setting = trial["scale"]
        components = {"small": 2, "medium": 4, "large": 8}[setting["size"]]
        leaves = components * (setting["depth"] + 1)
        edges = leaves - 1 if setting["density"] == "sparse" else leaves * (leaves - 1) // 2
        row["mechanism_evidence"]["tree"].update(
            goal_count=1 + components * (setting["depth"] - 2) + leaves,
            leaf_count=leaves, max_depth_edges=setting["depth"] - 1,
            dependency_edges=edges, dependency_density=2 * edges / (leaves * (leaves - 1)))
    return manifest, results


def synthetic_failure(row):
    row.update(status="FAIL", success=False, recovered=False if row["fault_delivered"] else None)
    row["mechanism_evidence"]["final_grade_passed"] = False


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

    def test_nine_requirements_are_explicit_and_unrun_data_cannot_pass(self):
        manifest = make_manifest()
        summary = analyze(manifest, [])
        criteria = criteria_by_id(summary)
        self.assertEqual(set(criteria), {f"R{number}" for number in range(1, 10)})
        self.assertTrue(all(item["status"] == "UNCERTAIN" for item in criteria.values()))
        self.assertTrue(all(item["engineering_status"] == "UNCERTAIN" for item in criteria.values()))
        self.assertIn("Nine requirement evidence rules", render_markdown(summary))
        self.assertIn("Zero checked objects cannot establish locality", render_markdown(summary))
        self.assertEqual(summary["scale"]["scheduled_settings"], 0)

    def test_legacy_success_flags_do_not_substitute_for_replayed_mechanisms(self):
        manifest = make_manifest()
        summary = analyze(manifest, make_results(manifest))
        self.assertEqual(summary["decision"], "PASS")  # Existing v1 algorithm fixture only.
        self.assertTrue(all(item["engineering_status"] == "UNCERTAIN"
                            for item in summary["requirement_evidence"]["criteria"]))

    def test_simulated_mechanisms_are_software_evidence_not_model_recovery(self):
        manifest = make_manifest(instances=2, repeats=3, backend="oracle", profile="mechanism")
        results = attach_synthetic_replay_evidence(manifest, make_results(manifest, lambda trial: True), forced=True)
        summary = analyze(manifest, results)
        criteria = criteria_by_id(summary)
        for identifier in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R9"):
            self.assertEqual(criteria[identifier]["engineering_status"], "PASS", identifier)
        self.assertEqual(criteria["R1"]["status"], "UNCERTAIN")
        self.assertEqual(criteria["R1"]["empirical_status"], "UNCERTAIN")
        self.assertEqual(criteria["R9"]["status"], "UNCERTAIN")
        self.assertEqual(summary["decision"], "UNCERTAIN")
        self.assertEqual(summary["design"]["scheduled_trials"], 108)
        self.assertEqual(summary["design"]["task_clusters"], 6)
        self.assertEqual(summary["primary_contrasts"], [])
        self.assertEqual(len(summary["descriptive_contrasts"]), 4)
        self.assertTrue(all(item["ci"] is None and item["test"] is None for item in summary["descriptive_contrasts"]))
        json.dumps(summary, allow_nan=False)

    def test_locality_requires_nonempty_goal_and_artifact_comparisons(self):
        for nonvacuous, expected in ((False, "UNCERTAIN"), (True, "PASS")):
            with self.subTest(nonvacuous=nonvacuous):
                manifest = make_manifest()
                results = attach_synthetic_replay_evidence(manifest, make_results(manifest), nonvacuous=nonvacuous)
                self.assertEqual(criteria_by_id(analyze(manifest, results))["R5"]["engineering_status"], expected)
        target = next(row for row in results if row["mechanism_evidence"]["replanning"]["accepted"])
        target["mechanism_evidence"]["execution_locality"].update(
            unrelated_artifact_fields_unchanged=1, violations=1)
        criteria = criteria_by_id(analyze(manifest, results))
        self.assertEqual(criteria["R5"]["engineering_status"], "FAIL")
        self.assertEqual(criteria["R5"]["evidence"]["artifact_locality_violations"], 1)

    def test_v2_requires_critical_replay_root_and_independent_grade_evidence(self):
        for field in ("mechanism_evidence", "audit", "trace_replayed", "root_preserved", "final_grade_called"):
            with self.subTest(field=field):
                manifest = make_manifest()
                results = attach_synthetic_replay_evidence(manifest, make_results(manifest))
                target = next(row for row in results if row["status"] == "PASS")
                if field in ("mechanism_evidence", "audit"):
                    target.pop(field)
                else:
                    target["mechanism_evidence"][field] = False
                summary = analyze(manifest, results)
                self.assertEqual(summary["decision"], "UNCERTAIN")
                self.assertFalse(summary["confirmatory_eligible"])
                self.assertEqual(summary["primary_contrasts"][0]["estimate"], 1)

    def test_budget_failure_can_legitimately_have_no_hidden_final_grade(self):
        manifest = make_manifest()
        results = attach_synthetic_replay_evidence(manifest, make_results(manifest))
        target = next(row for row in results if row["status"] == "FAIL")
        target["mechanism_evidence"].update(final_grade_called=False, final_grade_passed=None)
        summary = analyze(manifest, results)
        self.assertEqual(summary["validation"]["issues"], [])
        self.assertEqual(summary["decision"], "PASS")
        self.assertEqual(criteria_by_id(summary)["R7"]["evidence"]["no_final_grade"], 1)

    def test_fault_diagnostics_distinguish_no_impact_untriggered_and_unknown(self):
        manifest = make_manifest()
        results = make_results(manifest)
        assignments = {trial["trial_id"]: trial for trial in manifest["trials"]}
        for row in results:
            row["fault_triggered"] = assignments[row["trial_id"]]["condition"] == "fault"
        baseline = analyze(manifest, results)
        for instance, trigger in enumerate((False, True, None)):
            trial_id = find_trial(manifest, instance=instance)["trial_id"]
            next(row for row in results if row["trial_id"] == trial_id).update(
                fault_triggered=trigger, fault_delivered=False, recovered=None)
        summary = analyze(manifest, results)
        recovery = next(row for row in summary["recovery"] if row["arm"] == "hierarchy_adaptive")
        self.assertEqual(recovery["assigned"], 36)
        self.assertEqual(recovery["delivered"], 33)
        self.assertEqual(recovery["triggered_no_impact"], 1)
        self.assertEqual(recovery["untriggered"], 1)
        self.assertEqual(recovery["trigger_unknown"], 1)
        self.assertEqual(summary["primary_contrasts"], baseline["primary_contrasts"])

    def test_scale_is_descriptive_and_uses_its_actual_clusters_and_factor_levels(self):
        manifest, results = synthetic_scale_case()
        summary = analyze(manifest, results)
        self.assertEqual(summary["design"]["scheduled_trials"], 252)
        self.assertEqual(summary["design"]["task_clusters"], 21)
        self.assertEqual(summary["scale"]["scheduled_settings"], 7)
        self.assertEqual(summary["scale"]["scheduled_levels"]["requested_depth_levels"], [3, 4, 5])
        self.assertEqual(summary["scale"]["observed_tree_values"]["max_depth_edges"], [2, 3, 4])
        self.assertEqual(criteria_by_id(summary)["R8"]["engineering_status"], "PASS")
        self.assertEqual(summary["decision"], "UNCERTAIN")
        self.assertIn("scale_is_descriptive_only", summary["eligibility_blockers"])
        self.assertNotIn("study_requires_216_scheduled_trials", summary["eligibility_blockers"])
        self.assertEqual(summary["primary_contrasts"], [])
        self.assertTrue(all(item["task_clusters"] == 21 and item["ci"] is None and item["test"] is None
                            for item in summary["descriptive_contrasts"]))
        markdown = render_markdown(summary)
        self.assertIn("7 scale settings and 21 distinct task IDs", markdown)
        self.assertIn("not a full factorial design", markdown)
        self.assertNotIn("## Co-primary", markdown)
        self.assertIn("This schedule has 21 task clusters", markdown)

    def test_reliability_retains_clusters_and_distinguishes_mixed_from_missing(self):
        manifest = make_manifest(repeats=10, profile="reliability")
        failed_id = find_trial(manifest, repeat=2)["trial_id"]
        results = attach_synthetic_replay_evidence(manifest, make_results(manifest,
            lambda trial: trial["trial_id"] != failed_id))
        summary = analyze(manifest, results)
        self.assertEqual(summary["design"]["scheduled_trials"], 720)
        self.assertEqual(summary["design"]["task_clusters"], 12)
        self.assertEqual(summary["repeat_stability"]["minimum_scheduled_repeats"], 10)
        target = next(row for row in summary["repeat_stability"]["by_arm_condition"]
                      if row["arm"] == "hierarchy_adaptive" and row["condition"] == "fault")
        self.assertEqual(target["complete_task_clusters"], 12)
        self.assertEqual(target["clusters_all_repeats_passed"], 11)
        self.assertEqual(target["clusters_with_mixed_complete_outcomes"], 1)
        self.assertEqual(target["clusters_all_repeats_failed"], 0)
        self.assertEqual(criteria_by_id(summary)["R9"]["engineering_status"], "PASS")
        self.assertEqual(criteria_by_id(summary)["R9"]["status"], "UNCERTAIN")
        partial = analyze(manifest, [row for row in results if row["trial_id"] != failed_id])
        target = next(row for row in partial["repeat_stability"]["by_arm_condition"]
                      if row["arm"] == "hierarchy_adaptive" and row["condition"] == "fault")
        self.assertEqual(target["complete_task_clusters"], 11)
        self.assertEqual(target["clusters_with_mixed_complete_outcomes"], 0)
        self.assertEqual(criteria_by_id(partial)["R9"]["engineering_status"], "UNCERTAIN")
        self.assertEqual(len(summary["by_family_arm_condition_repeat"]), 180)

    def test_unnecessary_or_over_limit_replan_requests_fail_the_policy_requirement(self):
        for field, value in (("unnecessary", 1), ("attempted", 4)):
            with self.subTest(field=field):
                manifest = make_manifest()
                results = attach_synthetic_replay_evidence(manifest, make_results(manifest))
                target = next(row for row in results if row["mechanism_evidence"]["replanning"]["accepted"])
                target["mechanism_evidence"]["replanning"][field] = value
                self.assertEqual(criteria_by_id(analyze(manifest, results))["R6"]["engineering_status"], "FAIL")

    def test_invalid_mechanism_measurements_are_not_silently_coerced(self):
        for group, name, value in (("tree", "goal_count", True), ("tree", "dependency_density", 1.1),
                                    ("replanning", "attempted", -1), ("fault", "forced", "true")):
            with self.subTest(group=group, name=name):
                manifest = make_manifest()
                results = attach_synthetic_replay_evidence(manifest, make_results(manifest))
                results[0]["mechanism_evidence"][group][name] = value
                with self.assertRaises(AnalysisError):
                    analyze(manifest, results)

    def test_certification_only_invalidation_is_not_forced_domain_recovery(self):
        manifest = make_manifest(instances=2, profile="mechanism")
        results = attach_synthetic_replay_evidence(manifest, make_results(manifest, lambda trial: True), forced=True)
        for row in results:
            row["mechanism_evidence"]["fault"]["domain_delivered"] = False
        recovery = criteria_by_id(analyze(manifest, results))["R1"]
        self.assertGreater(recovery["evidence"]["adaptive_forced_recovered"], 0)
        self.assertEqual(recovery["evidence"]["adaptive_forced_domain_recovered"], 0)
        self.assertEqual(recovery["engineering_status"], "UNCERTAIN")

    def test_scale_factors_cannot_change_inside_a_task_cluster(self):
        manifest = make_manifest(profile="scale")
        for trial in manifest["trials"]:
            trial["scale"] = {"size": "small", "depth": 3, "density": "sparse"}
        manifest["trials"][0]["scale"] = {"size": "large", "depth": 5, "density": "dense"}
        with self.assertRaisesRegex(AnalysisError, "inconsistent scale or fault covariates"):
            analyze(manifest, [])

    def test_artifact_recovery_without_target_revision_does_not_pass_r1(self):
        manifest = make_manifest(instances=2, profile="mechanism")
        results = attach_synthetic_replay_evidence(manifest, make_results(manifest, lambda trial: True), forced=True)
        for row in results:
            row["mechanism_evidence"]["trace"]["post_fault_target_replans"] = 0
        criterion = criteria_by_id(analyze(manifest, results))["R1"]
        self.assertGreater(criterion["evidence"]["adaptive_forced_domain_recovered"], 0)
        self.assertEqual(criterion["evidence"]["adaptive_forced_modified_domain_recovered"], 0)
        self.assertEqual(criterion["status"], "FAIL")

    def test_conflicting_validity_flags_cannot_preserve_an_engineering_root_pass(self):
        manifest = make_manifest()
        results = attach_synthetic_replay_evidence(manifest, make_results(manifest))
        results[0]["invariant_ok"] = False
        criterion = criteria_by_id(analyze(manifest, results))["R3"]
        self.assertEqual(criterion["engineering_status"], "UNCERTAIN")
        self.assertEqual(criterion["evidence"]["verification_issue_trials"], 1)
        self.assertEqual(criterion["evidence"]["actual_root_changes"], 0)

    def test_synthetic_finite_scale_threshold_and_paired_drop_fail_separately(self):
        for failed_instances, expected, setting_pass, drop_pass in (
            ((), "PASS", True, True), ((1,), "PASS", True, True),
            ((1, 1), "FAIL", False, True), ((6,), "FAIL", True, False),
            ((0, 6), "PASS", True, True),
        ):
            with self.subTest(failed_instances=failed_instances):
                manifest, results = synthetic_scale_case()
                freeze_synthetic_finite_thresholds(manifest)
                counts = {}
                for instance in failed_instances:
                    repeat = counts.get(instance, 0) + 1
                    counts[instance] = repeat
                    target_id = find_trial(manifest, instance=instance, repeat=repeat)["trial_id"]
                    synthetic_failure(next(row for row in results if row["trial_id"] == target_id))
                summary = analyze(manifest, results)
                finite = summary["scale"]["finite_resilience"]
                self.assertEqual(finite["decision"], expected)
                self.assertEqual(finite["criteria"]["every_setting_meets_success_threshold"], setting_pass)
                self.assertEqual(finite["criteria"]["paired_drop_within_margin"], drop_pass)
                self.assertEqual(finite["paired_baseline_to_stress"]["observed_pairs"], 6)
                self.assertEqual(criteria_by_id(summary)["R8"]["status"], expected)
                self.assertEqual(summary["decision"], "UNCERTAIN")
                self.assertEqual(finite["scientific_sufficiency_status"], "UNCERTAIN")
        self.assertIn("Finite scale-resilience benchmark", render_markdown(summary))

    def test_finite_scale_missing_simulated_and_unassessed_locality_cannot_pass(self):
        for defect in ("missing", "oracle", "no_locality", "locality_violation"):
            with self.subTest(defect=defect):
                manifest, results = synthetic_scale_case("oracle" if defect == "oracle" else "openai")
                freeze_synthetic_finite_thresholds(manifest)
                if defect == "missing":
                    results.pop()  # Even an excluded comparator/normal cell stays required.
                elif defect in ("no_locality", "locality_violation"):
                    target_id = find_trial(manifest)["trial_id"]
                    evidence = next(row for row in results if row["trial_id"] == target_id)["mechanism_evidence"]["execution_locality"]
                    if defect == "no_locality":
                        evidence.update(unrelated_artifact_fields_checked=0, unrelated_artifact_fields_unchanged=0, nonvacuous_events=0)
                    else:
                        evidence.update(unrelated_artifact_fields_unchanged=1, violations=1)
                finite = analyze(manifest, results)["scale"]["finite_resilience"]
                self.assertEqual(finite["decision"], "FAIL" if defect == "locality_violation" else "UNCERTAIN")

    def test_synthetic_finite_repeatability_accepts_nine_but_rejects_eight_of_ten(self):
        for failures, expected in ((0, "PASS"), (1, "PASS"), (2, "FAIL")):
            with self.subTest(failures=failures):
                manifest = make_manifest(repeats=10, profile="reliability")
                results = attach_synthetic_replay_evidence(manifest, make_results(manifest, lambda trial: True))
                freeze_synthetic_finite_thresholds(manifest)
                for repeat in range(1, failures + 1):
                    target_id = find_trial(manifest, repeat=repeat)["trial_id"]
                    synthetic_failure(next(row for row in results if row["trial_id"] == target_id))
                summary = analyze(manifest, results)
                finite = summary["repeat_stability"]["finite_repeatability"]
                self.assertEqual(finite["decision"], expected)
                self.assertEqual(criteria_by_id(summary)["R9"]["status"], expected)
                self.assertEqual(finite["adaptive_task_condition_cells"], 24)
                self.assertEqual(summary["repeat_stability"]["sufficiency_status"], "UNCERTAIN")
                self.assertEqual(summary["decision"], "UNCERTAIN")
        self.assertIn("Finite repeatability benchmark", render_markdown(summary))

    def test_finite_repeatability_missing_simulated_and_invalid_records_stay_uncertain(self):
        for defect in ("missing", "oracle", "protocol"):
            with self.subTest(defect=defect):
                manifest = make_manifest(repeats=10, profile="reliability", backend="oracle" if defect == "oracle" else "openai")
                results = attach_synthetic_replay_evidence(manifest, make_results(manifest, lambda trial: True))
                freeze_synthetic_finite_thresholds(manifest)
                if defect == "missing":
                    results.pop()
                elif defect == "protocol":
                    results[0]["protocol_ok"] = False
                summary = analyze(manifest, results)
                self.assertEqual(summary["repeat_stability"]["finite_repeatability"]["decision"], "UNCERTAIN")
                self.assertEqual(criteria_by_id(summary)["R9"]["status"], "UNCERTAIN")


if __name__ == "__main__":
    unittest.main()
