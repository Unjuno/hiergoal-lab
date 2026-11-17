#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Explicit, fail-closed entry point. The --run flag is required for inference.
set -euo pipefail
cd "$(dirname "$0")/.."

MODE="${1:---check}"
if [[ "$MODE" == "--run" ]]; then
  shift
elif [[ "$MODE" == "--check" ]]; then
  shift
else
  echo "Usage: bash scripts/experiment.sh [--check|--run] [extra controller options]" >&2
  echo "  --check : validate without inference (default)" >&2
  echo "  --run   : after validation, start one real Hermes task" >&2
  exit 2
fi
if [[ "$MODE" == "--check" && "$#" -gt 0 ]]; then
  echo "--check does not take controller options" >&2
  exit 2
fi

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Python 3.11+ is required." >&2
  exit 2
fi

echo "[1/3] Offline tests (no model calls)"
"$PY" -m unittest discover -s tests -v

echo "[2/3] Dry-run controller validation (no model calls)"
"$PY" -m hiergoal.controller --dry-run

echo "[3/3] Readiness check (may query model catalog; no inference prompts)"
if ! "$PY" -m hiergoal.preflight --check-catalog; then
  echo >&2
  echo "Local environment NOT READY. Install Hermes and OpenCode v2, then run:" >&2
  echo "  bash scripts/setup_opencode_free.sh" >&2
  echo "Retry bash scripts/experiment.sh --check" >&2
  exit 2
fi

if [[ "$MODE" != "--run" ]]; then
  echo
  echo "CHECKS PASS. To start the live experiment:"
  echo "  bash scripts/experiment.sh --run"
  echo "The live run requires a disposable VM/container or other isolated environment."
  exit 0
fi
echo
echo "Starting ONE LIVE Hermes task using the selected OpenCode Free ACP model."
echo "Free-model availability and zero charges are NOT guaranteed."
echo "No external process sandbox is provided; use an isolated environment."
exec "$PY" -m hiergoal.controller --ack-unsandboxed "$@"
