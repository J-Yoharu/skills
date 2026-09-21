"""Regression checks for the current-session coordinator, not LLM behavior tests."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[3] / "skills" / "orquestrar"
EVALS = Path(__file__).resolve().parent
ENTRY = SKILL / ("SKILL.md" if (SKILL / "SKILL.md").exists() else "SKILL.md.template")
spec = importlib.util.spec_from_file_location('orq_route_boundary', SKILL / 'scripts/route.py')
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)
NOW = datetime(2026, 9, 21, 12, tzinfo=timezone.utc)


class CoordinatorBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((SKILL / 'assets/model-catalog.json').read_text())
        self.runtime = {
            'schema_version': 1,
            'session_id': 'current',
            'harness': 'codex',
            'observed_at': NOW.isoformat(),
            'evidence': 'synthetic-runtime-for-tests',
            'selection_scope': 'subagents',
            'model_selection': True,
            'effort_selection': True,
            'parent': {'model': 'user-selected-chat-model', 'effort': 'user-selected-chat-effort'},
            'models': [{
                'id': 'gpt-5.6-sol', 'available': True,
                'supported_efforts': ['medium', 'high', 'xhigh'],
                'evidence': 'synthetic-model-list-not-real-availability',
            }],
        }

    def resolve(self, role='implement', **kwargs):
        return route.resolve(self.catalog, self.runtime, 'current', role, now=NOW, **kwargs)

    def test_catalog_scoped_only_to_subagents_without_coordinator_roles(self):
        self.assertEqual(self.catalog['selection_scope'], 'subagents')
        for name, harness in self.catalog['harnesses'].items():
            with self.subTest(harness=name):
                self.assertFalse(set(harness['roles']) & route.COORDINATOR_ROLES)

    def test_no_native_coordinator_preset(self):
        for path in (SKILL / 'assets/native').rglob('*'):
            if path.is_file():
                self.assertNotIn(path.stem.removeprefix('orq-'), route.COORDINATOR_ROLES)

    def test_skill_frontmatter_does_not_select_main_model_or_fork(self):
        frontmatter = ENTRY.read_text().split('---', 2)[1]
        for key in ('model:', 'effort:', 'model_reasoning_effort:', 'context:', 'agent:'):
            self.assertFalse(any(line.startswith(key) for line in frontmatter.splitlines()), key)

    def test_profile_model_policy_is_subagent_only(self):
        data = json.loads((SKILL / 'assets/profile.example.json').read_text())
        self.assertEqual(data['sections']['models']['selection_scope'], 'subagents')
        self.assertNotIn('coordinate', data['sections']['models']['role_overrides'])

    def test_reserved_roles_rejected_for_both_harnesses(self):
        for harness in ('codex', 'claude-code'):
            self.runtime['harness'] = harness
            for role in route.COORDINATOR_ROLES | {' COORDINATE '}:
                with self.subTest(harness=harness, role=role):
                    with self.assertRaisesRegex(route.RouteError, 'current session'):
                        self.resolve(role)

    def test_legacy_catalog_cannot_make_coordinator_selectable(self):
        for harness in self.catalog['harnesses'].values():
            harness['roles']['coordinate'] = copy.deepcopy(harness['roles']['implement'])
        with self.assertRaisesRegex(route.RouteError, 'not routed'):
            self.resolve('coordinate')

    def test_override_cannot_make_coordinator_selectable(self):
        override = {'role_overrides': {'codex': {'coordinate': {
            'choices': [{'family': 'sol', 'effort': 'high'}],
        }}}}
        with self.assertRaisesRegex(route.RouteError, 'not routed'):
            self.resolve('coordinate', overrides=override)

    def test_other_execution_targets_rejected_even_with_implement_role(self):
        for target in ('parent', 'current_session', 'main', 'coordinator', None):
            with self.subTest(target=target):
                with self.assertRaisesRegex(route.RouteError, 'Only subagent'):
                    self.resolve(target=target)

    def test_explicit_conflicting_scope_rejected_in_catalog_runtime_overrides(self):
        for source in ('catalog', 'runtime', 'overrides'):
            with self.subTest(source=source):
                cat = copy.deepcopy(self.catalog)
                runtime = copy.deepcopy(self.runtime)
                override = {}
                {'catalog': cat, 'runtime': runtime, 'overrides': override}[source]['selection_scope'] = 'all'
                with self.assertRaisesRegex(route.RouteError, 'selection_scope must be subagents'):
                    route.resolve(cat, runtime, 'current', 'implement', overrides=override, now=NOW)

    def test_legacy_inputs_without_scope_still_route_only_subagent(self):
        self.catalog.pop('selection_scope')
        self.runtime.pop('selection_scope')
        result = self.resolve()
        self.assertEqual(result['status'], 'resolved')
        self.assertEqual(result['target'], 'subagent')

    def test_legacy_unused_coordinator_catalog_ignored_with_warning(self):
        roles = self.catalog['harnesses']['codex']['roles']
        roles['coordinate'] = copy.deepcopy(roles['implement'])
        result = self.resolve()
        self.assertEqual(result['status'], 'resolved')
        self.assertEqual(result['warnings'], [{'reason': 'coordinator_roles_ignored', 'roles': ['coordinate']}])
        self.assertIn('coordinate', roles)  # Do not silently erase a user's catalog.

    def test_legacy_unused_coordinator_override_ignored_and_preserved(self):
        override = {'role_overrides': {'codex': {'coordinate': {'choices': [{'family': 'sol', 'effort': 'high'}]}}}}
        before = copy.deepcopy(override)
        result = self.resolve(overrides=override)
        self.assertEqual(result['requested']['effort'], 'medium')
        self.assertEqual(result['warnings'][0]['reason'], 'coordinator_roles_ignored')
        self.assertEqual(override, before)

    def test_subagent_selection_does_not_mutate_parent_or_inputs(self):
        cat_before, runtime_before = copy.deepcopy(self.catalog), copy.deepcopy(self.runtime)
        result = self.resolve('critical')
        self.assertEqual(result['requested'], {'model': 'gpt-5.6-sol', 'effort': 'high'})
        self.assertEqual(self.runtime, runtime_before)
        self.assertEqual(self.catalog, cat_before)
        self.assertEqual(result['target'], 'subagent')

    def test_unknown_parent_identity_is_not_fabricated(self):
        self.runtime['parent'] = {'model': None, 'effort': None}
        self.assertEqual(self.resolve()['status'], 'resolved')
        self.assertEqual(self.runtime['parent'], {'model': None, 'effort': None})

    def test_inheritance_does_not_issue_native_fields_or_parent_reconfiguration(self):
        self.runtime['model_selection'] = False
        before = copy.deepcopy(self.runtime)
        result = self.resolve()
        self.assertEqual(result['status'], 'uncontrolled_inheritance')
        self.assertEqual(result['target'], 'subagent')
        self.assertNotIn('native_fields', result)
        self.assertEqual(self.runtime, before)

    def test_all_nonerror_results_explicitly_target_subagent(self):
        self.assertEqual(self.resolve()['target'], 'subagent')
        self.assertEqual(self.resolve('frontier')['target'], 'subagent')
        self.runtime['models'] = []
        self.assertEqual(self.resolve()['target'], 'subagent')
        self.runtime['model_selection'] = False
        self.assertEqual(self.resolve()['target'], 'subagent')

    def cli(self, *args):
        with tempfile.TemporaryDirectory() as temp:
            runtime = copy.deepcopy(self.runtime)
            runtime['observed_at'] = datetime.now(timezone.utc).isoformat()
            path = Path(temp) / 'runtime.json'
            path.write_text(json.dumps(runtime))
            return subprocess.run(
                [sys.executable, str(SKILL / 'scripts/route.py'), '--runtime', str(path),
                 '--session-id', 'current', *args],
                capture_output=True, text=True, timeout=15,
            )

    def test_cli_rejects_coordinator_without_emitting_native_fields(self):
        result = self.cli('--role', 'coordinate')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertEqual(json.loads(result.stderr)['status'], 'error')
        self.assertIn('current session', json.loads(result.stderr)['error'])

    def test_cli_rejects_parent_target(self):
        result = self.cli('--role', 'implement', '--target', 'parent')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')

    def test_cli_success_is_explicitly_subagent_not_parent(self):
        result = self.cli('--role', 'implement', '--target', 'subagent')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['target'], 'subagent')
        self.assertEqual(data['effective'], {'model': None, 'effort': None})

    def test_new_behavioral_boundary_scenarios_are_not_claimed_as_executed(self):
        data = json.loads((EVALS / "scenarios.json").read_text())
        scenarios = [item for item in data['scenarios'] if item['category'] == 'coordinator_boundary']
        self.assertEqual(len(scenarios), 4)
        self.assertTrue(all(item['execution_status'] == 'not_run' for item in scenarios))


if __name__ == '__main__':
    unittest.main()
