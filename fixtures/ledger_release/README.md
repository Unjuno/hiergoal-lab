# Ledger Release Task

Repair this Python package to meet the public contracts using Python standard library only.

- parse_csv(text) must read CSV with required columns client,amount.
- Ignore blank records, trim client and amount, and reject empty client or invalid/nonfinite amounts with ValueError.
- Treat negative amounts as refunds and do not use binary floating-point arithmetic.
- summarize(records) returns one dictionary per client sorted by client name with exact keys client, count, net. net is an exact string with two decimal places, rounded HALF_EVEN at final output.
- python -m miniledger path.csv prints a JSON list; invalid input exits nonzero without a traceback.
- Keep the public signatures and do not install dependencies.
- Visible tests: python -m unittest discover -s tests -v

Separate evaluation tests exist outside this task workspace.
