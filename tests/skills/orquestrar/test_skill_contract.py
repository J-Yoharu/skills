"""Package-shape and evaluation-record checks. Not LLM behavioral approval."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills" / "orquestrar"
EVALS = Path(__file__).resolve().parent
ENTRY = SKILL / ("SKILL.md" if (SKILL / "SKILL.md").exists() else "SKILL.md.template")


class SkillContractTests(unittest.TestCase):
    def setUp(self):
        self.text = ENTRY.read_text(encoding="utf-8")
        self.frontmatter = self.text.split("---", 2)[1]

    def test_frontmatter_names_skill_and_never_selects_the_coordinator_model(self):
        self.assertIn("name: orquestrar", self.frontmatter)
        for key in ("model:", "effort:", "model_reasoning_effort:", "context:", "agent:"):
            self.assertFalse(any(line.startswith(key) for line in self.frontmatter.splitlines()), key)

    def test_payload_is_instructions_only(self):
        # Regression: the JSON checkpoint and validators forced every repository into one format.
        files = {p.relative_to(SKILL).as_posix() for p in SKILL.rglob("*") if p.is_file()}
        self.assertEqual(files, {"SKILL.md.template" if ENTRY.name.endswith("template") else "SKILL.md",
                                 "agents/openai.yaml", "LICENSE", "CHANGELOG.md", "version.txt"})
        catalog = json.loads((ROOT / "catalog/orquestrar.json").read_text())
        self.assertEqual((catalog["entrypoints"], catalog["smoke_tests"]), ([], []))
        for stale in ("run.json", "checkpoint-save", "verify.py", "route.py", "profile.py"):
            self.assertNotIn(stale, self.text)

    def test_progress_uses_repository_mechanism_with_markdown_fallback(self):
        self.assertIn(".orquestrar/<run-name>.md", self.text)
        self.assertNotIn("```json", self.text)

    def test_internal_links_resolve(self):
        anchors = {re.sub(r"[^a-z0-9 -]", "", h.lower()).replace(" ", "-")
                   for h in re.findall(r"^#+ (.+)$", self.text, re.M)}
        for target in re.findall(r"\]\(([^)]+)\)", self.text):
            with self.subTest(target=target):
                self.assertTrue(target.startswith("#"), target)
                self.assertIn(target[1:], anchors)

    def test_codex_implicit_activation_enabled(self):
        self.assertIn("allow_implicit_invocation: true", (SKILL / "agents/openai.yaml").read_text())

    def test_eval_cases_cover_review_override_and_negative_activation(self):
        data = json.loads((EVALS / "evals.json").read_text())
        self.assertEqual(data["review"]["status"], "pending")
        cases = {c["id"]: c for c in data["cases"]}
        self.assertTrue(cases["review-override"]["should_trigger"])
        self.assertFalse(cases["discussion-only"]["should_trigger"])

    def test_supplied_scenarios_are_not_claimed_as_executed(self):
        data = json.loads((EVALS / "scenarios.json").read_text())
        self.assertTrue(all(s["execution_status"] == "not_run" for s in data["scenarios"]))


if __name__ == "__main__":
    unittest.main()
