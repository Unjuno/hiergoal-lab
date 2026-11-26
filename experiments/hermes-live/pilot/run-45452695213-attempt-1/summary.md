# Hermes live experiment

| Assessment | Result |
|---|---|
| Workflow | PASS |
| Infrastructure | PASS |
| API connection | PASS |
| Experiment | PASS |
| Mode | pilot |
| Diagnostic | BATCH_RETURNED_CHECK_EMPIRICAL_RESULT |
| Hermes revision | caafe5389ae585ef77387a962aee05b1bcf17029 |

## API probe

| Measurement | Value |
|---|---|
| Observed model | gpt-6-luna |
| Input tokens | 648 |
| Output tokens | 10 |
| Elapsed seconds | 14.423 |
| Estimated USD | 6.98e-05 |

## Execution conditions

| Condition | Value |
|---|---|
| Source commit | 14ca1496e82ac34fc3fcbe8047f178002efd7fb7 |
| Runner image | ubuntu24/20261116.133.1 |
| OS | Linux |
| Architecture | x86_64 |
| Python | 3.14.10 |
| CPU | Intel(R) Xeon(R) 6975P-C |
| Logical CPUs | 4 |
| Observed clock range (MHz) | [2700.0, 3799.119] |
| Memory (bytes) | 16464302080 |

Tasks execute sequentially. Hosted CPU clock and provider-side hardware are not controlled.

## Experimental observations

| Attempt | Case | Result | Hermes invocations | Input tokens | Output tokens | Tools | Hermes seconds | Estimated USD |
|---|---|---|---|---|---|---|---|---|
| 1 | legacy | PASS | 3 | 278595 | 3911 | 41 | 80.695 | 0.029815 |

Engineering target: NOT_APPLICABLE.

Connection success and experimental success are separate assessments. A CLI check makes no model requests.
Hermes invocations are not API-request counts. The soft spending guard uses the nominal token rates in the pinned source; USD values are estimates, not billing receipts or hard caps.
Combined observed estimate including the API probe (USD): 0.0298848.
Unknown counters remain unknown. This is a single-method preliminary experiment; it does not establish superiority.
