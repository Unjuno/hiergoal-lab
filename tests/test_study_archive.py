# SPDX-License-Identifier: Apache-2.0
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hiergoal.study import prepare, collect, run
from hiergoal.study_api import OpenAIResponder
from hiergoal.study_archive import export_run, verify, public_result, RECEIPT, file_hash
from hiergoal.study_protocol import digest, save
from hiergoal.study_wire import expand_wire
from test_study_api import FakeOpener, envelope


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

    def test_receipt_only_cannot_claim_completed_execution(self):
        for key, value in (("complete_audited_execution", True), ("scheduled_trials", 18),
                           ("outcomes", {"PASS": 18}), ("protocol_id", "invented")):
            with self.subTest(field=key), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)
                ident = self.identity()
                public = path / "public"
                receipt = export_run(path / "missing", public, **ident,
                                     live_outcome="failure", collection_outcome="failure")
                receipt[key] = value
                save(public / RECEIPT, receipt)
                with self.assertRaises(ValueError):
                    verify(public, **ident)

    def test_matching_checksums_do_not_override_public_result_semantics(self):
        cases = ("completion", "outcomes", "summary", "markdown", "csv", "host_commit",
                 "dirty_source", "source_hash", "execution", "collection_step")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)
                ident = self.identity()
                source, public = path / "source", path / "public"
                prepare(source)
                host = json.loads((source / "host.json").read_text())
                host.update(git_commit=ident["commit"], working_tree_dirty=False)
                save(source / "host.json", host)
                collect(source)
                receipt = export_run(source, public, **ident,
                                     live_outcome="failure", collection_outcome="success")
                changed = None
                if case == "completion":
                    receipt["complete_audited_execution"] = True
                elif case == "outcomes":
                    receipt["outcomes"].update(PASS=18, NOT_RUN=0)
                elif case == "collection_step":
                    receipt["collection_step"] = "failure"
                elif case == "summary":
                    changed = "summary.json"
                    value = json.loads((public / changed).read_text())
                    value["decision"] = "PASS"
                    save(public / changed, value)
                elif case == "markdown":
                    changed = "summary.md"
                    (public / changed).write_text("All trials passed.\n")
                elif case == "csv":
                    changed = "trials.csv"
                    with (public / changed).open("a") as stream:
                        stream.write("fabricated trial\n")
                elif case in ("host_commit", "dirty_source"):
                    changed = "host.json"
                    value = json.loads((public / changed).read_text())
                    value.update({"git_commit": "b" * 40} if case == "host_commit"
                                 else {"working_tree_dirty": True})
                    save(public / changed, value)
                elif case == "source_hash":
                    changed = "manifest.json"
                    value = json.loads((public / changed).read_text())
                    value["source_file_sha256"]["hiergoal/study.py"] = "0" * 64
                    value["protocol_id"] = digest({k: v for k, v in value.items() if k != "protocol_id"})
                    receipt["protocol_id"] = value["protocol_id"]
                    save(public / changed, value)
                elif case == "execution":
                    changed = "execution.json"
                    save(public / changed, {"protocol_id": receipt["protocol_id"], "backend": "openai",
                                            "status": "COMPLETED", "completed": 0, "stop_reason": None})
                if changed:
                    # Rehashing a modified file used to bypass verification.
                    receipt["files"][changed] = file_hash(public / changed)
                save(public / RECEIPT, receipt)
                with self.assertRaises(ValueError):
                    verify(public, **ident)

    def test_completed_negative_transport_fixture_remains_publishable(self):
        """An offline HTTP fixture exercises the real projection, never an API."""
        class InvalidActions(FakeOpener):
            def open(self, request, timeout):
                payload = expand_wire(json.loads(json.loads(request.data)["input"]))
                reply = {"patch": {}}
                if payload["role"] == "plan":
                    gates = list(payload["gates"])
                    owners = {gate: "S" + str(i + 1) for i, gate in enumerate(gates)}
                    leaves = [{"id": owners[gate], "instruction": "Meet the frozen gate: " + gate,
                               "checks": [gate], "depends_on": [owners[dep] for dep in
                                   payload["gate_dependencies"].get(gate, [])]} for gate in gates]
                    reply = {"milestones": [
                        {"id": "M1", "title": "Prepare intermediate artifacts", "subgoals": leaves[:-1]},
                        {"id": "M2", "title": "Complete the result", "subgoals": leaves[-1:]},
                    ]}
                self.payload = envelope(output=[{"type": "message", "content": [
                    {"type": "output_text", "text": json.dumps(reply)}]}])
                return super().open(request, timeout)

        with tempfile.TemporaryDirectory() as tmp, patch.dict(
                "os.environ", {"OPENAI_API_KEY": "offline-test-only"}, clear=True):
            path = Path(tmp)
            ident = self.identity()
            source, public = path / "source", path / "public"
            prepare(source)
            host = json.loads((source / "host.json").read_text())
            host.update(git_commit=ident["commit"], working_tree_dirty=False)
            save(source / "host.json", host)
            # Deliberately invalid actions give scientifically negative, audited
            # rows. All requests stay inside FakeOpener; no evidence is retained.
            opener = InvalidActions(envelope())
            backend = OpenAIResponder("gpt-6-luna", approve_live=True, opener=opener)
            with patch("hiergoal.study.OpenAIResponder", return_value=backend):
                run(source, execute=True, approve_paid_api=True)
            self.assertGreater(len(opener.requests), 0)
            receipt = export_run(source, public, **ident,
                                 live_outcome="success", collection_outcome="success")
            self.assertEqual(receipt["outcomes"]["FAIL"], 18)
            self.assertTrue(receipt["complete_audited_execution"])
            self.assertEqual(verify(public, **ident), receipt)


if __name__ == "__main__":
    unittest.main()
