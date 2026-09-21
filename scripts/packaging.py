"""Deterministic, per-skill tarballs and a versioned catalog index."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tarfile
import tempfile

from .common import atomic_write, file_list, inside, json_text, require, run, stable_version
from .planning import resolve_commit
from .repository import registry, settings, skill_version
from .validation import CODE_SUFFIXES, validate_repository


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def payload_files(directory: Path) -> list[Path]:
    return [path for path in file_list(directory) if path.name != ".gitkeep"]


def archive_skill(directory: Path, name: str) -> tuple[bytes, list[dict]]:
    memory = io.BytesIO()
    inventory = []
    with gzip.GzipFile(fileobj=memory, mode="wb", filename="", mtime=0, compresslevel=9) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for path in payload_files(directory):
                relative = path.relative_to(directory).as_posix()
                data = path.read_bytes()
                mode = 0o755 if relative.startswith("scripts/") and path.suffix in CODE_SUFFIXES else 0o644
                info = tarfile.TarInfo(f"{name}/{relative}")
                info.size, info.mode, info.mtime = len(data), mode, 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(data))
                inventory.append({"path": relative, "bytes": len(data), "sha256": digest(data), "mode": oct(mode)})
    return memory.getvalue(), inventory


def verify_release_context(root: Path, tag: str) -> str:
    require(re.fullmatch(r"v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", tag),
            "Release tag must be vMAJOR.MINOR.PATCH.")
    require(tag == "v" + stable_version((root / "version.txt").read_text().strip()),
            "Tag differs from the catalog version at checkout.")
    require(tag != "v0.0.0", "0.0.0 is a bootstrap value, not a release.")
    head = resolve_commit(root, "HEAD")
    require(head and resolve_commit(root, f"refs/tags/{tag}") == head,
            "Build the exact tagged commit, not the current main branch.")
    state = run(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=root).stdout
    require(not state.strip(), "Release requires a clean working tree; commit changes and build from the release tag.")
    require(settings(root)["github"], "Configure repository identity before releasing.")
    return head


def check_unchanged_versions(root: Path, tag: str, entries: list[dict]) -> None:
    current_tuple = tuple(map(int, tag[1:].split(".")))
    tags = run(["git", "tag", "--merged", "HEAD", "--list", "v*"], cwd=root).stdout.splitlines()
    candidates = []
    for previous in tags:
        if re.fullmatch(r"v\d+\.\d+\.\d+", previous):
            number = tuple(map(int, previous[1:].split(".")))
            if previous != tag:
                require(number < current_tuple, f"Catalog version must increase beyond previous release {previous}.")
                candidates.append((number, previous))
    if not candidates:
        return
    previous = max(candidates)[1]
    for item in entries:
        name = item["name"]
        old_version = run(["git", "show", f"{previous}:skills/{name}/version.txt"], cwd=root, check=False)
        if old_version.returncode:
            continue
        old_text = stable_version(old_version.stdout.strip())
        new_text = skill_version(root, name)
        require(tuple(map(int, new_text.split("."))) >= tuple(map(int, old_text.split("."))),
                f"{name}: component version must not decrease from {old_text} to {new_text}.")
        if old_text != new_text:
            continue
        changed = run(["git", "diff", "--name-only", previous, "HEAD", "--", f"skills/{name}"], cwd=root).stdout
        paths = [path for path in changed.splitlines() if not path.endswith("/.gitkeep")]
        require(not paths, f"{name}: contents changed without a version bump since {previous}.")


def build(root: Path, output: Path, *, preview: bool, tag: str | None = None) -> dict:
    root = root.resolve()
    require(not (root / "dist").is_symlink(), "The dist directory must not be a symlink.")
    output = output.resolve()
    require(output != root and inside(root / "dist", output), "Output must be dist/ or a subdirectory of dist/.")
    validate_repository(root)
    entries = [item for item in registry(root) if item["status"] == "active"]
    if preview:
        commit = resolve_commit(root, "HEAD")
        tag = None
    else:
        require(tag, "Pass --tag vX.Y.Z, or explicitly use --preview.")
        commit = verify_release_context(root, tag)
        require(entries, "There are no active skills to release.")
        require(all(skill_version(root, item["name"]) != "0.0.0" for item in entries),
                "Active skills still at 0.0.0 must receive their first Release Please bump.")
        check_unchanged_versions(root, tag, entries)
    index = {"schemaVersion": 1, "mode": "preview" if preview else "release",
             "repository": settings(root)["github"], "catalogVersion": (root / "version.txt").read_text().strip(),
             "tag": tag, "gitCommit": commit, "skills": []}
    if output.exists():
        require(output.is_dir() and ((output / ".build-output").is_file() or not any(output.iterdir())),
                "Refusing to replace a directory not created by this builder.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".build-", dir=output.parent) as temp:
        staging = Path(temp) / "output"
        staging.mkdir()
        hashes = []
        for item in entries:
            name = item["name"]
            version = skill_version(root, name)
            filename = f"{name}-{version}.tar.gz"
            archive, inventory = archive_skill(root / "skills" / name, name)
            atomic_write(staging / filename, archive)
            checksum = digest(archive)
            hashes.append(f"{checksum}  {filename}")
            index["skills"].append({"name": name, "version": version, "archive": filename,
                                    "sha256": checksum, "bytes": len(archive), "files": inventory})
        index_bytes = json_text(index).encode("utf-8")
        atomic_write(staging / "index.json", index_bytes)
        hashes.append(f"{digest(index_bytes)}  index.json")
        atomic_write(staging / "SHA256SUMS", "\n".join(sorted(hashes)) + "\n")
        atomic_write(staging / ".build-output", "Generated by agent-skills tooling.\n")
        if output.exists():
            shutil.rmtree(output)
        shutil.move(str(staging), output)
    return index


def preview_skill(root: Path, name: str) -> dict:
    """Materialize an unapproved local test copy, without changing lifecycle or versions."""
    from .common import mutation_lock
    from .fingerprints import payload_fingerprint
    from .repository import entry
    from .validation import validate_skill
    item = entry(root, name)
    validate_skill(root, item)
    source = root / "skills" / name
    output = root / "dist"
    parent = output / "skill-preview"
    destination = parent / name
    ownership = parent / f".{name}.managed"
    owner_text = f"Generated local preview: {name}\n"
    # Ownership markers live outside the copied payload, preserving its exact fingerprint.
    for part in (output, output / ".build-output", parent, destination, ownership):
        require(not part.is_symlink(), f"Preview destination must not be a symlink: {part}")
    with mutation_lock(root):
        if output.exists():
            require(output.is_dir() and ((output / ".build-output").is_file() or not any(output.iterdir())),
                    "Refusing to use an unowned dist directory for preview output.")
        if destination.exists():
            require(destination.is_dir() and ownership.is_file() and ownership.read_text() == owner_text,
                    "Refusing to replace an unowned preview directory.")
        parent.mkdir(parents=True, exist_ok=True)
        atomic_write(output / ".build-output", "Generated by agent-skills tooling.\n")
        with tempfile.TemporaryDirectory(prefix=".candidate-", dir=parent) as temporary:
            staged = Path(temporary) / name
            shutil.copytree(source, staged)
            if item["status"] == "draft":
                (staged / "SKILL.md.template").rename(staged / "SKILL.md")
            require(payload_fingerprint(source) == payload_fingerprint(staged), "Preview content drift.")
            if destination.exists():
                shutil.rmtree(destination)
            staged.rename(destination)
            atomic_write(ownership, owner_text)
    return {"name": name, "path": str(destination), "status": item["status"],
            "version": skill_version(root, name), "published": False,
            "warning": "Local evaluation copy only. Not behavioral approval or a release."}
