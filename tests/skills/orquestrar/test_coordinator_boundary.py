"""Regression checks for the current-session coordinator, not LLM behavior tests."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

SKILL = Path(__file__).resolve().parents[3] / "skills" / "orquestrar"
EVALS = Path(__file__).resolve().parent
ENTRY = SKILL / ("SKILL.md" if (SKILL / "SKILL.md").exists() else "SKILL.md.template")
spec = importlib.util.spec_from_file_location('orq_route_boundary', SKILL / 'scripts/route.py')
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)


class CoordinatorBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((SKILL / 'assets/model-catalog.json').read_text())

    def view(self, role='implement', harness='codex', **kwargs):
        return route.policy_view(self.catalog, harness, role, **kwargs)

    def test_catalog_scoped_only_to_subagents_without_coordinator_roles(self):
        self.assertEqual(self.catalog['selection_scope'], 'subagents')
        for name, harness in self.catalog['harnesses'].items():
            with self.subTest(harness=name):
                self.assertFalse(set(harness['roles']) & route.COORDINATOR_ROLES)

    def test_skill_frontmatter_does_not_select_main_model_or_fork(self):
        frontmatter = ENTRY.read_text().split('---', 2)[1]
        for key in ('model:', 'effort:', 'model_reasoning_effort:', 'context:', 'agent:'):
            self.assertFalse(any(line.startswith(key) for line in frontmatter.splitlines()), key)

    def test_profile_example_does_not_require_model_inventory(self):
        data = json.loads((SKILL / 'assets/profile.example.json').read_text())
        self.assertNotIn('models', data['sections'])

    def test_reserved_roles_rejected_for_both_harnesses(self):
        for harness in ('codex', 'claude-code'):
            for role in route.COORDINATOR_ROLES | {' COORDINATE '}:
                with self.subTest(harness=harness, role=role):
                    with self.assertRaisesRegex(route.RouteError, 'current session'):
                        self.view(role, harness)

    def test_legacy_catalog_cannot_make_coordinator_selectable(self):
        for harness in self.catalog['harnesses'].values():
            harness['roles']['coordinate'] = copy.deepcopy(harness['roles']['implement'])
        with self.assertRaisesRegex(route.RouteError, 'current session'):
            self.view('coordinate')

    def test_override_cannot_make_coordinator_selectable(self):
        override = {'role_overrides': {'codex': {'coordinate': {
            'choices': [{'family': 'sol', 'effort': 'high'}],
        }}}}
        with self.assertRaisesRegex(route.RouteError, 'current session'):
            self.view('coordinate', overrides=override)

    def test_explicit_conflicting_scope_rejected_in_catalog_and_overrides(self):
        for source in ('catalog', 'overrides'):
            with self.subTest(source=source):
                cat = copy.deepcopy(self.catalog)
                override = {}
                {'catalog': cat, 'overrides': override}[source]['selection_scope'] = 'all'
                with self.assertRaisesRegex(route.RouteError, 'selection_scope must be subagents'):
                    route.policy_view(cat, 'codex', 'implement', override)

    def test_legacy_inputs_without_scope_still_show_only_subagent(self):
        self.catalog.pop('selection_scope')
        result = self.view()
        self.assertEqual(result['status'], 'policy_only')
        self.assertEqual(result['target'], 'subagent')

    def test_legacy_unused_coordinator_catalog_ignored_with_warning(self):
        roles = self.catalog['harnesses']['codex']['roles']
        roles['coordinate'] = copy.deepcopy(roles['implement'])
        result = self.view()
        self.assertEqual(result['warnings'], [{'reason': 'coordinator_roles_ignored', 'roles': ['coordinate']}])
        self.assertIn('coordinate', roles)  # Do not silently erase a user's catalog.

    def test_legacy_unused_coordinator_override_ignored_and_preserved(self):
        override = {'role_overrides': {'codex': {'coordinate': {'choices': [{'family': 'sol', 'effort': 'high'}]}}}}
        before = copy.deepcopy(override)
        result = self.view(overrides=override)
        self.assertEqual(result['policy']['choices'][0]['effort'], 'medium')
        self.assertEqual(result['warnings'][0]['reason'], 'coordinator_roles_ignored')
        self.assertEqual(override, before)

    def test_policy_view_does_not_mutate_catalog(self):
        before = copy.deepcopy(self.catalog)
        self.assertEqual(self.view('critical')['target'], 'subagent')
        self.assertEqual(self.catalog, before)

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SKILL / 'scripts/route.py'), '--show-policy', '--harness', 'codex', *args],
            capture_output=True, text=True, timeout=15,
        )

    def test_cli_rejects_coordinator_without_emitting_policy(self):
        result = self.cli('--role', 'coordinate')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertEqual(json.loads(result.stderr)['status'], 'error')
        self.assertIn('current session', json.loads(result.stderr)['error'])

    def test_cli_has_no_parent_target(self):
        result = self.cli('--role', 'implement', '--target', 'parent')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertIn('unrecognized arguments: --target', result.stderr)

    def test_cli_success_is_explicitly_subagent_not_parent(self):
        result = self.cli('--role', 'implement')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['target'], 'subagent')
        self.assertIsNone(data['effective'])

    def test_new_behavioral_boundary_scenarios_are_not_claimed_as_executed(self):
        data = json.loads((EVALS / "scenarios.json").read_text())
        scenarios = [item for item in data['scenarios'] if item['category'] == 'coordinator_boundary']
        self.assertEqual(len(scenarios), 4)
        self.assertTrue(all(item['execution_status'] == 'not_run' for item in scenarios))


if __name__ == '__main__':
    unittest.main()
