# SPDX-License-Identifier: Apache-2.0
"""Readiness checks are non-inference and fail closed."""
import unittest
from unittest.mock import patch

from hiergoal.preflight import readiness


class ReadinessChecks(unittest.TestCase):
    def test_missing_cli_is_not_ready_without_network(self):
        with patch("hiergoal.preflight.shutil.which", return_value=None), \
             patch("hiergoal.preflight.verify_free_profile"):
            output = readiness(check_catalog=False)
        self.assertEqual(output["status"], "NOT_READY")
        self.assertFalse(output["conditions"]["hermes_cli_installed"])
        self.assertFalse(output["catalog_checked"])

    def test_available_cli_and_recognized_profile(self):
        def fake_run(cmd, seconds=20):
            if cmd[-2:] == ["models", "opencode"]:
                return {"ok": True, "exit_code": 0,
                        "stdout": "opencode/glm-5.3-flash-free\n", "error_hint": ""}
            return {"ok": True, "exit_code": 0, "stdout": "version 1.2.3\n",
                    "error_hint": ""}
        with patch("hiergoal.preflight.shutil.which", side_effect=lambda name: "/bin/"+name), \
             patch("hiergoal.preflight.verify_free_profile"), \
             patch("hiergoal.preflight._command", side_effect=fake_run):
            output = readiness(check_catalog=True)
        self.assertEqual(output["status"], "READY_FOR_MANUAL_LIVE_TEST")
        self.assertTrue(output["conditions"]["selected_model_in_current_catalog"])

    def test_not_in_catalog_is_not_ready(self):
        def fake_run(cmd, seconds=20):
            return {"ok": True, "exit_code": 0, "stdout": "opencode/paid-other\n",
                    "error_hint": ""}
        with patch("hiergoal.preflight.shutil.which", side_effect=lambda name: "/bin/"+name), \
             patch("hiergoal.preflight.verify_free_profile"), \
             patch("hiergoal.preflight._command", side_effect=fake_run):
            output = readiness(check_catalog=True)
        self.assertEqual(output["status"], "NOT_READY")
        self.assertFalse(output["conditions"]["selected_model_in_current_catalog"])


if __name__ == "__main__":
    unittest.main()
