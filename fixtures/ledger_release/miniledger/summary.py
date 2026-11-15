# SPDX-License-Identifier: Apache-2.0
"""Ledger summary. Deliberate defects: unsorted data and wrong net format."""


def summarize(records: list[dict]) -> list[dict]:
    totals = {}
    for record in records:
        client = record["client"]
        if client not in totals:
            totals[client] = {"client": client, "count": 0, "net": 0}
        totals[client]["count"] += 1
        totals[client]["net"] += record["amount"]
    return list(totals.values())
