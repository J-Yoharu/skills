#!/usr/bin/env python3
"""Copy the kit into a project, so tests keep working without the skill installed.

The project owns the copy: CI can run the free checks, and the golden cases can be
versioned next to the code they protect.

Usage:
  init_kit.py --target tools/mcp-eval
  init_kit.py --target tools/mcp-eval --ignore-locally   # keep the kit out of the repository
  init_kit.py --target tools/mcp-eval --update-scripts   # refresh only the engine
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Python's isolated mode (-I) leaves the script's own folder off the path, and the kit's modules live there.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kitlib.golden_common import git_ignore_state

SKILL_DIR = Path(__file__).resolve().parent.parent
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc")


def copy_scripts(target: Path) -> None:
    shutil.copytree(SKILL_DIR / "scripts", target / "scripts", ignore=SKIP, dirs_exist_ok=True)


def ignore_locally(target: Path) -> bool:
    """Ignore the kit only on this machine: `.git/info/exclude` changes nothing in the repository."""
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=target, capture_output=True, text=True)
    exclude = subprocess.run(["git", "rev-parse", "--git-path", "info/exclude"], cwd=target, capture_output=True, text=True)
    if root.returncode != 0 or exclude.returncode != 0:
        return False
    path = (target / exclude.stdout.strip()).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(f"/{target.relative_to(Path(root.stdout.strip()).resolve())}/\n")
    return True


def git_advice(target: Path) -> str | None:
    if git_ignore_state(target) != "not-ignored":
        return None
    return "This folder is in a Git repository and is not ignored. For a spike, keep it out with --ignore-locally or .gitignore. For a fixture, version it."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True, help="folder in the project that will hold the kit")
    parser.add_argument("--update-scripts", action="store_true", help="refresh scripts/ and leave cases and configuration alone")
    parser.add_argument("--ignore-locally", action="store_true", help="add the kit to .git/info/exclude, leaving the repository untouched")
    args = parser.parse_args()
    target = Path(args.target).resolve()

    if args.update_scripts:
        if not (target / "eval.config.json").exists():
            print(f"FAILED: no kit in {target}", file=sys.stderr)
            return 2
        copy_scripts(target)
        print(f"scripts updated in {target / 'scripts'}")
        return 0

    if target.exists() and any(target.iterdir()):
        print(f"FAILED: {target} is not empty; refusing to overwrite. Use --update-scripts to refresh the engine.", file=sys.stderr)
        return 2
    shutil.copytree(SKILL_DIR / "assets" / "kit", target, ignore=SKIP, dirs_exist_ok=True)
    copy_scripts(target)
    shutil.copy(target / "eval.config.example.json", target / "eval.config.json")
    shutil.move(str(target / "project-profile.template.md"), target / "project-profile.md")
    shutil.move(str(target / "gitignore.template"), target / ".gitignore")
    print(f"kit copied to {target}")
    if args.ignore_locally:
        print("ignored on this machine through .git/info/exclude" if ignore_locally(target) else "not a Git repository: nothing to ignore")
    elif advice := git_advice(target):
        print(advice)
    print("next:")
    print(f"  cd {target}")
    print("  python3 -B scripts/check_contract.py --config eval.config.json")
    print("  python3 -B scripts/run_golden.py --config eval.config.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
