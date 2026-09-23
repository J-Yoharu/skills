# Orquestrar import record

Source archive: `orquestrar-2.3.0(3).zip` supplied by the maintainer.
SHA-256: `762d1478dece4d95830660ad404245c89446e7e6001612ec086a43e7e7c4912b`.

The archive's editing label `2.3.0` is not a release. No version tag, GitHub Release,
activation, or behavioral approval was imported. This repository uses `0.0.0` as the
unreleased bootstrap value and leaves `catalog/orquestrar.json` in `draft` state.

## Preserved product

All three runtime Python helpers, adapters, references, native subagent presets,
model/example assets, and `agents/openai.yaml` were copied without rewriting their
behavior. The current chat remains coordinator. Dynamic model/effort choice remains
subagent-only. Graceful pause, immediate stop, resume, and existing Portuguese CLI
control spellings remain intact. User-language behavior remains independent of the
repository's English maintenance policy.

Later maintenance removed the unused route resolver mode (`--runtime`/`--session-id`),
the native subagent presets under `assets/native/`, and the unreferenced
`runtime.example.json` and `project.example.json` assets. This paragraph records the
import; it does not describe the current payload.

The skill was then reduced to a single Markdown instruction file. The bundled scripts
(`profile.py`, `route.py`, `verify.py`), the JSON checkpoint and profile, the model
catalog, the references, and the adapters were removed. Progress is recorded in the
repository's own mechanism (issues, handoff, plan checkboxes) or in a plain Markdown
file. The validator-based design remains in the git history for comparison.

`SKILL.md` became `SKILL.md.template` to prevent accidental distribution of an unapproved
candidate. Its metadata version became `0.0.0` with the repository release marker.
The redundant `disable-model-invocation: false` extension was removed: false is the
Claude Code default, and removing it leaves the portable frontmatter within the
Agent Skills format. Description and instruction body were not translated or rewritten.
This is a documented default-preserving adjustment, not a live-agent behavior claim.

## Maintenance separation

The five supplied unit-test modules were moved to `tests/skills/orquestrar/` and their
product/evaluation paths were adjusted. A Portuguese test docstring and skip message
were translated to English. Explicit multilingual fixture data and Unicode filename
tests were retained. The 58 scenarios were moved outside the product and remain
byte-identical to the supplied JSON, with every execution status still `not_run`.
Scenario documentation now calls the version labels candidate history, not releases.

The monorepo supplies license/changelog/version files and a pending activation contract.
Older top-level source-package reports and test logs were not treated as current proof.
The old empty `orchestrar` scaffold was removed; no duplicate skill or alias was created.
Review the existing MIT attribution before the first public push.

## Local evaluation and release boundary

`make skill-preview NAME=orquestrar` creates a disposable installable folder without
changing tracked readiness. Test that copy in a separate authorized native-agent
project, record real traces and results, and keep failed/unrun cases explicit.
Neither deterministic tests nor a matching content hash prove orchestration behavior.

The bundled model catalog was preserved as supplied, not verified as live account
availability. Its own routing contract requires current observed capabilities.
See [Verification](VERIFICATION.md) for checks actually executed during integration.

## Primary format references

- [Agent Skills specification](https://agentskills.io/specification)
- [Claude Code frontmatter defaults](https://code.claude.com/docs/en/skills)
