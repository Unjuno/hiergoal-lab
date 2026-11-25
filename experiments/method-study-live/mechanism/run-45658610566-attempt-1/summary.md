# HierGoal paired study analysis

**Prespecified exploratory benchmark decision: UNCERTAIN**  
Engineering invariant feasibility: **PASS**.  
Reason: `confirmatory_requirements_not_satisfied`.

Protocol: `d9b261c1036a9a24af0cb091f5ad1933a227bd31a465dde2d03011ae5f9fca0b`  
Declared backend/model: `openai` / `gpt-6-luna`; profile: `mechanism`.

**Descriptive mechanism profile. It does not alter the original 216-trial study efficacy rule; no inferential CI or p-value is derived from this profile. Finite acceptance criteria, where declared, are reported separately.**

## Coverage and validity

The schedule contains 108 trials in 36 paired blocks and 6 task clusters. Repeats and individual acceptance gates do not increase the number of task clusters.

| Scheduled | Supplied records | PASS | FAIL | UNCERTAIN | NOT_RUN | Missing outcomes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 108 | 108 | 98 | 10 | 0 | 0 | 0 |

Unrecorded scheduled trials: 0; these are included as NOT_RUN. Supplied records can include explicit NOT_RUN placeholders and do not imply execution. Record-consistency issues: 0. Benchmark decision eligible: no.

Benchmark decision blockers:

- `mechanism_is_descriptive_only`

## Nine requirement evidence rules

These nine scoped evidence rules do not replace the frozen study's separate efficacy decision. Engineering PASS on simulated records is software validation only.

PASS applies only to the scope in its row. Engineering PASS can describe simulated software validation. Model-execution coverage remains UNCERTAIN without valid declared model records; it is not the benchmark efficacy decision. Missing or zero unrelated comparisons are UNCERTAIN. NOT_APPLICABLE is reserved for an operation outside the declared arm or condition.

| ID | Requirement | Scoped status | Engineering | Model-execution coverage | Scope |
| --- | --- | --- | --- | --- | --- |
| R1 | Forced failed subgoal and verified recovery | UNCERTAIN | UNCERTAIN | UNCERTAIN | Public-pass to forced domain-fail to an accepted revision of that failed target to independent final-pass, in at least one adaptive trace per family. |
| R2 | Hierarchy, state transitions, and before/after replans | UNCERTAIN | UNCERTAIN | UNCERTAIN | Successfully replayed hierarchical checkpoints plus an exercised, failure-evidenced accepted replan. |
| R3 | Immutable root contract | PASS | PASS | PASS | Every scheduled trace was replayed and the root contract stayed identical in root-bearing state and request snapshots. |
| R4 | Task-family coverage and finite recovery applicability | FAIL | PASS | FAIL | Engineering status measures complete three-family coverage; the empirical rule requires each family's assigned adaptive forced-fault recovery proportion to meet the frozen threshold. |
| R5 | Unrelated goals and artifact fields preserved | PASS | PASS | PASS | Plan comparisons cover accepted adaptive revisions; artifact comparisons cover audited adaptive fault paths independently of whether a revision was accepted. Both comparison sets must be nonempty. |
| R6 | Failure-evidenced and bounded replanning | PASS | PASS | PASS | A replan request must have current failed-leaf evidence and authorization; attempted requests stay within the declared cap. |
| R7 | Independent final grading and replay | PASS | PASS | PASS | Audited final grades must match terminal claims; noncandidate budget failures need not call the hidden grader. |
| R8 | Scale coverage and finite resilience | UNCERTAIN | UNCERTAIN | UNCERTAIN | Engineering covers the varied observed trees; the separate finite live-data rule tests frozen per-setting success, paired stress drop, and observed locality thresholds. |
| R9 | Finite repeatability and scientific stability uncertainty | UNCERTAIN | PASS | UNCERTAIN | The frozen live reliability rule requires final acceptance in every normal cell and repeated forced domain failure, target revision, and final recovery in every fault cell. |

R8 and R9 scoped decisions concern only frozen finite benchmark thresholds on complete valid live records. General scaling-law, power, precision, and future-stability sufficiency remain UNCERTAIN even if a finite criterion passes. Per-criterion limitations and numerical evidence are retained in summary.json.

## Descriptive paired contrasts

Both normal and assigned-fault conditions are reported. The adaptive-minus-comparator difference is averaged within task and then equally across families. All assigned trials remain in their condition; the scale and reliability profiles do not create extra independent evidence by counting repetitions.

| Condition | Contrast | Task clusters | Observed/scheduled pairs | Difference | Missing-data worst/best bounds |
| --- | --- | ---: | ---: | ---: | --- |
| normal | adaptive_vs_fixed | 6 | 18/18 | 0.056 | [0.056, 0.056] |
| normal | adaptive_vs_flat_retry | 6 | 18/18 | -0.111 | [-0.111, -0.111] |
| fault | adaptive_vs_fixed | 6 | 18/18 | 0.056 | [0.056, 0.056] |
| fault | adaptive_vs_flat_retry | 6 | 18/18 | -0.111 | [-0.111, -0.111] |

Missing-data bounds are identification bounds, not confidence intervals. Incomplete paired data have no complete-case point estimate. No CI or p-value is introduced for these descriptive contrasts. Frozen finite benchmark criteria are reported separately.

## Outcomes by family, arm, and condition

The observed rate excludes missing outcomes only in this explicitly labeled descriptive column. The bounds retain every scheduled trial; no missing outcome is silently scored as failure.

| Family | Arm | Condition | Scheduled | PASS | FAIL | UNCERTAIN | NOT_RUN | Observed successes/observed trials | Scheduled rate bounds |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| code_repair | flat_retry | fault | 6 | 6 | 0 | 0 | 0 | 6/6 | [1.000, 1.000] |
| code_repair | flat_retry | normal | 6 | 6 | 0 | 0 | 0 | 6/6 | [1.000, 1.000] |
| code_repair | hierarchy_adaptive | fault | 6 | 6 | 0 | 0 | 0 | 6/6 | [1.000, 1.000] |
| code_repair | hierarchy_adaptive | normal | 6 | 6 | 0 | 0 | 0 | 6/6 | [1.000, 1.000] |
| code_repair | hierarchy_fixed | fault | 6 | 6 | 0 | 0 | 0 | 6/6 | [1.000, 1.000] |
| code_repair | hierarchy_fixed | normal | 6 | 6 | 0 | 0 | 0 | 6/6 | [1.000, 1.000] |
| data_transform | flat_retry | fault | 6 | 6 | 0 | 0 | 0 | 6/6 | [1.000, 1.000] |
| data_transform | flat_retry | normal | 6 | 6 | 0 | 0 | 0 | 6/6 | [1.000, 1.000] |
| data_transform | hierarchy_adaptive | fault | 6 | 4 | 2 | 0 | 0 | 4/6 | [0.667, 0.667] |
| data_transform | hierarchy_adaptive | normal | 6 | 4 | 2 | 0 | 0 | 4/6 | [0.667, 0.667] |
| data_transform | hierarchy_fixed | fault | 6 | 3 | 3 | 0 | 0 | 3/6 | [0.500, 0.500] |
| data_transform | hierarchy_fixed | normal | 6 | 3 | 3 | 0 | 0 | 3/6 | [0.500, 0.500] |
| scheduling | flat_retry | fault | 6 | 6 | 0 | 0 | 0 | 6/6 | [1.000, 1.000] |
| scheduling | flat_retry | normal | 6 | 6 | 0 | 0 | 0 | 6/6 | [1.000, 1.000] |
| scheduling | hierarchy_adaptive | fault | 6 | 6 | 0 | 0 | 0 | 6/6 | [1.000, 1.000] |
| scheduling | hierarchy_adaptive | normal | 6 | 6 | 0 | 0 | 0 | 6/6 | [1.000, 1.000] |
| scheduling | hierarchy_fixed | fault | 6 | 6 | 0 | 0 | 0 | 6/6 | [1.000, 1.000] |
| scheduling | hierarchy_fixed | normal | 6 | 6 | 0 | 0 | 0 | 6/6 | [1.000, 1.000] |

## Replayed mechanism measurements

Tree cells show median [minimum, maximum] and measured/scheduled trials. Root depth is zero; goal count includes the root. A flat arm has no hierarchy, so its hierarchy measurements are NOT_APPLICABLE.

| Arm | Condition | Replayed/scheduled | Goal count | Leaves | Maximum depth, edges | Dependency edges | Dependency density |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| flat_retry | fault | 18/18 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| flat_retry | normal | 18/18 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| hierarchy_adaptive | fault | 18/18 | 11 [1, 11] (18/18) | 8 [0, 8] (18/18) | 2 [0, 2] (18/18) | 6 [0, 8] (18/18) | 0.214 [0, 0.286] (18/18) |
| hierarchy_adaptive | normal | 18/18 | 11 [1, 11] (18/18) | 8 [0, 8] (18/18) | 2 [0, 2] (18/18) | 6 [0, 8] (18/18) | 0.214 [0, 0.286] (18/18) |
| hierarchy_fixed | fault | 18/18 | 11 [1, 11] (18/18) | 8 [0, 8] (18/18) | 2 [0, 2] (18/18) | 6 [0, 8] (18/18) | 0.214 [0, 0.286] (18/18) |
| hierarchy_fixed | normal | 18/18 | 11 [1, 11] (18/18) | 8 [0, 8] (18/18) | 2 [0, 2] (18/18) | 6 [0, 8] (18/18) | 0.214 [0, 0.286] (18/18) |

Replan counters show known totals and measured/scheduled trials. Attempts count issued requests, including interrupted or over-budget requests. A missing counter is not zero. Operational necessity tests the recorded failed-leaf and progress rule; it does not prove optimality.

| Arm | Condition | Attempted | Accepted | Rejected | Unnecessary | Decision events | Deferred after progress |
| --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 0 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) | 54 (18/18) | 0 (18/18) |
| flat_retry | normal | 0 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) | 20 (18/18) | 0 (18/18) |
| hierarchy_adaptive | fault | 33 (18/18) | 33 (18/18) | 0 (18/18) | 0 (18/18) | 164 (18/18) | 90 (18/18) |
| hierarchy_adaptive | normal | 17 (18/18) | 17 (18/18) | 0 (18/18) | 0 (18/18) | 130 (18/18) | 87 (18/18) |
| hierarchy_fixed | fault | 0 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) | 159 (18/18) | 82 (18/18) |
| hierarchy_fixed | normal | 0 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) | 136 (18/18) | 88 (18/18) |

Locality uses nonempty comparisons of unrelated goals and separately of unrelated artifact fields during repair. Zero checked objects cannot establish locality. Dependency invalidations and fresh re-verifications are counts of evidence transitions.

| Arm | Condition | Unrelated goals checked | Goals unchanged | Artifact fields checked | Fields unchanged | Artifact violations | Invalidated goals | Reverified goals |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 0 (18/18) | 0 (18/18) | 60 (18/18) | 60 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) |
| flat_retry | normal | 0 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) |
| hierarchy_adaptive | fault | 132 (18/18) | 132 (18/18) | 52 (18/18) | 52 (18/18) | 0 (18/18) | 48 (18/18) | 48 (18/18) |
| hierarchy_adaptive | normal | 68 (18/18) | 68 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) |
| hierarchy_fixed | fault | 0 (18/18) | 0 (18/18) | 48 (18/18) | 48 (18/18) | 0 (18/18) | 45 (18/18) | 45 (18/18) |
| hierarchy_fixed | normal | 0 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) | 0 (18/18) |

R5 plan-locality evidence: PASS, 21/21 accepted-revision trials with nonempty comparisons. Artifact-locality evidence: PASS, 16/16 delivered-fault trials with nonempty comparisons. Artifact violations remain included when every replan response was rejected; plan and artifact denominators are separate.

Replayed hierarchical checkpoints: 734; leaf state transitions: 759; milestone state transitions: 188; accepted replans with failure evidence: 50. Recorded host fault causes: 31; recorded model diagnoses: 50 (text provenance, not causal validation).

Root checked in 108/108 trials; explicit edit requests: 0; rejected edit requests: 0; actual root changes: 0. Record-verification issue trials: 0 (not assumed actual root mutations). A zero edit-attempt count leaves adversarial rejection unexercised in this run.

Final-grade disposition known in 108/108 trials: grader called 98, passed 98, failed 0, not reached 10. Audit failures: 0; grade/terminal-claim conflicts: 0.

## Repeated outcomes within task

Scheduled repeats per task/arm/condition range from 3 to 3. All-pass, mixed, and all-fail below partition only complete task records. Missing repeats remain explicit. These are observed patterns, not an independent-trial reliability estimate or a claim that the sample is sufficient.

| Arm | Condition | Task clusters | Complete clusters | All repeats PASS | Mixed complete outcomes | All repeats FAIL | Incomplete clusters |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| flat_retry | normal | 6 | 6 | 6 | 0 | 0 | 0 |
| flat_retry | fault | 6 | 6 | 6 | 0 | 0 | 0 |
| hierarchy_fixed | normal | 6 | 6 | 4 | 2 | 0 | 0 |
| hierarchy_fixed | fault | 6 | 6 | 4 | 2 | 0 | 0 |
| hierarchy_adaptive | normal | 6 | 6 | 4 | 2 | 0 | 0 |
| hierarchy_adaptive | fault | 6 | 6 | 4 | 2 | 0 | 0 |

Per-family/repeat cells show successful/observed trials, followed by the missing scheduled count. The same task IDs recur across repeats; the table does not create independent task samples.

| Family | Repeat | Flat normal | Flat fault | Fixed normal | Fixed fault | Adaptive normal | Adaptive fault |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| code_repair | 1 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 |
| code_repair | 2 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 |
| code_repair | 3 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 |
| data_transform | 1 | 2/2; missing 0 | 2/2; missing 0 | 1/2; missing 0 | 1/2; missing 0 | 1/2; missing 0 | 1/2; missing 0 |
| data_transform | 2 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 |
| data_transform | 3 | 2/2; missing 0 | 2/2; missing 0 | 0/2; missing 0 | 0/2; missing 0 | 1/2; missing 0 | 1/2; missing 0 |
| scheduling | 1 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 |
| scheduling | 2 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 |
| scheduling | 3 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 | 2/2; missing 0 |

Repeat sufficiency: **UNCERTAIN**. No population power, precision, or future-stability guarantee establishes that the repeat count is scientifically sufficient; a finite acceptance threshold is a separate claim.

## Finite task-family recovery applicability

**Scoped decision: FAIL.** Engineering coverage remains separate. Each of the three families must reach recovery proportion 0.80 over at least 6 assigned adaptive forced-fault trials. Recovery requires a delivered domain failure, an accepted revision of that target, and independent final acceptance. These are finite suite criteria, not a generalization or sample-adequacy guarantee.

| Family | Successful recoveries/observed | Final acceptances | Assigned | Meets frozen minimum |
| --- | ---: | ---: | ---: | --- |
| code_repair | 4/6 | 6 | 6 | FAIL |
| data_transform | 3/6 | 4 | 6 | FAIL |
| scheduling | 6/6 | 6 | 6 | PASS |

## Scale coverage and descriptive outcomes

The schedule contains 1 scale settings and 6 distinct task IDs. Parameter levels and observed tree metrics are separate. Requested depth counts levels including the root; measured depth counts edges from root zero. Topology cells show median [minimum, maximum] and measured/scheduled hierarchical trials.

| Size | Requested depth, levels | Dependency setting | Task IDs | Goals | Leaves | Maximum depth, edges | Dependency edges | Dependency density |
| --- | ---: | --- | ---: | --- | --- | --- | --- | --- |
| small | 3 | sparse | 6 | 11 [1, 11] (72/72) | 8 [0, 8] (72/72) | 2 [0, 2] (72/72) | 6 [0, 8] (72/72) | 0.214 [0, 0.286] (72/72) |

Outcome cells show successes/observed trials plus missing scheduled trials. Cost cells show median [minimum, maximum] with measured/scheduled trials. Both normal and fault conditions are retained. Paired descriptive contrasts within each setting are also available in summary.json.

| Size | Depth, levels | Dependency setting | Arm | Condition | Task IDs | Outcomes | Logical calls | Logical tokens | Trial wall seconds |
| --- | ---: | --- | --- | --- | ---: | --- | --- | --- | --- |
| small | 3 | sparse | flat_retry | fault | 6 | 18/18; missing 0 | 2 [2, 2] (18/18) | 7.46e+03 [6.9e+03, 1.02e+04] (18/18) | 7.84 [3.82, 10.1] (18/18) |
| small | 3 | sparse | flat_retry | normal | 6 | 18/18; missing 0 | 1 [1, 2] (18/18) | 3.67e+03 [3.34e+03, 7.94e+03] (18/18) | 4.8 [2.18, 10.2] (18/18) |
| small | 3 | sparse | hierarchy_adaptive | fault | 6 | 16/18; missing 0 | 11 [1, 22] (18/18) | 4.74e+04 [5.09e+03, 1.12e+05] (18/18) | 21.7 [11.3, 55.3] (18/18) |
| small | 3 | sparse | hierarchy_adaptive | normal | 6 | 16/18; missing 0 | 8.5 [1, 23] (18/18) | 3.87e+04 [5.09e+03, 1.11e+05] (18/18) | 12.9 [0.0028, 69.1] (18/18) |
| small | 3 | sparse | hierarchy_fixed | fault | 6 | 15/18; missing 0 | 9 [1, 20] (18/18) | 4.32e+04 [5.09e+03, 1.31e+05] (18/18) | 18.6 [0.00283, 53.4] (18/18) |
| small | 3 | sparse | hierarchy_fixed | normal | 6 | 15/18; missing 0 | 8.5 [1, 20] (18/18) | 3.87e+04 [5.09e+03, 1.32e+05] (18/18) | 13.6 [0.00275, 56.9] (18/18) |

- Requested depth counts levels including the root; measured max_depth_edges counts edges from root zero.
- Deeper scale fixtures add executable certification leaves. Depth is not varied at fixed leaf count or fixed work.
- The selected scale settings are not a full factorial design; marginal and interaction effects are not identified generally.
- Distinct scale settings generated from shared source instances need not be independent task draws. No scale CI or significance test is reported.


## Recorded per-trial costs

Cells show median [minimum, maximum] and measured/scheduled trial count. Missing token or timing measurements remain missing. Logical calls/tokens include cached shared planning charges per hierarchical trial and therefore do not equal provider billing. Recorded costs include failed and uncertain trials.

| Arm | Condition | Calls | Input tokens | Output tokens | Total tokens | Logical response seconds | Trial wall seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 2 [2, 2] (18/18) | 6.57e+03 [6.44e+03, 8.7e+03] (18/18) | 1.01e+03 [349, 1.49e+03] (18/18) | 7.46e+03 [6.9e+03, 1.02e+04] (18/18) | 7.82 [3.8, 10.1] (18/18) | 7.84 [3.82, 10.1] (18/18) |
| flat_retry | normal | 1 [1, 2] (18/18) | 3.1e+03 [3.03e+03, 6.48e+03] (18/18) | 638 [243, 1.46e+03] (18/18) | 3.67e+03 [3.34e+03, 7.94e+03] (18/18) | 4.79 [2.17, 10.2] (18/18) | 4.8 [2.18, 10.2] (18/18) |
| hierarchy_adaptive | fault | 11 [1, 22] (18/18) | 4.6e+04 [3.5e+03, 1.07e+05] (18/18) | 2.75e+03 [1.36e+03, 4.81e+03] (18/18) | 4.74e+04 [5.09e+03, 1.12e+05] (18/18) | 27.2 [11.3, 55.1] (18/18) | 21.7 [11.3, 55.3] (18/18) |
| hierarchy_adaptive | normal | 8.5 [1, 23] (18/18) | 3.76e+04 [3.5e+03, 1.06e+05] (18/18) | 1.89e+03 [1.11e+03, 6.74e+03] (18/18) | 3.87e+04 [5.09e+03, 1.11e+05] (18/18) | 17.3 [11.3, 68.9] (18/18) | 12.9 [0.0028, 69.1] (18/18) |
| hierarchy_fixed | fault | 9 [1, 20] (18/18) | 4.08e+04 [3.5e+03, 1.25e+05] (18/18) | 2.3e+03 [822, 6.37e+03] (18/18) | 4.32e+04 [5.09e+03, 1.31e+05] (18/18) | 23.7 [7.1, 63] (18/18) | 18.6 [0.00283, 53.4] (18/18) |
| hierarchy_fixed | normal | 8.5 [1, 20] (18/18) | 3.75e+04 [3.5e+03, 1.24e+05] (18/18) | 2.16e+03 [1.15e+03, 7.18e+03] (18/18) | 3.87e+04 [5.09e+03, 1.32e+05] (18/18) | 18.7 [11.3, 66.5] (18/18) | 13.6 [0.00275, 56.9] (18/18) |

Separately recorded actual provider usage (cached plan usage is charged only where recorded):

| Arm | Condition | Actual calls | Actual input tokens | Actual output tokens |
| --- | --- | --- | --- | --- |
| flat_retry | fault | 2 [2, 2] (18/18) | 6.57e+03 [6.44e+03, 8.7e+03] (18/18) | 1.01e+03 [349, 1.49e+03] (18/18) |
| flat_retry | normal | 1 [1, 2] (18/18) | 3.1e+03 [3.03e+03, 6.48e+03] (18/18) | 638 [243, 1.46e+03] (18/18) |
| hierarchy_adaptive | fault | 10 [1, 22] (18/18) | 4.45e+04 [3.5e+03, 1.07e+05] (18/18) | 2.2e+03 [978, 4.81e+03] (18/18) |
| hierarchy_adaptive | normal | 7.5 [0, 23] (18/18) | 3.46e+04 [0, 1.02e+05] (18/18) | 1.13e+03 [0, 6.74e+03] (18/18) |
| hierarchy_fixed | fault | 8.5 [0, 19] (18/18) | 3.79e+04 [0, 1.21e+05] (18/18) | 1.75e+03 [0, 4.91e+03] (18/18) |
| hierarchy_fixed | normal | 7.5 [0, 19] (18/18) | 3.61e+04 [0, 1.21e+05] (18/18) | 1.31e+03 [0, 5.73e+03] (18/18) |

Timing context: batch_size: 1; cpu: INTEL(R) XEON(R) PLATINUM 8573C; cpu_clock_mhz_observed_range: [800.0, 3600.756]; git_commit: 46df073625e33c12a63bf99bc8e975a351883628; logical_cpus: 4; memory_bytes: 16759275520; model_hardware: Provider-managed; not observable; platform: Linux-7.0.0-1020-azure-x86_64-with-glibc2.39; python: 3.12.3; timestamp_utc: 2026-11-25T16:53:13.060604+00:00; working_tree_dirty: False Recorded durations are not a controlled hardware benchmark.

## Recovery diagnostics

Recovery is conditional on a delivered fault and is descriptive. Fault delivery is a post-assignment event, so these rates cannot establish a causal treatment contrast. Fault-assigned trials without delivery still remain in both primary comparisons.

| Arm | Fault assigned | Triggered | Delivered | Triggered, no impact | Untriggered | Trigger unknown | Delivery unknown | Recovered/known recovery outcomes | Recovery bounds among delivered |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| flat_retry | 18 | 18 | 18 | 0 | 0 | 0 | 0 | 18/18 | [1.000, 1.000] |
| hierarchy_adaptive | 18 | 16 | 16 | 0 | 2 | 0 | 0 | 16/16 | [1.000, 1.000] |
| hierarchy_fixed | 18 | 15 | 15 | 0 | 3 | 0 | 0 | 15/15 | [1.000, 1.000] |

## Interpretation and limits

- The mechanism profile is descriptive only. It does not inherit or relax the frozen 216-trial study decision, and no inferential CI or p-value is assigned to its paired contrasts.
- The manifest defines assignment; fault delivery and recovery never select the primary analysis set (intention to treat).
- PASS is full trial acceptance and FAIL is zero; UNCERTAIN and NOT_RUN are missing, not assumed failures. No incomplete contrast receives a complete-case confirmatory CI or p-value.
- Repeated calls, repeats, and individual gates are not independent task samples. Repeats are averaged within each task and the bootstrap resamples tasks within family.
- This schedule has 6 task clusters (code_repair: 2, data_transform: 2, scheduling: 2). Percentile bootstrap coverage, when reported, is approximate; intervals may be unstable or degenerate and do not establish adequate power. The original study design remains 12 task clusters (4 per family).
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
