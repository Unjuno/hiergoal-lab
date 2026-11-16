# SPDX-License-Identifier: Apache-2.0
"""Read-only local readiness checks. Never invokes an inference prompt.

The optional catalog check may access OpenCode's model catalog service, but
it does not submit a prompt or access an OpenAI API key.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from hiergoal.controller import DEFAULT_MODEL, FREE_MODELS, PROFILE, ExperimentStopped, verify_free_profile


def _command(argv: list[str], seconds: int = 20) -> dict:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=seconds)
        return {"ok": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout[:20000],
                "error_hint": result.stderr[-700:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "exit_code": None, "stdout": "", "error_hint": str(exc)}


def readiness(model: str = DEFAULT_MODEL, check_catalog: bool = False,
              hermes: str = "hermes", opencode: str = "opencode") -> dict:
    conditions = {}
    versions = {}
    conditions["python_3_11_or_newer"] = sys.version_info >= (3, 11)
    conditions["model_in_allowlist"] = model in FREE_MODELS
    paths = {"hermes": shutil.which(hermes), "opencode": shutil.which(opencode)}
    conditions["hermes_cli_installed"] = bool(paths["hermes"])
    conditions["opencode_cli_installed"] = bool(paths["opencode"])
    profile_error = None
    try:
        verify_free_profile()
        conditions["free_only_profile_recognized"] = True
    except ExperimentStopped as exc:
        conditions["free_only_profile_recognized"] = False
        profile_error = str(exc)
    for name in ("hermes", "opencode"):
        if paths[name]:
            result = _command([paths[name], "--version"])
            conditions[name + "_version_responds"] = result["ok"]
            versions[name] = result["stdout"].strip()[:160] if result["ok"] else None
        else:
            conditions[name + "_version_responds"] = False
            versions[name] = None
    catalog_checked = False
    if check_catalog:
        catalog_checked = True
        if paths["opencode"]:
            listing = _command([paths["opencode"], "models", "opencode"], seconds=35)
            conditions["selected_model_in_current_catalog"] = listing["ok"] and any(
                row.strip() == model for row in listing["stdout"].splitlines()
            )
        else:
            conditions["selected_model_in_current_catalog"] = False
    ok = all(conditions.values())
    return {
        "status": ("READY_FOR_MANUAL_LIVE_TEST" if ok and catalog_checked
                   else "STATIC_CHECKS_PASS_CATALOG_NOT_CHECKED" if ok
                   else "NOT_READY"),
        "selected_model": model,
        "provider": "opencode-free-acp",
        "profile": PROFILE,
        "conditions": conditions,
        "cli_versions": versions,
        "profile_error": profile_error,
        "catalog_checked": catalog_checked,
        "warning": ("Read-only readiness does not verify inference login, plugin runtime, "
                    "actual zero-cost eligibility, model throughput, or tool calls. "
                    "Run in an isolated environment and respect any usage restriction."),
    }


def main() -> None:
    cli = argparse.ArgumentParser(description="Verify local Hermes/OpenCode prerequisites without inference")
    cli.add_argument("--model", choices=FREE_MODELS, default=DEFAULT_MODEL)
    cli.add_argument("--hermes", default="hermes")
    cli.add_argument("--opencode", default="opencode")
    cli.add_argument("--check-catalog", action="store_true",
                     help="Also query OpenCode's model catalog (network access, no inference)")
    cli.add_argument("--output", type=Path,
                     help="Write readiness result to a local JSON file")
    args = cli.parse_args()
    result = readiness(args.model, args.check_catalog, args.hermes, args.opencode)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["status"] != "NOT_READY" else 2)


if __name__ == "__main__":
    main()
