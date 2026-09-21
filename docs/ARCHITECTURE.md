# Architecture

## Standards versus repository conventions

| Path or file | Status and purpose |
| --- | --- |
| `SKILL.md`, supported frontmatter | Agent Skills format; the discovery entry point for an actual skill. |
| Per-skill `scripts/`, `references/`, `assets/` | Recognized resource conventions in the format; include only resources the skill needs. |
| `.github/workflows/` | GitHub Actions workflow location. |
| `AGENTS.md` / `CLAUDE.md` | Shared coding-agent policy and native compatibility import; not skill payload. |
| `Makefile` | Public maintenance task menu; GNU Make convention, not an Agent Skills requirement. |
| Root `scripts/`, `tests/`, `docs/` | Common repository conventions, not requirements for skills.sh publication. |
| `catalog/`, `schemas/`, `repository.json` | This repository's operational contracts, not a universal skills standard. |
| `version.txt`, release manifest, review fingerprint | Local release and review policies. |

The old name `tooling/` was a valid generic choice, not a standard. This revision uses
`scripts/` for familiar root maintenance commands, as seen in established skill catalogs.
No runtime skill depends on this directory. Do not create a separate repository merely
for validators tied to this catalog; split them only if they become an independently
maintained product used by several repositories.

## Product versus operations

A distributed skill contains its instructions, own runtime helpers, required references,
assets, license, version, and changelog. It cannot depend on sibling skills or root tooling.
Runtime helpers resolve files from their own location, not the caller's working directory.

Root `scripts/` contains the Python engine, a stdlib bootstrap, and an optional Node
launcher. Make runs each required runtime directly; pnpm is not in the Python command
path. The optional pnpm aliases reuse these modules. Dependencies remain explicit:
pip for Python maintenance and pnpm for any future root Node dependencies. There are
currently no third-party Node dependencies or artificial per-skill npm packages.

Each `catalog/<name>.json` declares lifecycle and smoke tests. Each
`tests/skills/<name>/evals.json` holds human evaluation cases, evidence, and the reviewed
payload fingerprint. Root schemas validate those local policies. These files are not
copied into the consumer payload.

## Lifecycle and scaling

`draft` has `SKILL.md.template`, version `0.0.0`, and no installation promise. `active`
requires real instructions, reviewed positive/negative cases, and passing structural and
isolation checks. Activation updates discovery and generated release configuration locally.
It does not create a release or perform remote writes.

The CI planner discovers names from individual catalog records. It selects affected skills
from Git diffs; shared maintenance changes or unavailable history select all skills.
Changes to Makefile and shared agent instructions also select all skills.
The default hosted CI runs everything selected in one standard Linux job. Existing
compact shard helpers are retained, with a default ceiling of 1, but no hosted matrix
is enabled. Increase parallelism only after measuring a real bottleneck. The planner
still avoids retesting unrelated skill suites and always selects everything if history
is missing. Validation traverses the full catalog to detect cross-catalog errors.

A draft may contain a full implementation awaiting evaluation, not just placeholders.
`make skill-preview NAME=orquestrar` provides a disposable local installation copy
without changing readiness. The imported editing version is provenance, not SemVer.
