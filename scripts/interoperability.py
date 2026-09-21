"""Opt-in external integration tests. Requires internet and installed skills-ref."""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

from .common import require, run
from .isolation import clean_environment
from .repository import registry

SKILLS_CLI_VERSION = "1.7.0"
REFERENCE_COMMIT = "69ef37e9424c0a7ea9dd2293b559e43ec8176379"


def check_interoperability(root: Path, *, cli: bool = True) -> dict:
    from skills_ref import validate as reference_validate
    results = []
    with tempfile.TemporaryDirectory(prefix="skills-interop-") as temporary:
        home = Path(temporary)
        environment = clean_environment(home)
        for item in registry(root):
            name = item["name"]
            target = home / "reference" / name
            shutil.copytree(root / "skills" / name, target)
            if item["status"] == "draft":
                # Check standard syntax without making the source draft discoverable.
                (target / "SKILL.md.template").rename(target / "SKILL.md")
            errors = reference_validate(target)
            require(not errors, f"Official reference validator rejected {name}: {errors}")
            results.append({"name": name, "reference_valid": True, "installed": False})
            if cli and item["status"] == "active":
                project = home / "consumer" / name
                project.mkdir(parents=True)
                # Use the actual published installer, not an imitation of its copy logic.
                result = run(["npx", "--yes", f"skills@{SKILLS_CLI_VERSION}", "add", str(root.resolve()),
                              "--skill", name, "--agent", "claude-code", "--copy", "--yes"],
                             cwd=project, env=environment, timeout=120)
                installed = project / ".claude" / "skills" / name / "SKILL.md"
                require(installed.is_file(), f"CLI did not install expected file for {name}: {result.stdout[-2000:]}")
                require(installed.read_bytes() == (root / "skills" / name / "SKILL.md").read_bytes(),
                        f"CLI changed SKILL.md for {name}.")
                results[-1]["installed"] = True
    return {"reference_commit": REFERENCE_COMMIT, "skills_cli": SKILLS_CLI_VERSION,
            "results": results, "note": "Drafts are format-checked only; they are deliberately not installed."}
