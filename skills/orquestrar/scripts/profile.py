#!/usr/bin/env python3
"""Optional profile cache helper. No network, shell commands or LLM discovery.

Checks only the anchors declared by the caller. Integrity protects against
accidental edits, not a malicious actor able to rewrite both payload and hash.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Any


class ProfileError(ValueError):
    """Controlled validation, concurrency or filesystem failure."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProfileError(f"Cannot read JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError("JSON root must be an object")
    return data


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone required")
        return parsed.astimezone(timezone.utc)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ProfileError("Invalid timestamp; timezone required") from exc


def validate_draft(data: dict) -> None:
    if data.get("schema_version") != 2:
        raise ProfileError("Unsupported schema_version (expected 2)")
    if not isinstance(data.get("project_id"), str) or not data["project_id"].strip():
        raise ProfileError("project_id required")
    if not isinstance(data.get("sections"), dict) or not data["sections"]:
        raise ProfileError("Nonempty sections required")
    anchors = data.get("anchors", {})
    if not isinstance(anchors, dict):
        raise ProfileError("anchors must be an object")
    for name, anchor in anchors.items():
        if not isinstance(anchor, dict):
            raise ProfileError(f"Invalid anchor: {name}")
        sections = anchor.get("sections")
        if not isinstance(sections, list) or not sections or any(
                not isinstance(s, str) or s not in data["sections"] for s in sections):
            raise ProfileError(f"Unknown/missing anchor section: {name}")
        for field in ("paths", "globs"):
            values = anchor.get(field, [])
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                raise ProfileError(f"{field} must be strings")
            for value in values:
                rel = Path(value)
                if not value or rel.is_absolute() or ".." in rel.parts or "\\" in value:
                    raise ProfileError(f"Anchor must be confined relative path: {value}")
                if ".git" in rel.parts:
                    raise ProfileError("Do not use Git metadata as a profile anchor")


def confined(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ProfileError(f"Anchor escapes project root: {path}")
    # Refuse symlinks even within root: do not implicitly read another target.
    rel = path.relative_to(root)
    current = root
    for component in rel.parts:
        current = current / component
        if current.is_symlink():
            raise ProfileError(f"Symlink anchor requires explicit project handling: {path}")
    return path


def capture(root: Path, anchor: dict) -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise ProfileError("root must be an existing directory")
    files: dict[str, str | None] = {}
    paths = set(anchor.get("paths", []))
    for pattern in anchor.get("globs", []):
        for path in root.glob(pattern):
            confined(root, path)
            if path.is_file():
                paths.add(path.relative_to(root).as_posix())
    for relative in sorted(paths):
        path = confined(root, root / relative)
        if not path.exists():
            files[relative] = None
        elif path.is_file():
            if path.stat().st_size > 8 * 1024 * 1024:
                raise ProfileError(f"Anchor exceeds 8 MiB; narrow evidence: {relative}")
            files[relative] = digest(path.read_bytes())
        else:
            raise ProfileError(f"Use bounded globs for directories: {relative}")
    return {"spec_sha256": digest(canonical(anchor)), "files": files}


def intact(profile: dict) -> bool:
    body = {k: v for k, v in profile.items() if k != "_integrity"}
    return profile.get("_integrity") == digest(canonical(body))


def seal(profile: dict) -> dict:
    result = copy.deepcopy(profile)
    result.pop("_integrity", None)
    result["_integrity"] = digest(canonical(result))
    return result


def check(root: Path, profile: dict, now: datetime | None = None,
          ttl_hours: float = 168) -> dict:
    validate_draft(profile)
    if ttl_hours <= 0:
        raise ProfileError("ttl_hours must be positive")
    if not intact(profile):
        return {"status": "manual_edit_or_corrupt", "invalid_sections": list(profile["sections"]),
                "valid_sections": [], "reasons": ["Do not overwrite; preserve human edits"]}
    now = now or utc_now()
    invalid: dict[str, list[str]] = {}
    coverage: set[str] = set()
    baseline = profile.get("_baselines", {})
    for name, anchor in profile.get("anchors", {}).items():
        coverage.update(anchor["sections"])
        try:
            same = capture(root, anchor) == baseline.get(name)
            reason = f"anchor_changed:{name}"
        except (OSError, ProfileError) as exc:
            same = False; reason = f"anchor_unverified:{name}:{exc}"
        if not same:
            for section in anchor["sections"]:
                invalid.setdefault(section, []).append(reason)
    times = profile.get("_validated_at", {})
    for section in profile["sections"]:
        if section not in coverage:
            invalid.setdefault(section, []).append("no_local_anchor:semantic_revalidation_required")
        try:
            age = now - timestamp(times.get(section))
            if age < timedelta(minutes=-5):
                invalid.setdefault(section, []).append("future_timestamp")
            elif age > timedelta(hours=ttl_hours):
                invalid.setdefault(section, []).append("ttl_expired")
        except ProfileError:
            invalid.setdefault(section, []).append("validation_time_missing")
    return {"status": "refresh_required" if invalid else "local_anchors_match",
            "invalid_sections": sorted(invalid),
            "valid_sections": sorted(set(profile["sections"]) - set(invalid)),
            "reasons": invalid,
            "external_sources": "Not checked. Revalidate relevant remote revisions before use."}


def build(root: Path, draft: dict, previous: dict | None = None,
          sections: list[str] | None = None, now: datetime | None = None) -> dict:
    """Caller must have semantically revalidated selected sections first."""
    validate_draft(draft)
    now = now or utc_now()
    selected = set(sections) if sections is not None else set(draft["sections"])
    if not selected or not selected <= set(draft["sections"]):
        raise ProfileError("Selected sections must exist")
    if previous is not None:
        validate_draft(previous)
        if not intact(previous):
            raise ProfileError("Edited/corrupt profile: preserve edits before regeneration")
        if previous["project_id"] != draft["project_id"]:
            raise ProfileError("Project identity changed; use an explicitly separate profile")
        if sections is None:
            selected |= set(previous["sections"])
        for section in set(previous["sections"]) | set(draft["sections"]):
            if section not in selected and previous["sections"].get(section) != draft["sections"].get(section):
                raise ProfileError(f"Unselected section changed: {section}")
        old_anchors = previous.get("anchors", {})
        for key in set(old_anchors) | set(draft.get("anchors", {})):
            old = old_anchors.get(key, {}); new = draft.get("anchors", {}).get(key, {})
            impacted = set(old.get("sections", [])) | set(new.get("sections", []))
            if old != new and not impacted <= selected:
                raise ProfileError("Changing shared anchors requires refreshing every impacted section")
    elif selected != set(draft["sections"]):
        raise ProfileError("First save must validate every section")
    result = {k: copy.deepcopy(v) for k, v in draft.items()
              if k not in {"_integrity", "_baselines", "_validated_at"}}
    result["_baselines"] = copy.deepcopy(previous.get("_baselines", {})) if previous else {}
    result["_validated_at"] = copy.deepcopy(previous.get("_validated_at", {})) if previous else {}
    for name, anchor in draft.get("anchors", {}).items():
        impacted = set(anchor["sections"])
        if impacted & selected:
            observed = capture(root, anchor)
            if impacted - selected and result["_baselines"].get(name) != observed:
                raise ProfileError("Changed shared anchor requires all impacted sections")
            result["_baselines"][name] = observed
    result["_baselines"] = {k: v for k, v in result["_baselines"].items() if k in draft.get("anchors", {})}
    for section in selected & set(draft["sections"]):
        result["_validated_at"][section] = now.isoformat()
    result["_validated_at"] = {k: v for k, v in result["_validated_at"].items()
                               if k in draft["sections"]}
    return seal(result)


def merged(base: Any, override: Any) -> Any:
    """Objects merge recursively; lists/scalars/null replace, never append."""
    if isinstance(base, dict) and isinstance(override, dict):
        result = copy.deepcopy(base)
        for key, value in override.items():
            result[key] = merged(result.get(key), value)
        return result
    return copy.deepcopy(override)


def replace_atomic(path: Path, content: bytes) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save(path: Path, profile: dict, expected: str) -> None:
    """Compare-and-swap for cooperating writers, with an exclusive metadata lock."""
    if path.is_symlink():
        raise ProfileError("Refusing symlink output")
    if not intact(profile):
        raise ProfileError("Unsealed profile")
    # Check before creating directories: never create through an existing symlink.
    if any(p.is_symlink() for p in [path.parent, *path.parent.parents]):
        raise ProfileError("Refusing symlink output directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ProfileError("Metadata lock exists; do not remove another writer's lock") from exc
    try:
        os.close(fd)
        if path.is_symlink():
            raise ProfileError("Refusing symlink output")
        old = path.read_bytes() if path.exists() else None
        actual = digest(old) if old is not None else "missing"
        if actual != expected:
            raise ProfileError("Concurrent change: expected digest no longer matches")
        if old is not None:
            try:
                old_object = json.loads(old)
            except ValueError as exc:
                raise ProfileError("Existing profile corrupt; preserve it") from exc
            if not isinstance(old_object, dict) or not intact(old_object):
                raise ProfileError("Existing profile manually edited/corrupt; preserve it")
            backup = path.with_name(path.name + ".previous")
            if backup.is_symlink():
                raise ProfileError("Refusing symlink backup")
            replace_atomic(backup, old)
        replace_atomic(path, json.dumps(profile, ensure_ascii=False, indent=2,
                                        allow_nan=False).encode("utf-8") + b"\n")
    finally:
        lock.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check"); c.add_argument("--root", type=Path, required=True)
    c.add_argument("--profile", type=Path, required=True); c.add_argument("--ttl-hours", type=float, default=168)
    s = sub.add_parser("save"); s.add_argument("--root", type=Path, required=True)
    s.add_argument("--draft", type=Path, required=True); s.add_argument("--profile", type=Path, required=True)
    s.add_argument("--expected", required=True, help="SHA-256 of read bytes, or missing")
    s.add_argument("--sections", nargs="+")
    args = parser.parse_args()
    try:
        if args.command == "check":
            if not args.profile.exists():
                result = {"status": "missing", "file_sha256": "missing"}
            else:
                raw = args.profile.read_bytes()
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ProfileError("Profile must be an object")
                result = check(args.root, data, ttl_hours=args.ttl_hours)
                result["file_sha256"] = digest(raw)
        else:
            previous = load(args.profile) if args.profile.exists() else None
            profile = build(args.root, load(args.draft), previous, args.sections)
            save(args.profile, profile, args.expected)
            result = {"status": "saved", "profile": str(args.profile),
                      "file_sha256": digest(args.profile.read_bytes())}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] in {"saved", "local_anchors_match"} else 1
    except (ProfileError, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
