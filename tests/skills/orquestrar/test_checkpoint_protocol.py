"""Real filesystem/CLI protocol regressions. Not LLM behavioral approval."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[3] / "skills" / "orquestrar"
ENTRY = SKILL / "scripts/verify.py"
spec = importlib.util.spec_from_file_location("orq_checkpoint_tests", ENTRY)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def initial():
    return {"schema_version": 1, "run_id": "checkout-feature", "objective": "Deliver a validated feature.",
            "result": "open", "control": {"state": "running", "drain_units": []},
            "sources": [{"locator": "docs/plan.md", "revision": "observed-plan-sha"}],
            "repositories": [{"id": "api", "path": "/project/api", "base_revision": "observed-head"}],
            "permissions": {"delivery": "local", "publish": False},
            "active_agents": [], "active_processes": [],
            "tasks": [{"id": "A", "repo": "api", "status": "running", "depends_on": [],
                       "write_scope": ["src/feature.py"], "acceptance": ["Approved behavior is verified."]}],
            "next_action": "Implement A."}


class CheckpointProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.file = self.root / "state/run.json"; self.draft = self.root / "draft.json"
        self.doc = initial()
    def tearDown(self): self.tmp.cleanup()
    def save(self, doc=None, expected="missing", **kwargs):
        self.draft.write_text(json.dumps(doc or self.doc))
        return v.checkpoint_save(self.file, self.draft, expected, **kwargs)
    def cli(self, *args):
        return subprocess.run([sys.executable, str(ENTRY), *map(str, args)],
                              text=True, capture_output=True, timeout=10)
    def finish(self, doc=None):
        d = copy.deepcopy(doc or self.doc); d['result'] = 'completed'
        for t in d['tasks']:
            t.update(status='delivered', evidence_ref='evidence/candidate.json')
        d['agent_history'] = [{'id': f"{role}-{t['id']}", 'role': role, 'unit': t['id'], 'state': 'completed'}
                              for t in d['tasks'] for role in ('implement', 'review')]
        d['next_action'] = 'No further authorized work.'
        return d

    def test_save_and_read_validate_full_content_return_brief_facts(self):
        result = self.save()
        self.assertEqual(json.loads(self.file.read_text()), self.doc)
        self.assertEqual(result['state_token'], hashlib.sha256(self.file.read_bytes()).hexdigest())
        self.assertEqual(result['comparison'], 'succeeded'); self.assertNotIn('sources', result)
        self.assertEqual(v.checkpoint_read(self.file, 'A')['unit'], self.doc['tasks'][0])
        self.assertEqual(list(self.file.parent.iterdir()), [self.file])

    def test_invalid_or_missing_draft_cannot_destroy_valid_checkpoint_or_print_success(self):
        old = self.save(); old_bytes = self.file.read_bytes()
        for content in ('{', '{"schema_version":1,"schema_version":2}', 'NaN', None):
            with self.subTest(content=content):
                if content is None: self.draft.unlink(missing_ok=True)
                else: self.draft.write_text(content)
                result = self.cli('checkpoint-save', '--file', self.file, '--draft', self.draft,
                                  '--expected', old['state_token'])
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertNotIn('succeeded', result.stdout)
                self.assertEqual(self.file.read_bytes(), old_bytes)

    def test_same_draft_target_and_stale_tokens_are_rejected(self):
        result = self.save(); original = self.file.read_bytes()
        with self.assertRaises(v.VerificationError):
            v.checkpoint_save(self.file, self.file, result['state_token'])
        with self.assertRaises(v.VerificationError): self.save(expected='0'*64)
        with self.assertRaises(v.VerificationError): self.save(expected='missing')
        self.assertEqual(self.file.read_bytes(), original)

    def test_no_implicit_adoption_or_repair_of_invalid_legacy_record(self):
        self.file.parent.mkdir(); self.file.write_text('{"old":"unmanaged"}')
        original = self.file.read_bytes()
        with self.assertRaises(v.VerificationError):
            self.save(expected=hashlib.sha256(original).hexdigest())
        self.assertEqual(self.file.read_bytes(), original)

    def test_replace_failure_preserves_previous_and_cleans_only_owned_temporary(self):
        saved = self.save(); original = self.file.read_bytes()
        sentinel = self.file.parent / '.unrelated.tmp'; sentinel.write_text('keep')
        with patch.object(v.os, 'replace', side_effect=PermissionError('denied')):
            with self.assertRaises(PermissionError): self.save(self.finish(), saved['state_token'])
        self.assertEqual(self.file.read_bytes(), original)
        self.assertEqual(sentinel.read_text(), 'keep')
        self.assertEqual({p.name for p in self.file.parent.iterdir()}, {'run.json', '.unrelated.tmp'})

    def test_flush_failure_before_replacement_preserves_previous_bytes(self):
        saved=self.save(); old=self.file.read_bytes()
        with patch.object(v.os,'fsync',side_effect=OSError('flush failed')):
            with self.assertRaises(OSError): self.save(self.finish(),saved['state_token'])
        self.assertEqual(self.file.read_bytes(),old)
        self.assertEqual([p.name for p in self.file.parent.iterdir()],['run.json'])

    def test_error_after_replace_is_not_success_and_requires_reconciliation(self):
        saved = self.save()
        real_read = v.checkpoint_bytes; calls = 0
        def read(*a, **kw):
            nonlocal calls
            calls += 1
            if calls == 4: raise OSError('read-back unavailable')
            return real_read(*a, **kw)
        with patch.object(v, 'checkpoint_bytes', side_effect=read):
            with self.assertRaisesRegex(v.VerificationError, 'may have been replaced'):
                self.save(self.finish(), saved['state_token'])
        self.assertEqual(json.loads(self.file.read_text())['result'], 'completed')
        self.assertFalse(self.file.with_name('run.json.lock').exists())

    def test_foreign_lock_and_symlink_are_never_removed_or_followed(self):
        saved = self.save(); lock = self.file.with_name('run.json.lock'); lock.mkdir()
        with self.assertRaisesRegex(v.VerificationError, 'lock exists'):
            self.save(expected=saved['state_token'])
        self.assertTrue(lock.exists()); lock.rmdir()
        target = self.root / 'alias.json'; target.symlink_to(self.file)
        with self.assertRaises(v.VerificationError): v.checkpoint_read(target)
        self.assertEqual(v.checkpoint_read(self.file)['state_token'], saved['state_token'])

    def test_two_processes_cannot_overwrite_each_other_from_one_observed_revision(self):
        saved = self.save(); drafts = []
        for action in ('First candidate', 'Second candidate'):
            d = copy.deepcopy(self.doc); d['next_action'] = action
            path = self.root / f'candidate-{len(drafts)}.json'; path.write_text(json.dumps(d)); drafts.append(path)
        processes = [subprocess.Popen([sys.executable, str(ENTRY), 'checkpoint-save', '--file', str(self.file),
                        '--draft', str(p), '--expected', saved['state_token']], text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE) for p in drafts]
        outputs = [p.communicate(timeout=10) for p in processes]
        self.assertEqual(sorted(p.returncode for p in processes), [0, 2], outputs)
        self.assertIn(json.loads(self.file.read_text())['next_action'], {'First candidate', 'Second candidate'})

    def test_unknown_fields_tasks_and_history_objects_survive_updates(self):
        self.doc['extension'] = {'business_id': 'existing'}
        saved = self.save(); d = self.finish(); del d['extension']
        with self.assertRaisesRegex(v.VerificationError, 'Preserve existing fields'): self.save(d, saved['state_token'])
        d = self.finish(); self.save(d, saved['state_token'])
        self.assertEqual(json.loads(self.file.read_text())['extension'], {'business_id': 'existing'})

    def test_actual_failure_classes_are_rejected_without_alias_guessing(self):
        for changes in ('in_progress', 'review_pending', 'missing_repo', 'completed_control', 'finished_active'):
            with self.subTest(changes=changes):
                d = initial()
                if changes == 'missing_repo': del d['tasks'][0]['repo']
                elif changes == 'completed_control': d['control']['state'] = 'completed'
                elif changes == 'finished_active': d['active_agents'] = [{'id':'reviewer', 'state':'completed'}]
                else: d['tasks'][0]['status'] = changes
                with self.assertRaises(v.VerificationError): self.save(d)
                self.assertFalse(self.file.exists())

    def test_completed_result_requires_boundaries_quiescence_and_evidence(self):
        for field in ('verified_only', 'missing_evidence', 'active_process'):
            with self.subTest(field=field):
                d = self.finish()
                if field == 'verified_only': d['tasks'][0]['status'] = 'verified'
                if field == 'missing_evidence': del d['tasks'][0]['evidence_ref']
                if field == 'active_process': d['active_processes'] = [{'id': 'gate', 'state': 'unknown'}]
                with self.assertRaises(v.VerificationError): self.save(d)
        saved = self.save(self.finish())
        self.assertIsNone(saved['next_ready'])
        self.assertEqual(v.validate_plan(self.finish())['dispatch_ready'], [])

    def test_until_scope_can_finish_without_falsely_delivering_successors(self):
        d = self.finish(); d['selected_tasks'] = ['A']
        d['tasks'].append({'id':'B','repo':'api','status':'pending','depends_on':['A'], 'acceptance':['Next request']})
        self.save(d)
        self.assertEqual(v.validate_plan(d)['dispatch_ready'], [])
        self.assertEqual(json.loads(self.file.read_text())['tasks'][1]['status'], 'pending')
        d['selected_tasks'] = ['B']
        with self.assertRaises(v.VerificationError): v.validate_plan(d)

    def test_pause_freezes_scope_closes_review_and_requires_explicit_resume(self):
        self.doc['tasks'].append({'id':'B','repo':'api','status':'pending','depends_on':['A'], 'acceptance':['Next unit']})
        saved = self.save()
        draining = copy.deepcopy(self.doc)
        draining['control'] = {'state':'draining', 'drain_units':['A'], 'reason':'User pause',
                               'requested_at':'2026-09-22T12:00:00Z'}
        saved = self.save(draining, saved['state_token'])
        bad = copy.deepcopy(draining); bad['tasks'][1]['status']='delivered'
        with self.assertRaises(v.VerificationError): self.save(bad, saved['state_token'])
        bad = copy.deepcopy(draining); bad['control']['drain_units'].append('B')
        with self.assertRaises(v.VerificationError): self.save(bad, saved['state_token'])
        bad = copy.deepcopy(draining); bad['control']['state']='paused'
        with self.assertRaises(v.VerificationError): self.save(bad, saved['state_token'])
        closed = copy.deepcopy(draining); closed['control']['state']='paused'
        closed['tasks'][0].update(status='integrated', evidence_ref='evidence/A.json')
        closed['agent_history'] = [{'id':'implement-A','role':'implement','unit':'A','state':'completed'},
                                   {'id':'review-A','role':'review','unit':'A','state':'completed'}]
        saved = self.save(closed, saved['state_token'])
        resumed = copy.deepcopy(closed); resumed['control']['state']='running'
        with self.assertRaisesRegex(v.VerificationError, '--resume'): self.save(resumed, saved['state_token'])
        saved = self.save(resumed, saved['state_token'], resume=True)
        self.assertEqual(saved['next_ready'],'B')
        self.assertEqual(v.checkpoint_read(self.file,'A')['unit']['evidence_ref'], 'evidence/A.json')

    def test_interruption_preserves_incomplete_work_but_cannot_advance_while_stopped(self):
        d = initial(); d['control'] = {'state':'interrupted','drain_units':['A'], 'reason':'Context limit',
                                      'requested_at':'2026-09-22T12:00:00Z'}
        d['active_agents']=[{'id':'worker-A','state':'unknown'}]
        saved = self.save(d); changed = copy.deepcopy(d); changed['tasks'][0]['status']='implemented'
        with self.assertRaises(v.VerificationError): self.save(changed, saved['state_token'])
        self.assertEqual(v.validate_plan(d)['dispatch_ready'], [])

    def test_partial_failure_cannot_become_completed_and_dag_rejects_cycles(self):
        d = initial(); d['tasks'].append({'id':'B','repo':'api','status':'blocked','depends_on':['A'],'acceptance':['Integration']})
        d['tasks'][0]['status']='integrated'; d['result']='completed'
        with self.assertRaises(v.VerificationError): self.save(d)
        d['result']='open'; d['tasks'][0]['depends_on']=['B']
        with self.assertRaisesRegex(v.VerificationError, 'cycle'): self.save(d)

    def test_finished_agent_is_archived_not_discarded_or_left_active(self):
        self.doc['active_agents']=[{'id':'review-A', 'state':'running', 'role':'review'}]
        saved=self.save(); d=self.finish(); d['active_agents']=[]
        d['agent_history']=[{'id':'implement-A','role':'implement','unit':'A','state':'completed'},
                            {'id':'another-review','role':'review','unit':'A','state':'completed'}]
        with self.assertRaisesRegex(v.VerificationError, 'Preserve resolved'):
            self.save(d,saved['state_token'])
        d['agent_history']=[{'id':'implement-A','role':'implement','unit':'A','state':'completed'},
                            {'id':'review-A','role':'review','unit':'A','state':'completed','evidence_ref':'review/A.json'}]
        self.save(d,saved['state_token'])
        self.assertEqual(json.loads(self.file.read_text())['active_agents'],[])

    def test_selection_summarizes_large_dag_without_loading_completed_history(self):
        d = initial(); d['tasks']=[]
        for i in range(1000):
            d['tasks'].append({'id':f'T{i}','repo':'api','status':'integrated' if i < 999 else 'pending',
                              'depends_on':[f'T{i-1}'] if i else [], 'acceptance':['Scoped requirement']})
        d['agent_history'] = [{'id':f'{r}-T{i}','role':r,'unit':f'T{i}','state':'completed'}
                              for i in range(999) for r in ('implement', 'review')]
        result = self.save(d)
        self.assertEqual(result['next_ready'],'T999')
        self.assertLess(len(json.dumps(result)), 1000)
        self.assertEqual(v.checkpoint_read(self.file,'T999')['unit']['depends_on'], ['T998'])

    def test_behavioral_unit_cannot_close_without_review_unless_self_is_explicit(self):
        # Regression: pause/resume closed small behavioral units without any reviewer.
        saved = self.save()
        closed = copy.deepcopy(self.doc); closed['tasks'][0].update(status='integrated', evidence_ref='evidence/A.json')
        with self.assertRaisesRegex(v.VerificationError, 'needs a review entry'): self.save(closed, saved['state_token'])
        other = copy.deepcopy(closed); other['agent_history'] = [{'id':'review-B','role':'review','unit':'B','state':'completed'}]
        with self.assertRaisesRegex(v.VerificationError, 'needs a review entry'): self.save(other, saved['state_token'])
        typo = copy.deepcopy(closed); typo['tasks'][0]['review'] = 'skip'
        with self.assertRaisesRegex(v.VerificationError, 'independent or self'): self.save(typo, saved['state_token'])
        explicit = copy.deepcopy(closed); explicit['tasks'][0].update(review='self', implementer='coordinator')
        self.save(explicit, saved['state_token'])

    def test_dependent_unit_cannot_start_before_its_prerequisite_is_accepted(self):
        # Regression: a consumer started while its prerequisite was still in review.
        self.doc['tasks'].append({'id': 'B', 'repo': 'api', 'status': 'pending', 'depends_on': ['A'],
                                  'acceptance': ['Uses A']})
        saved = self.save()
        for status in ('reviewing', 'verified'):
            early = copy.deepcopy(self.doc); early['tasks'][0]['status'] = status
            early['tasks'][1]['status'] = 'running'
            with self.subTest(prerequisite=status), self.assertRaisesRegex(v.VerificationError, 'dependencies'):
                self.save(early, saved['state_token'])
        ready = copy.deepcopy(self.doc)
        ready['tasks'][0].update(status='integrated', evidence_ref='evidence/A.json')
        ready['tasks'][1]['status'] = 'running'
        ready['agent_history'] = [{'id': 'implement-A', 'role': 'implement', 'unit': 'A', 'state': 'completed'},
                                  {'id': 'review-A', 'role': 'review', 'unit': 'A', 'state': 'completed'}]
        self.save(ready, saved['state_token'])

    def test_re_review_updates_the_entry_instead_of_duplicating_it(self):
        d = self.finish()
        d['agent_history'].append(dict(d['agent_history'][0]))
        with self.assertRaisesRegex(v.VerificationError, 'unique'): self.save(d)

    def test_unit_is_implemented_by_a_worker_unless_marked_coordinator(self):
        # Regression: the coordinator implemented every unit itself instead of delegating.
        saved = self.save()
        closed = copy.deepcopy(self.doc)
        closed['tasks'][0].update(status='integrated', evidence_ref='evidence/A.json')
        closed['agent_history'] = [{'id': 'review-A', 'role': 'review', 'unit': 'A', 'state': 'completed'}]
        with self.assertRaisesRegex(v.VerificationError, 'worker entry'): self.save(closed, saved['state_token'])
        typo = copy.deepcopy(closed); typo['tasks'][0]['implementer'] = 'me'
        with self.assertRaisesRegex(v.VerificationError, 'worker or coordinator'): self.save(typo, saved['state_token'])
        adjusted = copy.deepcopy(closed); adjusted['tasks'][0]['implementer'] = 'coordinator'
        self.save(adjusted, saved['state_token'])

    def check(self, doc, *args):
        return subprocess.run([sys.executable, str(ENTRY), 'checkpoint-check', *args], input=json.dumps(doc),
                              text=True, capture_output=True, timeout=10, cwd=self.root)

    def rejected(self, doc, error, *args):
        result = self.check(doc, *args)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn(error, json.loads(result.stderr)['error'])

    def test_native_state_run_keeps_unit_gates_without_writing_a_file(self):
        # Regression: a project that forbade state files skipped checkpoint-save and every gate.
        unreviewed = copy.deepcopy(self.doc)
        unreviewed['tasks'][0].update(status='integrated', evidence_ref='issue#12 comment')
        unreviewed['agent_history'] = [{'id': 'w-A', 'role': 'implement', 'unit': 'A', 'state': 'completed'}]
        unbuilt = copy.deepcopy(unreviewed)
        unbuilt['agent_history'] = [{'id': 'r-A', 'role': 'review', 'unit': 'A', 'state': 'completed'}]
        early = copy.deepcopy(self.doc)
        early['tasks'].append({'id': 'B', 'repo': 'api', 'status': 'running', 'depends_on': ['A'],
                               'write_scope': ['src/b.py'], 'acceptance': ['B works.']})
        for doc, error in ((unreviewed, 'review entry'), (unbuilt, 'worker entry'), (early, 'dependencies'),
                           ({k: x for k, x in self.doc.items() if k != 'sources'}, 'requires sources')):
            with self.subTest(error=error):
                self.rejected(doc, error)
        done = self.finish(); done['objective'] = 'Entregar ação validada.'
        result = self.check(done)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual((receipt['status'], receipt['persisted'], receipt['path'], receipt['transition']),
                         ('valid', False, None, 'initial'))
        self.assertNotIn('state_token', receipt)
        canonical = json.dumps(done, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()
        self.assertEqual(receipt['document_digest'], hashlib.sha256(canonical).hexdigest())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_native_state_transition_applies_save_latches(self):
        # Without a file there is no stored previous state; the caller supplies it.
        paused = copy.deepcopy(self.doc); paused['tasks'][0]['status'] = 'pending'
        paused['control'] = {'state': 'paused', 'drain_units': [], 'reason': 'user review',
                             'requested_at': '2026-09-23T12:00:00+00:00'}
        advanced = copy.deepcopy(paused); advanced['tasks'][0]['status'] = 'blocked'
        self.rejected({'previous': paused, 'candidate': advanced}, 'without explicit resume')
        released = copy.deepcopy(paused); released['control']['state'] = 'running'
        self.rejected({'previous': paused, 'candidate': released}, '--resume')
        result = self.check({'previous': paused, 'candidate': released}, '--resume')
        self.assertEqual(json.loads(result.stdout)['transition'], 'checked', result.stderr)
        dropped = copy.deepcopy(self.doc); dropped['tasks'] = []
        self.rejected({'previous': self.doc, 'candidate': dropped}, 'nonempty')
        grown = copy.deepcopy(self.doc); grown['tasks'].append(
            {'id': 'Z', 'repo': 'api', 'status': 'running', 'depends_on': [], 'write_scope': ['z'], 'acceptance': ['z']})
        grown = self.finish(grown)
        self.rejected({'previous': self.finish(), 'candidate': grown}, 'immutable')

    def test_native_state_check_rejects_empty_or_malformed_input_cleanly(self):
        result = subprocess.run([sys.executable, str(ENTRY), 'checkpoint-check'], input='',
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('stdin', json.loads(result.stderr)['error'])
        odd = copy.deepcopy(self.doc); odd['agent_history'] = [{'id': {}, 'role': 'review', 'unit': 'A'}]
        self.rejected(odd, 'Malformed document')


if __name__ == '__main__': unittest.main()
