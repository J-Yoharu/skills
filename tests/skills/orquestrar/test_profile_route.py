"""Deterministic helper tests, not execution in an LLM harness."""
from __future__ import annotations
import copy
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
def module(name):
    spec = importlib.util.spec_from_file_location('orq_'+name, SKILL/'scripts'/f'{name}.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod
profile = module('profile'); route = module('route')


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        (self.root/'AGENTS.md').write_text('Use the documented workflow.\n')
        (self.root/'package.json').write_text('{"scripts":{"test":"existing-test"}}')
        self.draft = {'project_id': 'local-test',
                      'sections': {'workflow': {'summary': 'Documented'}, 'verification': {'command': 'existing-test'}},
                      'sources': ['AGENTS.md', 'package.json', 'CLAUDE.md']}
        self.path = self.root/'.orquestrar/profile.json'
    def tearDown(self): self.temp.cleanup()
    def cli(self, *args):
        return subprocess.run([sys.executable, str(SKILL/'scripts/profile.py'), *map(str, args)],
                              capture_output=True, text=True, timeout=20)
    def save(self):
        draft = self.root/'draft.json'; draft.write_text(json.dumps(self.draft))
        return self.cli('save', '--root', self.root, '--draft', draft, '--profile', self.path)
    def status(self):
        return json.loads(self.cli('check', '--root', self.root, '--profile', self.path).stdout)

    def test_missing_profile_asks_for_discovery_without_writing(self):
        self.assertEqual(self.status()['status'], 'missing')
        self.assertFalse(self.path.exists())

    def test_saved_profile_is_fresh_and_reused(self):
        self.assertEqual(self.save().returncode, 0)
        self.assertEqual(self.status()['status'], 'fresh')
        self.assertEqual(json.loads(self.path.read_text())['sections'], self.draft['sections'])

    def test_changed_added_or_removed_source_is_reported(self):
        self.save()
        (self.root/'AGENTS.md').write_text('New rule.\n')
        (self.root/'CLAUDE.md').write_text('Now present.\n')
        (self.root/'package.json').unlink()
        self.assertEqual(self.status()['changed_sources'], ['AGENTS.md', 'CLAUDE.md', 'package.json'])

    def test_unrelated_product_edit_keeps_profile_fresh(self):
        self.save(); (self.root/'app.py').write_text('print(1)\n')
        self.assertEqual(self.status()['status'], 'fresh')

    def test_human_edit_to_sections_is_kept_and_not_flagged(self):
        self.save()
        data = json.loads(self.path.read_text()); data['sections']['team'] = {'note': 'human'}
        self.path.write_text(json.dumps(data))
        self.assertEqual(self.status()['status'], 'fresh')

    def test_sources_outside_project_are_rejected(self):
        for bad in ('../outside.md', '/etc/hosts'):
            with self.subTest(bad=bad):
                self.draft['sources'] = [bad]
                result = self.save()
                self.assertEqual(result.returncode, 2)
                self.assertFalse(self.path.exists())

    def test_empty_sections_rejected(self):
        self.draft['sections'] = {}
        self.assertEqual(self.save().returncode, 2)

    def test_model_policy_in_profile_feeds_route_overrides(self):
        self.draft['sections']['models'] = {'role_overrides': {'codex': {'review': {'choices': [{'family': 'sol', 'effort': 'medium'}]}}}}
        self.save()
        out = subprocess.run([sys.executable, str(SKILL/'scripts/route.py'), '--show-policy', '--harness', 'codex',
                              '--role', 'review', '--overrides', str(self.path)], capture_output=True, text=True)
        self.assertEqual(json.loads(out.stdout)['policy']['choices'], [{'family': 'sol', 'effort': 'medium'}])


class RoutingPolicyTests(unittest.TestCase):
    def setUp(self):
        self.cat=json.loads((SKILL/'assets/model-catalog.json').read_text())
    def view(self,role,harness='codex',**kwargs):
        return route.policy_view(self.cat,harness,role,**kwargs)
    def test_codex_implementation_defaults_sol_medium(self):
        view=self.view('implement')
        self.assertEqual(view['policy']['choices'][0],{'family':'sol','effort':'medium'})
        self.assertEqual((view['model_field'],view['effort_field']),('model','model_reasoning_effort'))
    def test_claude_uses_different_native_effort_field(self):
        self.assertEqual(self.view('implement','claude-code')['effort_field'],'effort')
    def test_haiku_does_not_receive_invented_effort(self):
        self.assertEqual(self.view('lookup','claude-code')['policy']['choices'][0],{'family':'haiku','effort':None})
    def test_review_is_not_downgraded_to_mechanical(self):
        self.assertEqual(self.view('review')['policy']['choices'][0],{'family':'sol','effort':'high'})
    def test_frontier_requires_explicit_opt_in(self):
        self.assertTrue(self.view('frontier')['policy']['opt_in'])
    def test_frontier_cannot_be_enabled_just_by_removing_opt_in_flag(self):
        over={'role_overrides':{'codex':{'frontier':{'opt_in':False}}}}
        self.assertTrue(self.view('frontier',overrides=over)['policy']['opt_in'])
    def test_frontier_family_in_other_role_still_requires_opt_in(self):
        for harness,family in [('codex','astra'),('claude-code','fable')]:
            with self.subTest(harness=harness):
                over={'role_overrides':{harness:{'critical':{'choices':[{'family':family,'effort':'high'}]}}}}
                self.assertTrue(self.view('critical',harness,overrides=over)['policy']['opt_in'])
        self.assertFalse(self.view('critical')['policy']['opt_in'])
    def test_policy_is_not_availability_or_execution(self):
        view=self.view('implement')
        self.assertEqual(view['availability'],'unverified'); self.assertIsNone(view['effective'])
    def test_project_override_is_applied_without_rewriting_catalog(self):
        before=copy.deepcopy(self.cat)
        over={'role_overrides':{'codex':{'implement':{'choices':[{'family':'sol','effort':'high'}]}}}}
        self.assertEqual(self.view('implement',overrides=over)['policy']['choices'][0]['effort'],'high')
        self.assertEqual(self.cat,before)
    def test_resolver_mode_was_removed(self):
        p=subprocess.run([sys.executable,str(SKILL/'scripts/route.py'),'--harness','codex','--runtime','x.json','--session-id','s','--role','review'],
                         capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,2); self.assertIn('unrecognized arguments',p.stderr)
        self.assertFalse(hasattr(route,'resolve'))
        self.assertFalse((SKILL/'assets/runtime.example.json').exists())


class PackageV21Tests(unittest.TestCase):
    def test_all_runtime_docs_are_source_provider_neutral(self):
        for path in SKILL.rglob('*.md'):
            text=path.read_text().lower()
            for token in ['clickup','github projects','adapters/sources/']:
                self.assertNotIn(token,text,str(path))
    def test_source_adapters_removed(self):
        self.assertFalse((SKILL/'adapters/sources').exists())
    def test_codex_implicit_activation_enabled(self):
        self.assertIn('allow_implicit_invocation: true',(SKILL/'agents/openai.yaml').read_text())
    def test_eval_count_and_not_run_status(self):
        data=json.loads((EVALS / "scenarios.json").read_text())
        ids = [e['id'] for e in data['scenarios']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue({f'E{i:02}' for i in range(1, 53)}.issubset(ids))
        self.assertTrue(all(e['execution_status']=='not_run' for e in data['scenarios']))
    def test_unused_install_examples_are_not_shipped(self):
        removed=('assets/native','project.example.json','runtime.example.json','--runtime','--allow-frontier')
        for name in removed[:3]:
            self.assertFalse((SKILL/'assets'/name.removeprefix('assets/')).exists(),name)
        for path in SKILL.rglob('*'):
            if path.suffix in {'.md','.json','.py','.template'}:
                for token in removed:
                    self.assertNotIn(token,path.read_text(),str(path))


if __name__ == '__main__': unittest.main()
