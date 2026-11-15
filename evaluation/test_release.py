# SPDX-License-Identifier: Apache-2.0
"""Independent deterministic acceptance tests; not copied to the agent workspace."""
import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from miniledger.parse import parse_csv
from miniledger.summary import summarize


class IndependentAcceptance(unittest.TestCase):
    def test_refunds_trim_and_sort(self):
        rows = parse_csv("client,amount\nZ,2.01\n A ,3.20\nZ,-0.01\n A ,-1.10\n")
        self.assertEqual(summarize(rows), [
            {"client": "A", "count": 2, "net": "2.10"},
            {"client": "Z", "count": 2, "net": "2.00"},
        ])

    def test_exact_decimal(self):
        rows = parse_csv("client,amount\nA,0.10\nA,0.20\nA,0.30\n")
        self.assertEqual(summarize(rows), [{"client": "A", "count": 3, "net": "0.60"}])

    def test_invalid_rows(self):
        for source in ("client,amount\n,2\n", "client,amount\nA,NaN\n",
                       "client,amount\nA,inf\n", "client,amount\nA,invalid\n",
                       "name,cost\nA,1\n", "client,amount\nA,\n"):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    parse_csv(source)

    def test_blanks(self):
        self.assertEqual(summarize(parse_csv("client,amount\n\n")), [])

    def test_half_even_rounding(self):
        result = summarize(parse_csv("client,amount\nA,1.005\nB,1.015\n"))
        self.assertEqual(result, [
            {"client": "A", "count": 1, "net": "1.00"},
            {"client": "B", "count": 1, "net": "1.02"},
        ])

    def test_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            input_file = Path(folder) / "data.csv"
            input_file.write_text("client,amount\nZ,5.01\nA,1.05\nZ,-0.03\n", encoding="utf-8")
            response = subprocess.run([sys.executable, "-m", "miniledger", str(input_file)],
                                      capture_output=True, text=True, timeout=10)
            self.assertEqual(response.returncode, 0, response.stderr)
            self.assertEqual(json.loads(response.stdout), [
                {"client": "A", "count": 1, "net": "1.05"},
                {"client": "Z", "count": 2, "net": "4.98"},
            ])


if __name__ == "__main__":
    unittest.main()
