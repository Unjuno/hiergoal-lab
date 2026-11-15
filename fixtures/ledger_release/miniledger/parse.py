# SPDX-License-Identifier: Apache-2.0
"""CSV parser. Deliberate defects: float, ignored refunds, no validation."""
import csv
from io import StringIO


def parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames or not {"client", "amount"}.issubset(reader.fieldnames):
        raise ValueError("Required columns missing")
    rows = []
    for row in reader:
        if not row["amount"]:
            continue
        rows.append({"client": row["client"], "amount": abs(float(row["amount"]))})
    return rows
