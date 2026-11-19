# SPDX-License-Identifier: Apache-2.0
"""Each benchmark case is distinct, deterministic and initially failing."""
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from hiergoal.cases import CASE_IDS, apply_case
from hiergoal.controller import grade
from hiergoal.core import GATES

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "ledger_release"


class CaseProfiles(unittest.TestCase):
    def test_all_cases_are_deterministic_and_begin_with_failing_gates(self):
        fingerprints = set()
        for case in CASE_IDS:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as folder:
                work = Path(folder) / "task"
                shutil.copytree(FIXTURE, work)
                apply_case(work, case)
                source = (
                    (work / "miniledger" / "parse.py").read_bytes()
                    + (work / "miniledger" / "summary.py").read_bytes()
                )
                self.assertNotIn(hashlib.sha256(source).digest(), fingerprints)
                fingerprints.add(hashlib.sha256(source).digest())
                verdict = grade(work, list(GATES))
                self.assertEqual(verdict["tests_run"], len(GATES))
                self.assertFalse(verdict["passed"])

    def test_every_case_supports_true_no_key_dry_run(self):
        import subprocess
        import sys
        for case in CASE_IDS:
            with self.subTest(case=case):
                proc = subprocess.run(
                    [sys.executable, "-m", "hiergoal.controller",
                     "--backend", "luna", "--case", case, "--dry-run"],
                    cwd=ROOT, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("Validated case: " + case, proc.stdout)

    def test_invalid_case_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder) / "task"
            shutil.copytree(FIXTURE, work)
            with self.assertRaisesRegex(ValueError, "Unknown benchmark case"):
                apply_case(work, "not-a-case")


if __name__ == "__main__":
    unittest.main()
