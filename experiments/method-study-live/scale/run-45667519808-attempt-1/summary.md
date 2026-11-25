# HierGoal paired study analysis

**Prespecified exploratory benchmark decision: UNCERTAIN**  
Engineering invariant feasibility: **FAIL**.  
Reason: `confirmatory_requirements_not_satisfied`.

Protocol: `25c3ee07783c209eb8bd1abf3f8cd6125d37703593b6643a9ef517c7c078593e`  
Declared backend/model: `openai` / `gpt-6-luna`; profile: `scale`.

**Descriptive scale profile. It does not alter the original 216-trial study efficacy rule; no inferential CI or p-value is derived from this profile. Finite acceptance criteria, where declared, are reported separately.**

## Coverage and validity

The schedule contains 252 trials in 84 paired blocks and 21 task clusters. Repeats and individual acceptance gates do not increase the number of task clusters.

| Scheduled | Supplied records | PASS | FAIL | UNCERTAIN | NOT_RUN | Missing outcomes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 252 | 252 | 168 | 0 | 63 | 21 | 84 |

Unrecorded scheduled trials: 0; these are included as NOT_RUN. Supplied records can include explicit NOT_RUN placeholders and do not imply execution. Record-consistency issues: 228. Benchmark decision eligible: no.

Benchmark decision blockers:

- `scale_is_descriptive_only`
- `missing_or_invalid_replay_and_root_evidence`
- `missing_or_invalid_independent_grade_evidence`
- `missing_outcomes`
- `record_validity_issues`

Record-consistency issue counts:

- `invariant_ok_false`: 62
- `missing_fault_delivery_flag`: 62
- `missing_validity_flag`: 42
- `protocol_ok_false`: 62

## Nine requirement evidence rules

These nine scoped evidence rules do not replace the frozen study's separate efficacy decision. Engineering PASS on simulated records is software validation only.

PASS applies only to the scope in its row. Engineering PASS can describe simulated software validation. Model-execution coverage remains UNCERTAIN without valid declared model records; it is not the benchmark efficacy decision. Missing or zero unrelated comparisons are UNCERTAIN. NOT_APPLICABLE is reserved for an operation outside the declared arm or condition.

| ID | Requirement | Scoped status | Engineering | Model-execution coverage | Scope |
| --- | --- | --- | --- | --- | --- |
| R1 | Forced failed subgoal and verified recovery | UNCERTAIN | UNCERTAIN | UNCERTAIN | Public-pass to forced domain-fail to an accepted revision of that failed target to independent final-pass, in at least one adaptive trace per family. |
| R2 | Hierarchy, state transitions, and before/after replans | FAIL | FAIL | UNCERTAIN | Successfully replayed hierarchical checkpoints plus an exercised, failure-evidenced accepted replan. |
| R3 | Immutable root contract | UNCERTAIN | UNCERTAIN | UNCERTAIN | Every scheduled trace was replayed and the root contract stayed identical in root-bearing state and request snapshots. |
| R4 | Task-family coverage and finite recovery applicability | UNCERTAIN | UNCERTAIN | UNCERTAIN | Engineering status measures complete three-family coverage; the empirical rule requires each family's assigned adaptive forced-fault recovery proportion to meet the frozen threshold. |
| R5 | Unrelated goals and artifact fields preserved | UNCERTAIN | UNCERTAIN | UNCERTAIN | Plan comparisons cover accepted adaptive revisions; artifact comparisons cover audited adaptive fault paths independently of whether a revision was accepted. Both comparison sets must be nonempty. |
| R6 | Failure-evidenced and bounded replanning | UNCERTAIN | UNCERTAIN | UNCERTAIN | A replan request must have current failed-leaf evidence and authorization; attempted requests stay within the declared cap. |
| R7 | Independent final grading and replay | FAIL | FAIL | UNCERTAIN | Audited final grades must match terminal claims; noncandidate budget failures need not call the hidden grader. |
| R8 | Scale coverage and finite resilience | UNCERTAIN | UNCERTAIN | UNCERTAIN | Engineering covers the varied observed trees; the separate finite live-data rule tests frozen per-setting success, paired stress drop, and observed locality thresholds. |
| R9 | Finite repeatability and scientific stability uncertainty | UNCERTAIN | UNCERTAIN | UNCERTAIN | The frozen live reliability rule requires final acceptance in every normal cell and repeated forced domain failure, target revision, and final recovery in every fault cell. |

R8 and R9 scoped decisions concern only frozen finite benchmark thresholds on complete valid live records. General scaling-law, power, precision, and future-stability sufficiency remain UNCERTAIN even if a finite criterion passes. Per-criterion limitations and numerical evidence are retained in summary.json.

## Descriptive paired contrasts

Both normal and assigned-fault conditions are reported. The adaptive-minus-comparator difference is averaged within task and then equally across families. All assigned trials remain in their condition; the scale and reliability profiles do not create extra independent evidence by counting repetitions.

| Condition | Contrast | Task clusters | Observed/scheduled pairs | Difference | Missing-data worst/best bounds |
| --- | --- | ---: | ---: | ---: | --- |
| normal | adaptive_vs_fixed | 21 | 23/42 | — | [-0.452, 0.452] |
| normal | adaptive_vs_flat_retry | 21 | 23/42 | — | [-0.452, 0.071] |
| fault | adaptive_vs_fixed | 21 | 22/42 | — | [-0.476, 0.452] |
| fault | adaptive_vs_flat_retry | 21 | 22/42 | — | [-0.476, 0.095] |

Missing-data bounds are identification bounds, not confidence intervals. Incomplete paired data have no complete-case point estimate. No CI or p-value is introduced for these descriptive contrasts. Frozen finite benchmark criteria are reported separately.

## Outcomes by family, arm, and condition

The observed rate excludes missing outcomes only in this explicitly labeled descriptive column. The bounds retain every scheduled trial; no missing outcome is silently scored as failure.

| Family | Arm | Condition | Scheduled | PASS | FAIL | UNCERTAIN | NOT_RUN | Observed successes/observed trials | Scheduled rate bounds |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| code_repair | flat_retry | fault | 14 | 11 | 0 | 0 | 3 | 11/11 | [0.786, 1.000] |
| code_repair | flat_retry | normal | 14 | 14 | 0 | 0 | 0 | 14/14 | [1.000, 1.000] |
| code_repair | hierarchy_adaptive | fault | 14 | 6 | 0 | 5 | 3 | 6/6 | [0.429, 1.000] |
| code_repair | hierarchy_adaptive | normal | 14 | 8 | 0 | 6 | 0 | 8/8 | [0.571, 1.000] |
| code_repair | hierarchy_fixed | fault | 14 | 7 | 0 | 4 | 3 | 7/7 | [0.500, 1.000] |
| code_repair | hierarchy_fixed | normal | 14 | 8 | 0 | 6 | 0 | 8/8 | [0.571, 1.000] |
| data_transform | flat_retry | fault | 14 | 14 | 0 | 0 | 0 | 14/14 | [1.000, 1.000] |
| data_transform | flat_retry | normal | 14 | 13 | 0 | 0 | 1 | 13/13 | [0.929, 1.000] |
| data_transform | hierarchy_adaptive | fault | 14 | 8 | 0 | 6 | 0 | 8/8 | [0.571, 1.000] |
| data_transform | hierarchy_adaptive | normal | 14 | 8 | 0 | 5 | 1 | 8/8 | [0.571, 1.000] |
| data_transform | hierarchy_fixed | fault | 14 | 8 | 0 | 6 | 0 | 8/8 | [0.571, 1.000] |
| data_transform | hierarchy_fixed | normal | 14 | 8 | 0 | 5 | 1 | 8/8 | [0.571, 1.000] |
| scheduling | flat_retry | fault | 14 | 13 | 0 | 0 | 1 | 13/13 | [0.929, 1.000] |
| scheduling | flat_retry | normal | 14 | 12 | 0 | 0 | 2 | 12/12 | [0.857, 1.000] |
| scheduling | hierarchy_adaptive | fault | 14 | 8 | 0 | 5 | 1 | 8/8 | [0.571, 1.000] |
| scheduling | hierarchy_adaptive | normal | 14 | 7 | 0 | 5 | 2 | 7/7 | [0.500, 1.000] |
| scheduling | hierarchy_fixed | fault | 14 | 8 | 0 | 5 | 1 | 8/8 | [0.571, 1.000] |
| scheduling | hierarchy_fixed | normal | 14 | 7 | 0 | 5 | 2 | 7/7 | [0.500, 1.000] |

## Replayed mechanism measurements

Tree cells show median [minimum, maximum] and measured/scheduled trials. Root depth is zero; goal count includes the root. A flat arm has no hierarchy, so its hierarchy measurements are NOT_APPLICABLE.

| Arm | Condition | Replayed/scheduled | Goal count | Leaves | Maximum depth, edges | Dependency edges | Dependency density |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| flat_retry | fault | 38/42 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| flat_retry | normal | 39/42 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| hierarchy_adaptive | fault | 23/42 | 15 [11, 19] (23/42) | 10 [8, 12] (23/42) | 3 [2, 4] (23/42) | 10 [6, 12] (23/42) | 0.214 [0.152, 0.429] (23/42) |
| hierarchy_adaptive | normal | 23/42 | 15 [11, 19] (23/42) | 10 [8, 12] (23/42) | 3 [2, 4] (23/42) | 10 [6, 12] (23/42) | 0.214 [0.152, 0.429] (23/42) |
| hierarchy_fixed | fault | 23/42 | 15 [11, 19] (23/42) | 10 [8, 12] (23/42) | 3 [2, 4] (23/42) | 10 [6, 12] (23/42) | 0.214 [0.152, 0.429] (23/42) |
| hierarchy_fixed | normal | 23/42 | 15 [11, 19] (23/42) | 10 [8, 12] (23/42) | 3 [2, 4] (23/42) | 10 [6, 12] (23/42) | 0.214 [0.152, 0.429] (23/42) |

Replan counters show known totals and measured/scheduled trials. Attempts count issued requests, including interrupted or over-budget requests. A missing counter is not zero. Operational necessity tests the recorded failed-leaf and progress rule; it does not prove optimality.

| Arm | Condition | Attempted | Accepted | Rejected | Unnecessary | Decision events | Deferred after progress |
| --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 0 (38/42) | 0 (38/42) | 0 (38/42) | 0 (38/42) | 127 (38/42) | 0 (38/42) |
| flat_retry | normal | 0 (39/42) | 0 (39/42) | 0 (39/42) | 0 (39/42) | 55 (39/42) | 0 (39/42) |
| hierarchy_adaptive | fault | 37 (23/42) | 35 (23/42) | 1 (23/42) | 0 (23/42) | 249 (23/42) | 166 (23/42) |
| hierarchy_adaptive | normal | 14 (23/42) | 14 (23/42) | 0 (23/42) | 0 (23/42) | 206 (23/42) | 169 (23/42) |
| hierarchy_fixed | fault | 0 (23/42) | 0 (23/42) | 0 (23/42) | 0 (23/42) | 278 (23/42) | 165 (23/42) |
| hierarchy_fixed | normal | 0 (23/42) | 0 (23/42) | 0 (23/42) | 0 (23/42) | 220 (23/42) | 168 (23/42) |

Locality uses nonempty comparisons of unrelated goals and separately of unrelated artifact fields during repair. Zero checked objects cannot establish locality. Dependency invalidations and fresh re-verifications are counts of evidence transitions.

| Arm | Condition | Unrelated goals checked | Goals unchanged | Artifact fields checked | Fields unchanged | Artifact violations | Invalidated goals | Reverified goals |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 0 (38/42) | 0 (38/42) | 498 (38/42) | 498 (38/42) | 0 (38/42) | 0 (38/42) | 0 (38/42) |
| flat_retry | normal | 0 (39/42) | 0 (39/42) | 0 (39/42) | 0 (39/42) | 0 (39/42) | 0 (39/42) | 0 (39/42) |
| hierarchy_adaptive | fault | 167 (23/42) | 167 (23/42) | 98 (23/42) | 98 (23/42) | 0 (23/42) | 87 (23/42) | 84 (23/42) |
| hierarchy_adaptive | normal | 69 (23/42) | 69 (23/42) | 0 (23/42) | 0 (23/42) | 0 (23/42) | 0 (23/42) | 0 (23/42) |
| hierarchy_fixed | fault | 0 (23/42) | 0 (23/42) | 94 (23/42) | 94 (23/42) | 0 (23/42) | 87 (23/42) | 87 (23/42) |
| hierarchy_fixed | normal | 0 (23/42) | 0 (23/42) | 0 (23/42) | 0 (23/42) | 0 (23/42) | 0 (23/42) | 0 (23/42) |

R5 plan-locality evidence: UNCERTAIN, 25/25 accepted-revision trials with nonempty comparisons. Artifact-locality evidence: UNCERTAIN, 22/23 delivered-fault trials with nonempty comparisons. Artifact violations remain included when every replan response was rejected; plan and artifact denominators are separate.

Replayed hierarchical checkpoints: 1140; leaf state transitions: 1322; milestone state transitions: 491; accepted replans with failure evidence: 49. Recorded host fault causes: 46; recorded model diagnoses: 49 (text provenance, not causal validation).

Root checked in 169/252 trials; explicit edit requests: 0; rejected edit requests: 0; actual root changes: 0. Record-verification issue trials: 83 (not assumed actual root mutations). A zero edit-attempt count leaves adversarial rejection unexercised in this run.

Final-grade disposition known in 169/252 trials: grader called 168, passed 168, failed 0, not reached 1. Audit failures: 62; grade/terminal-claim conflicts: 0.

## Repeated outcomes within task

Scheduled repeats per task/arm/condition range from 2 to 2. All-pass, mixed, and all-fail below partition only complete task records. Missing repeats remain explicit. These are observed patterns, not an independent-trial reliability estimate or a claim that the sample is sufficient.

| Arm | Condition | Task clusters | Complete clusters | All repeats PASS | Mixed complete outcomes | All repeats FAIL | Incomplete clusters |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| flat_retry | normal | 21 | 18 | 18 | 0 | 0 | 3 |
| flat_retry | fault | 21 | 18 | 18 | 0 | 0 | 3 |
| hierarchy_fixed | normal | 21 | 11 | 11 | 0 | 0 | 10 |
| hierarchy_fixed | fault | 21 | 11 | 11 | 0 | 0 | 10 |
| hierarchy_adaptive | normal | 21 | 11 | 11 | 0 | 0 | 10 |
| hierarchy_adaptive | fault | 21 | 11 | 11 | 0 | 0 | 10 |

Per-family/repeat cells show successful/observed trials, followed by the missing scheduled count. The same task IDs recur across repeats; the table does not create independent task samples.

| Family | Repeat | Flat normal | Flat fault | Fixed normal | Fixed fault | Adaptive normal | Adaptive fault |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| code_repair | 1 | 7/7; missing 0 | 5/5; missing 2 | 4/4; missing 3 | 3/3; missing 4 | 4/4; missing 3 | 3/3; missing 4 |
| code_repair | 2 | 7/7; missing 0 | 6/6; missing 1 | 4/4; missing 3 | 4/4; missing 3 | 4/4; missing 3 | 3/3; missing 4 |
| data_transform | 1 | 6/6; missing 1 | 7/7; missing 0 | 4/4; missing 3 | 4/4; missing 3 | 4/4; missing 3 | 4/4; missing 3 |
| data_transform | 2 | 7/7; missing 0 | 7/7; missing 0 | 4/4; missing 3 | 4/4; missing 3 | 4/4; missing 3 | 4/4; missing 3 |
| scheduling | 1 | 6/6; missing 1 | 7/7; missing 0 | 4/4; missing 3 | 4/4; missing 3 | 4/4; missing 3 | 4/4; missing 3 |
| scheduling | 2 | 6/6; missing 1 | 6/6; missing 1 | 3/3; missing 4 | 4/4; missing 3 | 3/3; missing 4 | 4/4; missing 3 |

Repeat sufficiency: **UNCERTAIN**. No population power, precision, or future-stability guarantee establishes that the repeat count is scientifically sufficient; a finite acceptance threshold is a separate claim.

## Finite task-family recovery applicability

**Scoped decision: UNCERTAIN.** Engineering coverage remains separate. Each of the three families must reach recovery proportion 0.80 over at least 6 assigned adaptive forced-fault trials. Recovery requires a delivered domain failure, an accepted revision of that target, and independent final acceptance. These are finite suite criteria, not a generalization or sample-adequacy guarantee.

| Family | Successful recoveries/observed | Final acceptances | Assigned | Meets frozen minimum |
| --- | ---: | ---: | ---: | --- |
| code_repair | 6/6 | 6 | 14 | UNCERTAIN |
| data_transform | 6/8 | 8 | 14 | UNCERTAIN |
| scheduling | 8/8 | 8 | 14 | UNCERTAIN |

Family applicability blockers:

- `incomplete_profile_outcomes`
- `incomplete_profile_replay_evidence`
- `missing_forced_domain_recovery_evidence`
- `missing_or_invalid_independent_grade_evidence`
- `missing_root_or_protocol_evidence`
- `record_validity_issues`

## Finite scale-resilience benchmark

**Scoped decision: UNCERTAIN.** This is a finite descriptive acceptance rule, not a population scaling law or a replacement study efficacy decision.

Frozen minimum success per adaptive fault setting: 0.80; maximum paired baseline-to-stress success-rate drop: 0.10. Baseline: `{'size': 'small', 'depth': 3, 'density': 'sparse'}`; joint stress: `{'size': 'large', 'depth': 5, 'density': 'dense'}`. Full scheduled outcomes and replay are required; simulations cannot pass this empirical rule.

| Size | Depth, levels | Dependency setting | Successes/observed | Scheduled | Meets frozen minimum |
| --- | ---: | --- | ---: | ---: | --- |
| small | 3 | sparse | 6/6 | 6 | PASS |
| medium | 3 | sparse | 0/0 | 6 | UNCERTAIN |
| large | 3 | sparse | 0/0 | 6 | UNCERTAIN |
| small | 4 | sparse | 6/6 | 6 | PASS |
| small | 5 | sparse | 6/6 | 6 | PASS |
| small | 3 | dense | 4/4 | 6 | UNCERTAIN |
| large | 5 | dense | 0/0 | 6 | UNCERTAIN |

Observed paired success-rate drop: —; complete pairs: 0/6. Pair by family, split, source instance, and repeat; task IDs differ across settings. Root/protocol violation trials: 62; locality violation trials: 0. Successful recovery paths without nonempty locality comparisons: 0; failed paths without such comparisons: 0.

Finite benchmark blockers:

- `incomplete_profile_outcomes`
- `incomplete_profile_replay_evidence`
- `incomplete_six_baseline_stress_pairs`
- `missing_or_invalid_independent_grade_evidence`
- `missing_root_or_protocol_evidence`
- `missing_scale_locality_counters`
- `record_validity_issues`

- Thresholds are frozen design choices, not estimates from these outcomes. With six assigned adaptive fault trials per setting, a 0.80 threshold requires at least five successes.
- The stress contrast jointly changes size, depth, and direct dependency burden; fault targets may also differ across paired settings. It is not an isolated causal scale effect.
- The six pairs reuse three source tasks across two repeats; no independent-Bernoulli or population reliability claim is made.
- A failed path without a repair remains a failure in the success denominator and supplies no positive artifact-locality evidence.

## Scale coverage and descriptive outcomes

The schedule contains 7 scale settings and 21 distinct task IDs. Parameter levels and observed tree metrics are separate. Requested depth counts levels including the root; measured depth counts edges from root zero. Topology cells show median [minimum, maximum] and measured/scheduled hierarchical trials.

| Size | Requested depth, levels | Dependency setting | Task IDs | Goals | Leaves | Maximum depth, edges | Dependency edges | Dependency density |
| --- | ---: | --- | ---: | --- | --- | --- | --- | --- |
| large | 3 | sparse | 3 | — (0/24) | — (0/24) | — (0/24) | — (0/24) | — (0/24) |
| large | 5 | dense | 3 | — (0/24) | — (0/24) | — (0/24) | — (0/24) | — (0/24) |
| medium | 3 | sparse | 3 | — (0/24) | — (0/24) | — (0/24) | — (0/24) | — (0/24) |
| small | 3 | dense | 3 | 11 [11, 11] (22/24) | 8 [8, 8] (22/24) | 2 [2, 2] (22/24) | 12 [12, 12] (22/24) | 0.429 [0.429, 0.429] (22/24) |
| small | 3 | sparse | 3 | 11 [11, 11] (22/24) | 8 [8, 8] (22/24) | 2 [2, 2] (22/24) | 6 [6, 8] (22/24) | 0.214 [0.214, 0.286] (22/24) |
| small | 4 | sparse | 3 | 15 [15, 15] (24/24) | 10 [10, 10] (24/24) | 3 [3, 3] (24/24) | 8 [8, 10] (24/24) | 0.178 [0.178, 0.222] (24/24) |
| small | 5 | sparse | 3 | 19 [19, 19] (24/24) | 12 [12, 12] (24/24) | 4 [4, 4] (24/24) | 10 [10, 12] (24/24) | 0.152 [0.152, 0.182] (24/24) |

Outcome cells show successes/observed trials plus missing scheduled trials. Cost cells show median [minimum, maximum] with measured/scheduled trials. Both normal and fault conditions are retained. Paired descriptive contrasts within each setting are also available in summary.json.

| Size | Depth, levels | Dependency setting | Arm | Condition | Task IDs | Outcomes | Logical calls | Logical tokens | Trial wall seconds |
| --- | ---: | --- | --- | --- | ---: | --- | --- | --- | --- |
| large | 3 | sparse | flat_retry | fault | 3 | 6/6; missing 0 | 3 [2, 4] (6/6) | 4.9e+04 [2.18e+04, 5.19e+04] (6/6) | 21.8 [5.68, 28.9] (6/6) |
| large | 3 | sparse | flat_retry | normal | 3 | 5/5; missing 1 | 1 [1, 3] (5/6) | 1.53e+04 [1.06e+04, 3.54e+04] (5/6) | 16.3 [4.28, 19.1] (5/6) |
| large | 3 | sparse | hierarchy_adaptive | fault | 3 | 0/0; missing 6 | — (0/6) | — (0/6) | — (0/6) |
| large | 3 | sparse | hierarchy_adaptive | normal | 3 | 0/0; missing 6 | — (0/6) | — (0/6) | — (0/6) |
| large | 3 | sparse | hierarchy_fixed | fault | 3 | 0/0; missing 6 | — (0/6) | — (0/6) | — (0/6) |
| large | 3 | sparse | hierarchy_fixed | normal | 3 | 0/0; missing 6 | — (0/6) | — (0/6) | — (0/6) |
| large | 5 | dense | flat_retry | fault | 3 | 5/5; missing 1 | 2 [2, 5] (5/6) | 4.26e+04 [3.12e+04, 8.71e+04] (5/6) | 23.7 [10, 31.8] (5/6) |
| large | 5 | dense | flat_retry | normal | 3 | 5/5; missing 1 | 1 [1, 4] (5/6) | 1.97e+04 [1.49e+04, 6.97e+04] (5/6) | 20.8 [8.01, 30.9] (5/6) |
| large | 5 | dense | hierarchy_adaptive | fault | 3 | 0/0; missing 6 | — (0/6) | — (0/6) | — (0/6) |
| large | 5 | dense | hierarchy_adaptive | normal | 3 | 0/0; missing 6 | — (0/6) | — (0/6) | — (0/6) |
| large | 5 | dense | hierarchy_fixed | fault | 3 | 0/0; missing 6 | — (0/6) | — (0/6) | — (0/6) |
| large | 5 | dense | hierarchy_fixed | normal | 3 | 0/0; missing 6 | — (0/6) | — (0/6) | — (0/6) |
| medium | 3 | sparse | flat_retry | fault | 3 | 4/4; missing 2 | 2.5 [2, 3] (4/6) | 1.86e+04 [1.79e+04, 1.97e+04] (4/6) | 13.1 [11.7, 13.7] (4/6) |
| medium | 3 | sparse | flat_retry | normal | 3 | 6/6; missing 0 | 1 [1, 2] (6/6) | 8.17e+03 [5.77e+03, 1.25e+04] (6/6) | 8.9 [2.81, 10.4] (6/6) |
| medium | 3 | sparse | hierarchy_adaptive | fault | 3 | 0/0; missing 6 | — (0/6) | — (0/6) | — (0/6) |
| medium | 3 | sparse | hierarchy_adaptive | normal | 3 | 0/0; missing 6 | — (0/6) | — (0/6) | — (0/6) |
| medium | 3 | sparse | hierarchy_fixed | fault | 3 | 0/0; missing 6 | — (0/6) | — (0/6) | — (0/6) |
| medium | 3 | sparse | hierarchy_fixed | normal | 3 | 0/0; missing 6 | — (0/6) | — (0/6) | — (0/6) |
| small | 3 | dense | flat_retry | fault | 3 | 5/5; missing 1 | 2 [2, 3] (5/6) | 7.52e+03 [7.1e+03, 1.62e+04] (5/6) | 7.64 [4, 12.4] (5/6) |
| small | 3 | dense | flat_retry | normal | 3 | 6/6; missing 0 | 1 [1, 1] (6/6) | 3.7e+03 [3.42e+03, 4.71e+03] (6/6) | 4.24 [2.46, 6.27] (6/6) |
| small | 3 | dense | hierarchy_adaptive | fault | 3 | 4/4; missing 2 | 10 [7, 23] (5/6) | 5.02e+04 [3.12e+04, 1.41e+05] (4/6) | 14.2 [13.1, 53] (5/6) |
| small | 3 | dense | hierarchy_adaptive | normal | 3 | 6/6; missing 0 | 9 [5, 17] (6/6) | 4.06e+04 [2.14e+04, 1.03e+05] (6/6) | 14.8 [6.87, 40.3] (6/6) |
| small | 3 | dense | hierarchy_fixed | fault | 3 | 5/5; missing 1 | 10 [6, 43] (5/6) | 4.54e+04 [2.65e+04, 3e+05] (5/6) | 12.1 [8.5, 169] (5/6) |
| small | 3 | dense | hierarchy_fixed | normal | 3 | 6/6; missing 0 | 9 [4, 19] (6/6) | 4.06e+04 [1.7e+04, 1.23e+05] (6/6) | 12.1 [9.31, 46.5] (6/6) |
| small | 3 | sparse | flat_retry | fault | 3 | 6/6; missing 0 | 2 [2, 3] (6/6) | 8.69e+03 [6.94e+03, 1.14e+04] (6/6) | 7.85 [3.84, 10.8] (6/6) |
| small | 3 | sparse | flat_retry | normal | 3 | 5/5; missing 1 | 1 [1, 2] (5/6) | 4.59e+03 [3.34e+03, 7.24e+03] (5/6) | 5.66 [2.06, 7.39] (5/6) |
| small | 3 | sparse | hierarchy_adaptive | fault | 3 | 6/6; missing 0 | 11 [7, 11] (6/6) | 4.74e+04 [3.08e+04, 6.58e+04] (6/6) | 18.7 [15.5, 25.5] (6/6) |
| small | 3 | sparse | hierarchy_adaptive | normal | 3 | 5/5; missing 1 | 9 [5, 9] (5/6) | 3.87e+04 [2.12e+04, 5.31e+04] (5/6) | 11 [8.27, 18.9] (5/6) |
| small | 3 | sparse | hierarchy_fixed | fault | 3 | 6/6; missing 0 | 10 [6, 10] (6/6) | 4.33e+04 [2.63e+04, 6.01e+04] (6/6) | 16 [12.8, 29.5] (6/6) |
| small | 3 | sparse | hierarchy_fixed | normal | 3 | 5/5; missing 1 | 9 [8, 9] (5/6) | 4.21e+04 [3.41e+04, 5.31e+04] (5/6) | 17.6 [9.77, 23] (5/6) |
| small | 4 | sparse | flat_retry | fault | 3 | 6/6; missing 0 | 2 [2, 2] (6/6) | 8.26e+03 [7.79e+03, 1.1e+04] (6/6) | 7.88 [3.75, 10] (6/6) |
| small | 4 | sparse | flat_retry | normal | 3 | 6/6; missing 0 | 1 [1, 1] (6/6) | 4.05e+03 [3.77e+03, 5.01e+03] (6/6) | 5.13 [2.3, 6.15] (6/6) |
| small | 4 | sparse | hierarchy_adaptive | fault | 3 | 6/6; missing 0 | 13 [9, 28] (6/6) | 6.5e+04 [4.52e+04, 1.93e+05] (6/6) | 18.2 [16.1, 73.2] (6/6) |
| small | 4 | sparse | hierarchy_adaptive | normal | 3 | 6/6; missing 0 | 11 [7, 25] (6/6) | 5.5e+04 [3.47e+04, 1.73e+05] (6/6) | 14.2 [10.6, 66.8] (6/6) |
| small | 4 | sparse | hierarchy_fixed | fault | 3 | 6/6; missing 0 | 12 [8, 23] (6/6) | 6.04e+04 [4.05e+04, 1.68e+05] (6/6) | 19.9 [11.8, 78.9] (6/6) |
| small | 4 | sparse | hierarchy_fixed | normal | 3 | 6/6; missing 0 | 11 [7, 26] (6/6) | 5.5e+04 [3.48e+04, 1.91e+05] (6/6) | 16.2 [11.9, 80] (6/6) |
| small | 5 | sparse | flat_retry | fault | 3 | 6/6; missing 0 | 2 [2, 3] (6/6) | 1.04e+04 [8.64e+03, 1.39e+04] (6/6) | 8.13 [4.41, 10.4] (6/6) |
| small | 5 | sparse | flat_retry | normal | 3 | 6/6; missing 0 | 1.5 [1, 3] (6/6) | 6.7e+03 [4.18e+03, 1.89e+04] (6/6) | 5.66 [2.7, 12.9] (6/6) |
| small | 5 | sparse | hierarchy_adaptive | fault | 3 | 6/6; missing 0 | 15 [11, 17] (6/6) | 8.58e+04 [6.15e+04, 1.23e+05] (6/6) | 27.6 [20.3, 39.1] (6/6) |
| small | 5 | sparse | hierarchy_adaptive | normal | 3 | 6/6; missing 0 | 13 [9, 19] (6/6) | 7.47e+04 [5e+04, 1.35e+05] (6/6) | 21.1 [13.4, 36.9] (6/6) |
| small | 5 | sparse | hierarchy_fixed | fault | 3 | 6/6; missing 0 | 14 [10, 14] (6/6) | 8.08e+04 [5.74e+04, 1.02e+05] (6/6) | 20.7 [16.6, 25.9] (6/6) |
| small | 5 | sparse | hierarchy_fixed | normal | 3 | 6/6; missing 0 | 13 [9, 14] (6/6) | 7.46e+04 [5.02e+04, 9.97e+04] (6/6) | 19.4 [13.7, 32] (6/6) |

- Requested depth counts levels including the root; measured max_depth_edges counts edges from root zero.
- Deeper scale fixtures add executable certification leaves. Depth is not varied at fixed leaf count or fixed work.
- The selected scale settings are not a full factorial design; marginal and interaction effects are not identified generally.
- Distinct scale settings generated from shared source instances need not be independent task draws. No scale CI or significance test is reported.


## Recorded per-trial costs

Cells show median [minimum, maximum] and measured/scheduled trial count. Missing token or timing measurements remain missing. Logical calls/tokens include cached shared planning charges per hierarchical trial and therefore do not equal provider billing. Recorded costs include failed and uncertain trials.

| Arm | Condition | Calls | Input tokens | Output tokens | Total tokens | Logical response seconds | Trial wall seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 2 [2, 5] (38/42) | 1.02e+04 [6.45e+03, 8.2e+04] (38/42) | 1.4e+03 [379, 5.08e+03] (38/42) | 1.16e+04 [6.94e+03, 8.71e+04] (38/42) | 9.9 [3.72, 31.7] (38/42) | 9.93 [3.75, 31.8] (38/42) |
| flat_retry | normal | 1 [1, 4] (39/42) | 5.37e+03 [3.07e+03, 6.55e+04] (39/42) | 977 [244, 5.16e+03] (39/42) | 5.77e+03 [3.34e+03, 6.97e+04] (39/42) | 5.94 [2.05, 30.8] (39/42) | 5.95 [2.06, 30.9] (39/42) |
| hierarchy_adaptive | fault | 11 [7, 28] (23/42) | 6.25e+04 [2.86e+04, 1.84e+05] (22/42) | 2.39e+03 [1.48e+03, 8.76e+03] (22/42) | 6.5e+04 [3.08e+04, 1.93e+05] (22/42) | 23.9 [15.3, 83.1] (23/42) | 20.3 [13.1, 73.2] (23/42) |
| hierarchy_adaptive | normal | 9 [5, 25] (23/42) | 5.07e+04 [1.98e+04, 1.65e+05] (23/42) | 1.6e+03 [1.14e+03, 8.07e+03] (23/42) | 5.31e+04 [2.12e+04, 1.73e+05] (23/42) | 18.3 [12.1, 76.8] (23/42) | 15.1 [6.87, 66.8] (23/42) |
| hierarchy_fixed | fault | 10 [6, 43] (23/42) | 5.72e+04 [2.46e+04, 2.81e+05] (23/42) | 1.9e+03 [1.25e+03, 1.93e+04] (23/42) | 6.01e+04 [2.63e+04, 3e+05] (23/42) | 22.1 [13.7, 177] (23/42) | 19.8 [8.5, 169] (23/42) |
| hierarchy_fixed | normal | 9 [4, 26] (23/42) | 5.07e+04 [1.55e+04, 1.81e+05] (23/42) | 1.7e+03 [1.15e+03, 1e+04] (23/42) | 5.31e+04 [1.7e+04, 1.91e+05] (23/42) | 21.4 [11.7, 89.9] (23/42) | 17.6 [9.31, 80] (23/42) |

Separately recorded actual provider usage (cached plan usage is charged only where recorded):

| Arm | Condition | Actual calls | Actual input tokens | Actual output tokens |
| --- | --- | --- | --- | --- |
| flat_retry | fault | 2 [2, 5] (38/42) | 1.02e+04 [6.45e+03, 8.2e+04] (38/42) | 1.4e+03 [379, 5.08e+03] (38/42) |
| flat_retry | normal | 1 [1, 4] (39/42) | 5.37e+03 [3.07e+03, 6.55e+04] (39/42) | 977 [244, 5.16e+03] (39/42) |
| hierarchy_adaptive | fault | 10 [6, 27] (23/42) | 5.91e+04 [2.58e+04, 1.81e+05] (22/42) | 1.59e+03 [1.06e+03, 7.2e+03] (22/42) |
| hierarchy_adaptive | normal | 9 [4, 24] (23/42) | 4.72e+04 [1.7e+04, 1.61e+05] (23/42) | 1.28e+03 [559, 6.5e+03] (23/42) |
| hierarchy_fixed | fault | 10 [5, 42] (23/42) | 5.72e+04 [2.22e+04, 2.77e+05] (23/42) | 1.71e+03 [748, 1.8e+04] (23/42) |
| hierarchy_fixed | normal | 8 [4, 25] (23/42) | 4.72e+04 [1.55e+04, 1.77e+05] (23/42) | 1.3e+03 [677, 8.48e+03] (23/42) |

Timing context: batch_size: 1; cpu: Intel(R) Xeon(R) 6975P-C; cpu_clock_mhz_observed_range: [2700.0, 3897.597]; git_commit: 8c45ba15293876d5ddb2a91bb7b60c333136219d; logical_cpus: 4; memory_bytes: 16464297984; model_hardware: Provider-managed; not observable; platform: Linux-7.0.0-1014-aws-x86_64-with-glibc2.39; python: 3.12.3; timestamp_utc: 2026-11-25T17:43:19.963691+00:00; working_tree_dirty: False Recorded durations are not a controlled hardware benchmark.

## Recovery diagnostics

Recovery is conditional on a delivered fault and is descriptive. Fault delivery is a post-assignment event, so these rates cannot establish a causal treatment contrast. Fault-assigned trials without delivery still remain in both primary comparisons.

| Arm | Fault assigned | Triggered | Delivered | Triggered, no impact | Untriggered | Trigger unknown | Delivery unknown | Recovered/known recovery outcomes | Recovery bounds among delivered |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| flat_retry | 42 | 38 | 38 | 0 | 0 | 4 | 4 | 38/38 | [1.000, 1.000] |
| hierarchy_adaptive | 42 | 23 | 23 | 0 | 0 | 19 | 19 | 22/22 | [0.957, 1.000] |
| hierarchy_fixed | 42 | 23 | 23 | 0 | 0 | 19 | 19 | 23/23 | [1.000, 1.000] |

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
