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


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"; self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "tests@example.invalid")
        self.git("config", "user.name", "Local tests")
        self.git("config", "commit.gpgsign", "false")
        (self.repo / "app.py").write_text("value = 1\n", encoding="utf-8")
        (self.repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        self.git("add", "app.py", ".gitignore"); self.git("commit", "-qm", "fixture")

    def tearDown(self): self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, timeout=15).stdout

    def test_unchanged_snapshot_matches(self):
        old = verify.snapshot(self.repo)
        self.assertTrue(verify.compare(self.repo, old)["same"])

    def test_same_diff_stat_does_not_hide_changed_behavior(self):
        (self.repo / "app.py").write_text("value = 2\n")
        status1, stat1 = self.git("status", "--short"), self.git("diff", "--stat")
        old = verify.snapshot(self.repo)
        (self.repo / "app.py").write_text("value = 3\n")
        self.assertEqual(status1, self.git("status", "--short"))
        self.assertEqual(stat1, self.git("diff", "--stat"))
        self.assertFalse(verify.compare(self.repo, old)["same"])

    def test_untracked_content_is_covered(self):
        p = self.repo / "new.txt"; p.write_text("first")
        old = verify.snapshot(self.repo); p.write_text("other")
        self.assertEqual(verify.compare(self.repo, old)["changed_files"], ["new.txt"])

    def test_deletion_is_covered(self):
        old = verify.snapshot(self.repo); (self.repo / "app.py").unlink()
        self.assertFalse(verify.compare(self.repo, old)["same"])

    def test_new_untracked_file_is_covered(self):
        old = verify.snapshot(self.repo); (self.repo / "other.py").write_text("x = 1")
        self.assertIn("other.py", verify.compare(self.repo, old)["changed_files"])

    def test_index_only_change_is_covered(self):
        (self.repo / "app.py").write_text("value = 2\n")
        old = verify.snapshot(self.repo); self.git("add", "app.py")
        result = verify.compare(self.repo, old)
        self.assertFalse(result["same"]); self.assertTrue(result["index_changed"])
        self.assertEqual(result["changed_files"], [])

    def test_head_change_is_covered(self):
        old = verify.snapshot(self.repo); self.git("commit", "--allow-empty", "-qm", "new head")
        self.assertTrue(verify.compare(self.repo, old)["head_changed"])

    def test_ignored_content_not_claimed_as_covered(self):
        old = verify.snapshot(self.repo); (self.repo / "ignored.txt").write_text("runtime differs")
        self.assertTrue(verify.compare(self.repo, old)["same"])

    def test_context_change_invalidates_snapshot(self):
        old = verify.snapshot(self.repo, {"image": "v1"})
        result = verify.compare(self.repo, old, {"image": "v2"})
        self.assertFalse(result["same"]); self.assertTrue(result["context_changed"])

    def test_tampered_payload_is_rejected(self):
        old = verify.snapshot(self.repo); old["payload"]["context"] = {"forged": True}
        with self.assertRaisesRegex(verify.VerificationError, "Inconsistent"):
            verify.compare(self.repo, old)

    def test_non_repository_reports_controlled_error(self):
        with self.assertRaises(verify.VerificationError): verify.snapshot(self.base)

    def test_unborn_repository_supported(self):
        other = self.base / "empty"; other.mkdir()
        subprocess.run(["git", "-C", str(other), "init", "-q"], check=True)
        self.assertIsNone(verify.snapshot(other)["payload"]["head"])

    def test_metadata_output_not_added_to_fingerprint(self):
        old = verify.snapshot(self.repo)
        dest = self.repo / ".git/orquestrar/runs/test/snapshot.json"
        verify.write_snapshot(dest, old)
        self.assertTrue(verify.compare(self.repo, old)["same"])

    def test_output_inside_product_tree_rejected(self):
        with self.assertRaises(verify.VerificationError):
            verify.write_snapshot(self.repo / "snapshot.json", verify.snapshot(self.repo))

    def test_output_does_not_overwrite_existing_file(self):
        dest = self.base / "proof.json"; dest.write_text("original")
        with self.assertRaises(verify.VerificationError):
            verify.write_snapshot(dest, verify.snapshot(self.repo))
        self.assertEqual(dest.read_text(), "original")

    def test_inherited_git_dir_does_not_change_target(self):
        with mock.patch.dict(os.environ, {"GIT_DIR": str(self.base / "missing")}):
            self.assertEqual(verify.snapshot(self.repo)["payload"]["repo"], str(self.repo))

    def test_nested_repository_is_explicitly_unsupported(self):
        nested = self.repo / "nested"; nested.mkdir()
        subprocess.run(["git", "-C", str(nested), "init", "-q"], check=True)
        (nested / "file.txt").write_text("nested")
        with self.assertRaises(verify.VerificationError): verify.snapshot(self.repo)

    def test_gitlink_requires_separate_snapshot(self):
        head = self.git("rev-parse", "HEAD").strip().decode()
        self.git("update-index", "--add", "--cacheinfo", f"160000,{head},submodule")
        with self.assertRaisesRegex(verify.VerificationError, "Submodule"):
            verify.snapshot(self.repo)

    @unittest.skipUnless(hasattr(os, "symlink") and os.name != "nt", "symlinks require supported permissions")
    def test_symlink_target_not_followed(self):
        external = self.base / "external"; external.write_text("first")
        (self.repo / "link").symlink_to(external)
        old = verify.snapshot(self.repo); external.write_text("changed")
        self.assertTrue(verify.compare(self.repo, old)["same"])
        record = old["payload"]["files"]["link"]
        self.assertEqual(record["kind"], "symlink")
        self.assertNotIn("sha256", record)

    def test_unicode_and_newline_file_names(self):
        names = ["ação.txt", "with space.txt"]
        if os.name != "nt": names.append("line\nbreak.txt")
        for name in names: (self.repo / name).write_text("data")
        result = verify.snapshot(self.repo)
        for name in names: self.assertIn(name, result["payload"]["files"])

    def test_cli_reports_difference_with_exit_one(self):
        old = verify.snapshot(self.repo); proof = self.base / "proof.json"
        proof.write_text(json.dumps(old))
        (self.repo / "app.py").write_text("value = 4\n")
        p = subprocess.run([sys.executable, str(SKILL / "scripts/verify.py"), "compare",
                            "--repo", str(self.repo), "--snapshot", str(proof)], capture_output=True)
        self.assertEqual(p.returncode, 1); self.assertFalse(json.loads(p.stdout)["same"])

    def test_invalid_json_is_controlled_error(self):
        bad = self.base / "invalid.json"; bad.write_text("{not json")
        with self.assertRaises(verify.VerificationError): verify.read_json(bad)


class PackageTests(unittest.TestCase):
    def test_skill_has_metadata_and_short_core(self):
        text = ENTRY.read_text()
        self.assertTrue(text.startswith("---\nname: orquestrar\n"))
        # False is the native default; omit the redundant harness-specific key.
        self.assertNotIn("disable-model-invocation: true", text)
        self.assertLess(len(text.splitlines()), 500)
        description = next(line for line in text.splitlines() if line.startswith("description:"))
        self.assertLess(len(description), 1024)

    def test_main_references_resolve_within_skill(self):
        text = ENTRY.read_text()
        for target in re.findall(r"\]\(([^)]+)\)", text):
            with self.subTest(target=target):
                path = (SKILL / target).resolve()
                self.assertTrue(path.is_relative_to(SKILL))
                self.assertTrue(path.is_file())

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
