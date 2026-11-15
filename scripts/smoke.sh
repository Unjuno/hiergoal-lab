#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/.."
PY=python3
command -v "$PY" >/dev/null || PY=python
"$PY" -m unittest discover -s tests -v
"$PY" -m hiergoal.controller --dry-run
echo
if command -v hermes >/dev/null; then
  echo "Hermes CLI found. Check: hermes doctor"
else
  echo "Hermes CLI not installed. Follow official Hermes installation guide."
fi
echo "Offline smoke checks complete. No model API calls."
