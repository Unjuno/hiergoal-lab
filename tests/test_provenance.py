# SPDX-License-Identifier: Apache-2.0
"""Protocol fingerprints are stable and sensitive to evaluator/source mutations."""
import tempfile
import unittest
from pathlib import Path

from hiergoal.provenance import protocol_manifest, capture_provenance, PROTOCOL_PATHS


class ProvenanceTests(unittest.TestCase):
    def test_capture_has_sane_host_metadata(self):
        root = Path(__file__).resolve().parents[1]
        a = protocol_manifest(root)
        b = protocol_manifest(root)
        self.assertEqual(a["protocol_id"], b["protocol_id"])
        self.assertEqual(len(a["source_file_sha256"]), len(PROTOCOL_PATHS))
        result = capture_provenance(root)
        self.assertTrue(result["python_version"])
        self.assertEqual(result["protocol_id"], a["protocol_id"])
        self.assertNotIn("HOME", result)

    def test_changed_evaluator_changes_protocol_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in PROTOCOL_PATHS:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("content:" + name, encoding="utf-8")
            original = protocol_manifest(root)["protocol_id"]
            target = root / "evaluation/test_release.py"
            target.write_text("changed acceptance contract", encoding="utf-8")
            self.assertNotEqual(protocol_manifest(root)["protocol_id"], original)

    def test_missing_protocol_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "missing"):
                protocol_manifest(Path(tmp))


if __name__ == "__main__":
    unittest.main()
