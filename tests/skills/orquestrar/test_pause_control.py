"""Declared-control validation and CLI regression tests, not live agent evaluations."""
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
spec = importlib.util.spec_from_file_location("verify_pause", SKILL / "scripts/verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


def plan(state="draining"):
    return {
        "schema_version": 1, "run_id": "pause-test", "objective": "Stable active unit",
        "control": {"state": state, "reason": "user pause", "requested_at": "2026-09-21T12:00:00-03:00", "drain_units": ["A"]},
        "active_agents": [], "active_processes": [],
        "tasks": [
            {"id": "A", "repo": "api", "status": "running", "depends_on": []},
            {"id": "B", "repo": "web", "status": "pending", "depends_on": ["A"]},
            {"id": "C", "repo": "docs", "status": "pending", "depends_on": []},
        ],
    }


class PauseControlTests(unittest.TestCase):
    def test_legacy_plan_keeps_graph_and_explicit_dispatch_view(self):
        p = plan(); p.pop("control"); p["tasks"][0]["status"] = "integrated"
        out = verify.validate_plan(p)
        self.assertEqual(out["dependency_ready"], ["C", "B"])
        self.assertEqual(out["dispatch_ready"], ["C", "B"])
        self.assertEqual(out["control_state"], "running")

    def test_drain_blocks_even_independent_lane(self):
        out = verify.validate_plan(plan())
        self.assertEqual(out["dependency_ready"], ["C"])
        self.assertEqual(out["dispatch_ready"], [])
        self.assertEqual(out["drain_remaining"], ["A"])

    def test_finishing_active_unit_does_not_release_successor(self):
        p = plan(); p["tasks"][0]["status"] = "integrated"
        out = verify.validate_plan(p)
        self.assertIn("B", out["dependency_ready"])
        self.assertEqual(out["dispatch_ready"], [])
        self.assertEqual(out["drain_remaining"], [])

    def test_until_cannot_bypass_latch_or_hide_active_units(self):
        out = verify.validate_plan(plan(), "C")
        self.assertEqual(out["selected_order"], ["C"])
        self.assertEqual(out["dispatch_ready"], [])
        self.assertEqual(out["drain_remaining"], ["A"])

    def test_review_and_gate_are_not_a_completed_boundary(self):
        for status in ("running", "implemented", "reviewing", "verified", "blocked", "paused"):
            with self.subTest(status=status):
                p = plan(); p["tasks"][0]["status"] = status
                self.assertEqual(verify.validate_plan(p)["drain_remaining"], ["A"])

    def test_paused_rejects_incomplete_frozen_unit(self):
        for status in ("pending", "running", "implemented", "reviewing", "verified", "blocked", "paused"):
            with self.subTest(status=status):
                p = plan("paused"); p["tasks"][0]["status"] = status
                with self.assertRaisesRegex(verify.VerificationError, "stable boundaries"):
                    verify.validate_plan(p)

    def test_paused_accepts_stable_local_content_without_commit_permission(self):
        p = plan("paused"); p["tasks"][0]["status"] = "integrated"
        p["permissions"] = {"commit": False, "push": False}
        p["delivery"] = "local"
        self.assertEqual(verify.validate_plan(p)["dispatch_ready"], [])

    def test_delivered_frozen_unit_is_stable(self):
        p = plan("paused"); p["tasks"][0]["status"] = "delivered"
        self.assertEqual(verify.validate_plan(p)["drain_remaining"], [])

    def test_paused_needs_confirmed_empty_agent_and_process_lists(self):
        for field in ("active_agents", "active_processes"):
            for bad in (None, {}, False, [{"id": "unknown"}], "none"):
                with self.subTest(field=field, value=bad):
                    p = plan("paused"); p["tasks"][0]["status"] = "integrated"; p[field] = bad
                    with self.assertRaisesRegex(verify.VerificationError, field):
                        verify.validate_plan(p)
            p = plan("paused"); p["tasks"][0]["status"] = "integrated"; p.pop(field)
            with self.assertRaisesRegex(verify.VerificationError, field):
                verify.validate_plan(p)

    def test_shared_retained_service_does_not_count_as_unfinished_build(self):
        p = plan("paused"); p["tasks"][0]["status"] = "integrated"
        p["retained_resources"] = [{"id": "shared-db", "ownership": "external", "reason": "stable shared service"}]
        self.assertEqual(verify.validate_plan(p)["control_state"], "paused")

    def test_draining_rejects_active_unit_missing_from_snapshot(self):
        p = plan(); p["tasks"][2]["status"] = "reviewing"
        with self.assertRaisesRegex(verify.VerificationError, "outside the frozen"):
            verify.validate_plan(p)

    def test_parallel_drain_reports_only_frozen_incomplete_units(self):
        p = plan(); p["tasks"][2]["status"] = "reviewing"; p["control"]["drain_units"].append("C")
        self.assertEqual(verify.validate_plan(p)["drain_remaining"], ["A", "C"])
        p["tasks"][0]["status"] = "integrated"
        self.assertEqual(verify.validate_plan(p)["drain_remaining"], ["C"])

    def test_interrupted_preserves_wip_and_unknown_agents_without_dispatch(self):
        p = plan("interrupted"); p["active_agents"] = [{"id": "old-worker", "state": "unknown"}]
        before = copy.deepcopy(p)
        out = verify.validate_plan(p)
        self.assertEqual(out["dispatch_ready"], [])
        self.assertEqual(out["drain_remaining"], ["A"])
        self.assertEqual(p, before)

    def test_cannot_hide_active_task_by_empty_drain(self):
        for state in ("draining", "paused"):
            p = plan(state); p["control"]["drain_units"] = []
            with self.subTest(state=state), self.assertRaises(verify.VerificationError):
                verify.validate_plan(p)

    def test_legacy_paused_task_prevents_clean_pause_declaration(self):
        p = plan("paused"); p["tasks"][0]["status"] = "integrated"; p["tasks"][2]["status"] = "paused"
        with self.assertRaisesRegex(verify.VerificationError, "stable boundaries"):
            verify.validate_plan(p)

    def test_pause_between_units_accepts_empty_frozen_set(self):
        p = plan("paused"); p["control"]["drain_units"] = []; p["tasks"][0]["status"] = "integrated"
        self.assertEqual(verify.validate_plan(p)["dispatch_ready"], [])

    def test_malformed_control_is_rejected_not_treated_as_running(self):
        for bad in (None, [], "paused", False):
            with self.subTest(value=bad):
                p = plan(); p["control"] = bad
                with self.assertRaises(verify.VerificationError): verify.validate_plan(p)

    def test_unknown_or_nonstring_state_rejected_with_domain_error(self):
        for bad in (None, [], {}, True, "done", "resume", "PAUSED"):
            with self.subTest(value=bad):
                p = plan(); p["control"]["state"] = bad
                with self.assertRaises(verify.VerificationError): verify.validate_plan(p)

    def test_frozen_ids_are_unique_known_and_typed(self):
        for bad in (None, "A", ["A", "A"], ["unknown"], [7], [{}]):
            with self.subTest(value=bad):
                p = plan(); p["control"]["drain_units"] = bad
                with self.assertRaises(verify.VerificationError): verify.validate_plan(p)

    def test_stopped_control_requires_freeze_reason_and_time(self):
        for field in ("drain_units", "reason", "requested_at"):
            with self.subTest(field=field):
                p = plan(); p["control"].pop(field)
                with self.assertRaises(verify.VerificationError): verify.validate_plan(p)

    def test_request_time_requires_iso_and_timezone(self):
        for bad in ("", "tomorrow", "2026-09-21T10:00:00", 70):
            with self.subTest(value=bad):
                p = plan(); p["control"]["requested_at"] = bad
                with self.assertRaises(verify.VerificationError): verify.validate_plan(p)
        p = plan(); p["control"]["requested_at"] = "2026-09-21T10:00:00Z"
        self.assertEqual(verify.validate_plan(p)["control_state"], "draining")

    def test_lower_context_after_compaction_does_not_unlatch(self):
        p = plan("paused"); p["tasks"][0]["status"] = "integrated"
        p["context_observation"] = {"used_percent": 5, "source": "synthetic-after-compaction"}
        self.assertEqual(verify.validate_plan(p)["dispatch_ready"], [])

    def test_validation_never_mutates_or_resumes_the_checkpoint(self):
        p = plan(); before = copy.deepcopy(p)
        self.assertEqual(verify.validate_plan(p), verify.validate_plan(p))
        self.assertEqual(p, before)

    def cli(self, p):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "run.json"; path.write_text(json.dumps(p))
            return subprocess.run([sys.executable, str(SKILL / "scripts/verify.py"), "plan", "--file", str(path)],
                                  capture_output=True, text=True, timeout=15)

    def test_cli_drain_succeeds_but_does_not_dispatch(self):
        out = self.cli(plan())
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["dispatch_ready"], [])

    def test_cli_invalid_clean_pause_fails_without_success_payload(self):
        out = self.cli(plan("paused"))
        self.assertEqual(out.returncode, 2)
        self.assertEqual(out.stdout, "")
        self.assertIn("error", json.loads(out.stderr))

    def test_cli_handles_malformed_state_without_traceback(self):
        p = plan(); p["control"]["state"] = []
        out = self.cli(p)
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("Traceback", out.stderr)
        self.assertIn("error", json.loads(out.stderr))


if __name__ == "__main__":
    unittest.main()
