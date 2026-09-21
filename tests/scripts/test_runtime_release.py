import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import unittest
from unittest.mock import patch

from helpers import RepositoryCase
from scripts.common import ToolError, atomic_write, load_json, write_json
from scripts.isolation import clean_environment, isolate_skill
from scripts.packaging import archive_skill, build, verify_release_context
from scripts.publishing import publish_assets
from scripts.repository import configure, registry


class IsolationTests(RepositoryCase):
    def test_runs_from_both_directories(self):
        folder = self.ready()
        atomic_write(folder / 'assets/data.txt', 'fixture-ok')
        self.add_script(code='from pathlib import Path\nprint((Path(__file__).resolve().parents[1] / "assets/data.txt").read_text())\n')
        result = isolate_skill(self.root, registry(self.root)[0])
        self.assertEqual(result['smoke_executions'], 2)

    def test_cwd_dependent_script_fails(self):
        folder = self.ready()
        atomic_write(folder / 'assets/data.txt', 'fixture-ok')
        self.add_script(code='from pathlib import Path\nprint(Path("assets/data.txt").read_text())\n')
        with self.assertRaisesRegex(ToolError, 'unrelated-directory'):
            isolate_skill(self.root, registry(self.root)[0])

    def test_bundled_python_helper_works(self):
        folder = self.ready()
        atomic_write(folder / 'scripts/helper.py', 'VALUE = "fixture-ok"\n')
        # Nested helper is not an independent entrypoint.
        (folder / 'scripts/helper.py').unlink()
        atomic_write(folder / 'scripts/lib/__init__.py', '')
        atomic_write(folder / 'scripts/lib/helper.py', 'VALUE = "fixture-ok"\n')
        self.add_script(code='from lib.helper import VALUE\nprint(VALUE)\n')
        self.assertEqual(isolate_skill(self.root, registry(self.root)[0])['smoke_executions'], 2)

    def test_environment_drops_secrets_and_pythonpath(self):
        with patch.dict(os.environ, {'AWS_SECRET_ACCESS_KEY': 'private', 'GH_TOKEN': 'private', 'PYTHONPATH': '/bad'}):
            env = clean_environment(self.root)
        for key in ('AWS_SECRET_ACCESS_KEY', 'GH_TOKEN', 'PYTHONPATH'):
            self.assertNotIn(key, env)

    def test_wrong_output_fails(self):
        self.ready()
        self.add_script(code='print("wrong")\n')
        with self.assertRaisesRegex(ToolError, 'expected output'):
            isolate_skill(self.root, registry(self.root)[0])

    def test_missing_command_fails_clearly(self):
        self.ready()
        self.add_script(runtime='node', suffix='mjs', code='console.log("fixture-ok");\n')
        with patch('scripts.isolation.run', side_effect=ToolError('Executable not found: node')):
            with self.assertRaisesRegex(ToolError, 'Executable not found'):
                isolate_skill(self.root, registry(self.root)[0])

    def test_modifying_installed_payload_fails(self):
        self.ready()
        self.add_script(code='from pathlib import Path\nPath(__file__).with_name("generated.txt").write_text("unexpected")\nprint("fixture-ok")\n')
        with self.assertRaisesRegex(ToolError, 'modified the installed skill'):
            isolate_skill(self.root, registry(self.root)[0])

    def test_python_site_packages_are_not_loaded(self):
        self.ready()
        self.add_script(code='import sys\nassert "site" not in sys.modules\nprint("fixture-ok")\n')
        self.assertEqual(isolate_skill(self.root, registry(self.root)[0])['smoke_executions'], 2)

    def test_output_can_be_written_to_work_directory(self):
        self.ready()
        self.add_script(code='from pathlib import Path\nimport sys\nPath(sys.argv[1]).write_text("fixture-ok")\nprint("fixture-ok")\n')
        item = load_json(self.root / 'catalog/alpha-skill.json')
        item['smoke_tests'][0]['command'].append('{work}/result.txt')
        write_json(self.root / 'catalog/alpha-skill.json', item)
        self.assertEqual(isolate_skill(self.root, item)['smoke_executions'], 2)

    @unittest.skipUnless(shutil.which('node'), 'Node not installed')
    def test_bundled_node_module_runs(self):
        folder = self.ready()
        atomic_write(folder / 'assets/data.txt', 'fixture-ok')
        self.add_script(runtime='node', suffix='mjs', code='import { readFileSync } from "node:fs";\nconsole.log(readFileSync(new URL("../assets/data.txt", import.meta.url), "utf8"));\n')
        self.assertEqual(isolate_skill(self.root, registry(self.root)[0])['smoke_executions'], 2)

    @unittest.skipUnless(shutil.which('node'), 'Node not installed')
    def test_node_syntax_error_is_detected(self):
        self.ready()
        self.add_script(runtime='node', suffix='mjs', code='const = ;\n')
        with self.assertRaises(ToolError):
            isolate_skill(self.root, registry(self.root)[0])


class PackagingTests(RepositoryCase):
    def test_preview_excludes_drafts(self):
        self.draft()
        self.assertEqual(build(self.root, self.root / 'dist', preview=True)['skills'], [])

    def test_archive_is_repeatable_and_contains_only_skill(self):
        folder = self.active()
        one, files = archive_skill(folder, 'alpha-skill')
        two, _ = archive_skill(folder, 'alpha-skill')
        self.assertEqual(one, two)
        with tarfile.open(fileobj=io.BytesIO(one), mode='r:gz') as archive:
            names = archive.getnames()
            self.assertIn('alpha-skill/LICENSE', names)
            self.assertIn('alpha-skill/SKILL.md', names)
            self.assertTrue(all(name.startswith('alpha-skill/') for name in names))
            self.assertFalse(any('/tests/' in name or '/tooling/' in name or name.endswith('.gitkeep') for name in names))
            self.assertTrue(all(info.uid == 0 and info.mtime == 0 for info in archive.getmembers()))

    def test_changed_content_changes_hash(self):
        folder = self.active()
        one, _ = archive_skill(folder, 'alpha-skill')
        atomic_write(folder / 'assets/new.txt', 'new')
        two, _ = archive_skill(folder, 'alpha-skill')
        self.assertNotEqual(hashlib.sha256(one).hexdigest(), hashlib.sha256(two).hexdigest())

    def test_index_and_checksums_match(self):
        self.active()
        self.draft('second-skill')
        output = self.root / 'dist'
        index = build(self.root, output, preview=True)
        self.assertEqual(len(index['skills']), 1)
        for line in (output / 'SHA256SUMS').read_text().splitlines():
            sha, name = line.split('  ', 1)
            self.assertEqual(sha, hashlib.sha256((output / name).read_bytes()).hexdigest())
        self.assertEqual(index['mode'], 'preview')
        self.assertIsNone(index['tag'])

    def test_builder_does_not_overwrite_user_directory(self):
        folder = self.root / 'dist'
        folder.mkdir()
        atomic_write(folder / 'important.txt', 'preserve')
        with self.assertRaisesRegex(ToolError, 'Refusing to replace'):
            build(self.root, folder, preview=True)
        self.assertEqual((folder / 'important.txt').read_text(), 'preserve')

    def test_builder_refuses_outside_dist(self):
        with self.assertRaisesRegex(ToolError, 'Output must'):
            build(self.root, self.root / 'skills', preview=True)

    def prepare_release(self):
        self.active()
        configure(self.root, 'fixture-owner/fixture-repo')
        self.simulated_release_bump('alpha-skill', '1.0.0')
        self.simulated_release_bump('.', '1.0.0')
        self.init_git()
        self.git('tag', 'v1.0.0')

    def test_real_git_tagged_fixture_builds(self):
        self.prepare_release()
        result = build(self.root, self.root / 'dist', preview=False, tag='v1.0.0')
        self.assertEqual(result['mode'], 'release')
        self.assertEqual(result['gitCommit'], self.git('rev-parse', 'HEAD'))
        self.assertEqual(result['skills'][0]['version'], '1.0.0')

    def test_release_dirty_tree_fails(self):
        self.prepare_release()
        atomic_write(self.root / 'uncommitted.txt', 'dirty')
        with self.assertRaisesRegex(ToolError, 'clean working tree'):
            verify_release_context(self.root, 'v1.0.0')

    def test_release_mismatched_tag_fails(self):
        self.prepare_release()
        with self.assertRaisesRegex(ToolError, 'differs from the catalog'):
            verify_release_context(self.root, 'v2.0.0')

    def test_release_not_at_tag_fails(self):
        self.prepare_release()
        self.commit('chore: unrelated later commit')
        with self.assertRaisesRegex(ToolError, 'exact tagged commit'):
            verify_release_context(self.root, 'v1.0.0')

    def test_bootstrap_not_releasable(self):
        self.active()
        with self.assertRaisesRegex(ToolError, 'bootstrap'):
            verify_release_context(self.root, 'v0.0.0')

    def test_changed_payload_without_skill_bump_fails(self):
        self.prepare_release()
        atomic_write(self.root / 'skills/alpha-skill/assets/change.txt', 'changed')
        self.evals()
        self.simulated_release_bump('.', '1.1.0')
        self.commit('feat(alpha-skill): content change fixture')
        self.git('tag', 'v1.1.0')
        with self.assertRaisesRegex(ToolError, 'without a version bump'):
            build(self.root, self.root / 'dist', preview=False, tag='v1.1.0')

    def test_unchanged_skill_can_keep_version(self):
        self.prepare_release()
        self.simulated_release_bump('.', '1.1.0')
        self.commit('feat(tooling): improve catalog fixture')
        self.git('tag', 'v1.1.0')
        self.assertEqual(build(self.root, self.root / 'dist', preview=False, tag='v1.1.0')['skills'][0]['version'], '1.0.0')

    def test_publish_refuses_wrong_github_repository(self):
        self.prepare_release()
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'other/repo'}):
            with self.assertRaisesRegex(ToolError, 'differs from the GitHub Actions'):
                publish_assets(self.root, 'v1.0.0', self.root / 'dist')

    def test_corrupt_archive_rejected_before_remote_call(self):
        self.prepare_release()
        output = self.root / 'dist'
        build(self.root, output, preview=False, tag='v1.0.0')
        atomic_write(output / 'alpha-skill-1.0.0.tar.gz', b'corrupt')
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'fixture-owner/fixture-repo'}):
            with self.assertRaisesRegex(ToolError, 'corrupted'):
                publish_assets(self.root, 'v1.0.0', output)
