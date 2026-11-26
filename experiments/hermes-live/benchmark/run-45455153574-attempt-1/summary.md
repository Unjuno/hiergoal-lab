# Hermes live experiment

| Assessment | Result |
|---|---|
| Workflow | PASS |
| Infrastructure | PASS |
| API connection | PASS |
| Experiment | PASS |
| Mode | benchmark |
| Diagnostic | BATCH_RETURNED_CHECK_EMPIRICAL_RESULT |
| Hermes revision | caafe5389ae585ef77387a962aee05b1bcf17029 |

## API probe

| Measurement | Value |
|---|---|
| Observed model | gpt-6-luna |
| Input tokens | 644 |
| Output tokens | 10 |
| Elapsed seconds | 13.672 |
| Estimated USD | 6.94e-05 |

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
| Observed clock range (MHz) | [2700.0, 3802.196] |
| Memory (bytes) | 16464297984 |

Tasks execute sequentially. Hosted CPU clock and provider-side hardware are not controlled.

## Experimental observations

| Attempt | Case | Result | Hermes invocations | Input tokens | Output tokens | Tools | Hermes seconds | Estimated USD |
|---|---|---|---|---|---|---|---|---|
| 1 | parser_ready | PASS | 2 | 80960 | 1913 | 19 | 47.116 | 0.0090525 |
| 2 | refund_rounding | PASS | 3 | 166558 | 2137 | 30 | 85.315 | 0.0177243 |
| 3 | summary_ready | PASS | 2 | 84645 | 1761 | 17 | 41.885 | 0.009345 |
| 4 | parser_ready | PASS | 2 | 126766 | 2171 | 17 | 45.398 | 0.0137621 |
| 5 | summary_ready | PASS | 2 | 96886 | 2251 | 17 | 60.428 | 0.0108141 |
| 6 | legacy | PASS | 5 | 302229 | 5309 | 51 | 143.3 | 0.0328774 |
| 7 | refund_rounding | PASS | 3 | 172543 | 2636 | 33 | 84.825 | 0.0185723 |
| 8 | legacy | PASS | 6 | 357536 | 5766 | 58 | 160.793 | 0.0386366 |

Engineering target: PASS.

Connection success and experimental success are separate assessments. A CLI check makes no model requests.
Hermes invocations are not API-request counts. The soft spending guard uses the nominal token rates in the pinned source; USD values are estimates, not billing receipts or hard caps.
Combined observed estimate including the API probe (USD): 0.1508537.
Unknown counters remain unknown. This is a single-method preliminary experiment; it does not establish superiority.
