#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Install a reviewed source revision and its locked core runtime. No inference.
set -euo pipefail
lab_root="$(cd "$(dirname "$0")/.." && pwd)"
hermes_install_root="${1:?Usage: install_ci_hermes.sh ABSOLUTE_NEW_DIRECTORY}"
if [[ "$hermes_install_root" != /* || -e "$hermes_install_root" ]]; then
  echo "The Hermes install directory must be an absolute, new directory." >&2
  exit 2
fi
read -r hermes_source hermes_revision hermes_python < <(
  python3 - "$lab_root/ci/hermes.json" <<'PY'
import json, sys
pin = json.load(open(sys.argv[1], encoding="utf-8"))
print(pin["repository"], pin["commit"], pin["python"])
PY
)
git init -q "$hermes_install_root"
git -C "$hermes_install_root" remote add origin "$hermes_source"
git -C "$hermes_install_root" fetch --depth 1 origin "$hermes_revision"
git -C "$hermes_install_root" checkout --detach -q FETCH_HEAD
test "$(git -C "$hermes_install_root" rev-parse HEAD)" = "$hermes_revision"
uv python install "$hermes_python"
uv sync --project "$hermes_install_root" --locked --python "$hermes_python" --no-dev
"$hermes_install_root/.venv/bin/hermes" --version
if [[ -n "${GITHUB_ENV:-}" && -n "${GITHUB_PATH:-}" ]]; then
  printf 'HIERGOAL_REAL_HERMES=%s/.venv/bin/hermes\n' "$hermes_install_root" >> "$GITHUB_ENV"
  printf '%s/.venv/bin\n' "$hermes_install_root" >> "$GITHUB_PATH"
fi
