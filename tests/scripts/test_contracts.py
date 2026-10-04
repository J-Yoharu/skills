import json
from pathlib import Path
import shutil
from unittest.mock import patch

from helpers import RepositoryCase
from scripts.common import ToolError, atomic_write, load_json, load_yaml, local_path, stable_version, write_json
from scripts.repository import activate_skill, configure, entry, new_skill, render_catalog, sync_release_config
from scripts.validation import frontmatter, markdown_links, validate_repository, validate_skill


class FormatTests(RepositoryCase):
    def test_empty_repository_is_valid(self):
        self.assertEqual(validate_repository(self.root), [])

    def test_draft_is_valid_but_not_discoverable(self):
        directory = self.draft()
        self.assertFalse((directory / "SKILL.md").exists())
        self.assertEqual(validate_repository(self.root)[0]["status"], "draft")

    def test_duplicate_yaml_key_rejected(self):
        with self.assertRaisesRegex(ToolError, "Duplicate YAML"):
            load_yaml("name: a\nname: b\n")

    def test_yaml_anchors_rejected(self):
        with self.assertRaisesRegex(ToolError, "anchors"):
            load_yaml("name: &anchor text\nother: *anchor\n")

    def test_yaml_custom_constructor_rejected(self):
        with self.assertRaises(ToolError):
            load_yaml('x: !!python/object/apply:os.system ["echo unsafe"]')

    def test_yaml_on_is_not_a_boolean(self):
        self.assertEqual(load_yaml("on:\n  push: true\n"), {"on": {"push": True}})

    def test_duplicate_json_key_rejected(self):
        path = self.root / "bad.json"
        atomic_write(path, '{"name":"a","name":"b"}')
        with self.assertRaisesRegex(ToolError, "Duplicate JSON"):
            load_json(path)

    def test_name_directory_mismatch_rejected(self):
        directory = self.draft()
        path = directory / "SKILL.md.template"
        atomic_write(path, path.read_text().replace("name: alpha-skill", "name: other-skill"))
        with self.assertRaisesRegex(ToolError, "name must equal"):
            validate_repository(self.root)

    def test_boolean_metadata_rejected(self):
        directory = self.draft()
        path = directory / "SKILL.md.template"
        atomic_write(path, path.read_text().replace('metadata:\n', 'metadata:\n  internal: true\n'))
        with self.assertRaisesRegex(ToolError, "strings to strings"):
            validate_repository(self.root)

    def test_missing_frontmatter_rejected(self):
        directory = self.draft()
        atomic_write(directory / "SKILL.md.template", "# Skill with no metadata\n")
        with self.assertRaisesRegex(ToolError, "frontmatter"):
            validate_repository(self.root)

    def test_extra_frontmatter_field_rejected(self):
        directory = self.draft()
        path = directory / "SKILL.md.template"
        atomic_write(path, path.read_text().replace("license: MIT", "license: MIT\nversion: 1.0.0"))
        with self.assertRaisesRegex(ToolError, "unsupported frontmatter"):
            validate_repository(self.root)

    def test_too_long_description_rejected(self):
        directory = self.draft()
        text = (directory / "SKILL.md.template").read_text()
        start, end = text.index("description:"), text.index("license:")
        atomic_write(directory / "SKILL.md.template", text[:start] + "description: " + "x" * 1025 + "\n" + text[end:])
        with self.assertRaisesRegex(ToolError, "description"):
            validate_repository(self.root)

    def test_line_limit_is_configurable_and_enforced(self):
        directory = self.draft()
        config = load_json(self.root / "repository.json")
        config["limits"]["max_skill_lines"] = 20
        write_json(self.root / "repository.json", config)
        with self.assertRaisesRegex(ToolError, "exceeds 20 lines"):
            validate_repository(self.root)

    def test_stable_semver_policy(self):
        self.assertEqual(stable_version("0.1.0"), "0.1.0")
        for value in ("01.2.3", "1.0", "v1.0.0", "1.0.0-beta.1", "1.0.0;rm -rf /"):
            with self.subTest(value=value), self.assertRaises(ToolError):
                stable_version(value)

    def test_root_skill_is_rejected(self):
        atomic_write(self.root / "SKILL.md", "not a root skill\n")
        with self.assertRaisesRegex(ToolError, "Unexpected discoverable"):
            validate_repository(self.root)

    def test_unregistered_skill_is_rejected(self):
        (self.root / "skills/rogue").mkdir()
        with self.assertRaisesRegex(ToolError, "Unregistered"):
            validate_repository(self.root)


class BoundaryTests(RepositoryCase):
    def test_valid_local_link(self):
        directory = self.ready()
        atomic_write(directory / "references/guide.md", "# Guide\n")
        self.instructions(body="# Skill\n\nRead [guide](references/guide.md).\n")
        validate_repository(self.root)

    def test_broken_local_link_rejected(self):
        self.ready()
        self.instructions(body="# Skill\n\nRead [missing](references/missing.md).\n")
        with self.assertRaisesRegex(ToolError, "broken local link"):
            validate_repository(self.root)

    def test_link_outside_skill_rejected(self):
        self.ready()
        self.instructions(body="# Skill\n\nRead [root](../../LICENSE).\n")
        with self.assertRaisesRegex(ToolError, "escapes skill"):
            validate_repository(self.root)

    def test_encoded_link_escape_rejected(self):
        self.ready()
        self.instructions(body="# Skill\n\nRead [root](%2e%2e/%2e%2e/LICENSE).\n")
        with self.assertRaisesRegex(ToolError, "escapes skill"):
            validate_repository(self.root)

    def test_external_links_not_requested(self):
        self.ready()
        self.instructions(body="# Skill\n\nRead [remote](https://example.invalid/doc).\n")
        validate_repository(self.root)

    def test_inline_code_resource_path_checked(self):
        self.ready()
        self.instructions(body="# Skill\n\nRead `references/missing.md`.\n")
        with self.assertRaisesRegex(ToolError, "Missing file"):
            validate_repository(self.root)

    def test_markdown_reference_html_and_parentheses(self):
        text = '[Guide](references/a(b).md)\n[ref]: references/c.md\n<img src="assets/icon.png">\n'
        self.assertEqual(set(markdown_links(text)), {"references/a(b).md", "references/c.md", "assets/icon.png"})

    def test_code_fence_examples_not_treated_as_links(self):
        self.assertEqual(markdown_links('```md\n[x](missing.md)\n```\n'), [])

    def test_symlink_rejected(self):
        directory = self.draft()
        try:
            (directory / "assets/outside").symlink_to(self.root / "LICENSE")
        except OSError:
            self.skipTest("Symlink permission unavailable on this runner")
        with self.assertRaisesRegex(ToolError, "Symlink"):
            validate_repository(self.root)

    def test_nested_skill_rejected(self):
        directory = self.draft()
        atomic_write(directory / "references/nested/SKILL.md", "bad\n")
        with self.assertRaisesRegex(ToolError, "Unexpected discoverable"):
            validate_repository(self.root)

    def test_environment_file_rejected(self):
        directory = self.draft()
        atomic_write(directory / ".env", "TOKEN=test\n")
        with self.assertRaisesRegex(ToolError, "Environment file"):
            validate_repository(self.root)

    def test_fixture_tree_not_shipped(self):
        directory = self.draft()
        atomic_write(directory / "tests/fixture.json", "{}\n")
        with self.assertRaisesRegex(ToolError, "Development-only"):
            validate_repository(self.root)

    def test_case_collision_rejected(self):
        directory = self.draft()
        atomic_write(directory / "assets/case.txt", "first\n")
        atomic_write(directory / "assets/Case.txt", "second\n")
        if len(list((directory / "assets").glob("*.txt"))) < 2:
            self.skipTest("Case-insensitive filesystem cannot create this fixture")
        with self.assertRaisesRegex(ToolError, "Case-insensitive"):
            validate_repository(self.root)

    def test_nonbundled_python_import_rejected(self):
        self.ready()
        self.add_script(code='import yaml\nprint("fixture-ok")\n')
        with self.assertRaisesRegex(ToolError, "non-bundled import"):
            validate_repository(self.root)

    def test_repository_python_import_rejected(self):
        self.ready()
        self.add_script(code='from scripts.common import run\nprint("fixture-ok")\n')
        with self.assertRaisesRegex(ToolError, "non-bundled import"):
            validate_repository(self.root)

    def test_javascript_cross_skill_import_rejected(self):
        self.ready()
        self.add_script(code="import other from '../../../other/dep.mjs';\nconsole.log('fixture-ok');\n", runtime="node", suffix="mjs")
        with self.assertRaisesRegex(ToolError, "import escapes"):
            validate_repository(self.root)

    def test_javascript_npm_runtime_dependency_rejected(self):
        self.ready()
        self.add_script(code="import x from 'lodash';\nconsole.log('fixture-ok');\n", runtime="node", suffix="mjs")
        with self.assertRaisesRegex(ToolError, "node: built-ins"):
            validate_repository(self.root)

    def test_script_registration_required(self):
        directory = self.ready()
        atomic_write(directory / "scripts/unregistered.py", 'print("hello")\n')
        with self.assertRaisesRegex(ToolError, "register script entrypoints"):
            validate_repository(self.root)

    def test_smoke_output_assertion_required(self):
        self.ready()
        self.add_script()
        path = self.root / "catalog/alpha-skill.json"
        value = load_json(path)
        value["smoke_tests"][0].pop("stdout_contains")
        write_json(path, value)
        with self.assertRaisesRegex(ToolError, "assert stdout_contains"):
            validate_repository(self.root)

    def test_shell_command_not_allowed_in_smoke(self):
        self.ready()
        self.add_script()
        path = self.root / "catalog/alpha-skill.json"
        value = load_json(path)
        value["smoke_tests"][0]["command"] = ["bash", "-c", "echo bad"]
        write_json(path, value)
        with self.assertRaises(ToolError):
            validate_repository(self.root)


class LifecycleTests(RepositoryCase):
    def test_duplicate_creation_does_not_overwrite(self):
        directory = self.draft()
        before = (directory / "SKILL.md.template").read_bytes()
        with self.assertRaisesRegex(ToolError, "already exists"):
            new_skill(self.root, "alpha-skill")
        self.assertEqual((directory / "SKILL.md.template").read_bytes(), before)

    def test_traversal_slug_rejected(self):
        for name in ("../evil", "other/name", "UPPER", "a--b", "-bad", "bad-", "x" * 65):
            with self.subTest(name=name), self.assertRaises(ToolError):
                new_skill(self.root, name)

    def test_placeholder_cannot_activate_and_rolls_back(self):
        directory = self.draft()
        with self.assertRaisesRegex(ToolError, "unfinished placeholder"):
            activate_skill(self.root, "alpha-skill")
        self.assertTrue((directory / "SKILL.md.template").is_file())
        self.assertFalse((directory / "SKILL.md").exists())
        self.assertEqual(entry(self.root, "alpha-skill")["status"], "draft")
        validate_repository(self.root)

    def test_pending_review_cannot_activate(self):
        directory = self.ready()
        self.evals(approved=False)
        with self.assertRaisesRegex(ToolError, "approved human evaluation"):
            activate_skill(self.root, "alpha-skill")
        self.assertTrue((directory / "SKILL.md.template").exists())

    def test_active_requires_negative_case(self):
        self.ready()
        path = self.root / "tests/skills/alpha-skill/evals.json"
        value = load_json(path)
        value["cases"] = value["cases"][:1]
        write_json(path, value)
        with self.assertRaisesRegex(ToolError, "positive and negative"):
            activate_skill(self.root, "alpha-skill")

    def test_activation_updates_registry_and_release_paths(self):
        directory = self.active()
        self.assertTrue((directory / "SKILL.md").exists())
        self.assertFalse((directory / "SKILL.md.template").exists())
        config = load_json(self.root / "release-please-config.json")
        self.assertIn("skills/alpha-skill", config["packages"])
        self.assertEqual(config["packages"]["."]["initial-version"], "0.1.0")
        self.assertEqual(config["packages"]["skills/alpha-skill"]["initial-version"], "0.1.0")
        self.assertEqual(config["packages"]["skills/alpha-skill"]["extra-files"], [{"type": "generic", "path": "SKILL.md"}])
        self.assertTrue(config["packages"]["skills/alpha-skill"]["skip-github-release"])
        validate_repository(self.root)

    def test_release_config_drift_fails(self):
        self.draft()
        config = load_json(self.root / "release-please-config.json")
        config["separate-pull-requests"] = True
        write_json(self.root / "release-please-config.json", config)
        with self.assertRaisesRegex(ToolError, "Release config drift"):
            validate_repository(self.root)
        sync_release_config(self.root)
        validate_repository(self.root)

    def test_sync_preserves_independent_versions(self):
        self.active("alpha-skill")
        self.active("beta-skill")
        self.simulated_release_bump("alpha-skill", "1.2.3")
        self.simulated_release_bump("beta-skill", "0.4.0")
        self.simulated_release_bump(".", "2.0.0")
        before = load_json(self.root / ".release-please-manifest.json")
        sync_release_config(self.root)
        self.assertEqual(before, load_json(self.root / ".release-please-manifest.json"))
        validate_repository(self.root)

    def test_sync_refuses_version_reset(self):
        self.active()
        atomic_write(self.root / "skills/alpha-skill/version.txt", "1.0.0\n")
        with self.assertRaisesRegex(ToolError, "Version mismatch"):
            sync_release_config(self.root)

    def test_generated_catalog_drift_fails(self):
        self.draft()
        atomic_write(self.root / "docs/CATALOG.md", "handwritten\n")
        with self.assertRaisesRegex(ToolError, "catalog drift"):
            validate_repository(self.root)

    def test_configure_updates_identity_without_remote_access(self):
        self.active()
        configure(self.root, "some-owner/agent-skills", "@some-owner")
        self.assertIn("some-owner/agent-skills", (self.root / "docs/CATALOG.md").read_text())
        self.assertIn("* @some-owner", (self.root / ".github/CODEOWNERS").read_text())
        validate_repository(self.root)

    def test_failed_scaffold_cleans_up_created_directories(self):
        with patch("scripts.repository.sync_release_config", side_effect=ToolError("simulated failure")):
            with self.assertRaisesRegex(ToolError, "simulated"):
                new_skill(self.root, "alpha-skill")
        self.assertFalse((self.root / "skills/alpha-skill").exists())
        self.assertFalse((self.root / "catalog/alpha-skill.json").exists())
        self.assertFalse((self.root / "tests/skills/alpha-skill").exists())
        validate_repository(self.root)
