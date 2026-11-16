#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# One-time local setup: dedicated free-only Hermes profile + OpenCode ACP plugin.
# This script never invokes the model or handles API keys.
set -euo pipefail

cd "$(dirname "$0")/.."
PROFILE=hiergoal-free
MODEL=opencode/glm-5.3-flash-free
PLUGIN=cryptobredda/hermes-opencode-free-acp
# Reviewed source revision: v0.4.0 (reproducible, no moving default branch).
PLUGIN_REF=0ef669a84c024661c03d34768c118275e93aa713

if [[ -n "$(printenv HERMES_HOME 2>/dev/null || true)" ]]; then
  echo "HERMES_HOME is overridden; unset it for the dedicated named-profile setup." >&2
  exit 2
fi
if ! command -v hermes >/dev/null 2>&1; then
  echo "Hermes CLI not found. Install the official Hermes CLI first." >&2
  exit 2
fi
if ! command -v opencode >/dev/null 2>&1; then
  echo "OpenCode CLI not found. Install the official OpenCode CLI first." >&2
  exit 2
fi

echo "Checking that the current OpenCode installation offers $MODEL..."
if ! opencode models opencode | grep -Fx "$MODEL" >/dev/null; then
  echo "The selected free model is unavailable in the current OpenCode catalog." >&2
  echo "Try 'opencode auth login' and 'opencode models opencode'; do not substitute a paid model." >&2
  exit 2
fi

PROFILE_DIR="$HOME/.hermes/profiles/$PROFILE"
CONFIG="$PROFILE_DIR/config.yaml"
if [[ -e "$PROFILE_DIR" ]]; then
  if [[ ! -f "$CONFIG" ]] || ! grep -Fq "# HierGoal isolated free-only configuration" "$CONFIG"; then
    echo "Profile $PROFILE already exists and is not owned by HierGoal Lab." >&2
    echo "No configuration changes were made; inspect or rename it manually." >&2
    exit 2
  fi
  echo "Existing HierGoal profile found; preserving its settings."
else
  echo "Creating a Hermes profile without copying provider keys or paid fallbacks..."
  hermes profile create "$PROFILE" --no-skills --no-alias --no-credentials
  mkdir -p "$PROFILE_DIR"
  cat > "$CONFIG" <<'YAML'
# HierGoal isolated free-only configuration
# Never clone another profile; avoid paid fallback and auxiliary routes.
model:
  provider: opencode-free-acp
  default: opencode/glm-5.3-flash-free
fallback_providers: []
delegation:
  fallback_providers: []
YAML
fi

echo "Installing the public ACP model-provider plugin into $PROFILE..."
hermes -p "$PROFILE" plugins install "$PLUGIN" --ref "$PLUGIN_REF" --enable
echo "Verifying installed provider..."
hermes -p "$PROFILE" plugins list
echo
echo "Setup completed. No inference request was sent."
echo "Run the independent offline checks, then the explicit real experiment:"
echo "  python3 -m unittest discover -s tests -v"
echo "  python3 -m hiergoal.controller --dry-run"
echo "  python3 -m hiergoal.controller --ack-unsandboxed"
echo "Free status is temporary; availability and vendor terms can change."
