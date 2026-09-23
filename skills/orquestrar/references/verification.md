# Review and quality evidence

The ordinary gate/review policy is in `SKILL.md`. Read **Changed evidence** when a
failure or finding needs interpretation. This file is not a mandatory preflight read.

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

Choose the reviewer separately from the implementer; neither a worker nor a
coordinator adjustment approves its own behavioral change. New or
changed behavior requires an independent context even for a small isolated helper.
Use disclosed self-review only for small nonbehavioral changes when policy allows.
Product rules, public APIs/events, databases/data, authorization, concurrency,
multi-repository integration and a DoD requiring independence also require it.
Without the required review, keep acceptance pending rather than mark delivered.
Add another reviewer only for a distinct specialist risk; voting and agent counts
are not proof.

Decide whether independent review is required while planning the unit, and check
whether the session can provide it. Lack of that capability must be surfaced
before coding, not after repeated configuration attempts. Useful authorized work
may proceed, but cannot pass the missing gate.

The reviewer receives requirements, base/candidate, scope, and test references.
It reads the full scoped diff and necessary code. Treat the implementer's report
as a hypothesis, not a conclusion. Restrict writes and delegation through tools
and permissions where supported; a sentence in a prompt is not access control.

A finding includes file/line, reproduction condition, consequence, evidence, and
affected criterion. Classify blocking/nonblocking without severity inflation.
Validate findings in code; do not dismiss a defect because the plan omitted its
fix. After material corrections, review the change and rerun affected tests.
Contract changes also reopen acceptance review; rereading changed lines is insufficient.

## Evidence

Evidence is what a reviewer or a resumed session needs to trust a result: the
canonical command, where it ran, its actual outcome, and which criteria it covers.
Prefer the project's own reports and CI on the correct commit. Do not invent or
silently change the project's test command; disclose any substitution and why.

## Changed evidence

Inspect the actual diff/changed paths before selecting a response. A product, rule,
contract, dependency, command or material environment change invalidates affected
proof. A mandatory new gate or material review finding also requires verification.
A report-only change does not.

After a valid check and resolved review, accept the unit. No rerun for a read-only
reviewer, checkpoint write, final summary or different person reading evidence,
unless a real input changed or policy demands it. Flaky output needs diagnosis or an
explicit unverified result, not a retry loop.

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

## Completion is observable

A finished implementation must produce a final result or a concrete blocked
handoff, not remain in optional profile/routing maintenance. Record code, test,
review and delivery outcomes separately. A rejected optional cache does not
invalidate an independent review or a product test by itself; a material source
or content change does. Conversely, passing tests do not make missing review
complete. Fix environment commands from documented evidence; an unavailable
`python` is not evidence that product code failed if the declared runtime is
`python3`. Disclose any command substitution and its basis.

## Persistence is a different proof

A `checkpoint-save` receipt confirms validated declared state and exact read-back.
It does not attest tests, requirements, independence or delivery. Use `plan` for
graph/control diagnostics and `checkpoint-read` for the durable contract, not
`json.tool` or an unconditional success string. If the record is invalid, preserve
it and use the reconciliation procedure rather than weakening the validator.
A gate can pass while a save fails: keep the gate evidence, freeze dispatch and
report the unpersisted delta. Never rerun product tests to repair a state file.
