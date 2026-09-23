# Orquestrar self-review: real-repository traits (2026-09-23)

This is a **self-review**, not an approval. `review.status` stays `pending`.

## Payload and method

- Payload: `0e6b08fb5076946075d2dd546b7e8ea809abf4949bc96afca1961b5bfb756e56`.
  This payload is after removing the unused resolver mode, the native presets, and the
  unreferenced example assets. It also restores the frontier-family `opt_in` gate.
- The global `~/.claude/skills/orquestrar` install was absent, so no global core could
  contaminate the runs.
- Traits came from read-only mapping of two local repositories: a multi-repo monorepo
  with strict agent rules, and a Vite frontend with no agent instruction file. Nothing
  was executed in those repositories, no secret files were opened, and no content was
  copied. The skill was not changed to fit either one.
- Three synthetic Python fixtures reproduce the traits. Each has an approved 2–3 unit
  plan and a hidden test suite kept outside the fixture.
  - The payload came from `make skill-preview` and was copied to
    `<fixture>/.claude/skills/orquestrar`.
  - Each run used a fresh `general-purpose` subagent. It got only the working directory,
    a note that the project skill must be read from its `SKILL.md`, and the canonical
    `implementation-request` prompt invoked as `/orquestrar`.
  - Results below were re-checked on disk: hidden suites, `git log`/`status`, strict
    checkpoint reads, and the fixtures' own logs. Coordinator transcripts were only
    grepped for counts.
- Evidence: `~/orquestrar-evals/real-traits-claude-20260923-selfreview/`
  (`f1`, `f2`, `f3`, `frozen-before.tgz`, `*/hidden/test_hidden.py`).

## F1: no agent instructions, pt-BR conventions

**Traits.** There is no `AGENTS.md`/`CLAUDE.md`. Rules live in `README.md`,
`CONTRIBUTING.md`, a PR template, and a deploy-on-push CI workflow. The test command
alone is not the gate: `make check` adds an offline-first build check that rejects
network imports. User-facing messages must be pt-BR. `.orquestrar/` is not ignored, and
CONTRIBUTING forbids unrelated or tool-generated files.

**Result.** The hidden suite passed 10/10.
- It found `make check` as the verification command and recorded it in a profile whose
  sources include CONTRIBUTING, the Makefile, and the CI workflow.
- U1 and U2 ran in parallel with disjoint files, and U3 ran after both. All three used
  `sonnet` workers with `opus` reviewers.
- The U3 review found real defects: English OS/JSON error text leaking into
  `erro: ...`, tracebacks on wrong field types, and loose date parsing. They were fixed
  and re-reviewed.
- There was no commit or push, and the final report cites the push-to-production risk.
- `.orquestrar/` was left untracked and flagged to the user. It was not added to
  `.gitignore`, which would have been an unrelated change.
- The strict checkpoint read reports `completed`, with 3 units `integrated`.
- Coordinator cost: 84.6k tokens, 34 tool calls, 9.5 min.

## F2: monorepo with strict state, gate, and git rules

**Traits.**
- Root `CLAUDE.md` plus nested `api/AGENTS.md` and `web/AGENTS.md`.
- The plan lives only in a tracker issue, reached through `scripts/issue show 12`.
- Execution state in repository files is forbidden (state goes in issue comments).
- The canonical gate is `scripts/quality-gate` (exit 2 = unverified, never green), and it
  must run in the main context. Subproject commands must not run directly.
- One commit per unit on a branch from `scripts/issue link`, never on `master`, with pt-BR
  messages ending in `Refs #12`.
- Depth-1 delegation, and no parallel writers.

**Result.** The hidden suite passed 11/11. One initial failure was a wrong expected
value in the hidden suite itself, not an agent defect.
- No `.orquestrar/` or other state file was created. Progress went as 11 issue comments
  with unit status, agent IDs, gate results, and commits.
- The gate ran 5 times, and all 5 were from the coordinator (the gate log matches the
  transcript count). Workers did not run it.
- Three commits landed on `feat/12-cupons-no-checkout`, `master` is untouched, and every
  message is pt-BR with `Refs #12`.
- Units ran serially. The nested rules were respected: `ApiError`, no `float`,
  `group_thousands` reused, and `api` does not import `web`.
- One review cycle caught Portuguese identifiers.
- Coordinator cost: 71.1k tokens, 32 tool calls, 6.8 min.

**Observation.** With a project-native state location, the bundled
`checkpoint-save` validator was not used. Its structural locks (worker required,
reviewer required, dependency order) therefore did not apply. The behavior still
matched them in this run, but that was not enforced.

## F3: two repositories with a contract dependency and a slow suite

**Traits.** A provider repository (`contract`) and a consumer repository (`billing`)
that vendors the provider's **committed** `HEAD` through a sync script. Contract changes
are additive with a changelog entry. Each repository requires a commit per unit with a
fixed prefix. The full suite takes about 2 minutes and must run once, right before
delivery; `make test-fast` is for development.

**Result.** The hidden suite passed 7/7.
- U1 was committed in `contract` before the sync, and the vendored copy is
  byte-identical to that commit.
- Both repositories got one prefixed commit each and have clean trees.
- The full suite ran exactly once (fixture log), and `make test-fast` ran during
  development.
- The coordinator explained why it committed: the skill's default treats invocation as
  no commit authorization, but both repository rules require a commit per unit.
- The checkpoint sits at the workspace root, outside both repositories. The strict read
  reports `completed`, with 2 units `delivered`.
- Coordinator cost: 63.7k tokens, 22 tool calls, 7.0 min.

## Summary

In all three fixtures the skill followed the repository's own rules over its defaults:
- it found the real gate;
- it used project-native state when files were forbidden;
- it followed the commit, branch, and language rules;
- it kept the gate in the main context when required;
- it ran the slow suite once;
- it ordered cross-repository dependencies correctly.

Every product unit was delegated and independently reviewed. No generic skill defect
was found, so the skill was not changed.

Open points (not fixed; they need a design decision):
- The state lock depends on `checkpoint-save`. It has no equivalent when a project
  forbids state files (F2).
- A repository that does not ignore `.orquestrar/` gets untracked state. The skill only
  reports it (F1).
- A worker's final report named a wrong agent ID, which the coordinator caught and
  recorded as a harness or worker mislabel (F1).
