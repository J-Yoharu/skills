"""Native Make integration regressions. Fixtures are synthetic, never skill approvals."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from helpers import RepositoryCase
from scripts.bootstrap import bootstrap
from scripts.common import ToolError, atomic_write, load_json
from scripts.fingerprints import payload_fingerprint
from scripts.packaging import build, preview_skill
from scripts.planning import needs_maintenance_tests, plan
from scripts.testing import selective_check, skill_tests


class CandidatePreviewTests(RepositoryCase):
    def prepare(self):
        directory = self.draft()
        self.instructions()
        self.evals(approved=False)
        return directory

    def test_preview_materializes_entrypoint_without_activating_or_bumping(self):
        source = self.prepare()
        paths = [self.root / 'catalog/alpha-skill.json',
                 self.root / '.release-please-manifest.json',
                 self.root / 'tests/skills/alpha-skill/evals.json',
                 source / 'version.txt']
        before = [p.read_bytes() for p in paths]
        value = preview_skill(self.root, 'alpha-skill')
        target = Path(value['path'])
        self.assertTrue((target / 'SKILL.md').is_file())
        self.assertFalse((target / 'SKILL.md.template').exists())
        self.assertTrue((source / 'SKILL.md.template').is_file())
        self.assertFalse((source / 'SKILL.md').exists())
        self.assertEqual(before, [p.read_bytes() for p in paths])
        self.assertEqual(payload_fingerprint(source), payload_fingerprint(target))
        self.assertFalse(value['published'])
        self.assertEqual(value['status'], 'draft')
        self.assertEqual(value['version'], '0.0.0')
        self.assertFalse((target / 'tests').exists())

    def test_rebuilding_owned_preview_removes_stale_generated_files(self):
        self.prepare()
        value = preview_skill(self.root, 'alpha-skill')
        target = Path(value['path'])
        (target / 'local-stale.txt').write_text('Disposable generated copy.\n')
        preview_skill(self.root, 'alpha-skill')
        self.assertFalse((target / 'local-stale.txt').exists())

    def test_active_preview_does_not_require_a_template(self):
        source = self.active()
        value = preview_skill(self.root, 'alpha-skill')
        self.assertEqual(value['status'], 'active')
        self.assertEqual(payload_fingerprint(source), payload_fingerprint(Path(value['path'])))

    def test_dist_symlink_does_not_redirect_preview_writes(self):
        self.prepare()
        outside = self.root.parent / 'outside'
        outside.mkdir()
        (self.root / 'dist').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ToolError, 'symlink'):
            preview_skill(self.root, 'alpha-skill')
        self.assertEqual(list(outside.iterdir()), [])

    def test_unowned_dist_is_not_claimed(self):
        self.prepare()
        marker = self.root / 'dist/personal.txt'
        atomic_write(marker, 'User data')
        with self.assertRaisesRegex(ToolError, 'unowned dist'):
            preview_skill(self.root, 'alpha-skill')
        self.assertEqual(marker.read_text(), 'User data')

    def test_unowned_preview_is_not_deleted(self):
        self.prepare()
        atomic_write(self.root / 'dist/.build-output', 'Generated')
        marker = self.root / 'dist/skill-preview/alpha-skill/personal.txt'
        atomic_write(marker, 'User data')
        with self.assertRaisesRegex(ToolError, 'unowned preview'):
            preview_skill(self.root, 'alpha-skill')
        self.assertEqual(marker.read_text(), 'User data')

    def test_preview_then_catalog_build_is_supported_and_excludes_drafts(self):
        self.prepare()
        preview_skill(self.root, 'alpha-skill')
        value = build(self.root, self.root / 'dist', preview=True)
        self.assertEqual(value['skills'], [])
        self.assertTrue((self.root / 'skills/alpha-skill/SKILL.md.template').exists())

    def test_unknown_skill_has_no_output_side_effect(self):
        with self.assertRaises(ToolError):
            preview_skill(self.root, 'missing-skill')
        self.assertFalse((self.root / 'dist').exists())


class SkillRegressionRunnerTests(RepositoryCase):
    def fixture_test(self, name='alpha-skill', *, fail=False):
        self.draft(name)
        filename = self.root / 'tests/skills' / name / 'test_future_behavior.py'
        atomic_write(filename, 'import unittest\nclass FutureTest(unittest.TestCase):\n'
                     f'    def test_synthetic_behavior(self):\n        self.assertTrue({not fail!r})\n')
        return filename

    def test_future_skill_suite_is_discovered_and_executed(self):
        self.fixture_test()
        with redirect_stdout(io.StringIO()):
            result = skill_tests(self.root)
        self.assertEqual(result, [{'name': 'alpha-skill', 'test_modules': 1, 'status': 'passed'}])

    def test_empty_selection_does_not_fall_back_to_every_skill(self):
        self.fixture_test(fail=True)
        with patch('scripts.testing.run') as command:
            self.assertEqual(skill_tests(self.root, []), [])
            command.assert_not_called()

    def test_missing_suite_is_reported_not_claimed_as_a_test_pass(self):
        self.draft()
        self.assertEqual(skill_tests(self.root)[0]['status'], 'no_unit_suite')

    def test_unknown_skill_selection_is_rejected(self):
        with self.assertRaisesRegex(ToolError, 'Unknown skills'):
            skill_tests(self.root, ['does-not-exist'])

    def test_failing_real_unittest_subprocess_propagates_failure(self):
        self.fixture_test(fail=True)
        with self.assertRaises(ToolError):
            skill_tests(self.root)

    def test_symlinked_test_module_is_refused(self):
        filename = self.fixture_test()
        filename.rename(filename.with_suffix('.source'))
        filename.symlink_to(filename.with_suffix('.source'))
        with self.assertRaisesRegex(ToolError, 'symlinks'):
            skill_tests(self.root)

    def test_specific_skill_does_not_execute_another_failing_suite(self):
        self.fixture_test('alpha-skill')
        self.fixture_test('beta-skill', fail=True)
        with redirect_stdout(io.StringIO()):
            result = skill_tests(self.root, ['alpha-skill'])
        self.assertEqual([item['name'] for item in result], ['alpha-skill'])


class SelectiveNativeCITests(RepositoryCase):
    def test_docs_only_changes_skip_expensive_maintenance(self):
        self.assertFalse(needs_maintenance_tests(['README.md', 'docs/SETUP.md']))
        self.assertFalse(needs_maintenance_tests([]))

    def test_shared_engine_changes_select_maintenance(self):
        for path in ('Makefile', 'scripts/bootstrap.py', '.github/workflows/ci.yml',
                     'tests/launchers/make.test.mjs', 'AGENTS.md', 'repository.json'):
            with self.subTest(path=path):
                self.assertTrue(needs_maintenance_tests([path]))

    def test_unknown_history_is_conservative(self):
        self.draft()
        value = plan(self.root, None)
        self.assertTrue(value['maintenance'])
        self.assertTrue(value['all'])
        self.assertEqual(value['selected'], ['alpha-skill'])

    def test_real_git_docs_only_diff_selects_no_suites(self):
        self.draft()
        self.init_git()
        base = self.git('rev-parse', 'HEAD')
        atomic_write(self.root / 'docs/SETUP.md', '# Synthetic docs update\n')
        head = self.commit('docs: update setup')
        value = plan(self.root, base, head)
        self.assertFalse(value['maintenance'])
        self.assertFalse(value['has_skills'])
        self.assertEqual(value['selected'], [])

    def test_real_git_skill_diff_selects_only_affected_skill(self):
        self.draft()
        self.draft('beta-skill')
        self.init_git()
        base = self.git('rev-parse', 'HEAD')
        atomic_write(self.root / 'skills/beta-skill/assets/sample.txt', 'Example')
        head = self.commit('feat(beta-skill): add example')
        value = plan(self.root, base, head)
        self.assertFalse(value['maintenance'])
        self.assertEqual(value['selected'], ['beta-skill'])

    def test_selective_gate_still_validates_docs_with_empty_selection(self):
        self.draft()
        choice = {'maintenance': False, 'selected': [], 'all': False}
        with patch('scripts.planning.plan', return_value=choice), \
             patch('scripts.validation.validate_repository') as validate, \
             patch('scripts.testing.maintenance_tests') as maintenance, \
             patch('scripts.testing.skill_tests', return_value=[]) as suites, \
             patch('scripts.isolation.isolate_skill') as isolation:
            value = selective_check(self.root, 'base', 'head')
        validate.assert_called_once_with(self.root)
        maintenance.assert_not_called()
        suites.assert_called_once_with(self.root, [])
        isolation.assert_not_called()
        self.assertFalse(value['remote_writes'])
        self.assertEqual(value['behavioral_evaluation'], 'not executed')


class NativeBootstrapTests(RepositoryCase):
    def prepare(self):
        atomic_write(self.root / '.python-version', f'{sys.version_info.major}.{sys.version_info.minor}\n')
        filename = self.root / '.venv/bin/python'
        atomic_write(filename, 'Synthetic interpreter marker; subprocesses are mocked.\n')
        return filename

    def test_pinned_requirements_and_pip_check_share_one_native_flow(self):
        python = self.prepare()
        with patch('scripts.bootstrap.subprocess.run') as run, redirect_stdout(io.StringIO()):
            bootstrap(self.root)
        calls = [c.args[0] for c in run.call_args_list]
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[1], [str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', 'requirements-dev.txt'])
        self.assertEqual(calls[2], [str(python), '-m', 'pip', 'check'])
        self.assertFalse((self.root / '.bootstrap.lock').exists())

    def test_reference_bootstrap_uses_reference_requirements(self):
        self.prepare()
        with patch('scripts.bootstrap.subprocess.run') as run, redirect_stdout(io.StringIO()):
            bootstrap(self.root, reference=True)
        self.assertEqual(run.call_args_list[1].args[0][-1], 'requirements-reference.txt')

    def test_bootstrap_failure_propagates_and_cleans_own_lock(self):
        self.prepare()
        with patch('scripts.bootstrap.subprocess.run', side_effect=subprocess.CalledProcessError(1, ['pip'])):
            with self.assertRaises(subprocess.CalledProcessError):
                bootstrap(self.root)
        self.assertFalse((self.root / '.bootstrap.lock').exists())

    def test_existing_lock_is_not_removed(self):
        self.prepare()
        atomic_write(self.root / '.bootstrap.lock', 'Another invocation')
        with self.assertRaisesRegex(RuntimeError, 'Another bootstrap'):
            bootstrap(self.root)
        self.assertEqual((self.root / '.bootstrap.lock').read_text(), 'Another invocation')

    def test_wrong_python_fails_before_lock_or_install(self):
        self.prepare()
        atomic_write(self.root / '.python-version', '9.9\n')
        with patch('scripts.bootstrap.subprocess.run') as run:
            with self.assertRaisesRegex(RuntimeError, 'Use Python 9.9'):
                bootstrap(self.root)
            run.assert_not_called()
        self.assertFalse((self.root / '.bootstrap.lock').exists())
