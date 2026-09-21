"""Explicit GitHub publication: verify tagged artifacts and preflight before writes.

GitHub does not offer a transaction across assets and refs. A failed network write
can still leave a partial release; retries preserve identical bytes and never clobber.
"""
from __future__ import annotations

from pathlib import Path
import json
import os
import re
import tempfile

from .common import inside, require, run
from .packaging import build, digest, verify_release_context
from .planning import resolve_commit
from .repository import settings


def remote_tag_commit(root: Path, repo: str, tag: str, *, optional: bool) -> str | None:
    """Read actual remote refs; a local tag is not evidence that GitHub has it."""
    result = run(["gh", "api", f"repos/{repo}/git/ref/tags/{tag}"], cwd=root, check=False)
    if result.returncode:
        if optional and "HTTP 404" in result.stderr:
            return None
        require(False, f"Cannot read remote tag {tag}: {result.stderr.strip()}")
    item = json.loads(result.stdout)["object"]
    for _ in range(8):
        require(re.fullmatch(r"[0-9a-f]{40}", item["sha"]), "Invalid remote Git object SHA.")
        if item["type"] == "commit":
            return item["sha"]
        require(item["type"] == "tag", f"Tag {tag} does not resolve to a commit.")
        item = json.loads(run(["gh", "api", f"repos/{repo}/git/tags/{item['sha']}"], cwd=root).stdout)["object"]
    require(False, f"Annotated tag chain too deep: {tag}")


def verified_artifacts(root: Path, tag: str, output: Path) -> tuple[dict, list[str]]:
    """Rebuild from the clean tagged source, not from caller-provided checksums."""
    require(inside(root / "dist", output) and output.is_dir(), "Artifacts must be under dist/.")
    with tempfile.TemporaryDirectory(prefix=".verify-release-", dir=root / "dist") as temporary:
        expected = Path(temporary) / "expected"
        index = build(root, expected, preview=False, tag=tag)
        names = ["index.json", "SHA256SUMS"] + [item["archive"] for item in index["skills"]]
        for name in names:
            actual = output / name
            require(actual.is_file() and not actual.is_symlink(), f"Missing/unsafe release artifact: {name}")
            require(actual.read_bytes() == (expected / name).read_bytes(),
                    f"Local artifact corrupted or differs from tagged source: {name}")
    return index, names


def publish_assets(root: Path, tag: str, output: Path) -> dict:
    commit = verify_release_context(root, tag)
    repo = settings(root)["github"]
    require(not os.environ.get("GITHUB_REPOSITORY") or os.environ["GITHUB_REPOSITORY"] == repo,
            "Configured repository differs from the GitHub Actions repository; refusing remote publication.")
    output = output.resolve()
    index, names = verified_artifacts(root, tag, output)
    require(remote_tag_commit(root, repo, tag, optional=False) == commit,
            "Remote catalog tag differs from the verified local commit.")
    release = json.loads(run(["gh", "release", "view", tag, "--repo", repo, "--json", "assets"], cwd=root).stdout)
    existing = {asset["name"] for asset in release["assets"]}
    missing_assets, preserved, missing_tags = [], [], []
    # Complete read-only preflight before the first upload or ref creation.
    with tempfile.TemporaryDirectory(prefix="release-assets-") as temporary:
        for name in names:
            if name not in existing:
                missing_assets.append(name)
                continue
            run(["gh", "release", "download", tag, "--repo", repo, "--pattern", name, "--dir", temporary], cwd=root)
            downloaded = Path(temporary) / name
            require(digest(downloaded.read_bytes()) == digest((output / name).read_bytes()),
                    f"Existing published asset differs: {name}. Never overwrite; publish a new version.")
            downloaded.unlink()
            preserved.append(name)
    for item in index["skills"]:
        component_tag = f"{item['name']}-v{item['version']}"
        previous = remote_tag_commit(root, repo, component_tag, optional=True)
        if previous is None:
            missing_tags.append(component_tag)
            continue
        require(resolve_commit(root, previous), f"Fetch remote tags/history before verifying {component_tag}.")
        diff = run(["git", "diff", "--name-only", previous, commit, "--", f"skills/{item['name']}"], cwd=root).stdout
        require(not [path for path in diff.splitlines() if not path.endswith("/.gitkeep")],
                f"Immutable component tag contents differ: {component_tag}")
    # No --clobber or force updates. Concurrent creation fails rather than overwriting.
    for name in missing_assets:
        run(["gh", "release", "upload", tag, str(output / name), "--repo", repo], cwd=root)
    for component_tag in missing_tags:
        run(["gh", "api", "--method", "POST", f"repos/{repo}/git/refs",
             "-f", f"ref=refs/tags/{component_tag}", "-f", f"sha={commit}"], cwd=root)
    return {"uploaded": missing_assets, "preserved_identical": preserved, "created_component_tags": missing_tags}
