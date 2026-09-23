# Orquestrar self-review: instructions-only skill (2026-09-23)

This is a **self-review**, not an approval. `review.status` stays `pending`.

## What changed

The skill is now one instruction file (about 170 lines) plus `agents/openai.yaml`.
The JSON checkpoint, the project profile, the model catalog, the three helper scripts,
the references, and the adapters were removed. The validator-based design is kept in
commit `bd414c7` for comparison.

The skill states five guarantees:

1. Workers implement.
2. Review matches risk.
3. Dependencies come first.
4. The repository's gate decides.
5. Progress is resumable.

Progress goes to the repository's own mechanism, or to a plain
`.orquestrar/<run-name>.md` when there is none. Review is independent for behavior
changes and skipped for non-behavioral changes, and the user can replace that policy.
Units run in parallel only when their write areas and contracts are disjoint.

## Method

- Payload evaluated: `27329df2413a760d887a4babef7dec4835106ec028d7964429528c1c189e9c92`
  (commit `e172d9f`).
- There was no global install, so no other copy of the skill could be loaded.
- The payload came from `make skill-preview` and was copied to
  `<fixture>/.claude/skills/orquestrar`.
- Each run used a fresh `general-purpose` subagent that got the working directory, a
  note that project skills must be read from their `SKILL.md`, and the user prompt.
- Results were re-checked on disk: hidden suites kept outside the fixtures,
  `git log`/`status`, the progress records, and the fixtures' own logs.
- Fixtures F1–F3 are the frozen fixtures from `evaluation-2026-09-23-traits.md`. F4–F6
  are new.
- Evidence: `~/orquestrar-evals/simple-claude-20260923-selfreview/`.

## Results

| Fixture | Prompt / trait | Hidden suite | Coordinator cost |
|---|---|---|---|
| F1 | No agent instructions; gate is `make check`; pt-BR | 10/10 | 78.6k tokens, 12.3 min |
| F2 | Tracker-only plan, no state files, main-context gate, commit per unit | 11/11 | 61.0k tokens, 5.9 min |
| F3 | Two repositories, committed-contract dependency, slow suite | 7/7 | 57.6k tokens, 7.8 min |
| F4 | "Skip per-unit reviews, one review at the end"; docs unit; two units on one file | 6/6 | 44.6k tokens, 4.5 min |
| F5 | Handoff-driven repository; "pause after the first two units" | 5/5 | 47.6k tokens, 5.6 min |
| F6 | Explain and translate only (negative activation) | nothing written | 26.1k tokens, 0.5 min |

### F1: no agent instructions

- U1 and U2 ran in parallel because they write disjoint files. U3 ran after both.
- Reviews found real defects in U1 and U3, and each fix was re-reviewed.
- The final `make check` ran on the combined tree.
- The Markdown record lists, for each unit, the worker, the reviewer, and the evidence.
- The work stayed local, and the coordinator gave the push-to-production rule as the
  reason.

### F2: tracker-driven

- State lived only in 9 issue comments.
- There are three pt-BR commits ending in `Refs #12` on the linked branch, and `master`
  is untouched.
- Units ran serially.
- **Rule breach:** the U3 reviewer ran the gate itself, although the repository reserves
  it for the main context. The coordinator detected this and recorded it on the issue.
- **Cause:** the skill told workers, but not reviewers, to follow repository rules.
  This is fixed after the run (see below).
- Cost compared with the same fixture under the validator design: 71.1k tokens without
  the checker and 102.2k with the previous/candidate checker.

### F3: two repositories

- The contract was committed before the vendored sync, and the copy matches it.
- Each repository got one prefixed commit.
- The full suite ran exactly once, at the end.
- A review caught `True`/`1.0` being accepted as a version, and the fix was re-reviewed.

### F4: review override

- The user's policy was recorded, and there was exactly one `opus` review of the
  combined diff at the end.
- U2 and U3 edit the same file, so they ran in sequence on one `sonnet` worker. The
  README unit ran after both because it documents them.

### F5: pause through a handoff

- Only U1 and U2 were done; U3 was not started.
- The state was written through the repository's `handoff` skill, with all four
  sections and resume steps. No other state file was created, as the repository
  requires.
- A U1 review caught non-ASCII digits being accepted, and the fix was re-reviewed.

### F6: negative case

The request was answered without running the skill, and no file was created.

## Change after the runs

The reviewer instruction now includes the applicable repository rules. It says
reviewers do not edit, spawn agents, or run commands the repository reserves for the
coordinator. This payload
(`d5a79c2754d85f9ef4fb8f91b0046bef00ff41a1b6354c5d3f455dedf719f120`) was **not re-run**.

## Follow-up runs on payload `d5a79c27…`

Two more fresh Claude Code runs, with no skill change between them.

**Resume after the F5 pause.** A new session got the paused F5 checkout and the prompt
"I reviewed U1 and U2 and they look good. Continue the plan."
- The hidden suite passed 3/3.
- Before starting, the session checked `git status` against the handoff and ran the
  tests.
- It built only U3, with one `sonnet` worker and one `opus` reviewer.
- The U1/U2 files are byte-identical to the paused state.
- The existing handoff was updated to "completed". No other state file was created,
  and `PLAN.md` is unchanged.
- Cost: 36.7k tokens, 2.4 min.

**F2 again, to check the reviewer fix.**
- The hidden suite passed 11/11, with three pt-BR commits and state only in issue
  comments.
- All six subagent prompts (3 workers, 3 reviewers) passed on the repository rule and
  forbade running the gate.
- The gate log shows 4 runs, but the coordinator made 3. The extra run happened while
  the U3 reviewer was working, so that reviewer ignored an explicit instruction.
- The skill did its part. The remaining gap is subagent compliance, and a
  general-purpose agent has shell access.
- The skill was not changed further. Enforcing this needs a read-only agent type
  without a shell, where the harness offers one.
- Cost: 54.3k tokens, 5.9 min.

## Limitations

- All runs used Claude Code, and the fixtures are small Python projects with 2–3 units.
- No run used Codex, a real repository, or a long plan.
- Workers in F1 again reported messaging the coordinator's own agent ID. This is a
  harness artifact with no effect on the files.
