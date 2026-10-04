# Orquestrar effort and unit-label follow-up — 2026-10-03

Status: controlled Codex self-evaluation, **pending human review**. This
record does not claim a new Claude Code run or approve the skill.

## Failure evidence and change

The user-run Claude Code session in
`/home/yoharu/.claude/projects/-var-www-html-skills/582fd5de-d84b-4f0e-ae9c-e6d3449c5fe3.jsonl`
used the prior payload `98c4a0faa9af20e0db7eebfc36ccb7fcce1f4bb3ae1b3d649dad6e95e5eb75ee`.
Its pre-dispatch preview called `reasoning_effort 30` the visible session
level; the parent JSONL metadata reported `effort=xhigh` and
`perTurnEffort=xhigh`. Intermediate user-facing text included bare IDs in
"Relatório de U1 recebido", "Confiro U2", and "lote U1+U2", despite
ID-title pairs in the preview and final progress record. Its final report
acknowledged the unverified numeric claim. This is diagnostic evidence for
the prior payload, not execution evidence for the current one.

The current payload fingerprint is
`a84c13b949ee9b8c36080579a15ab5a31f27fae145ea69b19dd01cf3524e1dc3`.
It now requires an ID-title pair in **every** user-facing unit mention,
including short status and review updates. Chat titles use the user's
language; source IDs and canonical titles remain in the project record.
For effort, a named level must come from a runtime control or configuration;
numeric hints, token budgets, and agent guesses do not establish it. If
inheritance is the only mechanism and the session level is unconfirmed, the
preview says so. Requested and effective values remain separate.

This distinction follows the official Claude Code documentation: subagent
`effort` frontmatter overrides the session level and otherwise inherits it;
supported levels are named and model-dependent; model support, organization
caps, and fallback can affect the applied level.

- https://code.claude.com/docs/en/sub-agents#frontmatter-reference
- https://code.claude.com/docs/en/model-config#adjust-effort-level

## Controlled forward test

The controlled run used payload
`1320afd3e28ecaac3493473def0a01a4cb1dcf95fff9c35988b57c8da602e195`.
The only subsequent skill-content edit removed an accidentally duplicated
sentence about not changing the coordinator's own model or effort; the same
sentence remains immediately above. The behavioral run therefore predates
the current fingerprint by this editorial deletion, not by a behavioral
instruction change. No full behavioral rerun is claimed for the current
fingerprint.

The older global installation at `/home/yoharu/.agents/skills/orquestrar`
was moved out of discovery before the run. The current skill was copied
byte-for-byte into the disposable fixture and compared with `diff -qr`.
The global installation was restored **once** after the run; no new payload
was installed. The fixture was
`/tmp/orquestrar-last-fixes-k2bD06/fixture`, with no Git, issue tracker,
network use, or credentials. Its `AGENTS.md` designated
`collaboration.send_message` to the evaluator as the user-visible channel.
Before orchestration, the fixture gate failed all five tests on deliberate
`NotImplementedError` stubs.

The coordinator was given the approved three-unit plan: two independent
units, U1 - Normalize customer labels and U2 - Validate quantity, followed
by dependent U3 - Render report line. The source titles were English and
the user's language was Portuguese. An opaque `reasoning_effort 30` hint
was present, but no confirmed named session level was supplied.

The evaluator received the preview before any worker appeared in the agent
tree. It used Portuguese ID-title pairs for all three units, `0 of 3`
accepted, dependencies, review and gate policy, state location, and local
delivery. It said workers and reviewers inherit effort and that the
effective level is unconfirmed; it did not equate `30` with a named level.
The coordinator then dispatched separate workers for U1 and U2.

All observed user-facing progress messages paired each mentioned unit ID
with a Portuguese title. Counts remained `0 of 3` during initial review,
`2 of 3` after U1/U2 acceptance, and `3 of 3` after U3 acceptance. Review
found a real Python integer-string limit in U2 and its inverse formatting
limit in U3. The coordinator kept the affected units pending, returned each
finding to its worker, and obtained a focused second review. U3 started
only after U1 and U2 were accepted.

The final `.orquestrar/compact-report.md` retained the canonical English
source titles, owners, dependencies, review outcomes, and test evidence.
The final fixture gate, independently re-run by the evaluator, was
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`:
10 tests passed, exit 0. No Git or remote resource was created.

## Local checks and limits

`make skill-fingerprint NAME=orquestrar` returned the digest above.
`make test-skills NAME=orquestrar` passed 7/7 and `git diff --check` passed.
The controlled fixture verifies observable Codex behavior on the
pre-editorial payload, not the
effective effort assigned by its runtime. It does not replace a fresh
Claude Code run on this fingerprint. `review.status` remains pending and
`review.payload_sha256` blank until human review; the full repository gate
therefore cannot pass its approval check for this payload.
