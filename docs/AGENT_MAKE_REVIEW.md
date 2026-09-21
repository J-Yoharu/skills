> Historical review of the preceding archive. Superseded by [current verification](VERIFICATION.md).

# Agent instructions and Make integration review

Date: 2026-09-21
Input: `agent-skills-orchestrar-pnpm-reviewed.zip`
Scope: shared Codex/Claude Code instructions, Make entry points, command integration,
documentation, and regression coverage. This is a separate self-review pass by the
same assistant, not a second-model review or native agent execution.

## Delivered design

`AGENTS.md` is the shared policy. `CLAUDE.md` is a native `@AGENTS.md` import and a
short maintenance comment, not duplicated prose or a symlink. The rules cover
capability discovery/reuse, English maintained content, product boundaries, honest
evidence, focused changes, review expectations, versioning, and authorization.
No global agent settings, automatic hooks, broad permissions, or model dependencies
were introduced. See `docs/AGENT_WORKFLOW.md` for authorized native-session checks.

`Makefile` is the public task menu. Help is extracted from the recipes, and bare
`make` is read-only help. Make delegates to the existing pinned pnpm aliases; aliases
call the Node launcher and Python engine. pnpm never invokes Make. There is no second
validator implementation, no raw shell ARGS parameter, and no per-skill Makefile.

Workflows now use the same Make task entry points. GitHub event orchestration, action
setup, permissions, and stable gate logic stay in YAML. The identity comparison that
was embedded in release YAML now has a local, tested command. Optional reference
installation is explicit and uses the same environment lock as ordinary bootstrap.

## Review findings and corrections

| Finding | Resolution and evidence |
| --- | --- |
| The original Claude entry point only linked to the shared instructions. | Replaced by native import; structural tests verify the import, plain file, and lack of duplicated policy. Native session loading remains untested. |
| The Node launcher ran a hard-coded test file. | Added regular-file discovery for all `tests/launchers/*.test.mjs`. A temporary future test is actually executed to verify discovery. |
| Make argument handling could regress quoting or command routing. | Real GNU Make tests use an explicit fake pnpm executable, including paths with spaces, punctuation, untrusted environment PR titles, shard zero, and workflow environment fallbacks. |
| Parallel setup and failed installation could cause unsafe sequencing. | Setup calls install then bootstrap; top-level tasks are serialized. A failure prevents the next step. Bootstrap operations share a lock. |
| A release facade could publish accidentally. | Bare Make only shows help. Publication requires a tag and exact `CONFIRM_PUBLISH=yes`. Remote code retains the original verification and opt-in workflow gates. |
| Workflow command migration could drop shard/base/head values. | Workflow contracts and routing tests verify the values still reach the same underlying CLI. |
| Shared policy and Make changes were not in selective-CI inputs. | They now select all skill isolation shards, while unrelated documentation remains selective. |
| Instructions and public documentation could diverge. | README, setup, contributing, operations, the generated catalog, and PR guidance now point to Make and the canonical policy. Direct pnpm aliases remain documented. |

The additional dependency-bootstrap and local-identity commands are maintenance
operations only. No skill runtime, external installer implementation, release strategy,
or dependency pin was changed. Scope-related fixtures were updated to assert the new
routing rather than requiring old YAML command strings.

## Executed checks

The complete launcher entry `node scripts/run.mjs check` passed with **72 Node tests
and 149 Python tests: 221 total, zero failures and zero skips**. This includes actual
GNU Make routing tests with a fake pnpm child process, repository validation, copied
Orchestrar payload checks, and preview packaging. The draft has no runtime scripts,
so its copied-payload check reports zero runtime smoke executions and zero active
skills packaged. Unit fixtures exercise active skills; that is not a live evaluation
of Orchestrar.

Bare `make` / `make help` and a dependency consistency check were also executed.
The review venv was seeded offline with the seven exact already-installed requirement
versions, without importing unrelated host application packages. `pip check` passed.
This is not evidence of a clean online bootstrap or a network package installation.

The final archive is checked again after extraction into a different directory. Its
result is recorded in `docs/agent-make-verification.json`, with command output in
`docs/agent-make-verification.log`. These are current results; the earlier pnpm-review
logs remain historical rather than being presented as new executions.

## Preservation checks

Sixteen key files were compared byte-for-byte against the input archive and stayed
identical: every file under `skills/orchestrar/`, its operational and evaluation records,
the repository identity/settings, catalog version and release manifests/configuration,
Python requirement files, and pnpm lockfile. Their SHA-256 values are in the current
verification JSON. The reserved `orchestrar` slug, draft lifecycle, version `0.0.0`,
and pending review evidence remain unchanged. No remote resources were created.

## Not executed and limitations

There was no usable pnpm binary or package-network access in this runtime. No genuine
`pnpm install --frozen-lockfile`, complete Make-to-real-pnpm setup, or online bootstrap
was executed. The routing boundary is tested with a fake child, while the real Node
launcher/Python engine is tested directly. Do not equate those with a native pnpm run.

Codex and Claude Code sessions, hosted GitHub Actions, Release Please, real publication,
external interoperability tools, and native Windows/macOS runs were not executed.
GNU Make 4.4.1 on Linux was exercised; older supported Make behavior is not a tested
platform matrix. The Make confirmation guard is accident prevention, not authorization,
an OS sandbox, or a substitute for existing agent permissions.
