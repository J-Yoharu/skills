# Review and quality evidence

## Verification plan

Discover canonical commands in instructions, scripts, and CI. For each acceptance
criterion, identify evidence that distinguishes correct implementation from a
wrong one. Reuse existing tests/fixtures; avoid tests that merely confirm mocks
without exercising behavior. For a reproducible bug, try to observe failure
before the fix and success afterward; disclose when reproduction is unavailable.

Separate quick edit checks, affected-behavior tests, combined-candidate integration,
and publication-specific gates. These are semantic categories: a project may call
everything `test`, `gate`, or `check`, or rely on remote CI.

Passing lint does not cover an untested criterion. `not_applicable` requires a
reason; `unverified` requires cause and necessary action. An unavailable mandatory
check prevents declaring delivery ready, even when the code looks correct.

## Risk-based review

A review explicitly covers both:
1. Compliance: complete acceptance criteria, invariants, contracts, and exclusions.
2. Engineering: correctness, regressions, boundaries, concurrency, security,
   meaningful tests, and absence of duplicated capabilities.

Use disclosed self-review only for small nonbehavioral changes when policy allows.
Require independent context for product rules, public APIs/events, databases/data,
authorization, concurrency, multi-repository integration, or when DoD requires it.
Add another reviewer only for a distinct specialist risk; voting and agent counts
are not proof.

The reviewer receives requirements, base/candidate, scope, and test references.
It reads the full scoped diff and necessary code. Treat the implementer's report
as a hypothesis, not a conclusion. Restrict writes and delegation through tools
and permissions where supported; a sentence in a prompt is not access control.

A finding includes file/line, reproduction condition, consequence, evidence, and
affected criterion. Classify blocking/nonblocking without severity inflation.
Validate findings in code; do not dismiss a defect because the plan omitted its
fix. After material corrections, review the change and rerun affected tests.
Contract changes also reopen acceptance review; rereading changed lines is insufficient.

## Evidence identity

Reusable evidence records:
- Repositories/checkouts, HEAD/base, file content, and relevant index state.
- Command/arguments, working directory, toolchain/image/lockfiles, and relevant environment.
- Requirement revisions, dependency contracts, and covered acceptance criteria.
- Time, exit code, per-step outcome, logs/artifacts, and executor.

Compare content **before and after** execution to detect concurrent changes.
Tests that generate code or update snapshots must stabilize first; verify the
final result. Do not accept a tree still being edited by another agent.

`git status --short`, line counts, and `diff --stat` can remain unchanged after a
behavioral change. They are not fingerprints. Prefer native project evidence tied
to the exact artifact. Otherwise, this skill's helper hashes tracked and nonignored
untracked files, HEAD, and index using SHA-256.

Store output **outside the captured files**, outside the checkout or under
`<git-common-dir>/orquestrar/`:

```bash
python3 <skill>/scripts/verify.py snapshot --repo <checkout> --context <run>/verification-context.json --out <run>/before.json
# Run the authorized canonical test command and capture its actual outcome here.
python3 <skill>/scripts/verify.py compare --repo <checkout> --context <run>/verification-context.json --snapshot <run>/before.json
```

`verification-context.json` contains nonsecret metadata: command, source IDs and
revisions, tool versions/test image, dataset, and dependencies. Example:
`{"command":["npm","test"],"requirements_revision":"r3","runtime":"node-22","dataset":"fixture-v1"}`.
The helper compares the file; it **does not discover or attest** the actual
environment. Update metadata from observation, never to force equality.

Limits: the helper does not cover ignored files, credentials, databases, clocks,
remote services, processes, or transient edit history. It does not follow symlinks;
it compares target text. If a gate depends on linked content, capture the authorized
target separately or do not reuse evidence. Nested repositories/submodules need
their own snapshots; the helper fails explicitly on them. Matching snapshots do
not replace isolation during execution. SHA-256 detects change, not a report's author.

Inspect actual logs/reports and map steps to criteria. If any material input is
unknown, do not certify reuse; run verification in the correct environment or
record `unverified`. Do not repeat an expensive gate merely because another person
reads the report. If delivery policy requires a new run, comply.

## Baselines and regressions

A claimed pre-existing failure must reproduce on the correct base under comparable
conditions and safe isolation. A familiar error message alone does not prove an
environment problem. Workarounds are valid only if they do not hide tested behavior.

After integration, rebase, or merge, verify the combined candidate. After commits
with hooks, check for content changes; material changes invalidate evidence.
Remote CI must match the correct SHA, not the latest green job with a similar name.
A gate accessing staging/production is not authorized merely because it is named
"test". Before migrations, seeds, resets, or data-writing tests, confirm the actual
target, disposability, and authorization without printing credentials. A local-looking
hostname is insufficient: a tunnel may target a real database. Unknown or
nondisposable targets require specific permission; stop before changing data.
Generating migration files does not authorize applying them.

## Compact results without lost evidence

Summarize unit, files, contract decisions, checks/results, review, and gaps. Keep
logs, long lists, and findings in referenced checkpoint artifacts. Never omit a
risk or requirement to meet a line limit. Telegraphic style is optional; complete
contracts and accurate evidence are not.
