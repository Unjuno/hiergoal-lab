# SPDX-License-Identifier: Apache-2.0
import json
import tempfile
import unittest
from pathlib import Path

from hiergoal.study import prepare, collect
from hiergoal.study_archive import export_run, verify, public_result, RECEIPT
from hiergoal.study_protocol import save


class PublicArchiveTests(unittest.TestCase):
    def identity(self, commit="a" * 40):
        return dict(profile="pilot", run_id="12345", attempt="1", commit=commit)

    def test_receipt_when_preparation_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            ident = self.identity()
            receipt = export_run(path / "missing", path / "public", **ident,
                                 live_outcome="skipped", collection_outcome="success")
            self.assertEqual(receipt["state"], "NO_COLLECTED_RESULTS")
            self.assertEqual({p.name for p in (path / "public").iterdir()}, {RECEIPT})
            self.assertEqual(verify(path / "public", **ident), receipt)
            with self.assertRaises(ValueError):
                export_run(path / "missing", path / "public", **ident,
                           live_outcome="skipped", collection_outcome="success")

    def test_prepared_not_run_results_are_retained_and_hash_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            source = path / "study"
            prepare(source, "pilot")
            host = json.loads((source / "host.json").read_text(encoding="utf-8"))
            # The local checkout may be dirty; represent a clean runner in
            # this synthetic test only. No live calls are issued.
            host.update(git_commit="a" * 40, working_tree_dirty=False)
            save(source / "host.json", host)
            collect(source)
            (source / "secret.txt").write_text("must-not-publish")
            ident = self.identity()
            public = path / "public"
            receipt = export_run(source, public, **ident,
                                 live_outcome="failure", collection_outcome="success")
            self.assertEqual(receipt["outcomes"]["NOT_RUN"], 18)
            self.assertFalse(receipt["complete_audited_execution"])
            self.assertFalse((public / "secret.txt").exists())
            self.assertEqual(verify(public, **ident), receipt)
            (public / "trials.csv").write_text("tampered")
            with self.assertRaises(ValueError):
                verify(public, **ident)

    def test_raw_fields_and_arbitrary_diagnostics_never_publish(self):
        manifest = {"model": "gpt-6-luna", "backend": "openai", "protocol_id": "p"}
        trial = {"trial_id": "t"}
        record = {"trial_id": "t", "status": "FAIL", "audit": "PASS",
                  "diagnostic": "private response and key", "raw_response": "private",
                  "observed_models": ["gpt-6-luna", "unexpected private text"],
                  "mechanism_evidence": {"tree": {"goal_count": 2, "private": "secret"},
                                         "private": "secret"}}
        result = public_result(record, trial, manifest)
        self.assertEqual(result["diagnostic"], "OTHER_RECORDED_DIAGNOSTIC")
        self.assertEqual(result["observed_models"], ["gpt-6-luna"])
        self.assertEqual(result["mechanism_evidence"], {"tree": {"goal_count": 2}})
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("raw_response", result)


if __name__ == "__main__":
    unittest.main()
