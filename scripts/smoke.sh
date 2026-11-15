#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/.."
PY=python3
command -v "$PY" >/dev/null || PY=python
"$PY" -m unittest discover -s tests -v
"$PY" scripts/run_hermes.py --dry-run
echo
if command -v hermes >/dev/null; then
  echo "Hermes CLI found. Run 'hermes doctor' to check your local installation."
else
  echo "Hermes not yet installed. See the official installation guide in README.md."
fi
echo "Offline smoke checks complete. No model API call made."
