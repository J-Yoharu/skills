"""Deterministic regression tests. These are not LLM behavioral evaluations."""
from __future__ import annotations
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from urllib.parse import unquote, urlsplit

SKILL = Path(__file__).resolve().parents[3] / "skills" / "orquestrar"
EVALS = Path(__file__).resolve().parent
ENTRY = SKILL / ("SKILL.md" if (SKILL / "SKILL.md").exists() else "SKILL.md.template")
SPEC = importlib.util.spec_from_file_location("verify", SKILL / "scripts/verify.py")
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


def minimal_plan():
    return {"schema_version": 1, "run_id": "test", "objective": "Resultado testável",
            "tasks": [{"id": "A", "repo": "app", "status": "pending", "depends_on": []},
                      {"id": "B", "repo": "app", "status": "pending", "depends_on": ["A"]},
                      {"id": "C", "repo": "app", "status": "pending", "depends_on": ["B"]}]}


class PlanTests(unittest.TestCase):
    def test_dependency_order_and_ready(self):
        result = verify.validate_plan(minimal_plan())
        self.assertEqual(result["selected_order"], ["A", "B", "C"])
        self.assertEqual(result["dependency_ready"], ["A"])

    def test_implemented_is_not_dependency_satisfied(self):
        p = minimal_plan(); p["tasks"][0]["status"] = "implemented"
        self.assertEqual(verify.validate_plan(p)["dependency_ready"], [])

    def test_verified_is_not_integrated(self):
        p = minimal_plan(); p["tasks"][0]["status"] = "verified"
        self.assertEqual(verify.validate_plan(p)["dependency_ready"], [])

    def test_integrated_releases_dependent(self):
        p = minimal_plan(); p["tasks"][0]["status"] = "integrated"
        self.assertEqual(verify.validate_plan(p)["dependency_ready"], ["B"])

    def test_delivered_releases_dependent(self):
        p = minimal_plan(); p["tasks"][0]["status"] = "delivered"
        self.assertEqual(verify.validate_plan(p)["dependency_ready"], ["B"])

    def test_until_includes_ancestors_not_descendants(self):
        self.assertEqual(verify.validate_plan(minimal_plan(), "B")["selected_order"], ["A", "B"])

    def test_unknown_until_rejected(self):
        with self.assertRaises(verify.VerificationError): verify.validate_plan(minimal_plan(), "X")

    def test_cycle_rejected(self):
        p = minimal_plan(); p["tasks"][0]["depends_on"] = ["C"]
        with self.assertRaisesRegex(verify.VerificationError, "cycle"): verify.validate_plan(p)

    def test_unknown_dependency_rejected(self):
        p = minimal_plan(); p["tasks"][1]["depends_on"] = ["X"]
        with self.assertRaises(verify.VerificationError): verify.validate_plan(p)

    def test_duplicate_ids_rejected(self):
        p = minimal_plan(); p["tasks"].append(copy.deepcopy(p["tasks"][0]))
        with self.assertRaisesRegex(verify.VerificationError, "Duplicate"): verify.validate_plan(p)

    def test_duplicate_dependencies_rejected(self):
        p = minimal_plan(); p["tasks"][1]["depends_on"] = ["A", "A"]
        with self.assertRaises(verify.VerificationError): verify.validate_plan(p)

    def test_status_is_validated(self):
        for bad in ("done", "PASS", None, 7, [], {}):
            with self.subTest(bad=bad):
                p = minimal_plan(); p["tasks"][0]["status"] = bad
                with self.assertRaises(verify.VerificationError): verify.validate_plan(p)

    def test_missing_minimum_fields_rejected(self):
        for field in ("schema_version", "run_id", "objective", "tasks"):
            p = minimal_plan(); del p[field]
            with self.subTest(field=field), self.assertRaises(verify.VerificationError):
                verify.validate_plan(p)

    def test_blocked_unit_does_not_block_independent_one(self):
        p = minimal_plan(); p["tasks"][0]["status"] = "blocked"
        p["tasks"].append({"id": "D", "repo": "docs", "status": "pending", "depends_on": []})
        self.assertEqual(verify.validate_plan(p)["dependency_ready"], ["D"])

    def test_invalid_scope_rejected(self):
        p = minimal_plan(); p["tasks"][0]["write_scope"] = "src"
        with self.assertRaises(verify.VerificationError): verify.validate_plan(p)

    def test_large_dag_does_not_depend_on_recursion_limit(self):
        p = minimal_plan()
        p["tasks"] = [{"id": f"T{i}", "repo": "r", "status": "pending",
                       "depends_on": [f"T{i-1}"] if i else []} for i in range(2000)]
        self.assertEqual(len(verify.validate_plan(p, "T1999")["selected_order"]), 2000)


class PackageTests(unittest.TestCase):
    def test_skill_has_metadata_and_short_core(self):
        text = ENTRY.read_text()
        self.assertTrue(text.startswith("---\nname: orquestrar\n"))
        # False is the native default; omit the redundant harness-specific key.
        self.assertNotIn("disable-model-invocation: true", text)
        self.assertLess(len(text.splitlines()), 500)
        description = next(line for line in text.splitlines() if line.startswith("description:"))
        self.assertLess(len(description), 1024)

    def resolve_reference(self, target):
        # Section routing uses ordinary Markdown fragments, not filenames
        # containing '#'. Keep containment checks and also validate the heading.
        parsed = urlsplit(target)
        self.assertFalse(parsed.scheme or parsed.netloc)
        path = (SKILL / unquote(parsed.path)).resolve()
        self.assertTrue(path.is_relative_to(SKILL))
        self.assertTrue(path.is_file())
        if parsed.fragment:
            headings, fenced = [], False
            for line in path.read_text().splitlines():
                if line.startswith(("```", "~~~")):
                    fenced = not fenced
                elif not fenced and re.match(r"^#{1,6} ", line):
                    heading = re.sub(r"^#+ ", "", line).strip().lower()
                    headings.append(re.sub(r"[^\w -]", "", heading).replace(" ", "-"))
            self.assertIn(unquote(parsed.fragment), headings)
        return path

    def test_main_references_resolve_within_skill(self):
        for target in re.findall(r"\]\(([^)]+)\)", ENTRY.read_text()):
            with self.subTest(target=target):
                self.resolve_reference(target)

    def test_missing_section_is_not_accepted_as_valid_reference(self):
        with self.assertRaises(AssertionError):
            self.resolve_reference("references/discovery.md#section-does-not-exist")

    def test_fragment_does_not_bypass_skill_boundary(self):
        with self.assertRaises(AssertionError):
            self.resolve_reference("../../AGENTS.md#bounded-search")

    def test_no_original_project_hardcodes_in_runtime(self):
        forbidden = ["cordixhealth", "~/.cordix-dev", "CORDIX_SERVER_PATH", "server/src",
                     "scripts/issue next", "gh project item-list 4"]
        for path in list(SKILL.rglob("*.md")):
            if "evals" in path.parts: continue
            text = path.read_text()
            for literal in forbidden:
                with self.subTest(path=path.name, literal=literal):
                    self.assertNotIn(literal, text)

    def test_all_json_assets_parse(self):
        for path in (SKILL / "assets").glob("*.json"):
            self.assertIsInstance(verify.read_json(path), dict)

    def test_example_run_graph_valid(self):
        result = verify.validate_plan(verify.read_json(SKILL / "assets/run.example.json"), "T2")
        self.assertEqual(result["selected_order"], ["T1", "T2"])

    def test_presentation_metadata_mentions_actual_skill(self):
        self.assertIn("$orquestrar", (SKILL / "agents/openai.yaml").read_text())


if __name__ == "__main__": unittest.main()
