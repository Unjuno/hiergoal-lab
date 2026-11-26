# Preliminary benchmark protocol — Hermes Issue #156054

> **Historical protocol.** The body preserves the conditions and knowledge available when this preliminary benchmark was prepared. Its statements about live runs being unverified or CI using only fake Hermes are historical, not the current experiment status. Real Hermes pilot and benchmark reports were subsequently recorded. See [results and evidence boundaries as of 2026-11-26 JST](results_20261126_ja.md). The execution steps below are retained for provenance; this document does not schedule another run.

## Scope

**Goal:** Observe whether a real Hermes Agent, driven by the external hierarchical goal controller, completes multiple versioned coding tasks and uses evidence-driven local replanning. This is a **single-method operational benchmark**, not a comparison with flat goals.

**Workload:** Four deterministic initial defect profiles of the same CSV ledger project. All use the same root goal and the same six independent acceptance gates; only initial code differs:

| ID | Initial defects / distinguishing feature |
|---|---|
| `legacy` | Original parser and summary both defective |
| `parser_ready` | Parser fixed in advance; summary still defective |
| `summary_ready` | Summary fixed in advance; parser still defective |
| `refund_rounding` | Refund-sign handling and HALF_EVEN rounding errors |

The experiment uses **two fresh, independent runs per profile**: eight observed attempts in total. Task order is shuffled using seed 1729, and the actual execution order is saved before the first call. The seed controls task order, **not** model sampling. Each run uses a new workspace; no task is solved using another run's modified files.

## H / T / D / C / U

**H (falsifiable operational hypothesis):** The implemented hierarchy can generate valid milestones/leaves, invoke real Hermes to repair the task, independently verify parent and root acceptance criteria and recover from failures. An engineering target of at least 6 verified PASS results out of 8 is set before running. This threshold is a pragmatic prototype target, **not a scientifically established performance threshold**.

**T (minimal execution):** n_min = 4 defect profiles × 2 repetitions = 8 fresh experiments. Python 3.11+, Hermes Agent and direct OpenAI API `gpt-6-luna`, low reasoning, `file,terminal,todo` tools for execution, same max 18 turns per Hermes call, 12 calls and 2 replans per experiment. First execute **one pilot** and inspect live integration before running eight attempts. Batch aggregate nominal soft guard = $6 USD, per-task soft guard = $1.50 USD. These are not enforceable billing limits.

**D (decision rules):**

- Operational target **PASS** only when at least 6 of all 8 attempts are backed by independent parent/root/leaf evidence, all eight attempts have a terminal classification, and no unaccounted process or missing result is presented as a success.
- Operational target **FAIL** if all eight finish with valid classifications but fewer than six verified PASS results.
- **UNCERTAIN** if the batch halts early, the API model cannot be accessed, there are incomplete traces, token-metering gaps, or evaluation/evidence cannot be authenticated. A model-reported success is never accepted without independent deterministic tests.

**C (counter-hypotheses):** (i) The model merely writes a plan but cannot execute it; (ii) plan generation fails schema validation; (iii) completion of a lower subgoal breaks earlier gates; (iv) environment/provider/auth failures mimic planning failures; (v) only trivially related bug variations are solved and findings do not generalize outside this small Python project.

**U (uncertainty):** Model non-determinism without a controlled generation seed, task selection, the single repository/domain, gateway/tool differences across hosts, usage telemetry, caching, and provider charges. With eight heterogeneous cases, this report is **descriptive only**. A pooled Bernoulli confidence interval or a single combined standard uncertainty u_c with expansion factor k is not justified without assumptions beyond this design. Report raw counts and per-case results.

## Metrics and variables

| Symbol | Japanese meaning | SI unit | Operational definition | Domain / assumptions | Type |
|---|---|---|---|---|---|
| N | 評価を開始した実行数 | 1 (count) | PASS/FAIL/UNCERTAIN の件数 | 0..8, integer | Integer scalar |
| S | 証拠付き成功数 | 1 (count) | 監査レポートが PASS と認定した回数 | 0..N | Integer scalar |
| R | 再計画回数 | 1 (count) | state.json の replans | >=0, bounded by budget | Integer scalar |
| T | Hermes実行時間 | s | `elapsed_seconds` of actual Hermes invocations, summed per task | >=0, no queue/wall setup overhead | Real scalar |
| K | ツール呼び出し件数 | 1 (count) | Hermes JSONLの `tool_use` イベント数 | >=0, visible-stream count only | Integer scalar |
| N_in | 観測された入力トークン数 | 1 (count) | Hermes終端イベントの input token count | nonnegative, can be missing | Integer scalar or missing |
| N_out | 観測された出力トークン数 | 1 (count) | Hermes終端イベントの output token count | nonnegative, can be missing | Integer scalar or missing |
| C_est | 名目推定API利用額 | USD (not SI) | sum of each recorded run's estimated cost | >=0 or missing; not billing evidence | Real scalar or missing |

The observed pass fraction is the number of independently verified passes divided by the number of attempted runs; planned-but-not-executed tasks are reported separately and are never counted as failures. Unit check: task and token counts are dimensionless; time is in seconds; a token count multiplied by its per-token USD rate yields USD. These units are not mixed.

## Execution — no model calls until expressly authorized

1. In a **disposable VM/container or low-privilege OS account**, clone/pull the repo and configure Hermes direct OpenAI API credentials locally. Never publish keys.
2. Run `bash scripts/experiment.sh --check --backend luna` and `python3 -m hiergoal.benchmark` to verify setup and print the randomized schedule without inference.
3. Run one paid pilot: `python3 -m hiergoal.controller --backend luna --case legacy --approve-paid-api --ack-unsandboxed --pilot-budget-usd 1`. Inspect state, grade files, and raw trace. This is deliberately a separate pilot not counted among the eight runs.
4. Only if the pilot behaves correctly, run `python3 -m hiergoal.benchmark --run --backend luna --approve-paid-api --ack-unsandboxed --total-soft-budget-usd 6 --per-case-soft-budget-usd 1.5`.
5. Inspect `runs/benchmarks/benchmark-*/summary.json` and `schedule.json`, and retain each individual run's `records.json`, `state.json` and JSONL traces locally. The batch stops on UNCERTAIN or missing paid token telemetry. Read `halt_reason` before retrying or changing the run protocol.
6. Review and redact all files before publication. For any quoted PASS outcome, publish source/fixture hashes, model route, tool trace summary and independent verification evidence.

**Cost limitation:** The cost guard is based on the last returned visible token meter. One expensive request can exceed a limit; auxiliary calls and long-context/caching costs may not be included. Use OpenAI Platform budget settings and inspect actual usage. The first live run can still fail due to an API key, inaccessible model, incompatible Hermes version, tool permissions or network.

## Inference and evidence boundaries

GitHub Actions only executes synthetic fake-Hermes integration tests. It can validate state transitions, CLI argument generation, case initialization and metric aggregation, but **cannot prove real Luna inference works**. The H-JEPA paper is an architectural motivation and does not imply a result for Hermes. The upstream issue requires more evidence before proposing integration into native `/goal`, `/subgoal` or Kanban.

Links: [Hermes Issue #156054](https://github.com/NousResearch/hermes-agent/issues/156054), [H-JEPA arXiv](https://arxiv.org/abs/2610.06805).
