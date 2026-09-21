# Native Make, Orquestrar, and CI/CD integration review

Repository: `J-Yoharu/skills`. Review date: 2026-09-21.
Method: a separate self-review pass with executable regression coverage. No second
agent, hosted run, native-agent session, or remote mutation is claimed.

## Decisions and verified changes

### Make is the command hub, not a pnpm proxy

The old Makefile forwarded maintenance operations through pnpm. Python tasks now
invoke the selected Python interpreter directly; Node tests invoke Node directly.
Only the optional JavaScript dependency-install task invokes pnpm. The Makefile
contains orchestration/argument guards, not duplicate validator implementations.

A stdlib-only `scripts/bootstrap.py` is shared by Make and the optional Node/pnpm
launcher. The duplicated bootstrap implementation was removed. `make setup` no
longer forces a JavaScript installation before Python tooling. Explicit version,
lock, failure propagation, and reference-dependency behavior are regression-tested.

The real full Make gate passed with pnpm deliberately unavailable. Recording mocks
are used only for isolated routing/error tests, not as evidence of real operations.

### Incoming skill becomes a genuine, unapproved candidate

The supplied `orquestrar` identifier replaces the empty `orchestrar` placeholder.
All 36 non-entrypoint product files were preserved byte-for-byte; this includes
all three Python helpers. The SKILL instruction body is unchanged. The frontmatter
editing version is replaced by bootstrap `0.0.0`; redundant Claude default-false
metadata is omitted for the portable format. No final version is inferred.

Five test modules moved to `tests/skills/orquestrar`, with test paths adapted to
`SKILL.md.template` while supporting future activation. All 152 deterministic tests
pass. The 58 scenario specifications remain byte-identical and unexecuted. Explicit
Portuguese CLI identifiers and multilingual fixtures are compatibility data, not
untranslated maintenance instructions. No historical source report was imported
as current evaluation proof. Existing MIT attribution is retained for owner review.

A local `make skill-preview` command materializes SKILL.md in disposable output
without activating, approving, or versioning the tracked candidate. Runtime payloads
do not acquire root validators, tests, evidence, or repository agent policies.

### CI/CD respects cost and maintenance overhead

Routine CI has one standard Linux job instead of separate plan/validate/isolate/gate
job definitions. It creates one Python environment, caches pip downloads, avoids pnpm
installation and routine artifact uploads, and cancels obsolete runs. The required
check stays present: validation always runs; expensive suites are selected inside
that workflow, not suppressed by whole-workflow path filters.

Skill-only diffs run the affected suite and smoke tests. Shared operational changes
run all suites. Missing history selects everything. Ordinary docs-only changes run
structural/documentation checks and PR intent checks. Main checks are retained after
merges; duplicate feature-branch push checks are not configured. Compact shard helpers
remain available, but no premature hosted matrix is enabled.

Release and external interoperability are manual and opt-in. Release preflight does
not repeat on every push. There is one release job; test evidence may be reused only
for the exact tested commit. A different tag SHA stops publication. Release Please
uses the native token with an optional scoped override; current GitHub PR-run approval
requirements are documented. No recursive push/release trigger is needed. Dependabot
version updates are monthly/grouped, not a reason to delay security fixes.

The repository was read as public. GitHub documents free standard hosted-runner
usage for public repositories, while private quotas, larger runners, and storage
are separate concerns. This is not an account-wide billing guarantee; settings and
budgets were not changed. See [primary sources and limits](CI_CD.md).

## Review findings addressed

| Finding | Resolution/evidence |
| --- | --- |
| Make only proxied pnpm | Direct native recipes; real Make gate without pnpm; updated routing tests. |
| Bootstrap logic would otherwise diverge | One stdlib bootstrap shared by both command interfaces. |
| Source editing label could be mistaken for a release | Draft lifecycle, bootstrap version, pending proof, no active release component. |
| New skill unit modules were outside maintenance discovery | Independent per-skill suite discovery; real synthetic success/failure tests. |
| Empty affected selection could accidentally mean all | Empty-list selection is explicit and tested separately from default discovery. |
| Preview replacement could delete unowned local output | Ownership guards and symlink rejection; regression tests preserve user files. |
| Preview could prevent a subsequent normal build | Shared generated-output ownership; preview-to-build regression. |
| Old regressions enforced obsolete pnpm/matrix design | Replaced with native-runtime, single-gate, same-ref scope contracts. |
| Release work repeated automatically | Manual opt-in workflow and exact-commit evidence guard. |
| Historical logs could be rewritten during name normalization | Historical evidence restored; clearly marked superseded, not re-attributed. |

## Evidence and remaining work

[Verification](VERIFICATION.md) records 404 passing deterministic tests and eight copied
smoke executions, with commands, logs, environment, and a second full passing run in an extracted
directory with spaces and no .git or .venv. Only verification evidence was appended
after that run; executable code and configuration are unchanged.
The attempted clean bootstrap stopped on network DNS failure; no successful online
installation is claimed. Hosted workflows and Release Please still require the
owner's first real run. No actual skill behavioral scenario has been executed.

Before activation, use the local preview in authorized Codex/Claude projects, collect
real scenario traces, resolve failures, record current evidence and fingerprint,
and review the license. Do not replace pending evidence with this maintenance report.
