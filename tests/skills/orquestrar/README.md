# Orquestrar verification

The runtime implementation is in `skills/orquestrar/`. The five imported `test_*.py`
files are deterministic helper/contract regressions; they do not execute an LLM.
Run them with `make test-skills NAME=orquestrar`. The test runner discovers future
`test_*.py` files automatically and runs each skill in a fresh subprocess.

[Scenarios](scenarios.json) preserves all 58 supplied behavioral specifications and
multilingual user inputs. [Scenario guidance](SCENARIOS.md) explains execution evidence.
Every scenario remains `not_run`. [Readiness](evals.json) remains `pending`; passing
unit tests or CLI smoke tests is not behavioral approval.

Use `make skill-preview NAME=orquestrar` to obtain a local, installable evaluation
copy at `dist/skill-preview/orquestrar`. This does not rename the source template,
activate the catalog entry, record approval, register a release, or contact GitHub.
See [the import record](../../../docs/ORQUESTRAR_IMPORT.md) for provenance and changes.

After real native-agent evaluation and explicit authorization, record the current
fingerprint from `make skill-fingerprint NAME=orquestrar` with actual review evidence.
Only then use `make skill-activate NAME=orquestrar`. Never approve solely to pass CI.
