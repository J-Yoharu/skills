# Orquestrar Git and no-Git adaptation evaluation — 2026-10-02

Status: controlled Codex subagent self-evaluation, **pending human review**.
This report supplements the earlier evaluation on the previous payload. It
does not establish Claude Code behavior or approve the distributed skill.

## Payload and fixtures

- Payload fingerprint:
  `eaf3952bfec3071b681ee23d01b11addf7dd143e68dc5d512afb44f32744636a`.
- The older global Orquestrar installation was moved out of discovery before
  either run. Each fixture received an exact copied payload; `diff -qr` found
  no differences from the source. The original global installation was
  restored once after evaluation; the new unapproved payload was not installed.
- Both fixtures were disposable and synthetic under
  `/tmp/orquestrar-adapt-eval-3PGiGO/`. No credentials or network were used.
- Baseline `make check` failed on the deliberate `NotImplementedError`
  skeletons in both fixtures.

## Git project with a local issue

The fixture was initialized as a local Git repository on `main`, with
`ISSUES.md` as its project-owned progress record and no remote. Its approved
plan specified U1 quantity parsing, U2 label normalization, and U3 integration
into a formatted line. The coordinator created `feature/local-report`.
Distinct workers handled U1 and U2; agent capacity forced sequential dispatch,
so this run is **not** evidence of parallel execution. The dependent U3 began
only after U1 and U2 were accepted.

An independent reviewer examined U1/U2 and then U3. The coordinator made one
local commit per accepted unit, updating `ISSUES.md` in each:
`0af2a8c` (U1), `29a1777` (U2), and `a2c7cdb` (U3). No PR, remote issue,
push, or competing `.orquestrar` record was created. The final Git worktree
was clean. Focused tests passed 2/2, 4/4, and 2/2; integrated `make check`
passed 8/8. An independent hidden checker verified behavior, branch, commits,
tracker completion, absence of remotes, and clean status.

The Git run did not demonstrate every field requested by the skill's progress
guidance: ISSUES.md omitted explicit unit owners and dependencies, checkout and
delivery metadata, and active-agent status. PLAN.md and Git history provide
some of those facts, but the hidden checker did not grade their recovery. Count
this as successful Git workflow routing with a progress-record limitation, not
full conformance to the state contract.

## Project without Git or a tracker

The second approved plan specified U1 port parsing, U2 service-name
normalization, and U3 endpoint integration. It contained no `.git` directory
or tracker. Distinct workers handled the units; the same agent-capacity limit
forced sequential dispatch. The coordinator kept one local
`.orquestrar/endpoint-formatter.md` current-state record and did not initialize
Git.

The independent reviewer found a real U1 blocker: valid port strings with
thousands of leading zeros exceeded Python's integer conversion limit. The
same worker corrected it, added regression coverage, and a focused second
review found no remaining issue. U2 and U3 passed review. Focused tests passed
4/4, 4/4, and 3/3; integrated `make check` passed 11/11. An independent
hidden checker verified edge behavior, absence of Git, and the local 3-of-3
progress record.

## Boundaries and maintenance checks

This pair of runs confirms adaptation to local Git plus an existing tracker
and to a project without either. It does not test GitHub integration,
multi-repository delivery, a third review after two failed passes, large
finding lists, or the effective reasoning effort of subagents. The previous
payload's pause, unsafe-gate, and resume evidence remains historical and is
not silently attributed to this fingerprint.

An independent read-only final review found no new defect in the skill text;
it identified the Git progress-record limitation described above.
`make test-skills NAME=orquestrar`, `make test`, JSON parsing, and
`git diff --check` passed after the content update. `make check` and
`make isolate` stopped before
their later stages with `record an approved human evaluation with concrete
evidence before activation.` The active catalog requires human approval for
the new payload. No review status or digest was fabricated.
