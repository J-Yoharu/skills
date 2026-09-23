"""Policy slicing is not evidence of live model availability."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
SKILL = Path(__file__).resolve().parents[3] / 'skills' / 'orquestrar'
spec = importlib.util.spec_from_file_location('orq_route_view', SKILL/'scripts/route.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)

class RouteViewTests(unittest.TestCase):
    def test_only_requested_role_and_bindings_are_returned(self):
        catalog = r.read(SKILL/'assets/model-catalog.json')
        for harness in ('codex', 'claude-code'):
            view = r.policy_view(catalog,harness,'review')
            self.assertEqual(view['status'],'policy_only'); self.assertEqual(view['availability'],'unverified')
            self.assertIsNone(view['effective']); self.assertNotIn('harnesses',view)
            self.assertEqual(set(view['bindings']),{c['family'] for c in view['policy']['choices']})
            self.assertNotIn('implement', json.dumps(view))
    def test_same_overrides_are_used_without_rewriting_the_catalog(self):
        catalog = r.read(SKILL/'assets/model-catalog.json'); original = json.dumps(catalog,sort_keys=True)
        override={'role_overrides':{'codex':{'review':{'choices':[{'family':'sol','effort':'medium'}]}}}}
        self.assertEqual(r.policy_view(catalog,'codex','review',override)['policy']['choices'][0]['effort'],'medium')
        self.assertEqual(json.dumps(catalog,sort_keys=True), original)
    def test_cli_policy_needs_no_fake_inventory_but_never_routes_coordinator(self):
        for role, code in [('review',0),('coordinate',2)]:
            p=subprocess.run([sys.executable,str(SKILL/'scripts/route.py'),'--show-policy','--harness','codex','--role',role],
                             capture_output=True,text=True,timeout=10)
            self.assertEqual(p.returncode,code,p.stderr)
    def test_harness_is_required(self):
        p=subprocess.run([sys.executable,str(SKILL/'scripts/route.py'),'--role','review'],capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,2); self.assertIn('--harness',p.stderr)

if __name__=='__main__': unittest.main()
