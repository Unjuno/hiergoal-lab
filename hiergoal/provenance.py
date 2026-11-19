# SPDX-License-Identifier: Apache-2.0
"""Content-addressed experimental protocol and non-sensitive host metadata."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROTOCOL_PATHS = (
    "hiergoal/core.py",
    "hiergoal/cases.py",
    "hiergoal/benchmark.py",
    "hiergoal/controller.py",
    "scripts/stream_report.py",
    "evaluation/test_release.py",
    "fixtures/ledger_release/README.md",
    "fixtures/ledger_release/miniledger/__init__.py",
    "fixtures/ledger_release/miniledger/parse.py",
    "fixtures/ledger_release/miniledger/summary.py",
    "fixtures/ledger_release/miniledger/__main__.py",
    "fixtures/ledger_release/tests/test_visible.py",
    "scripts/setup_opencode_free.sh",
)


def protocol_manifest(root: Path) -> dict:
    """Hash source and evaluator files; refuse if any are missing."""
    paths = {}
    for name in PROTOCOL_PATHS:
        file = root / name
        if not file.is_file():
            raise ValueError("Experiment protocol file missing: " + name)
        paths[name] = hashlib.sha256(file.read_bytes()).hexdigest()
    canonical = json.dumps(paths, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "protocol_id": hashlib.sha256(canonical).hexdigest(),
        "source_file_sha256": paths,
    }


def _git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                                capture_output=True, text=True, timeout=5)
        value = result.stdout.strip()
        return value if result.returncode == 0 and len(value) == 40 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def capture_provenance(root: Path) -> dict:
    result = protocol_manifest(root)
    result.update({
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(root),
        "host_os": platform.system(),
        "host_architecture": platform.machine(),
        "python_version": sys.version.split()[0],
        "platform_release": platform.release(),
    })
    return result
