# Controlled recovery pilot

**LIVE API PILOT**

Protocol: `d36c836de43c41cb0248a95abaa6af810c0eafd896f606207b20ba4b7a3533a1`

Apparatus: **PASS**. Effectiveness: **UNCERTAIN**.

6 distinct tasks; 12 matched pair slots; 24 repair slots.

Verified preparation yield: 12/12.

Measurements below are medians [minimum, maximum] over valid observed repair trials.

| Arm | Assigned | Valid observed | Recovered | Recovery rate | Calls | Tokens | Wall seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| fixed | 12 | 12 | 12 | 100.0% | 1.0 [1, 2] | 5002.0 [3812, 12027] | 2.8288952585000118 [1.0344638459999942, 6.445792912999991] |
| adaptive | 12 | 12 | 12 | 100.0% | 2.0 [2, 3] | 7785.5 [7202, 17106] | 6.653419486500013 [3.144116217999965, 12.551140375000017] |

Model: gpt-6-luna; reasoning: low; batch: 1. Controller host: Intel(R) Xeon(R) 6975P-C; observed MHz range: [3590.904, 3899.491]; Python: 3.12.3. Model hardware is provider-managed and unobservable.

## Matched outcomes

Both recover: 12; adaptive only: 0; fixed only: 0; neither: 0; incomplete: 0.

Observed adaptive minus fixed: 0.0 percentage points.

No confirmatory confidence interval or equivalence claim is made from this pilot.

## Accounting and integrity

Known source-generation tokens: 96076; known repair tokens: 187041; requests started: 66.

Audit: PASS; root preserved in 24 audited repairs; artifact locality violations in 0 audited repairs.

Ceiling observed in fixed arm: True.

## Limits

- Task parameters are unused, but task families and graders are reused.
- The estimand is repair conditional on successful blinded model-generated preparation.
- Adaptive adds one diagnosis-plus-instruction revision; the components are not separately identified.
- No scale/depth generalization, trigger specificity, broad subtree restructuring, or Hermes integration is tested.
- Repeated gate/field observations are not independent tasks.
- A valid hash chain and semantic replay do not constitute provider-signed proof of API provenance.
