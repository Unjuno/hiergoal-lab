# HierGoal Lab — Hermes × OpenCode Free Research

[![Offline CI](https://github.com/Unjuno/hiergoal-lab/actions/workflows/offline.yml/badge.svg)](https://github.com/Unjuno/hiergoal-lab/actions/workflows/offline.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

An experimental Python controller running real **Hermes Agent** instances through a three-level goal hierarchy: fixed long-term objective → model-proposed mid-term milestones → short-term executable tasks. The controller validates plans and dependencies, invokes Hermes, independently verifies results and replans failed leaves.

**Default inference:** official OpenCode v2 CLI via ACP, using a curated free model instead of the OpenAI paid API. Hermes executes file/terminal tools; OpenCode supplies inference.

**Status:** offline tests and synthetic-Hermes integration pass in GitHub Actions. **No actual Hermes + OpenCode model-inference experiment has been run in this environment.** No causal performance comparison or superiority claim is made.

## Requirements

- macOS / Linux / Windows WSL2, Python 3.11+, Git
- Hermes Agent >=0.22.2
- Official **OpenCode v2 CLI** (separate runtime), installed with one of:
  - npm install -g @opencode/cli
  - brew install anomalyco/tap/opencode-v2
  - Other systems: https://opencode.ai/docs/
- An OpenCode Console account / login if required for the free models. An OpenAI API key is **not needed**.

## 1. Clone and run zero-cost tests

~~~bash
git clone https://github.com/Unjuno/hiergoal-lab.git
cd hiergoal-lab
python3 -m unittest discover -s tests -v
python3 -m hiergoal.controller --dry-run
~~~

These commands make no inference requests.

## 2. Configure the isolated free-only provider

Inspect your binaries and current model availability:

~~~bash
hermes --version
opencode --version
opencode models opencode
~~~

If the free model is not listed, complete official OpenCode login with opencode auth login, then retry the catalog. **Do not substitute a paid model.**

Read the setup script before running it. Then:

~~~bash
bash scripts/setup_opencode_free.sh
~~~

The setup creates a **dedicated Hermes profile** named hiergoal-free with the --no-credentials and --no-skills flags, avoiding the default copying of API keys, model and skills. It writes an explicit free-only provider with an empty paid fallback chain. **Caveat:** Hermes may still read the root auth store through its fallback behavior; this profile is not an OS-level security or complete credential-isolation boundary. Use a separate OS account or container with a clean HOME for stronger isolation. It configures opencode-free-acp with an empty fallback list and installs the separately reviewed community provider from https://github.com/cryptobredda/hermes-opencode-free-acp pinned to immutable commit:

0ef669a84c024661c03d34768c118275e93aa713 (release v0.4.0)

The community plugin runs the actual OpenCode CLI over ACP and hands tool calls to Hermes. It checks each selected model against a curated free-model list. However, a third-party plugin **cannot guarantee model eligibility, quotas, zero charges, or compliance with OpenCode terms**; review its source and current privacy policy.

**Do not call free models directly via an OpenCode-compatible HTTP endpoint from Hermes.** OpenCode documents that free-tier chat models are available only from within OpenCode and direct third-party API calls receive HTTP 403. Respect any access refusal; do not attempt to disguise a client or evade quotas.

## 3. Run one actual free-model experiment

Use a disposable VM/container or a low-privilege user. Hermes terminal/file tools are not an OS sandbox; copied workspaces alone do not isolate the host.

~~~bash
python3 -m hiergoal.controller --ack-unsandboxed \
  --model opencode/glm-5.3-flash-free \
  --max-calls 12 --max-replans 2
~~~

The provider and isolated profile are hardcoded by the controller. A paid model such as gpt-6-luna is rejected by the command-line allowlist, and the profile guard rejects inherited paid fallback chains. The ACP plugin checks model availability before inference. Other free model choices appear under python3 -m hiergoal.controller --help; verify the current vendor catalog before selecting them.

The legacy paid OpenAI/Luna runner under scripts/run_hermes.py is disabled unless explicitly invoked with --allow-paid-openai. It is not needed for this study.

## 4. Inspect experimental evidence

All run data is local and Git-ignored:

~~~text
runs/hiergoal-<UTC>-<id>/
  workspace/                actual agent modifications
  state.json                goal hierarchy, progress, superseded leaves
  records.json              model, call counts, stop reason, final outcome
  initial_grading.json      evidence the task was initially unsolved
  NN-plan.prompt.txt        actual model-planning prompt
  NN-*.stream.jsonl         raw Hermes tool/output events
  NN-*.stderr.txt           diagnostics
  gate-*.json               immutable independent acceptance checks
  final-visible.json        visible tests run outside writable workspace
~~~

A **PASS** requires all six independent acceptance tests, all three visible tests, no edits to the original visible tests, and a successfully completed controller. One PASS is only a case observation, not an estimate of overall agent success rate.

The community ACP transport reports unknown token usage. This project therefore records estimated_visible_usd = null (not $0) and does **not** calculate an imaginary price from zero token counters. During the free promotion the OpenCode model catalog lists the selected model at zero input/output price; access restrictions, rates and billing terms may change. Confirm any actual billing in the OpenCode Console.

An interrupted experiment can be resumed only after verifying the previous Hermes/OpenCode session has stopped. The controller blocks cross-provider/model/profile resumes.

## 5. Research mechanism

- Owner-fixed root acceptance contract
- AI-generated 2–4 mid-term milestones and 3–8 actionable short-term goals
- Strict checks for missing gates, duplicate coverage, invalid dependencies and cycles
- Dependency-aware execution, independent per-leaf acceptance gates
- Bounded replacement of failed leaves, without changing parent or root
- Saved event traces, plan state and deterministic final evaluation

This is **external hierarchical orchestration**, not an alteration to Hermes native /goal and not a JEPA world model.

## References

- [Japanese research protocol](docs/protocol_ja.md)
- [Hermes issue #156054](https://github.com/NousResearch/hermes-agent/issues/156054)
- [H-JEPA (Zhang et al., 2026)](https://arxiv.org/abs/2610.06805)
- [OpenCode model catalog and privacy notes](https://opencode.ai/docs/console/models)
- [OpenCode supported harness policy](https://opencode.ai/docs/console/harnesses)
- [OpenCode Free ACP community source](https://github.com/cryptobredda/hermes-opencode-free-acp)

Apache-2.0 independent research project. The authors of Hermes Agent, OpenCode and the ACP provider do not endorse this research. Review and redact raw tool logs before sharing.

## 6. Generate a publication-ready evidence summary (no inference)

After a run, create a **whitelisted report** that excludes prompts, raw tool output and stderr:

~~~bash
python3 -m hiergoal.report runs/hiergoal-<your-run-id>
~~~

The resulting `report-public.json` verifies the saved PASS claim against final test evidence and a terminal Hermes stream event, records SHA-256 fingerprints and flags missing evidence as `UNCERTAIN`. It is not a signed artifact or proof that the model was free. Inspect this summary and redact any sensitive local metadata before publishing. Do not upload the raw `runs/` directory.
