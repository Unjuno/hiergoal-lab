# SPDX-License-Identifier: Apache-2.0
"""Read-only readiness check for direct OpenAI Luna API.

No model prompt; no key contents ever returned or printed. Status means
local prerequisites appear present, not that actual API access works.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def credential_location() -> str | None:
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return "OPENAI_API_KEY environment variable"
    env_file = Path.home() / ".hermes" / ".env"
    try:
        source = env_file.read_text(encoding="utf-8")
    except OSError:
        return None
    if re.search(r'(?m)^\s*(?:export\s+)?OPENAI_API_KEY\s*=\s*["\x27]?\S+', source):
        return "~/.hermes/.env"
    return None


def check() -> dict:
    binary = shutil.which("hermes")
    cred = credential_location()
    base = os.environ.get("OPENAI_BASE_URL", "").strip()
    allowed = ("", "https://api.openai.com/v1", "https://api.openai.com/v1/")
    direct = base in allowed
    if direct:
        # Hermes loads its own .env even with --ignore-user-config.
        # A hidden custom endpoint there would undermine direct-API attribution.
        env_path = Path.home() / ".hermes" / ".env"
        try:
            env_lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            env_lines = []
        for line in env_lines:
            match = re.match(r"^\s*(?:export\s+)?OPENAI_BASE_URL\s*=\s*(.*?)\s*$", line)
            if match:
                declared = match.group(1).strip().strip(chr(34) + chr(39))
                if declared not in allowed:
                    direct = False
                    break
    version, version_ok = None, False
    if binary:
        try:
            proc = subprocess.run([binary, "--version"], capture_output=True,
                                  text=True, timeout=12)
            version_ok = proc.returncode == 0
            version = proc.stdout.strip()[:120] if version_ok else None
        except (OSError, subprocess.TimeoutExpired):
            pass
    conditions = {
        "python_3_11_or_newer": sys.version_info >= (3, 11),
        "hermes_cli": bool(binary),
        "hermes_version_responds": version_ok,
        "openai_api_credential_present": cred is not None,
        "direct_openai_endpoint": direct,
    }
    return {
        "status": "READY_FOR_MANUAL_LIVE_TEST" if all(conditions.values()) else "NOT_READY",
        "backend": "luna", "model": "gpt-6-luna", "provider": "openai-api",
        "credential_source": cred, "hermes_version": version,
        "checks": conditions,
        "warning": (
            "No paid request was made. API access, billing, actual spending "
            "and live Hermes tool execution remain unverified."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Luna/API readiness, no inference")
    parser.parse_args()
    result = check()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "READY_FOR_MANUAL_LIVE_TEST" else 2)


if __name__ == "__main__":
    main()
