# SPDX-License-Identifier: Apache-2.0
"""Non-inference local checks for the paid Luna route."""
import unittest
from unittest.mock import patch
from hiergoal.preflight_luna import check


class LunaPreflight(unittest.TestCase):
    @patch("hiergoal.preflight_luna.shutil.which", return_value=None)
    def test_missing_hermes(self, _):
        with patch("hiergoal.preflight_luna.credential_location", return_value=None):
            result = check()
        self.assertEqual(result["status"], "NOT_READY")

    @patch("hiergoal.preflight_luna.subprocess.run")
    @patch("hiergoal.preflight_luna.shutil.which", return_value="/usr/bin/hermes")
    def test_configured_direct_api(self, _, proc):
        proc.return_value.returncode = 0
        proc.return_value.stdout = "v0.22.2"
        with patch("hiergoal.preflight_luna.credential_location", return_value="~/.hermes/.env"), \
             patch.dict("os.environ", {"OPENAI_BASE_URL": ""}):
            result = check()
        self.assertEqual(result["status"], "READY_FOR_MANUAL_LIVE_TEST")
        self.assertEqual(result["credential_source"], "~/.hermes/.env")

    @patch("hiergoal.preflight_luna.subprocess.run")
    @patch("hiergoal.preflight_luna.shutil.which", return_value="/usr/bin/hermes")
    def test_reject_custom_base_url(self, _, proc):
        proc.return_value.returncode = 0
        proc.return_value.stdout = "v0.22.2"
        with patch("hiergoal.preflight_luna.credential_location", return_value="environment"), \
             patch.dict("os.environ", {"OPENAI_BASE_URL": "https://proxy.invalid/v1"}):
            result = check()
        self.assertEqual(result["status"], "NOT_READY")


if __name__ == "__main__":
    unittest.main()
