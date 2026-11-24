# SPDX-License-Identifier: Apache-2.0
"""Paired, task-clustered analysis of the frozen HierGoal method study.

``analyze`` performs no model calls and does not modify its inputs.  A manifest
is the assignment authority: result metadata never changes an arm, condition,
task, or repeat.  The caller must separately validate the frozen manifest and
its source fingerprints; this module cannot attest to the origin of records.

The estimand is the equally weighted mean across the three task families of
the mean task-level success difference.  Repeats are averaged within each
task, and each repeat compares the assigned arms in the same block.  Missing
outcomes are retained, with sharp binary-outcome bounds instead of an assumed
failure or a complete-case confirmatory estimate.

The two co-primary contrasts use a family-stratified task bootstrap with
Bonferroni-adjusted, two-sided percentile intervals.  One-sided sign-flip
tests concern a zero difference, with Holm correction across the two tests;
the intervals separately assess the practical minimum-effect margin.  The
sign-flip distribution is exact only conditional on the required symmetry or
exchangeability assumptions.  Repeated stochastic calls and acceptance gates
are never counted as independent tasks.
"""
from __future__ import annotations

import math
import random
import statistics
from collections import Counter, defaultdict
from fractions import Fraction
from typing import Any


SCHEMA = "hiergoal.study.v1"
ARMS = ("flat_retry", "hierarchy_fixed", "hierarchy_adaptive")
FAMILIES = ("code_repair", "data_transform", "scheduling")
CONDITIONS = ("normal", "fault")
STATUSES = ("PASS", "FAIL", "UNCERTAIN", "NOT_RUN")
COMPARATORS = ("hierarchy_fixed", "flat_retry")
ASSIGNMENT_FIELDS = (
    "block_id", "task_id", "family", "split", "instance", "condition", "arm", "repeat",
)
INTEGER_METRICS = (
    "calls", "input_tokens", "output_tokens", "patch_actions", "replans",
    "actual_calls", "actual_input_tokens", "actual_output_tokens",
)
METRICS = (
    "calls", "input_tokens", "output_tokens", "total_tokens", "elapsed_seconds", "wall_seconds",
    "patch_actions", "replans", "actual_calls", "actual_input_tokens",
    "actual_output_tokens", "actual_total_tokens",
)


class AnalysisError(ValueError):
    """Records cannot be safely joined or their declared schema is malformed."""


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise AnalysisError(f"{label} must be an integer >= {minimum}")
    return value


def _number(value: Any, label: str, *, minimum: float = 0.0) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < minimum):
        raise AnalysisError(f"{label} must be a finite number >= {minimum}")
    return float(value)


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnalysisError(f"{label} must be a nonempty string")
    return value


def _validate_manifest(manifest: dict) -> tuple[list[dict], dict]:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA:
        raise AnalysisError(f"manifest schema_version must be {SCHEMA}")
    if manifest.get("backend") not in ("openai", "oracle", "scripted"):
        raise AnalysisError("Unknown backend")
    if manifest.get("profile") not in ("pilot", "study"):
        raise AnalysisError("Unknown profile")
    for name in ("protocol_id", "model"):
        _string(manifest.get(name), name)
    trials = manifest.get("trials")
    if not isinstance(trials, list) or not trials:
        raise AnalysisError("manifest.trials must be a nonempty list")
    seen_ids, cluster_identity, identity_cluster = set(), {}, {}
    blocks = defaultdict(list)
    for trial in trials:
        if not isinstance(trial, dict):
            raise AnalysisError("Every manifest trial must be an object")
        for key in ("trial_id", "block_id", "task_id", "family", "split"):
            _string(trial.get(key), f"trial.{key}")
        trial_id = trial["trial_id"]
        if trial_id in seen_ids:
            raise AnalysisError(f"Duplicate manifest trial_id: {trial_id}")
        seen_ids.add(trial_id)
        if trial.get("arm") not in ARMS or trial.get("condition") not in CONDITIONS:
            raise AnalysisError(f"Unknown arm/condition for {trial_id}")
        instance = trial.get("instance")
        if type(instance) not in (int, str) or (isinstance(instance, str) and not instance.strip()):
            raise AnalysisError(f"Invalid instance for {trial_id}")
        _integer(trial.get("repeat"), f"repeat for {trial_id}")
        identity = (trial["family"], trial["split"], type(instance).__name__, instance)
        previous = cluster_identity.setdefault(trial["task_id"], identity)
        if previous != identity:
            raise AnalysisError(f"Task cluster has inconsistent identity: {trial['task_id']}")
        previous_task = identity_cluster.setdefault(identity, trial["task_id"])
        if previous_task != trial["task_id"]:
            raise AnalysisError("One family/split/instance cannot be counted as multiple task clusters")
        blocks[trial["block_id"]].append(trial)
    block_keys = set()
    for block_id, members in blocks.items():
        first = members[0]
        keys = ("task_id", "family", "split", "instance", "condition", "repeat")
        if any(any(item[key] != first[key] for key in keys) for item in members):
            raise AnalysisError(f"Mismatched assignments within block: {block_id}")
        if len(members) != len(ARMS) or Counter(item["arm"] for item in members) != Counter(ARMS):
            raise AnalysisError(f"Block must contain exactly one trial from each arm: {block_id}")
        key = (first["task_id"], first["condition"], first["repeat"])
        if key in block_keys:
            raise AnalysisError("A task/condition/repeat has multiple block IDs")
        block_keys.add(key)
    config = manifest.get("analysis", {})
    if not isinstance(config, dict):
        raise AnalysisError("manifest.analysis must be an object")
    effect = _number(config.get("minimum_effect", 0.10), "minimum_effect")
    confidence = _number(config.get("confidence", 0.95), "confidence")
    if effect > 1.0 or not 0.0 < confidence < 1.0:
        raise AnalysisError("minimum_effect must be <= 1 and confidence must be between 0 and 1")
    settings = {
        "minimum_effect": effect,
        "confidence": confidence,
        "bootstrap_samples": _integer(config.get("bootstrap_samples", 5000), "bootstrap_samples", minimum=2),
        "seed": _integer(config.get("seed", 20261125), "seed"),
        "sign_flip_samples": _integer(config.get("sign_flip_samples", 50000), "sign_flip_samples", minimum=1),
    }
    return sorted(trials, key=lambda item: item["trial_id"]), settings


def _join_results(trials: list[dict], results: list[dict], manifest: dict) -> tuple[list[dict], list[dict]]:
    if not isinstance(results, list):
        raise AnalysisError("results must be a list")
    assignments = {trial["trial_id"]: trial for trial in trials}
    indexed, issues = {}, []
    for record in results:
        if not isinstance(record, dict):
            raise AnalysisError("Every result must be an object")
        trial_id = _string(record.get("trial_id"), "result.trial_id")
        if trial_id not in assignments:
            raise AnalysisError(f"Unknown result trial_id: {trial_id}")
        if trial_id in indexed:
            raise AnalysisError(f"Duplicate result trial_id: {trial_id}")
        if record.get("status") not in STATUSES:
            raise AnalysisError(f"Unknown result status for {trial_id}")
        for field in ("success", "fault_delivered", "recovered", "invariant_ok", "protocol_ok", "simulated", "fault_assigned"):
            if record.get(field) is not None and type(record[field]) is not bool:
                raise AnalysisError(f"{field} must be boolean or null for {trial_id}")
        for field in INTEGER_METRICS:
            if record.get(field) is not None:
                _integer(record[field], f"{field} for {trial_id}")
        for field in ("elapsed_seconds", "wall_seconds"):
            if record.get(field) is not None:
                _number(record[field], f"{field} for {trial_id}")
        indexed[trial_id] = record
    rows = []
    for trial in trials:
        trial_id = trial["trial_id"]
        record = indexed.get(trial_id)
        row = dict(trial)
        row["recorded"] = record is not None
        row["status"] = record["status"] if record is not None else "NOT_RUN"
        row["outcome"] = {"PASS": 1, "FAIL": 0}.get(row["status"])
        for key in (*INTEGER_METRICS, "elapsed_seconds", "wall_seconds", "fault_delivered", "recovered", "invariant_ok", "protocol_ok"):
            row[key] = record.get(key) if record is not None else None
        for prefix in ("", "actual_"):
            input_tokens, output_tokens = row[prefix + "input_tokens"], row[prefix + "output_tokens"]
            row[prefix + "total_tokens"] = (
                input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None
            )
        if record is not None:
            def issue(code: str, field: str | None = None) -> None:
                item = {"trial_id": trial_id, "code": code}
                if field is not None:
                    item["field"] = field
                issues.append(item)

            for field in ASSIGNMENT_FIELDS:
                if field in record and record[field] != trial[field]:
                    issue("result_assignment_conflict", field)
            for field in ("backend", "protocol_id"):
                if field in record and record[field] != manifest[field]:
                    issue("result_provenance_conflict", field)
            if "simulated" in record and record["simulated"] is not (manifest["backend"] != "openai"):
                issue("result_provenance_conflict", "simulated")
            if "fault_assigned" in record and record["fault_assigned"] is not (trial["condition"] == "fault"):
                issue("result_assignment_conflict", "fault_assigned")
            if row["outcome"] is not None and "audit" in record and record["audit"] != "PASS":
                issue("completed_record_failed_audit")
            claimed = record.get("success")
            if ((row["outcome"] is not None and claimed is not bool(row["outcome"]))
                    or (row["outcome"] is None and claimed is not None)):
                issue("success_status_mismatch")
            for field in ("protocol_ok", "invariant_ok"):
                if row[field] is None:
                    issue("missing_validity_flag", field)
                elif row[field] is False:
                    issue(field + "_false")
            if row["fault_delivered"] is None and row["status"] != "NOT_RUN":
                issue("missing_fault_delivery_flag")
            if row["condition"] == "normal" and row["fault_delivered"] is True:
                issue("fault_delivered_in_normal_condition")
            if row["recovered"] is True and (row["fault_delivered"] is not True or row["status"] != "PASS"):
                issue("recovery_without_delivered_fault_and_success")
            if (row["fault_delivered"] is True and row["outcome"] is not None
                    and row["recovered"] is not bool(row["outcome"])):
                issue("recovery_status_mismatch")
        rows.append(row)
    return rows, issues


def _metric_summary(values: list[Any], denominator: int) -> dict:
    measured = [value for value in values if value is not None]
    return {
        "n_measured": len(measured), "n_missing": denominator - len(measured),
        "median": statistics.median(measured) if measured else None,
        "min": min(measured) if measured else None,
        "max": max(measured) if measured else None,
    }


def _summarize_rows(rows: list[dict]) -> dict:
    counts = {status: sum(row["status"] == status for row in rows) for status in STATUSES}
    expected = len(rows)
    observed = counts["PASS"] + counts["FAIL"]
    missing = expected - observed
    return {
        "expected": expected, "recorded": sum(row["recorded"] for row in rows),
        "unrecorded": sum(not row["recorded"] for row in rows),
        "observed": observed, "missing": missing, "successes": counts["PASS"],
        "status_counts": counts,
        "success_rate": counts["PASS"] / expected if expected and not missing else None,
        "observed_success_rate": counts["PASS"] / observed if observed else None,
        "success_rate_bounds": {
            "lower": counts["PASS"] / expected if expected else None,
            "upper": (counts["PASS"] + missing) / expected if expected else None,
        },
        "costs": {metric: _metric_summary([row[metric] for row in rows], expected) for metric in METRICS},
    }


def _group_summaries(rows: list[dict], fields: tuple[str, ...]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in fields)].append(row)
    return [{**dict(zip(fields, key)), **_summarize_rows(members)}
            for key, members in sorted(groups.items())]


def _percentile(sorted_values: list[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    return sorted_values[lower] + (position - lower) * (sorted_values[upper] - sorted_values[lower])


def _stratified_mean(clusters: list[dict], field: str) -> float:
    strata = defaultdict(list)
    for cluster in clusters:
        strata[cluster["family"]].append(cluster[field])
    return statistics.fmean(statistics.fmean(values) for values in strata.values())


def _bootstrap(clusters: list[dict], settings: dict) -> dict:
    strata = defaultdict(list)
    for cluster in clusters:
        strata[cluster["family"]].append(cluster["estimate"])
    ordered = [strata[family] for family in sorted(strata)]
    rng = random.Random(settings["seed"])
    samples = []
    for _ in range(settings["bootstrap_samples"]):
        samples.append(statistics.fmean(
            statistics.fmean(values[rng.randrange(len(values))] for _ in values)
            for values in ordered
        ))
    samples.sort()
    # Two co-primary contrasts: each two-sided CI has alpha/2 noncoverage.
    tail = (1.0 - settings["confidence"]) / (2 * len(COMPARATORS))
    return {
        "lower": _percentile(samples, tail), "upper": _percentile(samples, 1.0 - tail),
        "confidence": 1.0 - (1.0 - settings["confidence"]) / len(COMPARATORS),
        "familywise_confidence_nominal": settings["confidence"],
        "method": "family_stratified_task_cluster_percentile_bootstrap",
        "adjustment": "Bonferroni_two_coprimary_contrasts", "samples": len(samples),
        "seed": settings["seed"], "quantile": "linear_interpolation",
    }


def _sign_flip(clusters: list[dict], settings: dict) -> dict:
    family_sizes = Counter(cluster["family"] for cluster in clusters)
    fractions = [Fraction(cluster["paired_difference_sum"],
                          cluster["scheduled_pairs"] * len(family_sizes) * family_sizes[cluster["family"]])
                 for cluster in clusters]
    denominator = math.lcm(*(value.denominator for value in fractions))
    # Binary outcomes have rational cluster means. Integer scaling makes ties
    # exact, avoiding accumulated rounding in long Gray-code enumerations.
    weighted = [value.numerator * (denominator // value.denominator) for value in fractions]
    observed = sum(weighted)
    count, extreme = len(weighted), 0
    if count <= 20:
        # Gray-code enumeration updates one sign at a time without a 2**n array.
        draws, previous_gray, statistic = 1 << count, 0, -observed
        extreme += statistic >= observed
        for index in range(1, draws):
            gray = index ^ (index >> 1)
            changed = gray ^ previous_gray
            bit = changed.bit_length() - 1
            statistic += (2 if gray & changed else -2) * weighted[bit]
            extreme += statistic >= observed
            previous_gray = gray
        p_value, method, mc_error = extreme / draws, "exact_task_sign_flip", None
    else:
        rng = random.Random(settings["seed"] + 1)
        draws = settings["sign_flip_samples"]
        for _ in range(draws):
            statistic = sum(value if rng.getrandbits(1) else -value for value in weighted)
            extreme += statistic >= observed
        # Including the observed assignment avoids a spurious zero Monte Carlo p.
        p_value = (extreme + 1) / (draws + 1)
        method = "monte_carlo_task_sign_flip_plus_one"
        mc_error = math.sqrt(p_value * (1.0 - p_value) / (draws + 1))
    return {
        "p_raw": p_value, "p_holm": None, "method": method, "alternative": "greater",
        "null_difference": 0.0, "task_clusters": count,
        "nonzero_task_differences": sum(cluster["estimate"] != 0 for cluster in clusters),
        "draws": draws, "extreme_draws": extreme, "monte_carlo_standard_error": mc_error,
        "seed": settings["seed"] + 1 if count > 20 else None,
        "validity": "conditional_on_independent_cluster_sign_exchangeability_or_null_symmetry",
    }


def _contrast(rows: list[dict], comparator: str, settings: dict) -> dict:
    blocks = defaultdict(dict)
    for row in rows:
        if row["condition"] == "fault" and row["arm"] in ("hierarchy_adaptive", comparator):
            blocks[row["block_id"]][row["arm"]] = row
    by_task = defaultdict(list)
    for block_id, arms in sorted(blocks.items()):
        adaptive, baseline = arms["hierarchy_adaptive"], arms[comparator]
        a, b = adaptive["outcome"], baseline["outcome"]
        by_task[adaptive["task_id"]].append({
            "family": adaptive["family"], "block_id": block_id,
            "observed": a is not None and b is not None,
            "difference": a - b if a is not None and b is not None else None,
            "lower": (a if a is not None else 0) - (b if b is not None else 1),
            "upper": (a if a is not None else 1) - (b if b is not None else 0),
        })
    clusters = []
    for task_id, pairs in sorted(by_task.items()):
        observed = [pair["difference"] for pair in pairs if pair["observed"]]
        clusters.append({
            "task_id": task_id, "family": pairs[0]["family"],
            "scheduled_pairs": len(pairs), "observed_pairs": len(observed),
            "estimate": statistics.fmean(observed) if len(observed) == len(pairs) else None,
            "paired_difference_sum": sum(observed) if len(observed) == len(pairs) else None,
            "observed_pair_mean": statistics.fmean(observed) if observed else None,
            "lower": statistics.fmean(pair["lower"] for pair in pairs),
            "upper": statistics.fmean(pair["upper"] for pair in pairs),
        })
    complete = bool(clusters) and all(cluster["estimate"] is not None for cluster in clusters)
    expected_pairs = sum(cluster["scheduled_pairs"] for cluster in clusters)
    observed_pairs = sum(cluster["observed_pairs"] for cluster in clusters)
    return {
        "id": "adaptive_vs_" + comparator.removeprefix("hierarchy_"),
        "adaptive_arm": "hierarchy_adaptive", "comparator_arm": comparator,
        "assigned_condition": "fault", "estimand": "equal_family_mean_of_task_mean_paired_success_differences",
        "task_clusters": len(clusters), "complete_task_clusters": sum(
            cluster["estimate"] is not None for cluster in clusters),
        "scheduled_pairs": expected_pairs, "observed_pairs": observed_pairs,
        "missing_pairs": expected_pairs - observed_pairs, "complete": complete,
        "estimate": _stratified_mean(clusters, "estimate") if complete else None,
        "sensitivity": {
            "lower": _stratified_mean(clusters, "lower") if clusters else None,
            "upper": _stratified_mean(clusters, "upper") if clusters else None,
            "method": "all_scheduled_binary_outcomes_worst_best_case",
        },
        "ci": _bootstrap(clusters, settings) if complete else None,
        "test": _sign_flip(clusters, settings) if complete else None,
        "clusters": clusters,
    }


def _holm(contrasts: list[dict]) -> None:
    # Missing tests are retained in the family as p=1 for adjustment. They are
    # never synthesized into an inferential result or used to permit PASS.
    ordered = sorted(contrasts, key=lambda item: item["test"]["p_raw"] if item["test"] else 1.0)
    previous = 0.0
    for index, contrast in enumerate(ordered):
        raw = contrast["test"]["p_raw"] if contrast["test"] else 1.0
        previous = max(previous, min(1.0, (len(contrasts) - index) * raw))
        if contrast["test"] is not None:
            contrast["test"]["p_holm"] = previous


def _design_blockers(manifest: dict, rows: list[dict]) -> list[str]:
    blockers = []
    if manifest["backend"] != "openai":
        blockers.append("simulated_backend_not_empirical_model_evidence")
    if manifest["profile"] != "study":
        blockers.append("pilot_is_exploratory")
    if any(row["split"] != "heldout" for row in rows):
        blockers.append("not_all_tasks_heldout")
    families = {row["family"] for row in rows}
    if families != set(FAMILIES):
        blockers.append("study_requires_three_predeclared_families")
    tasks = {family: {row["task_id"] for row in rows if row["family"] == family} for family in families}
    if any(len(tasks.get(family, set())) != 4 for family in FAMILIES):
        blockers.append("study_requires_four_instances_per_family")
    if len(rows) != 216:
        blockers.append("study_requires_216_scheduled_trials")
    repeat_sets = defaultdict(set)
    for row in rows:
        repeat_sets[(row["task_id"], row["condition"])].add(row["repeat"])
    if any(len(repeat_sets.get((task_id, condition), set())) != 3
           for task_id in {row["task_id"] for row in rows} for condition in CONDITIONS):
        blockers.append("study_requires_three_repeats_in_both_conditions")
    if len({tuple(sorted(repeats)) for repeats in repeat_sets.values()}) != 1:
        blockers.append("repeat_labels_differ_between_task_conditions")
    return blockers


def _recovery(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        if row["condition"] == "fault":
            groups[row["arm"]].append(row)
    output = []
    for arm, members in sorted(groups.items()):
        delivered = [row for row in members if row["fault_delivered"] is True]
        recovered = sum(row["recovered"] is True for row in delivered)
        observed = sum(row["recovered"] is not None for row in delivered)
        missing = len(delivered) - observed
        output.append({
            "arm": arm, "assigned": len(members), "delivered": len(delivered),
            "not_delivered": sum(row["fault_delivered"] is False for row in members),
            "delivery_unknown": sum(row["fault_delivered"] is None for row in members),
            "recovered": recovered, "recovery_observed": observed, "recovery_missing": missing,
            "observed_recovery_rate": recovered / observed if observed else None,
            "recovery_rate_bounds": {
                "lower": recovered / len(delivered) if delivered else None,
                "upper": (recovered + missing) / len(delivered) if delivered else None,
            },
        })
    return output


def analyze(manifest: dict, results: list[dict]) -> dict:
    """Return a JSON-serializable analysis; malformed joins raise AnalysisError.

    ``decision`` is the prespecified exploratory benchmark minimum-effect
    decision, separate from the engineering feasibility decision. Invalid or
    incomplete records, pilots, and simulations cannot receive efficacy PASS
    or FAIL. A PASS
    is conditional on the stated inferential assumptions, not a proof of
    broad superiority or a power assessment.
    """
    trials, settings = _validate_manifest(manifest)
    rows, issues = _join_results(trials, results, manifest)
    overall = _summarize_rows(rows)
    contrasts = [_contrast(rows, comparator, settings) for comparator in COMPARATORS]
    _holm(contrasts)
    blockers = _design_blockers(manifest, rows)
    if overall["missing"]:
        blockers.append("missing_outcomes")
    if issues:
        blockers.append("record_validity_issues")
    eligible = not blockers
    alpha = 1.0 - settings["confidence"]
    minimum = settings["minimum_effect"]
    decision, reason = "UNCERTAIN", "confirmatory_requirements_not_satisfied"
    if eligible:
        if all(item["ci"]["lower"] > minimum and item["test"]["p_holm"] <= alpha for item in contrasts):
            decision, reason = "PASS", "both_adjusted_intervals_and_holm_tests_exceed_declared_criteria"
        elif any(item["ci"]["upper"] < minimum for item in contrasts):
            decision, reason = "FAIL", "at_least_one_adjusted_interval_below_practical_effect_margin"
        else:
            reason = "evidence_does_not_resolve_the_practical_effect_claim"
    invariant_failures = [row["trial_id"] for row in rows if row["invariant_ok"] is False]
    invariant_unknown = [row["trial_id"] for row in rows if row["invariant_ok"] is None]
    feasibility = "FAIL" if invariant_failures else (
        "UNCERTAIN" if invariant_unknown or overall["missing"] or issues else "PASS")
    families = sorted({row["family"] for row in rows})
    family_counts = {family: len({row["task_id"] for row in rows if row["family"] == family})
                     for family in families}
    simulated = manifest["backend"] != "openai"
    caveats = [
        "The manifest defines assignment; fault delivery and recovery never select the primary analysis set (intention to treat).",
        "PASS is full trial acceptance and FAIL is zero; UNCERTAIN and NOT_RUN are missing, not assumed failures. No incomplete contrast receives a complete-case confirmatory CI or p-value.",
        "Repeated calls, repeats, and individual gates are not independent task samples. Repeats are averaged within each task and the bootstrap resamples tasks within family.",
        "Percentile bootstrap coverage is approximate. The planned study has only 12 task clusters (4 per family); intervals may be unstable or degenerate and do not establish adequate power.",
        "Sign-flip p-values are one-sided tests of zero improvement, conditional on independent cluster sign exchangeability or symmetry under the null. Paired execution alone does not prove these assumptions; the bootstrap CI separately assesses the practical margin.",
        "The target weights families equally and tasks equally within family. Generalization is limited to the represented task families, task-generating process, model, budgets, and fault intervention.",
        "Recovery rates condition on delivered faults, a post-assignment event; they are descriptive and cannot replace the assigned-fault comparison.",
        "Logical calls/tokens include a reused planning artifact for each assigned hierarchical trial. Actual provider usage, when recorded separately, must not be inferred by summing logical charges.",
        "elapsed_seconds sums logical response durations including reused planning; wall_seconds, when supplied, measures trial wall time. Neither establishes a controlled hardware benchmark.",
        "Local records and declared backend/model are not an anti-tamper attestation. The caller must validate the frozen manifest and source fingerprints separately.",
        "The decision is a prespecified exploratory benchmark decision, not general proof of method superiority or a guarantee of power or population coverage.",
    ]
    if simulated:
        caveats.insert(0, "Oracle/scripted outputs are simulated software-validation results, not empirical model success or evidence of method efficacy.")
    if manifest["profile"] == "pilot":
        caveats.insert(0, "The pilot is exploratory development validation and cannot confirm a heldout research claim.")
    return {
        "schema_version": "hiergoal.study.analysis.v1", "protocol_id": manifest["protocol_id"],
        "backend": manifest["backend"], "profile": manifest["profile"], "model": manifest["model"],
        "evidence_kind": "simulated_software_validation" if simulated else "declared_model_execution_records",
        "decision": decision, "decision_reason": reason,
        "confirmatory_eligible": eligible, "eligibility_blockers": blockers,
        "validation": {"status": "FAIL" if issues else "PASS", "issues": issues,
                       "scope": "record_consistency_checks_only_not_research_validation"},
        "feasibility": {"decision": feasibility, "invariant_failures": invariant_failures,
                        "invariant_unknown": invariant_unknown,
                        "requires": "complete_consistent_observations_and_all_invariant_flags_true",
                        "scope": "recorded_engineering_invariants_separate_from_efficacy"},
        "analysis": {**settings, "coprimary_contrasts": 2, "alpha": alpha,
                     "ci_confidence_per_contrast": 1.0 - alpha / 2,
                     "ci_adjustment": "Bonferroni", "p_adjustment": "Holm",
                     "missing_data": "binary_outcome_worst_best_case_bounds_no_complete_case_inference"},
        "design": {"scheduled_trials": len(rows), "task_clusters": sum(family_counts.values()),
                   "clusters_per_family": family_counts,
                   "blocks": len({row["block_id"] for row in rows}),
                   "primary_condition": "fault", "unit_of_inference": "task_id"},
        "overall": overall, "unrecorded_trial_ids": [row["trial_id"] for row in rows if not row["recorded"]],
        "missing_outcome_trial_ids": [row["trial_id"] for row in rows if row["outcome"] is None],
        "by_family_arm_condition": _group_summaries(rows, ("family", "arm", "condition")),
        "by_arm_condition": _group_summaries(rows, ("arm", "condition")),
        "primary_contrasts": contrasts, "recovery": _recovery(rows),
        "execution_context": manifest.get("execution_context"), "caveats": caveats,
    }


def _md(value: Any) -> str:
    return str(value).replace("\n", " ").replace("\r", " ").replace("|", "\\|").replace("`", "\\`").replace("<", "&lt;").replace(">", "&gt;")


def _fmt(value: float | None, *, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _interval(value: dict | None) -> str:
    if not value or value["lower"] is None:
        return "—"
    return f"[{_fmt(value['lower'])}, {_fmt(value['upper'])}]"


def _metric_cell(metric: dict, denominator: int) -> str:
    if metric["median"] is None:
        return f"— (0/{denominator})"
    return (f"{metric['median']:.3g} [{metric['min']:.3g}, {metric['max']:.3g}] "
            f"({metric['n_measured']}/{denominator})")


def render_markdown(summary: dict) -> str:
    """Render an analysis without raw model text or per-call trace contents."""
    overall, design, settings = summary["overall"], summary["design"], summary["analysis"]
    counts = overall["status_counts"]
    lines = [
        "# HierGoal paired study analysis", "",
        f"**Prespecified exploratory benchmark decision: {summary['decision']}**  ",
        f"Engineering invariant feasibility: **{summary['feasibility']['decision']}**.  ",
        f"Reason: `{_md(summary['decision_reason'])}`.", "",
        f"Protocol: `{_md(summary['protocol_id'])}`  ",
        f"Declared backend/model: `{_md(summary['backend'])}` / `{_md(summary['model'])}`; profile: `{_md(summary['profile'])}`.", "",
    ]
    if summary["evidence_kind"] == "simulated_software_validation":
        lines.extend(["**Software-validation results only. These simulated outcomes do not measure empirical model success or establish method efficacy.**", ""])
    elif summary["profile"] == "pilot":
        lines.extend(["**Exploratory pilot. This is not a confirmatory heldout result.**", ""])
    lines.extend([
        "## Coverage and validity", "",
        f"The schedule contains {design['scheduled_trials']} trials in {design['blocks']} paired blocks and {design['task_clusters']} task clusters. "
        "Repeats and individual acceptance gates do not increase the number of task clusters.", "",
        "| Scheduled | Supplied records | PASS | FAIL | UNCERTAIN | NOT_RUN | Missing outcomes |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {overall['expected']} | {overall['recorded']} | {counts['PASS']} | {counts['FAIL']} | {counts['UNCERTAIN']} | {counts['NOT_RUN']} | {overall['missing']} |", "",
        f"Unrecorded scheduled trials: {overall['unrecorded']}; these are included as NOT_RUN. "
        "Supplied records can include explicit NOT_RUN placeholders and do not imply execution. "
        f"Record-consistency issues: {len(summary['validation']['issues'])}. "
        f"Benchmark decision eligible: {'yes' if summary['confirmatory_eligible'] else 'no'}.", "",
    ])
    if summary["eligibility_blockers"]:
        lines.extend(["Benchmark decision blockers:", ""] + [f"- `{_md(item)}`" for item in summary["eligibility_blockers"]] + [""])
    if summary["validation"]["issues"]:
        issue_counts = Counter(issue["code"] for issue in summary["validation"]["issues"])
        lines.extend(["Record-consistency issue counts:", ""] + [
            f"- `{_md(code)}`: {count}" for code, count in sorted(issue_counts.items())] + [""])
    lines.extend([
        "## Co-primary assigned-fault contrasts", "",
        "All trials assigned to the fault condition are included regardless of whether a fault was delivered or recovered. "
        "The effect is the adaptive success probability minus comparator success probability, averaged first within task and then equally across families. "
        "Differences and interval endpoints are probability differences (multiply by 100 for percentage points).", "",
        f"The practical margin is {settings['minimum_effect']:.3f}. "
        f"Each interval has nominal {100 * settings['ci_confidence_per_contrast']:.1f}% confidence using Bonferroni adjustment for two contrasts "
        f"(nominal familywise {100 * settings['confidence']:.1f}%). "
        "P-values test zero improvement, are one-sided, and are Holm adjusted. Their validity is conditional on the sign-flip assumptions.", "",
        "| Contrast | Task clusters | Observed/scheduled pairs | Difference | Adjusted CI | Raw p | Holm p | Missing-data worst/best bounds |",
        "| --- | ---: | ---: | ---: | --- | ---: | ---: | --- |",
    ])
    for item in summary["primary_contrasts"]:
        test = item["test"] or {}
        lines.append(f"| {_md(item['id'])} | {item['task_clusters']} | {item['observed_pairs']}/{item['scheduled_pairs']} | "
                     f"{_fmt(item['estimate'])} | {_interval(item['ci'])} | {_fmt(test.get('p_raw'), digits=6)} | "
                     f"{_fmt(test.get('p_holm'), digits=6)} | {_interval(item['sensitivity'])} |")
    lines.extend(["", "Missing-data bounds are identification bounds, not confidence intervals. "
                  "An incomplete contrast has no confirmatory point estimate, CI, or p-value. "
                  "An efficacy PASS requires complete valid heldout OpenAI study data, both adjusted CI lower endpoints strictly above the margin, "
                  "and both Holm p-values at or below the familywise significance level. An efficacy FAIL means at least one adjusted CI upper endpoint "
                  "is strictly below the margin in an otherwise eligible study; other cases are UNCERTAIN.", "",
                  "## Outcomes by family, arm, and condition", "",
                  "The observed rate excludes missing outcomes only in this explicitly labeled descriptive column. "
                  "The bounds retain every scheduled trial; no missing outcome is silently scored as failure.", "",
                  "| Family | Arm | Condition | Scheduled | PASS | FAIL | UNCERTAIN | NOT_RUN | Observed successes/observed trials | Scheduled rate bounds |",
                  "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"])
    for row in summary["by_family_arm_condition"]:
        status = row["status_counts"]
        lines.append(f"| {_md(row['family'])} | {_md(row['arm'])} | {_md(row['condition'])} | {row['expected']} | "
                     f"{status['PASS']} | {status['FAIL']} | {status['UNCERTAIN']} | {status['NOT_RUN']} | "
                     f"{row['successes']}/{row['observed']} | {_interval(row['success_rate_bounds'])} |")
    lines.extend(["", "## Recorded per-trial costs", "",
                  "Cells show median [minimum, maximum] and measured/scheduled trial count. Missing token or timing measurements remain missing. "
                  "Logical calls/tokens include cached shared planning charges per hierarchical trial and therefore do not equal provider billing. "
                  "Recorded costs include failed and uncertain trials.", "",
                  "| Arm | Condition | Calls | Input tokens | Output tokens | Total tokens | Logical response seconds | Trial wall seconds |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- |"])
    for row in summary["by_arm_condition"]:
        cells = [_metric_cell(row["costs"][field], row["expected"])
                 for field in ("calls", "input_tokens", "output_tokens", "total_tokens", "elapsed_seconds", "wall_seconds")]
        lines.append(f"| {_md(row['arm'])} | {_md(row['condition'])} | " + " | ".join(cells) + " |")
    if any(row["costs"]["actual_calls"]["n_measured"] for row in summary["by_arm_condition"]):
        lines.extend(["", "Separately recorded actual provider usage (cached plan usage is charged only where recorded):", "",
                      "| Arm | Condition | Actual calls | Actual input tokens | Actual output tokens |",
                      "| --- | --- | --- | --- | --- |"])
        for row in summary["by_arm_condition"]:
            cells = [_metric_cell(row["costs"][field], row["expected"])
                     for field in ("actual_calls", "actual_input_tokens", "actual_output_tokens")]
            lines.append(f"| {_md(row['arm'])} | {_md(row['condition'])} | " + " | ".join(cells) + " |")
    context = summary.get("execution_context")
    lines.extend(["", "Timing context: " + (
        "; ".join(f"{_md(key)}: {_md(value)}" for key, value in sorted(context.items()))
        if isinstance(context, dict) and context else
        "host hardware, clock, and batch metadata were not supplied to this analysis. Provider hardware is not inferred."
    ) + " Recorded durations are not a controlled hardware benchmark.", "",
                  "## Recovery diagnostics", "",
                  "Recovery is conditional on a delivered fault and is descriptive. Fault delivery is a post-assignment event, "
                  "so these rates cannot establish a causal treatment contrast. Fault-assigned trials without delivery still remain in both primary comparisons.", "",
                  "| Arm | Fault assigned | Delivered | Not delivered | Delivery unknown | Recovered/known recovery outcomes | Recovery bounds among delivered |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | --- |"])
    for row in summary["recovery"]:
        lines.append(f"| {_md(row['arm'])} | {row['assigned']} | {row['delivered']} | {row['not_delivered']} | "
                     f"{row['delivery_unknown']} | {row['recovered']}/{row['recovery_observed']} | {_interval(row['recovery_rate_bounds'])} |")
    lines.extend(["", "## Interpretation and limits", ""])
    lines.extend(f"- {_md(caveat)}" for caveat in summary["caveats"])
    lines.append("")
    return "\n".join(lines)
