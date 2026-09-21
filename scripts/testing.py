"""Repository-owned regression runners; never claim a unit test is an LLM evaluation."""
from __future__ import annotations

from pathlib import Path
import sys
from .common import require, run
from .repository import registry


def maintenance_tests(root: Path) -> None:
    result = run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests/scripts", "-v"], cwd=root, timeout=180)
    print(result.stdout + result.stderr, flush=True)


def skill_tests(root: Path, names: list[str] | None = None) -> list[dict]:
    available = {item["name"] for item in registry(root)}
    chosen = available if names is None else set(names)
    require(chosen <= available, f"Unknown skills in regression selection: {sorted(chosen - available)}")
    results = []
    for name in sorted(chosen):
        folder = root / "tests" / "skills" / name
        files = sorted(folder.glob("test_*.py"))
        require(not any(path.is_symlink() for path in files), "Skill test modules must not be symlinks.")
        if not files:
            results.append({"name": name, "test_modules": 0, "status": "no_unit_suite"})
            continue
        result = run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(folder), "-p", "test_*.py", "-v"], cwd=root, timeout=180)
        print(result.stdout + result.stderr, flush=True)
        results.append({"name": name, "test_modules": len(files), "status": "passed"})
    return results


def selective_check(root: Path, base: str | None, head: str) -> dict:
    from .isolation import isolate_skill
    from .planning import plan
    from .validation import validate_repository
    value = plan(root, base, head)
    validate_repository(root)  # Always validate docs and cross-catalog contracts.
    if value["maintenance"]:
        maintenance_tests(root)
    suites = skill_tests(root, value["selected"])
    selected = set(value["selected"])
    copies = [isolate_skill(root, item) for item in registry(root) if item["name"] in selected]
    return {"plan": value, "skill_suites": suites, "isolation": copies,
            "behavioral_evaluation": "not executed", "remote_writes": False}
