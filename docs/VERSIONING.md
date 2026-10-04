# Versioning and releases

## Independent products, aggregate snapshot

Each active skill has its own SemVer (`MAJOR.MINOR.PATCH`). A catalog release identifies
one repository snapshot containing those independent versions. For example, catalog
`v2.3.0` can include `orquestrar` `1.4.1` and another skill `2.0.0`. An unchanged skill
does not need the same version as its neighbors or the catalog.

`version.txt`, `metadata.version` in `SKILL.md`, the release manifest, and the changelog
must agree. Release Please owns the synchronized updates after the initial `0.0.0`
bootstrap. The committed manifest is operational state; do not reset it to resolve a conflict.
`metadata.version` is an extensible metadata convention, not installer version resolution.

A combined Release Please PR updates changed components. Only the catalog creates a
GitHub Release; components use `skip-github-release: true`. The asset publisher creates
immutable component tags such as `orquestrar-v1.4.1` after verification, without separate
component release pages. Every Git tag still identifies a whole repository snapshot.

## Commit intent

| Intent | Typical release meaning |
| --- | --- |
| `fix(orquestrar): ...` | Compatible correction. |
| `feat(orquestrar): ...` | New compatible capability. |
| `feat(orquestrar)!: ...` | Breaking behavioral/usage contract. |
| `docs: ...` | Non-behavioral repository documentation only. |

Scopes describe intent; actual changed paths determine affected components. Shipped
Markdown is behavioral content. Editing instructions or bundled references can require
`fix:` or `feat:` even when no programming-language file changes.
The configuration explicitly uses pre-1.0 behavior: breaking changes bump the minor while
below 1.0; ordinary features bump the minor as configured. Review every release PR; do
not assume the first release must be 1.0.0. A deliberate stable-1.0 release decision is
separate from accepting the scaffold's initial version.
The generated release configuration starts new catalog and skill releases at `0.1.0`;
`0.0.0` remains the unreleased bootstrap state.

## Workflow

```text
Content PR -> CI/review -> squash merge on main
           -> manually dispatch Release -> version PR
           -> review/version merge -> manually dispatch Release
           -> catalog release -> verified artifacts and component tags
```

## Release runbook

1. Confirm the content PR is merged, the exact `main` commit passed CI, and the
   worktree is clean. Run `make verify-identity REPO=J-Yoharu/skills` and
   `make check`. For a changed skill, confirm that its `evals.json` approval
   names the current `make skill-fingerprint NAME=<skill>` digest. Choose the
   first SemVer deliberately; generated configuration starts at `0.1.0`.
   Release Please, not the maintainer, updates version files, changelogs, and
   the manifest.
2. Check GitHub prerequisites **before** dispatching. `RELEASES_ENABLED` must
   equal `true`. If the workflow uses `GITHUB_TOKEN`, the repository setting
   [**Allow GitHub Actions to create and approve pull requests**](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)
   must be enabled; alternatively configure the optional scoped
   `RELEASE_PLEASE_TOKEN`. Do not dispatch while neither PR-creation route works.
   Verify the current settings:

   ```bash
   gh variable get RELEASES_ENABLED --repo J-Yoharu/skills
   gh api repos/J-Yoharu/skills/actions/permissions/workflow --jq '.can_approve_pull_request_reviews'
   ```

3. Dispatch `gh workflow run release.yml --repo J-Yoharu/skills --ref main`
   with no `release_tag`. Release Please opens or updates the combined version
   PR. Keep its generated title and body: its default combined title is
   `chore: release main`, its body contains parseable per-component versions,
   and its label is `autorelease: pending`. A plausible manual title or a
   generic PR description is **not** equivalent; Release Please uses them to
   find the merged PR and create tags. Review the exact proposed versions,
   manifest, changelogs, metadata-only `SKILL.md` changes, and CI. If a PR
   created by `GITHUB_TOKEN` does not trigger PR CI, validate the PR title/diff
   locally and dispatch CI for its branch. Confirm that CI tested the same head
   SHA before merging:

   ```bash
   git fetch origin main release-please--branches--main
   BASE_SHA=$(git rev-parse origin/main) HEAD_SHA=$(git rev-parse origin/release-please--branches--main) PR_TITLE='chore: release main' PR_BRANCH='release-please--branches--main' make check-pr
   gh workflow run ci.yml --repo J-Yoharu/skills --ref release-please--branches--main
   ```

   Squash-merge the reviewed release PR.
4. Wait for the merged `main` commit's CI to pass. Dispatch Release again on
   `main` with no `release_tag`. The workflow creates the catalog GitHub
   Release and tag, builds from that exact tagged commit, uploads `index.json`,
   `SHA256SUMS`, and skill archives, then creates component tags.
5. Verify publication independently. A successful workflow with build/upload
   steps skipped is **not** a published release. Confirm the GitHub Release is
   neither draft nor missing assets, and confirm both remote tags resolve to
   the tested commit. For example, replace `0.1.0` with the chosen version:

   ```bash
   gh release view v0.1.0 --repo J-Yoharu/skills --json tagName,targetCommitish,assets,url
   git ls-remote --tags origin refs/tags/v0.1.0 refs/tags/orquestrar-v0.1.0
   ```

If GitHub reports `GitHub Actions is not permitted to create or approve pull
requests`, fix the PR-creation permission or token before retrying. Do not
manually open the generated branch as the routine workaround: an incorrect
title or body can pass ordinary CI yet prevent Release Please from recognizing
the merged PR. If this already happened, inspect the merged PR's title, body,
and `autorelease: pending` label against the [Release Please pull-request
format](https://github.com/googleapis/release-please/blob/main/docs/customizing.md)
before another dispatch. Never merge the newly proposed next-version branch
while the previous release is untagged. Once the catalog tag and GitHub Release
exist, repair missing assets with `release_tag` set to that **existing** tag;
this path validates the tagged snapshot and never moves tags or clobbers assets.

Release handling remains manual and requires an active skill, configured identity,
credentials, and `RELEASES_ENABLED=true`. Merge content and release PRs only after checks.
A release build rejects a dirty tree, a mismatched tag, catalog/component downgrades,
and changed skill files without a version bump. A maintenance-only catalog release may
retain unchanged component versions.

Do not mutate released tags or assets. Use a new patch release for corrections.
The standard default-branch installer command does not pin a semantic version. Git refs
and local checkout commits provide reproducibility; do not reinterpret `@skill-name`
shorthand as a version selector. For an auditable exact installation, check out the desired
catalog/component tag or full commit and use the pinned external installer's documented
local-source syntax after verifying compatibility. No untested version-install shortcut
is promised by this scaffold.

## Current release

Catalog `v0.1.0` and component `orquestrar-v0.1.0` identify the same tested
repository snapshot. Orquestrar's supplied archive label `2.3.0` was an editing
iteration, not an earlier semantic release; see [import provenance](ORQUESTRAR_IMPORT.md).
