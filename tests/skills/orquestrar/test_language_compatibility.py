"""Data/CLI compatibility checks, not multilingual LLM behavior evaluations."""
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
spec = importlib.util.spec_from_file_location(
    "orq_verify_language", SKILL / "scripts/verify.py"
)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


def legacy_run() -> dict:
    return {
        "schema_version": 1,
        "run_id": "exemplo-001",
        "objective": "Preservar a implementação aprovada e suas decisões.",
        "decisions": ["Manter os nomes atuais; não publicar."],
        "tasks": [
            {"id": "T1", "repo": "api", "status": "integrated", "depends_on": []},
            {"id": "T2", "repo": "web", "status": "pending", "depends_on": ["T1"]},
        ],
        "control": {
            "state": "paused",
            "reason": "Pausa concluída para análise em outra sessão.",
            "requested_at": "2026-09-21T12:00:00-03:00",
            "drain_units": ["T1"],
        },
        "active_agents": [],
        "active_processes": [],
    }


class LanguageCompatibilityTests(unittest.TestCase):
    def test_prose_language_does_not_change_graph_or_release_pause(self):
        original = legacy_run()
        translated = copy.deepcopy(original)
        translated["objective"] = "Preserve the approved implementation and decisions."
        translated["decisions"] = ["Keep existing names; do not publish."]
        translated["control"]["reason"] = "Paused for review in another session."
        self.assertEqual(verify.validate_plan(original), verify.validate_plan(translated))
        self.assertEqual(verify.validate_plan(original)["dispatch_ready"], [])
        self.assertEqual(verify.validate_plan(original)["dependency_ready"], ["T2"])

    def test_validation_preserves_legacy_portuguese_records(self):
        document = legacy_run()
        before = copy.deepcopy(document)
        result = verify.validate_plan(document)
        self.assertEqual(document, before)
        self.assertEqual(result["control_state"], "paused")
        self.assertEqual(result["drain_remaining"], [])

    def test_stored_states_are_not_translated_or_given_locale_aliases(self):
        document = legacy_run()
        document["control"]["state"] = "pausado"
        with self.assertRaisesRegex(verify.VerificationError, r"control\.state"):
            verify.validate_plan(document)
        document = legacy_run()
        document["tasks"][0]["status"] = "integrado"
        with self.assertRaisesRegex(verify.VerificationError, "Invalid state"):
            verify.validate_plan(document)

    def test_cli_reads_legacy_file_without_rewriting_and_keeps_error_envelope(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "retomada.json"
            path.write_text(json.dumps(legacy_run(), ensure_ascii=False), encoding="utf-8")
            before = path.read_bytes()
            command = [sys.executable, str(SKILL / "scripts/verify.py"),
                       "plan", "--file", str(path)]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["control_state"], "paused")
            self.assertEqual(path.read_bytes(), before)
            invalid = legacy_run()
            invalid["control"]["state"] = "pausado"
            path.write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")
            failed = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(failed.returncode, 2)
            self.assertEqual(failed.stdout, "")
            self.assertEqual(set(json.loads(failed.stderr)), {"error"})
            self.assertIn("control.state", json.loads(failed.stderr)["error"])


if __name__ == "__main__":
    unittest.main()
