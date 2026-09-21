"""Explicit stdlib-only environment bootstrap shared by Make and pnpm. Never auto-run."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def bootstrap(root: Path = ROOT, *, reference: bool = False) -> None:
    expected = tuple(map(int, (root / ".python-version").read_text().strip().split(".")))
    if sys.version_info[:2] != expected:
        raise RuntimeError(f"Use Python {'.'.join(map(str, expected))} for bootstrap; got {sys.version.split()[0]}.")
    lock = root / ".bootstrap.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise RuntimeError("Another bootstrap is running. Inspect .bootstrap.lock before removing a stale lock.") from exc
    try:
        with handle:
            handle.write(str(os.getpid()))
        python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not python.is_file():
            if reference:
                raise RuntimeError("Run make bootstrap before installing optional reference dependencies.")
            subprocess.run([sys.executable, "-m", "venv", str(root / ".venv")], cwd=root, check=True)
        subprocess.run([str(python), "-c", f"import sys; assert sys.version_info[:2] == {expected!r}, 'Recreate .venv for the required Python version'"], cwd=root, check=True)
        requirements = "requirements-reference.txt" if reference else "requirements-dev.txt"
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", requirements], cwd=root, check=True)
        subprocess.run([str(python), "-m", "pip", "check"], cwd=root, check=True)
        print("Python environment ready. No skill was activated or published.")
    finally:
        lock.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", action="store_true")
    args = parser.parse_args()
    try:
        bootstrap(reference=args.reference)
        return 0
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
