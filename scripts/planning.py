"""Selective CI, bounded shards and pull-request commit policy."""
from __future__ import annotations

from pathlib import Path
import re

from .common import require, run
from .repository import registry, settings

SHARED_PREFIXES = ("scripts/", "schemas/", ".github/", "tests/scripts/", "tests/launchers/")
SHARED_FILES = {"Makefile", "AGENTS.md", "CLAUDE.md", "docs/AGENT_WORKFLOW.md", "repository.json", "requirements-dev.txt", "requirements-reference.txt", "pyproject.toml",
                ".python-version", "package.json", "package-lock.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", ".npmrc", ".node-version", "LICENSE",
                "release-please-config.json", ".release-please-manifest.json", "version.txt"}
COMMIT = re.compile(r"^(feat|fix|perf|refactor|docs|test|build|ci|chore|revert)(?:\(([a-z0-9._/-]+)\))?(!)?: .+\S$")


def resolve_commit(root: Path, ref: str) -> str | None:
    if not ref or set(ref) == {"0"}:
        return None
    result = run(["git", "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"], cwd=root, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def changed_files(root: Path, base: str | None, head: str = "HEAD") -> list[str] | None:
    if not base:
        return None
    base_sha = resolve_commit(root, base)
    head_sha = resolve_commit(root, head)
    if not base_sha or not head_sha:
        return None  # First push, shallow or missing history: test everything, never guess.
    merge_base = run(["git", "merge-base", base_sha, head_sha], cwd=root, check=False)
    if merge_base.returncode:
        return None
    diff = run(["git", "diff", "--name-only", "--no-renames", "-z", merge_base.stdout.strip(), head_sha, "--"], cwd=root)
    return [path for path in diff.stdout.split("\0") if path]


def select_skills(names: list[str], paths: list[str] | None) -> list[str]:
    names = sorted(names)
    if paths is None or any(path in SHARED_FILES or path.startswith(SHARED_PREFIXES) for path in paths):
        return names
    selected = set()
    for path in paths:
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] == "skills":
            selected.add(parts[1])
        elif len(parts) == 2 and parts[0] == "catalog" and parts[1].endswith(".json"):
            selected.add(parts[1][:-5])
        elif len(parts) >= 3 and parts[:2] == ["tests", "skills"]:
            selected.add(parts[2])
    return [name for name in names if name in selected]


def make_shards(names: list[str], maximum: int) -> list[dict]:
    require(1 <= maximum <= 64, "max_shards must be 1..64.")
    count = min(len(names), maximum)
    return [{"id": index, "skills": names[index::count]} for index in range(count)] if count else []


def plan(root: Path, base: str | None = None, head: str = "HEAD") -> dict:
    items = registry(root)
    paths = changed_files(root, base, head)
    selected = select_skills([item["name"] for item in items], paths)
    return {"all": paths is None, "selected": selected, "has_skills": bool(selected),
            "matrix": compact_matrix(selected, settings(root)["ci"]["max_shards"]),
            "maintenance": needs_maintenance_tests(paths)}


def needs_maintenance_tests(paths: list[str] | None) -> bool:
    """Missing history is conservative; ordinary docs/skill edits do not retest tooling."""
    return paths is None or any(path in SHARED_FILES or path.startswith(SHARED_PREFIXES) for path in paths)


def compact_matrix(names: list[str], maximum: int) -> dict:
    require(1 <= maximum <= 64, "max_shards must be 1..64.")
    count = min(len(names), maximum)
    # Pass fixed-size identifiers, not every skill name, through GitHub job outputs.
    return {"include": [{"id": index, "count": count} for index in range(count)]}


def verify_metadata_only_diff(root: Path, base: str | None, head: str, paths: list[str] | None) -> bool:
    if paths is None or not base:
        return False
    old, new = resolve_commit(root, base), resolve_commit(root, head)
    if not old or not new:
        return False
    common = run(["git", "merge-base", old, new], cwd=root, check=False)
    if common.returncode:
        return False
    for path in paths:
        if not path.endswith("/SKILL.md"):
            continue
        before = run(["git", "show", f"{common.stdout.strip()}:{path}"], cwd=root, check=False)
        after = run(["git", "show", f"{new}:{path}"], cwd=root, check=False)
        if before.returncode or after.returncode:
            return False
        pattern = r'^  version: "[0-9]+\.[0-9]+\.[0-9]+" # x-release-please-version$'
        normalize = lambda text: re.sub(pattern, "  RELEASE VERSION ONLY", text, flags=re.M)
        if normalize(before.stdout) != normalize(after.stdout):
            return False
    return True


def check_pr(title: str, paths: list[str] | None, *, release_branch: bool = False,
             metadata_only: bool = False) -> None:
    require("\n" not in title and "\r" not in title and COMMIT.fullmatch(title),
            "Use a Conventional Commit PR title, e.g. feat(orquestrar): add validated orchestration flow")
    if release_branch and re.match(r"^chore(?:\([^)]*\))?: release\b", title):
        allowed_root = {"version.txt", "CHANGELOG.md", ".release-please-manifest.json"}
        require(paths is not None and all(path in allowed_root or re.fullmatch(
            r"skills/[a-z0-9-]+/(?:version\.txt|CHANGELOG\.md|SKILL\.md)", path) for path in paths),
            "Release exception is limited to version metadata and changelogs, not arbitrary files.")
        require(not any(path.endswith("/SKILL.md") for path in paths) or metadata_only,
                "Release exception requires a verified version-only SKILL.md diff; branch names are not authorization.")
        return
    kind = COMMIT.fullmatch(title).group(1)
    changes_payload = paths is None or any(
        path.startswith("skills/") and not path.endswith(("/CHANGELOG.md", "/.gitkeep", ".template"))
        for path in paths
    )
    if changes_payload:
        require(kind in {"feat", "fix", "perf", "revert"} or "!:" in title,
                "Changes to shipped skill content need feat/fix/perf/revert (or a breaking commit), not docs/chore.")
