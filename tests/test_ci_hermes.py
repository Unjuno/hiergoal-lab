# SPDX-License-Identifier: Apache-2.0
"""Exercise real subprocess cleanup without a provider or network request."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "ci_hermes.py"
FAKE = r'''#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys, time
home = pathlib.Path(os.environ["HERMES_HOME"])
if sys.argv[1:] == ["gateway", "stop", "--yes"]:
    (home / "stop.json").write_text(json.dumps({"home": str(home)}))
    raise SystemExit(int(os.environ.get("FAKE_STOP_CODE", "0")))
(home / "start.json").write_text(json.dumps({
    "home": str(home), "argv": sys.argv[1:],
    "inherited_overrides": any(name in os.environ for name in
        ("HERMES_PROFILE", "HERMES_PROFILE_NAME", "HERMES_TUI_GATEWAY_URL"))}))
if os.environ.get("FAKE_DETACHED"):
    program = "import ctypes, pathlib, time; "
    if os.environ.get("FAKE_CHILD_NONDUMPABLE"):
        program += "assert ctypes.CDLL(None).prctl(4, 0, 0, 0, 0) == 0; "
    program += "pathlib.Path(" + repr(str(home / "child-ready")) + ").write_text('ready'); time.sleep(30)"
    detached = subprocess.Popen([sys.executable, "-c", program],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
    (home / "detached.pid").write_text(str(detached.pid))
    deadline = time.monotonic() + 3
    while not (home / "child-ready").exists() and time.monotonic() < deadline:
        time.sleep(0.01)
print(json.dumps({"type": "result", "text": "visible-stream"}), flush=True)
if os.environ.get("FAKE_SLEEP"):
    time.sleep(30)
raise SystemExit(int(os.environ.get("FAKE_EXIT_CODE", "0")))
'''


@unittest.skipUnless(sys.platform.startswith("linux"), "The hosted CI adapter requires Linux")
class CiHermesAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fake = self.root / "real-hermes"
        self.fake.write_text(FAKE, encoding="utf-8")
        self.fake.chmod(0o755)
        self.homes = self.root / "private-homes"
        self.env = os.environ.copy()
        self.env.update({"HIERGOAL_REAL_HERMES": str(self.fake),
                         "HIERGOAL_CI_HOMES": str(self.homes),
                         "HIERGOAL_HERMES_TIMEOUT_SECONDS": "3"})
        self.env.pop("OPENAI_API_KEY", None)
        self.command = [sys.executable, str(WRAPPER), "chat", "--source", "tool"]

    def invoke(self, **environment):
        return subprocess.run(self.command, env={**self.env, **environment},
                              capture_output=True, text=True, timeout=15)

    def metadata(self):
        return [json.loads(path.read_text())
                for path in sorted(self.homes.glob("call-*/ci-cleanup.json"))]

    def test_stream_forwarding_and_fresh_home_for_each_invocation(self):
        for _ in range(2):
            result = self.invoke(HERMES_HOME="/must-not-be-used", HERMES_PROFILE="inherited",
                                 HERMES_PROFILE_NAME="inherited",
                                 HERMES_TUI_GATEWAY_URL="wss://must-not-be-used.invalid")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["text"], "visible-stream")
        homes = list(self.homes.glob("call-*"))
        self.assertEqual(len(homes), 2)
        for home in homes:
            start = json.loads((home / "start.json").read_text())
            stop = json.loads((home / "stop.json").read_text())
            self.assertEqual(start["home"], stop["home"])
            self.assertEqual(start["home"], str(home))
            self.assertFalse(start["inherited_overrides"])
            self.assertEqual(start["argv"], ["chat", "--source", "tool"])
            self.assertEqual(home.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(item["cleanup_confirmed"] for item in self.metadata()))

    def test_timeout_still_stops_the_detached_gateway(self):
        result = self.invoke(FAKE_SLEEP="1", HIERGOAL_HERMES_TIMEOUT_SECONDS="1")
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertEqual(len(list(self.homes.glob("call-*/stop.json"))), 1)
        item = self.metadata()[0]
        self.assertTrue(item["timed_out"])
        self.assertTrue(item["cleanup_confirmed"])

    def test_sigterm_still_stops_the_detached_gateway(self):
        process = subprocess.Popen(self.command, env={**self.env, "FAKE_SLEEP": "1"},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not list(self.homes.glob("call-*/start.json")):
                if time.monotonic() >= deadline:
                    self.fail("Fake Hermes did not start")
                time.sleep(0.02)
            process.send_signal(signal.SIGTERM)
            _, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 128 + signal.SIGTERM, stderr)
            self.assertTrue(self.metadata()[0]["cleanup_confirmed"])
            self.assertEqual(len(list(self.homes.glob("call-*/stop.json"))), 1)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_cleanup_failure_prevents_success(self):
        result = self.invoke(FAKE_STOP_CODE="1")
        self.assertEqual(result.returncode, 70)
        self.assertFalse(self.metadata()[0]["cleanup_confirmed"])

    def test_detached_worker_is_stopped_even_when_stop_cli_leaves_it_alive(self):
        try:
            result = self.invoke(FAKE_DETACHED="1")
            self.assertEqual(result.returncode, 0, result.stderr)
            item = self.metadata()[0]
            self.assertEqual(item["gateway_stop_returncode"], 0)
            self.assertTrue(item["cleanup_confirmed"])
            self.assertEqual(item["lingering_process_count"], 0)
            self.assertEqual(item["scoped_processes_terminated"], 1)
        finally:
            for pid_file in self.homes.glob("call-*/detached.pid"):
                try:
                    os.kill(int(pid_file.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_original_nonzero_exit_preserved_and_cleanup_runs(self):
        result = self.invoke(FAKE_EXIT_CODE="7")
        self.assertEqual(result.returncode, 7)
        self.assertTrue(self.metadata()[0]["cleanup_confirmed"])

    def test_unrelated_unreadable_process_does_not_block_or_receive_cleanup(self):
        ready = self.root / "foreign-ready"
        foreign = subprocess.Popen([
            sys.executable, "-c",
            "import ctypes, pathlib, time; "
            "assert ctypes.CDLL(None).prctl(4, 0, 0, 0, 0) == 0; "
            f"pathlib.Path({str(ready)!r}).write_text('ready'); time.sleep(30)",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 3
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(ready.exists())
            result = self.invoke()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIsNone(foreign.poll(), "Cleanup touched an unrelated process")
            item = self.metadata()[0]
            self.assertTrue(item["cleanup_confirmed"])
            self.assertEqual(item["process_scope"], "owned_descendants")
        finally:
            foreign.terminate()
            foreign.wait(timeout=3)

    def test_unreadable_owned_detached_child_is_still_stopped(self):
        result = self.invoke(FAKE_DETACHED="1", FAKE_CHILD_NONDUMPABLE="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        item = self.metadata()[0]
        self.assertTrue(item["cleanup_confirmed"])
        self.assertEqual(item["scoped_processes_terminated"], 1)
        self.assertEqual(item["lingering_process_count"], 0)
        child_pid = int(next(self.homes.glob("call-*/detached.pid")).read_text())
        self.assertFalse((Path("/proc") / str(child_pid)).exists())

    def test_missing_private_home_fails_before_starting_hermes(self):
        env = self.env.copy()
        env.pop("HIERGOAL_CI_HOMES")
        result = subprocess.run(self.command, env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.homes.exists())


if __name__ == "__main__":
    unittest.main()
