"""Deterministic helper tests, not execution in an LLM harness."""
from __future__ import annotations
import copy
from datetime import datetime, timezone, timedelta
import importlib.util
import json
from pathlib import Path
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
NOW = datetime(2026, 9, 21, 12, tzinfo=timezone.utc)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        (self.root/'AGENTS.md').write_text('Use the documented workflow.\n')
        (self.root/'package.json').write_text('{"scripts":{"test":"existing-test"}}')
        (self.root/'rules').mkdir(); (self.root/'rules/one.md').write_text('Rule one')
        self.draft = {'schema_version':2, 'project_id':'local-test',
                      'sections': {'workflow':{'summary':'Documented'}, 'verification':{'command':'existing-test'}},
                      'anchors':{'rules':{'sections':['workflow'],'paths':['AGENTS.md','CLAUDE.md'],'globs':['rules/*.md']},
                                 'tests':{'sections':['verification'],'paths':['package.json'],'globs':[]}}}
        self.cache = profile.build(self.root, self.draft, now=NOW)
    def tearDown(self): self.temp.cleanup()
    def check(self, cache=None, now=NOW): return profile.check(self.root, cache or self.cache, now)

    def test_unchanged_local_anchors_match(self):
        self.assertEqual(self.check()['status'],'local_anchors_match')
    def test_anchor_edit_invalidates_only_workflow(self):
        (self.root/'AGENTS.md').write_text('New workflow')
        self.assertEqual(self.check()['invalid_sections'],['workflow'])
    def test_new_rule_is_detected(self):
        (self.root/'rules/two.md').write_text('new')
        self.assertEqual(self.check()['invalid_sections'],['workflow'])
    def test_removed_rule_is_detected(self):
        (self.root/'rules/one.md').unlink()
        self.assertEqual(self.check()['invalid_sections'],['workflow'])
    def test_previously_missing_instruction_is_detected(self):
        (self.root/'CLAUDE.md').write_text('New instruction')
        self.assertEqual(self.check()['invalid_sections'],['workflow'])
    def test_unrelated_product_edit_does_not_invalidate_workflow(self):
        (self.root/'app.py').write_text('new implementation')
        self.assertEqual(self.check()['invalid_sections'],[])
    def test_ttl_requires_revalidation_not_automatic_renewal(self):
        result = self.check(now=NOW+timedelta(days=8))
        self.assertEqual(result['invalid_sections'],['verification','workflow'])
        self.assertEqual(self.cache['_validated_at']['workflow'],NOW.isoformat())
    def test_manual_edits_are_not_overwritten(self):
        bad=copy.deepcopy(self.cache); bad['sections']['workflow']['summary']='human edit'
        self.assertEqual(self.check(bad)['status'],'manual_edit_or_corrupt')
        with self.assertRaises(profile.ProfileError): profile.build(self.root,self.draft,bad,now=NOW)
    def test_no_anchor_is_never_claimed_automatically_valid(self):
        self.draft['sections']['sources']={'locator':'opaque-resource'}
        cache=profile.build(self.root,self.draft,now=NOW)
        self.assertIn('sources',self.check(cache)['invalid_sections'])
    def test_external_status_is_explicitly_not_checked(self):
        self.assertIn('Not checked',self.check()['external_sources'])
    def test_selective_refresh_preserves_other_section_timestamp(self):
        (self.root/'AGENTS.md').write_text('new')
        newer=profile.build(self.root,self.draft,self.cache,['workflow'],NOW+timedelta(days=1))
        self.assertNotEqual(newer['_validated_at']['workflow'],self.cache['_validated_at']['workflow'])
        self.assertEqual(newer['_validated_at']['verification'],self.cache['_validated_at']['verification'])
    def test_selective_refresh_rejects_unselected_value_change(self):
        self.draft['sections']['verification']['command']='other'
        with self.assertRaises(profile.ProfileError): profile.build(self.root,self.draft,self.cache,['workflow'],NOW)
    def test_shared_changed_anchor_requires_all_sections(self):
        self.draft['anchors']['rules']['sections'].append('verification')
        with self.assertRaises(profile.ProfileError): profile.build(self.root,self.draft,self.cache,['workflow'],NOW)
    def test_first_save_requires_all_sections(self):
        with self.assertRaises(profile.ProfileError): profile.build(self.root,self.draft,None,['workflow'],NOW)
    def test_root_escape_is_rejected(self):
        self.draft['anchors']['rules']['paths']=['../outside']
        with self.assertRaises(profile.ProfileError): profile.build(self.root,self.draft,now=NOW)
    def test_absolute_path_is_rejected(self):
        self.draft['anchors']['rules']['paths']=['/tmp/example']
        with self.assertRaises(profile.ProfileError): profile.build(self.root,self.draft,now=NOW)
    def test_symlink_anchor_is_not_followed(self):
        (self.root/'AGENTS.md').unlink(); (self.root/'AGENTS.md').symlink_to(self.root/'package.json')
        self.assertIn('workflow',self.check()['invalid_sections'])
    def test_unknown_section_in_anchor_is_rejected(self):
        self.draft['anchors']['rules']['sections']=['missing']
        with self.assertRaises(profile.ProfileError): profile.build(self.root,self.draft,now=NOW)
    def test_nested_overrides_preserve_unrelated_fields(self):
        self.assertEqual(profile.merged({'a':{'b':1,'c':2}},{'a':{'b':3}}),{'a':{'b':3,'c':2}})
    def test_override_lists_replace_instead_of_append(self):
        self.assertEqual(profile.merged({'a':[1,2]},{'a':[]}),{'a':[]})
    def test_override_does_not_mutate_inputs(self):
        base={'a':{'b':1}}; profile.merged(base,{'a':{'b':2}})
        self.assertEqual(base,{'a':{'b':1}})
    def test_first_save_and_atomic_update_keep_backup(self):
        target=self.root/'.orquestrar/profile.json'; profile.save(target,self.cache,'missing')
        old=target.read_bytes(); updated=profile.build(self.root,self.draft,self.cache,now=NOW+timedelta(hours=1))
        profile.save(target,updated,profile.digest(old))
        self.assertEqual(target.with_name('profile.json.previous').read_bytes(),old)
        self.assertTrue(profile.intact(profile.load(target)))
    def test_compare_and_swap_rejects_stale_writer(self):
        target=self.root/'profile.json'; profile.save(target,self.cache,'missing')
        with self.assertRaises(profile.ProfileError): profile.save(target,self.cache,'missing')
    def test_metadata_lock_is_not_removed_by_other_writer(self):
        target=self.root/'profile.json'; lock=self.root/'profile.json.lock'; lock.write_text('owner')
        with self.assertRaises(profile.ProfileError): profile.save(target,self.cache,'missing')
        self.assertEqual(lock.read_text(),'owner')
    def test_existing_human_edited_profile_preserved_even_with_current_digest(self):
        target=self.root/'profile.json'; target.write_text('{"manual":"keep"}')
        old=target.read_bytes()
        with self.assertRaises(profile.ProfileError): profile.save(target,self.cache,profile.digest(old))
        self.assertEqual(target.read_bytes(),old)
    def test_no_timestamp_from_future_is_accepted(self):
        newer=profile.build(self.root,self.draft,now=NOW+timedelta(days=1))
        self.assertIn('workflow',self.check(newer)['invalid_sections'])

    def test_full_rediscovery_can_remove_obsolete_sections(self):
        self.draft['sections'].pop('verification')
        self.draft['anchors'].pop('tests')
        new = profile.build(self.root,self.draft,self.cache,now=NOW)
        self.assertNotIn('verification',new['_validated_at'])
        self.assertNotIn('tests',new['_baselines'])
    def test_inspection_check_does_not_create_state(self):
        before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob('*'))
        self.check()
        after = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob('*'))
        self.assertEqual(before,after)
    def test_profile_save_refuses_symlink_parent_before_mkdir(self):
        external=self.root/'external'; external.mkdir()
        alias=self.root/'alias'; alias.symlink_to(external,target_is_directory=True)
        with self.assertRaises(profile.ProfileError):
            profile.save(alias/'newdir'/'profile.json',self.cache,'missing')
        self.assertFalse((external/'newdir').exists())


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.cat=json.loads((SKILL/'assets/model-catalog.json').read_text())
        self.runtime={'schema_version':1,'session_id':'current','harness':'codex','observed_at':NOW.isoformat(),
                      'evidence':'runtime-schema-and-model-list','model_selection':True,'effort_selection':True,
                      'models':[{'id':id,'available':True,'supported_efforts':['low','medium','high','xhigh'],
                                 'evidence':'current-list'} for id in ['gpt-5.6-luna','gpt-5.6-terra','gpt-5.6-sol','gpt-6-astra']]}
    def resolve(self,role,**kwargs):
        return route.resolve(self.cat,self.runtime,'current',role,now=NOW,**kwargs)
    def claude(self):
        self.runtime['harness']='claude-code'
        self.runtime['models']=[{'id':id,'available':True,'supported_efforts':[] if id=='haiku' else ['low','medium','high','xhigh'],
                                 'evidence':'current-list'} for id in ['haiku','sonnet','opus','fable']]
    def test_codex_implementation_defaults_sol_medium(self):
        self.assertEqual(self.resolve('implement')['native_fields'],{'model':'gpt-5.6-sol','model_reasoning_effort':'medium'})
    def test_codex_explore_uses_terra(self):
        self.assertEqual(self.resolve('explore')['requested']['model'],'gpt-5.6-terra')
    def test_codex_review_uses_sol_high(self):
        self.assertEqual(self.resolve('review')['requested'],{'model':'gpt-5.6-sol','effort':'high'})
    def test_claude_implementation_uses_different_native_effort_field(self):
        self.claude(); self.assertEqual(self.resolve('implement')['native_fields'],{'model':'sonnet','effort':'high'})
    def test_haiku_does_not_receive_invented_effort(self):
        self.claude(); self.assertEqual(self.resolve('lookup')['native_fields'],{'model':'haiku'})
    def test_effort_unknown_does_not_resolve(self):
        self.runtime['models'][2]['supported_efforts']=None
        self.assertEqual(self.resolve('implement')['status'],'configuration_required')
    def test_effort_not_controllable_does_not_claim_applied(self):
        self.runtime['effort_selection']=False
        self.assertEqual(self.resolve('implement')['status'],'configuration_required')
    def test_missing_model_does_not_silently_downgrade_review(self):
        self.runtime['models'][2]['available']=False
        self.assertEqual(self.resolve('review')['status'],'configuration_required')
    def test_allowed_fallback_can_upgrade_lookup(self):
        self.runtime['models'][0]['available']=False
        self.assertEqual(self.resolve('lookup')['requested']['model'],'gpt-5.6-terra')
    def test_frontier_requires_explicit_opt_in(self):
        self.assertEqual(self.resolve('frontier')['status'],'authorization_required')
    def test_frontier_opt_in_still_requires_availability(self):
        self.runtime['models'][3]['available']=False
        self.assertEqual(self.resolve('frontier',allow_frontier=True)['status'],'configuration_required')
    def test_frontier_opt_in_uses_mapped_model(self):
        self.assertEqual(self.resolve('frontier',allow_frontier=True)['requested']['model'],'gpt-6-astra')
    def test_old_session_inventory_is_rejected(self):
        self.runtime['session_id']='previous'
        with self.assertRaises(route.RouteError): self.resolve('implement')
    def test_stale_runtime_is_rejected(self):
        self.runtime['observed_at']=(NOW-timedelta(days=2)).isoformat()
        with self.assertRaises(route.RouteError): self.resolve('implement')
    def test_no_selection_is_uncontrolled_not_claimed_optimized(self):
        self.runtime['model_selection']=False
        self.assertEqual(self.resolve('implement')['status'],'uncontrolled_inheritance')
    def test_resolved_is_not_effective_execution(self):
        self.assertEqual(self.resolve('implement')['effective'],{'model':None,'effort':None})
    def test_project_override_is_applied_without_rewriting_catalog(self):
        over={'role_overrides':{'codex':{'implement':{'choices':[{'family':'sol','effort':'high'}]}}}}
        self.assertEqual(self.resolve('implement',overrides=over)['requested']['effort'],'high')
        self.assertEqual(self.resolve('implement')['requested']['effort'],'medium')
    def test_gpt_alias_only_used_when_observed(self):
        self.runtime['models'][2]['id']='gpt-5.6'
        self.assertEqual(self.resolve('implement')['requested']['model'],'gpt-5.6')
    def test_frontier_cannot_be_enabled_just_by_removing_opt_in_flag(self):
        over={'role_overrides':{'codex':{'frontier':{'opt_in':False}}}}
        self.assertEqual(self.resolve('frontier',overrides=over)['status'],'authorization_required')
    def test_model_evidence_required(self):
        self.runtime['models'][2].pop('evidence')
        self.assertEqual(self.resolve('implement')['status'],'configuration_required')
    def test_deep_does_not_silently_clamp_to_high(self):
        self.runtime['models'][2]['supported_efforts']=['medium','high']
        self.assertEqual(self.resolve('deep')['status'],'configuration_required')
    def test_catalog_age_is_reported_not_silently_updated(self):
        self.cat['reviewed_on']='2026-01-01'
        self.assertTrue(self.resolve('implement')['policy_review_due'])
    def test_duplicate_runtime_models_are_rejected(self):
        self.runtime['models'].append(copy.deepcopy(self.runtime['models'][0]))
        with self.assertRaises(route.RouteError): self.resolve('implement')


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
    def test_native_presets_exist_for_each_harness(self):
        for harness,extension in [('claude-code','md'),('codex','toml')]:
            self.assertEqual(len(list((SKILL/'assets/native'/harness).glob('*.'+extension))),7)
    def test_claude_review_has_no_shell_or_write_tool(self):
        text=(SKILL/'assets/native/claude-code/orq-review.md').read_text()
        self.assertIn('tools: Read, Glob, Grep',text)
        self.assertNotIn('Bash',text)


if __name__ == '__main__': unittest.main()
