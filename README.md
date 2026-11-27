# HierGoal Lab — Hierarchical Goal Control Research

[![Offline CI](https://github.com/Unjuno/hiergoal-lab/actions/workflows/offline.yml/badge.svg)](https://github.com/Unjuno/hiergoal-lab/actions/workflows/offline.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

**Research question:** can evidence-driven local replanning recover from failed
subgoals while preserving the owner's objective, and improve on simpler controls?

The current method study compares `flat_retry`, `hierarchy_fixed`, and
`hierarchy_adaptive` on bounded code-expression repair, data transformation, and
resource scheduling. It runs directly through the model API; Hermes is optional.
Fixed and adaptive methods share an initial plan. Independent grading and trace
replay determine outcomes.

## Current findings — 2026-11-26 JST

The limited recovery mechanism works in observed cases. **An advantage in success
rate or token efficiency over the flat control has not been demonstrated under
the tested conditions.** The adaptive implementation revises a failed leaf's
instruction within fixed goals and dependencies; it does not split or merge the
goal tree. See the [results and evidence](docs/results_20261126_ja.md) and
[discussion](docs/discussion_20261126_ja.md) for the supported claims and limits.

| Latest v2.5 run | Completed trials | Task PASS / FAIL | Scoped result |
| --- | ---: | ---: | --- |
| [Study](experiments/method-study-live/study/run-45729335900-attempt-1/summary.md) | 216 | 176 / 40 | Prespecified comparative-effect criterion: FAIL |
| [Scale](experiments/method-study-live/scale/run-45703053665-attempt-1/summary.md) | 252 | 215 / 37 | Finite scale-resilience criterion R8: FAIL |
| [Reliability](experiments/method-study-live/reliability/run-45732751285-attempt-1/summary.md) | 720 | 717 / 3 | Finite repeatability criterion R9: PASS |

These are different criteria. All three runs completed with passing record audits;
audit PASS is not evidence of method superiority. Repeated trials are not independent
tasks, and the profiles must not be pooled as one homogeneous study.

The earlier real Hermes benchmark also ran: its saved audit reports record 8/8
successful cases and two successful paths after replanning. It had no flat control
and used four defect conditions of one CSV-ledger task. See the
[results record](docs/results_20261126_ja.md) for its evidence limits.

## Read in this order

The next focused study is the [Controlled Recovery Pilot](docs/controlled_recovery_protocol_ja.md):
six unused task instances, twelve identical post-failure checkpoints, and twenty-four
fixed/adaptive repair slots. Its preparation, repair budgets, and replay auditor are
separate from v2.5. See its [execution and evidence index](experiments/controlled-recovery/README.md).
This pilot tests the apparatus and feasibility; it cannot establish comparative efficacy.
Its first authorized live launch stopped at OpenAI authentication (`401 / expired_secret_key`)
before any repair trial. The final code passed 358 offline tests; see the
[launch status and restart steps](docs/recovery_pilot_status_20261127_ja.md).

1. [Latest results](docs/results_20261126_ja.md): what ran, what passed, and which claims remain unresolved.
2. [Discussion](docs/discussion_20261126_ja.md): observed failure stages, causal hypotheses, and their limits.
3. [Repository map](docs/repository_map_ja.md): code, evaluation, workflows, and evidence locations.
4. [Experiment archive](experiments/README.md): run identities, protocol versions, and stored evidence.
5. [Documentation index](docs/README.md): specifications, operational guides, and historical audits.

## Offline verification

The method-study apparatus uses Python 3.11+ and the standard library. These checks
need no API key, Hermes, or OpenCode and submit no model requests:

```bash
git clone https://github.com/Unjuno/hiergoal-lab.git
cd hiergoal-lab
python3 -m unittest discover -s tests -v
python3 -m hiergoal.study check --profile pilot --output runs/method-check-pilot
python3 -m hiergoal.study prepare --profile study --output runs/method-ready
```

`check` uses a simulated oracle to verify the apparatus. `prepare` freezes a manifest
without executing it. Neither measures live model performance. Use a new output
directory for each preparation or check; preserve earlier evidence.

For all five profiles and the combined requirement review, follow
[the offline workflow](.github/workflows/offline.yml). The suite reviewer needs
compatible manifests and complete traces, not only the public summary files.

## Study profiles

| Profile | Task design | Conditions | Repeats per method and condition | Scheduled trials |
| --- | --- | --- | ---: | ---: |
| `pilot` | 3 development tasks | normal / environment change | 1 | 18 |
| `study` | 12 heldout tasks | normal / environment change | 3 | 216 |
| `mechanism` | 6 composed tasks with independent branches | normal / forced subgoal fault | 3 | 108 |
| `scale` | 3 families × 7 prescribed configurations | normal / forced subgoal fault | 2 | 252 |
| `reliability` | 12 composed tasks with independent branches | normal / forced subgoal fault | 10 | 720 |

All profiles compare three methods. Environmental changes do not always cause a
failure; fault assignment, delivery, and recovery are reported separately.
The scale profile reaches 73 goals, 48 leaves, five hierarchy levels, and 120 direct
dependency edges. Deeper configurations add verification work, so depth is not an
isolated factor. These are controlled synthetic tasks, not a general autonomy benchmark.

The [protocol](docs/method_study_ja.md), [nine-requirement definitions](docs/method_requirements_audit_ja.md),
[v2.4 audit](docs/method_reaudit_v2_4_ja.md), and [v2.5 repair record](docs/method_resume_v2_5_ja.md)
are included in the protocol fingerprint. Their historical text is retained;
use the latest results above for the current execution status.

## When a new live run is needed

Read the [launch and archival guide](docs/method_live_launch_ja.md) and the frozen
conditions before selecting **Actions → Method validation study**. The default
`mode=prepare` performs offline checks and prepares a manifest. Only a manual
`mode=run` uses `OPENAI_API_KEY` and starts the selected profile. Ordinary pushes do
not start model inference. Resource ceilings are experiment budgets, not billing caps.

Audited public results are archived under
`experiments/method-study-live/<profile>/run-<run_id>-attempt-<attempt>/`.
Raw traces remain separate Actions artifacts with limited retention; public
summaries alone cannot support a full trace replay. See the
[archive index](experiments/README.md) before reusing any evidence.

## Earlier Hermes route

The external Hermes controller, task fixture, benchmark, and optional OpenCode ACP
route are retained for reproducibility. This is not native Hermes `/goal` or Kanban
integration. It is separate from the method study above.

- [Hermes CI execution and evidence guide](docs/ci_experiments_ja.md)
- [Original benchmark protocol](docs/benchmark_protocol_ja.md)
- [Issue #156054 conformance](docs/issue-156054-conformance.md)
- [Original OpenCode ACP protocol](docs/protocol_ja.md)
- [Hermes local helper](scripts/experiment.sh) and [free-profile setup](scripts/setup_opencode_free.sh)

The Hermes route uses file and terminal tools; follow its environment and resumption
requirements. A green installation check does not establish live inference or billing.

## Project references

- [Original proposal: Hermes issue #156054](https://github.com/NousResearch/hermes-agent/issues/156054)
- [H-JEPA motivation paper](https://arxiv.org/abs/2610.06805): architectural motivation, not evidence of this implementation's effectiveness.
- [Contributing and evidence preservation](CONTRIBUTING.md)

Apache-2.0 independent research project. Hermes Agent and provider authors do not
endorse this work. Keep credentials and unreviewed raw logs out of public commits.
