import json
import os
from pathlib import Path
import sys

from helpers import RepositoryCase
from scripts.common import DEFAULT_ROOT, ToolError, atomic_write, run
from scripts.planning import changed_files, check_pr, make_shards, plan, select_skills


class PlanningTests(RepositoryCase):
    def test_docs_only_does_not_run_all_smokes(self):
        self.assertEqual(select_skills(['alpha', 'beta'], ['README.md', 'docs/SETUP.md']), [])

    def test_shared_tooling_impacts_all(self):
        self.assertEqual(select_skills(['alpha', 'beta'], ['scripts/new.py']), ['alpha', 'beta'])

    def test_skill_test_and_catalog_map_to_owner(self):
        names = ['alpha', 'beta', 'gamma']
        self.assertEqual(select_skills(names, ['tests/skills/beta/evals.json']), ['beta'])
        self.assertEqual(select_skills(names, ['catalog/alpha.json']), ['alpha'])

    def test_missing_base_conservatively_selects_all(self):
        self.draft('alpha')
        self.draft('beta')
        self.assertEqual(plan(self.root)['selected'], ['alpha', 'beta'])

    def test_shards_bound_10000_skills_without_loss(self):
        names = [f'skill-{number:05}' for number in range(10000)]
        shards = make_shards(names, 16)
        self.assertEqual(len(shards), 16)
        self.assertEqual(sorted(name for shard in shards for name in shard['skills']), names)
        self.assertLessEqual(max(map(lambda s: len(s['skills']), shards)) - min(map(lambda s: len(s['skills']), shards)), 1)

    def test_empty_shards(self):
        self.assertEqual(make_shards([], 16), [])

    def test_shards_limit_validated(self):
        for limit in (0, 65):
            with self.assertRaises(ToolError):
                make_shards(['alpha'], limit)

    def test_real_git_diff_selects_affected_skill(self):
        self.draft('alpha')
        self.draft('beta')
        self.init_git()
        base = self.git('rev-parse', 'HEAD')
        atomic_write(self.root / 'skills/beta/assets/data.txt', 'fixture')
        head = self.commit('feat(beta): add fixture')
        self.assertEqual(changed_files(self.root, base, head), ['skills/beta/assets/data.txt'])
        self.assertEqual(plan(self.root, base, head)['selected'], ['beta'])

    def test_real_git_deleted_file_is_detected(self):
        self.draft('alpha')
        file = self.root / 'skills/alpha/assets/data.txt'
        atomic_write(file, 'fixture')
        self.init_git()
        base = self.git('rev-parse', 'HEAD')
        file.unlink()
        self.commit('fix(alpha): remove fixture')
        self.assertEqual(plan(self.root, base)['selected'], ['alpha'])

    def test_unknown_git_base_falls_back(self):
        self.init_git()
        self.assertIsNone(changed_files(self.root, 'missing-ref'))

    def test_valid_conventional_title(self):
        check_pr('feat(alpha): support fixture inputs', ['skills/alpha/SKILL.md'])
        check_pr('docs: explain operations', ['docs/SETUP.md'])
        check_pr('refactor(alpha)!: change output contract', ['skills/alpha/SKILL.md'])

    def test_behavior_changes_are_not_docs_only(self):
        with self.assertRaisesRegex(ToolError, 'shipped skill content'):
            check_pr('docs(alpha): alter mandatory behavior', ['skills/alpha/SKILL.md'])

    def test_invalid_title_rejected(self):
        for title in ('Update things', 'feat: a\nmalicious', 'feat: '):
            with self.assertRaises(ToolError):
                check_pr(title, [])

    def test_release_pr_exemption_is_explicit(self):
        check_pr('chore(main): release 1.0.0', ['skills/alpha/version.txt'], release_branch=True)
        with self.assertRaises(ToolError):
            check_pr('chore(main): release 1.0.0', ['skills/alpha/version.txt'])


class CliTests(RepositoryCase):
    def cli(self, *arguments):
        return run([sys.executable, '-m', 'scripts', '--root', str(self.root), *arguments], cwd=DEFAULT_ROOT, check=False)

    def test_new_validate_and_has_active(self):
        self.assertEqual(self.cli('new', 'from-cli').returncode, 0)
        result = self.cli('validate')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['valid'])
        self.assertFalse(json.loads(self.cli('has-active').stdout)['active'])

    def test_cli_duplicate_returns_nonzero(self):
        self.cli('new', 'from-cli')
        self.assertNotEqual(self.cli('new', 'from-cli').returncode, 0)

    def test_cli_activation_fails_for_shell(self):
        self.cli('new', 'from-cli')
        result = self.cli('activate', 'from-cli')
        self.assertEqual(result.returncode, 1)
        self.assertIn('ERROR:', result.stderr)

    def test_preview_cli_excludes_shell(self):
        self.cli('new', 'from-cli')
        result = self.cli('build', '--preview')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['skills'], [])

    def test_cli_unknown_skill_returns_error(self):
        result = self.cli('isolate', '--skills-json', '["unknown"]')
        self.assertEqual(result.returncode, 1)

    def test_help_available(self):
        self.assertEqual(self.cli('--help').returncode, 0)
