# Orquestrar verification

The skill is a single instruction file, `skills/orquestrar/SKILL.md`, plus
`agents/openai.yaml`. It bundles no scripts, so there are no runtime entrypoints or
smoke tests. `test_skill_contract.py` checks the package shape and the evaluation
record; it does not execute an LLM. Run it with `make test-skills NAME=orquestrar`.

Behavioral evidence comes from real agent runs recorded in `evaluation-*.md` and
summarized in [evals.json](evals.json). The maintainer approved payload `d5a79c27…`
on 2026-09-23; any content change makes that record stale. [Scenarios](scenarios.json) and [SCENARIOS.md](SCENARIOS.md) are the 58
specifications supplied with the imported design; many describe its JSON checkpoint,
which no longer exists. All remain `not_run`.

Use `make skill-preview NAME=orquestrar` for a disposable installable copy under
`dist/skill-preview/orquestrar`. See [the import record](../../../docs/ORQUESTRAR_IMPORT.md)
for provenance and later changes.
