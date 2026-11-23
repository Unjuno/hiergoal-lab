#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run one Hermes invocation in a private home and stop its detached gateway.

Linux CI adapter, not a general sandbox. Stdout is reserved for Hermes JSONL.
No API keys, prompts, stderr, or environment contents enter cleanup metadata.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


def _terminate_group(process: subprocess.Popen) -> None:
    """Terminate only the new session created for this specific child."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    # The group leader exiting does not prove that its tool children exited.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=3)


def _home_processes(home: Path) -> list[int] | None:
    """Inspect only liveness; never return or log environment contents.

The generated home is unique to this invocation. Checking its exact value also
detects a detached gateway after its launching CLI has exited. Linux /proc is
required: failure to inspect a process owned by this user is not proof of stop.
"""
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return None
    marker = ("HERMES_HOME=" + str(home)).encode()
    found = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            if entry.stat().st_uid != os.geteuid():
                continue
            # /proc/PID/stat's comm can contain spaces and parentheses.
            state = (entry / "stat").read_text().rsplit(")", 1)[1].split()[0]
            if state == "Z":
                continue
            if marker in (entry / "environ").read_bytes().split(b"\0"):
                found.append(int(entry.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (OSError, IndexError):
            return None
    return found


def _signal_home_process(pid: int, home: Path, sig: int) -> bool:
    """Signal a scoped process through a pidfd, avoiding PID-reuse races."""
    descriptor = None
    try:
        descriptor = os.pidfd_open(pid)
        marker = ("HERMES_HOME=" + str(home)).encode()
        if marker not in (Path("/proc") / str(pid) / "environ").read_bytes().split(b"\0"):
            return False
        signal.pidfd_send_signal(descriptor, sig)
        return True
    except (OSError, AttributeError):
        # The final liveness check will reject any process we could not stop.
        return False
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _stop_home_processes(home: Path) -> tuple[list[int] | None, int]:
    """Drain private workers left behind by an otherwise successful stop CLI.

    A Hermes managed worker can briefly outlive `gateway stop`. Nothing with
    this random home's marker belongs to another invocation. Bound both the
    graceful drain and escalation, and never target a PID by name alone.
    """
    terminated = set()
    for sig, grace_seconds in ((signal.SIGTERM, 3), (signal.SIGKILL, 2)):
        signalled_in_phase = set()
        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            remaining = _home_processes(home)
            if remaining == []:
                return remaining, len(terminated)
            for pid in remaining or []:
                if pid not in signalled_in_phase and _signal_home_process(pid, home, sig):
                    terminated.add(pid)
                    signalled_in_phase.add(pid)
            # During process exit, /proc/environ can briefly become unreadable
            # before /proc/stat identifies a zombie. Retry within the bound.
            time.sleep(0.05)
    return _home_processes(home), len(terminated)


def _private_home_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    env["HERMES_GATEWAY_NO_SUPERVISE"] = "1"
    for name in ("HERMES_PROFILE", "HERMES_PROFILE_NAME", "HERMES_TUI_GATEWAY_URL"):
        env.pop(name, None)
    return env


def cleanup_home(binary: Path, home: Path) -> dict:
    """Stop processes belonging to one caller-owned private CI home only.

    The caller must obtain `home` from its dedicated private homes directory,
    never from untrusted run data or an existing user's Hermes installation.
    This helper can also finish interrupted cleanup from a workflow's final
    step. It makes no inference request and never targets an entire host.
    """
    result = {
        "gateway_stop_returncode": None,
        "gateway_stop_timed_out": False,
        "cleanup_confirmed": False,
        "scoped_processes_terminated": 0,
        "lingering_process_count": None,
    }
    if (not binary.is_absolute() or not binary.is_file()
            or binary.resolve() == Path(__file__).resolve()
            or not home.is_absolute() or not home.is_dir() or home.is_symlink()
            or not home.name.startswith("call-")):
        return result
    home = home.resolve()
    stop_process = None
    try:
        stop_process = subprocess.Popen(
            [str(binary), "gateway", "stop", "--yes"], env=_private_home_env(home),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
        try:
            result["gateway_stop_returncode"] = stop_process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            result["gateway_stop_timed_out"] = True
            _terminate_group(stop_process)
        remaining, terminated = _stop_home_processes(home)
        result["scoped_processes_terminated"] = terminated
        result["lingering_process_count"] = len(remaining) if remaining is not None else None
        result["cleanup_confirmed"] = result["gateway_stop_returncode"] == 0 and remaining == []
    except OSError:
        pass
    finally:
        if stop_process is not None and stop_process.poll() is None:
            _terminate_group(stop_process)
    return result


def _write_metadata(home: Path, data: dict) -> None:
    # Replacing the destination avoids following a pre-existing file symlink.
    fd, filename = tempfile.mkstemp(prefix=".cleanup-", dir=home)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
        os.replace(filename, home / "ci-cleanup.json")
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


def run(arguments: list[str]) -> int:
    try:
        binary = Path(os.environ["HIERGOAL_REAL_HERMES"])
        base = Path(os.environ["HIERGOAL_CI_HOMES"])
        timeout = int(os.environ.get("HIERGOAL_HERMES_TIMEOUT_SECONDS", "540"))
        if (not arguments or not binary.is_absolute() or not base.is_absolute()
                or not binary.is_file() or not os.access(binary, os.X_OK)
                or binary.resolve() == Path(__file__).resolve()
                or base.is_symlink() or not 1 <= timeout <= 540):
            raise ValueError
        base = base.resolve()
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        home = Path(tempfile.mkdtemp(prefix="call-", dir=base))
    except (KeyError, ValueError, OSError):
        print("CI Hermes adapter: invalid executable, private-home directory or timeout.", file=sys.stderr)
        return 2

    env = _private_home_env(home)
    received_signal = None

    def interrupted(signum, _frame):
        nonlocal received_signal
        received_signal = received_signal or signum

    previous_handlers = {sig: signal.signal(sig, interrupted)
                         for sig in (signal.SIGTERM, signal.SIGINT)}
    started = time.monotonic()
    process = None
    timed_out = False
    returncode = 70
    metadata = {"schema_version": "1.0", "status": "STARTED"}
    try:
        _write_metadata(home, metadata)
        process = subprocess.Popen(
            [str(binary), *arguments], env=env, stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = started + timeout
        while True:
            if received_signal is not None:
                returncode = 128 + received_signal
                _terminate_group(process)
                break
            remaining_time = deadline - time.monotonic()
            if remaining_time <= 0:
                timed_out, returncode = True, 124
                _terminate_group(process)
                break
            try:
                returncode = process.wait(timeout=min(0.25, remaining_time))
                break
            except subprocess.TimeoutExpired:
                continue
    except OSError:
        print("CI Hermes adapter: invocation could not be started or recorded.", file=sys.stderr)
        returncode = 70
    finally:
        if process is not None and process.poll() is None:
            _terminate_group(process)
        # stream-json's gateway is detached from the CLI process group. Stop it
        # explicitly, scoped to the NEW home, including after CLI failure.
        try:
            cleanup = cleanup_home(binary, home)
        finally:
            for sig, previous in previous_handlers.items():
                signal.signal(sig, previous)
        if received_signal is not None:
            returncode = 128 + received_signal
        elif returncode < 0:
            returncode = 128 - returncode
        if not cleanup["cleanup_confirmed"] and returncode == 0:
            returncode = 70
        metadata.update({
            "status": "COMPLETE" if cleanup["cleanup_confirmed"] else "CLEANUP_UNCERTAIN",
            "returncode": returncode,
            "timed_out": timed_out,
            "received_signal": received_signal,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            **cleanup,
        })
        try:
            _write_metadata(home, metadata)
        except OSError:
            returncode = returncode or 70
        if not cleanup["cleanup_confirmed"]:
            print("CI Hermes adapter: gateway cleanup could not be confirmed; stop the experiment.",
                  file=sys.stderr)
    return returncode


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
