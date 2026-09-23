#!/usr/bin/env python3
"""Run checkpoint helper: validate the plan graph and save/read run state safely.

Python 3.10+ standard library only. Does not run gates, access networks, or write
product code. Exit codes: 0 = valid, 2 = error or invalid input.
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
import sys
from typing import Any


class VerificationError(ValueError):
    """Invalid input or a condition preventing safe verification."""


def parse_json(raw: bytes | str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise VerificationError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def constant(value):
        raise VerificationError(f"Non-finite JSON number: {value}")
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"Invalid JSON: {exc}") from exc


def read_json(path: Path) -> Any:
    try:
        return parse_json(path.read_bytes())
    except OSError as exc:
        raise VerificationError(f"Unreadable JSON at {path}: {exc}") from exc


def signature(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


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
    result = document.get("result", "open")
    if result not in ("open", "completed"):
        raise VerificationError("result must be open or completed; it is not control.state.")
    declared_selection = document.get("selected_tasks", list(tasks))
    if (not isinstance(declared_selection, list) or not declared_selection
            or any(not isinstance(i, str) or i not in tasks for i in declared_selection)
            or len(set(declared_selection)) != len(declared_selection)):
        raise VerificationError("selected_tasks must be distinct known IDs.")
    selected_ids = set(declared_selection)
    if any(d not in selected_ids for i in selected_ids for d in tasks[i]["depends_on"]):
        raise VerificationError("selected_tasks must include prerequisites.")
    selected &= selected_ids
    ready = [i for i in ready if i in selected]
    if result == "completed":
        if state != "running" or document.get("active_agents") != [] or document.get("active_processes") != []:
            raise VerificationError("Completed result requires running control and confirmed empty active arrays.")
        if any(tasks[i]["status"] not in DEPENDENCY_SATISFIED for i in selected_ids):
            raise VerificationError("Completed result requires every selected unit integrated/delivered, not merely verified.")
        if any(t["status"] in {"running", "implemented", "reviewing", "verified"}
               for i, t in tasks.items() if i not in selected_ids):
            raise VerificationError("Cannot complete with active work outside selected scope.")
    return {"valid": True, "selected_order": [i for i in order if i in selected],
            "dependency_ready": ready,
            "control_state": state,
            "dispatch_ready": ready if state == "running" and result == "open" else [],
            "result": result,
            "drain_remaining": remaining,
            "note": "Declared graph/control only. Resources, sources, revisions, processes, and permissions still require validation."}


# This is a local storage protocol, not an approval or process-monitoring service.
# One owner, cooperating writers, local filesystem. No distributed lock guarantee.
def validate_checkpoint(document: Any, *, writing: bool = False) -> dict[str, Any]:
    report = validate_plan(document)
    if writing:
        for key in ("control", "result", "sources", "repositories", "permissions",
                    "active_agents", "active_processes", "next_action"):
            if key not in document:
                raise VerificationError(f"Checkpoint requires {key}; see SKILL.md checkpoint contract.")
        if not isinstance(document["permissions"], dict):
            raise VerificationError("permissions must be an object.")
        for key in ("sources", "repositories"):
            if not isinstance(document[key], list) or not document[key]:
                raise VerificationError(f"{key} must contain observed identities, not an empty inventory.")
        for source in document["sources"]:
            if not isinstance(source, dict) or any(
                not isinstance(source.get(k), str) or not source[k].strip()
                for k in ("locator", "revision")
            ):
                raise VerificationError("Each source requires locator and observed revision.")
        for repository in document["repositories"]:
            if not isinstance(repository, dict) or any(
                not isinstance(repository.get(k), str) or not repository[k].strip()
                for k in ("id", "path", "base_revision")
            ):
                raise VerificationError("Each repository requires id, path and observed base_revision (unborn is explicit).")
        repo_ids = [r["id"] for r in document["repositories"]]
        if len(set(repo_ids)) != len(repo_ids) or any(t["repo"] not in repo_ids for t in document["tasks"]):
            raise VerificationError("Task repo must match a unique repositories[].id.")
        if not isinstance(document["next_action"], str) or not document["next_action"].strip():
            raise VerificationError("next_action must describe continuation, closure, or the blocker.")
        history = document.get("agent_history", [])
        if not isinstance(history, list) or any(not isinstance(a, dict) for a in history):
            raise VerificationError("agent_history must be a list of observations.")
        ids = [a.get("id") for a in history]
        if len(ids) != len(set(ids)):
            raise VerificationError("agent_history IDs must be unique; update the entry for a re-review.")
        reviewed = {a.get("unit") for a in history if a.get("role") == "review"}
        built = {a.get("unit") for a in history if a.get("role") not in (None, "review")}
        statuses = {t["id"]: t["status"] for t in document["tasks"]}
        for task in document["tasks"]:
            waiting = [d for d in task["depends_on"] if statuses[d] not in DEPENDENCY_SATISFIED]
            if task["status"] not in ("pending", "blocked") and waiting:
                raise VerificationError(
                    f"{task['id']} cannot be {task['status']} before its dependencies are "
                    f"integrated or delivered: {', '.join(waiting)}")
            if not isinstance(task.get("acceptance"), list) or not task["acceptance"]:
                raise VerificationError(f"Acceptance criteria missing for {task['id']}.")
            # Independent review is the default; "self" is an explicit, visible choice for
            # whoever resumes the run rather than a shortcut inherited from earlier units.
            review = task.get("review", "independent")
            if review not in ("independent", "self"):
                raise VerificationError(f"review must be independent or self: {task['id']}")
            if (review == "independent" and task["status"] in DEPENDENCY_SATISFIED
                    and task["id"] not in reviewed):
                raise VerificationError(
                    f"{task['id']} needs a review entry in agent_history before "
                    f"{task['status']}, or an explicit review=self for nonbehavioral work.")
            # Workers implement; a coordinator edit is an explicit, visible exception.
            implementer = task.get("implementer", "worker")
            if implementer not in ("worker", "coordinator"):
                raise VerificationError(f"implementer must be worker or coordinator: {task['id']}")
            if (implementer == "worker" and task["status"] in DEPENDENCY_SATISFIED
                    and task["id"] not in built):
                raise VerificationError(
                    f"{task['id']} needs its worker entry in agent_history before "
                    f"{task['status']}, or implementer=coordinator for a small adjustment.")
    for field in ("active_agents", "active_processes"):
        values = document.get(field, [])
        if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
            raise VerificationError(f"{field} must be an array of observations.")
        if writing and any(not isinstance(v.get("id"), str) or not v["id"].strip()
                           or not isinstance(v.get("state"), str) or not v["state"].strip() for v in values):
            raise VerificationError(f"{field} entries need actual id and observed state.")
        if any(isinstance(v.get("state"), str) and v["state"] in {"completed", "closed", "stopped"} for v in values):
            raise VerificationError(f"Move finished observations from {field} to history; active arrays mean unresolved activity.")
    if document.get("result") == "completed":
        selected = set(document.get("selected_tasks", [t["id"] for t in document["tasks"]]))
        for task in document["tasks"]:
            if task["id"] in selected and not task.get("evidence_ref"):
                raise VerificationError(f"Completed task requires evidence_ref: {task['id']}")
    return report


def preserve_fields(previous: Any, candidate: Any, location: str = "checkpoint") -> None:
    """Protect unknown object fields; active arrays remain replaceable observations."""
    if isinstance(previous, dict):
        if not isinstance(candidate, dict):
            raise VerificationError(f"Preserve existing object fields: {location}")
        missing = set(previous) - set(candidate)
        if missing:
            raise VerificationError(f"Preserve existing fields at {location}: {', '.join(sorted(missing))}")
        for key in previous:
            if isinstance(previous[key], dict):
                preserve_fields(previous[key], candidate[key], f"{location}.{key}")
    # The task list is durable identity, unlike a list of currently active agents.
    if location == "checkpoint":
        old = {t["id"]: t for t in previous["tasks"]}
        new = {t["id"]: t for t in candidate["tasks"]}
        if set(old) - set(new):
            raise VerificationError("Preserve existing task IDs; record changed scope instead of erasing work.")
        for ident, task in old.items():
            preserve_fields(task, new[ident], f"tasks.{ident}")


def validate_update(previous: dict[str, Any], candidate: dict[str, Any], *, resume: bool) -> None:
    if previous["run_id"] != candidate["run_id"]:
        raise VerificationError("A checkpoint update cannot replace another run identity.")
    preserve_fields(previous, candidate)
    before = previous.get("control", {"state": "running", "drain_units": []})
    after = candidate["control"]
    if previous.get("result", "open") == "completed" and any(
        previous.get(key) != candidate.get(key)
        for key in ("result", "objective", "tasks", "selected_tasks")
    ):
        raise VerificationError("A completed run is immutable in scope; begin a new run for additional work.")
    old_tasks = {t["id"]: t for t in previous["tasks"]}
    new_tasks = {t["id"]: t for t in candidate["tasks"]}
    for active_key, archive_key in (("active_agents", "agent_history"), ("active_processes", "process_history")):
        removed = {a.get("id") for a in previous.get(active_key, [])} - {a.get("id") for a in candidate.get(active_key, [])}
        archive = candidate.get(archive_key, [])
        if not isinstance(archive, list) or any(not isinstance(a, dict) for a in archive):
            raise VerificationError(f"{archive_key} must be a list of observations.")
        retained = candidate.get("retained_resources", []) if active_key == "active_processes" else []
        if not isinstance(retained, list) or any(not isinstance(a, dict) for a in retained):
            raise VerificationError("retained_resources must contain identified observations.")
        if removed - {a.get("id") for a in archive + retained}:
            raise VerificationError(f"Preserve resolved {active_key} observations in {archive_key} or retained resources.")
    if before["state"] in {"paused", "interrupted", "draining"} and after["state"] == "running" and not resume:
        raise VerificationError("Releasing a stop latch requires --resume after an explicit request and live reconciliation.")
    if before["state"] in {"paused", "interrupted"} and after["state"] == "draining" and not resume:
        raise VerificationError("Resuming drain closure requires --resume after reconciliation.")
    if before["state"] == "draining" and after["state"] != "running":
        if set(before.get("drain_units", [])) != set(after["drain_units"]):
            raise VerificationError("A frozen drain set cannot expand or shrink.")
        for ident, task in new_tasks.items():
            if ident not in before["drain_units"] and (
                ident not in old_tasks or task["status"] != old_tasks[ident]["status"]
            ):
                raise VerificationError("No new unit or status advancement outside the frozen drain set.")
    if before["state"] in {"paused", "interrupted"} and after["state"] in {"paused", "interrupted"}:
        if (set(new_tasks) != set(old_tasks) or
                any(new_tasks[i]["status"] != t["status"] for i, t in old_tasks.items())):
            raise VerificationError("Stopped work cannot advance without explicit resume.")
    if before["state"] == "running" and after["state"] == "draining":
        expected = {i for i, t in old_tasks.items() if t["status"] in
                    {"running", "implemented", "reviewing", "verified", "paused"}}
        # A blocked-but-started unit can be identified explicitly by started_at.
        expected |= {i for i, t in old_tasks.items() if t["status"] == "blocked" and t.get("started_at")}
        if set(after["drain_units"]) != expected:
            raise VerificationError("Latch the active set from the previous checkpoint before further work.")


def checked_path(path: Path) -> Path:
    path = path.expanduser().absolute()
    if path != path.resolve():
        raise VerificationError("Checkpoint paths must not traverse symlinks or aliases.")
    return path


def checkpoint_bytes(path: Path, *, optional: bool = False) -> bytes | None:
    try:
        before = path.lstat()
    except FileNotFoundError:
        if optional:
            return None
        raise VerificationError(f"Checkpoint/draft is missing: {path}")
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise VerificationError("Checkpoint/draft must be a regular, unaliased file.")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, "rb") as stream:
        if signature(os.fstat(stream.fileno())) != signature(before):
            raise VerificationError("Checkpoint changed before reading.")
        raw = stream.read()
        if signature(os.fstat(stream.fileno())) != signature(before):
            raise VerificationError("Checkpoint changed while reading.")
    if signature(path.lstat()) != signature(before):
        raise VerificationError("Checkpoint replaced while reading.")
    return raw


def checkpoint_summary(document: dict[str, Any], raw: bytes, path: Path | None) -> dict[str, Any]:
    report = validate_checkpoint(document)
    counts: dict[str, int] = {}
    for task in document["tasks"]:
        counts[task["status"]] = counts.get(task["status"], 0) + 1
    return {"path": str(path) if path is not None else None, "run_id": document["run_id"],
            "result": document.get("result", "open"), "control": report["control_state"],
            "task_counts": counts, "next_ready": next(iter(report["dispatch_ready"]), None),
            "next_action": document.get("next_action"), "state_token": hashlib.sha256(raw).hexdigest(),
            "validation": "declared_state_only"}


def checkpoint_read(path: Path, unit: str | None = None, *, strict: bool = False) -> dict[str, Any]:
    path = checked_path(path)
    raw = checkpoint_bytes(path)
    document = parse_json(raw)
    validate_checkpoint(document, writing=strict)
    result = checkpoint_summary(document, raw, path)
    if unit is not None:
        selected = next((t for t in document["tasks"] if t["id"] == unit), None)
        if selected is None:
            raise VerificationError(f"Unknown unit: {unit}")
        result["unit"] = selected
    return result


def checkpoint_check(raw: bytes, *, resume: bool = False) -> dict[str, Any]:
    """Apply the save contract to a run kept in project-native state; writes nothing.

    Project rules may forbid state files. The unit gates still apply, so the caller
    checks each change here. Input is the first run document, or
    {"previous": <last checked document>, "candidate": <next document>} so the same
    transition rules as checkpoint-save (latches, preserved fields/tasks) apply.
    """
    if not raw.strip():
        raise VerificationError("checkpoint-check reads the run document (or previous/candidate) from stdin.")
    document = parse_json(raw)
    previous = None
    if isinstance(document, dict) and set(document) == {"previous", "candidate"}:
        previous, document = document["previous"], document["candidate"]
        validate_checkpoint(previous)
    validate_checkpoint(document, writing=True)
    if previous is not None:
        validate_update(previous, document, resume=resume)
    canonical = json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    summary = checkpoint_summary(document, canonical, None)
    # The digest names the checked document; it is not a save token or an attestation.
    summary["document_digest"] = summary.pop("state_token")
    return {**summary, "status": "valid", "persisted": False,
            "transition": "checked" if previous is not None else "initial"}


def checkpoint_save(path: Path, draft: Path, expected: str, *, resume: bool = False) -> dict[str, Any]:
    """Validate then replace with local lock + compare-and-swap; never emit false success.

    The lock coordinates users of this protocol, not adversarial/uncooperative writers.
    A crash can leave a lock; it is NOT removed automatically by a later process.
    """
    import tempfile
    path, draft = checked_path(path), checked_path(draft)
    if path == draft:
        raise VerificationError("Draft must be separate from the persisted checkpoint.")
    if expected != "missing" and not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise VerificationError("--expected must be missing or the last observed state_token.")
    document = parse_json(checkpoint_bytes(draft))
    validate_checkpoint(document, writing=True)  # Before touching the destination.
    raw = (json.dumps(document, ensure_ascii=True, indent=2, allow_nan=False) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    checked_path(path)
    lock = path.with_name(path.name + ".lock")
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise VerificationError("Checkpoint lock exists; reconcile the owner, never delete it automatically.") from exc
    temp: Path | None = None
    replaced = False
    owner_file = lock / "owner.json"
    try:
        owner_file.write_text(json.dumps({"pid": os.getpid(), "run_id": document["run_id"],
                              "created_at": datetime.now(timezone.utc).isoformat()}) + "\n", encoding="utf-8")
        current = checkpoint_bytes(path, optional=True)
        token = hashlib.sha256(current).hexdigest() if current is not None else "missing"
        if token != expected:
            raise VerificationError("Checkpoint conflict: reread/reconcile; do not blindly retry with a new token.")
        if current is not None:
            previous = parse_json(current)
            validate_checkpoint(previous)
            validate_update(previous, document, resume=resume)
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temp = Path(name)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # Defend against a noncooperating edit detected before replacement.
        if checkpoint_bytes(path, optional=True) != current:
            raise VerificationError("Checkpoint changed before replace; candidate was not saved.")
        os.replace(temp, path)
        replaced = True
        temp = None
        # POSIX local-filesystem durability; unavailable directory fsync is not hidden.
        if os.name == "posix":
            directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        actual = checkpoint_bytes(path)
        if actual != raw or parse_json(actual) != document:
            raise VerificationError("Checkpoint read-back differs from the intended update.")
        result = {**checkpoint_summary(document, actual, path), "status": "saved", "comparison": "succeeded"}
    except (OSError, VerificationError) as exc:
        if replaced:
            raise VerificationError("Checkpoint may have been replaced but confirmation failed; reconcile the file before any retry. " + str(exc)) from exc
        raise
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
        owner_file.unlink(missing_ok=True)
        lock.rmdir()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("--file", required=True, type=Path)
    plan.add_argument("--until")
    save = commands.add_parser("checkpoint-save", help="Validate, CAS-save and reread one run; compact output")
    save.add_argument("--file", required=True, type=Path)
    save.add_argument("--draft", required=True, type=Path)
    save.add_argument("--expected", required=True, help="missing or state_token from the last successful read/save")
    save.add_argument("--resume", action="store_true", help="Only after explicit continuation and live reconciliation; not authorization")
    read = commands.add_parser("checkpoint-read", help="Validate and summarize without writing")
    read.add_argument("--file", required=True, type=Path)
    read.add_argument("--unit", help="Include one task's detail, not all completed history")
    read.add_argument("--strict", action="store_true", help="Require the complete current writer contract; no legacy defaults")
    check = commands.add_parser("checkpoint-check", help="Validate a run (or previous/candidate pair) from stdin with the save contract; writes nothing")
    check.add_argument("--resume", action="store_true", help="Only after explicit continuation and live reconciliation; not authorization")
    args = parser.parse_args(argv)
    try:
        if args.command == "checkpoint-save":
            result = checkpoint_save(args.file, args.draft, args.expected, resume=args.resume)
        elif args.command == "checkpoint-check":
            if sys.stdin.isatty():
                raise VerificationError("checkpoint-check reads JSON from stdin; pipe the document in.")
            result = checkpoint_check(sys.stdin.buffer.read(), resume=args.resume)
        elif args.command == "checkpoint-read":
            result = checkpoint_read(args.file, args.unit, strict=args.strict)
        else:
            result = validate_plan(read_json(args.file), args.until)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (VerificationError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2
    except (TypeError, RecursionError) as exc:
        # Malformed shapes (e.g. unhashable IDs) are rejected input, not a crash.
        print(json.dumps({"error": f"Malformed document: {type(exc).__name__}"}, ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
