# HierGoal Lab — Hierarchical Goal Control Research

[![Offline CI](https://github.com/Unjuno/hiergoal-lab/actions/workflows/offline.yml/badge.svg)](https://github.com/Unjuno/hiergoal-lab/actions/workflows/offline.yml)
[![Hermes CI](https://github.com/Unjuno/hiergoal-lab/actions/workflows/live-experiment.yml/badge.svg)](https://github.com/Unjuno/hiergoal-lab/actions/workflows/live-experiment.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

## Method validation study — Hermes is optional

The research target is **evidence-driven hierarchical goal control and local replanning**.
The new method study compares `flat_retry`, `hierarchy_fixed`, and `hierarchy_adaptive`
with the same model, public feedback, artifact tools, and resource ceilings. Fixed and
adaptive hierarchies share their initial plan. Persistent environment updates and
forced substantive subgoal faults test recovery; withheld final grading and
semantic trace replay determine success. The v2.1 audit covers all nine requested
requirements, including nonempty unrelated branches, bounded replanning, scaling,
and repeated outcomes.

| Profile | Tasks | Conditions | Methods | Repeats | Scheduled trials |
| --- | --- | --- | --- | --- | ---: |
| `pilot` | 3 development tasks, one per family | normal / fault | 3 | 1 | 18 |
| `study` | 12 heldout tasks, four per family | normal / fault | 3 | 3 | 216 |
| `mechanism` | 6 composed tasks with independent branches | normal / forced subgoal fault | 3 | 3 | 108 |
| `scale` | 3 families × 7 prescribed configurations | normal / forced subgoal fault | 3 | 2 | 252 |
| `reliability` | The same 12 heldout tasks as `study` | normal / fault | 3 | 10 | 720 |

The task families are bounded code-expression repair, data transformation, and
resource scheduling. These are controlled synthetic tasks, not a general autonomy
benchmark. The final analysis retains failures and missing outcomes, clusters
repeats by task, reports paired contrasts and uncertainty, and separates functional
feasibility from evidence of an advantage over the controls.

The scale profile reaches **73 total goals, 48 leaves, 5 hierarchy levels, and
120 direct dependency edges**. Depth changes add validation work; they do not
isolate depth while holding leaf count fixed. Repeated calls and scaled variants
do not become independent task samples.

**Readiness:** all 242 offline regression tests and 1,314 oracle-driven
trajectories across all five profiles passed local verification and semantic
replay. The no-key workflow repeats these checks. See the verification record
below for conditions and evidence. Oracle results are software checks, not model-performance measurements.
The first v2.1 live pilot revealed a replay inconsistency when an accepted patch invalidated an upstream leaf. v2.2 selects the post-patch executable leaf for both decision and replay; see [the pilot regression fix](docs/method_pilot_fix_v2_2_ja.md).
The v2.3 mechanism follow-up adds strict initial-plan schemas and lossless input deduplication; see [the mechanism fix and offline evidence](docs/method_mechanism_fix_v2_3_ja.md). Live model performance remains unverified. The earlier offline counts above refer to v2.1. No new live trial is started by this fix.

```bash
# No API calls or key required:
python -m unittest discover -s tests -v
for profile in pilot study mechanism scale reliability; do
  python -m hiergoal.study check --profile "$profile" --output "runs/method-check-$profile"
done
python -m hiergoal.study prepare --profile study --output runs/method-ready
```

For later execution, use **Actions → Method validation study**. Its default
`mode=prepare` runs only offline checks and prepares a frozen manifest. Only an
explicit manual `mode=run` receives `OPENAI_API_KEY` and starts the chosen profile.
Pushes never start live inference. The initial live profile should be `pilot`.
Use the other profiles separately for mechanism, method comparison, scale, and
repeatability. The report separates engineering coverage, finite observed
benchmark criteria, empirical evidence, and unresolved scientific uncertainty.

See the [Japanese research protocol and commands](docs/method_study_ja.md),
[nine-requirement audit](docs/method_requirements_audit_ja.md),
[v2.1 follow-up audit and regression evidence](docs/method_reaudit_v2_1_ja.md),
[completed readiness checks](docs/method_study_readiness_ja.md), and
[frozen v2.1 study manifest](experiments/method-study-v2.1/study-manifest.json).
The previous v1 and v2 manifests are historical and cannot be run against changed
newer sources; prepare a new output directory instead of reusing old traces.

## Earlier Hermes integration experiment

An experimental Python controller running real **Hermes Agent** instances through a three-level goal hierarchy: fixed long-term objective → model-proposed mid-term milestones → short-term executable tasks. The controller validates plans and dependencies, invokes Hermes, independently verifies results and replans failed leaves.

**Default inference:** official OpenCode v2 CLI via ACP, using a curated free model instead of the OpenAI paid API. Hermes executes file/terminal tools; OpenCode supplies inference.

**Current live experiment path:** to use the user's original OpenAI API/Luna plan, explicitly select `--backend luna` in the commands below. The free OpenCode route is optional and produces a separate dataset. Neither route's live inference has been proven by offline CI.

**Independent re-audit (2026-11-18):** [findings and unresolved limitations](docs/re-audit-2026-11-18.md). Completed dependencies are now invalidated on local replanning and the public report requires independent parent and leaf acceptance evidence.

## Run real Hermes experiments in GitHub Actions

Register the repository Actions secret **`OPENAI_API_KEY`**, then open **Actions → Hermes live experiment → Run workflow**. Select `smoke` for the first real API connection check, `pilot` for one task, or `benchmark` for the existing four profiles × two repetitions. The initial nominal spend guard is USD 1; it is not a billing cap.

The workflow installs an immutable Hermes revision with Python 3.14.10, runs the direct `openai-api` / `gpt-6-luna` path, and publishes verified JSON/CSV results and an Actions summary, including failed attempts. Each Hermes invocation gets a fresh home and explicit gateway cleanup. Raw prompts, traces, stderr, workspaces and credentials are excluded from uploaded artifacts.

Push-triggered runs and manual `check` mode only verify the actual Hermes installation and CLI; they make **no inference requests**. A green check run is not evidence of successful API inference. See the [Japanese CI execution guide](docs/ci_experiments_ja.md) for setup, budgets, result retrieval and interpretation.

## Quick start: one command to verify, one command to run

After installing Hermes 0.22.2+, OpenCode v2 and creating the dedicated profile with `bash scripts/setup_opencode_free.sh`:

~~~bash
# Safe check: offline tests + catalog/CLI checks, no model prompts
bash scripts/experiment.sh --check

# Execute one real benchmark task; requires isolated environment
bash scripts/experiment.sh --run
~~~

If the check fails, follow the setup steps below. This local quick start uses the **OpenCode free-model** configuration. Free eligibility is not guaranteed; verify current vendor terms. The separate manual Actions workflow above uses the direct paid Luna route.

**Status:** offline tests and synthetic-Hermes integration pass in GitHub Actions. **No actual Hermes + OpenCode model-inference experiment has been run in this environment.** No causal performance comparison or superiority claim is made.

**Issue-specific research contract:** [Conformance to Issue #156054](docs/issue-156054-conformance.md). This prototype is not a native Hermes /goal integration. Mid-term parent acceptance now requires fresh independent evidence; child completion alone is insufficient.

## Preliminary multi-case benchmark (4 profiles × 2 runs)

The benchmark uses the **same Issue #156054 hierarchical goal controller** across four initial bug distributions with two fresh repetitions each (8 actual Hermes runs). It is a preliminary operational test, **not** evidence that the hierarchy outperforms a flat goal. Read the [preregistered benchmark protocol](docs/benchmark_protocol_ja.md).

~~~bash
# Inspect the case schedule only: no model calls or billing
python3 -m hiergoal.benchmark

# After ONE successful paid pilot and only in an isolated local environment:
python3 -m hiergoal.benchmark --run --backend luna \
  --approve-paid-api --ack-unsandboxed \
  --total-soft-budget-usd 6 --per-case-soft-budget-usd 1.5
~~~

Results are retained locally at `runs/benchmarks/benchmark-<id>/summary.json` and `schedule.json`. They include PASS/FAIL/UNCERTAIN per attempt, verified success count, median elapsed Hermes seconds, median visible tool calls, replans and nominal spend where measured. **Budget numbers are soft telemetry-based guards, not billing caps**. Never publish raw prompts, stderr or agent traces without redaction.
## Run with the original Luna / OpenAI API plan

This is an explicitly opted-in alternative to the OpenCode Free ACP backend; it needs **only Hermes and an existing OpenAI API key**, not OpenCode or a community plugin.

Set `OPENAI_API_KEY` in your local environment or `~/.hermes/.env`. Never commit keys, paste them into GitHub, or send them to chat.

~~~bash
git clone https://github.com/Unjuno/hiergoal-lab.git
cd hiergoal-lab

# Zero-cost local checks (Hermes CLI, key presence, tests)
bash scripts/experiment.sh --check --backend luna

# One real hierarchical Hermes task (paid OpenAI API, explicitly authorized)
bash scripts/experiment.sh --run --backend luna --approve-paid-api --pilot-budget-usd 3
~~~

Use a disposable VM/container or a restricted OS account: Hermes has shell and file tools. The `$3` local budget guard estimates **previously observed** standard-rate Luna usage, not an enforceable billing cap. It cannot cancel a model request after that request starts or account for all auxiliary calls. The model is pinned to `gpt-6-luna` via `openai-api`; normal `.env` credentials are used even with `--ignore-user-config`. Inspect actual charges in OpenAI Platform.

One run means **one observational case**, not a comparative benchmark. Existing free-ACP mode is unchanged: `bash scripts/experiment.sh --run --backend free`. Keep traces separate by backend. Real CI inference is verified only by the corresponding live-run evidence, not the offline badge.
## Requirements

- macOS / Linux / Windows WSL2, Python 3.11+, Git
- Hermes Agent >=0.22.2 with its required Python runtime. The CI-pinned Hermes v0.23.3 requires Python 3.14; the controller's offline tests still support Python 3.11+.
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

## 7. Interrupted calls and safe resumption

Every Hermes invocation writes a `started` record before process launch and records its status after the terminal event. The controller uses a POSIX file lock to prevent two local controllers from writing to one run. If a previous invocation was interrupted, **resumption is refused by default**. Confirm externally that the old Hermes process and gateway turn are no longer running, then use:

~~~bash
python3 -m hiergoal.controller --resume runs/hiergoal-<your-run-id> \
  --ack-unsandboxed --confirm-stopped
~~~

`--confirm-stopped` is an explicit operator assertion, **not** an automated stop check. A detached gateway may continue even after the CLI exits. Do not use this flag until the old session is verified stopped. The interrupted call remains counted toward `--max-calls` and the recovery is recorded. These POSIX locks require macOS / Linux / WSL2 and do not protect runs shared across hosts or network filesystems.

## 8. Experiment provenance

Each new run records an immutable `protocol_id` computed from SHA-256 digests of the controller, planner validator, logging parser, acceptance tests, task fixture and free-model setup script, plus the local Git commit, Python version, OS and architecture. Resumption refuses a changed protocol to prevent results from mixing different evaluator/code revisions; create a new run after updating the repository. The public report includes a limited provenance subset and does not publish local paths or raw environment variables.

## 9. Read-only local preflight (no inference)

After setting up the `hiergoal-free` profile, check the local Hermes and OpenCode CLI binaries and config before running the task:

~~~bash
python3 -m hiergoal.preflight --check-catalog --output runs/preflight.json
~~~

This checks the installed CLI versions and the selected model's current OpenCode catalog listing. `--check-catalog` may access the Internet for catalog metadata but never submits a model prompt. A reported `READY_FOR_MANUAL_LIVE_TEST` is **not proof of login, successful Hermes tool execution, or free billing**; it only verifies the static prerequisites. The first live run remains a manual operator action.
