# HierGoal paired study analysis

**Prespecified exploratory benchmark decision: UNCERTAIN**  
Engineering invariant feasibility: **PASS**.  
Reason: `confirmatory_requirements_not_satisfied`.

Protocol: `2c7d8eca0b43e4dac8ee1cebc87414ee3f881741d5b8bbe21de5c45c954b2153`  
Declared backend/model: `openai` / `gpt-6-luna`; profile: `reliability`.

**Descriptive reliability profile. It does not alter the original 216-trial study efficacy rule; no inferential CI or p-value is derived from this profile. Finite acceptance criteria, where declared, are reported separately.**

## Coverage and validity

The schedule contains 720 trials in 240 paired blocks and 12 task clusters. Repeats and individual acceptance gates do not increase the number of task clusters.

| Scheduled | Supplied records | PASS | FAIL | UNCERTAIN | NOT_RUN | Missing outcomes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 720 | 720 | 717 | 3 | 0 | 0 | 0 |

Unrecorded scheduled trials: 0; these are included as NOT_RUN. Supplied records can include explicit NOT_RUN placeholders and do not imply execution. Record-consistency issues: 0. Benchmark decision eligible: no.

Benchmark decision blockers:

- `reliability_is_descriptive_only`

## Nine requirement evidence rules

These nine scoped evidence rules do not replace the frozen study's separate efficacy decision. Engineering PASS on simulated records is software validation only.

PASS applies only to the scope in its row. Engineering PASS can describe simulated software validation. Model-execution coverage remains UNCERTAIN without valid declared model records; it is not the benchmark efficacy decision. Missing or zero unrelated comparisons are UNCERTAIN. NOT_APPLICABLE is reserved for an operation outside the declared arm or condition.

| ID | Requirement | Scoped status | Engineering | Model-execution coverage | Scope |
| --- | --- | --- | --- | --- | --- |
| R1 | Forced failed subgoal and verified recovery | UNCERTAIN | UNCERTAIN | UNCERTAIN | Public-pass to forced domain-fail to an accepted revision of that failed target to independent final-pass, in at least one adaptive trace per family. |
| R2 | Hierarchy, state transitions, and before/after replans | PASS | PASS | PASS | Successfully replayed hierarchical checkpoints plus an exercised, failure-evidenced accepted replan. |
| R3 | Immutable root contract | PASS | PASS | PASS | Every scheduled trace was replayed and the root contract stayed identical in root-bearing state and request snapshots. |
| R4 | Task-family coverage and finite recovery applicability | PASS | PASS | PASS | Engineering status measures complete three-family coverage; the empirical rule requires each family's assigned adaptive forced-fault recovery proportion to meet the frozen threshold. |
| R5 | Unrelated goals and artifact fields preserved | PASS | PASS | PASS | Plan comparisons cover accepted adaptive revisions; artifact comparisons cover audited adaptive fault paths independently of whether a revision was accepted. Both comparison sets must be nonempty. |
| R6 | Failure-evidenced and bounded replanning | PASS | PASS | PASS | A replan request must have current failed-leaf evidence and authorization; attempted requests stay within the declared cap. |
| R7 | Independent final grading and replay | PASS | PASS | PASS | Audited final grades must match terminal claims; noncandidate budget failures need not call the hidden grader. |
| R8 | Scale coverage and finite resilience | UNCERTAIN | UNCERTAIN | UNCERTAIN | Engineering covers the varied observed trees; the separate finite live-data rule tests frozen per-setting success, paired stress drop, and observed locality thresholds. |
| R9 | Finite repeatability and scientific stability uncertainty | PASS | PASS | PASS | The frozen live reliability rule requires final acceptance in every normal cell and repeated forced domain failure, target revision, and final recovery in every fault cell. |

R8 and R9 scoped decisions concern only frozen finite benchmark thresholds on complete valid live records. General scaling-law, power, precision, and future-stability sufficiency remain UNCERTAIN even if a finite criterion passes. Per-criterion limitations and numerical evidence are retained in summary.json.

## Descriptive paired contrasts

Both normal and assigned-fault conditions are reported. The adaptive-minus-comparator difference is averaged within task and then equally across families. All assigned trials remain in their condition; the scale and reliability profiles do not create extra independent evidence by counting repetitions.

| Condition | Contrast | Task clusters | Observed/scheduled pairs | Difference | Missing-data worst/best bounds |
| --- | --- | ---: | ---: | ---: | --- |
| normal | adaptive_vs_fixed | 12 | 120/120 | 0.000 | [0.000, 0.000] |
| normal | adaptive_vs_flat_retry | 12 | 120/120 | 0.000 | [0.000, 0.000] |
| fault | adaptive_vs_fixed | 12 | 120/120 | 0.008 | [0.008, 0.008] |
| fault | adaptive_vs_flat_retry | 12 | 120/120 | -0.008 | [-0.008, -0.008] |

Missing-data bounds are identification bounds, not confidence intervals. Incomplete paired data have no complete-case point estimate. No CI or p-value is introduced for these descriptive contrasts. Frozen finite benchmark criteria are reported separately.

## Outcomes by family, arm, and condition

The observed rate excludes missing outcomes only in this explicitly labeled descriptive column. The bounds retain every scheduled trial; no missing outcome is silently scored as failure.

| Family | Arm | Condition | Scheduled | PASS | FAIL | UNCERTAIN | NOT_RUN | Observed successes/observed trials | Scheduled rate bounds |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| code_repair | flat_retry | fault | 40 | 40 | 0 | 0 | 0 | 40/40 | [1.000, 1.000] |
| code_repair | flat_retry | normal | 40 | 40 | 0 | 0 | 0 | 40/40 | [1.000, 1.000] |
| code_repair | hierarchy_adaptive | fault | 40 | 40 | 0 | 0 | 0 | 40/40 | [1.000, 1.000] |
| code_repair | hierarchy_adaptive | normal | 40 | 40 | 0 | 0 | 0 | 40/40 | [1.000, 1.000] |
| code_repair | hierarchy_fixed | fault | 40 | 39 | 1 | 0 | 0 | 39/40 | [0.975, 0.975] |
| code_repair | hierarchy_fixed | normal | 40 | 40 | 0 | 0 | 0 | 40/40 | [1.000, 1.000] |
| data_transform | flat_retry | fault | 40 | 40 | 0 | 0 | 0 | 40/40 | [1.000, 1.000] |
| data_transform | flat_retry | normal | 40 | 40 | 0 | 0 | 0 | 40/40 | [1.000, 1.000] |
| data_transform | hierarchy_adaptive | fault | 40 | 40 | 0 | 0 | 0 | 40/40 | [1.000, 1.000] |
| data_transform | hierarchy_adaptive | normal | 40 | 40 | 0 | 0 | 0 | 40/40 | [1.000, 1.000] |
| data_transform | hierarchy_fixed | fault | 40 | 39 | 1 | 0 | 0 | 39/40 | [0.975, 0.975] |
| data_transform | hierarchy_fixed | normal | 40 | 40 | 0 | 0 | 0 | 40/40 | [1.000, 1.000] |
| scheduling | flat_retry | fault | 40 | 40 | 0 | 0 | 0 | 40/40 | [1.000, 1.000] |
| scheduling | flat_retry | normal | 40 | 40 | 0 | 0 | 0 | 40/40 | [1.000, 1.000] |
| scheduling | hierarchy_adaptive | fault | 40 | 39 | 1 | 0 | 0 | 39/40 | [0.975, 0.975] |
| scheduling | hierarchy_adaptive | normal | 40 | 40 | 0 | 0 | 0 | 40/40 | [1.000, 1.000] |
| scheduling | hierarchy_fixed | fault | 40 | 40 | 0 | 0 | 0 | 40/40 | [1.000, 1.000] |
| scheduling | hierarchy_fixed | normal | 40 | 40 | 0 | 0 | 0 | 40/40 | [1.000, 1.000] |

## Replayed mechanism measurements

Tree cells show median [minimum, maximum] and measured/scheduled trials. Root depth is zero; goal count includes the root. A flat arm has no hierarchy, so its hierarchy measurements are NOT_APPLICABLE.

| Arm | Condition | Replayed/scheduled | Goal count | Leaves | Maximum depth, edges | Dependency edges | Dependency density |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| flat_retry | fault | 120/120 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| flat_retry | normal | 120/120 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| hierarchy_adaptive | fault | 120/120 | 11 [11, 11] (120/120) | 8 [8, 8] (120/120) | 2 [2, 2] (120/120) | 6 [6, 8] (120/120) | 0.214 [0.214, 0.286] (120/120) |
| hierarchy_adaptive | normal | 120/120 | 11 [11, 11] (120/120) | 8 [8, 8] (120/120) | 2 [2, 2] (120/120) | 6 [6, 8] (120/120) | 0.214 [0.214, 0.286] (120/120) |
| hierarchy_fixed | fault | 120/120 | 11 [11, 11] (120/120) | 8 [8, 8] (120/120) | 2 [2, 2] (120/120) | 6 [6, 8] (120/120) | 0.214 [0.214, 0.286] (120/120) |
| hierarchy_fixed | normal | 120/120 | 11 [11, 11] (120/120) | 8 [8, 8] (120/120) | 2 [2, 2] (120/120) | 6 [6, 8] (120/120) | 0.214 [0.214, 0.286] (120/120) |

Replan counters show known totals and measured/scheduled trials. Attempts count issued requests, including interrupted or over-budget requests. A missing counter is not zero. Operational necessity tests the recorded failed-leaf and progress rule; it does not prove optimality.

| Arm | Condition | Attempted | Accepted | Rejected | Unnecessary | Decision events | Deferred after progress |
| --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 0 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) | 390 (120/120) | 0 (120/120) |
| flat_retry | normal | 0 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) | 143 (120/120) | 0 (120/120) |
| hierarchy_adaptive | fault | 162 (120/120) | 160 (120/120) | 2 (120/120) | 0 (120/120) | 1091 (120/120) | 674 (120/120) |
| hierarchy_adaptive | normal | 29 (120/120) | 29 (120/120) | 0 (120/120) | 0 (120/120) | 823 (120/120) | 666 (120/120) |
| hierarchy_fixed | fault | 0 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) | 1092 (120/120) | 672 (120/120) |
| hierarchy_fixed | normal | 0 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) | 823 (120/120) | 663 (120/120) |

Locality uses nonempty comparisons of unrelated goals and separately of unrelated artifact fields during repair. Zero checked objects cannot establish locality. Dependency invalidations and fresh re-verifications are counts of evidence transitions.

| Arm | Condition | Unrelated goals checked | Goals unchanged | Artifact fields checked | Fields unchanged | Artifact violations | Invalidated goals | Reverified goals |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 0 (120/120) | 0 (120/120) | 420 (120/120) | 420 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) |
| flat_retry | normal | 0 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) |
| hierarchy_adaptive | fault | 640 (120/120) | 640 (120/120) | 412 (120/120) | 412 (120/120) | 0 (120/120) | 357 (120/120) | 357 (120/120) |
| hierarchy_adaptive | normal | 116 (120/120) | 116 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) |
| hierarchy_fixed | fault | 0 (120/120) | 0 (120/120) | 404 (120/120) | 404 (120/120) | 0 (120/120) | 354 (120/120) | 354 (120/120) |
| hierarchy_fixed | normal | 0 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) | 0 (120/120) |

R5 plan-locality evidence: PASS, 136/136 accepted-revision trials with nonempty comparisons. Artifact-locality evidence: PASS, 119/119 delivered-fault trials with nonempty comparisons. Artifact violations remain included when every replan response was rejected; plan and artifact denominators are separate.

Replayed hierarchical checkpoints: 4738; leaf state transitions: 5733; milestone state transitions: 1430; accepted replans with failure evidence: 189. Recorded host fault causes: 237; recorded model diagnoses: 189 (text provenance, not causal validation).

Root checked in 720/720 trials; explicit edit requests: 0; rejected edit requests: 0; actual root changes: 0. Record-verification issue trials: 0 (not assumed actual root mutations). A zero edit-attempt count leaves adversarial rejection unexercised in this run.

Final-grade disposition known in 720/720 trials: grader called 717, passed 717, failed 0, not reached 3. Audit failures: 0; grade/terminal-claim conflicts: 0.

## Repeated outcomes within task

Scheduled repeats per task/arm/condition range from 10 to 10. All-pass, mixed, and all-fail below partition only complete task records. Missing repeats remain explicit. These are observed patterns, not an independent-trial reliability estimate or a claim that the sample is sufficient.

| Arm | Condition | Task clusters | Complete clusters | All repeats PASS | Mixed complete outcomes | All repeats FAIL | Incomplete clusters |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| flat_retry | normal | 12 | 12 | 12 | 0 | 0 | 0 |
| flat_retry | fault | 12 | 12 | 12 | 0 | 0 | 0 |
| hierarchy_fixed | normal | 12 | 12 | 12 | 0 | 0 | 0 |
| hierarchy_fixed | fault | 12 | 12 | 10 | 2 | 0 | 0 |
| hierarchy_adaptive | normal | 12 | 12 | 12 | 0 | 0 | 0 |
| hierarchy_adaptive | fault | 12 | 12 | 11 | 1 | 0 | 0 |

Per-family/repeat cells show successful/observed trials, followed by the missing scheduled count. The same task IDs recur across repeats; the table does not create independent task samples.

| Family | Repeat | Flat normal | Flat fault | Fixed normal | Fixed fault | Adaptive normal | Adaptive fault |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| code_repair | 1 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| code_repair | 2 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| code_repair | 3 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| code_repair | 4 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| code_repair | 5 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| code_repair | 6 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| code_repair | 7 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| code_repair | 8 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| code_repair | 9 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| code_repair | 10 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 3/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| data_transform | 1 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| data_transform | 2 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| data_transform | 3 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 3/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| data_transform | 4 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| data_transform | 5 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| data_transform | 6 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| data_transform | 7 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| data_transform | 8 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| data_transform | 9 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| data_transform | 10 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| scheduling | 1 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| scheduling | 2 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 3/4; missing 0 |
| scheduling | 3 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| scheduling | 4 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| scheduling | 5 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| scheduling | 6 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| scheduling | 7 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| scheduling | 8 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| scheduling | 9 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| scheduling | 10 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |

Repeat sufficiency: **UNCERTAIN**. No population power, precision, or future-stability guarantee establishes that the repeat count is scientifically sufficient; a finite acceptance threshold is a separate claim.

## Finite task-family recovery applicability

**Scoped decision: PASS.** Engineering coverage remains separate. Each of the three families must reach recovery proportion 0.80 over at least 6 assigned adaptive forced-fault trials. Recovery requires a delivered domain failure, an accepted revision of that target, and independent final acceptance. These are finite suite criteria, not a generalization or sample-adequacy guarantee.

| Family | Successful recoveries/observed | Final acceptances | Assigned | Meets frozen minimum |
| --- | ---: | ---: | ---: | --- |
| code_repair | 37/40 | 40 | 40 | PASS |
| data_transform | 37/40 | 40 | 40 | PASS |
| scheduling | 39/40 | 39 | 40 | PASS |

## Finite repeatability benchmark

**Scoped decision: PASS.** This evaluates the recorded repetitions only; future stability and scientific sample sufficiency remain UNCERTAIN.

Every adaptive task/condition cell must meet success proportion 0.90 across exactly 10 scheduled repeats. All 12 task IDs and both conditions are retained; complete valid live outcomes and zero root/protocol violations are required.

Normal-condition successes mean independent final acceptance. Fault-condition successes mean the complete forced-domain-failure, accepted target-revision, final-recovery chain. Final artifact success alone does not count as mechanism recovery.

| Family | Task | Condition | Successes/observed | Scheduled | Meets frozen minimum |
| --- | --- | --- | ---: | ---: | --- |
| code_repair | scale-code_repair-heldout-000-small-d3-sparse-4d051506 | fault | 9/10 | 10 | PASS |
| code_repair | scale-code_repair-heldout-000-small-d3-sparse-4d051506 | normal | 10/10 | 10 | PASS |
| code_repair | scale-code_repair-heldout-001-small-d3-sparse-a19c83b0 | fault | 9/10 | 10 | PASS |
| code_repair | scale-code_repair-heldout-001-small-d3-sparse-a19c83b0 | normal | 10/10 | 10 | PASS |
| code_repair | scale-code_repair-heldout-002-small-d3-sparse-b0f5211c | fault | 10/10 | 10 | PASS |
| code_repair | scale-code_repair-heldout-002-small-d3-sparse-b0f5211c | normal | 10/10 | 10 | PASS |
| code_repair | scale-code_repair-heldout-003-small-d3-sparse-e87a05c3 | fault | 9/10 | 10 | PASS |
| code_repair | scale-code_repair-heldout-003-small-d3-sparse-e87a05c3 | normal | 10/10 | 10 | PASS |
| data_transform | scale-data_transform-heldout-000-small-d3-sparse-5a988b43 | fault | 9/10 | 10 | PASS |
| data_transform | scale-data_transform-heldout-000-small-d3-sparse-5a988b43 | normal | 10/10 | 10 | PASS |
| data_transform | scale-data_transform-heldout-001-small-d3-sparse-96ee4cc2 | fault | 10/10 | 10 | PASS |
| data_transform | scale-data_transform-heldout-001-small-d3-sparse-96ee4cc2 | normal | 10/10 | 10 | PASS |
| data_transform | scale-data_transform-heldout-002-small-d3-sparse-b587cfee | fault | 9/10 | 10 | PASS |
| data_transform | scale-data_transform-heldout-002-small-d3-sparse-b587cfee | normal | 10/10 | 10 | PASS |
| data_transform | scale-data_transform-heldout-003-small-d3-sparse-a6db55b6 | fault | 9/10 | 10 | PASS |
| data_transform | scale-data_transform-heldout-003-small-d3-sparse-a6db55b6 | normal | 10/10 | 10 | PASS |
| scheduling | scale-scheduling-heldout-000-small-d3-sparse-5fdae192 | fault | 10/10 | 10 | PASS |
| scheduling | scale-scheduling-heldout-000-small-d3-sparse-5fdae192 | normal | 10/10 | 10 | PASS |
| scheduling | scale-scheduling-heldout-001-small-d3-sparse-f3488644 | fault | 10/10 | 10 | PASS |
| scheduling | scale-scheduling-heldout-001-small-d3-sparse-f3488644 | normal | 10/10 | 10 | PASS |
| scheduling | scale-scheduling-heldout-002-small-d3-sparse-c58b60e9 | fault | 9/10 | 10 | PASS |
| scheduling | scale-scheduling-heldout-002-small-d3-sparse-c58b60e9 | normal | 10/10 | 10 | PASS |
| scheduling | scale-scheduling-heldout-003-small-d3-sparse-62fcf41d | fault | 10/10 | 10 | PASS |
| scheduling | scale-scheduling-heldout-003-small-d3-sparse-62fcf41d | normal | 10/10 | 10 | PASS |

Root/protocol violation trials: 0.

- The per-task threshold and repeat count are frozen design choices, not fitted to observed outcomes.
- Nine successes in ten scheduled repeats meet a finite descriptive criterion; they do not prove a 0.90 future success probability.
- All 24 task/condition cells must meet the criterion; missing outcomes are not replaced, discarded, or selectively rerun.
- No independence assumption, confidence interval, adequate-power claim, or general sample-sufficiency decision is introduced.
- Fault cells count final PASS only after a delivered forced domain failure and an accepted post-fault revision of that target. Normal cells count final acceptance.
- Final artifact success with zero target revisions counts as zero mechanism recoveries. Missing or invalid delivery/revision receipts prevent a positive decision.

## Scale coverage and descriptive outcomes

The schedule contains 1 scale settings and 12 distinct task IDs. Parameter levels and observed tree metrics are separate. Requested depth counts levels including the root; measured depth counts edges from root zero. Topology cells show median [minimum, maximum] and measured/scheduled hierarchical trials.

| Size | Requested depth, levels | Dependency setting | Task IDs | Goals | Leaves | Maximum depth, edges | Dependency edges | Dependency density |
| --- | ---: | --- | ---: | --- | --- | --- | --- | --- |
| small | 3 | sparse | 12 | 11 [11, 11] (480/480) | 8 [8, 8] (480/480) | 2 [2, 2] (480/480) | 6 [6, 8] (480/480) | 0.214 [0.214, 0.286] (480/480) |

Outcome cells show successes/observed trials plus missing scheduled trials. Cost cells show median [minimum, maximum] with measured/scheduled trials. Both normal and fault conditions are retained. Paired descriptive contrasts within each setting are also available in summary.json.

| Size | Depth, levels | Dependency setting | Arm | Condition | Task IDs | Outcomes | Logical calls | Logical tokens | Trial wall seconds |
| --- | ---: | --- | --- | --- | ---: | --- | --- | --- | --- |
| small | 3 | sparse | flat_retry | fault | 12 | 120/120; missing 0 | 2 [2, 4] (120/120) | 9.98e+03 [6.88e+03, 1.74e+04] (120/120) | 8.07 [3.16, 17.8] (120/120) |
| small | 3 | sparse | flat_retry | normal | 12 | 120/120; missing 0 | 1 [1, 3] (120/120) | 3.72e+03 [3.34e+03, 1.17e+04] (120/120) | 4.56 [1.83, 14] (120/120) |
| small | 3 | sparse | hierarchy_adaptive | fault | 12 | 119/120; missing 0 | 11 [4, 24] (120/120) | 4.79e+04 [2.39e+04, 1.29e+05] (120/120) | 18.8 [9.95, 101] (120/120) |
| small | 3 | sparse | hierarchy_adaptive | normal | 12 | 120/120; missing 0 | 9 [2, 24] (120/120) | 3.89e+04 [1.09e+04, 1.09e+05] (120/120) | 13.4 [4.77, 49.5] (120/120) |
| small | 3 | sparse | hierarchy_fixed | fault | 12 | 118/120; missing 0 | 10 [3, 24] (120/120) | 4.37e+04 [1.78e+04, 1.33e+05] (120/120) | 15.9 [7.31, 68.1] (120/120) |
| small | 3 | sparse | hierarchy_fixed | normal | 12 | 120/120; missing 0 | 9 [2, 16] (120/120) | 3.89e+04 [1.13e+04, 1.07e+05] (120/120) | 12.6 [4.74, 51.7] (120/120) |

- Requested depth counts levels including the root; measured max_depth_edges counts edges from root zero.
- Deeper scale fixtures add executable certification leaves. Depth is not varied at fixed leaf count or fixed work.
- The selected scale settings are not a full factorial design; marginal and interaction effects are not identified generally.
- Distinct scale settings generated from shared source instances need not be independent task draws. No scale CI or significance test is reported.


## Recorded per-trial costs

Cells show median [minimum, maximum] and measured/scheduled trial count. Missing token or timing measurements remain missing. Logical calls/tokens include cached shared planning charges per hierarchical trial and therefore do not equal provider billing. Recorded costs include failed and uncertain trials.

| Arm | Condition | Calls | Input tokens | Output tokens | Total tokens | Logical response seconds | Trial wall seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 2 [2, 4] (120/120) | 8.66e+03 [6.44e+03, 1.47e+04] (120/120) | 1.13e+03 [325, 2.71e+03] (120/120) | 9.98e+03 [6.88e+03, 1.74e+04] (120/120) | 8.05 [3.13, 17.7] (120/120) | 8.07 [3.16, 17.8] (120/120) |
| flat_retry | normal | 1 [1, 3] (120/120) | 3.1e+03 [3.03e+03, 1.02e+04] (120/120) | 686 [244, 2.2e+03] (120/120) | 3.72e+03 [3.34e+03, 1.17e+04] (120/120) | 4.55 [1.82, 14] (120/120) | 4.56 [1.83, 14] (120/120) |
| hierarchy_adaptive | fault | 11 [4, 24] (120/120) | 4.64e+04 [2.08e+04, 1.15e+05] (120/120) | 2.53e+03 [1.22e+03, 1.35e+04] (120/120) | 4.79e+04 [2.39e+04, 1.29e+05] (120/120) | 22.2 [15.5, 107] (120/120) | 18.8 [9.95, 101] (120/120) |
| hierarchy_adaptive | normal | 9 [2, 24] (120/120) | 3.79e+04 [8.77e+03, 1.04e+05] (120/120) | 1.81e+03 [943, 4.96e+03] (120/120) | 3.89e+04 [1.09e+04, 1.09e+05] (120/120) | 16.1 [10.7, 52.6] (120/120) | 13.4 [4.77, 49.5] (120/120) |
| hierarchy_fixed | fault | 10 [3, 24] (120/120) | 4.25e+04 [1.55e+04, 1.24e+05] (120/120) | 2e+03 [1.05e+03, 9.16e+03] (120/120) | 4.37e+04 [1.78e+04, 1.33e+05] (120/120) | 17.3 [13.2, 74.3] (120/120) | 15.9 [7.31, 68.1] (120/120) |
| hierarchy_fixed | normal | 9 [2, 16] (120/120) | 3.78e+04 [8.91e+03, 1.01e+05] (120/120) | 1.81e+03 [950, 6.06e+03] (120/120) | 3.89e+04 [1.13e+04, 1.07e+05] (120/120) | 15.9 [10.9, 51.6] (120/120) | 12.6 [4.74, 51.7] (120/120) |

Separately recorded actual provider usage (cached plan usage is charged only where recorded):

| Arm | Condition | Actual calls | Actual input tokens | Actual output tokens |
| --- | --- | --- | --- | --- |
| flat_retry | fault | 2 [2, 4] (120/120) | 8.66e+03 [6.44e+03, 1.47e+04] (120/120) | 1.13e+03 [325, 2.71e+03] (120/120) |
| flat_retry | normal | 1 [1, 3] (120/120) | 3.1e+03 [3.03e+03, 1.02e+04] (120/120) | 686 [244, 2.2e+03] (120/120) |
| hierarchy_adaptive | fault | 10 [3, 23] (120/120) | 4.41e+04 [1.73e+04, 1.12e+05] (120/120) | 1.99e+03 [874, 1.25e+04] (120/120) |
| hierarchy_adaptive | normal | 8 [1, 23] (120/120) | 3.51e+04 [5.26e+03, 1.01e+05] (120/120) | 1.29e+03 [506, 4.52e+03] (120/120) |
| hierarchy_fixed | fault | 9 [3, 23] (120/120) | 4.03e+04 [1.27e+04, 1.2e+05] (120/120) | 1.49e+03 [623, 7.74e+03] (120/120) |
| hierarchy_fixed | normal | 8 [1, 16] (120/120) | 3.5e+04 [5.42e+03, 1.01e+05] (120/120) | 1.08e+03 [493, 6.06e+03] (120/120) |

Timing context: batch_size: 1; cpu: Intel(R) Xeon(R) 6975P-C; cpu_clock_mhz_observed_range: [2700.0, 3901.452]; git_commit: 983bf8c14e22eda6adea5b58113679b69ff0204a; logical_cpus: 4; memory_bytes: 16464289792; model_hardware: Provider-managed; not observable; platform: Linux-7.0.0-1014-aws-x86_64-with-glibc2.39; python: 3.12.3; timestamp_utc: 2026-11-26T01:02:23.917213+00:00; working_tree_dirty: False Recorded durations are not a controlled hardware benchmark.

## Recovery diagnostics

Recovery is conditional on a delivered fault and is descriptive. Fault delivery is a post-assignment event, so these rates cannot establish a causal treatment contrast. Fault-assigned trials without delivery still remain in both primary comparisons.

| Arm | Fault assigned | Triggered | Delivered | Triggered, no impact | Untriggered | Trigger unknown | Delivery unknown | Recovered/known recovery outcomes | Recovery bounds among delivered |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| flat_retry | 120 | 120 | 120 | 0 | 0 | 0 | 0 | 120/120 | [1.000, 1.000] |
| hierarchy_adaptive | 120 | 119 | 119 | 0 | 1 | 0 | 0 | 119/119 | [1.000, 1.000] |
| hierarchy_fixed | 120 | 118 | 118 | 0 | 2 | 0 | 0 | 118/118 | [1.000, 1.000] |

## Interpretation and limits

- The reliability profile is descriptive only. It does not inherit or relax the frozen 216-trial study decision, and no inferential CI or p-value is assigned to its paired contrasts.
- The manifest defines assignment; fault delivery and recovery never select the primary analysis set (intention to treat).
- PASS is full trial acceptance and FAIL is zero; UNCERTAIN and NOT_RUN are missing, not assumed failures. No incomplete contrast receives a complete-case confirmatory CI or p-value.
- Repeated calls, repeats, and individual gates are not independent task samples. Repeats are averaged within each task and the bootstrap resamples tasks within family.
- This schedule has 12 task clusters (code_repair: 4, data_transform: 4, scheduling: 4). Percentile bootstrap coverage, when reported, is approximate; intervals may be unstable or degenerate and do not establish adequate power. The original study design remains 12 task clusters (4 per family).
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
