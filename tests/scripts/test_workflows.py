"""Workflow contract checks, not a substitute for GitHub execution/actionlint."""
import re
import unittest

from scripts.common import DEFAULT_ROOT, load_yaml


class WorkflowContracts(unittest.TestCase):
    def workflow(self, name):
        return load_yaml((DEFAULT_ROOT / '.github/workflows' / name).read_text())

    def test_all_actions_pinned_to_full_sha(self):
        count = 0
        for path in (DEFAULT_ROOT / '.github/workflows').glob('*.yml'):
            workflow = load_yaml(path.read_text())
            for job in workflow['jobs'].values():
                for step in job.get('steps', []):
                    if 'uses' in step:
                        count += 1
                        self.assertRegex(step['uses'], r'^[A-Za-z0-9_./-]+@[a-f0-9]{40}$')
        self.assertGreaterEqual(count, 10)

    def test_pr_workflow_is_read_only(self):
        workflow = self.workflow('ci.yml')
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        self.assertIn('pull_request', workflow['on'])
        self.assertNotIn('pull_request_target', workflow['on'])
        self.assertNotIn('secrets.', (DEFAULT_ROOT / '.github/workflows/ci.yml').read_text())

    def test_checkouts_do_not_persist_credentials(self):
        for path in (DEFAULT_ROOT / '.github/workflows').glob('*.yml'):
            for job in load_yaml(path.read_text())['jobs'].values():
                for step in job.get('steps', []):
                    if step.get('uses', '').startswith('actions/checkout@'):
                        self.assertIs(step['with']['persist-credentials'], False)

    def test_ci_has_one_stable_required_gate(self):
        workflow = self.workflow('ci.yml')
        self.assertEqual(set(workflow['jobs']), {'gate'})
        gate = workflow['jobs']['gate']
        self.assertEqual(gate['name'], 'gate')
        self.assertNotIn('if', gate)
        self.assertNotIn('paths-ignore', workflow['on']['pull_request'])
        self.assertNotIn('paths', workflow['on']['pull_request'])

    def test_release_is_manual_opt_in_and_main_only(self):
        workflow = self.workflow('release.yml')
        self.assertEqual(set(workflow['on']), {'workflow_dispatch'})
        self.assertEqual(set(workflow['jobs']), {'release'})
        condition = workflow['jobs']['release']['if']
        self.assertIn("vars.RELEASES_ENABLED == 'true'", condition)
        self.assertIn("github.ref == 'refs/heads/main'", condition)
        self.assertIn("steps.active.outputs.active == 'true'", str(workflow))

    def test_remote_publish_not_in_ci(self):
        ci = (DEFAULT_ROOT / '.github/workflows/ci.yml').read_text()
        self.assertNotIn('publish-assets', ci)
        self.assertNotIn('release-please-action', ci)

    def test_release_recovers_from_explicit_tag(self):
        workflow = self.workflow('release.yml')
        self.assertIn('release_tag', workflow['on']['workflow_dispatch']['inputs'])
        checkouts = [s for s in workflow['jobs']['release']['steps'] if s.get('uses', '').startswith('actions/checkout@')]
        self.assertTrue(any(s.get('with', {}).get('ref') == '${{ steps.selected.outputs.tag }}' for s in checkouts))

    def test_user_pr_title_not_interpolated_in_shell(self):
        for step in self.workflow('ci.yml')['jobs']['gate']['steps']:
            if 'run' in step:
                self.assertNotIn('${{ github.event.pull_request.title }}', step['run'])
                self.assertNotIn('${{ github.head_ref }}', step['run'])

    def test_optional_external_integrations_opt_in(self):
        job = self.workflow('interop.yml')['jobs']['official-tools']
        self.assertEqual(job['if'], "vars.INTEROP_ENABLED == 'true'")

    def test_native_token_is_explicit_with_optional_scoped_override(self):
        steps = self.workflow('release.yml')['jobs']['release']['steps']
        action = next(s for s in steps if s.get('uses', '').startswith('googleapis/release-please-action@'))
        self.assertEqual(action['with']['token'], '${{ secrets.RELEASE_PLEASE_TOKEN || github.token }}')

    def test_workflows_have_explicit_timeouts(self):
        for path in (DEFAULT_ROOT / '.github/workflows').glob('*.yml'):
            for job in load_yaml(path.read_text())['jobs'].values():
                self.assertGreater(job['timeout-minutes'], 0)

    def test_issue_forms_parse_and_have_required_information(self):
        for name in ('bug_report.yml', 'skill_request.yml'):
            value = load_yaml((DEFAULT_ROOT / '.github/ISSUE_TEMPLATE' / name).read_text())
            self.assertIn('name', value)
            self.assertIn('description', value)
            self.assertGreaterEqual(len(value['body']), 3)

    def test_routine_ci_has_no_pnpm_or_artifact_upload(self):
        text = (DEFAULT_ROOT / '.github/workflows/ci.yml').read_text()
        self.assertNotIn('pnpm/action-setup', text)
        self.assertNotIn('make install', text)
        self.assertNotIn('upload-artifact', text)
        self.assertIn('cache: pip', text)
        self.assertIn('make ci-check', text)
        self.assertIn("steps.plan.outputs.maintenance == 'true'", text)

    def test_manual_interoperability_has_no_schedule(self):
        self.assertEqual(set(self.workflow('interop.yml')['on']), {'workflow_dispatch'})

    def test_release_reuses_results_only_for_identical_commit(self):
        text = (DEFAULT_ROOT / '.github/workflows/release.yml').read_text()
        self.assertIn('git rev-parse HEAD', text)
        self.assertIn('CHECKED_SHA', text)
        self.assertIn('Released tag differs from the tested commit', text)
        self.assertIn('main advanced', text)
        self.assertEqual(text.count('make check\n'), 1)

    def test_dependabot_is_grouped_monthly(self):
        value = load_yaml((DEFAULT_ROOT / '.github/dependabot.yml').read_text())
        for item in value['updates']:
            self.assertEqual(item['schedule']['interval'], 'monthly')
            self.assertEqual(item['open-pull-requests-limit'], 1)
            self.assertTrue(item['groups'])
