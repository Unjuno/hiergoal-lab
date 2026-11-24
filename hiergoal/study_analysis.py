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


SCHEMAS = ("hiergoal.study.v1", "hiergoal.study.v2")
ARMS = ("flat_retry", "hierarchy_fixed", "hierarchy_adaptive")
FAMILIES = ("code_repair", "data_transform", "scheduling")
CONDITIONS = ("normal", "fault")
DESCRIPTIVE_PROFILES = ("mechanism", "scale", "reliability")
SCALE_FACTOR_CELLS = (
    ("small", 3, "sparse"), ("medium", 3, "sparse"), ("large", 3, "sparse"),
    ("small", 4, "sparse"), ("small", 5, "sparse"),
    ("small", 3, "dense"), ("large", 5, "dense"),
)
STATUSES = ("PASS", "FAIL", "UNCERTAIN", "NOT_RUN")
COMPARATORS = ("hierarchy_fixed", "flat_retry")
ASSIGNMENT_FIELDS = (
    "block_id", "task_id", "family", "split", "instance", "condition", "arm", "repeat",
    "scale", "source_instance", "fault_kind", "planned_tree",
)
INTEGER_METRICS = (
    "calls", "input_tokens", "output_tokens", "patch_actions", "replans",
    "replan_attempts", "rejected_actions",
    "actual_calls", "actual_input_tokens", "actual_output_tokens",
)
METRICS = (
    "calls", "input_tokens", "output_tokens", "total_tokens", "elapsed_seconds", "wall_seconds",
    "patch_actions", "replans", "actual_calls", "actual_input_tokens",
    "actual_output_tokens", "actual_total_tokens", "replan_attempts", "rejected_actions",
)
EVIDENCE_BOOLEAN_FIELDS = (
    "trace_replayed", "root_preserved", "final_grade_called", "final_grade_passed",
)
EVIDENCE_INTEGER_FIELDS = {
    "tree": ("goal_count", "leaf_count", "max_depth_edges", "dependency_edges"),
    "trace": ("checkpoint_events", "leaf_state_transitions", "milestone_state_transitions",
              "accepted_replans_with_failure_evidence", "post_fault_target_replans", "failure_causes_recorded", "model_diagnoses_recorded"),
    "root_changes": ("explicit_edit_requests", "rejected_edit_requests", "actual_changes"),
    "replanning": ("attempted", "accepted", "rejected", "unnecessary", "parent_preserved_events",
                   "unrelated_goals_checked", "unrelated_goals_unchanged", "decision_events",
                   "needed_decisions", "deferred_progress_decisions"),
    "execution_locality": ("unrelated_artifact_fields_checked", "unrelated_artifact_fields_unchanged",
                           "violations", "nonvacuous_events"),
    "dependencies": ("invalidation_events", "invalidated_goals", "reverified_goals"),
}


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


def _validate_mechanism_evidence(value: Any, trial_id: str) -> None:
    """Check declared types; successful replay remains the caller's job."""
    if value is None:
        return
    if not isinstance(value, dict):
        raise AnalysisError(f"mechanism_evidence must be an object or null for {trial_id}")
    for name in EVIDENCE_BOOLEAN_FIELDS:
        if value.get(name) is not None and type(value[name]) is not bool:
            raise AnalysisError(f"mechanism_evidence.{name} must be boolean or null for {trial_id}")
    for group, names in EVIDENCE_INTEGER_FIELDS.items():
        nested = value.get(group)
        if nested is None:
            continue
        if not isinstance(nested, dict):
            raise AnalysisError(f"mechanism_evidence.{group} must be an object for {trial_id}")
        for name in names:
            if nested.get(name) is not None:
                _integer(nested[name], f"mechanism_evidence.{group}.{name} for {trial_id}")
    density = (value.get("tree") or {}).get("dependency_density")
    if density is not None and _number(density, f"dependency_density for {trial_id}") > 1:
        raise AnalysisError(f"dependency_density must be <= 1 for {trial_id}")
    fault = value.get("fault")
    if fault is not None:
        if not isinstance(fault, dict):
            raise AnalysisError(f"mechanism_evidence.fault must be an object for {trial_id}")
        for name in ("triggered", "delivered", "no_impact", "forced", "domain_delivered"):
            if fault.get(name) is not None and type(fault[name]) is not bool:
                raise AnalysisError(f"mechanism_evidence.fault.{name} must be boolean or null for {trial_id}")


def _finite_settings(value: Any) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("scale"), dict) or not isinstance(value.get("reliability"), dict):
        raise AnalysisError("finite_diagnostics must declare scale and reliability objects")
    output = {"scale": {}, "reliability": {}}
    for group, name in (("scale", "minimum_setting_success"), ("scale", "maximum_paired_drop"),
                        ("reliability", "minimum_task_condition_success")):
        number = _number(value[group].get(name), f"finite_diagnostics.{group}.{name}")
        if number > 1:
            raise AnalysisError(f"finite_diagnostics.{group}.{name} must be <= 1")
        output[group][name] = number
    for name in ("baseline", "stress"):
        setting = value["scale"].get(name)
        if not isinstance(setting, dict):
            raise AnalysisError(f"finite_diagnostics.scale.{name} must be an object")
        output["scale"][name] = {
            "size": _string(setting.get("size"), f"{name}.size"),
            "depth": _integer(setting.get("depth"), f"{name}.depth", minimum=1),
            "density": _string(setting.get("density"), f"{name}.density"),
        }
    if output["scale"]["baseline"] == output["scale"]["stress"]:
        raise AnalysisError("Finite scale baseline and stress settings must differ")
    output["reliability"]["required_repeats"] = _integer(value["reliability"].get("required_repeats"),
        "finite_diagnostics.reliability.required_repeats", minimum=2)
    return output


def _evidence_value(row: dict, *path: str) -> Any:
    value = row.get("mechanism_evidence")
    for name in path:
        if not isinstance(value, dict):
            return None
        value = value.get(name)
    return value


def _replayed(row: dict) -> bool:
    return row["audit"] == "PASS" and _evidence_value(row, "trace_replayed") is True


def _validate_manifest(manifest: dict) -> tuple[list[dict], dict]:
    if not isinstance(manifest, dict) or manifest.get("schema_version") not in SCHEMAS:
        raise AnalysisError(f"manifest schema_version must be one of {SCHEMAS}")
    if manifest.get("backend") not in ("openai", "oracle", "scripted"):
        raise AnalysisError("Unknown backend")
    if manifest.get("profile") not in ("pilot", "study", *DESCRIPTIVE_PROFILES):
        raise AnalysisError("Unknown profile")
    for name in ("protocol_id", "model"):
        _string(manifest.get(name), name)
    trials = manifest.get("trials")
    if not isinstance(trials, list) or not trials:
        raise AnalysisError("manifest.trials must be a nonempty list")
    seen_ids, cluster_identity, identity_cluster, task_covariates = set(), {}, {}, {}
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
        covariates = {name: trial.get(name) for name in ("scale", "source_instance", "fault_kind", "planned_tree")}
        if task_covariates.setdefault(trial["task_id"], covariates) != covariates:
            raise AnalysisError(f"Task cluster has inconsistent scale or fault covariates: {trial['task_id']}")
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
        "finite_diagnostics": _finite_settings(config.get("finite_diagnostics")),
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
        for field in ("success", "fault_triggered", "fault_delivered", "recovered", "invariant_ok", "protocol_ok", "simulated", "fault_assigned"):
            if record.get(field) is not None and type(record[field]) is not bool:
                raise AnalysisError(f"{field} must be boolean or null for {trial_id}")
        for field in INTEGER_METRICS:
            if record.get(field) is not None:
                _integer(record[field], f"{field} for {trial_id}")
        for field in ("elapsed_seconds", "wall_seconds"):
            if record.get(field) is not None:
                _number(record[field], f"{field} for {trial_id}")
        _validate_mechanism_evidence(record.get("mechanism_evidence"), trial_id)
        indexed[trial_id] = record
    rows = []
    for trial in trials:
        trial_id = trial["trial_id"]
        record = indexed.get(trial_id)
        row = dict(trial)
        row["recorded"] = record is not None
        row["status"] = record["status"] if record is not None else "NOT_RUN"
        row["outcome"] = {"PASS": 1, "FAIL": 0}.get(row["status"])
        for key in (*INTEGER_METRICS, "elapsed_seconds", "wall_seconds", "fault_triggered", "fault_delivered", "recovered", "invariant_ok", "protocol_ok", "audit", "mechanism_evidence"):
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
                if field in record and record[field] != trial.get(field):
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
            if row["condition"] == "normal" and row["fault_triggered"] is True:
                issue("fault_triggered_in_normal_condition")
            if row["fault_triggered"] is False and row["fault_delivered"] is True:
                issue("fault_delivered_without_trigger")
            if row["recovered"] is True and (row["fault_delivered"] is not True or row["status"] != "PASS"):
                issue("recovery_without_delivered_fault_and_success")
            if (row["fault_delivered"] is True and row["outcome"] is not None
                    and row["recovered"] is not bool(row["outcome"])):
                issue("recovery_status_mismatch")
            mechanism = row["mechanism_evidence"]
            if mechanism is not None:
                for field in ("trace_replayed", "root_preserved"):
                    if mechanism.get(field) is False:
                        issue("mechanism_" + field + "_false")
                called, passed = mechanism.get("final_grade_called"), mechanism.get("final_grade_passed")
                if ((called is False and passed is not None)
                        or (called is True and (row["outcome"] is None or type(passed) is not bool or passed is not bool(row["outcome"])))
                        or (row["status"] == "PASS" and called is False)):
                    issue("independent_grade_status_mismatch")
                for field in ("triggered", "delivered"):
                    known = _evidence_value(row, "fault", field)
                    if known is not None and row["fault_" + field] is not None and known is not row["fault_" + field]:
                        issue("mechanism_fault_accounting_conflict", field)
                for group, checked, unchanged in (
                    ("replanning", "unrelated_goals_checked", "unrelated_goals_unchanged"),
                    ("execution_locality", "unrelated_artifact_fields_checked", "unrelated_artifact_fields_unchanged"),
                ):
                    total, preserved = _evidence_value(row, group, checked), _evidence_value(row, group, unchanged)
                    if total is not None and preserved is not None and preserved > total:
                        issue("mechanism_preservation_count_exceeds_checked", group)
                attempts, accepted, rejected = (_evidence_value(row, "replanning", name)
                                                for name in ("attempted", "accepted", "rejected"))
                if all(value is not None for value in (attempts, accepted, rejected)) and accepted + rejected > attempts:
                    issue("mechanism_replan_outcomes_exceed_attempts")
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


def _contrast(rows: list[dict], comparator: str, settings: dict, *, inference: bool = True,
              condition: str = "fault") -> dict:
    blocks = defaultdict(dict)
    for row in rows:
        if row["condition"] == condition and row["arm"] in ("hierarchy_adaptive", comparator):
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
        "scope": "prespecified_study_contrast" if inference else "descriptive_paired_contrast",
        "adaptive_arm": "hierarchy_adaptive", "comparator_arm": comparator,
        "assigned_condition": condition, "estimand": "equal_family_mean_of_task_mean_paired_success_differences",
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
        "ci": _bootstrap(clusters, settings) if complete and inference else None,
        "test": _sign_flip(clusters, settings) if complete and inference else None,
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
        blockers.append(manifest["profile"] + "_is_descriptive_only" if manifest["profile"] in DESCRIPTIVE_PROFILES else "pilot_is_exploratory")
    if manifest["schema_version"] == "hiergoal.study.v2":
        if manifest.get("evidence_contract") != "all-nine-v2":
            blockers.append("missing_or_unknown_v2_evidence_contract")
        if any(not _replayed(row) or _evidence_value(row, "root_preserved") is not True for row in rows):
            blockers.append("missing_or_invalid_replay_and_root_evidence")
        if any(_evidence_value(row, "final_grade_called") not in (True, False)
               or (row["status"] == "PASS" and
                   (_evidence_value(row, "final_grade_called") is not True
                    or _evidence_value(row, "final_grade_passed") is not True)) for row in rows):
            blockers.append("missing_or_invalid_independent_grade_evidence")
    if manifest["profile"] in DESCRIPTIVE_PROFILES:
        # A separate descriptive profile never inherits or relaxes the frozen
        # 216-trial study's inferential eligibility rule.
        return blockers
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
            "triggered": sum(row["fault_triggered"] is True for row in members),
            "trigger_unknown": sum(row["fault_triggered"] is None for row in members),
            "untriggered": sum(row["fault_triggered"] is False for row in members),
            "triggered_no_impact": sum(row["fault_triggered"] is True and row["fault_delivered"] is False
                                       for row in members),
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


def _repeat_stability(rows: list[dict]) -> dict:
    """Describe within-task repetition without creating independent samples."""
    groups = defaultdict(list)
    for row in rows:
        groups[(row["family"], row["task_id"], row["arm"], row["condition"])].append(row)
    task_rows = []
    for (family, task_id, arm, condition), members in sorted(groups.items()):
        observed = [row["outcome"] for row in members if row["outcome"] is not None]
        complete = len(observed) == len(members)
        task_rows.append({
            "family": family, "task_id": task_id, "arm": arm, "condition": condition,
            "scheduled_repeats": len(members), "observed_repeats": len(observed),
            "repeat_labels": sorted(row["repeat"] for row in members),
            "complete": complete, "successes": sum(observed),
            "mixed_observed_outcomes": len(set(observed)) > 1,
            "all_repeats_passed": all(observed) if complete else None,
            "success_rate": statistics.fmean(observed) if complete else None,
            "success_rate_bounds": {
                "lower": sum(observed) / len(members),
                "upper": (sum(observed) + len(members) - len(observed)) / len(members),
            },
        })
    by_arm_condition = []
    for arm in ARMS:
        for condition in CONDITIONS:
            selected = [row for row in task_rows if row["arm"] == arm and row["condition"] == condition]
            if not selected:
                continue
            by_arm_condition.append({
                "arm": arm, "condition": condition, "task_clusters": len(selected),
                "complete_task_clusters": sum(row["complete"] for row in selected),
                "clusters_with_mixed_observed_outcomes": sum(row["mixed_observed_outcomes"] for row in selected),
                "clusters_with_mixed_complete_outcomes": sum(row["complete"] and row["mixed_observed_outcomes"] for row in selected),
                "clusters_all_repeats_passed": sum(row["all_repeats_passed"] is True for row in selected),
                "clusters_all_repeats_failed": sum(row["complete"] and row["successes"] == 0 for row in selected),
                "scheduled_repeats": _metric_summary([row["scheduled_repeats"] for row in selected], len(selected)),
                "within_task_success_rate": _metric_summary([row["success_rate"] for row in selected], len(selected)),
            })
    return {
        "scope": "descriptive_within_task_variability_not_a_power_or_reliability_guarantee",
        "sufficiency_status": "UNCERTAIN",
        "sufficiency_reason": "No population power, precision, or future-stability guarantee establishes that the repeat count is scientifically sufficient; a finite acceptance threshold is a separate claim.",
        "minimum_scheduled_repeats": min(row["scheduled_repeats"] for row in task_rows),
        "maximum_scheduled_repeats": max(row["scheduled_repeats"] for row in task_rows),
        "by_task_arm_condition": task_rows, "by_arm_condition": by_arm_condition,
    }


def _evidence_values(rows: list[dict], *path: str) -> list[Any]:
    return [_evidence_value(row, *path) for row in rows if _replayed(row)
            and _evidence_value(row, *path) is not None]


def _evidence_counter(rows: list[dict], *path: str) -> dict:
    values = _evidence_values(rows, *path)
    return {"known_total": sum(values), "n_measured": len(values), "n_missing": len(rows) - len(values)}


def _mechanism_summary(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[(row["arm"], row["condition"])].append(row)
    output = []
    for (arm, condition), members in sorted(groups.items()):
        counts = {group: {name: _evidence_counter(members, group, name) for name in names}
                  for group, names in EVIDENCE_INTEGER_FIELDS.items() if group != "tree"}
        tree = {name: _metric_summary(
            [_evidence_value(row, "tree", name) if _replayed(row) else None for row in members], len(members))
            for name in (*EVIDENCE_INTEGER_FIELDS["tree"], "dependency_density")}
        output.append({
            "arm": arm, "condition": condition, "expected_trials": len(members),
            "replayed_trials": sum(_replayed(row) for row in members),
            "hierarchy_applicability": "NOT_APPLICABLE" if arm == "flat_retry" else "APPLICABLE",
            "tree": tree, **counts,
        })
    return output


def _scale_summary(manifest: dict, rows: list[dict], settings: dict) -> dict:
    """Frozen scale covariates, with one cluster count per actual task ID."""
    tasks = {item["task_id"]: item for item in manifest.get("tasks", []) if isinstance(item, dict) and "task_id" in item}
    grouped, cells = defaultdict(list), defaultdict(list)
    for row in rows:
        scale = row.get("scale", tasks.get(row["task_id"], {}).get("scale"))
        if scale is None:
            continue
        if not isinstance(scale, dict):
            raise AnalysisError("scale covariates must be an object")
        size = _string(scale.get("size"), "scale.size")
        depth = _integer(scale.get("depth"), "scale.depth", minimum=1)
        density = _string(scale.get("density"), "scale.density")
        grouped[(size, depth, density, row["arm"], row["condition"])].append(row)
        cells[(size, depth, density)].append(row)
    table = []
    for (size, depth, density, arm, condition), members in sorted(grouped.items()):
        tree = {name: _metric_summary([
            _evidence_value(row, "tree", name) if _replayed(row) else None for row in members], len(members))
            for name in (*EVIDENCE_INTEGER_FIELDS["tree"], "dependency_density")}
        table.append({
            "size": size, "requested_depth_levels": depth, "density": density, "arm": arm,
            "condition": condition, "task_clusters": len({row["task_id"] for row in members}),
            "replayed_trials": sum(_replayed(row) for row in members), "tree": tree,
            **_summarize_rows(members),
        })
    paired = []
    for (size, depth, density), members in sorted(cells.items()):
        hierarchical_members = [row for row in members if row["arm"] != "flat_retry"]
        paired.append({
            "size": size, "requested_depth_levels": depth, "density": density,
            "task_clusters": len({row["task_id"] for row in members}),
            "hierarchical_trials": len(hierarchical_members),
            "tree": {name: _metric_summary([
                _evidence_value(row, "tree", name) if _replayed(row) else None for row in hierarchical_members],
                len(hierarchical_members)) for name in (*EVIDENCE_INTEGER_FIELDS["tree"], "dependency_density")},
            "contrasts": [_contrast(members, comparator, settings, inference=False, condition=condition)
                          for condition in CONDITIONS for comparator in COMPARATORS],
        })
    hierarchy = [row for row in rows if row["arm"] != "flat_retry"]
    return {
        "scope": "descriptive_scale_coverage_without_a_scaling_law_or_efficacy_decision",
        "profile": manifest["profile"], "task_clusters": len({row["task_id"] for row in rows}),
        "scheduled_settings": len(cells),
        "scheduled_levels": {
            "size": sorted({key[0] for key in cells}), "requested_depth_levels": sorted({key[1] for key in cells}),
            "density": sorted({key[2] for key in cells}),
        },
        "observed_tree_values": {name: sorted(set(_evidence_values(hierarchy, "tree", name)))
                                 for name in ("goal_count", "max_depth_edges", "dependency_density")},
        "by_setting_arm_condition": table, "paired_contrasts_by_setting": paired,
        "limitations": [
            "Requested depth counts levels including the root; measured max_depth_edges counts edges from root zero.",
            "Deeper scale fixtures add executable certification leaves. Depth is not varied at fixed leaf count or fixed work.",
            "The selected scale settings are not a full factorial design; marginal and interaction effects are not identified generally.",
            "Distinct scale settings generated from shared source instances need not be independent task draws. No scale CI or significance test is reported.",
        ],
    }


def _coverage_status(expected: int, measured: int, *, failures: int = 0, exercised: bool = True) -> str:
    if failures:
        return "FAIL"
    if expected == 0 or measured != expected or not exercised:
        return "UNCERTAIN"
    return "PASS"


def _finite_blockers(manifest: dict, rows: list[dict], issues: list[dict], profile: str, config: dict | None) -> list[str]:
    blockers = []
    if manifest["profile"] != profile:
        blockers.append("requires_" + profile + "_profile")
    if config is None:
        blockers.append("missing_frozen_finite_diagnostic_thresholds")
    if manifest["schema_version"] != "hiergoal.study.v2" or manifest.get("evidence_contract") != "all-nine-v2":
        blockers.append("requires_all_nine_v2_evidence_contract")
    if manifest["backend"] != "openai":
        blockers.append("simulated_backend_not_empirical_model_evidence")
    if any(row["outcome"] is None for row in rows):
        blockers.append("incomplete_profile_outcomes")
    if any(not _replayed(row) for row in rows):
        blockers.append("incomplete_profile_replay_evidence")
    if issues:
        blockers.append("record_validity_issues")
    if any(_evidence_value(row, "root_preserved") is None or row["protocol_ok"] is None for row in rows):
        blockers.append("missing_root_or_protocol_evidence")
    return blockers


def _finite_decision(blockers: list[str], criteria: dict) -> str:
    if blockers or any(value is None for value in criteria.values()):
        return "UNCERTAIN"
    return "PASS" if all(criteria.values()) else "FAIL"


def _scale_resilience(manifest: dict, rows: list[dict], issues: list[dict], settings: dict) -> dict:
    """Frozen finite-scale acceptance rule, without a population inference."""
    config = (settings.get("finite_diagnostics") or {}).get("scale")
    blockers = _finite_blockers(manifest, rows, issues, "scale", config)
    grouped = defaultdict(list)
    selected = [row for row in rows if row["arm"] == "hierarchy_adaptive" and row["condition"] == "fault"]
    for row in selected:
        scale = row.get("scale") or {}
        grouped[(scale.get("size"), scale.get("depth"), scale.get("density"))].append(row)
    expected = set(SCALE_FACTOR_CELLS)
    valid_shape = len(rows) == 252 and set(grouped) == expected
    for members in grouped.values():
        for family in FAMILIES:
            cell = [row for row in members if row["family"] == family]
            valid_shape = valid_shape and len(cell) == 2 and {row["repeat"] for row in cell} == {1, 2} and len({row["task_id"] for row in cell}) == 1
        valid_shape = valid_shape and len(members) == 6
    if not valid_shape:
        blockers.append("requires_seven_scale_cells_three_families_two_repeats")
    table = []
    for size, depth, density in SCALE_FACTOR_CELLS:
        members = grouped.get((size, depth, density), [])
        successes = sum(row["outcome"] == 1 for row in members)
        observed = sum(row["outcome"] is not None for row in members)
        complete = len(members) == 6 and observed == 6
        proportion = Fraction(successes, len(members)) if complete else None
        table.append({
            "size": size, "requested_depth_levels": depth, "density": density,
            "scheduled": len(members), "observed": observed, "successes": successes,
            "success_rate": float(proportion) if proportion is not None else None,
            "meets_minimum": (proportion >= Fraction(str(config["minimum_setting_success"]))
                              if proportion is not None and config is not None else None),
        })
    pair_groups = defaultdict(lambda: defaultdict(list))
    if config is not None:
        labels = {tuple(config[name][field] for field in ("size", "depth", "density")): name
                  for name in ("baseline", "stress")}
        for row in selected:
            scale = row.get("scale") or {}
            label = labels.get(tuple(scale.get(field) for field in ("size", "depth", "density")))
            if label is not None:
                if row.get("source_instance") is None:
                    blockers.append("missing_source_instance_for_scale_pairing")
                    continue
                key = (row["family"], row["split"], row["source_instance"], row["repeat"])
                pair_groups[key][label].append(row)
    differences = []
    for pair in pair_groups.values():
        if len(pair["baseline"]) != 1 or len(pair["stress"]) != 1:
            blockers.append("missing_or_duplicate_baseline_stress_pair")
            continue
        baseline, stress = pair["baseline"][0]["outcome"], pair["stress"][0]["outcome"]
        if baseline is not None and stress is not None:
            differences.append(baseline - stress)
    if len(pair_groups) != 6 or len(differences) != 6:
        blockers.append("incomplete_six_baseline_stress_pairs")
    drop = Fraction(sum(differences), 6) if len(differences) == 6 and len(pair_groups) == 6 else None
    locality_violations = 0
    successful_unassessed, failed_unassessed, missing_counters = 0, 0, 0
    for row in selected:
        values = [_evidence_value(row, *path) if _replayed(row) else None for path in (
            ("replanning", "accepted"), ("replanning", "parent_preserved_events"),
            ("replanning", "unrelated_goals_checked"), ("replanning", "unrelated_goals_unchanged"),
            ("execution_locality", "unrelated_artifact_fields_checked"),
            ("execution_locality", "unrelated_artifact_fields_unchanged"),
            ("execution_locality", "violations"), ("execution_locality", "nonvacuous_events"))]
        if any(value is None for value in values):
            missing_counters += 1
            continue
        accepted, parents, goals, kept_goals, artifacts, kept_artifacts, violations, events = values
        locality_violations += int(parents != accepted or goals != kept_goals or artifacts != kept_artifacts or violations > 0)
        assessed = artifacts > 0 and events > 0 and (accepted == 0 or goals > 0)
        successful_unassessed += int(row["outcome"] == 1 and not assessed)
        failed_unassessed += int(row["outcome"] == 0 and not assessed)
    if missing_counters:
        blockers.append("missing_scale_locality_counters")
    if successful_unassessed:
        blockers.append("successful_scale_recovery_without_nonvacuous_locality")
    unexercised_success = sum(row["outcome"] == 1 and
        (_evidence_value(row, "fault", "forced") is not True or _evidence_value(row, "fault", "domain_delivered") is not True
         or row["fault_delivered"] is not True) for row in selected)
    if unexercised_success:
        blockers.append("successful_scale_record_without_forced_domain_failure")
    root_protocol_violations = sum(_evidence_value(row, "root_preserved") is False or row["protocol_ok"] is False for row in rows)
    criteria = {
        "every_setting_meets_success_threshold": (all(item["meets_minimum"] for item in table)
                                                  if all(item["meets_minimum"] is not None for item in table) else None),
        "paired_drop_within_margin": drop <= Fraction(str(config["maximum_paired_drop"])) if drop is not None and config else None,
        "zero_root_protocol_violations": root_protocol_violations == 0,
        "zero_observed_locality_violations": locality_violations == 0 if not missing_counters else None,
    }
    blockers = sorted(set(blockers))
    return {
        "decision": _finite_decision(blockers, criteria), "eligible": not blockers, "eligibility_blockers": blockers,
        "scope": "prespecified_finite_adaptive_fault_scale_benchmark_not_a_population_scaling_law",
        "thresholds": config, "criteria": criteria, "by_setting": table,
        "paired_baseline_to_stress": {
            "scheduled_pairs": len(pair_groups), "observed_pairs": len(differences), "required_pairs": 6,
            "success_rate_drop": float(drop) if drop is not None else None,
            "direction": "baseline_success_minus_stress_success",
            "pairing": "family_split_source_instance_repeat_not_task_id",
        },
        "root_protocol_violation_trials": root_protocol_violations,
        "locality_violation_trials": locality_violations,
        "successful_recovery_paths_without_locality_comparisons": successful_unassessed,
        "failed_paths_without_locality_comparisons": failed_unassessed,
        "scientific_sufficiency_status": "UNCERTAIN",
        "limitations": [
            "Thresholds are frozen design choices, not estimates from these outcomes. With six assigned adaptive fault trials per setting, a 0.80 threshold requires at least five successes.",
            "The stress contrast jointly changes size, depth, and direct dependency burden; fault targets may also differ across paired settings. It is not an isolated causal scale effect.",
            "The six pairs reuse three source tasks across two repeats; no independent-Bernoulli or population reliability claim is made.",
            "A failed path without a repair remains a failure in the success denominator and supplies no positive artifact-locality evidence.",
        ],
    }


def _finite_repeatability(manifest: dict, rows: list[dict], issues: list[dict], settings: dict) -> dict:
    config = (settings.get("finite_diagnostics") or {}).get("reliability")
    blockers = _finite_blockers(manifest, rows, issues, "reliability", config)
    required = config["required_repeats"] if config is not None else None
    groups = defaultdict(list)
    for row in rows:
        if row["arm"] == "hierarchy_adaptive":
            groups[(row["family"], row["task_id"], row["condition"])].append(row)
    family_tasks = {family: {key[1] for key in groups if key[0] == family} for family in FAMILIES}
    valid_shape = (required is not None and len(rows) == 12 * 2 * 3 * required and len(groups) == 24
                   and all(len(tasks) == 4 for tasks in family_tasks.values()))
    table = []
    for (family, task_id, condition), members in sorted(groups.items()):
        valid_shape = valid_shape and len(members) == required and {row["repeat"] for row in members} == set(range(1, required + 1))
        observed = sum(row["outcome"] is not None for row in members)
        successes = sum(row["outcome"] == 1 for row in members)
        proportion = Fraction(successes, len(members)) if required is not None and len(members) == observed == required else None
        table.append({"family": family, "task_id": task_id, "condition": condition,
                      "scheduled": len(members), "observed": observed, "successes": successes,
                      "success_rate": float(proportion) if proportion is not None else None,
                      "meets_minimum": (proportion >= Fraction(str(config["minimum_task_condition_success"]))
                                        if proportion is not None and config else None)})
    if not valid_shape:
        blockers.append("requires_twelve_tasks_both_conditions_and_declared_repeat_count")
    violations = sum(_evidence_value(row, "root_preserved") is False or row["protocol_ok"] is False for row in rows)
    criteria = {
        "every_task_condition_meets_success_threshold": (all(item["meets_minimum"] for item in table)
            if len(table) == 24 and all(item["meets_minimum"] is not None for item in table) else None),
        "zero_root_protocol_violations": violations == 0,
    }
    blockers = sorted(set(blockers))
    return {
        "decision": _finite_decision(blockers, criteria), "eligible": not blockers, "eligibility_blockers": blockers,
        "scope": "prespecified_finite_adaptive_repeatability_benchmark_not_population_stability_or_power",
        "thresholds": config, "criteria": criteria, "by_task_condition": table,
        "task_clusters": len({key[1] for key in groups}), "adaptive_task_condition_cells": len(groups),
        "root_protocol_violation_trials": violations, "scientific_sufficiency_status": "UNCERTAIN",
        "limitations": [
            "The per-task threshold and repeat count are frozen design choices, not fitted to observed outcomes.",
            "Nine successes in ten scheduled repeats meet a finite descriptive criterion; they do not prove a 0.90 future success probability.",
            "All 24 task/condition cells must meet the criterion; missing outcomes are not replaced, discarded, or selectively rerun.",
            "No independence assumption, confidence interval, adequate-power claim, or general sample-sufficiency decision is introduced.",
        ],
    }


def _requirement_evidence(manifest: dict, rows: list[dict], issues: list[dict],
                          repeats: dict, scale: dict) -> dict:
    """Nine explicitly scoped evidence rules, never a replacement efficacy test.

    Positive mechanism claims require the replay receipt, not a self-reported
    success flag. Missing, unexercised, and vacuous comparisons stay uncertain.
    Even complete repetition has no automatic adequacy or stability guarantee.
    """
    hierarchy = [row for row in rows if row["arm"] != "flat_retry"]
    adaptive = [row for row in rows if row["arm"] == "hierarchy_adaptive"]
    replayed = [row for row in rows if _replayed(row)]
    empirical = manifest["backend"] == "openai" and not issues
    criteria = []

    def total(selected, group, name):
        return _evidence_counter(selected, group, name)["known_total"]

    def add(identifier, key, title, status, scope, evidence, limitations, *, empirical_required=False,
            sufficiency_unresolved=False, finite=None):
        if issues and status == "PASS":
            status = "UNCERTAIN"
        model_status = finite["decision"] if finite is not None else (status if empirical and status in ("PASS", "FAIL") else "UNCERTAIN")
        criteria.append({
            "id": identifier, "key": key, "title": title,
            "status": "UNCERTAIN" if sufficiency_unresolved else (model_status if empirical_required or finite is not None else status),
            "engineering_status": status, "empirical_status": model_status,
            "scope": scope, "evidence": evidence, "limitations": limitations,
        })

    forced = [row for row in adaptive if row["condition"] == "fault" and row.get("fault_kind") == "forced_subgoal"]
    forced_measured = [row for row in forced if _replayed(row)
                       and _evidence_value(row, "fault", "forced") is True
                       and _evidence_value(row, "fault", "delivered") is not None
                       and _evidence_value(row, "fault", "domain_delivered") is not None
                       and _evidence_value(row, "trace", "post_fault_target_replans") is not None and row["outcome"] is not None]
    domain_delivered = [row for row in forced_measured if row["fault_delivered"] is True
                        and _evidence_value(row, "fault", "domain_delivered") is True]
    delivered_families = {row["family"] for row in domain_delivered}
    modified_recovered = [row for row in domain_delivered if row["recovered"] is True
                          and _evidence_value(row, "trace", "post_fault_target_replans") > 0]
    recovered_families = {row["family"] for row in modified_recovered}
    exercised = set(FAMILIES).issubset(delivered_families)
    recovery_status = _coverage_status(len(forced), len(forced_measured), exercised=exercised)
    if recovery_status == "PASS" and not set(FAMILIES).issubset(recovered_families):
        recovery_status = "FAIL"
    add("R1", "forced_subgoal_recovery", "Forced failed subgoal and verified recovery", recovery_status,
        "Public-pass to forced domain-fail to an accepted revision of that failed target to independent final-pass, in at least one adaptive trace per family.",
        {"assigned_adaptive_forced_trials": len(forced), "measured_adaptive_forced_trials": len(forced_measured),
         "adaptive_forced_delivered": sum(row["fault_delivered"] is True for row in forced_measured),
         "adaptive_forced_recovered": sum(row["recovered"] is True for row in forced_measured),
         "adaptive_forced_domain_delivered": len(domain_delivered),
         "adaptive_forced_domain_recovered": sum(row["recovered"] is True for row in domain_delivered),
         "adaptive_forced_modified_domain_recovered": len(modified_recovered),
         "post_fault_target_replans": total(forced, "trace", "post_fault_target_replans"),
         "families_with_delivery": sorted(delivered_families), "families_with_recovery": sorted(recovered_families),
         "domain_failures_delivered": sum(_evidence_value(row, "fault", "domain_delivered") is True for row in replayed),
         "fault_accounting": _recovery(rows)},
        ["Forced certification invalidation and a domain failure are reported separately; one does not imply the other.",
         "Pre-fault success is checked with public gates only; hidden final grading is deliberately not queried before the fault or fed back for repair.",
         "Observed recovery demonstrates a finite trace; it does not establish comparative efficacy or uniform reliability."],
        empirical_required=True)

    trace_measured = [row for row in hierarchy if _replayed(row)
                      and (_evidence_value(row, "tree", "goal_count") or 0) > 0
                      and (_evidence_value(row, "tree", "max_depth_edges") or 0) >= 2
                      and (_evidence_value(row, "trace", "checkpoint_events") or 0) > 0]
    accepted = total(adaptive, "replanning", "accepted")
    evidenced_replans = total(adaptive, "trace", "accepted_replans_with_failure_evidence")
    trace_status = _coverage_status(len(hierarchy), len(trace_measured),
        failures=sum(row["audit"] == "FAIL" for row in hierarchy),
        exercised=accepted > 0 and evidenced_replans == accepted)
    add("R2", "traceable_hierarchy", "Hierarchy, state transitions, and before/after replans", trace_status,
        "Successfully replayed hierarchical checkpoints plus an exercised, failure-evidenced accepted replan.",
        {"scheduled_hierarchical_trials": len(hierarchy), "replayed_hierarchical_trials": len(trace_measured),
         "checkpoint_events": total(hierarchy, "trace", "checkpoint_events"),
         "leaf_state_transitions": total(hierarchy, "trace", "leaf_state_transitions"),
         "milestone_state_transitions": total(hierarchy, "trace", "milestone_state_transitions"),
         "accepted_replans": accepted, "accepted_replans_with_failure_evidence": evidenced_replans,
         "post_fault_target_replans": total(adaptive, "trace", "post_fault_target_replans"),
         "host_failure_causes_recorded": total(hierarchy, "trace", "failure_causes_recorded"),
         "model_diagnoses_recorded": total(hierarchy, "trace", "model_diagnoses_recorded")},
        ["Replay checks the recorded state and diagnosis provenance; it does not certify the semantic truth of model-written causal explanations.",
         "Hash chains detect checked inconsistencies, not wholesale forgery by a writer able to regenerate the entire record."])

    root_measured = [row for row in replayed if _evidence_value(row, "root_preserved") is not None]
    root_failures = sum(_evidence_value(row, "root_preserved") is False for row in root_measured)
    root_status = _coverage_status(len(rows), len(root_measured), failures=root_failures + total(rows, "root_changes", "actual_changes"))
    add("R3", "immutable_root", "Immutable root contract", root_status,
        "Every scheduled trace was replayed and the root contract stayed identical in root-bearing state and request snapshots.",
        {"scheduled_trials": len(rows), "root_checked_trials": len(root_measured), "root_preservation_failures": root_failures,
         "verification_issue_trials": len({issue["trial_id"] for issue in issues}),
         "explicit_edit_requests": total(rows, "root_changes", "explicit_edit_requests"),
         "rejected_edit_requests": total(rows, "root_changes", "rejected_edit_requests"),
         "actual_root_changes": total(rows, "root_changes", "actual_changes")},
        ["Zero explicit edit requests does not exercise rejection of a root edit; mutation rejection is a separate adversarial software test.",
         "Syntactic edit-request counts do not infer a model's intent."])

    complete = [row for row in replayed if row["outcome"] is not None]
    observed_families = {row["family"] for row in complete}
    diversity = _coverage_status(len(rows), len(complete), exercised=set(FAMILIES).issubset(observed_families))
    add("R4", "diverse_tasks", "Observed coverage across different task families", diversity,
        "Complete replayed outcomes across all three declared synthetic task families; failures remain in coverage.",
        {"scheduled_families": sorted({row["family"] for row in rows}), "observed_families": sorted(observed_families),
         "task_clusters": len({row["task_id"] for row in rows}), "observed_trials": len(complete),
         "clusters_per_family": {family: len({row["task_id"] for row in rows if row["family"] == family})
                                 for family in sorted({row["family"] for row in rows})}},
        ["Coverage includes unsuccessful trials and is not a success claim.",
         "Three selected synthetic families do not establish broad real-world task generalization."], empirical_required=True)

    local_rows = [row for row in adaptive if _replayed(row) and (_evidence_value(row, "replanning", "accepted") or 0) > 0]
    locality_measured, locality_failures = [], 0
    for row in local_rows:
        values = [_evidence_value(row, *path) for path in (
            ("replanning", "unrelated_goals_checked"), ("replanning", "unrelated_goals_unchanged"),
            ("execution_locality", "unrelated_artifact_fields_checked"),
            ("execution_locality", "unrelated_artifact_fields_unchanged"),
            ("execution_locality", "violations"), ("execution_locality", "nonvacuous_events"),
            ("replanning", "parent_preserved_events"))]
        if all(value is not None for value in values):
            goals, unchanged_goals, artifacts, unchanged_artifacts, violations, events, parents = values
            locality_failures += int(goals != unchanged_goals or artifacts != unchanged_artifacts or violations > 0
                                     or parents != _evidence_value(row, "replanning", "accepted"))
            if goals > 0 and artifacts > 0 and events > 0:
                locality_measured.append(row)
    locality = _coverage_status(len(local_rows), len(locality_measured), failures=locality_failures,
                               exercised=all(_replayed(row) for row in adaptive))
    add("R5", "locality", "Unrelated goals and artifact fields preserved", locality,
        "Nonempty comparisons in exercised adaptive replan trials; plan edits and subsequent artifact repairs are measured separately.",
        {"adaptive_trials_with_accepted_replans": len(local_rows), "nonvacuous_locality_trials": len(locality_measured),
         "trials_with_locality_violation": locality_failures,
         "unrelated_goals_checked": total(adaptive, "replanning", "unrelated_goals_checked"),
         "unrelated_goals_unchanged": total(adaptive, "replanning", "unrelated_goals_unchanged"),
         "unrelated_artifact_fields_checked": total(adaptive, "execution_locality", "unrelated_artifact_fields_checked"),
         "unrelated_artifact_fields_unchanged": total(adaptive, "execution_locality", "unrelated_artifact_fields_unchanged"),
         "artifact_locality_violations": total(adaptive, "execution_locality", "violations"),
         "nonvacuous_artifact_events": total(adaptive, "execution_locality", "nonvacuous_events"),
         "dependency_invalidation_events": total(adaptive, "dependencies", "invalidation_events"),
         "invalidated_goals": total(adaptive, "dependencies", "invalidated_goals"),
         "reverified_goals": total(adaptive, "dependencies", "reverified_goals")},
        ["Zero unrelated comparisons is UNCERTAIN, never a vacuous locality PASS.",
         "Locality is defined by the declared task dependencies and artifact ownership, not inferred semantic independence."])

    replan_measured = [row for row in adaptive if _replayed(row) and all(_evidence_value(row, "replanning", name) is not None
                      for name in ("attempted", "accepted", "rejected", "unnecessary"))]
    cap = manifest.get("limits", {}).get("max_replans")
    excessive = sum(_evidence_value(row, "replanning", "attempted") > cap for row in replan_measured) if type(cap) is int else 0
    unnecessary = total(adaptive, "replanning", "unnecessary")
    bounded = _coverage_status(len(adaptive), len(replan_measured), failures=excessive + unnecessary,
                              exercised=type(cap) is int and total(adaptive, "replanning", "attempted") > 0)
    add("R6", "necessary_bounded_replanning", "Failure-evidenced and bounded replanning", bounded,
        "A replan request must have current failed-leaf evidence and authorization; attempted requests stay within the declared cap.",
        {"scheduled_adaptive_trials": len(adaptive), "measured_adaptive_trials": len(replan_measured),
         "attempted_requests": total(adaptive, "replanning", "attempted"), "accepted": accepted,
         "rejected": total(adaptive, "replanning", "rejected"), "unnecessary_requests": unnecessary,
         "declared_request_cap": cap, "trials_exceeding_request_cap": excessive,
         "decision_events": total(adaptive, "replanning", "decision_events"),
         "needed_decisions": total(adaptive, "replanning", "needed_decisions"),
         "deferred_progress_decisions": total(adaptive, "replanning", "deferred_progress_decisions"),
         "normal_condition_attempts": total([row for row in adaptive if row["condition"] == "normal"], "replanning", "attempted")},
        ["Operational necessity means satisfying the declared failure/progress predicate; it does not prove each replan improves outcomes or is globally optimal.",
         "Attempts count issued replan requests, including failed or over-budget requests, and may exceed accepted plus rejected replies."])

    grading_measured = [row for row in replayed if _evidence_value(row, "final_grade_called") is not None]
    grading_failures = sum(issue["code"] == "independent_grade_status_mismatch" for issue in issues)
    grading = _coverage_status(len(rows), len(grading_measured), failures=grading_failures + sum(row["audit"] == "FAIL" for row in rows),
        exercised=any(_evidence_value(row, "final_grade_called") is True for row in grading_measured))
    add("R7", "independent_evaluation", "Independent final grading and replay", grading,
        "Audited final grades must match terminal claims; noncandidate budget failures need not call the hidden grader.",
        {"scheduled_trials": len(rows), "grade_disposition_known": len(grading_measured),
         "final_grader_called": sum(_evidence_value(row, "final_grade_called") is True for row in grading_measured),
         "final_grader_passed": sum(_evidence_value(row, "final_grade_passed") is True for row in grading_measured),
         "final_grader_failed": sum(_evidence_value(row, "final_grade_passed") is False for row in grading_measured),
         "no_final_grade": sum(_evidence_value(row, "final_grade_called") is False for row in grading_measured),
         "audit_failures": sum(row["audit"] == "FAIL" for row in rows), "grade_claim_conflicts": grading_failures},
        ["Replay and hidden grading establish agreement with the implemented evaluator, not absence of evaluator bugs.",
         "Self-reported success and changed tests cannot substitute for this evidence."])

    levels, actual = scale["scheduled_levels"], scale["observed_tree_values"]
    scale_measured = [row for row in hierarchy if _replayed(row) and all(_evidence_value(row, "tree", name) is not None
                     for name in ("goal_count", "max_depth_edges", "dependency_density")) and row["outcome"] is not None]
    varied = (len(levels["size"]) >= 3 and len(levels["requested_depth_levels"]) >= 3 and len(levels["density"]) >= 2
              and len(actual["goal_count"]) >= 3 and len(actual["max_depth_edges"]) >= 3
              and len(actual["dependency_density"]) >= 2)
    scale_status = _coverage_status(len(hierarchy), len(scale_measured), exercised=varied)
    scale_finite = scale["finite_resilience"]
    add("R8", "scale_coverage", "Scale coverage and finite resilience", scale_status,
        "Engineering covers the varied observed trees; the separate finite live-data rule tests frozen per-setting success, paired stress drop, and observed locality thresholds.",
        {"profile": manifest["profile"], "scheduled_settings": scale["scheduled_settings"], "scheduled_levels": levels,
         "observed_tree_values": actual, "task_clusters": scale["task_clusters"],
         "measured_hierarchical_trials": len(scale_measured), "scaling_law_status": "UNCERTAIN",
         "finite_decision": scale_finite["decision"], "finite_criteria": scale_finite["criteria"],
         "finite_blockers": scale_finite["eligibility_blockers"]},
        scale["limitations"] + scale_finite["limitations"], empirical_required=True, finite=scale_finite)

    repeated = _coverage_status(len(rows), len(complete), exercised=repeats["minimum_scheduled_repeats"] >= 3)
    repeat_finite = repeats["finite_repeatability"]
    add("R9", "repeat_stability", "Finite repeatability and scientific stability uncertainty", repeated,
        "Engineering covers repeated outcome reporting; the separate live reliability rule requires every adaptive task/condition cell to meet frozen success and integrity thresholds.",
        {"minimum_scheduled_repeats": repeats["minimum_scheduled_repeats"],
         "maximum_scheduled_repeats": repeats["maximum_scheduled_repeats"],
         "by_arm_condition": repeats["by_arm_condition"], "sufficiency_status": repeats["sufficiency_status"],
         "finite_decision": repeat_finite["decision"], "finite_criteria": repeat_finite["criteria"],
         "finite_blockers": repeat_finite["eligibility_blockers"]},
        [repeats["sufficiency_reason"], "Repeated calls of one task are dependent observations within the same task cluster.",
         "Deterministic oracle repetitions do not estimate model stochasticity or empirical stability."],
        empirical_required=True, finite=repeat_finite)
    return {
        "evidence_contract": manifest.get("evidence_contract"),
        "evidence_kind": "declared_model_execution_records" if manifest["backend"] == "openai" else "simulated_software_validation",
        "status_semantics": {
            "PASS": "The explicitly scoped finite-evidence rule was satisfied; not a general efficacy or reliability claim.",
            "FAIL": "An observed violation or failed scoped criterion was recorded; not automatically method inferiority.",
            "UNCERTAIN": "Missing, unexercised, vacuous, simulated-only empirical, or scientifically insufficient evidence.",
            "NOT_APPLICABLE": "The operation is outside the declared arm or condition; absence of evidence is not non-applicability.",
        },
        "criteria": criteria,
        "status_counts": dict(Counter(item["status"] for item in criteria)),
        "note": "These nine scoped evidence rules do not replace the frozen study's separate efficacy decision. Engineering PASS on simulated records is software validation only.",
    }


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
    descriptive = manifest["profile"] in DESCRIPTIVE_PROFILES
    contrasts = [_contrast(rows, comparator, settings, inference=not descriptive) for comparator in COMPARATORS]
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
    repeats = _repeat_stability(rows)
    scale = _scale_summary(manifest, rows, settings)
    scale["finite_resilience"] = _scale_resilience(manifest, rows, issues, settings)
    repeats["finite_repeatability"] = _finite_repeatability(manifest, rows, issues, settings)
    requirements = _requirement_evidence(manifest, rows, issues, repeats, scale)
    simulated = manifest["backend"] != "openai"
    caveats = [
        "The manifest defines assignment; fault delivery and recovery never select the primary analysis set (intention to treat).",
        "PASS is full trial acceptance and FAIL is zero; UNCERTAIN and NOT_RUN are missing, not assumed failures. No incomplete contrast receives a complete-case confirmatory CI or p-value.",
        "Repeated calls, repeats, and individual gates are not independent task samples. Repeats are averaged within each task and the bootstrap resamples tasks within family.",
        f"This schedule has {sum(family_counts.values())} task clusters ({', '.join(f'{name}: {count}' for name, count in family_counts.items())}). Percentile bootstrap coverage, when reported, is approximate; intervals may be unstable or degenerate and do not establish adequate power. The original study design remains 12 task clusters (4 per family).",
        "Sign-flip p-values are one-sided tests of zero improvement, conditional on independent cluster sign exchangeability or symmetry under the null. Paired execution alone does not prove these assumptions; the bootstrap CI separately assesses the practical margin.",
        "The target weights families equally and tasks equally within family. Generalization is limited to the represented task families, task-generating process, model, budgets, and fault intervention.",
        "Recovery rates condition on delivered faults, a post-assignment event; they are descriptive and cannot replace the assigned-fault comparison.",
        "Logical calls/tokens include a reused planning artifact for each assigned hierarchical trial. Actual provider usage, when recorded separately, must not be inferred by summing logical charges.",
        "elapsed_seconds sums logical response durations including reused planning; wall_seconds, when supplied, measures trial wall time. Neither establishes a controlled hardware benchmark.",
        "Local records and declared backend/model are not an anti-tamper attestation. The caller must validate the frozen manifest and source fingerprints separately.",
        "The decision is a prespecified exploratory benchmark decision, not general proof of method superiority or a guarantee of power or population coverage.",
        "Mechanism counters are included only from declared successful replay receipts. Missing or zero unrelated-comparison counts cannot establish locality. The analyzer itself does not replay trace files.",
        "A bounded, failure-evidenced replan policy is operationally testable; globally optimal or causally necessary replanning is not established by this policy check.",
        "Repeat tables describe all-pass, all-fail, and mixed observed outcomes. No unregistered power, precision, or stability threshold is introduced after observing results.",
    ]
    if simulated:
        caveats.insert(0, "Oracle/scripted outputs are simulated software-validation results, not empirical model success or evidence of method efficacy.")
    if manifest["profile"] == "pilot":
        caveats.insert(0, "The pilot is exploratory development validation and cannot confirm a heldout research claim.")
    if descriptive:
        caveats.insert(0, f"The {manifest['profile']} profile is descriptive only. It does not inherit or relax the frozen 216-trial study decision, and no inferential CI or p-value is assigned to its paired contrasts.")
    return {
        "schema_version": "hiergoal.study.analysis.v2" if manifest["schema_version"] == "hiergoal.study.v2" else "hiergoal.study.analysis.v1",
        "protocol_id": manifest["protocol_id"],
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
                   "primary_condition": None if descriptive else "fault", "unit_of_inference": "task_id",
                   "analysis_scope": "descriptive_only" if descriptive else "prespecified_study_rule"},
        "overall": overall, "unrecorded_trial_ids": [row["trial_id"] for row in rows if not row["recorded"]],
        "missing_outcome_trial_ids": [row["trial_id"] for row in rows if row["outcome"] is None],
        "by_family_arm_condition": _group_summaries(rows, ("family", "arm", "condition")),
        "by_family_arm_condition_repeat": _group_summaries(rows, ("family", "arm", "condition", "repeat")),
        "by_arm_condition": _group_summaries(rows, ("arm", "condition")),
        "primary_contrasts": [] if descriptive else contrasts,
        "descriptive_contrasts": ([_contrast(rows, comparator, settings, inference=False, condition=condition)
                                   for condition in CONDITIONS for comparator in COMPARATORS] if descriptive else []),
        "recovery": _recovery(rows), "repeat_stability": repeats,
        "mechanisms_by_arm_condition": _mechanism_summary(rows), "scale": scale,
        "requirement_evidence": requirements,
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


def _counter_cell(counter: dict, denominator: int) -> str:
    return (f"{counter['known_total']} ({counter['n_measured']}/{denominator})"
            if counter["n_measured"] else f"— (0/{denominator})")


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
    if summary["profile"] in DESCRIPTIVE_PROFILES:
        lines.extend([f"**Descriptive {_md(summary['profile'])} profile. It does not alter the original 216-trial study efficacy rule; no inferential CI or p-value is derived from this profile. Finite acceptance criteria, where declared, are reported separately.**", ""])
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
    requirements = summary["requirement_evidence"]
    lines.extend([
        "## Nine requirement evidence rules", "", requirements["note"], "",
        "PASS applies only to the scope in its row. Engineering PASS can describe simulated software validation. "
        "Model-execution coverage remains UNCERTAIN without valid declared model records; it is not the benchmark efficacy decision. "
        "Missing or zero unrelated comparisons are UNCERTAIN. NOT_APPLICABLE is reserved for an operation outside the declared arm or condition.", "",
        "| ID | Requirement | Scoped status | Engineering | Model-execution coverage | Scope |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for item in requirements["criteria"]:
        lines.append(f"| {item['id']} | {_md(item['title'])} | {item['status']} | {item['engineering_status']} | "
                     f"{item['empirical_status']} | {_md(item['scope'])} |")
    lines.extend(["", "R8 and R9 scoped decisions concern only frozen finite benchmark thresholds on complete valid live records. "
                  "General scaling-law, power, precision, and future-stability sufficiency remain UNCERTAIN even if a finite criterion passes. "
                  "Per-criterion limitations and numerical evidence are retained in summary.json.", ""])
    if summary["profile"] in DESCRIPTIVE_PROFILES:
        lines.extend([
            "## Descriptive paired contrasts", "",
            "Both normal and assigned-fault conditions are reported. The adaptive-minus-comparator difference is averaged within task and then equally across families. "
            "All assigned trials remain in their condition; the scale and reliability profiles do not create extra independent evidence by counting repetitions.", "",
            "| Condition | Contrast | Task clusters | Observed/scheduled pairs | Difference | Missing-data worst/best bounds |",
            "| --- | --- | ---: | ---: | ---: | --- |",
        ])
        for item in summary["descriptive_contrasts"]:
            lines.append(f"| {_md(item['assigned_condition'])} | {_md(item['id'])} | {item['task_clusters']} | "
                         f"{item['observed_pairs']}/{item['scheduled_pairs']} | {_fmt(item['estimate'])} | {_interval(item['sensitivity'])} |")
        lines.extend(["", "Missing-data bounds are identification bounds, not confidence intervals. Incomplete paired data have no complete-case point estimate. "
                      "No CI or p-value is introduced for these descriptive contrasts. Frozen finite benchmark criteria are reported separately.", ""])
    else:
        _render_primary_contrasts(summary, lines)
    lines.extend(["## Outcomes by family, arm, and condition", "",
                  "The observed rate excludes missing outcomes only in this explicitly labeled descriptive column. "
                  "The bounds retain every scheduled trial; no missing outcome is silently scored as failure.", "",
                  "| Family | Arm | Condition | Scheduled | PASS | FAIL | UNCERTAIN | NOT_RUN | Observed successes/observed trials | Scheduled rate bounds |",
                  "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"])
    for row in summary["by_family_arm_condition"]:
        status = row["status_counts"]
        lines.append(f"| {_md(row['family'])} | {_md(row['arm'])} | {_md(row['condition'])} | {row['expected']} | "
                     f"{status['PASS']} | {status['FAIL']} | {status['UNCERTAIN']} | {status['NOT_RUN']} | "
                     f"{row['successes']}/{row['observed']} | {_interval(row['success_rate_bounds'])} |")
    _render_mechanisms(summary, lines)
    _render_repeats(summary, lines)
    _render_finite_benchmarks(summary, lines)
    _render_scale(summary, lines)
    _render_costs_and_limits(summary, lines)
    return "\n".join(lines)


def _render_primary_contrasts(summary: dict, lines: list[str]) -> None:
    settings = summary["analysis"]
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
                  "is strictly below the margin in an otherwise eligible study; other cases are UNCERTAIN.", ""])


def _render_mechanisms(summary: dict, lines: list[str]) -> None:
    lines.extend(["", "## Replayed mechanism measurements", "",
                  "Tree cells show median [minimum, maximum] and measured/scheduled trials. Root depth is zero; goal count includes the root. "
                  "A flat arm has no hierarchy, so its hierarchy measurements are NOT_APPLICABLE.", "",
                  "| Arm | Condition | Replayed/scheduled | Goal count | Leaves | Maximum depth, edges | Dependency edges | Dependency density |",
                  "| --- | --- | ---: | --- | --- | --- | --- | --- |"])
    for row in summary["mechanisms_by_arm_condition"]:
        cells = (["NOT_APPLICABLE"] * 5 if row["hierarchy_applicability"] == "NOT_APPLICABLE" else
                 [_metric_cell(row["tree"][name], row["expected_trials"])
                  for name in ("goal_count", "leaf_count", "max_depth_edges", "dependency_edges", "dependency_density")])
        lines.append(f"| {_md(row['arm'])} | {_md(row['condition'])} | {row['replayed_trials']}/{row['expected_trials']} | " + " | ".join(cells) + " |")
    lines.extend(["", "Replan counters show known totals and measured/scheduled trials. Attempts count issued requests, including interrupted or over-budget requests. "
                  "A missing counter is not zero. Operational necessity tests the recorded failed-leaf and progress rule; it does not prove optimality.", "",
                  "| Arm | Condition | Attempted | Accepted | Rejected | Unnecessary | Decision events | Deferred after progress |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- |"])
    for row in summary["mechanisms_by_arm_condition"]:
        cells = [_counter_cell(row["replanning"][name], row["expected_trials"])
                 for name in ("attempted", "accepted", "rejected", "unnecessary", "decision_events", "deferred_progress_decisions")]
        lines.append(f"| {_md(row['arm'])} | {_md(row['condition'])} | " + " | ".join(cells) + " |")
    lines.extend(["", "Locality uses nonempty comparisons of unrelated goals and separately of unrelated artifact fields during repair. "
                  "Zero checked objects cannot establish locality. Dependency invalidations and fresh re-verifications are counts of evidence transitions.", "",
                  "| Arm | Condition | Unrelated goals checked | Goals unchanged | Artifact fields checked | Fields unchanged | Artifact violations | Invalidated goals | Reverified goals |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"])
    for row in summary["mechanisms_by_arm_condition"]:
        cells = [_counter_cell(row[group][name], row["expected_trials"]) for group, name in (
            ("replanning", "unrelated_goals_checked"), ("replanning", "unrelated_goals_unchanged"),
            ("execution_locality", "unrelated_artifact_fields_checked"),
            ("execution_locality", "unrelated_artifact_fields_unchanged"), ("execution_locality", "violations"),
            ("dependencies", "invalidated_goals"), ("dependencies", "reverified_goals"))]
        lines.append(f"| {_md(row['arm'])} | {_md(row['condition'])} | " + " | ".join(cells) + " |")
    criteria = {item["id"]: item["evidence"] for item in summary["requirement_evidence"]["criteria"]}
    trace, root, grades = criteria["R2"], criteria["R3"], criteria["R7"]
    lines.extend(["", f"Replayed hierarchical checkpoints: {trace['checkpoint_events']}; leaf state transitions: {trace['leaf_state_transitions']}; "
                  f"milestone state transitions: {trace['milestone_state_transitions']}; accepted replans with failure evidence: {trace['accepted_replans_with_failure_evidence']}. "
                  f"Recorded host fault causes: {trace['host_failure_causes_recorded']}; recorded model diagnoses: {trace['model_diagnoses_recorded']} (text provenance, not causal validation).", "",
                  f"Root checked in {root['root_checked_trials']}/{root['scheduled_trials']} trials; explicit edit requests: {root['explicit_edit_requests']}; "
                  f"rejected edit requests: {root['rejected_edit_requests']}; actual root changes: {root['actual_root_changes']}. "
                  f"Record-verification issue trials: {root['verification_issue_trials']} (not assumed actual root mutations). "
                  "A zero edit-attempt count leaves adversarial rejection unexercised in this run.", "",
                  f"Final-grade disposition known in {grades['grade_disposition_known']}/{grades['scheduled_trials']} trials: "
                  f"grader called {grades['final_grader_called']}, passed {grades['final_grader_passed']}, failed {grades['final_grader_failed']}, "
                  f"not reached {grades['no_final_grade']}. Audit failures: {grades['audit_failures']}; grade/terminal-claim conflicts: {grades['grade_claim_conflicts']}.", ""])


def _render_repeats(summary: dict, lines: list[str]) -> None:
    repeats = summary["repeat_stability"]
    lines.extend(["## Repeated outcomes within task", "",
                  f"Scheduled repeats per task/arm/condition range from {repeats['minimum_scheduled_repeats']} to {repeats['maximum_scheduled_repeats']}. "
                  "All-pass, mixed, and all-fail below partition only complete task records. Missing repeats remain explicit. "
                  "These are observed patterns, not an independent-trial reliability estimate or a claim that the sample is sufficient.", "",
                  "| Arm | Condition | Task clusters | Complete clusters | All repeats PASS | Mixed complete outcomes | All repeats FAIL | Incomplete clusters |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for row in repeats["by_arm_condition"]:
        lines.append(f"| {_md(row['arm'])} | {_md(row['condition'])} | {row['task_clusters']} | {row['complete_task_clusters']} | "
                     f"{row['clusters_all_repeats_passed']} | {row['clusters_with_mixed_complete_outcomes']} | "
                     f"{row['clusters_all_repeats_failed']} | {row['task_clusters'] - row['complete_task_clusters']} |")
    lines.extend(["", "Per-family/repeat cells show successful/observed trials, followed by the missing scheduled count. "
                  "The same task IDs recur across repeats; the table does not create independent task samples.", "",
                  "| Family | Repeat | Flat normal | Flat fault | Fixed normal | Fixed fault | Adaptive normal | Adaptive fault |",
                  "| --- | ---: | --- | --- | --- | --- | --- | --- |"])
    groups = defaultdict(dict)
    for row in summary["by_family_arm_condition_repeat"]:
        groups[(row["family"], row["repeat"])][(row["arm"], row["condition"])] = row
    for (family, repeat), members in sorted(groups.items()):
        cells = []
        for arm in ARMS:
            for condition in CONDITIONS:
                row = members.get((arm, condition))
                cells.append(f"{row['successes']}/{row['observed']}; missing {row['missing']}" if row is not None else "not scheduled")
        lines.append(f"| {_md(family)} | {repeat} | " + " | ".join(cells) + " |")
    lines.extend(["", f"Repeat sufficiency: **{repeats['sufficiency_status']}**. {repeats['sufficiency_reason']}", ""])


def _render_scale(summary: dict, lines: list[str]) -> None:
    scale = summary["scale"]
    if not scale["scheduled_settings"]:
        lines.extend(["## Scale coverage", "", "This schedule declares no scale settings. A successful small base task does not establish scale coverage (R8 remains UNCERTAIN).", ""])
        return
    lines.extend(["## Scale coverage and descriptive outcomes", "",
                  f"The schedule contains {scale['scheduled_settings']} scale settings and {scale['task_clusters']} distinct task IDs. "
                  "Parameter levels and observed tree metrics are separate. Requested depth counts levels including the root; measured depth counts edges from root zero. "
                  "Topology cells show median [minimum, maximum] and measured/scheduled hierarchical trials.", "",
                  "| Size | Requested depth, levels | Dependency setting | Task IDs | Goals | Leaves | Maximum depth, edges | Dependency edges | Dependency density |",
                  "| --- | ---: | --- | ---: | --- | --- | --- | --- | --- |"])
    for row in scale["paired_contrasts_by_setting"]:
        cells = [_metric_cell(row["tree"][name], row["hierarchical_trials"])
                 for name in ("goal_count", "leaf_count", "max_depth_edges", "dependency_edges", "dependency_density")]
        lines.append(f"| {_md(row['size'])} | {row['requested_depth_levels']} | {_md(row['density'])} | {row['task_clusters']} | " + " | ".join(cells) + " |")
    lines.extend(["", "Outcome cells show successes/observed trials plus missing scheduled trials. Cost cells show median [minimum, maximum] with measured/scheduled trials. "
                  "Both normal and fault conditions are retained. Paired descriptive contrasts within each setting are also available in summary.json.", "",
                  "| Size | Depth, levels | Dependency setting | Arm | Condition | Task IDs | Outcomes | Logical calls | Logical tokens | Trial wall seconds |",
                  "| --- | ---: | --- | --- | --- | ---: | --- | --- | --- | --- |"])
    for row in scale["by_setting_arm_condition"]:
        cells = [_metric_cell(row["costs"][name], row["expected"]) for name in ("calls", "total_tokens", "wall_seconds")]
        lines.append(f"| {_md(row['size'])} | {row['requested_depth_levels']} | {_md(row['density'])} | {_md(row['arm'])} | {_md(row['condition'])} | "
                     f"{row['task_clusters']} | {row['successes']}/{row['observed']}; missing {row['missing']} | " + " | ".join(cells) + " |")
    lines.extend([""] + [f"- {_md(item)}" for item in scale["limitations"]] + [""])


def _render_finite_benchmarks(summary: dict, lines: list[str]) -> None:
    if summary["profile"] == "scale":
        diagnostic = summary["scale"]["finite_resilience"]
        config = diagnostic["thresholds"]
        lines.extend(["## Finite scale-resilience benchmark", "",
                      f"**Scoped decision: {diagnostic['decision']}.** This is a finite descriptive acceptance rule, not a population scaling law or a replacement study efficacy decision.", ""])
        if config is not None:
            lines.extend([f"Frozen minimum success per adaptive fault setting: {config['minimum_setting_success']:.2f}; "
                          f"maximum paired baseline-to-stress success-rate drop: {config['maximum_paired_drop']:.2f}. "
                          f"Baseline: `{_md(config['baseline'])}`; joint stress: `{_md(config['stress'])}`. "
                          "Full scheduled outcomes and replay are required; simulations cannot pass this empirical rule.", ""])
        lines.extend(["| Size | Depth, levels | Dependency setting | Successes/observed | Scheduled | Meets frozen minimum |",
                      "| --- | ---: | --- | ---: | ---: | --- |"])
        for row in diagnostic["by_setting"]:
            status = "UNCERTAIN" if row["meets_minimum"] is None else "PASS" if row["meets_minimum"] else "FAIL"
            lines.append(f"| {_md(row['size'])} | {row['requested_depth_levels']} | {_md(row['density'])} | "
                         f"{row['successes']}/{row['observed']} | {row['scheduled']} | {status} |")
        paired = diagnostic["paired_baseline_to_stress"]
        lines.extend(["", f"Observed paired success-rate drop: {_fmt(paired['success_rate_drop'])}; "
                      f"complete pairs: {paired['observed_pairs']}/{paired['required_pairs']}. Pair by family, split, source instance, and repeat; task IDs differ across settings. "
                      f"Root/protocol violation trials: {diagnostic['root_protocol_violation_trials']}; locality violation trials: {diagnostic['locality_violation_trials']}. "
                      f"Successful recovery paths without nonempty locality comparisons: {diagnostic['successful_recovery_paths_without_locality_comparisons']}; "
                      f"failed paths without such comparisons: {diagnostic['failed_paths_without_locality_comparisons']}.", ""])
    elif summary["profile"] == "reliability":
        diagnostic = summary["repeat_stability"]["finite_repeatability"]
        config = diagnostic["thresholds"]
        lines.extend(["## Finite repeatability benchmark", "",
                      f"**Scoped decision: {diagnostic['decision']}.** This evaluates the recorded repetitions only; future stability and scientific sample sufficiency remain UNCERTAIN.", ""])
        if config is not None:
            lines.extend([f"Every adaptive task/condition cell must meet success proportion {config['minimum_task_condition_success']:.2f} "
                          f"across exactly {config['required_repeats']} scheduled repeats. All 12 task IDs and both conditions are retained; "
                          "complete valid live outcomes and zero root/protocol violations are required.", ""])
        lines.extend(["| Family | Task | Condition | Successes/observed | Scheduled | Meets frozen minimum |",
                      "| --- | --- | --- | ---: | ---: | --- |"])
        for row in diagnostic["by_task_condition"]:
            status = "UNCERTAIN" if row["meets_minimum"] is None else "PASS" if row["meets_minimum"] else "FAIL"
            lines.append(f"| {_md(row['family'])} | {_md(row['task_id'])} | {_md(row['condition'])} | "
                         f"{row['successes']}/{row['observed']} | {row['scheduled']} | {status} |")
        lines.extend(["", f"Root/protocol violation trials: {diagnostic['root_protocol_violation_trials']}.", ""])
    else:
        return
    if diagnostic["eligibility_blockers"]:
        lines.extend(["Finite benchmark blockers:", ""] + [f"- `{_md(item)}`" for item in diagnostic["eligibility_blockers"]] + [""])
    lines.extend([f"- {_md(item)}" for item in diagnostic["limitations"]] + [""])


def _render_costs_and_limits(summary: dict, lines: list[str]) -> None:
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
                  "| Arm | Fault assigned | Triggered | Delivered | Triggered, no impact | Untriggered | Trigger unknown | Delivery unknown | Recovered/known recovery outcomes | Recovery bounds among delivered |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"])
    for row in summary["recovery"]:
        lines.append(f"| {_md(row['arm'])} | {row['assigned']} | {row['triggered']} | {row['delivered']} | {row['triggered_no_impact']} | "
                     f"{row['untriggered']} | {row['trigger_unknown']} | {row['delivery_unknown']} | "
                     f"{row['recovered']}/{row['recovery_observed']} | {_interval(row['recovery_rate_bounds'])} |")
    lines.extend(["", "## Interpretation and limits", ""])
    lines.extend(f"- {_md(caveat)}" for caveat in summary["caveats"])
    lines.append("")
