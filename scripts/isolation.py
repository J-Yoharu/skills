"""Copy-only installation checks. Isolation from repository layout, NOT an OS sandbox."""
from __future__ import annotations

import os
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile

from .common import ToolError, file_list, require, run
from .validation import validate_skill


def clean_environment(home: Path) -> dict[str, str]:
    # Do not pass developer/cloud credentials or language module search paths.
    result = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT") if key in os.environ}
    result.update({"HOME": str(home), "USERPROFILE": str(home), "TMPDIR": str(home),
                   "TEMP": str(home), "TMP": str(home), "CI": "1", "NO_COLOR": "1",
                   "PYTHONDONTWRITEBYTECODE": "1", "DISABLE_TELEMETRY": "1",
                   "DO_NOT_TRACK": "1", "LANG": "C.UTF-8"})
    return result


def isolate_skill(root: Path, item: dict) -> dict:
    validate_skill(root, item)
    name = item["name"]
    with tempfile.TemporaryDirectory(prefix="agent-skill-isolated-") as temporary:
        base = Path(temporary)
        copied = base / "installation" / name
        shutil.copytree(root / "skills" / name, copied)
        home = base / "home"
        home.mkdir()
        environment = clean_environment(home)
        # Validate references against the copy, not against the monorepo.
        validate_skill(root, item, skill_dir=copied)
        files = file_list(copied)
        for path in files:
            if path.suffix in {".js", ".mjs", ".cjs"}:
                run(["node", "--check", str(path)], cwd=home, env=environment, timeout=20)
            elif path.suffix == ".sh":
                run(["bash", "-n", str(path)], cwd=home, env=environment, timeout=20)
        original_payload = {p.relative_to(copied).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        executed = 0
        for position, smoke in enumerate(item["smoke_tests"]):
            for cwd_kind in ("skill-directory", "unrelated-directory"):
                work = base / f"work-{position}-{cwd_kind}"
                work.mkdir()
                args = [arg.replace("{skill}", str(copied)).replace("{work}", str(work))
                        for arg in smoke["command"]]
                if args[0] == "python":
                    # Ignore PYTHON* configuration; do not load site packages; retain bundled imports.
                    args = [sys.executable, "-E", "-S", "-B", *args[1:]]
                cwd = copied if cwd_kind == "skill-directory" else work
                result = run(args, cwd=cwd, env=environment, timeout=smoke["timeout_seconds"], check=False)
                require(result.returncode == smoke["expected_exit"],
                        f"{name}/{smoke['name']} ({cwd_kind}): exit {result.returncode}, expected {smoke['expected_exit']}.\n{result.stderr[-4000:]}")
                require(smoke["stdout_contains"] in result.stdout,
                        f"{name}/{smoke['name']} ({cwd_kind}): expected output not observed.\n{result.stdout[-4000:]}")
                current_payload = {p.relative_to(copied).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in file_list(copied)}
                require(current_payload == original_payload,
                        f"{name}/{smoke['name']}: smoke test modified the installed skill. Write outputs to {{work}}, not {{skill}}.")
                executed += 1
        return {"name": name, "copied_files": len(files), "smoke_executions": executed,
                "behavioral_llm_evaluation": "not executed by this command"}
