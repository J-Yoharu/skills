"""Small synthetic repositories; test cost does not grow with the user's catalog."""
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.fingerprints import payload_fingerprint
from scripts.common import DEFAULT_ROOT, atomic_write, json_text, load_json, run, write_json
from scripts.repository import activate_skill, new_skill, render_catalog, sync_release_config


class RepositoryCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="skills-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        shutil.copytree(DEFAULT_ROOT / "schemas", self.root / "schemas")
        for folder in ("skills", "catalog", "docs", "scripts", "tests/scripts", "tests/skills", ".github/workflows"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        for file in ("LICENSE", ".gitignore"):
            shutil.copyfile(DEFAULT_ROOT / file, self.root / file)
        write_json(self.root / "repository.json", {
            "schema_version": 1, "name": "Synthetic fixture", "github": None,
            "limits": {"max_skill_lines": 500, "max_file_bytes": 2097152, "max_skill_bytes": 10485760},
            "ci": {"max_shards": 16},
        })
        atomic_write(self.root / "version.txt", "0.0.0\n")
        atomic_write(self.root / "CHANGELOG.md", "# Test catalog\n")
        write_json(self.root / ".release-please-manifest.json", {".": "0.0.0"})
        sync_release_config(self.root)
        atomic_write(self.root / "docs/CATALOG.md", render_catalog(self.root))

    def draft(self, name="alpha-skill"):
        new_skill(self.root, name)
        return self.root / "skills" / name

    def ready(self, name="alpha-skill"):
        directory = self.draft(name)
        self.instructions(name)
        self.evals(name)
        return directory

    def instructions(self, name="alpha-skill", body=None):
        path = self.root / "skills" / name / "SKILL.md.template"
        if not path.exists():
            path = path.with_name("SKILL.md")
        body = body or "# Synthetic fixture\n\nRead the supplied fixture and report exactly its contents. Do not modify the input.\n"
        atomic_write(path, f'''---
name: {name}
description: Read a synthetic local fixture when explicitly asked to run the fixture test.
license: MIT
metadata:
  version: "0.0.0" # x-release-please-version
---

{body}''')

    def evals(self, name="alpha-skill", approved=True):
        write_json(self.root / "tests/skills" / name / "evals.json", {
            "schema_version": 1, "skill": name,
            "review": {"status": "approved" if approved else "pending",
                       "payload_sha256": payload_fingerprint(self.root / "skills" / name),
                       "evidence": "SYNTHETIC TEST FIXTURE: approval is simulated inside this unit test, not a user skill evaluation."},
            "cases": [
                {"id": "positive", "prompt": "Read the explicit synthetic fixture.", "should_trigger": True,
                 "expected_behaviors": ["Read the specified fixture and report its exact contents."]},
                {"id": "negative", "prompt": "Write a fictional poem, unrelated to fixture reading.", "should_trigger": False,
                 "expected_behaviors": ["Do not activate the synthetic fixture reader."]},
            ],
        })

    def active(self, name="alpha-skill"):
        directory = self.ready(name)
        activate_skill(self.root, name)
        return directory

    def add_script(self, name="alpha-skill", code=None, runtime="python", suffix="py", expected="fixture-ok"):
        path = self.root / "skills" / name / "scripts" / f"inspect.{suffix}"
        atomic_write(path, code or 'print("fixture-ok")\n')
        record = load_json(self.root / "catalog" / f"{name}.json")
        record["entrypoints"] = [f"scripts/inspect.{suffix}"]
        record["smoke_tests"] = [{"name": "inspect", "command": [runtime, f"{{skill}}/scripts/inspect.{suffix}"],
                                  "timeout_seconds": 5, "expected_exit": 0, "stdout_contains": expected}]
        write_json(self.root / "catalog" / f"{name}.json", record)
        return path

    def simulated_release_bump(self, name, version):
        # A local fixture for consistency/packaging tests, not an imitation of the Release Please engine.
        base = self.root if name == "." else self.root / "skills" / name
        old = (base / "version.txt").read_text().strip()
        atomic_write(base / "version.txt", version + "\n")
        if name != ".":
            skill = base / "SKILL.md"
            atomic_write(skill, skill.read_text().replace(f'version: "{old}" #', f'version: "{version}" #'))
        manifest = load_json(self.root / ".release-please-manifest.json")
        manifest["." if name == "." else f"skills/{name}"] = version
        write_json(self.root / ".release-please-manifest.json", manifest)

    def git(self, *args):
        return run(["git", *args], cwd=self.root).stdout.strip()

    def init_git(self):
        self.git("init", "--initial-branch=main")
        self.git("config", "user.email", "fixtures@example.invalid")
        self.git("config", "user.name", "Synthetic Test Fixture")
        self.git("config", "commit.gpgSign", "false")
        self.git("config", "tag.gpgSign", "false")
        self.commit("chore: initialize synthetic fixture")

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")
