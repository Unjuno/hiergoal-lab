# HierGoal paired study analysis

**Prespecified exploratory benchmark decision: UNCERTAIN**  
Engineering invariant feasibility: **PASS**.  
Reason: `confirmatory_requirements_not_satisfied`.

Protocol: `8da9ed005341508f4c302d312023a03ae8588f20b0523abf9b6ebd4ad2a83fee`  
Declared backend/model: `openai` / `gpt-6-luna`; profile: `scale`.

**Descriptive scale profile. It does not alter the original 216-trial study efficacy rule; no inferential CI or p-value is derived from this profile. Finite acceptance criteria, where declared, are reported separately.**

## Coverage and validity

The schedule contains 252 trials in 84 paired blocks and 21 task clusters. Repeats and individual acceptance gates do not increase the number of task clusters.

| Scheduled | Supplied records | PASS | FAIL | UNCERTAIN | NOT_RUN | Missing outcomes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 252 | 252 | 215 | 37 | 0 | 0 | 0 |

Unrecorded scheduled trials: 0; these are included as NOT_RUN. Supplied records can include explicit NOT_RUN placeholders and do not imply execution. Record-consistency issues: 0. Benchmark decision eligible: no.

Benchmark decision blockers:

- `scale_is_descriptive_only`

## Nine requirement evidence rules

These nine scoped evidence rules do not replace the frozen study's separate efficacy decision. Engineering PASS on simulated records is software validation only.

PASS applies only to the scope in its row. Engineering PASS can describe simulated software validation. Model-execution coverage remains UNCERTAIN without valid declared model records; it is not the benchmark efficacy decision. Missing or zero unrelated comparisons are UNCERTAIN. NOT_APPLICABLE is reserved for an operation outside the declared arm or condition.

| ID | Requirement | Scoped status | Engineering | Model-execution coverage | Scope |
| --- | --- | --- | --- | --- | --- |
| R1 | Forced failed subgoal and verified recovery | UNCERTAIN | UNCERTAIN | UNCERTAIN | Public-pass to forced domain-fail to an accepted revision of that failed target to independent final-pass, in at least one adaptive trace per family. |
| R2 | Hierarchy, state transitions, and before/after replans | PASS | PASS | PASS | Successfully replayed hierarchical checkpoints plus an exercised, failure-evidenced accepted replan. |
| R3 | Immutable root contract | PASS | PASS | PASS | Every scheduled trace was replayed and the root contract stayed identical in root-bearing state and request snapshots. |
| R4 | Task-family coverage and finite recovery applicability | FAIL | PASS | FAIL | Engineering status measures complete three-family coverage; the empirical rule requires each family's assigned adaptive forced-fault recovery proportion to meet the frozen threshold. |
| R5 | Unrelated goals and artifact fields preserved | UNCERTAIN | UNCERTAIN | UNCERTAIN | Plan comparisons cover accepted adaptive revisions; artifact comparisons cover audited adaptive fault paths independently of whether a revision was accepted. Both comparison sets must be nonempty. |
| R6 | Failure-evidenced and bounded replanning | PASS | PASS | PASS | A replan request must have current failed-leaf evidence and authorization; attempted requests stay within the declared cap. |
| R7 | Independent final grading and replay | PASS | PASS | PASS | Audited final grades must match terminal claims; noncandidate budget failures need not call the hidden grader. |
| R8 | Scale coverage and finite resilience | FAIL | PASS | FAIL | Engineering covers the varied observed trees; the separate finite live-data rule tests frozen per-setting success, paired stress drop, and observed locality thresholds. |
| R9 | Finite repeatability and scientific stability uncertainty | UNCERTAIN | UNCERTAIN | UNCERTAIN | The frozen live reliability rule requires final acceptance in every normal cell and repeated forced domain failure, target revision, and final recovery in every fault cell. |

R8 and R9 scoped decisions concern only frozen finite benchmark thresholds on complete valid live records. General scaling-law, power, precision, and future-stability sufficiency remain UNCERTAIN even if a finite criterion passes. Per-criterion limitations and numerical evidence are retained in summary.json.

## Descriptive paired contrasts

Both normal and assigned-fault conditions are reported. The adaptive-minus-comparator difference is averaged within task and then equally across families. All assigned trials remain in their condition; the scale and reliability profiles do not create extra independent evidence by counting repetitions.

| Condition | Contrast | Task clusters | Observed/scheduled pairs | Difference | Missing-data worst/best bounds |
| --- | --- | ---: | ---: | ---: | --- |
| normal | adaptive_vs_fixed | 21 | 42/42 | 0.024 | [0.024, 0.024] |
| normal | adaptive_vs_flat_retry | 21 | 42/42 | -0.190 | [-0.190, -0.190] |
| fault | adaptive_vs_fixed | 21 | 42/42 | 0.000 | [0.000, 0.000] |
| fault | adaptive_vs_flat_retry | 21 | 42/42 | -0.238 | [-0.238, -0.238] |

Missing-data bounds are identification bounds, not confidence intervals. Incomplete paired data have no complete-case point estimate. No CI or p-value is introduced for these descriptive contrasts. Frozen finite benchmark criteria are reported separately.

## Outcomes by family, arm, and condition

The observed rate excludes missing outcomes only in this explicitly labeled descriptive column. The bounds retain every scheduled trial; no missing outcome is silently scored as failure.

| Family | Arm | Condition | Scheduled | PASS | FAIL | UNCERTAIN | NOT_RUN | Observed successes/observed trials | Scheduled rate bounds |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| code_repair | flat_retry | fault | 14 | 14 | 0 | 0 | 0 | 14/14 | [1.000, 1.000] |
| code_repair | flat_retry | normal | 14 | 14 | 0 | 0 | 0 | 14/14 | [1.000, 1.000] |
| code_repair | hierarchy_adaptive | fault | 14 | 10 | 4 | 0 | 0 | 10/14 | [0.714, 0.714] |
| code_repair | hierarchy_adaptive | normal | 14 | 12 | 2 | 0 | 0 | 12/14 | [0.857, 0.857] |
| code_repair | hierarchy_fixed | fault | 14 | 10 | 4 | 0 | 0 | 10/14 | [0.714, 0.714] |
| code_repair | hierarchy_fixed | normal | 14 | 11 | 3 | 0 | 0 | 11/14 | [0.786, 0.786] |
| data_transform | flat_retry | fault | 14 | 14 | 0 | 0 | 0 | 14/14 | [1.000, 1.000] |
| data_transform | flat_retry | normal | 14 | 14 | 0 | 0 | 0 | 14/14 | [1.000, 1.000] |
| data_transform | hierarchy_adaptive | fault | 14 | 10 | 4 | 0 | 0 | 10/14 | [0.714, 0.714] |
| data_transform | hierarchy_adaptive | normal | 14 | 10 | 4 | 0 | 0 | 10/14 | [0.714, 0.714] |
| data_transform | hierarchy_fixed | fault | 14 | 10 | 4 | 0 | 0 | 10/14 | [0.714, 0.714] |
| data_transform | hierarchy_fixed | normal | 14 | 10 | 4 | 0 | 0 | 10/14 | [0.714, 0.714] |
| scheduling | flat_retry | fault | 14 | 14 | 0 | 0 | 0 | 14/14 | [1.000, 1.000] |
| scheduling | flat_retry | normal | 14 | 14 | 0 | 0 | 0 | 14/14 | [1.000, 1.000] |
| scheduling | hierarchy_adaptive | fault | 14 | 12 | 2 | 0 | 0 | 12/14 | [0.857, 0.857] |
| scheduling | hierarchy_adaptive | normal | 14 | 12 | 2 | 0 | 0 | 12/14 | [0.857, 0.857] |
| scheduling | hierarchy_fixed | fault | 14 | 12 | 2 | 0 | 0 | 12/14 | [0.857, 0.857] |
| scheduling | hierarchy_fixed | normal | 14 | 12 | 2 | 0 | 0 | 12/14 | [0.857, 0.857] |

## Replayed mechanism measurements

Tree cells show median [minimum, maximum] and measured/scheduled trials. Root depth is zero; goal count includes the root. A flat arm has no hierarchy, so its hierarchy measurements are NOT_APPLICABLE.

| Arm | Condition | Replayed/scheduled | Goal count | Leaves | Maximum depth, edges | Dependency edges | Dependency density |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| flat_retry | fault | 42/42 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| flat_retry | normal | 42/42 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| hierarchy_adaptive | fault | 42/42 | 19 [11, 73] (42/42) | 12 [8, 48] (42/42) | 2 [2, 4] (42/42) | 12 [6, 120] (42/42) | 0.152 [0.0484, 0.429] (42/42) |
| hierarchy_adaptive | normal | 42/42 | 19 [11, 73] (42/42) | 12 [8, 48] (42/42) | 2 [2, 4] (42/42) | 12 [6, 120] (42/42) | 0.152 [0.0484, 0.429] (42/42) |
| hierarchy_fixed | fault | 42/42 | 19 [11, 73] (42/42) | 12 [8, 48] (42/42) | 2 [2, 4] (42/42) | 12 [6, 120] (42/42) | 0.152 [0.0484, 0.429] (42/42) |
| hierarchy_fixed | normal | 42/42 | 19 [11, 73] (42/42) | 12 [8, 48] (42/42) | 2 [2, 4] (42/42) | 12 [6, 120] (42/42) | 0.152 [0.0484, 0.429] (42/42) |

Replan counters show known totals and measured/scheduled trials. Attempts count issued requests, including interrupted or over-budget requests. A missing counter is not zero. Operational necessity tests the recorded failed-leaf and progress rule; it does not prove optimality.

| Arm | Condition | Attempted | Accepted | Rejected | Unnecessary | Decision events | Deferred after progress |
| --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 0 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) | 152 (42/42) | 0 (42/42) |
| flat_retry | normal | 0 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) | 67 (42/42) | 0 (42/42) |
| hierarchy_adaptive | fault | 58 (42/42) | 56 (42/42) | 1 (42/42) | 0 (42/42) | 621 (42/42) | 497 (42/42) |
| hierarchy_adaptive | normal | 17 (42/42) | 17 (42/42) | 0 (42/42) | 0 (42/42) | 549 (42/42) | 498 (42/42) |
| hierarchy_fixed | fault | 0 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) | 664 (42/42) | 486 (42/42) |
| hierarchy_fixed | normal | 0 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) | 600 (42/42) | 496 (42/42) |

Locality uses nonempty comparisons of unrelated goals and separately of unrelated artifact fields during repair. Zero checked objects cannot establish locality. Dependency invalidations and fresh re-verifications are counts of evidence transitions.

| Arm | Condition | Unrelated goals checked | Goals unchanged | Artifact fields checked | Fields unchanged | Artifact violations | Invalidated goals | Reverified goals |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 0 (42/42) | 0 (42/42) | 609 (42/42) | 609 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) |
| flat_retry | normal | 0 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) |
| hierarchy_adaptive | fault | 618 (42/42) | 618 (42/42) | 191 (42/42) | 191 (42/42) | 0 (42/42) | 120 (42/42) | 114 (42/42) |
| hierarchy_adaptive | normal | 306 (42/42) | 306 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) |
| hierarchy_fixed | fault | 0 (42/42) | 0 (42/42) | 226 (42/42) | 226 (42/42) | 0 (42/42) | 117 (42/42) | 114 (42/42) |
| hierarchy_fixed | normal | 0 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) | 0 (42/42) |

R5 plan-locality evidence: PASS, 44/44 accepted-revision trials with nonempty comparisons. Artifact-locality evidence: UNCERTAIN, 32/34 delivered-fault trials with nonempty comparisons. Artifact violations remain included when every replan response was rejected; plan and artifact denominators are separate.

Replayed hierarchical checkpoints: 2742; leaf state transitions: 3166; milestone state transitions: 1076; accepted replans with failure evidence: 73. Recorded host fault causes: 67; recorded model diagnoses: 73 (text provenance, not causal validation).

Root checked in 252/252 trials; explicit edit requests: 0; rejected edit requests: 0; actual root changes: 0. Record-verification issue trials: 0 (not assumed actual root mutations). A zero edit-attempt count leaves adversarial rejection unexercised in this run.

Final-grade disposition known in 252/252 trials: grader called 215, passed 215, failed 0, not reached 37. Audit failures: 0; grade/terminal-claim conflicts: 0.

## Repeated outcomes within task

Scheduled repeats per task/arm/condition range from 2 to 2. All-pass, mixed, and all-fail below partition only complete task records. Missing repeats remain explicit. These are observed patterns, not an independent-trial reliability estimate or a claim that the sample is sufficient.

| Arm | Condition | Task clusters | Complete clusters | All repeats PASS | Mixed complete outcomes | All repeats FAIL | Incomplete clusters |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| flat_retry | normal | 21 | 21 | 21 | 0 | 0 | 0 |
| flat_retry | fault | 21 | 21 | 21 | 0 | 0 | 0 |
| hierarchy_fixed | normal | 21 | 21 | 16 | 1 | 4 | 0 |
| hierarchy_fixed | fault | 21 | 21 | 15 | 2 | 4 | 0 |
| hierarchy_adaptive | normal | 21 | 21 | 17 | 0 | 4 | 0 |
| hierarchy_adaptive | fault | 21 | 21 | 16 | 0 | 5 | 0 |

Per-family/repeat cells show successful/observed trials, followed by the missing scheduled count. The same task IDs recur across repeats; the table does not create independent task samples.

| Family | Repeat | Flat normal | Flat fault | Fixed normal | Fixed fault | Adaptive normal | Adaptive fault |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| code_repair | 1 | 7/7; missing 0 | 7/7; missing 0 | 6/7; missing 0 | 6/7; missing 0 | 6/7; missing 0 | 5/7; missing 0 |
| code_repair | 2 | 7/7; missing 0 | 7/7; missing 0 | 5/7; missing 0 | 4/7; missing 0 | 6/7; missing 0 | 5/7; missing 0 |
| data_transform | 1 | 7/7; missing 0 | 7/7; missing 0 | 5/7; missing 0 | 5/7; missing 0 | 5/7; missing 0 | 5/7; missing 0 |
| data_transform | 2 | 7/7; missing 0 | 7/7; missing 0 | 5/7; missing 0 | 5/7; missing 0 | 5/7; missing 0 | 5/7; missing 0 |
| scheduling | 1 | 7/7; missing 0 | 7/7; missing 0 | 6/7; missing 0 | 6/7; missing 0 | 6/7; missing 0 | 6/7; missing 0 |
| scheduling | 2 | 7/7; missing 0 | 7/7; missing 0 | 6/7; missing 0 | 6/7; missing 0 | 6/7; missing 0 | 6/7; missing 0 |

Repeat sufficiency: **UNCERTAIN**. No population power, precision, or future-stability guarantee establishes that the repeat count is scientifically sufficient; a finite acceptance threshold is a separate claim.

## Finite task-family recovery applicability

**Scoped decision: FAIL.** Engineering coverage remains separate. Each of the three families must reach recovery proportion 0.80 over at least 6 assigned adaptive forced-fault trials. Recovery requires a delivered domain failure, an accepted revision of that target, and independent final acceptance. These are finite suite criteria, not a generalization or sample-adequacy guarantee.

| Family | Successful recoveries/observed | Final acceptances | Assigned | Meets frozen minimum |
| --- | ---: | ---: | ---: | --- |
| code_repair | 10/14 | 10 | 14 | FAIL |
| data_transform | 10/14 | 10 | 14 | FAIL |
| scheduling | 12/14 | 12 | 14 | PASS |

## Finite scale-resilience benchmark

**Scoped decision: FAIL.** This is a finite descriptive acceptance rule, not a population scaling law or a replacement study efficacy decision.

Frozen minimum success per adaptive fault setting: 0.80; maximum paired baseline-to-stress success-rate drop: 0.10. Baseline: `{'size': 'small', 'depth': 3, 'density': 'sparse'}`; joint stress: `{'size': 'large', 'depth': 5, 'density': 'dense'}`. Full scheduled outcomes and replay are required; simulations cannot pass this empirical rule.

| Size | Depth, levels | Dependency setting | Successes/observed | Scheduled | Meets frozen minimum |
| --- | ---: | --- | ---: | ---: | --- |
| small | 3 | sparse | 6/6 | 6 | PASS |
| medium | 3 | sparse | 6/6 | 6 | PASS |
| large | 3 | sparse | 2/6 | 6 | FAIL |
| small | 4 | sparse | 6/6 | 6 | PASS |
| small | 5 | sparse | 6/6 | 6 | PASS |
| small | 3 | dense | 6/6 | 6 | PASS |
| large | 5 | dense | 0/6 | 6 | FAIL |

Observed paired success-rate drop: 1.000; complete pairs: 6/6. Pair by family, split, source instance, and repeat; task IDs differ across settings. Root/protocol violation trials: 0; locality violation trials: 0. Successful recovery paths without nonempty locality comparisons: 0; failed paths without such comparisons: 10.

- Thresholds are frozen design choices, not estimates from these outcomes. With six assigned adaptive fault trials per setting, a 0.80 threshold requires at least five successes.
- The stress contrast jointly changes size, depth, and direct dependency burden; fault targets may also differ across paired settings. It is not an isolated causal scale effect.
- The six pairs reuse three source tasks across two repeats; no independent-Bernoulli or population reliability claim is made.
- A failed path without a repair remains a failure in the success denominator and supplies no positive artifact-locality evidence.

## Scale coverage and descriptive outcomes

The schedule contains 7 scale settings and 21 distinct task IDs. Parameter levels and observed tree metrics are separate. Requested depth counts levels including the root; measured depth counts edges from root zero. Topology cells show median [minimum, maximum] and measured/scheduled hierarchical trials.

| Size | Requested depth, levels | Dependency setting | Task IDs | Goals | Leaves | Maximum depth, edges | Dependency edges | Dependency density |
| --- | ---: | --- | ---: | --- | --- | --- | --- | --- |
| large | 3 | sparse | 3 | 41 [41, 41] (24/24) | 32 [32, 32] (24/24) | 2 [2, 2] (24/24) | 24 [24, 32] (24/24) | 0.0484 [0.0484, 0.0645] (24/24) |
| large | 5 | dense | 3 | 73 [73, 73] (24/24) | 48 [48, 48] (24/24) | 4 [4, 4] (24/24) | 120 [120, 120] (24/24) | 0.106 [0.106, 0.106] (24/24) |
| medium | 3 | sparse | 3 | 21 [21, 21] (24/24) | 16 [16, 16] (24/24) | 2 [2, 2] (24/24) | 12 [12, 16] (24/24) | 0.1 [0.1, 0.133] (24/24) |
| small | 3 | dense | 3 | 11 [11, 11] (24/24) | 8 [8, 8] (24/24) | 2 [2, 2] (24/24) | 12 [12, 12] (24/24) | 0.429 [0.429, 0.429] (24/24) |
| small | 3 | sparse | 3 | 11 [11, 11] (24/24) | 8 [8, 8] (24/24) | 2 [2, 2] (24/24) | 6 [6, 8] (24/24) | 0.214 [0.214, 0.286] (24/24) |
| small | 4 | sparse | 3 | 15 [15, 15] (24/24) | 10 [10, 10] (24/24) | 3 [3, 3] (24/24) | 8 [8, 10] (24/24) | 0.178 [0.178, 0.222] (24/24) |
| small | 5 | sparse | 3 | 19 [19, 19] (24/24) | 12 [12, 12] (24/24) | 4 [4, 4] (24/24) | 10 [10, 12] (24/24) | 0.152 [0.152, 0.182] (24/24) |

Outcome cells show successes/observed trials plus missing scheduled trials. Cost cells show median [minimum, maximum] with measured/scheduled trials. Both normal and fault conditions are retained. Paired descriptive contrasts within each setting are also available in summary.json.

| Size | Depth, levels | Dependency setting | Arm | Condition | Task IDs | Outcomes | Logical calls | Logical tokens | Trial wall seconds |
| --- | ---: | --- | --- | --- | ---: | --- | --- | --- | --- |
| large | 3 | sparse | flat_retry | fault | 3 | 6/6; missing 0 | 2.5 [2, 10] (6/6) | 4.29e+04 [2.2e+04, 1.23e+05] (6/6) | 21.4 [5.6, 31.4] (6/6) |
| large | 3 | sparse | flat_retry | normal | 3 | 6/6; missing 0 | 1.5 [1, 4] (6/6) | 1.9e+04 [1.06e+04, 4.94e+04] (6/6) | 14.1 [4.12, 23.1] (6/6) |
| large | 3 | sparse | hierarchy_adaptive | fault | 3 | 2/6; missing 0 | 27.5 [21, 35] (6/6) | 5.18e+05 [3.11e+05, 5.28e+05] (6/6) | 54.7 [48.3, 60.6] (6/6) |
| large | 3 | sparse | hierarchy_adaptive | normal | 3 | 4/6; missing 0 | 27 [17, 33] (6/6) | 4.92e+05 [2.52e+05, 5.27e+05] (6/6) | 47.8 [35.6, 63.6] (6/6) |
| large | 3 | sparse | hierarchy_fixed | fault | 3 | 3/6; missing 0 | 23.5 [7, 34] (6/6) | 4.06e+05 [9.6e+04, 5.27e+05] (6/6) | 44.4 [19.2, 55.6] (6/6) |
| large | 3 | sparse | hierarchy_fixed | normal | 3 | 4/6; missing 0 | 23 [17, 33] (6/6) | 3.92e+05 [2.46e+05, 5.27e+05] (6/6) | 42.3 [26.5, 72.1] (6/6) |
| large | 5 | dense | flat_retry | fault | 3 | 6/6; missing 0 | 2 [2, 5] (6/6) | 4.27e+04 [3.14e+04, 9.17e+04] (6/6) | 24.3 [9.43, 31.6] (6/6) |
| large | 5 | dense | flat_retry | normal | 3 | 6/6; missing 0 | 2 [1, 9] (6/6) | 3.69e+04 [1.49e+04, 1.55e+05] (6/6) | 21.6 [7.34, 28.4] (6/6) |
| large | 5 | dense | hierarchy_adaptive | fault | 3 | 0/6; missing 0 | 24 [21, 25] (6/6) | 5.23e+05 [5.18e+05, 5.33e+05] (6/6) | 46.7 [38.5, 54.1] (6/6) |
| large | 5 | dense | hierarchy_adaptive | normal | 3 | 0/6; missing 0 | 24 [21, 25] (6/6) | 5.23e+05 [5.12e+05, 5.33e+05] (6/6) | 45.9 [35, 56.9] (6/6) |
| large | 5 | dense | hierarchy_fixed | fault | 3 | 0/6; missing 0 | 24 [21, 25] (6/6) | 5.3e+05 [5.17e+05, 5.36e+05] (6/6) | 43.2 [33.7, 55] (6/6) |
| large | 5 | dense | hierarchy_fixed | normal | 3 | 0/6; missing 0 | 24 [21, 25] (6/6) | 5.3e+05 [5.17e+05, 5.35e+05] (6/6) | 42.7 [33, 57.6] (6/6) |
| medium | 3 | sparse | flat_retry | fault | 3 | 6/6; missing 0 | 2 [2, 3] (6/6) | 1.51e+04 [1.19e+04, 1.93e+04] (6/6) | 10.2 [4.23, 12.6] (6/6) |
| medium | 3 | sparse | flat_retry | normal | 3 | 6/6; missing 0 | 1 [1, 2] (6/6) | 7.24e+03 [5.75e+03, 1.26e+04] (6/6) | 7.68 [2.53, 11.1] (6/6) |
| medium | 3 | sparse | hierarchy_adaptive | fault | 3 | 6/6; missing 0 | 19 [12, 23] (6/6) | 1.48e+05 [9.33e+04, 2.38e+05] (6/6) | 26.8 [23.1, 51] (6/6) |
| medium | 3 | sparse | hierarchy_adaptive | normal | 3 | 6/6; missing 0 | 17 [10, 19] (6/6) | 1.33e+05 [7.78e+04, 1.97e+05] (6/6) | 24.7 [21.5, 38.6] (6/6) |
| medium | 3 | sparse | hierarchy_fixed | fault | 3 | 6/6; missing 0 | 18 [10, 19] (6/6) | 1.41e+05 [7.83e+04, 2.03e+05] (6/6) | 22.8 [18.6, 37.8] (6/6) |
| medium | 3 | sparse | hierarchy_fixed | normal | 3 | 6/6; missing 0 | 17 [9, 17] (6/6) | 1.33e+05 [6.98e+04, 1.79e+05] (6/6) | 25.8 [15.6, 38.6] (6/6) |
| small | 3 | dense | flat_retry | fault | 3 | 6/6; missing 0 | 2 [2, 3] (6/6) | 8.89e+03 [7.06e+03, 1.67e+04] (6/6) | 7.7 [3.46, 13] (6/6) |
| small | 3 | dense | flat_retry | normal | 3 | 6/6; missing 0 | 1 [1, 2] (6/6) | 4.15e+03 [3.43e+03, 7.72e+03] (6/6) | 4.69 [2.18, 7.47] (6/6) |
| small | 3 | dense | hierarchy_adaptive | fault | 3 | 6/6; missing 0 | 9 [4, 25] (6/6) | 4.78e+04 [1.55e+04, 1.11e+05] (6/6) | 15.9 [4.92, 44.6] (6/6) |
| small | 3 | dense | hierarchy_adaptive | normal | 3 | 6/6; missing 0 | 7 [3, 21] (6/6) | 3.07e+04 [1.67e+04, 9.3e+04] (6/6) | 14.5 [5.6, 37.8] (6/6) |
| small | 3 | dense | hierarchy_fixed | fault | 3 | 6/6; missing 0 | 10 [6, 14] (6/6) | 5.19e+04 [2.59e+04, 6.32e+04] (6/6) | 15.3 [8.21, 22.6] (6/6) |
| small | 3 | dense | hierarchy_fixed | normal | 3 | 6/6; missing 0 | 9 [4, 14] (6/6) | 4.6e+04 [1.73e+04, 6.33e+04] (6/6) | 12.4 [6.98, 20.4] (6/6) |
| small | 3 | sparse | flat_retry | fault | 3 | 6/6; missing 0 | 2 [2, 3] (6/6) | 8.65e+03 [6.89e+03, 1.14e+04] (6/6) | 6.82 [3.12, 9.96] (6/6) |
| small | 3 | sparse | flat_retry | normal | 3 | 6/6; missing 0 | 1 [1, 2] (6/6) | 4.6e+03 [3.35e+03, 7.26e+03] (6/6) | 5 [2.18, 7.41] (6/6) |
| small | 3 | sparse | hierarchy_adaptive | fault | 3 | 6/6; missing 0 | 10 [6, 14] (6/6) | 5.05e+04 [2.56e+04, 6.45e+04] (6/6) | 18.3 [8.48, 23.5] (6/6) |
| small | 3 | sparse | hierarchy_adaptive | normal | 3 | 6/6; missing 0 | 8 [4, 13] (6/6) | 4.28e+04 [1.68e+04, 5.7e+04] (6/6) | 12.2 [6.01, 19.4] (6/6) |
| small | 3 | sparse | hierarchy_fixed | fault | 3 | 5/6; missing 0 | 10 [6, 64] (6/6) | 5.2e+04 [2.65e+04, 3.1e+05] (6/6) | 17.5 [11.2, 160] (6/6) |
| small | 3 | sparse | hierarchy_fixed | normal | 3 | 5/6; missing 0 | 8.5 [4, 64] (6/6) | 4.3e+04 [1.68e+04, 3.1e+05] (6/6) | 13.1 [5.73, 157] (6/6) |
| small | 4 | sparse | flat_retry | fault | 3 | 6/6; missing 0 | 2 [2, 3] (6/6) | 9.52e+03 [7.9e+03, 1.77e+04] (6/6) | 7.65 [4.55, 12.2] (6/6) |
| small | 4 | sparse | flat_retry | normal | 3 | 6/6; missing 0 | 1 [1, 2] (6/6) | 4.48e+03 [3.75e+03, 8.17e+03] (6/6) | 4.65 [2.2, 6.74] (6/6) |
| small | 4 | sparse | hierarchy_adaptive | fault | 3 | 6/6; missing 0 | 13 [9, 15] (6/6) | 7.05e+04 [4.49e+04, 1e+05] (6/6) | 17.7 [15.4, 31.3] (6/6) |
| small | 4 | sparse | hierarchy_adaptive | normal | 3 | 6/6; missing 0 | 10.5 [7, 15] (6/6) | 6.14e+04 [3.45e+04, 7.58e+04] (6/6) | 16.7 [9.34, 22.5] (6/6) |
| small | 4 | sparse | hierarchy_fixed | fault | 3 | 6/6; missing 0 | 11.5 [8, 18] (6/6) | 6.78e+04 [4.02e+04, 9.59e+04] (6/6) | 24.5 [11.8, 33.1] (6/6) |
| small | 4 | sparse | hierarchy_fixed | normal | 3 | 6/6; missing 0 | 11 [7, 15] (6/6) | 6.43e+04 [3.44e+04, 8.08e+04] (6/6) | 15.6 [12, 27.4] (6/6) |
| small | 5 | sparse | flat_retry | fault | 3 | 6/6; missing 0 | 2 [2, 4] (6/6) | 9.07e+03 [8.63e+03, 2.62e+04] (6/6) | 7.07 [3.83, 15.8] (6/6) |
| small | 5 | sparse | flat_retry | normal | 3 | 6/6; missing 0 | 1.5 [1, 2] (6/6) | 7.22e+03 [4.15e+03, 1.2e+04] (6/6) | 6.62 [2.45, 10.8] (6/6) |
| small | 5 | sparse | hierarchy_adaptive | fault | 3 | 6/6; missing 0 | 15 [13, 15] (6/6) | 8.52e+04 [7.51e+04, 1.1e+05] (6/6) | 28.5 [19.2, 32.8] (6/6) |
| small | 5 | sparse | hierarchy_adaptive | normal | 3 | 6/6; missing 0 | 13 [9, 13] (6/6) | 7.4e+04 [5.12e+04, 9.54e+04] (6/6) | 19 [14.5, 20.8] (6/6) |
| small | 5 | sparse | hierarchy_fixed | fault | 3 | 6/6; missing 0 | 14 [11, 14] (6/6) | 8.01e+04 [6.4e+04, 1.04e+05] (6/6) | 20.2 [17.1, 23.8] (6/6) |
| small | 5 | sparse | hierarchy_fixed | normal | 3 | 6/6; missing 0 | 12.5 [9, 13] (6/6) | 7.4e+04 [5.14e+04, 9.54e+04] (6/6) | 16.1 [12.8, 29.4] (6/6) |

- Requested depth counts levels including the root; measured max_depth_edges counts edges from root zero.
- Deeper scale fixtures add executable certification leaves. Depth is not varied at fixed leaf count or fixed work.
- The selected scale settings are not a full factorial design; marginal and interaction effects are not identified generally.
- Distinct scale settings generated from shared source instances need not be independent task draws. No scale CI or significance test is reported.


## Recorded per-trial costs

Cells show median [minimum, maximum] and measured/scheduled trial count. Missing token or timing measurements remain missing. Logical calls/tokens include cached shared planning charges per hierarchical trial and therefore do not equal provider billing. Recorded costs include failed and uncertain trials.

| Arm | Condition | Calls | Input tokens | Output tokens | Total tokens | Logical response seconds | Trial wall seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 2 [2, 10] (42/42) | 1.14e+04 [6.44e+03, 1.19e+05] (42/42) | 1.36e+03 [330, 5.22e+03] (42/42) | 1.22e+04 [6.89e+03, 1.23e+05] (42/42) | 8.79 [3.1, 31.4] (42/42) | 8.81 [3.12, 31.6] (42/42) |
| flat_retry | normal | 1 [1, 9] (42/42) | 6.4e+03 [3.07e+03, 1.51e+05] (42/42) | 994 [255, 4.22e+03] (42/42) | 7.09e+03 [3.35e+03, 1.55e+05] (42/42) | 6.09 [2.17, 28.2] (42/42) | 6.1 [2.18, 28.4] (42/42) |
| hierarchy_adaptive | fault | 15 [4, 35] (42/42) | 9.03e+04 [1.46e+04, 5.28e+05] (42/42) | 3.47e+03 [897, 8.54e+03] (42/42) | 9.37e+04 [1.55e+04, 5.33e+05] (42/42) | 31.6 [7.66, 74] (42/42) | 26.4 [4.92, 60.6] (42/42) |
| hierarchy_adaptive | normal | 13 [3, 33] (42/42) | 7.43e+04 [1.44e+04, 5.28e+05] (42/42) | 2.5e+03 [1.14e+03, 7.81e+03] (42/42) | 7.68e+04 [1.67e+04, 5.33e+05] (42/42) | 26 [11.2, 65.8] (42/42) | 21.2 [5.6, 63.6] (42/42) |
| hierarchy_fixed | fault | 14 [6, 64] (42/42) | 8.39e+04 [2.44e+04, 5.3e+05] (42/42) | 3.01e+03 [1.23e+03, 1.63e+04] (42/42) | 8.72e+04 [2.59e+04, 5.36e+05] (42/42) | 26.3 [13.8, 163] (42/42) | 22.8 [8.21, 160] (42/42) |
| hierarchy_fixed | normal | 13 [4, 64] (42/42) | 7.71e+04 [1.53e+04, 5.29e+05] (42/42) | 2.76e+03 [1.1e+03, 1.64e+04] (42/42) | 8.01e+04 [1.68e+04, 5.35e+05] (42/42) | 26 [11.2, 156] (42/42) | 21.1 [5.73, 157] (42/42) |

Separately recorded actual provider usage (cached plan usage is charged only where recorded):

| Arm | Condition | Actual calls | Actual input tokens | Actual output tokens |
| --- | --- | --- | --- | --- |
| flat_retry | fault | 2 [2, 10] (42/42) | 1.14e+04 [6.44e+03, 1.19e+05] (42/42) | 1.36e+03 [330, 5.22e+03] (42/42) |
| flat_retry | normal | 1 [1, 9] (42/42) | 6.4e+03 [3.07e+03, 1.51e+05] (42/42) | 994 [255, 4.22e+03] (42/42) |
| hierarchy_adaptive | fault | 14 [3, 34] (42/42) | 8.56e+04 [1.16e+04, 5.17e+05] (42/42) | 2.56e+03 [487, 6.78e+03] (42/42) |
| hierarchy_adaptive | normal | 12 [3, 33] (42/42) | 7.4e+04 [1.25e+04, 5.28e+05] (42/42) | 1.83e+03 [456, 7.28e+03] (42/42) |
| hierarchy_fixed | fault | 13 [5, 63] (42/42) | 7.96e+04 [2.16e+04, 5.3e+05] (42/42) | 2.27e+03 [740, 1.58e+04] (42/42) |
| hierarchy_fixed | normal | 12 [3, 64] (42/42) | 7.54e+04 [1.25e+04, 5.25e+05] (42/42) | 1.78e+03 [615, 1.64e+04] (42/42) |

Timing context: batch_size: 1; cpu: AMD EPYC 9V45 96-Core Processor; cpu_clock_mhz_observed_range: [2596.098, 4234.098]; git_commit: 07905889ae5f08289915e5e78c4b301f841bb431; logical_cpus: 4; memory_bytes: 16760340480; model_hardware: Provider-managed; not observable; platform: Linux-7.0.0-1017-azure-x86_64-with-glibc2.39; python: 3.12.3; timestamp_utc: 2026-11-25T21:19:13.730854+00:00; working_tree_dirty: False Recorded durations are not a controlled hardware benchmark.

## Recovery diagnostics

Recovery is conditional on a delivered fault and is descriptive. Fault delivery is a post-assignment event, so these rates cannot establish a causal treatment contrast. Fault-assigned trials without delivery still remain in both primary comparisons.

| Arm | Fault assigned | Triggered | Delivered | Triggered, no impact | Untriggered | Trigger unknown | Delivery unknown | Recovered/known recovery outcomes | Recovery bounds among delivered |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| flat_retry | 42 | 42 | 42 | 0 | 0 | 0 | 0 | 42/42 | [1.000, 1.000] |
| hierarchy_adaptive | 42 | 34 | 34 | 0 | 8 | 0 | 0 | 32/34 | [0.941, 0.941] |
| hierarchy_fixed | 42 | 33 | 33 | 0 | 9 | 0 | 0 | 32/33 | [0.970, 0.970] |

## Interpretation and limits

- The scale profile is descriptive only. It does not inherit or relax the frozen 216-trial study decision, and no inferential CI or p-value is assigned to its paired contrasts.
- The manifest defines assignment; fault delivery and recovery never select the primary analysis set (intention to treat).
- PASS is full trial acceptance and FAIL is zero; UNCERTAIN and NOT_RUN are missing, not assumed failures. No incomplete contrast receives a complete-case confirmatory CI or p-value.
- Repeated calls, repeats, and individual gates are not independent task samples. Repeats are averaged within each task and the bootstrap resamples tasks within family.
- This schedule has 21 task clusters (code_repair: 7, data_transform: 7, scheduling: 7). Percentile bootstrap coverage, when reported, is approximate; intervals may be unstable or degenerate and do not establish adequate power. The original study design remains 12 task clusters (4 per family).
- Sign-flip p-values are one-sided tests of zero improvement, conditional on independent cluster sign exchangeability or symmetry under the null. Paired execution alone does not prove these assumptions; the bootstrap CI separately assesses the practical margin.
- The target weights families equally and tasks equally within family. Generalization is limited to the represented task families, task-generating process, model, budgets, and fault intervention.
- Recovery rates condition on delivered faults, a post-assignment event; they are descriptive and cannot replace the assigned-fault comparison.
- Logical calls/tokens include a reused planning artifact for each assigned hierarchical trial. Actual provider usage, when recorded separately, must not be inferred by summing logical charges.
- elapsed_seconds sums logical response durations including reused planning; wall_seconds, when supplied, measures trial wall time. Neither establishes a controlled hardware benchmark.
- Local records and declared backend/model are not an anti-tamper attestation. The caller must validate the frozen manifest and source fingerprints separately.
- The decision is a prespecified exploratory benchmark decision, not general proof of method superiority or a guarantee of power or population coverage.
- Mechanism counters are included only from declared successful replay receipts. Missing or zero unrelated-comparison counts cannot establish locality. The analyzer itself does not replay trace files.
- A bounded, failure-evidenced replan policy is operationally testable; globally optimal or causally necessary replanning is not established by this policy check.
- Repeat tables describe all-pass, all-fail, and mixed observed outcomes. No unregistered power, precision, or stability threshold is introduced after observing results.
