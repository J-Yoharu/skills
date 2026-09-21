#!/usr/bin/env python3
"""Optional local verification. Does not run gates, access networks, or write product code.

Python 3.10+; standard library and Git only. Exit codes: 0 = valid/unchanged,
1 = changed snapshot, 2 = error or unverifiable input.
"""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any


class VerificationError(ValueError):
    """Invalid input or a condition preventing safe verification."""


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"Unreadable/invalid JSON at {path}: {exc}") from exc


def git(repo: Path, *args: str, missing_ok: bool = False) -> bytes:
    # Inherited GIT_DIR/INDEX_FILE must not silently redirect the target checkout.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"})
    try:
        result = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-C", str(repo), *args],
            capture_output=True, timeout=30, check=False, env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VerificationError(f"Could not query Git: {exc}") from exc
    if result.returncode == 0:
        return result.stdout
    if missing_ok and result.returncode == 1:
        return b""
    # Do not dump logs that may contain private configuration data.
    raise VerificationError(f"Git {args[0]} failed (exit={result.returncode}).")


def repo_root(repo: Path) -> Path:
    root = git(repo, "rev-parse", "--show-toplevel").decode("utf-8", "surrogateescape").strip()
    return Path(root).resolve()


def metadata_dir(repo: Path) -> Path:
    value = os.fsdecode(git(repo, "rev-parse", "--git-common-dir")).strip()
    path = Path(value)
    return (path if path.is_absolute() else repo / path).resolve()


def signature(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def file_record(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.parent.resolve().is_relative_to(root):
        raise VerificationError(f"Path traverses a symlink outside the checkout: {relative}")
    try:
        initial = path.lstat()
    except FileNotFoundError:
        return {"kind": "missing"}
    if stat.S_ISLNK(initial.st_mode):
        value = {"kind": "symlink", "target": os.readlink(path)}
    elif stat.S_ISREG(initial.st_mode):
        h = hashlib.sha256()
        # O_NOFOLLOW prevents a symlink-swap race where the platform supports it.
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
            with os.fdopen(descriptor, "rb") as stream:
                if signature(os.fstat(stream.fileno())) != signature(initial):
                    raise VerificationError(f"File changed while being read: {relative}")
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(block)
                if signature(os.fstat(stream.fileno())) != signature(initial):
                    raise VerificationError(f"File changed while being read: {relative}")
        except OSError as exc:
            raise VerificationError(f"Could not read a stable file: {relative}") from exc
        value = {"kind": "file", "sha256": h.hexdigest(),
                 "executable": bool(initial.st_mode & 0o111)}
    else:
        raise VerificationError(
            f"Directory/nested repository/special file is not covered: {relative}. "
            "Verify that checkout separately."
        )
    try:
        stable = signature(path.lstat()) == signature(initial)
    except FileNotFoundError:
        stable = False
    if not stable:
        raise VerificationError(f"File changed while being read: {relative}")
    return value


def snapshot(repo: Path, context: Any = None) -> dict[str, Any]:
    root = repo_root(repo)
    head = git(root, "rev-parse", "--verify", "-q", "HEAD", missing_ok=True).strip().decode() or None
    index_raw = git(root, "ls-files", "--stage", "-z")
    untracked_raw = git(root, "ls-files", "--others", "--exclude-standard", "-z")
    entries: list[dict[str, str]] = []
    paths: set[str] = set()
    for entry in index_raw.split(b"\0"):
        if not entry:
            continue
        header, raw_path = entry.split(b"\t", 1)
        mode, oid, stage = header.decode("ascii").split()
        relative = os.fsdecode(raw_path)
        if stage != "0":
            raise VerificationError(f"Index contains an unresolved conflict: {relative}")
        if mode == "160000":
            raise VerificationError(f"Submodule requires its own snapshot: {relative}")
        entries.append({"path": relative, "mode": mode, "oid": oid})
        paths.add(relative)
    paths.update(os.fsdecode(p) for p in untracked_raw.split(b"\0") if p)
    records = {p: file_record(root, p) for p in sorted(paths)}
    if index_raw != git(root, "ls-files", "--stage", "-z") or untracked_raw != git(
        root, "ls-files", "--others", "--exclude-standard", "-z"
    ):
        raise VerificationError("Index/file list changed during the snapshot.")
    final_head = git(root, "rev-parse", "--verify", "-q", "HEAD", missing_ok=True).strip().decode() or None
    if head != final_head:
        raise VerificationError("HEAD changed during the snapshot.")
    payload = {"repo": str(root), "head": head,
               "index": sorted(entries, key=lambda x: x["path"]),
               "files": records, "context": context}
    return {"schema_version": 1, "captured_at": datetime.now(timezone.utc).isoformat(),
            "fingerprint": digest(payload), "payload": payload}


def compare(repo: Path, previous: Any, context: Any = None) -> dict[str, Any]:
    if not isinstance(previous, dict) or previous.get("schema_version") != 1:
        raise VerificationError("Invalid snapshot schema.")
    payload = previous.get("payload")
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), dict):
        raise VerificationError("Invalid snapshot payload.")
    if previous.get("fingerprint") != digest(payload):
        raise VerificationError("Inconsistent snapshot: fingerprint does not match payload.")
    current = snapshot(repo, context)
    old_files, new_files = payload["files"], current["payload"]["files"]
    changed = sorted(p for p in set(old_files) | set(new_files)
                     if old_files.get(p) != new_files.get(p))
    return {"same": current["fingerprint"] == previous["fingerprint"],
            "previous": previous["fingerprint"], "current": current["fingerprint"],
            "changed_files": changed,
            "context_changed": payload.get("context") != current["payload"]["context"],
            "head_changed": payload.get("head") != current["payload"]["head"],
            "index_changed": payload.get("index") != current["payload"]["index"]}


STATUSES = {"pending", "running", "implemented", "reviewing", "verified",
            "integrated", "delivered", "blocked", "paused"}
DEPENDENCY_SATISFIED = {"integrated", "delivered"}
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")


def validate_control(document: dict[str, Any], tasks: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    """Check the declared pause latch; never observe processes or grant permission."""
    control = document.get("control", {"state": "running", "drain_units": []})
    if not isinstance(control, dict):
        raise VerificationError("control must be an object; absence is accepted only for legacy data.")
    state = control.get("state")
    if not isinstance(state, str) or state not in {"running", "draining", "paused", "interrupted"}:
        raise VerificationError("Invalid control.state.")
    frozen = control.get("drain_units", [])
    if not isinstance(frozen, list) or not all(isinstance(i, str) for i in frozen):
        raise VerificationError("control.drain_units must be a list of IDs.")
    if len(frozen) != len(set(frozen)) or any(i not in tasks for i in frozen):
        raise VerificationError("control.drain_units contains a duplicate or unknown ID.")
    if state != "running":
        if "drain_units" not in control:
            raise VerificationError("Stopped control requires drain_units, even when empty.")
        for field in ("reason", "requested_at"):
            if not isinstance(control.get(field), str) or not control[field].strip():
                raise VerificationError(f"Stopped control requires {field}.")
        try:
            timestamp = datetime.fromisoformat(control["requested_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise VerificationError("requested_at must be an ISO 8601 timestamp.") from exc
        if timestamp.tzinfo is None:
            raise VerificationError("requested_at requires a timezone.")
    # In this schema integrated also covers verified local work in its target tree.
    remaining = [i for i in frozen if tasks[i]["status"] not in DEPENDENCY_SATISFIED]
    started = {i for i, task in tasks.items()
               if task["status"] in {"running", "implemented", "reviewing", "verified"}}
    if state == "draining" and started - set(frozen):
        raise VerificationError("Active unit outside the frozen drain set.")
    if state == "paused":
        if remaining or started or any(t["status"] == "paused" for t in tasks.values()):
            raise VerificationError("A clean pause requires stable boundaries; a unit is incomplete.")
        for field in ("active_agents", "active_processes"):
            if document.get(field) != []:
                raise VerificationError(f"A clean pause requires {field} to be empty and confirmed.")
    return state, remaining


def validate_plan(document: Any, until: str | None = None) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise VerificationError("Plan requires schema_version 1.")
    for key in ("run_id", "objective"):
        if not isinstance(document.get(key), str) or not document[key].strip():
            raise VerificationError(f"Plan requires {key} to be nonempty.")
    items = document.get("tasks")
    if not isinstance(items, list) or not items:
        raise VerificationError("tasks must be a nonempty list.")
    tasks: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise VerificationError("Each task must be an object.")
        ident = item.get("id")
        if not isinstance(ident, str) or not ID.fullmatch(ident):
            raise VerificationError("Invalid task ID.")
        if ident in tasks:
            raise VerificationError(f"Duplicate ID: {ident}")
        if not isinstance(item.get("status"), str) or item["status"] not in STATUSES:
            raise VerificationError(f"Invalid state: {ident}")
        if not isinstance(item.get("repo"), str) or not item["repo"].strip():
            raise VerificationError(f"Invalid repository/scope: {ident}")
        dependencies = item.get("depends_on")
        if not isinstance(dependencies, list) or not all(isinstance(d, str) for d in dependencies):
            raise VerificationError(f"depends_on must be a list of IDs: {ident}")
        if len(dependencies) != len(set(dependencies)):
            raise VerificationError(f"Duplicate dependency: {ident}")
        scope = item.get("write_scope", [])
        if not isinstance(scope, list) or not all(isinstance(p, str) and p for p in scope):
            raise VerificationError(f"Invalid write_scope: {ident}")
        tasks[ident] = item
    incoming = {i: len(t["depends_on"]) for i, t in tasks.items()}
    children: dict[str, list[str]] = {i: [] for i in tasks}
    for ident, task in tasks.items():
        for dep in task["depends_on"]:
            if dep not in tasks:
                raise VerificationError(f"Unknown dependency: {ident} -> {dep}")
            children[dep].append(ident)
    queue = deque(i for i in tasks if incoming[i] == 0)
    order = []
    while queue:
        ident = queue.popleft()
        order.append(ident)
        for child in children[ident]:
            incoming[child] -= 1
            if incoming[child] == 0:
                queue.append(child)
    if len(order) != len(tasks):
        raise VerificationError("Graph contains a cycle; no executable order exists.")
    selected = set(tasks)
    if until is not None:
        if until not in tasks:
            raise VerificationError(f"Unknown --until target: {until}")
        selected, stack = set(), [until]
        while stack:
            ident = stack.pop()
            if ident not in selected:
                selected.add(ident)
                stack.extend(tasks[ident]["depends_on"])
    ready = [i for i in order if i in selected and tasks[i]["status"] == "pending"
             and all(tasks[d]["status"] in DEPENDENCY_SATISFIED for d in tasks[i]["depends_on"])]
    state, remaining = validate_control(document, tasks)
    return {"valid": True, "selected_order": [i for i in order if i in selected],
            "dependency_ready": ready,
            "control_state": state,
            "dispatch_ready": ready if state == "running" else [],
            "drain_remaining": remaining,
            "note": "Declared graph/control only. Resources, sources, revisions, processes, and permissions still require validation."}


def write_snapshot(path: Path, value: dict[str, Any]) -> None:
    root = Path(value["payload"]["repo"])
    destination = path.expanduser().absolute()
    resolved = destination.resolve()
    allowed_metadata = metadata_dir(root) / "orquestrar"
    if resolved.is_relative_to(root) and not resolved.is_relative_to(allowed_metadata):
        raise VerificationError("Save outside the captured tree or in <git-common-dir>/orquestrar/.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Never accidentally replace existing evidence or files.
        with destination.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise VerificationError(f"Destination already exists; use another name: {destination}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("snapshot", "compare"):
        child = commands.add_parser(name)
        child.add_argument("--repo", required=True, type=Path)
        child.add_argument("--context", type=Path, help="JSON of observed, nonsecret metadata")
        if name == "snapshot":
            child.add_argument("--out", type=Path, help="New file outside the captured tree")
        else:
            child.add_argument("--snapshot", required=True, type=Path)
    plan = commands.add_parser("plan")
    plan.add_argument("--file", required=True, type=Path)
    plan.add_argument("--until")
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            result = validate_plan(read_json(args.file), args.until)
        else:
            context = read_json(args.context) if args.context else None
            if args.command == "snapshot":
                result = snapshot(args.repo, context)
                if args.out:
                    write_snapshot(args.out, result)
            else:
                result = compare(args.repo, read_json(args.snapshot), context)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 1 if result.get("same") is False else 0
    except (VerificationError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
