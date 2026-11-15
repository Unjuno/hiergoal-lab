# SPDX-License-Identifier: Apache-2.0
import unittest
from miniledger.parse import parse_csv
from miniledger.summary import summarize


class LedgerVisibleTests(unittest.TestCase):
    def test_positive_payment(self):
        self.assertEqual(summarize(parse_csv("client,amount\nA,3.20\n")),
                         [{"client": "A", "count": 1, "net": "3.20"}])

    def test_refund(self):
        self.assertEqual(summarize(parse_csv("client,amount\nA,10.00\nA,-2.50\n")),
                         [{"client": "A", "count": 2, "net": "7.50"}])

    def test_sort(self):
        rows = parse_csv("client,amount\nZ,1\nA,2\n")
        self.assertEqual([r["client"] for r in summarize(rows)], ["A", "Z"])


if __name__ == "__main__":
    unittest.main()
