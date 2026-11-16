# SPDX-License-Identifier: Apache-2.0
"""Local process-lock and interrupted-run recovery invariants."""
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from hiergoal.controller import Controller, ExperimentStopped, DEFAULT_MODEL, PROVIDER, PROFILE, save_json
from hiergoal.core import ROOT_GOAL, validate_plan
from tests.test_hiergoal_controller import PLAN


def options(path, resume=None, confirm=False):
    return Namespace(
        output=path / "runs", resume=resume, model=DEFAULT_MODEL,
        confirm_stopped=confirm
    )


def seed_run(path: Path):
    run = path / "recovery"
    workspace = run / "workspace"
    workspace.mkdir(parents=True)
    state = validate_plan(PLAN)
    state["root"]["status"] = "active"
    state["leaves"]["S1"]["status"] = "running"
    save_json(run / "state.json", state)
    records = {
        "provider": PROVIDER, "profile": PROFILE, "model": DEFAULT_MODEL,
        "outcome": "UNCERTAIN", "calls": [
            {"index": 1, "role": "execute-S1", "status": "started"}
        ],
    }
    save_json(run / "records.json", records)
    return run


class RecoverySafety(unittest.TestCase):
    def test_resume_requires_confirmation_for_incomplete_call(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = seed_run(root)
            with self.assertRaisesRegex(ExperimentStopped, "confirm-stopped"):
                Controller(options(root, resume=path))

    def test_explicit_resume_records_recovery_and_resets_leaf(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = seed_run(root)
            controller = Controller(options(root, resume=path, confirm=True))
            try:
                self.assertEqual(controller.state["leaves"]["S1"]["status"], "pending")
                self.assertEqual(controller.records["calls"][0]["status"],
                                 "operator_confirmed_stopped")
                self.assertEqual(len(controller.records["recovery_notes"]), 1)
            finally:
                controller.close()

    def test_simultaneous_resume_refused_by_file_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = seed_run(root)
            owner = Controller(options(root, resume=path, confirm=True))
            try:
                with self.assertRaisesRegex(ExperimentStopped, "Another controller"):
                    Controller(options(root, resume=path, confirm=True))
            finally:
                owner.close()

    def test_completed_run_cannot_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = seed_run(root)
            records = json.loads((path / "records.json").read_text())
            records["outcome"] = "PASS"
            save_json(path / "records.json", records)
            with self.assertRaisesRegex(ExperimentStopped, "already complete"):
                Controller(options(root, resume=path, confirm=True))


if __name__ == "__main__":
    unittest.main()
