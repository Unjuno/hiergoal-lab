# SPDX-License-Identifier: Apache-2.0
"""Replay the three complementary profiles and report all nine requirements.

This command never instantiates a responder or calls an API. Profiles are fixed
in advance; it cannot select a favorable run or pool unlike interventions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hiergoal.study import collect
from hiergoal.study_protocol import canonical, save, validate_manifest

REQUIRED_PROFILES = ("mechanism", "scale", "reliability")
REQUIREMENTS = {
    "R1": ("mechanism", "reliability"),
    "R2": REQUIRED_PROFILES,
    "R3": REQUIRED_PROFILES,
    "R4": REQUIRED_PROFILES,
    "R5": REQUIRED_PROFILES,
    "R6": REQUIRED_PROFILES,
    "R7": REQUIRED_PROFILES,
    "R8": ("scale",),
    "R9": ("reliability",),
}


def combine_status(values):
    # A measured violation is not erased by a missing complementary profile.
    if "FAIL" in values:
        return "FAIL"
    return "PASS" if values and all(value == "PASS" for value in values) else "UNCERTAIN"


def review(directories: dict[str, Path]) -> dict:
    if not set(directories).issubset(REQUIRED_PROFILES):
        raise ValueError("Unknown suite profile")
    summaries, manifests, errors, observed_models = {}, {}, [], {}
    for profile in REQUIRED_PROFILES:
        if profile not in directories:
            errors.append({"profile": profile, "code": "MISSING_PROFILE"})
            continue
        directory = Path(directories[profile])
        try:
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            validate_manifest(manifest)
            if manifest["profile"] != profile:
                raise ValueError("Profile assignment mismatch")
            # Never trust an existing summary or declared replay receipt alone.
            summary = collect(directory)
            results = json.loads((directory / "results.json").read_text(encoding="utf-8"))
            models = []
            for result in results:
                if result.get("audit") != "PASS":
                    continue
                observed = result.get("observed_models", [])
                if not isinstance(observed, list) or any(not isinstance(model, str) or not model for model in observed):
                    raise ValueError("Invalid observed model identifiers")
                models.extend(observed)
            # Publish the complete profile atomically, including its provenance.
            manifests[profile], summaries[profile] = manifest, summary
            observed_models[profile] = sorted(set(models))
            if summary["validation"]["status"] != "PASS":
                errors.append({"profile": profile, "code": "RESULT_VALIDATION_FAILED"})
            if summary["overall"]["missing"]:
                errors.append({"profile": profile, "code": "INCOMPLETE_EXECUTION"})
        except (OSError, ValueError, KeyError, TypeError, RecursionError):
            # Avoid copying arbitrary exception/provider/model text to public output.
            errors.append({"profile": profile, "code": "SOURCE_OR_REPLAY_INVALID"})
    signatures = {
        canonical({key: manifest.get(key) for key in
                   ("schema_version", "protocol_revision", "source_file_sha256",
                    "backend", "model", "reasoning_effort", "endpoint", "analysis")})
        for manifest in manifests.values()
    }
    if len(signatures) > 1:
        errors.append({"profile": None, "code": "INCOMPATIBLE_PROFILE_CONTEXTS"})
    live = bool(manifests) and all(value["backend"] == "openai" for value in manifests.values())
    if live and len({model for values in observed_models.values() for model in values}) > 1:
        errors.append({"profile": None, "code": "OBSERVED_MODEL_CHANGED_BETWEEN_PROFILES"})
    criteria = []
    for identifier, profiles in REQUIREMENTS.items():
        sources = []
        for profile in profiles:
            criterion = next((item for item in summaries.get(profile, {}).get(
                "requirement_evidence", {}).get("criteria", []) if item["id"] == identifier), None)
            sources.append({"profile": profile, "criterion": criterion,
                            "protocol_id": manifests.get(profile, {}).get("protocol_id")})
        engineering = combine_status([
            item["criterion"]["engineering_status"] if item["criterion"] else "UNCERTAIN"
            for item in sources])
        empirical = combine_status([
            item["criterion"]["empirical_status"] if item["criterion"] else "UNCERTAIN"
            for item in sources]) if live else "UNCERTAIN"
        # A positive suite conclusion requires all three valid, complete inputs.
        if errors:
            engineering = "UNCERTAIN" if engineering == "PASS" else engineering
            empirical = "UNCERTAIN" if empirical == "PASS" else empirical
        criteria.append({"id": identifier, "profiles": list(profiles),
                         "engineering_status": engineering, "empirical_status": empirical,
                         "sources": sources})
    return {
        "schema_version": "hiergoal.requirement_suite.v1",
        "scope": "Fixed finite criteria across mechanism, scale and reliability; no pooled efficacy claim.",
        "evidence_kind": "declared_model_execution_records" if live else "software_validation_or_missing",
        "engineering_decision": combine_status([item["engineering_status"] for item in criteria]),
        "empirical_decision": combine_status([item["empirical_status"] for item in criteria]),
        "input_issues": errors,
        "profiles": {profile: {"protocol_id": manifests[profile]["protocol_id"],
                                "protocol_revision": manifests[profile]["protocol_revision"],
                                "backend": manifests[profile]["backend"],
                                "observed_models": observed_models[profile],
                                "scheduled_trials": len(manifests[profile]["trials"]),
                                "outcomes": summaries[profile]["overall"]["status_counts"],
                                "source_file_sha256": manifests[profile]["source_file_sha256"]}
                     for profile in summaries},
        "criteria": criteria,
        "limitations": [
            "Every supplied profile is replayed from traces; missing and invalid evidence never becomes success.",
            "Oracle/scripted results test software only and cannot yield empirical PASS.",
            "A FAIL records a scoped violation even if another profile is missing; inspect input issues separately.",
            "This report neither proves causal necessity of replanning nor treats repeated calls as independent tasks.",
            "Archive and retain the original run directories for future replay; structured summaries alone are insufficient.",
        ],
    }


def render_markdown(report):
    lines = ["# Nine-requirement replay review", "",
             "Engineering: **" + report["engineering_decision"] + "**; empirical: **" + report["empirical_decision"] + "**.",
             "", report["scope"], "",
             "| Requirement | Fixed profiles | Engineering | Empirical |",
             "| --- | --- | --- | --- |"]
    for item in report["criteria"]:
        lines.append("| " + " | ".join((item["id"], ", ".join(item["profiles"]),
                                         item["engineering_status"], item["empirical_status"])) + " |")
    lines += ["", "## Input issues", ""]
    lines += ["- " + (item["profile"] or "suite") + ": " + item["code"] for item in report["input_issues"]] or ["None."]
    lines += ["", "## Interpretation", ""]
    lines += ["- " + item for item in report["limitations"]]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for profile in REQUIRED_PROFILES:
        parser.add_argument("--" + profile, type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = review({profile: getattr(args, profile) for profile in REQUIRED_PROFILES if getattr(args, profile)})
    args.output.mkdir(parents=True, exist_ok=True)
    save(args.output / "requirements.json", report)
    (args.output / "requirements.md").write_text(render_markdown(report), encoding="utf-8")
    print("NINE-REQUIREMENT REVIEW: engineering=" + report["engineering_decision"] +
          "; empirical=" + report["empirical_decision"] + "; NO API REQUESTS")
    return 0 if report["engineering_decision"] == "PASS" and not report["input_issues"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
