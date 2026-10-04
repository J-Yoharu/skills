# CI/CD and GitHub Free

## Account context and scope

The intended repository is `J-Yoharu/skills`, public at the integration review.
GitHub documents free standard hosted-runner usage for public repositories. The
2,000-minute GitHub Free allowance applies to private-repository hosted usage, not
a universal public-repository cap. Larger runners have separate charges. Artifact
and cache usage have separate accounting; no account-wide zero-cost guarantee is made.

Sources checked on 2026-09-21:
- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Workflow triggering and required checks](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)
- [Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)

## Implemented CI choices

One standard `ubuntu-latest` job exposes the stable required check `gate`. It runs on
PRs to the repository and main pushes, with cancellation of obsolete runs. PRs do not
also trigger a branch-push CI run; the merged main snapshot still receives its own check.
A 15-minute timeout caps a stuck CI job, not total account usage.

Python dependencies use a pip download/wheel cache keyed by pinned requirements.
Each job creates its own venv; untrusted virtualenvs are not restored from a shared cache.
No pnpm installation, npm dependency installation, artifact upload, paid API call,
external LLM evaluation, service container, or larger runner is used in routine CI.

The workflow always starts and validates all repository/docs contracts. It skips
expensive regression steps based on an internal Git diff, rather than `paths-ignore`
for the required workflow: GitHub warns that path-filtered required checks can remain
pending. Root maintenance changes run all deterministic suites; a skill-only change
runs that skill's suite and copied checks; ordinary docs-only changes run validation
and PR intent checks. Unknown history falls back to full coverage.

No success-only upload/retention job is configured; GitHub logs and summaries carry
routine results. Review account budgets, log retention, and cache limits in GitHub
settings before enabling additional services. CI does not change account settings;
release enablement and PR-creation permissions are maintainer-controlled live settings.

## Releases and interoperability

Both are manual `workflow_dispatch` workflows, gated by their repository variables.
`RELEASES_ENABLED` was enabled for the `v0.1.0` release; verify its live value before
future runs. There is no release preflight on every push and no weekly interop
schedule. Release has one job and a 20-minute timeout. It validates the requested
snapshot once and reuses that evidence only if the released tag has the exact same SHA;
a different SHA stops publication and requires a fresh dispatch against that tag.

`RELEASES_ENABLED=true` and an active evaluated skill are required. The native
`GITHUB_TOKEN` also needs GitHub's **Allow GitHub Actions to create and approve pull
requests** repository setting to open Release Please PRs. PRs created with that token
do not automatically trigger GitHub Actions workflows; validate their exact head
separately, or use an authorized scoped `RELEASE_PLEASE_TOKEN`. Release artifacts
are published in the same explicit run; no recursive push/release workflow trigger
is required. See the [release runbook](VERSIONING.md#release-runbook).

The first manual run opens a release PR; merge it only after valid checks/review,
then dispatch again to create the release. Asset repair uses `release_tag` and the
existing immutable snapshot. Nothing is deployed to an application environment.

Dependabot version updates are monthly and grouped, with one open PR per ecosystem.
This reduces routine update noise; it is not a reason to defer urgent security fixes.

## Scaling without premature infrastructure

The single-job default eliminates repeated bootstrap/checkouts for a small catalog.
Affected-suite selection still helps as the catalog grows. Compact shard helpers are
retained for an explicitly reviewed matrix later. Measure runtime and confidence before
adding workers, cache layers, automatic release schedules, or per-skill workflows.
