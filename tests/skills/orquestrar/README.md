# Orquestrar verification

The skill is a single instruction file, `skills/orquestrar/SKILL.md.template`, plus
`agents/openai.yaml`. It bundles no scripts, so there are no runtime entrypoints or
smoke tests. `test_skill_contract.py` checks the package shape and the evaluation
record; it does not execute an LLM. Run it with `make test-skills NAME=orquestrar`.

Behavioral evidence comes from real agent runs recorded in `evaluation-*.md` and
summarized in [evals.json](evals.json), whose review stays `pending` until a human
approves it. [Scenarios](scenarios.json) and [SCENARIOS.md](SCENARIOS.md) are the 58
specifications supplied with the imported design; many describe its JSON checkpoint,
which no longer exists. All remain `not_run`.

Use `make skill-preview NAME=orquestrar` for a disposable installable copy under
`dist/skill-preview/orquestrar`. See [the import record](../../../docs/ORQUESTRAR_IMPORT.md)
for provenance and later changes.
