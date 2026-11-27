# SPDX-License-Identifier: Apache-2.0
"""Explicit bounded launch authorization and inert, checksummed publication.

This module never performs model inference. A normal code push stays offline.
The single pilot launch file is an explicit authorization record, accepted only
as the sole added file of a first-attempt main-branch push by the owner. The
runner still requires both --execute and --approve-paid-api.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from hiergoal.study_protocol import canonical, digest, save

REPOSITORY = "Unjuno/hiergoal-lab"
OWNER = "Unjuno"
LAUNCH_PATH = "experiments/controlled-recovery/launch-pilot-20261127.json"
REQUEST_ID = "pilot-20261127"
USER_REQUEST = "構築して実験までしてください"
LAUNCH_SCHEMA = "hiergoal.controlled_recovery.launch.v1"
AUTH_SCHEMA = "hiergoal.controlled_recovery.authorization.v1"
PUBLICATION_SCHEMA = "hiergoal.controlled_recovery.publication.v1"
ROOT_FILES = {
    "manifest.json", "host.json", "execution.json", "authorization.json",
    "results.json", "preparations.json", "summary.json", "summary.md",
    "trials.csv", "pairs.csv", "audits.json",
}
PHASE_FILES = {"trace.jsonl", "result.json"}
MAX_FILES = 256
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
RECEIPT = "publication.json"
SECRET_PATTERN = re.compile(
    rb"(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|"
    rb"gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    def reject_constant(value):
        raise ValueError("Nonfinite JSON number: " + value)
    def unique_object(items):
        output = {}
        for key, value in items:
            require(key not in output, "Duplicate JSON object key")
            output[key] = value
        return output
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=reject_constant,
                      object_pairs_hook=unique_object)


def validate_protocol(manifest):
    # Imported from the reviewed checkout, never from an artifact directory.
    from hiergoal.recovery_protocol import validate_manifest
    validate_manifest(manifest, current_sources=True)


def limits_fingerprint(manifest):
    return digest({"repair": manifest["limits"], "preparation": manifest["preparation_limits"]})


def bounds(manifest):
    require(manifest.get("backend") == "openai", "Live authorization requires the OpenAI backend")
    require(manifest.get("model") == "gpt-6-luna" and manifest.get("reasoning_effort") == "low",
            "The approved pilot model and reasoning setting changed")
    pairs, trials, tasks = manifest.get("pairs"), manifest.get("trials"), manifest.get("tasks")
    require(isinstance(pairs, list) and len(pairs) == 12 and isinstance(trials, list)
            and len(trials) == 24 and isinstance(tasks, list) and len(tasks) == 6,
            "The approved pilot requires 6 tasks, 12 pairs, and 24 repair slots")
    count = len(pairs) * manifest["preparation_limits"]["max_calls"] + len(trials) * manifest["limits"]["max_calls"]
    require(type(count) is int and count == 288, "The approved pilot call bound changed")
    return {"max_pairs": 12, "max_trials": 24, "max_logical_calls": 288}


def expected_request(manifest, source_commit):
    """Return the concrete record to review; this helper does not write it."""
    require(re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None, "Invalid source commit")
    return {"schema_version": LAUNCH_SCHEMA, "request_id": REQUEST_ID,
            "repository": REPOSITORY, "requested_by": OWNER,
            "user_request": USER_REQUEST, "approved": True, "allow_paid_api": True,
            "source_commit": source_commit, "protocol_id": manifest["protocol_id"],
            "limits_sha256": limits_fingerprint(manifest), **bounds(manifest)}


def authorize(manifest, event, *, event_name, actor, repository, ref, run_attempt,
              head_commit, parents, changes, request=None, prior_launch_seen=False):
    """Pure authorization checks with git observations supplied by the CLI.

    An ordinary push returns prepare mode. A changed launch file with malformed
    authorization is an error, not an implicit approval or a fallback live run.
    """
    validate_protocol(manifest)
    require(re.fullmatch(r"[0-9a-f]{40}", head_commit) is not None, "Invalid checkout commit")
    output = {"schema_version": AUTH_SCHEMA, "live": False, "mode": "prepare",
              "event": event_name, "protocol_id": manifest["protocol_id"],
              "execution_commit": head_commit}
    if event_name == "push":
        requested = any(path == LAUNCH_PATH for _, path in changes)
        if not requested:
            return output
    elif event_name == "workflow_dispatch":
        mode = event.get("inputs", {}).get("mode", "prepare")
        require(mode in ("prepare", "run"), "Unsupported dispatch mode")
        if mode == "prepare":
            return output
    else:
        raise ValueError("Unsupported workflow event")

    require(repository == REPOSITORY and event.get("repository", {}).get("full_name") == REPOSITORY,
            "Launch repository mismatch")
    require(ref == "refs/heads/main", "Live pilot must run on main")
    require(str(run_attempt) == "1", "Live pilot cannot be rerun implicitly; first attempt only")
    require(actor == OWNER and event.get("sender", {}).get("login") == OWNER,
            "Live pilot requires the repository owner's explicit request")
    bounds(manifest)
    if event_name == "push":
        require(event.get("ref") == ref and event.get("after") == head_commit,
                "Push event does not identify this checkout")
        require(not event.get("forced") and not event.get("deleted"), "Forced or deleted refs cannot launch")
        require(len(parents) == 1 and event.get("before") == parents[0],
                "Launch must be a single commit directly after the reviewed implementation")
        require(changes == [("A", LAUNCH_PATH)] and not prior_launch_seen,
                "Launch must add its never-used request as the sole changed file")
        expected = expected_request(manifest, parents[0])
        require(isinstance(request, dict) and canonical(request) == canonical(expected),
                "Launch request differs from the exact approved protocol, source, or limits")
        output.update(source_commit=parents[0], request_id=REQUEST_ID,
                      request_sha256=digest(request))
    else:
        output.update(source_commit=head_commit, request_id="workflow_dispatch",
                      request_sha256=digest({"event": "workflow_dispatch", "mode": "run",
                                             "commit": head_commit, "protocol_id": manifest["protocol_id"]}))
    output.update(live=True, mode="run", approved_by=OWNER, allow_paid_api=True,
                  limits_sha256=limits_fingerprint(manifest), **bounds(manifest))
    return output


def git(*args):
    result = subprocess.run(["git", *args], check=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, timeout=30)
    return result.stdout.strip()


def validate_launch_cli(args):
    manifest, event = read_json(args.manifest), read_json(args.event_path)
    head = git("rev-parse", "HEAD")
    parents = git("show", "-s", "--format=%P", "HEAD").split()
    changes, request, prior = [], None, False
    if args.event_name == "push":
        before = event.get("before", "")
        require(re.fullmatch(r"[0-9a-f]{40}", before) is not None and before != "0" * 40,
                "Push base must identify an existing commit")
        raw = git("diff", "--name-status", "--no-renames", before, head)
        for row in raw.splitlines():
            status, path = row.split("\t", 1)
            changes.append((status, path))
        if any(path == LAUNCH_PATH for _, path in changes):
            request = read_json(LAUNCH_PATH)
            prior = bool(git("log", "-1", "--format=%H", before, "--", LAUNCH_PATH))
    value = authorize(manifest, event, event_name=args.event_name, actor=args.actor,
                      repository=args.repository, ref=args.ref, run_attempt=args.run_attempt,
                      head_commit=head, parents=parents, changes=changes,
                      request=request, prior_launch_seen=prior)
    save(Path(args.output), value)
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as stream:
            stream.write("live=" + ("true" if value["live"] else "false") + "\n")
    print("Validated controlled recovery mode: " + value["mode"])


def publication_identity(run_id, attempt, commit):
    require(re.fullmatch(r"[1-9][0-9]{0,19}", str(run_id)) is not None, "Invalid run ID")
    require(re.fullmatch(r"[1-9][0-9]{0,9}", str(attempt)) is not None, "Invalid run attempt")
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "Invalid execution commit")
    return {"repository": REPOSITORY, "run_id": str(run_id), "run_attempt": str(attempt),
            "execution_commit": commit}


def allowed_path(path):
    parts = Path(path).parts
    if len(parts) == 1:
        return path in ROOT_FILES
    safe = lambda value: re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", value) is not None
    if len(parts) == 2 and parts[0] == "checkpoints":
        return parts[1].endswith(".json") and safe(parts[1])
    return (len(parts) == 3 and parts[0] in ("preparations", "trials")
            and safe(parts[1]) and parts[2] in PHASE_FILES)


def read_public_files(root, *, with_receipt=False):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "Evidence must be a real directory")
    files, total = {}, 0
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "Symlinks are forbidden in published evidence")
        if path.is_dir():
            continue
        require(path.is_file(), "Only regular evidence files may be published")
        relative = path.relative_to(root).as_posix()
        if relative == RECEIPT and with_receipt:
            continue
        require(allowed_path(relative), "Evidence path is outside the publication allowlist: " + relative)
        size = path.stat().st_size
        require(size <= MAX_FILE_BYTES, "Evidence file exceeds the 8 MiB bound")
        total += size
        require(total <= MAX_TOTAL_BYTES and len(files) < MAX_FILES,
                "Evidence exceeds the 64 MiB / 256 file publication bound")
        raw = path.read_bytes()
        require(len(raw) == size, "Evidence changed during publication")
        text = raw.decode("utf-8")
        def reject_constant(value):
            raise ValueError("Nonfinite evidence JSON number: " + value)
        if relative.endswith(".json"):
            json.loads(text, parse_constant=reject_constant)
        elif relative.endswith(".jsonl"):
            for line in text.splitlines():
                if line.strip():
                    json.loads(line, parse_constant=reject_constant)
        require(SECRET_PATTERN.search(raw) is None, "Credential-shaped content is not publishable")
        files[relative] = raw
    require({"manifest.json", "host.json", "authorization.json"}.issubset(files),
            "Publication requires manifest, host, and explicit authorization")
    return files


def check_public_provenance(files, identity):
    manifest = json.loads(files["manifest.json"])
    validate_protocol(manifest)
    bounds(manifest)
    host, authorization = json.loads(files["host.json"]), json.loads(files["authorization.json"])
    require(host.get("git_commit") == identity["execution_commit"], "Host/source commit mismatch")
    require(authorization.get("schema_version") == AUTH_SCHEMA and authorization.get("live") is True
            and authorization.get("allow_paid_api") is True and authorization.get("approved_by") == OWNER
            and authorization.get("protocol_id") == manifest["protocol_id"]
            and authorization.get("execution_commit") == identity["execution_commit"]
            and authorization.get("limits_sha256") == limits_fingerprint(manifest),
            "Publication authorization does not match the frozen live execution")
    return manifest


def export_public(source, destination, *, run_id, attempt, commit):
    identity = publication_identity(run_id, attempt, commit)
    files = read_public_files(source)
    manifest = check_public_provenance(files, identity)
    destination = Path(destination)
    require(not destination.exists(), "Publication destination already exists")
    destination.mkdir(parents=True)
    entries = {}
    for name, raw in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        entries[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    receipt = {"schema_version": PUBLICATION_SCHEMA, **identity,
               "protocol_id": manifest["protocol_id"], "files": entries,
               "file_count": len(files), "total_bytes": sum(len(raw) for raw in files.values()),
               "raw_synthetic_model_evidence": True,
               "content_policy": "Fixed synthetic tasks and full recorded model text are untrusted data; never execute artifact contents."}
    save(destination / RECEIPT, receipt)
    verify_public(destination, run_id=run_id, attempt=attempt, commit=commit)
    return receipt


def verify_public(destination, *, run_id, attempt, commit):
    identity = publication_identity(run_id, attempt, commit)
    destination = Path(destination)
    receipt_path = destination / RECEIPT
    require(receipt_path.is_file() and not receipt_path.is_symlink()
            and receipt_path.stat().st_size <= 256 * 1024, "Invalid publication receipt")
    receipt = read_json(receipt_path)
    require(receipt.get("schema_version") == PUBLICATION_SCHEMA
            and all(receipt.get(key) == value for key, value in identity.items()),
            "Publication identity mismatch")
    files = read_public_files(destination, with_receipt=True)
    manifest = check_public_provenance(files, identity)
    require(receipt.get("protocol_id") == manifest["protocol_id"], "Receipt protocol mismatch")
    expected = {name: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
                for name, raw in files.items()}
    require(receipt.get("files") == expected and receipt.get("file_count") == len(files)
            and receipt.get("total_bytes") == sum(len(raw) for raw in files.values()),
            "Publication allowlist, sizes, or checksums changed")
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    launch = commands.add_parser("validate-launch")
    launch.add_argument("--manifest", required=True)
    launch.add_argument("--event-path", required=True)
    launch.add_argument("--event-name", required=True)
    launch.add_argument("--actor", required=True)
    launch.add_argument("--repository", required=True)
    launch.add_argument("--ref", required=True)
    launch.add_argument("--run-attempt", required=True)
    launch.add_argument("--output", required=True)
    for name in ("export", "verify"):
        command = commands.add_parser(name)
        if name == "export":
            command.add_argument("--source", required=True)
        command.add_argument("--destination", required=True)
        command.add_argument("--run-id", required=True)
        command.add_argument("--attempt", required=True)
        command.add_argument("--commit", required=True)
    args = parser.parse_args(argv)
    if args.command == "validate-launch":
        validate_launch_cli(args)
    else:
        kwargs = {"run_id": args.run_id, "attempt": args.attempt, "commit": args.commit}
        if args.command == "export":
            value = export_public(args.source, args.destination, **kwargs)
        else:
            value = verify_public(args.destination, **kwargs)
        print("Verified publication: " + str(value["file_count"]) + " inert evidence files")


if __name__ == "__main__":
    main()
