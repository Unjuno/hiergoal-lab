# HierGoal paired study analysis

**Prespecified exploratory benchmark decision: UNCERTAIN**  
Engineering invariant feasibility: **PASS**.  
Reason: `confirmatory_requirements_not_satisfied`.

Protocol: `df31920c82fd7e6207a034226575675961f00b3bd2537bf240415f6a1d94b26e`  
Declared backend/model: `openai` / `gpt-6-luna`; profile: `pilot`.

**Exploratory pilot. This is not a confirmatory heldout result.**

## Coverage and validity

The schedule contains 18 trials in 6 paired blocks and 3 task clusters. Repeats and individual acceptance gates do not increase the number of task clusters.

| Scheduled | Supplied records | PASS | FAIL | UNCERTAIN | NOT_RUN | Missing outcomes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 18 | 18 | 10 | 8 | 0 | 0 | 0 |

Unrecorded scheduled trials: 0; these are included as NOT_RUN. Supplied records can include explicit NOT_RUN placeholders and do not imply execution. Record-consistency issues: 0. Benchmark decision eligible: no.

Benchmark decision blockers:

- `pilot_is_exploratory`
- `not_all_tasks_heldout`
- `study_requires_four_instances_per_family`
- `study_requires_216_scheduled_trials`
- `study_requires_three_repeats_in_both_conditions`

## Nine requirement evidence rules

These nine scoped evidence rules do not replace the frozen study's separate efficacy decision. Engineering PASS on simulated records is software validation only.

PASS applies only to the scope in its row. Engineering PASS can describe simulated software validation. Model-execution coverage remains UNCERTAIN without valid declared model records; it is not the benchmark efficacy decision. Missing or zero unrelated comparisons are UNCERTAIN. NOT_APPLICABLE is reserved for an operation outside the declared arm or condition.

| ID | Requirement | Scoped status | Engineering | Model-execution coverage | Scope |
| --- | --- | --- | --- | --- | --- |
| R1 | Forced failed subgoal and verified recovery | UNCERTAIN | UNCERTAIN | UNCERTAIN | Public-pass to forced domain-fail to an accepted revision of that failed target to independent final-pass, in at least one adaptive trace per family. |
| R2 | Hierarchy, state transitions, and before/after replans | UNCERTAIN | UNCERTAIN | UNCERTAIN | Successfully replayed hierarchical checkpoints plus an exercised, failure-evidenced accepted replan. |
| R3 | Immutable root contract | PASS | PASS | PASS | Every scheduled trace was replayed and the root contract stayed identical in root-bearing state and request snapshots. |
| R4 | Task-family coverage and finite recovery applicability | UNCERTAIN | PASS | UNCERTAIN | Engineering status measures complete three-family coverage; the empirical rule requires each family's assigned adaptive forced-fault recovery proportion to meet the frozen threshold. |
| R5 | Unrelated goals and artifact fields preserved | UNCERTAIN | UNCERTAIN | UNCERTAIN | Plan comparisons cover accepted adaptive revisions; artifact comparisons cover audited adaptive fault paths independently of whether a revision was accepted. Both comparison sets must be nonempty. |
| R6 | Failure-evidenced and bounded replanning | PASS | PASS | PASS | A replan request must have current failed-leaf evidence and authorization; attempted requests stay within the declared cap. |
| R7 | Independent final grading and replay | PASS | PASS | PASS | Audited final grades must match terminal claims; noncandidate budget failures need not call the hidden grader. |
| R8 | Scale coverage and finite resilience | UNCERTAIN | UNCERTAIN | UNCERTAIN | Engineering covers the varied observed trees; the separate finite live-data rule tests frozen per-setting success, paired stress drop, and observed locality thresholds. |
| R9 | Finite repeatability and scientific stability uncertainty | UNCERTAIN | UNCERTAIN | UNCERTAIN | The frozen live reliability rule requires final acceptance in every normal cell and repeated forced domain failure, target revision, and final recovery in every fault cell. |

R8 and R9 scoped decisions concern only frozen finite benchmark thresholds on complete valid live records. General scaling-law, power, precision, and future-stability sufficiency remain UNCERTAIN even if a finite criterion passes. Per-criterion limitations and numerical evidence are retained in summary.json.

## Co-primary assigned-fault contrasts

All trials assigned to the fault condition are included regardless of whether a fault was delivered or recovered. The effect is the adaptive success probability minus comparator success probability, averaged first within task and then equally across families. Differences and interval endpoints are probability differences (multiply by 100 for percentage points).

The practical margin is 0.100. Each interval has nominal 97.5% confidence using Bonferroni adjustment for two contrasts (nominal familywise 95.0%). P-values test zero improvement, are one-sided, and are Holm adjusted. Their validity is conditional on the sign-flip assumptions.

| Contrast | Task clusters | Observed/scheduled pairs | Difference | Adjusted CI | Raw p | Holm p | Missing-data worst/best bounds |
| --- | ---: | ---: | ---: | --- | ---: | ---: | --- |
| adaptive_vs_fixed | 3 | 3/3 | 0.000 | [0.000, 0.000] | 1.000000 | 1.000000 | [0.000, 0.000] |
| adaptive_vs_flat_retry | 3 | 3/3 | -0.667 | [-0.667, -0.667] | 1.000000 | 1.000000 | [-0.667, -0.667] |

Missing-data bounds are identification bounds, not confidence intervals. An incomplete contrast has no confirmatory point estimate, CI, or p-value. An efficacy PASS requires complete valid heldout OpenAI study data, both adjusted CI lower endpoints strictly above the margin, and both Holm p-values at or below the familywise significance level. An efficacy FAIL means at least one adjusted CI upper endpoint is strictly below the margin in an otherwise eligible study; other cases are UNCERTAIN.

## Outcomes by family, arm, and condition

The observed rate excludes missing outcomes only in this explicitly labeled descriptive column. The bounds retain every scheduled trial; no missing outcome is silently scored as failure.

| Family | Arm | Condition | Scheduled | PASS | FAIL | UNCERTAIN | NOT_RUN | Observed successes/observed trials | Scheduled rate bounds |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| code_repair | flat_retry | fault | 1 | 1 | 0 | 0 | 0 | 1/1 | [1.000, 1.000] |
| code_repair | flat_retry | normal | 1 | 1 | 0 | 0 | 0 | 1/1 | [1.000, 1.000] |
| code_repair | hierarchy_adaptive | fault | 1 | 0 | 1 | 0 | 0 | 0/1 | [0.000, 0.000] |
| code_repair | hierarchy_adaptive | normal | 1 | 0 | 1 | 0 | 0 | 0/1 | [0.000, 0.000] |
| code_repair | hierarchy_fixed | fault | 1 | 0 | 1 | 0 | 0 | 0/1 | [0.000, 0.000] |
| code_repair | hierarchy_fixed | normal | 1 | 0 | 1 | 0 | 0 | 0/1 | [0.000, 0.000] |
| data_transform | flat_retry | fault | 1 | 1 | 0 | 0 | 0 | 1/1 | [1.000, 1.000] |
| data_transform | flat_retry | normal | 1 | 1 | 0 | 0 | 0 | 1/1 | [1.000, 1.000] |
| data_transform | hierarchy_adaptive | fault | 1 | 1 | 0 | 0 | 0 | 1/1 | [1.000, 1.000] |
| data_transform | hierarchy_adaptive | normal | 1 | 1 | 0 | 0 | 0 | 1/1 | [1.000, 1.000] |
| data_transform | hierarchy_fixed | fault | 1 | 1 | 0 | 0 | 0 | 1/1 | [1.000, 1.000] |
| data_transform | hierarchy_fixed | normal | 1 | 1 | 0 | 0 | 0 | 1/1 | [1.000, 1.000] |
| scheduling | flat_retry | fault | 1 | 1 | 0 | 0 | 0 | 1/1 | [1.000, 1.000] |
| scheduling | flat_retry | normal | 1 | 1 | 0 | 0 | 0 | 1/1 | [1.000, 1.000] |
| scheduling | hierarchy_adaptive | fault | 1 | 0 | 1 | 0 | 0 | 0/1 | [0.000, 0.000] |
| scheduling | hierarchy_adaptive | normal | 1 | 0 | 1 | 0 | 0 | 0/1 | [0.000, 0.000] |
| scheduling | hierarchy_fixed | fault | 1 | 0 | 1 | 0 | 0 | 0/1 | [0.000, 0.000] |
| scheduling | hierarchy_fixed | normal | 1 | 0 | 1 | 0 | 0 | 0/1 | [0.000, 0.000] |

## Replayed mechanism measurements

Tree cells show median [minimum, maximum] and measured/scheduled trials. Root depth is zero; goal count includes the root. A flat arm has no hierarchy, so its hierarchy measurements are NOT_APPLICABLE.

| Arm | Condition | Replayed/scheduled | Goal count | Leaves | Maximum depth, edges | Dependency edges | Dependency density |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| flat_retry | fault | 3/3 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| flat_retry | normal | 3/3 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| hierarchy_adaptive | fault | 3/3 | 1 [1, 7] (3/3) | 0 [0, 3] (3/3) | 0 [0, 2] (3/3) | 0 [0, 2] (3/3) | 0 [0, 0.667] (3/3) |
| hierarchy_adaptive | normal | 3/3 | 1 [1, 7] (3/3) | 0 [0, 3] (3/3) | 0 [0, 2] (3/3) | 0 [0, 2] (3/3) | 0 [0, 0.667] (3/3) |
| hierarchy_fixed | fault | 3/3 | 1 [1, 7] (3/3) | 0 [0, 3] (3/3) | 0 [0, 2] (3/3) | 0 [0, 2] (3/3) | 0 [0, 0.667] (3/3) |
| hierarchy_fixed | normal | 3/3 | 1 [1, 7] (3/3) | 0 [0, 3] (3/3) | 0 [0, 2] (3/3) | 0 [0, 2] (3/3) | 0 [0, 0.667] (3/3) |

Replan counters show known totals and measured/scheduled trials. Attempts count issued requests, including interrupted or over-budget requests. A missing counter is not zero. Operational necessity tests the recorded failed-leaf and progress rule; it does not prove optimality.

| Arm | Condition | Attempted | Accepted | Rejected | Unnecessary | Decision events | Deferred after progress |
| --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 9 (3/3) | 0 (3/3) |
| flat_retry | normal | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 3 (3/3) | 0 (3/3) |
| hierarchy_adaptive | fault | 1 (3/3) | 1 (3/3) | 0 (3/3) | 0 (3/3) | 5 (3/3) | 2 (3/3) |
| hierarchy_adaptive | normal | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 3 (3/3) | 2 (3/3) |
| hierarchy_fixed | fault | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 7 (3/3) | 4 (3/3) |
| hierarchy_fixed | normal | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 3 (3/3) | 2 (3/3) |

Locality uses nonempty comparisons of unrelated goals and separately of unrelated artifact fields during repair. Zero checked objects cannot establish locality. Dependency invalidations and fresh re-verifications are counts of evidence transitions.

| Arm | Condition | Unrelated goals checked | Goals unchanged | Artifact fields checked | Fields unchanged | Artifact violations | Invalidated goals | Reverified goals |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) |
| flat_retry | normal | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) |
| hierarchy_adaptive | fault | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 2 (3/3) | 2 (3/3) |
| hierarchy_adaptive | normal | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) |
| hierarchy_fixed | fault | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 2 (3/3) | 2 (3/3) |
| hierarchy_fixed | normal | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) | 0 (3/3) |

R5 plan-locality evidence: UNCERTAIN, 0/1 accepted-revision trials with nonempty comparisons. Artifact-locality evidence: UNCERTAIN, 0/1 delivered-fault trials with nonempty comparisons. Artifact violations remain included when every replan response was rejected; plan and artifact denominators are separate.

Replayed hierarchical checkpoints: 25; leaf state transitions: 24; milestone state transitions: 24; accepted replans with failure evidence: 1. Recorded host fault causes: 2; recorded model diagnoses: 1 (text provenance, not causal validation).

Root checked in 18/18 trials; explicit edit requests: 0; rejected edit requests: 0; actual root changes: 0. Record-verification issue trials: 0 (not assumed actual root mutations). A zero edit-attempt count leaves adversarial rejection unexercised in this run.

Final-grade disposition known in 18/18 trials: grader called 10, passed 10, failed 0, not reached 8. Audit failures: 0; grade/terminal-claim conflicts: 0.

## Repeated outcomes within task

Scheduled repeats per task/arm/condition range from 1 to 1. All-pass, mixed, and all-fail below partition only complete task records. Missing repeats remain explicit. These are observed patterns, not an independent-trial reliability estimate or a claim that the sample is sufficient.

| Arm | Condition | Task clusters | Complete clusters | All repeats PASS | Mixed complete outcomes | All repeats FAIL | Incomplete clusters |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| flat_retry | normal | 3 | 3 | 3 | 0 | 0 | 0 |
| flat_retry | fault | 3 | 3 | 3 | 0 | 0 | 0 |
| hierarchy_fixed | normal | 3 | 3 | 1 | 0 | 2 | 0 |
| hierarchy_fixed | fault | 3 | 3 | 1 | 0 | 2 | 0 |
| hierarchy_adaptive | normal | 3 | 3 | 1 | 0 | 2 | 0 |
| hierarchy_adaptive | fault | 3 | 3 | 1 | 0 | 2 | 0 |

Per-family/repeat cells show successful/observed trials, followed by the missing scheduled count. The same task IDs recur across repeats; the table does not create independent task samples.

| Family | Repeat | Flat normal | Flat fault | Fixed normal | Fixed fault | Adaptive normal | Adaptive fault |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| code_repair | 1 | 1/1; missing 0 | 1/1; missing 0 | 0/1; missing 0 | 0/1; missing 0 | 0/1; missing 0 | 0/1; missing 0 |
| data_transform | 1 | 1/1; missing 0 | 1/1; missing 0 | 1/1; missing 0 | 1/1; missing 0 | 1/1; missing 0 | 1/1; missing 0 |
| scheduling | 1 | 1/1; missing 0 | 1/1; missing 0 | 0/1; missing 0 | 0/1; missing 0 | 0/1; missing 0 | 0/1; missing 0 |

Repeat sufficiency: **UNCERTAIN**. No population power, precision, or future-stability guarantee establishes that the repeat count is scientifically sufficient; a finite acceptance threshold is a separate claim.

## Finite task-family recovery applicability

**Scoped decision: UNCERTAIN.** Engineering coverage remains separate. Each of the three families must reach recovery proportion 0.80 over at least 6 assigned adaptive forced-fault trials. Recovery requires a delivered domain failure, an accepted revision of that target, and independent final acceptance. These are finite suite criteria, not a generalization or sample-adequacy guarantee.

| Family | Successful recoveries/observed | Final acceptances | Assigned | Meets frozen minimum |
| --- | ---: | ---: | ---: | --- |
| code_repair | 0/1 | 0 | 1 | UNCERTAIN |
| data_transform | 0/0 | 1 | 1 | UNCERTAIN |
| scheduling | 0/1 | 0 | 1 | UNCERTAIN |

Family applicability blockers:

- `insufficient_assigned_fault_trials_per_family`
- `missing_forced_domain_recovery_evidence`
- `requires_assigned_forced_subgoal_faults`

## Scale coverage

This schedule declares no scale settings. A successful small base task does not establish scale coverage (R8 remains UNCERTAIN).


## Recorded per-trial costs

Cells show median [minimum, maximum] and measured/scheduled trial count. Missing token or timing measurements remain missing. Logical calls/tokens include cached shared planning charges per hierarchical trial and therefore do not equal provider billing. Recorded costs include failed and uncertain trials.

| Arm | Condition | Calls | Input tokens | Output tokens | Total tokens | Logical response seconds | Trial wall seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 2 [1, 3] (3/3) | 3.36e+03 [1.11e+03, 3.72e+03] (3/3) | 927 [142, 975] (3/3) | 4.33e+03 [1.25e+03, 4.65e+03] (3/3) | 7.01 [1.59, 7.65] (3/3) | 7.02 [1.6, 7.66] (3/3) |
| flat_retry | normal | 1 [1, 1] (3/3) | 1.11e+03 [1.08e+03, 1.33e+03] (3/3) | 291 [137, 551] (3/3) | 1.37e+03 [1.25e+03, 1.88e+03] (3/3) | 3.91 [1.58, 4.26] (3/3) | 3.91 [1.59, 4.26] (3/3) |
| hierarchy_adaptive | fault | 1 [1, 6] (3/3) | 1.2e+03 [1.1e+03, 1.23e+04] (3/3) | 472 [272, 1.76e+03] (3/3) | 1.58e+03 [1.47e+03, 1.41e+04] (3/3) | 5.16 [2.8, 17.3] (3/3) | 2.8 [0.000861, 13.7] (3/3) |
| hierarchy_adaptive | normal | 1 [1, 4] (3/3) | 1.2e+03 [1.1e+03, 7.58e+03] (3/3) | 472 [272, 1.02e+03] (3/3) | 1.58e+03 [1.47e+03, 8.6e+03] (3/3) | 5.16 [2.8, 10.6] (3/3) | 0.00108 [0.000813, 6.97] (3/3) |
| hierarchy_fixed | fault | 1 [1, 7] (3/3) | 1.2e+03 [1.1e+03, 1.55e+04] (3/3) | 472 [272, 1.62e+03] (3/3) | 1.58e+03 [1.47e+03, 1.71e+04] (3/3) | 5.16 [2.8, 17.6] (3/3) | 0.00106 [0.000797, 14] (3/3) |
| hierarchy_fixed | normal | 1 [1, 4] (3/3) | 1.2e+03 [1.1e+03, 7.58e+03] (3/3) | 472 [272, 988] (3/3) | 1.58e+03 [1.47e+03, 8.57e+03] (3/3) | 5.16 [2.8, 10.9] (3/3) | 5.17 [0.000955, 11] (3/3) |

Separately recorded actual provider usage (cached plan usage is charged only where recorded):

| Arm | Condition | Actual calls | Actual input tokens | Actual output tokens |
| --- | --- | --- | --- | --- |
| flat_retry | fault | 2 [1, 3] (3/3) | 3.36e+03 [1.11e+03, 3.72e+03] (3/3) | 927 [142, 975] (3/3) |
| flat_retry | normal | 1 [1, 1] (3/3) | 1.11e+03 [1.08e+03, 1.33e+03] (3/3) | 291 [137, 551] (3/3) |
| hierarchy_adaptive | fault | 1 [0, 5] (3/3) | 1.2e+03 [0, 1.09e+04] (3/3) | 272 [0, 1.45e+03] (3/3) |
| hierarchy_adaptive | normal | 0 [0, 3] (3/3) | 0 [0, 6.15e+03] (3/3) | 0 [0, 708] (3/3) |
| hierarchy_fixed | fault | 0 [0, 6] (3/3) | 0 [0, 1.41e+04] (3/3) | 0 [0, 1.31e+03] (3/3) |
| hierarchy_fixed | normal | 1 [0, 4] (3/3) | 1.1e+03 [0, 7.58e+03] (3/3) | 472 [0, 988] (3/3) |

Timing context: batch_size: 1; cpu: Intel(R) Xeon(R) 6975P-C; cpu_clock_mhz_observed_range: [3387.696, 3900.821]; git_commit: 4bc260c0e643d66e90bb2fba7ccbf1dbad7b74eb; logical_cpus: 4; memory_bytes: 16464306176; model_hardware: Provider-managed; not observable; platform: Linux-7.0.0-1014-aws-x86_64-with-glibc2.39; python: 3.12.3; timestamp_utc: 2026-11-25T16:43:38.680251+00:00; working_tree_dirty: False Recorded durations are not a controlled hardware benchmark.

## Recovery diagnostics

Recovery is conditional on a delivered fault and is descriptive. Fault delivery is a post-assignment event, so these rates cannot establish a causal treatment contrast. Fault-assigned trials without delivery still remain in both primary comparisons.

| Arm | Fault assigned | Triggered | Delivered | Triggered, no impact | Untriggered | Trigger unknown | Delivery unknown | Recovered/known recovery outcomes | Recovery bounds among delivered |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| flat_retry | 3 | 3 | 2 | 1 | 0 | 0 | 0 | 2/2 | [1.000, 1.000] |
| hierarchy_adaptive | 3 | 1 | 1 | 0 | 2 | 0 | 0 | 1/1 | [1.000, 1.000] |
| hierarchy_fixed | 3 | 1 | 1 | 0 | 2 | 0 | 0 | 1/1 | [1.000, 1.000] |

## Interpretation and limits

- The pilot is exploratory development validation and cannot confirm a heldout research claim.
- The manifest defines assignment; fault delivery and recovery never select the primary analysis set (intention to treat).
- PASS is full trial acceptance and FAIL is zero; UNCERTAIN and NOT_RUN are missing, not assumed failures. No incomplete contrast receives a complete-case confirmatory CI or p-value.
- Repeated calls, repeats, and individual gates are not independent task samples. Repeats are averaged within each task and the bootstrap resamples tasks within family.
- This schedule has 3 task clusters (code_repair: 1, data_transform: 1, scheduling: 1). Percentile bootstrap coverage, when reported, is approximate; intervals may be unstable or degenerate and do not establish adequate power. The original study design remains 12 task clusters (4 per family).
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
