#!/usr/bin/env python3
"""Project profile cache: how this repository works, reused across runs.

The profile is plain, human-editable JSON. `save` records a SHA-256 for each listed
source file; `check` reports which sources changed so only stale knowledge is
rediscovered. No network, shell commands or LLM discovery.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


class ProfileError(ValueError):
    """Invalid draft/profile or filesystem failure."""


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProfileError(f"Cannot read JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError("JSON root must be an object")
    return data


def validate(data: dict[str, Any]) -> list[str]:
    if not isinstance(data.get("sections"), dict) or not data["sections"]:
        raise ProfileError("Nonempty sections object required")
    sources = data.get("sources", [])
    if not isinstance(sources, list) or any(not isinstance(s, str) for s in sources):
        raise ProfileError("sources must be a list of relative paths")
    for value in sources:
        rel = Path(value)
        if not value or rel.is_absolute() or ".." in rel.parts:
            raise ProfileError(f"Source must be a path inside the project: {value}")
    return sources


def digests(root: Path, sources: list[str]) -> dict[str, str | None]:
    root = root.resolve()
    result: dict[str, str | None] = {}
    for relative in sorted(set(sources)):
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ProfileError(f"Source escapes project root: {relative}")
        result[relative] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return result


def build(root: Path, draft: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    sources = validate(draft)
    profile = {k: v for k, v in draft.items() if k not in ("source_digests", "saved_at")}
    profile["source_digests"] = digests(root, sources)
    profile["saved_at"] = (now or datetime.now(timezone.utc)).isoformat()
    return profile


def check(root: Path, profile: dict[str, Any]) -> dict[str, Any]:
    sources = validate(profile)
    recorded = profile.get("source_digests", {})
    if not isinstance(recorded, dict):
        raise ProfileError("source_digests must be an object")
    current = digests(root, sources)
    changed = sorted(p for p in set(current) | set(recorded) if current.get(p) != recorded.get(p))
    if changed:
        return {"status": "stale", "changed_sources": changed,
                "next_action": "reread the changed sources, update affected sections, save once"}
    return {"status": "fresh", "next_action": "reuse the profile"}


def write(path: Path, profile: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(profile, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "save"):
        child = sub.add_parser(name)
        child.add_argument("--root", type=Path, required=True)
        child.add_argument("--profile", type=Path, required=True)
        if name == "save":
            child.add_argument("--draft", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            if not args.profile.exists():
                result = {"status": "missing", "next_action": "discover, then save a draft"}
            else:
                result = check(args.root, load(args.profile))
        else:
            profile = build(args.root, load(args.draft))
            write(args.profile, profile)
            result = {"status": "saved", "profile": str(args.profile),
                      "tracked_sources": sorted(profile["source_digests"])}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ProfileError, OSError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
