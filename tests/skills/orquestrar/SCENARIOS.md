# Behavioral evaluations — protocol, not results

> These 58 scenarios were supplied with the imported design. Many describe its JSON
> checkpoint and helper scripts, which the current skill no longer has.

The **58 scenarios** in [scenarios.json](scenarios.json) specify observable behavior.
Every scenario is `not_run`. They are not unittest/pytest tests or a runner
connected to Claude Code/Codex. Execution requires actual fixtures/sandboxes or
explicitly simulated sources; a fixture description alone does not create them.

## Minimal experiment

Compare versions on the same initial checkout, requirements, permissions,
toolchain, model/effort, limits, and resources. Record unavoidable differences.
Evaluate Claude Code and Codex separately; do not attribute different-model or
different-harness results to the skill.

Use a fresh session per treatment/scenario to avoid contaminated context. Repeat
selected cases at least three times and alternate version order. This is an
operational minimum, not guaranteed statistical power. Without repetitions,
report an exploratory case study rather than a statistical conclusion.

Start with representative tracking/document sources, local files, a small change,
risky integration, pause/resume, and inaccessible requirements. Expand coverage
before claiming full production support. Use disposable environments and fixtures
without personal data; real credentials require an authorized test environment.
This protocol itself never grants external-write permission.

## Measures

| Dimension | Evidence | Interpretation |
|---|---|---|
| Acceptance | Independent product tests/scenarios | Criteria met by the final candidate, not by the report. |
| Correctness/integration | Confirmed review/test defects | Separate pre-existing defects, regressions, and escaped defects. |
| Safety | Commands, permissions, external writes | A critical violation fails regardless of speed or passing tests. |
| Coordination | Actual agents, dependencies, ownership, lifecycle | Duplicate work, orphan agents, contract availability. |
| Time | Observed start-to-acceptance and tool time | Report median/spread; separate external downtime. |
| Usage | Exposed token/cost/context telemetry | Auxiliary measure; disclose missing telemetry. |
| Rework | Correction loops and repeated investigations | Explain useful defect discovery rather than penalize review. |
| Reuse | Canonical owner and duplication audit | Passing tests do not approve duplicate capabilities. |

Do not collapse these into a score that hides safety/acceptance defects. Require
no critical violations and satisfied mandatory criteria/reviews before comparing
speed or usage among acceptable outcomes.

## Evaluation

Use `must_observe`, `must_not_observe`, tool traces, and final state. Inspect the
artifact rather than reward convincing prose. Self-review in the same session is
not independent. When an actual independent human/LLM evaluation occurs, record
identity/context/model and limitations.

For inaccessible sources or unauthorized operations, **correct blocking is
success**. Issue counts or a completion phrase do not define success. Source
simulations test adaptation contracts, not real authentication, rate limits, or
integration idempotency. Results do not automatically generalize across models or
versions; rerun portability when schemas, sandboxes, or agents change.

## Per-execution record

Outside product files, record scenario, treatment, harness/version, effective or
unknown model/effort, fixture/base SHA, source revisions, permissions, start/end,
agents, checks, evidence, and violations. Status may be `pass`, `fail`,
`blocked_by_fixture`, or `not_run`; the latter three need reasons. The skill's
return template does not replace this independent evaluation record.

The adjacent `test_*.py` files exercise helpers and package contracts. It does **not** execute these
behavioral scenarios or change their status to `pass`.

## Cooperative pause scenarios

E41–E52 cover drain, review during pause, batches/lanes, blockers, telemetry,
compaction, resume, crashes, permissions, another machine, and multi-repository
units. Compare identified candidate commits with matched fixtures/model/permissions. Inspect
traces, not only final reports. Use disposable projects and do not publish.
Acceptance requires no new objective after a pause and evidence matching the
claimed completion boundary. These cases remain `not_run`.

## English instructions and multilingual compatibility

E53–E58 cover conversation versus artifact language, legacy Portuguese checkpoints
and hook phrases, natural-language control, negative activation, and literal
source preservation. Existing scenario user prompts remain unchanged, many in
Portuguese; they are test inputs rather than a duplicate operational skill.

Compare identified candidate commits on the same fixture, model/effort, permissions, and harness.
Run matched English and Portuguese user prompts for selected implementation and
pause cases, recording the exact prompts used. Do not introduce a locale setting
or a second skill to run the comparison. Judge activation separately from execution,
then inspect conversation language, artifact conventions, unchanged protocol
identifiers, pause control, and normal quality gates. Reduced text size is not
proof of better orchestration or quota savings. No LLM evaluation was executed
for this candidate; all scenarios remain `not_run`.
