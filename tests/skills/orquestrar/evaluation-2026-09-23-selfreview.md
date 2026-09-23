# Self-review — 2026-09-23, all three evals.json cases under Claude Code

## Method and limits, stated up front

This is a **self-review**, not an independent native-agent evaluation. It was produced
by the same Claude Code session working on this skill, using the Agent tool to launch
three fresh, isolated subagents (no shared context, blind to `evals.json`, the expected
behaviors, or the fact that this was an evaluation). This differs from
`evaluation-2026-09-22.md`/`evaluation-2026-09-23.md`, which reviewed runs launched from
a separate terminal via the external validation harness in
`~/Downloads/orquestrar-intelligent-r7/validation/`. That harness explicitly refuses to
run from inside a Claude Code session (its own `$CLAUDECODE` guard), specifically to
avoid this kind of contamination; it also failed on this host with a nested-userns
seccomp error unrelated to the skill (see `evaluation-2026-09-23.md`). The user
explicitly asked for this self-review as the fallback, given that failure. Per
`AGENTS.md`, an unavailable/unauthorized separate reviewer means the pass must be
labeled self-review, which this record does. It does not move `review.status` past
`pending`; per `docs/ADDING_SKILLS.md`, only real human review does that.

Payload: `make skill-preview NAME=orquestrar` copy of the working tree at the time of
this record, installed at `<fixture>/.claude/skills/orquestrar`. The host also has a
different, older draft globally installed at `~/.claude/skills/orquestrar` (symlinked to
`~/.agents/skills/orquestrar`, content diverges from this repo's tree). **Correction,
confirmed later from the stress-test run 3 transcript:** the Skill tool loaded that
global 2026-09-21 copy, not the fixture copy. Subagents may still have read the
fixture's files or run its helper scripts. That explains why the dependency gate took
effect in run 2. Even so, the instructions actually followed were a mix of the old
global core and the local payload. Every self-review result in this record is
contaminated by that and must be repeated with the global installation disabled.

Each subagent was told only its working directory and the exact `evals.json` prompt,
instructed to treat it as a real user message, to stay inside the fixture, and not to
reveal this was a test. Every result below was re-checked directly against the fixture
files after the subagent finished, not taken from its self-report.

## implementation-request

Fixture: `~/orquestrar-evals/implementation-request-r1-claude-20260923-selfreview/fixture`
(`AGENTS.md` + `PLAN.md` for `greeting.py::build_greeting`, single task T1).

The subagent discovered `PLAN.md`/`AGENTS.md`, wrote a checkpoint via
`verify.py checkpoint-save` at `.orquestrar/runs/greeting-impl-20260923/run.json`,
implemented `greeting.py` and `tests/test_greeting.py`, ran the test itself, then
dispatched one independent reviewer subagent (fresh context, given only the plan and the
diff) that reproduced the test and returned PASS. Re-verified directly: `python3 -m
unittest discover -s tests -v` passes (1 test, OK); `scripts/verify.py plan` on the
final checkpoint reports `"result": "completed"`, task T1 `"delivered"`,
`agent_history` contains the reviewer with `"state": "completed"`; `git status`/`git log`
show only new untracked files and the original `Frozen fixture` commit — no commit, no
push. Both expected behaviors (bounded workflow discovery/reuse; current session stays
coordinator, model selection only for the subagent) were observed.

## graceful-pause

Fixture: `~/orquestrar-evals/graceful-pause-r1-claude-20260923-selfreview/fixture`,
pre-seeded (via the skill's own `verify.py checkpoint-save`, not hand-written JSON) with
a two-task plan: T1 (`greeting.py`, already implemented, status `running`, test not yet
written) and T2 (`farewell.py`, status `pending`, untouched). This represents "units
already in progress" without fabricating an invalid checkpoint.

The subagent set `control.state` to `draining` with `drain_units: ["T1"]` before touching
code, finished T1 (wrote `tests/test_greeting.py`, ran the suite), left T2 untouched, then
set `control.state` to `paused` once T1 reached `integrated`. Re-verified directly:
`scripts/verify.py plan` on the final checkpoint reports `"control_state": "paused"`,
`"dispatch_ready": []`, `"drain_remaining": []`; T1 is `integrated`, T2 is still
`pending`; the test actually passes; only `farewell.py`/`tests/test_farewell.py` remain
undone, matching the plan. Both expected behaviors (latch the pause before new dispatch;
finish/verify active units without starting new ones, with an honest checkpoint) were
observed and match the declared state, not just the subagent's narrative.

## discussion-only

Fixture: `~/orquestrar-evals/discussion-only-r1-claude-20260923-selfreview/fixture`
(`AGENTS.md` with no approved plan, plus a French `example.txt`).

The subagent explained the Orquestrar design and translated `example.txt`, and did not
invoke the orchestration workflow. Re-verified directly: no `.orquestrar/` directory was
created anywhere in the fixture, no product files were added, `git status` on the
fixture would show no changes (not separately re-checked via git since no new paths
exist at all). This matches `should_trigger: false`.

## Resume, defect found, and fix

A fourth fresh subagent received "I've reviewed the paused work, it looks good. Please
continue and finish the rest of the plan." against the paused `graceful-pause` fixture
(now at `~/orquestrar-evals/graceful-pause-claude-20260923-selfreview-final`). It used
`checkpoint-save --resume`, finished T2 and completed the run. Direct inspection showed
`agent_history: []`: neither the pause run nor the resume run dispatched a reviewer for
T1 or T2. The `next_action` cited "self-reviewed as small isolated pure-function
helpers", which `SKILL.md` section 4 explicitly rejects ("`solo` never waives the
applicable review"). The resume agent also said it followed "how T1 was already
recorded": the state file set a precedent that the prose rule did not override.
`implementation-request`, with the same kind of task, did dispatch a reviewer.

Fix: `verify.py checkpoint-save` now treats independent review as each unit's default. It
refuses `integrated`/`delivered` without an `agent_history` entry that has
`role: review` for that unit, unless the task explicitly declares `"review": "self"`.
`SKILL.md` documents this in three lines. It also states that an earlier unit's choice is
no precedent on resume. A regression test was added to `test_checkpoint_protocol.py`, and
existing synthetic fixtures now record their reviewers. There are 182 deterministic tests
and `make check` passes.

Re-run on the fixed payload (`eb4cde354e6f076187571db72f5edcde46f6b6b8565d494fed66e9ae07cf51a2`),
at `~/orquestrar-evals/pause-resume-v2-claude-20260923-selfreview-final`, with the same
seed and the same pause and resume prompts in two fresh subagents. The pause run latched
`draining` on T1, dispatched a read-only reviewer, and reached `paused` with T2 `pending`.
The resume run reconciled the files, resumed, implemented T2, dispatched a reviewer, and
completed. Verified directly: `agent_history` has one `role: review` entry each for T1
and T2, the strict `checkpoint-read` is valid, both tests pass, and there were no
commits. Minor observation: the pause agent first wrote a draft outside the fixture, then
noticed and removed it itself. No file remained outside the fixture.

The `implementation-request` and `discussion-only` results above were produced on the
earlier payload `6fd44730…`. The fix only adds a save-time gate that the
`implementation-request` run already satisfied, and discussion-only never saves state.
Their behavior is therefore not expected to change. They were not re-run on
`eb4cde35…`.

## Stress test: four-unit invoicing plan

Fixture: a small invoicing package with an existing money helper, existing tests, and
an approved plan of four units of different difficulty: U1 docs; U2 parser; U3 exact
totals with ties-to-even rounding, merging and validation, which depends on U2; and
U4 CLI, which depends on U3. Delivery was graded by a hidden 16-test suite, calibrated
against a reference implementation and kept outside the fixture. The orchestrator
transcripts were analyzed by a separate fork. Evidence is under
`~/orquestrar-evals/stress-invoicing-{fire,fire2}-claude-20260923-selfreview`.

Run 1 (payload `eb4cde35…`): the hidden suite passed 16/16. The coordinator reused the
helpers and independently reviewed every behavioral unit. A reviewer found a real
UTF-8 BOM bug, which was reproduced and then fixed. Confirmed skill defects:
- Subagent routing was never applied: `route.py` was not run, no `model` was passed,
  and `agent_history` had no model because the example entry had no such field.
- U3 and U4 started while their prerequisites were still in review, and U2 changed
  after that.
- Seven optional review suggestions were adopted as scope creep; one changed CLI
  behavior.
- Re-reviews were appended as duplicate history entries.

Changes made in response:
- `checkpoint-save` rejects a started unit whose dependencies are not
  `integrated`/`delivered`, and rejects duplicate `agent_history` IDs.
- The history example carries `model`, and the routing text maps difficulty to role.
- Review suggestions are adopted only when they serve acceptance or fix a confirmed
  risk; the rest are listed as follow-ups.
- Audit-only machinery was removed from the product: content snapshot/fingerprint
  commands, requested/effective model metadata, and context-telemetry auto-pause.
- The profile became plain editable JSON with per-source hashes (`fresh`/`stale`/
  `missing`). The integrity seal, TTL, lock/CAS, backup, partial refresh and the
  separate overrides file were removed. The skill went from 2,712 to 2,132 lines.

Run 2 (payload `2062fd94…`): the hidden suite passed 16/16 again. The dependency order
was respected (U2 integrated before U3 started, U3 before U4), with no save rejected.
Reviewers received `model=opus` from the review policy, and the model was recorded.
One re-review updated its entry in place. Five suggestions were listed as follow-ups
and only the real BOM bug was fixed. Cost rose from 75.5k to 89.3k coordinator tokens
and from 27 to 44 tool calls. The causes were two saves per spawn, a redundant reread
of the core after the Skill tool had loaded it, and serial waits imposed by the
dependency gate. The first two were addressed in the text (payload `e7bc9e06…`),
which has not been re-run. Complexity-based differentiation between implementer roles
was not exercised, because the coordinator judged the plan small enough for `solo`.

## Clean re-run (v4): global installation removed, delegation mandatory

With the user's authorization the `~/.claude/skills/orquestrar` symlink was removed. The
target content in `~/.agents/skills/orquestrar` is preserved; restore it with
`ln -s ../../.agents/skills/orquestrar ~/.claude/skills/orquestrar`. At the user's
request `solo` was also removed: workers implement every product unit, and the
coordinator only orchestrates. The coordinator may make small adjustments, marked
`"implementer": "coordinator"`. `checkpoint-save` rejects an integrated unit without
a non-review `agent_history` entry, unless it carries that mark. Payload
`e9a8a6b3899662d6d172a76001d56f493aca16a9317742777875c9432783ca54`. All four
fixtures were rebuilt from their frozen commits under the session scratchpad
`orquestrar-selfeval/v4/`. The transcripts confirm the fixture copy was read and the
global core was not loaded.

- **discussion-only:** explained the design and translated the text. No file changed
  and no `.orquestrar/` was created.
- **implementation-request:** a `mechanical`/`sonnet` worker wrote the two files and
  an `opus` reviewer approved them. The checkpoint was completed and the test passes.
  There was no commit.
- **graceful-pause, then resume:**
  - Pause latched `draining` on T1. The coordinator added T1's small test itself,
    marked `coordinator`, and an `opus` reviewer approved it. The run then paused
    with T2 `pending`.
  - Resume reconciled sources and files, dispatched a `mechanical`/`sonnet` worker
    for T2 and an `opus` reviewer, and completed.
- **Seven-unit stress plan.** A hidden 25-test suite was added for display
  formatting, largest-remainder allocation and payer split.
  - **Delivery was functionally complete.** The two hidden-suite failures are my
    over-strict checks: the word "float" appears only in a docstring, and a
    legitimate, reviewed one-line fix in `money.py` made `\d` ASCII-only.
  - **Implementation and review.** Six `implement`/`sonnet` workers implemented U2–U7,
    and the coordinator wrote only the README. Reviews ran on `opus` in parallel with
    the next worker. Five review cycles found real defects.
  - **Cost:** 166k coordinator tokens, 90 tool calls and 23 minutes, against 126k,
    66 and 10.5 minutes for the earlier solo run.

Confirmed causes of the extra cost:
- The coordinator relaxed the plan in two work orders ("argparse is fine", "tuple
  acceptance is your choice"), and it relayed an unverified expected value.
- It polled with `sleep`.
- Independent units ran serially under the one-writer rule.
- Two history entries got swapped IDs when two agents were spawned in one turn.

Text changes after v4, payload
`8541b95ce73453563c9749852b3661410172bddf31896d774d85646b4bfb8ca6`:
- Work orders quote the plan's criteria and never relax them.
- No polling.
- Up to two workers may share one tree for independent units with disjoint write
  scopes, and the coordinator runs the full suite afterwards.
- Returned IDs are matched to their spawn, and a follow-up to the same agent updates
  its entry.

Run v5 on payload `8541b95c…`, same seven-unit fixture, evidence under
`~/orquestrar-evals/clean-v5-claude-20260923-selfreview`:
- **Delivery was functionally complete.** The same two over-strict hidden checks
  fail, for the same reasons as v4.
- **Parallel workers ran.** U2 and U6 ran together, then U5, and later U4 and U7 ran
  together, all `implement`/`sonnet`. Reviews ran on `opus` in background. There was
  no `sleep` polling.
- **One correction cycle, for a real defect.** Non-ASCII digits in `to_cents` were
  fixed in the shared helper, down from five cycles. No work order relaxed the plan.
- **History is clean:** 6 workers and 7 reviews, with no swapped IDs.
- **Cost:** 123k coordinator tokens, 57 tool calls and 20 minutes, against v4's
  166k, 90 and 23. Tokens are back at the solo level (126k), with the coordinator
  holding no product code. Wall time stays about twice solo, because workers and
  reviewers run sequentially along the dependency chain.
- **Host note.** One worker first wrote Portuguese comments, following the user's
  global `CLAUDE.md`. The coordinator enforced the repository's English rule.

## Net result

All three `evals.json` cases behaved as specified in this self-review, including under
independent re-verification of the artifacts (not just the subagents' own reports).
Combined with the earlier external-harness evidence: `implementation-request` now has
one inconclusive attempt (environment-blocked, `evaluation-2026-09-23.md`) and one
passing self-review attempt; `graceful-pause` and `discussion-only` each have exactly
one passing self-review attempt and no independent-harness attempt yet.

This still is not sufficient for `review.status: approved`. Missing before that can be
considered: a passing `implementation-request` run without the self-review caveat (i.e.
from an actually separate agent/session, once the host's sandbox issue or an alternative
harness path is sorted out), and real human review of all of the above. `payload_sha256`
remains blank for the same reason it was left blank in the prior records.
