# HierGoal paired study analysis

**Prespecified exploratory benchmark decision: FAIL**  
Engineering invariant feasibility: **PASS**.  
Reason: `at_least_one_adjusted_interval_below_practical_effect_margin`.

Protocol: `246ea3956e33e00fe9b27dccc1d03c3cc5f520dce5ebcde60fb0b6c1e22e8b91`  
Declared backend/model: `openai` / `gpt-6-luna`; profile: `study`.

## Coverage and validity

The schedule contains 216 trials in 72 paired blocks and 12 task clusters. Repeats and individual acceptance gates do not increase the number of task clusters.

| Scheduled | Supplied records | PASS | FAIL | UNCERTAIN | NOT_RUN | Missing outcomes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 216 | 216 | 176 | 40 | 0 | 0 | 0 |

Unrecorded scheduled trials: 0; these are included as NOT_RUN. Supplied records can include explicit NOT_RUN placeholders and do not imply execution. Record-consistency issues: 0. Benchmark decision eligible: yes.

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
| R9 | Finite repeatability and scientific stability uncertainty | UNCERTAIN | PASS | UNCERTAIN | The frozen live reliability rule requires final acceptance in every normal cell and repeated forced domain failure, target revision, and final recovery in every fault cell. |

R8 and R9 scoped decisions concern only frozen finite benchmark thresholds on complete valid live records. General scaling-law, power, precision, and future-stability sufficiency remain UNCERTAIN even if a finite criterion passes. Per-criterion limitations and numerical evidence are retained in summary.json.

## Co-primary assigned-fault contrasts

All trials assigned to the fault condition are included regardless of whether a fault was delivered or recovered. The effect is the adaptive success probability minus comparator success probability, averaged first within task and then equally across families. Differences and interval endpoints are probability differences (multiply by 100 for percentage points).

The practical margin is 0.100. Each interval has nominal 97.5% confidence using Bonferroni adjustment for two contrasts (nominal familywise 95.0%). P-values test zero improvement, are one-sided, and are Holm adjusted. Their validity is conditional on the sign-flip assumptions.

| Contrast | Task clusters | Observed/scheduled pairs | Difference | Adjusted CI | Raw p | Holm p | Missing-data worst/best bounds |
| --- | ---: | ---: | ---: | --- | ---: | ---: | --- |
| adaptive_vs_fixed | 12 | 36/36 | 0.000 | [0.000, 0.000] | 1.000000 | 1.000000 | [0.000, 0.000] |
| adaptive_vs_flat_retry | 12 | 36/36 | -0.278 | [-0.361, -0.222] | 1.000000 | 1.000000 | [-0.278, -0.278] |

Missing-data bounds are identification bounds, not confidence intervals. An incomplete contrast has no confirmatory point estimate, CI, or p-value. An efficacy PASS requires complete valid heldout OpenAI study data, both adjusted CI lower endpoints strictly above the margin, and both Holm p-values at or below the familywise significance level. An efficacy FAIL means at least one adjusted CI upper endpoint is strictly below the margin in an otherwise eligible study; other cases are UNCERTAIN.

## Outcomes by family, arm, and condition

The observed rate excludes missing outcomes only in this explicitly labeled descriptive column. The bounds retain every scheduled trial; no missing outcome is silently scored as failure.

| Family | Arm | Condition | Scheduled | PASS | FAIL | UNCERTAIN | NOT_RUN | Observed successes/observed trials | Scheduled rate bounds |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| code_repair | flat_retry | fault | 12 | 12 | 0 | 0 | 0 | 12/12 | [1.000, 1.000] |
| code_repair | flat_retry | normal | 12 | 12 | 0 | 0 | 0 | 12/12 | [1.000, 1.000] |
| code_repair | hierarchy_adaptive | fault | 12 | 12 | 0 | 0 | 0 | 12/12 | [1.000, 1.000] |
| code_repair | hierarchy_adaptive | normal | 12 | 12 | 0 | 0 | 0 | 12/12 | [1.000, 1.000] |
| code_repair | hierarchy_fixed | fault | 12 | 12 | 0 | 0 | 0 | 12/12 | [1.000, 1.000] |
| code_repair | hierarchy_fixed | normal | 12 | 12 | 0 | 0 | 0 | 12/12 | [1.000, 1.000] |
| data_transform | flat_retry | fault | 12 | 12 | 0 | 0 | 0 | 12/12 | [1.000, 1.000] |
| data_transform | flat_retry | normal | 12 | 12 | 0 | 0 | 0 | 12/12 | [1.000, 1.000] |
| data_transform | hierarchy_adaptive | fault | 12 | 11 | 1 | 0 | 0 | 11/12 | [0.917, 0.917] |
| data_transform | hierarchy_adaptive | normal | 12 | 11 | 1 | 0 | 0 | 11/12 | [0.917, 0.917] |
| data_transform | hierarchy_fixed | fault | 12 | 11 | 1 | 0 | 0 | 11/12 | [0.917, 0.917] |
| data_transform | hierarchy_fixed | normal | 12 | 11 | 1 | 0 | 0 | 11/12 | [0.917, 0.917] |
| scheduling | flat_retry | fault | 12 | 12 | 0 | 0 | 0 | 12/12 | [1.000, 1.000] |
| scheduling | flat_retry | normal | 12 | 12 | 0 | 0 | 0 | 12/12 | [1.000, 1.000] |
| scheduling | hierarchy_adaptive | fault | 12 | 3 | 9 | 0 | 0 | 3/12 | [0.250, 0.250] |
| scheduling | hierarchy_adaptive | normal | 12 | 3 | 9 | 0 | 0 | 3/12 | [0.250, 0.250] |
| scheduling | hierarchy_fixed | fault | 12 | 3 | 9 | 0 | 0 | 3/12 | [0.250, 0.250] |
| scheduling | hierarchy_fixed | normal | 12 | 3 | 9 | 0 | 0 | 3/12 | [0.250, 0.250] |

## Replayed mechanism measurements

Tree cells show median [minimum, maximum] and measured/scheduled trials. Root depth is zero; goal count includes the root. A flat arm has no hierarchy, so its hierarchy measurements are NOT_APPLICABLE.

| Arm | Condition | Replayed/scheduled | Goal count | Leaves | Maximum depth, edges | Dependency edges | Dependency density |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| flat_retry | fault | 36/36 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| flat_retry | normal | 36/36 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| hierarchy_adaptive | fault | 36/36 | 7 [1, 7] (36/36) | 3 [0, 3] (36/36) | 2 [0, 2] (36/36) | 2 [0, 3] (36/36) | 0.667 [0, 1] (36/36) |
| hierarchy_adaptive | normal | 36/36 | 7 [1, 7] (36/36) | 3 [0, 3] (36/36) | 2 [0, 2] (36/36) | 2 [0, 3] (36/36) | 0.667 [0, 1] (36/36) |
| hierarchy_fixed | fault | 36/36 | 7 [1, 7] (36/36) | 3 [0, 3] (36/36) | 2 [0, 2] (36/36) | 2 [0, 3] (36/36) | 0.667 [0, 1] (36/36) |
| hierarchy_fixed | normal | 36/36 | 7 [1, 7] (36/36) | 3 [0, 3] (36/36) | 2 [0, 2] (36/36) | 2 [0, 3] (36/36) | 0.667 [0, 1] (36/36) |

Replan counters show known totals and measured/scheduled trials. Attempts count issued requests, including interrupted or over-budget requests. A missing counter is not zero. Operational necessity tests the recorded failed-leaf and progress rule; it does not prove optimality.

| Arm | Condition | Attempted | Accepted | Rejected | Unnecessary | Decision events | Deferred after progress |
| --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 97 (36/36) | 0 (36/36) |
| flat_retry | normal | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 38 (36/36) | 0 (36/36) |
| hierarchy_adaptive | fault | 31 (36/36) | 31 (36/36) | 0 (36/36) | 0 (36/36) | 116 (36/36) | 33 (36/36) |
| hierarchy_adaptive | normal | 12 (36/36) | 12 (36/36) | 0 (36/36) | 0 (36/36) | 63 (36/36) | 25 (36/36) |
| hierarchy_fixed | fault | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 111 (36/36) | 32 (36/36) |
| hierarchy_fixed | normal | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 64 (36/36) | 30 (36/36) |

Locality uses nonempty comparisons of unrelated goals and separately of unrelated artifact fields during repair. Zero checked objects cannot establish locality. Dependency invalidations and fresh re-verifications are counts of evidence transitions.

| Arm | Condition | Unrelated goals checked | Goals unchanged | Artifact fields checked | Fields unchanged | Artifact violations | Invalidated goals | Reverified goals |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) |
| flat_retry | normal | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) |
| hierarchy_adaptive | fault | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 28 (36/36) | 28 (36/36) |
| hierarchy_adaptive | normal | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 2 (36/36) | 2 (36/36) |
| hierarchy_fixed | fault | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 30 (36/36) | 30 (36/36) |
| hierarchy_fixed | normal | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 0 (36/36) | 2 (36/36) | 2 (36/36) |

R5 plan-locality evidence: UNCERTAIN, 0/36 accepted-revision trials with nonempty comparisons. Artifact-locality evidence: UNCERTAIN, 0/15 delivered-fault trials with nonempty comparisons. Artifact violations remain included when every replan response was rejected; plan and artifact denominators are separate.

Replayed hierarchical checkpoints: 553; leaf state transitions: 564; milestone state transitions: 564; accepted replans with failure evidence: 43. Recorded host fault causes: 52; recorded model diagnoses: 43 (text provenance, not causal validation).

Root checked in 216/216 trials; explicit edit requests: 0; rejected edit requests: 0; actual root changes: 0. Record-verification issue trials: 0 (not assumed actual root mutations). A zero edit-attempt count leaves adversarial rejection unexercised in this run.

Final-grade disposition known in 216/216 trials: grader called 176, passed 176, failed 0, not reached 40. Audit failures: 0; grade/terminal-claim conflicts: 0.

## Repeated outcomes within task

Scheduled repeats per task/arm/condition range from 3 to 3. All-pass, mixed, and all-fail below partition only complete task records. Missing repeats remain explicit. These are observed patterns, not an independent-trial reliability estimate or a claim that the sample is sufficient.

| Arm | Condition | Task clusters | Complete clusters | All repeats PASS | Mixed complete outcomes | All repeats FAIL | Incomplete clusters |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| flat_retry | normal | 12 | 12 | 12 | 0 | 0 | 0 |
| flat_retry | fault | 12 | 12 | 12 | 0 | 0 | 0 |
| hierarchy_fixed | normal | 12 | 12 | 7 | 4 | 1 | 0 |
| hierarchy_fixed | fault | 12 | 12 | 7 | 4 | 1 | 0 |
| hierarchy_adaptive | normal | 12 | 12 | 7 | 4 | 1 | 0 |
| hierarchy_adaptive | fault | 12 | 12 | 7 | 4 | 1 | 0 |

Per-family/repeat cells show successful/observed trials, followed by the missing scheduled count. The same task IDs recur across repeats; the table does not create independent task samples.

| Family | Repeat | Flat normal | Flat fault | Fixed normal | Fixed fault | Adaptive normal | Adaptive fault |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| code_repair | 1 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| code_repair | 2 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| code_repair | 3 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| data_transform | 1 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| data_transform | 2 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 | 4/4; missing 0 |
| data_transform | 3 | 4/4; missing 0 | 4/4; missing 0 | 3/4; missing 0 | 3/4; missing 0 | 3/4; missing 0 | 3/4; missing 0 |
| scheduling | 1 | 4/4; missing 0 | 4/4; missing 0 | 1/4; missing 0 | 1/4; missing 0 | 1/4; missing 0 | 1/4; missing 0 |
| scheduling | 2 | 4/4; missing 0 | 4/4; missing 0 | 0/4; missing 0 | 0/4; missing 0 | 0/4; missing 0 | 0/4; missing 0 |
| scheduling | 3 | 4/4; missing 0 | 4/4; missing 0 | 2/4; missing 0 | 2/4; missing 0 | 2/4; missing 0 | 2/4; missing 0 |

Repeat sufficiency: **UNCERTAIN**. No population power, precision, or future-stability guarantee establishes that the repeat count is scientifically sufficient; a finite acceptance threshold is a separate claim.

## Finite task-family recovery applicability

**Scoped decision: UNCERTAIN.** Engineering coverage remains separate. Each of the three families must reach recovery proportion 0.80 over at least 6 assigned adaptive forced-fault trials. Recovery requires a delivered domain failure, an accepted revision of that target, and independent final acceptance. These are finite suite criteria, not a generalization or sample-adequacy guarantee.

| Family | Successful recoveries/observed | Final acceptances | Assigned | Meets frozen minimum |
| --- | ---: | ---: | ---: | --- |
| code_repair | 0/0 | 12 | 12 | UNCERTAIN |
| data_transform | 0/1 | 11 | 12 | UNCERTAIN |
| scheduling | 0/9 | 3 | 12 | UNCERTAIN |

Family applicability blockers:

- `missing_forced_domain_recovery_evidence`
- `requires_assigned_forced_subgoal_faults`

## Scale coverage

This schedule declares no scale settings. A successful small base task does not establish scale coverage (R8 remains UNCERTAIN).


## Recorded per-trial costs

Cells show median [minimum, maximum] and measured/scheduled trial count. Missing token or timing measurements remain missing. Logical calls/tokens include cached shared planning charges per hierarchical trial and therefore do not equal provider billing. Recorded costs include failed and uncertain trials.

| Arm | Condition | Calls | Input tokens | Output tokens | Total tokens | Logical response seconds | Trial wall seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| flat_retry | fault | 2 [1, 4] (36/36) | 2.33e+03 [1.08e+03, 8.29e+03] (36/36) | 606 [131, 1.8e+03] (36/36) | 2.93e+03 [1.24e+03, 9.83e+03] (36/36) | 4.74 [1.29, 12.1] (36/36) | 4.75 [1.29, 12.1] (36/36) |
| flat_retry | normal | 1 [1, 2] (36/36) | 1.11e+03 [1.08e+03, 2.33e+03] (36/36) | 320 [134, 675] (36/36) | 1.4e+03 [1.25e+03, 3e+03] (36/36) | 2.49 [1.41, 4.82] (36/36) | 2.49 [1.42, 4.82] (36/36) |
| hierarchy_adaptive | fault | 5 [1, 10] (36/36) | 7.14e+03 [1.11e+03, 2.39e+04] (36/36) | 1.15e+03 [338, 2.54e+03] (36/36) | 8.19e+03 [1.45e+03, 2.64e+04] (36/36) | 11.1 [2.86, 22.5] (36/36) | 8.13 [0.000733, 22.5] (36/36) |
| hierarchy_adaptive | normal | 3 [1, 8] (36/36) | 4.21e+03 [1.11e+03, 1.24e+04] (36/36) | 944 [338, 1.58e+03] (36/36) | 5.24e+03 [1.45e+03, 1.4e+04] (36/36) | 8.09 [2.86, 15.5] (36/36) | 6.11 [0.000719, 14.3] (36/36) |
| hierarchy_fixed | fault | 3.5 [1, 7] (36/36) | 5.68e+03 [1.11e+03, 1.58e+04] (36/36) | 814 [338, 1.76e+03] (36/36) | 6.51e+03 [1.45e+03, 1.75e+04] (36/36) | 8.37 [2.86, 16.5] (36/36) | 5.23 [0.000737, 12.6] (36/36) |
| hierarchy_fixed | normal | 3 [1, 5] (36/36) | 4.12e+03 [1.11e+03, 7.9e+03] (36/36) | 744 [338, 1.13e+03] (36/36) | 4.74e+03 [1.45e+03, 9.01e+03] (36/36) | 6.68 [2.86, 10.4] (36/36) | 4.24 [0.000727, 10.4] (36/36) |

Separately recorded actual provider usage (cached plan usage is charged only where recorded):

| Arm | Condition | Actual calls | Actual input tokens | Actual output tokens |
| --- | --- | --- | --- | --- |
| flat_retry | fault | 2 [1, 4] (36/36) | 2.33e+03 [1.08e+03, 8.29e+03] (36/36) | 606 [131, 1.8e+03] (36/36) |
| flat_retry | normal | 1 [1, 2] (36/36) | 1.11e+03 [1.08e+03, 2.33e+03] (36/36) | 320 [134, 675] (36/36) |
| hierarchy_adaptive | fault | 4 [0, 10] (36/36) | 5.94e+03 [0, 2.39e+04] (36/36) | 806 [0, 2.54e+03] (36/36) |
| hierarchy_adaptive | normal | 2.5 [0, 7] (36/36) | 3.65e+03 [0, 1.24e+04] (36/36) | 662 [0, 1.58e+03] (36/36) |
| hierarchy_fixed | fault | 3 [0, 6] (36/36) | 4.36e+03 [0, 1.44e+04] (36/36) | 454 [0, 1.39e+03] (36/36) |
| hierarchy_fixed | normal | 2.5 [0, 5] (36/36) | 3.65e+03 [0, 7.82e+03] (36/36) | 430 [0, 1.11e+03] (36/36) |

Timing context: batch_size: 1; cpu: Intel(R) Xeon(R) 6975P-C; cpu_clock_mhz_observed_range: [2700.0, 3882.82]; git_commit: 129d8d4f2d885699c33aba51506b87079bdb70eb; logical_cpus: 4; memory_bytes: 16464293888; model_hardware: Provider-managed; not observable; platform: Linux-7.0.0-1014-aws-x86_64-with-glibc2.39; python: 3.12.3; timestamp_utc: 2026-11-26T00:32:22.088444+00:00; working_tree_dirty: False Recorded durations are not a controlled hardware benchmark.

## Recovery diagnostics

Recovery is conditional on a delivered fault and is descriptive. Fault delivery is a post-assignment event, so these rates cannot establish a causal treatment contrast. Fault-assigned trials without delivery still remain in both primary comparisons.

| Arm | Fault assigned | Triggered | Delivered | Triggered, no impact | Untriggered | Trigger unknown | Delivery unknown | Recovered/known recovery outcomes | Recovery bounds among delivered |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| flat_retry | 36 | 36 | 20 | 16 | 0 | 0 | 0 | 20/20 | [1.000, 1.000] |
| hierarchy_adaptive | 36 | 26 | 15 | 11 | 10 | 0 | 0 | 15/15 | [1.000, 1.000] |
| hierarchy_fixed | 36 | 26 | 16 | 10 | 10 | 0 | 0 | 16/16 | [1.000, 1.000] |

## Interpretation and limits

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
