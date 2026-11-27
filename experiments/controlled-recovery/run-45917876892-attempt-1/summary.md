# Controlled recovery pilot

**LIVE API PILOT**

Protocol: `d36c836de43c41cb0248a95abaa6af810c0eafd896f606207b20ba4b7a3533a1`

Apparatus: **UNCERTAIN**. Effectiveness: **UNCERTAIN**.

6 distinct tasks; 12 matched pair slots; 24 repair slots.

Verified preparation yield: 0/12.

Measurements below are medians [minimum, maximum] over valid observed repair trials.

| Arm | Assigned | Valid observed | Recovered | Recovery rate | Calls | Tokens | Wall seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| fixed | 12 | 0 | 0 | NA | NA | NA | NA |
| adaptive | 12 | 0 | 0 | NA | NA | NA | NA |

Model: gpt-6-luna; reasoning: low; batch: 1. Controller host: Intel(R) Xeon(R) 6975P-C; observed MHz range: [3613.784, 3897.867]; Python: 3.12.3. Model hardware is provider-managed and unobservable.

## Matched outcomes

Both recover: 0; adaptive only: 0; fixed only: 0; neither: 0; incomplete: 12.

Observed adaptive minus fixed: None percentage points.

No confirmatory confidence interval or equivalence claim is made from this pilot.

## Accounting and integrity

Known source-generation tokens: 0; known repair tokens: 0; requests started: 1.

Audit: INCOMPLETE; root preserved in 0 audited repairs; artifact locality violations in 0 audited repairs.

Ceiling observed in fixed arm: False.

## Limits

- Task parameters are unused, but task families and graders are reused.
- The estimand is repair conditional on successful blinded model-generated preparation.
- Adaptive adds one diagnosis-plus-instruction revision; the components are not separately identified.
- No scale/depth generalization, trigger specificity, broad subtree restructuring, or Hermes integration is tested.
- Repeated gate/field observations are not independent tasks.
- A valid hash chain and semantic replay do not constitute provider-signed proof of API provenance.
