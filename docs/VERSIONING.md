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

Release handling is disabled by default and requires an active skill, configured identity,
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

## Current imported candidate

Orquestrar is `draft`, with `version.txt` and `metadata.version` both `0.0.0`.
The supplied archive label `2.3.0` identified an editing iteration, not a validated
release, so it is recorded only in [import provenance](ORQUESTRAR_IMPORT.md).
The release manifest contains only the bootstrap catalog until authorized activation.
Unit tests do not choose the first stable SemVer or approve an implementation.
