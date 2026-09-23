"""Review-driven regressions. Remote responses and review approvals are synthetic."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch

from helpers import RepositoryCase
from scripts.common import DEFAULT_ROOT, ToolError, atomic_write, load_json, load_yaml, run, write_json
from scripts.fingerprints import payload_fingerprint
from scripts.packaging import build, digest
from scripts.planning import compact_matrix, check_pr, select_skills, verify_metadata_only_diff
from scripts.publishing import publish_assets, remote_tag_commit
from scripts.repository import registry
from scripts.validation import _python_imports, validate_documentation, validate_repository


class ReviewRegressions(RepositoryCase):
    def test_branch_name_alone_cannot_authorize_skill_content(self):
        with self.assertRaisesRegex(ToolError, 'version-only'):
            check_pr('chore(main): release 1.0.0', ['skills/alpha-skill/SKILL.md'], release_branch=True)

    def test_release_exception_rejects_runtime_files(self):
        with self.assertRaisesRegex(ToolError, 'limited to version metadata'):
            check_pr('chore(main): release 1.0.0', ['skills/alpha-skill/scripts/do.py'], release_branch=True, metadata_only=True)

    def test_release_exception_rejects_unknown_diff(self):
        with self.assertRaises(ToolError):
            check_pr('chore(main): release 1.0.0', None, release_branch=True, metadata_only=True)

    def test_actual_git_diff_allows_only_version_metadata(self):
        self.active()
        self.init_git()
        base = self.git('rev-parse', 'HEAD')
        self.simulated_release_bump('alpha-skill', '0.1.0')
        head = self.commit('chore: release alpha-skill 0.1.0')
        paths = ['skills/alpha-skill/SKILL.md', 'skills/alpha-skill/version.txt', '.release-please-manifest.json']
        self.assertTrue(verify_metadata_only_diff(self.root, base, head, paths))
        check_pr('chore(main): release 0.1.0', paths, release_branch=True, metadata_only=True)

    def test_actual_git_behavior_change_is_not_metadata(self):
        directory = self.active()
        self.init_git()
        base = self.git('rev-parse', 'HEAD')
        path = directory / 'SKILL.md'
        atomic_write(path, path.read_text() + '\nPerform an additional operation.\n')
        head = self.commit('chore: pretend this is a release')
        self.assertFalse(verify_metadata_only_diff(self.root, base, head, ['skills/alpha-skill/SKILL.md']))

    def test_new_skill_file_cannot_use_version_only_exception(self):
        self.init_git()
        base = self.git('rev-parse', 'HEAD')
        self.active()
        head = self.commit('feat: introduce fixture')
        self.assertFalse(verify_metadata_only_diff(self.root, base, head, ['skills/alpha-skill/SKILL.md']))

    def test_active_review_rejects_changed_asset(self):
        directory = self.active()
        atomic_write(directory / 'assets/changed.txt', 'unreviewed content')
        with self.assertRaisesRegex(ToolError, 'reviewed payload has changed'):
            validate_repository(self.root)

    def test_active_review_rejects_missing_fingerprint(self):
        self.active()
        path = self.root / 'tests/skills/alpha-skill/evals.json'
        data = load_json(path)
        del data['review']['payload_sha256']
        write_json(path, data)
        with self.assertRaisesRegex(ToolError, 'fingerprint is missing'):
            validate_repository(self.root)

    def test_release_only_changes_keep_review_fingerprint(self):
        directory = self.active()
        before = payload_fingerprint(directory)
        self.simulated_release_bump('alpha-skill', '0.1.0')
        atomic_write(directory / 'CHANGELOG.md', '# Changelog\n\nAutomated release metadata.\n')
        self.assertEqual(before, payload_fingerprint(directory))
        validate_repository(self.root)

    def test_activation_keeps_review_fingerprint(self):
        from scripts.repository import activate_skill
        directory = self.ready()
        before = payload_fingerprint(directory)
        activate_skill(self.root, 'alpha-skill')
        self.assertEqual(before, payload_fingerprint(directory))

    def test_skill_license_change_requires_review(self):
        directory = self.active()
        atomic_write(directory / 'LICENSE', 'A different license requiring review.\n')
        with self.assertRaisesRegex(ToolError, 'reviewed payload has changed'):
            validate_repository(self.root)

    def test_root_readme_broken_link_fails(self):
        atomic_write(self.root / 'README.md', '# Readme\n\n[Missing](docs/not-here.md)\n')
        with self.assertRaisesRegex(ToolError, 'broken documentation link'):
            validate_repository(self.root)

    def test_root_readme_external_link_is_not_fetched(self):
        atomic_write(self.root / 'README.md', '# Readme\n\n[External](https://example.invalid/not-fetched)\n')
        validate_documentation(self.root)

    def test_documentation_escape_fails(self):
        atomic_write(self.root / 'docs/ESCAPE.md', '# Example\n\n[Escape](../../outside.txt)\n')
        with self.assertRaisesRegex(ToolError, 'escapes repository'):
            validate_documentation(self.root)

    def test_fenced_documentation_examples_are_not_file_links(self):
        atomic_write(self.root / 'README.md', '# Example\n\n```md\n[Example](not-a-real-file.md)\n```\n')
        validate_documentation(self.root)

    def test_nested_bundled_python_module_is_checked(self):
        directory = self.draft()
        atomic_write(directory / 'scripts/lib/__init__.py', '')
        with self.assertRaisesRegex(ToolError, 'lib.missing'):
            _python_imports(directory, directory / 'scripts/check.py', 'from lib.missing import VALUE\n')

    def test_nested_bundled_python_module_is_allowed(self):
        directory = self.draft()
        atomic_write(directory / 'scripts/lib/value.py', 'VALUE = 1\n')
        _python_imports(directory, directory / 'scripts/check.py', 'from lib.value import VALUE\n')

    def test_compact_matrix_does_not_embed_names(self):
        names = [f'skill-{number:06d}-' + 'x' * 40 for number in range(100000)]
        matrix = compact_matrix(names, 16)
        encoded = json.dumps(matrix).encode('utf-16-le')
        self.assertLess(len(encoded), 2000)
        self.assertEqual(len(matrix['include']), 16)
        recovered = [name for shard in matrix['include'] for name in names[shard['id']::shard['count']]]
        self.assertEqual(len(recovered), len(names))
        self.assertEqual(set(recovered), set(names))
        self.assertNotIn('skill-', encoded.decode('utf-16-le'))

    def test_empty_matrix_is_empty(self):
        self.assertEqual(compact_matrix([], 16), {'include': []})

    def test_launcher_tests_are_shared_changes(self):
        self.assertEqual(select_skills(['alpha', 'beta'], ['tests/launchers/run.test.mjs']), ['alpha', 'beta'])

    def test_new_skill_templates_are_english_and_keep_identity(self):
        directory = self.draft('orquestrar')
        content = (directory / 'SKILL.md.template').read_text()
        self.assertIn('name: orquestrar', content)
        self.assertIn('Reserved draft', content)
        self.assertIn('Do not', content)
        self.assertIn('Not released yet.', (directory / 'CHANGELOG.md').read_text())
        self.assertIn('evaluations', (self.root / 'tests/skills/orquestrar/README.md').read_text())
        self.assertEqual(load_json(self.root / 'tests/skills/orquestrar/evals.json')['review']['status'], 'pending')

    def test_dist_symlink_cannot_redirect_the_builder(self):
        outside = self.root.parent / 'external-output'
        outside.mkdir()
        (self.root / 'dist').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ToolError, 'dist directory must not be a symlink'):
            build(self.root, self.root / 'dist', preview=True)
        self.assertEqual(list(outside.iterdir()), [])

    def test_activation_fingerprint_sort_is_filename_independent(self):
        from scripts.repository import activate_skill
        directory = self.ready()
        atomic_write(directory / 'SKILL.md.notes', 'Bundled metadata example.\n')
        self.evals()
        before = payload_fingerprint(directory)
        activate_skill(self.root, 'alpha-skill')
        self.assertEqual(before, payload_fingerprint(directory))

    def test_root_package_and_empty_lock_agree(self):
        package = load_json(DEFAULT_ROOT / 'package.json')
        lock = load_yaml((DEFAULT_ROOT / 'pnpm-lock.yaml').read_text())
        self.assertEqual(package['packageManager'], 'pnpm@' + package['engines']['pnpm'])
        self.assertTrue(package['private'])
        self.assertEqual(lock['importers'], {'.': {}})
        self.assertFalse(package.get('dependencies'))
        self.assertFalse(package.get('devDependencies'))
        self.assertEqual(float(lock['lockfileVersion']), 9.0)

    def test_native_make_used_without_pnpm_in_all_operational_jobs(self):
        for path in (DEFAULT_ROOT / '.github/workflows').glob('*.yml'):
            for job in load_yaml(path.read_text())['jobs'].values():
                text = json.dumps(job['steps'])
                self.assertNotIn('pnpm/action-setup@', text)
                self.assertNotIn('make install', text)
                self.assertIn('make bootstrap', text)

    def test_single_gate_recomputes_selection_from_the_same_refs(self):
        workflow = load_yaml((DEFAULT_ROOT / '.github/workflows/ci.yml').read_text())
        job = workflow['jobs']['gate']
        self.assertEqual(len(workflow['jobs']), 1)
        self.assertTrue(any(s.get('run') == 'make ci-check' for s in job['steps']))
        self.assertIn('BASE_SHA', job['env'])
        self.assertIn('HEAD_SHA', job['env'])
        self.assertNotIn('matrix.skills', json.dumps(job))
        checkout = next(s for s in job['steps'] if s.get('uses', '').startswith('actions/checkout@'))
        self.assertEqual(checkout['with']['fetch-depth'], 0)
        makefile = (DEFAULT_ROOT / 'Makefile').read_text()
        self.assertIn('--shard-index "$$SHARD_INDEX" --shard-count "$$SHARD_COUNT"', makefile)


class ReleaseReviewRegressions(RepositoryCase):
    def prepare(self):
        from scripts.repository import configure
        # CI exports GITHUB_REPOSITORY; the fixture repository must not inherit it.
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop('GITHUB_REPOSITORY', None)
        self.active()
        configure(self.root, 'fixture-owner/fixture-repo')
        self.simulated_release_bump('alpha-skill', '1.0.0')
        self.simulated_release_bump('.', '1.0.0')
        self.init_git()
        self.git('tag', 'v1.0.0')
        return self.git('rev-parse', 'HEAD')

    def test_catalog_downgrade_is_rejected(self):
        self.prepare()
        self.simulated_release_bump('.', '0.9.0')
        self.commit('chore: invalid catalog downgrade')
        self.git('tag', 'v0.9.0')
        with self.assertRaisesRegex(ToolError, 'Catalog version must increase'):
            build(self.root, self.root / 'dist', preview=False, tag='v0.9.0')

    def test_component_downgrade_is_rejected(self):
        self.prepare()
        self.simulated_release_bump('alpha-skill', '0.9.0')
        self.simulated_release_bump('.', '1.1.0')
        self.commit('chore: invalid component downgrade')
        self.git('tag', 'v1.1.0')
        with self.assertRaisesRegex(ToolError, 'component version must not decrease'):
            build(self.root, self.root / 'dist', preview=False, tag='v1.1.0')

    def test_rewritten_checksum_cannot_authorize_changed_archive(self):
        self.prepare()
        output = self.root / 'dist'
        build(self.root, output, preview=False, tag='v1.0.0')
        archive = output / 'alpha-skill-1.0.0.tar.gz'
        archive.write_bytes(b'replaced artifact')
        index = load_json(output / 'index.json')
        index['skills'][0]['sha256'] = digest(archive.read_bytes())
        write_json(output / 'index.json', index)
        atomic_write(output / 'SHA256SUMS', '\n'.join(f'{digest(p.read_bytes())}  {p.name}' for p in [archive, output / 'index.json']) + '\n')
        with patch('scripts.publishing.run') as remote:
            with self.assertRaisesRegex(ToolError, 'differs from tagged source'):
                publish_assets(self.root, 'v1.0.0', output)
            remote.assert_not_called()

    def fake_remote(self, commit, output, *, conflict=None, remote_commit=None, remote_component=None):
        calls = []
        def fake(command, *, cwd, **options):
            if command[0] == 'git':
                return run(command, cwd=cwd, **options)
            calls.append(command)
            if command[:3] == ['gh', 'api', 'repos/fixture-owner/fixture-repo/git/ref/tags/v1.0.0']:
                return subprocess.CompletedProcess(command, 0, json.dumps({'object': {'type': 'commit', 'sha': remote_commit or commit}}), '')
            if command[:2] == ['gh', 'api'] and '/git/ref/tags/alpha-skill-v' in command[2]:
                if remote_component:
                    return subprocess.CompletedProcess(command, 0, json.dumps({'object': {'type': 'commit', 'sha': remote_component}}), '')
                return subprocess.CompletedProcess(command, 1, '', 'gh: Not Found (HTTP 404)')
            if command[:3] == ['gh', 'release', 'view']:
                assets = [{'name': conflict}] if conflict else []
                return subprocess.CompletedProcess(command, 0, json.dumps({'assets': assets}), '')
            if command[:3] == ['gh', 'release', 'download']:
                name = command[command.index('--pattern') + 1]
                directory = Path(command[command.index('--dir') + 1])
                (directory / name).write_bytes(b'remote-conflict')
            return subprocess.CompletedProcess(command, 0, '{}', '')
        return calls, fake

    def test_remote_asset_conflict_precedes_any_write(self):
        commit = self.prepare()
        output = self.root / 'dist'
        build(self.root, output, preview=False, tag='v1.0.0')
        calls, fake = self.fake_remote(commit, output, conflict='alpha-skill-1.0.0.tar.gz')
        with patch('scripts.publishing.run', side_effect=fake):
            with self.assertRaisesRegex(ToolError, 'Existing published asset differs'):
                publish_assets(self.root, 'v1.0.0', output)
        self.assertFalse(any('upload' in c or 'POST' in c for c in calls))

    def test_remote_catalog_mismatch_precedes_any_write(self):
        commit = self.prepare()
        output = self.root / 'dist'
        build(self.root, output, preview=False, tag='v1.0.0')
        calls, fake = self.fake_remote(commit, output, remote_commit='a' * 40)
        with patch('scripts.publishing.run', side_effect=fake):
            with self.assertRaisesRegex(ToolError, 'Remote catalog tag differs'):
                publish_assets(self.root, 'v1.0.0', output)
        self.assertFalse(any('upload' in c or 'POST' in c for c in calls))

    def test_missing_assets_and_component_tag_are_written_after_preflight(self):
        commit = self.prepare()
        output = self.root / 'dist'
        build(self.root, output, preview=False, tag='v1.0.0')
        calls, fake = self.fake_remote(commit, output)
        with patch('scripts.publishing.run', side_effect=fake):
            result = publish_assets(self.root, 'v1.0.0', output)
        self.assertEqual(len(result['uploaded']), 3)
        self.assertEqual(result['created_component_tags'], ['alpha-skill-v1.0.0'])
        writes = [i for i, c in enumerate(calls) if 'upload' in c or 'POST' in c]
        reads = [i for i, c in enumerate(calls) if 'upload' not in c and 'POST' not in c]
        self.assertGreater(min(writes), max(reads))
        self.assertFalse(any('--clobber' in c for c in calls))

    def test_existing_remote_component_does_not_get_recreated(self):
        commit = self.prepare()
        output = self.root / 'dist'
        build(self.root, output, preview=False, tag='v1.0.0')
        calls, fake = self.fake_remote(commit, output, remote_component=commit)
        with patch('scripts.publishing.run', side_effect=fake):
            result = publish_assets(self.root, 'v1.0.0', output)
        self.assertEqual(result['created_component_tags'], [])
        self.assertFalse(any('POST' in c for c in calls))

    def test_unknown_remote_component_history_fails_before_upload(self):
        commit = self.prepare()
        output = self.root / 'dist'
        build(self.root, output, preview=False, tag='v1.0.0')
        calls, fake = self.fake_remote(commit, output, remote_component='b' * 40)
        with patch('scripts.publishing.run', side_effect=fake):
            with self.assertRaisesRegex(ToolError, 'Fetch remote tags/history'):
                publish_assets(self.root, 'v1.0.0', output)
        self.assertFalse(any('upload' in c or 'POST' in c for c in calls))

    def test_remote_auth_error_is_not_treated_as_missing_tag(self):
        response = subprocess.CompletedProcess([], 1, '', 'gh: Bad credentials (HTTP 401)')
        with patch('scripts.publishing.run', return_value=response):
            with self.assertRaisesRegex(ToolError, 'Cannot read remote tag'):
                remote_tag_commit(self.root, 'owner/repo', 'v1.0.0', optional=True)

    def test_annotated_remote_tag_is_peeled(self):
        one = subprocess.CompletedProcess([], 0, json.dumps({'object': {'type': 'tag', 'sha': 'a' * 40}}), '')
        two = subprocess.CompletedProcess([], 0, json.dumps({'object': {'type': 'commit', 'sha': 'b' * 40}}), '')
        with patch('scripts.publishing.run', side_effect=[one, two]):
            self.assertEqual(remote_tag_commit(self.root, 'owner/repo', 'v1.0.0', optional=False), 'b' * 40)
