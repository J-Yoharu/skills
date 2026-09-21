"""Agent/Make integration contracts; no native model session or remote operation."""
import contextlib
import io
import re

from scripts.__main__ import main
from scripts.common import DEFAULT_ROOT, load_yaml
from scripts.planning import select_skills
from scripts.repository import configure
from tests.scripts.helpers import RepositoryCase


class AgentOperations(RepositoryCase):
    def test_make_and_shared_instructions_select_all_skills(self):
        names = ["alpha", "beta"]
        for path in ["Makefile", "AGENTS.md", "CLAUDE.md", "docs/AGENT_WORKFLOW.md"]:
            with self.subTest(path=path):
                self.assertEqual(select_skills(names, [path]), names)

    def test_unrelated_documentation_does_not_select_products(self):
        self.assertEqual(select_skills(["alpha", "beta"], ["docs/SETUP.md"]), [])

    def test_identity_check_is_local_and_preserves_configuration(self):
        configure(self.root, "fixture/skills")
        before = (self.root / "repository.json").read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = main(["--root", str(self.root), "verify-identity", "--github", "fixture/skills"])
        self.assertEqual(code, 0)
        self.assertIn("No remote calls", output.getvalue())
        self.assertEqual(before, (self.root / "repository.json").read_bytes())

    def test_identity_mismatch_fails_without_reconfiguring(self):
        configure(self.root, "fixture/skills")
        with contextlib.redirect_stderr(io.StringIO()) as error:
            code = main(["--root", str(self.root), "verify-identity", "--github", "other/skills"])
        self.assertEqual(code, 1)
        self.assertIn("mismatch", error.getvalue())

    def test_unconfigured_identity_is_not_accepted(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--root", str(self.root), "verify-identity", "--github", "fixture/skills"]), 1)

    def test_workflow_tasks_use_declared_make_targets(self):
        makefile = (DEFAULT_ROOT / "Makefile").read_text()
        targets = set(re.findall(r"^([a-z][a-z0-9-]*):", makefile, re.M))
        for path in (DEFAULT_ROOT / ".github/workflows").glob("*.yml"):
            for job in load_yaml(path.read_text())["jobs"].values():
                for step in job.get("steps", []):
                    command = step.get("run", "")
                    self.assertNotRegex(command, r"\bpnpm (?:run |install|bootstrap|check|test|interop|repo:|build:|ci:)")
                    self.assertNotIn(".venv/bin/python", command)
                    for target in re.findall(r"(?:^|\n)\s*make ([a-z][a-z0-9-]*)", command):
                        self.assertIn(target, targets)

    def test_release_workflow_explicitly_acknowledges_publication(self):
        text = (DEFAULT_ROOT / ".github/workflows/release.yml").read_text()
        self.assertIn("make publish-assets CONFIRM_PUBLISH=yes", text)
        self.assertIn("make verify-identity", text)
        self.assertNotIn("make publish-assets", (DEFAULT_ROOT / ".github/workflows/ci.yml").read_text())
