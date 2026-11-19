# SPDX-License-Identifier: Apache-2.0
"""Four deterministic defect profiles for a small *functional* Hermes benchmark.

Each profile exercises the same immutable user goal and external acceptance
suite, while changing the initial bug distribution. This is a narrow coding
benchmark, not an H-JEPA reproduction or a flat-goal comparison.
"""
from __future__ import annotations

from pathlib import Path

CASE_IDS = ("legacy", "parser_ready", "summary_ready", "refund_rounding")
CASE_DESCRIPTION = {
    "legacy": "Original broken parser and broken aggregator",
    "parser_ready": "Parser correct; aggregator has numeric and formatting defects",
    "summary_ready": "Aggregator correct; parser has validation/refund/float defects",
    "refund_rounding": "Refund-sign and half-even rounding regressions",
}

# Independent, version-controlled fixture variations. These are provided only
# to the controller before launch; the workspace contains the selected code.
GOOD_PARSER = '''import csv
from decimal import Decimal, InvalidOperation
from io import StringIO


def parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames or not {"client", "amount"}.issubset(reader.fieldnames):
        raise ValueError("Required columns missing")
    rows = []
    for row in reader:
        if row is None or not any(x not in (None, "") for x in row.values()):
            continue
        client = (row.get("client") or "").strip()
        raw = (row.get("amount") or "").strip()
        if not client or not raw:
            raise ValueError("Missing client or amount")
        try:
            amount = Decimal(raw)
        except InvalidOperation as exc:
            raise ValueError("Invalid amount") from exc
        if not amount.is_finite():
            raise ValueError("Nonfinite amount")
        rows.append({"client": client, "amount": amount})
    return rows
'''

GOOD_SUMMARY = '''from decimal import Decimal, ROUND_HALF_EVEN


def summarize(records: list[dict]) -> list[dict]:
    totals = {}
    for record in records:
        client = record["client"]
        if client not in totals:
            totals[client] = {"count": 0, "net": Decimal("0")}
        totals[client]["count"] += 1
        totals[client]["net"] += record["amount"]
    return [{"client": client, "count": totals[client]["count"],
             "net": str(totals[client]["net"].quantize(
                 Decimal("0.01"), rounding=ROUND_HALF_EVEN))}
            for client in sorted(totals)]
'''


def apply_case(workspace: Path, case_id: str) -> None:
    if case_id not in CASE_IDS:
        raise ValueError("Unknown benchmark case: " + case_id)
    parse = workspace / "miniledger" / "parse.py"
    summary = workspace / "miniledger" / "summary.py"
    if not parse.is_file() or not summary.is_file():
        raise ValueError("Fixture missing before case application")
    if case_id == "parser_ready":
        parse.write_text(GOOD_PARSER, encoding="utf-8")
    elif case_id == "summary_ready":
        summary.write_text(GOOD_SUMMARY, encoding="utf-8")
    elif case_id == "refund_rounding":
        bad_parser = GOOD_PARSER.replace(
            'rows.append({"client": client, "amount": amount})',
            'rows.append({"client": client, "amount": abs(amount)})',
        )
        bad_summary = GOOD_SUMMARY.replace("ROUND_HALF_EVEN", "ROUND_HALF_UP")
        if bad_parser == GOOD_PARSER or bad_summary == GOOD_SUMMARY:
            raise RuntimeError("The defect profile was not injected")
        parse.write_text(bad_parser, encoding="utf-8")
        summary.write_text(bad_summary, encoding="utf-8")
