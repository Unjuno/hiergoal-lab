#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# A live inference request requires explicit --run.
set -euo pipefail
cd "$(dirname "$0")/.."

if (( $# == 0 )); then
  MODE="--check"
else
  MODE="$1"
  shift
fi
if [[ "$MODE" != "--check" && "$MODE" != "--run" ]]; then
  echo "Usage: bash scripts/experiment.sh [--check|--run] [--backend free|luna] [controller options]" >&2
  exit 2
fi
BACKEND=free
last=""
for arg in "$@"; do
  if [[ "$last" == "--backend" ]]; then
    BACKEND="$arg"
  fi
  last="$arg"
done
if [[ "$BACKEND" != "free" && "$BACKEND" != "luna" ]]; then
  echo "Unsupported backend: $BACKEND" >&2
  exit 2
fi
if [[ "$MODE" == "--check" && $# -gt 0 ]]; then
  if [[ $# != 2 || "$1" != "--backend" ]]; then
    echo "For --check only --backend free|luna is supported." >&2
    exit 2
  fi
fi

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Python 3.11+ is required." >&2
  exit 2
fi

echo "[1/3] Offline unit tests (no inference)"
"$PY" -m unittest discover -s tests -v
echo "[2/3] Controller dry-run"
"$PY" -m hiergoal.controller --backend "$BACKEND" --dry-run
echo "[3/3] Local preflight (no inference)"
if [[ "$BACKEND" == "luna" ]]; then
  if ! "$PY" -m hiergoal.preflight_luna; then
    echo "Set OPENAI_API_KEY in your local environment or ~/.hermes/.env." >&2
    exit 2
  fi
else
  if ! "$PY" -m hiergoal.preflight --check-catalog; then
    echo "Set up OpenCode and the isolated profile: bash scripts/setup_opencode_free.sh" >&2
    exit 2
  fi
fi
if [[ "$MODE" == "--check" ]]; then
  echo "Readiness passed (live inference and billing remain unverified)."
  if [[ "$BACKEND" == "luna" ]]; then
    echo "Run: bash scripts/experiment.sh --run --backend luna --approve-paid-api --pilot-budget-usd 3"
  else
    echo "Run: bash scripts/experiment.sh --run --backend free"
  fi
  exit 0
fi
echo "Hermes uses local file and terminal tools. Run in a disposable environment."
if [[ "$BACKEND" == "luna" ]]; then
  echo "Direct OpenAI API: paid usage. The USD guard is only an estimate."
fi
exec "$PY" -m hiergoal.controller --ack-unsandboxed "$@"
