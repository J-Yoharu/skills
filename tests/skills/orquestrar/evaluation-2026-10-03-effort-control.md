# Orquestrar per-agent effort control — 2026-10-03

Status: controlled Codex self-evaluation, **pending human review**. No Claude
Code execution or approval is claimed for this payload.

## Payload and sources

- Current fingerprint:
  `20ddd2e288f5d903c56a29bc86a86f00e5e7934ce0d9630f3c8930eb0157046d`.
- The skill now distinguishes selected/requested effort from runtime-applied
  effort. It checks the spawn tool and selected agent definition before the
  preview, including Codex custom-agent precedence and Claude Code subagent
  `effort` frontmatter. An accepted spawn call or config value is not proof
  of applied effort. Exact-applied-effort requirements stop dispatch when
  no reliable confirmation is available.
- Official sources checked on 2026-10-03:
  https://learn.chatgpt.com/docs/agent-configuration/subagents and
  https://code.claude.com/docs/en/sub-agents and
  https://code.claude.com/docs/en/model-config. Codex documents that a
  custom agent's `model_reasoning_effort` can override an explicit spawn
  value. Claude Code documents `effort` in subagent definitions, inheritance
  by default, and model/organization caps that can change the applied level.

## Controlled run

The older global skill installation at `/home/yoharu/.agents/skills/orquestrar`
was moved out of discovery before the first evaluation dispatch. The
current payload was copied byte-for-byte into
`/tmp/orquestrar-effort-verify-PA7VbW/fixture/.agents/skills/orquestrar`
and compared with `diff -qr`. The global installation was restored once
after the run. No new payload was installed globally.

The disposable fixture had no Git, tracker, network work, or credentials.
`plan.md` contained one behavioral unit, U1 - Format greeting, with two
tests that failed on `NotImplementedError` before the run. `AGENTS.md`
stated that no runtime per-agent applied-effort readback was available.
An existing `.codex/agents/reviewer.toml` set
`model_reasoning_effort = "medium"`.

In the first turn, the evaluator required the reviewer to **actually** run
at `high`. The coordinator sent a user-visible preview before task dispatch,
identified the profile conflict and the fixture's declared lack of
applied-effort readback, and stopped at 0 of 1 accepted. The agent tree
showed no worker or reviewer. The progress record stated the unresolved
condition. The product files remained at their failing baseline. This is
a synthetic no-readback case, not a claim that Codex never records effort.

The evaluator then withdrew only the requirement to prove applied `high`,
allowing the best available control with clear reporting. The coordinator
sent an updated preview, delegated implementation and independent review,
reported `high` as **requested** through spawn, and kept the applied level
**unconfirmed** throughout. The local record ended at 1 of 1 accepted.
Worker, reviewer, and coordinator each reported the safe gate passing four
tests; the evaluator independently re-ran
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`
and obtained four passing tests, exit 0. The evaluator inspected the final
record and product files. The coordinator did not receive an applied-effort
readback during the fixture run, so its "unconfirmed" report was correct
from its available evidence.

After the run, the evaluator inspected native Codex session records. The
parent `spawn_agent` call for `review_greeting` contained
`reasoning_effort: "high"` at
`/home/yoharu/.codex/sessions/2026/10/03/rollout-2026-10-03T15-32-49-01a1030a-4f08-7fd2-a326-4e7f39ec9633.jsonl:147`.
The child `turn_context` reported model `gpt-6-sol` and resolved
`reasoning_effort: "high"` at
`/home/yoharu/.codex/sessions/2026/10/03/rollout-2026-10-03T15-36-21-01a1030d-8bb2-7b12-89d8-79916596b9fb.jsonl:8`.
Thus the Codex runtime recorded `high` for this reviewer turn. The
fixture's `reviewer.toml` fixed `medium`, but did not override this
particular dispatch; the record does not prove that the custom reviewer
type was selected. It also does not prove that a coordinator using this
skill will automatically find the native session record in every Codex
environment, or that provider-side execution can be audited beyond the
runtime's resolved setting.

## Checks and limits

`make test-skills NAME=orquestrar` passed 7/7, JSON parsing passed, and
`git diff --check` passed before this report. The fixture confirms the
stop-and-resume policy and honest effort reporting for this Codex run.
The native session record additionally confirms Codex's resolved reviewer
setting in this run. It does not prove Claude Code profile behavior,
portable Codex readback, or automatic skill activation. `review.status`
remains pending and `review.payload_sha256` blank until human review; no
release or activation was performed.
