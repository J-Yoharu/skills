"""Executable public examples and diagnostics; not an LLM behavior evaluation."""
import copy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

SKILL = Path(__file__).resolve().parents[3] / 'skills' / 'orquestrar'
spec = importlib.util.spec_from_file_location('orq_r6_verify', SKILL / 'scripts/verify.py')
verify = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = verify
spec.loader.exec_module(verify)
rsp = importlib.util.spec_from_file_location('orq_r6_route', SKILL / 'scripts/route.py')
route = importlib.util.module_from_spec(rsp); rsp.loader.exec_module(route)


class ClarityTests(unittest.TestCase):
    def test_unknown_role_lists_real_roles_for_both_harnesses_without_aliasing(self):
        catalog = route.read(SKILL / 'assets/model-catalog.json')
        for harness in ('codex', 'claude-code'):
            with self.subTest(harness=harness):
                proc = subprocess.run([sys.executable, str(SKILL/'scripts/route.py'),
                    '--show-policy', '--harness', harness, '--role', 'reviewer'],
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stdout, '')
                self.assertIn('Unknown role', proc.stderr)
                self.assertIn('review', proc.stderr)
                expected = ', '.join(sorted(catalog['harnesses'][harness]['roles']))
                self.assertIn(f'Valid subagent roles: {expected}', proc.stderr)

    def test_diagnostic_uses_custom_catalog_and_excludes_coordinator_roles(self):
        catalog = route.read(SKILL / 'assets/model-catalog.json')
        original = copy.deepcopy(catalog)
        catalog['harnesses']['codex']['roles']['project-review'] = copy.deepcopy(catalog['harnesses']['codex']['roles']['review'])
        catalog['harnesses']['codex']['roles']['coordinator'] = {'choices': []}
        with self.assertRaises(route.RouteError) as caught:
            route.policy_view(catalog, 'codex', 'typo')
        suffix = str(caught.exception).split('Valid subagent roles: ', 1)[1]
        self.assertIn('project-review', suffix)
        self.assertNotIn('coordinator', suffix)
        self.assertEqual(route.policy_view(catalog, 'codex', 'project-review')['role'], 'project-review')
        self.assertEqual(catalog['harnesses']['codex']['roles']['review'], original['harnesses']['codex']['roles']['review'])

    def test_inline_checkpoint_and_observation_follow_existing_contract(self):
        core = next(p for p in (SKILL/'SKILL.md.template', SKILL/'SKILL.md') if p.is_file()).read_text()
        examples = [json.loads(block) for block in re.findall(r'```json\n(.*?)\n```', core, re.S)]
        doc = next(x for x in examples if x.get('schema_version') == 1)
        observation = next(x for x in examples if x.get('role') == 'review')
        doc['run_id'] = 'documentation-check'
        doc['objective'] = 'Check the published observation contract'
        doc['sources'] = [{'locator': 'PLAN.md', 'revision': 'git:example'}]
        doc['repositories'] = [{'id': 'app', 'path': str(SKILL), 'base_revision': 'example'}]
        doc['tasks'][0].update(status='reviewing', write_scope=['module.py'], acceptance=['Criterion'])
        observation.update(id='/native/reader-1', unit='T1', state='running', checkout=str(SKILL), input_revision='candidate:example')
        doc['active_agents'] = [observation]
        self.assertTrue(verify.validate_checkpoint(doc, writing=True)['valid'])
        # Terminal observations cannot remain in the active registry.
        observation['state'] = 'completed'
        with self.assertRaises(verify.VerificationError):
            verify.validate_checkpoint(doc, writing=True)
        doc['active_agents'] = []
        doc['agent_history'] = [{**observation, 'id': '/native/worker-1', 'role': 'implement'},
                                {**observation, 'result_ref': 'review.json'}]
        doc['tasks'][0].update(status='delivered', evidence_ref='evidence.json')
        doc['result'] = 'completed'
        self.assertTrue(verify.validate_checkpoint(doc, writing=True)['valid'])


if __name__ == '__main__':
    unittest.main()
