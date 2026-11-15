# HierGoal Lab — Hermes Agent Hierarchical Goal Experiment

[![Offline CI](https://github.com/Unjuno/hiergoal-lab/actions/workflows/offline.yml/badge.svg)](https://github.com/Unjuno/hiergoal-lab/actions/workflows/offline.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

A self-contained experimental controller that runs a **real Hermes Agent** through a three-level goal hierarchy: user-owned long-term goal → model-proposed mid-term milestones → model-proposed short-term executable tasks.

The controller (Python standard library only) validates the plan, schedules leaves by dependency, invokes Hermes for each leaf, uses an **independent deterministic evaluator** for acceptance, and requests **bounded local replanning** when a leaf fails. This is an actual external execution controller, not just a prompt asking the agent to plan.

**State:** offline tests and fake-Hermes end-to-end integration pass in GitHub Actions. Real Hermes + an OpenAI API key are required for a paid experiment on your machine; **no real paid experiment has been executed here**.

**Study type:** one observational case; no comparison group, no statistical performance claim, and no direct implementation of H-JEPA.

## First experiment: local execution

Requirements: macOS/Linux/WSL2, Git, Python 3.11+, a separately installed Hermes Agent CLI, and OpenAI API credentials supported by Hermes.

1. Clone and run the **zero-cost checks**:

~~~bash
git clone https://github.com/Unjuno/hiergoal-lab.git
cd hiergoal-lab
python3 -m unittest discover -s tests -v
python3 -m hiergoal.controller --dry-run
~~~

2. Install Hermes if needed, following the [official installation guide](https://hermes-agent.nousresearch.com/docs/getting-started/installation). If installed, configure the direct **OpenAI API** provider and your existing key:

~~~bash
hermes doctor
hermes model
~~~

Select OpenAI API (direct), not ChatGPT subscription / Codex OAuth / OpenRouter. The controller pins provider = openai-api, model = gpt-6-luna, reasoning = low by default, and uses the officially documented one-shot structured CLI protocol. Hermes reads credentials using its normal local credential configuration. Do not put the key in this repository or a GitHub issue.

3. **Run in a disposable VM/container or a low-privilege local account.** Hermes terminal/file tools have host-level capabilities; a copied workspace is NOT an OS security sandbox. Inspect the prompt/CLI before using real credentials. When ready, explicitly acknowledge the limitation:

~~~bash
python3 -m hiergoal.controller \
  --ack-unsandboxed \
  --reasoning low \
  --max-calls 12 \
  --max-replans 2 \
  --pilot-budget-usd 3
~~~

This is the first **paid** Hermes/Luna experiment. Start with one run and review outputs before increasing scope. The $3 pilot guard is based on recorded visible tokens and nominal price; **it is not a hard billing cap**. It cannot prevent one request from exceeding the amount or fully account for auxiliary model calls. Monitor actual API project spending in the [OpenAI Platform](https://platform.openai.com/usage).

On success the controller exits 0. Other outcomes exit nonzero and are reported as FAIL or UNCERTAIN. No fabricated benchmark results are included.

## What it actually controls

- **Root / long term:** exact fixed owner objective, not writable by model-generated plan.
- **Mid term:** 2–4 model-generated milestones.
- **Short term:** 3–8 model-generated coding leaves with owner-defined acceptance gates, explicit parent IDs and dependency IDs.
- **Plan validation:** exhaustive gate coverage, unique IDs, nonempty instructions, no missing dependencies/cycles.
- **Execution:** only dependency-ready leaves run; already-passing gates may be marked preverified without another model call.
- **Verification:** independently maintained Python unit tests, executed from outside the writable workspace. Agent claims cannot determine success; final integration and visible tests run separately.
- **Adaptive replanning:** when a leaf fails verification, call Hermes for a diagnosis and an alternative leaf instruction, supersede the failed leaf, rewire dependents, and retry. Root goal and gate IDs are unchanged. Replan attempts and API calls are bounded.
- **Traceability:** saved plan, per-call prompt and argv, raw stream-json/stderr, independent gate outputs, task statuses, token-count-based expense estimates.

This does NOT rewrite Hermes internals or replace its native /goal subsystem. It is an **external, task-specific orchestrator** exercising a real Hermes instance. One trace does not prove hierarchical planning improves success rates, nor that an internal Hermes todo tree was causally responsible.

## Outputs and reproducibility

All local output is excluded from Git by .gitignore. Each run creates a distinct folder:

~~~text
runs/hiergoal-<UTC>-<id>/
  workspace/                 copy of the coding task after agent edits
  state.json                 actual goal hierarchy, status, supersessions
  records.json               per-call usage, estimate and overall verdict
  initial_grading.json       fixed starting state
  01-plan.prompt.txt         exact planner instruction
  01-plan.stream.jsonl       actual Hermes output and tool events
  01-plan.stderr.txt         diagnostics
  ...-execute-S*.stream.jsonl / ...-replan-S*.stream.jsonl
  gate-*.json                immutable gate results
  final-visible.json         external visible-test check
~~~

The evaluator in evaluation/test_release.py is **not copied into the task workspace**, although it is part of this public repository. The harness is not a malicious-agent security boundary: never execute it against sensitive host data.

To resume an interrupted run, first confirm no earlier Hermes gateway task is still working and then run:

~~~bash
python3 -m hiergoal.controller --resume runs/hiergoal-<id> --ack-unsandboxed
~~~

Running the same experiment on different Hermes versions or workstations can change results; record the Hermes version, Python version, OS, model route, reasoning level, and time when publishing.

## Safety and pricing

- The only approved model route for this controller is gpt-6-luna via the direct OpenAI API.
- Default maximum: 12 Hermes invocations, 18 tool iterations per invocation, 2 replans, 600 seconds per invocation. These are bounded local execution controls, not guaranteed API billing limits or a secure container.
- USD estimates use the standard short-context Luna rates of $0.10 input and $0.50 output per 1M tokens and may differ from actual billing due to caching, context-length tiers, service tiers and additional API calls.
- The controller stops additional invocations if estimated visible spend exceeds its local pilot guard or token telemetry is absent. API metering can still lag behind real billing.
- Inspect and redact traces before publishing. Raw logs may include local system information.

## References

- [Research protocol in Japanese](docs/protocol_ja.md)
- [Original Hermes feature proposal #156054](https://github.com/NousResearch/hermes-agent/issues/156054)
- [H-JEPA: End-to-End Learning of Hierarchical World Models for Visual Planning (2026)](https://arxiv.org/abs/2610.06805) — architectural research motivation, not direct evidence about LLM agents
- [Hermes Agent official CLI reference](https://hermes-agent.nousresearch.com/docs/reference/cli-commands)
- [GPT-6 Luna model specification and pricing](https://developers.openai.com/api/docs/models/gpt-6-luna)

Independent research project licensed under Apache-2.0. Hermes Agent remains an upstream dependency with its own license. Neither Nous Research nor OpenAI endorses the experiment.
