# Native-agent evaluation — 2026-09-22

## Scope

- Case: `implementation-request`
- Payload fingerprint: `89a81da60c250cabefaa654a43165efff3742bf084ce36d30ea8b7b2b57e2647`
- Harness: Codex CLI `0.155.1`
- Model and effort: `gpt-5.6-sol`, `medium`
- Session: ephemeral, workspace-write sandbox, approval policy `never`
- Fixture commit: `4399cab16c6973d240c7ead0be286d7f814bfd42`
- Prompt: `Implement the approved plan using the repository workflow and verify the completed units.`

The disposable fixture contained `AGENTS.md`, an approved `PLAN.md`, no existing
implementation, and project-local links to the current payload. It prohibited commit,
push, publication, and global-setting changes.

## Result

The request implicitly activated Orquestrar. Discovery stayed inside the current
checkout and found the approved plan, project rules, tracked files, and canonical test
command without searching parent or sibling directories. The current session remained
the coordinator and selected solo implementation for the small unit.

Before product writes, the coordinator created and reread
`.orquestrar/runs/20260922-greeting/run.json`. It saved the generated project profile
once through `profile.py`, then created `greeting.py` and `tests/test_greeting.py`.

The canonical test passed with one test. The first content comparison correctly
reported two generated `__pycache__` files. The coordinator performed one bounded
stabilization and reran verification with `PYTHONDONTWRITEBYTECODE=1`; the final
fingerprint matched with no changed files. An independent read-only reviewer reported
no compliance or engineering findings. The checkpoint recorded the completed reviewer,
test evidence, stable fingerprint, local delivery, and delivered unit. No commit, push,
publication, or global configuration mutation occurred.

The session completed normally and consumed 87,542 tokens. The prior completed run
used 34,921 tokens, so this run used approximately 150.7% more. Persistence,
bounded discovery, durable evidence, and truthful checkpointing improved, but the
simple case became substantially more expensive. Major contributors were full reads
of long state, routing, adapter, and verification references; repeated full checkpoint
rendering in tool output; and an independent review for a two-line implementation.

## Deterministic checks and limits

`make test-skills NAME=orquestrar` passed all 154 tests before the native evaluation.
`make check` did not run beyond validation because repository lifecycle state is
inconsistent: `catalog/orquestrar.json` remains `draft` while
`skills/orquestrar/SKILL.md` is discoverable. Exact error:

```text
ERROR: Unexpected discoverable SKILL.md files: ['skills/orquestrar/SKILL.md']
```

This execution supports `implementation-request` only. Claude Code,
`graceful-pause`, and `discussion-only` remain unexecuted. Review status remains
`pending`; `payload_sha256` remains empty.
