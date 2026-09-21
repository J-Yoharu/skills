# J-Yoharu Skills

A monorepo of self-contained Agent Skills, maintained at **J-Yoharu/skills**.
The supplied **Orquestrar** implementation is integrated at
`skills/orquestrar/SKILL.md.template`, with its helpers, adapters, references, and assets.
It is an **unreleased candidate**, not an empty scaffold and not a validated release.

## Start here

Use GNU Make, a POSIX shell, Git, Python 3.13, and Node.js in the supported range
(see `package.json`). pnpm is optional when using Make.

```bash
make help
make setup
make check
```

Make calls Python directly for Python operations, Node directly for JavaScript tests,
and pnpm only for the optional `make install` task. `make setup` installs the pinned
Python requirements into `.venv`; ordinary checks never install packages implicitly.
See [Setup](docs/SETUP.md) for prerequisites and the first push to the already configured
repository. Nothing here creates a remote, pushes, activates, or publishes automatically.

## Layout

```text
skills/orquestrar/       Candidate product, without root maintenance dependencies
scripts/                Python operations and optional Node/pnpm launcher
catalog/                Per-skill lifecycle and copied-payload smoke declarations
tests/skills/orquestrar/ Helper regressions and unexecuted behavioral scenarios
tests/scripts/          Maintenance regression tests
tests/launchers/        Node, Make routing, and agent-policy contracts
schemas/                Repository-specific JSON schemas
.github/                One-job CI, manual release/interop, ownership, issue forms
docs/                   Setup, architecture, operations, import and verification records
AGENTS.md               Canonical repository policy for coding agents
CLAUDE.md               Native import of AGENTS.md
Makefile                Central command menu
```

The operational directory names are repository conventions, not requirements imposed
by skills.sh. See [Architecture](docs/ARCHITECTURE.md).

## Work on Orquestrar

```bash
make test-skills NAME=orquestrar
make isolate SKILLS_JSON='["orquestrar"]'
make skill-preview NAME=orquestrar
```

The last command creates `dist/skill-preview/orquestrar/SKILL.md` for local native-agent
evaluation. The tracked source remains a draft. Preview copies are disposable and
must not be committed or described as published releases.

The source archive's editing version was **not adopted** as a release. Both the
catalog and candidate begin at `0.0.0`, a bootstrap value that cannot be published.
The 58 imported behavioral scenarios remain `not_run`, and review remains `pending`.
[The import record](docs/ORQUESTRAR_IMPORT.md) lists exact preservation and adjustments.

## Add future skills

```bash
make skill-new NAME=example-skill DISPLAY_NAME="Example Skill"
make catalog-update
make validate
```

Follow [Adding skills](docs/ADDING_SKILLS.md). Activation requires real evaluation
and explicit authorization; CI never manufactures approval from passing unit tests.
After activation/publication, the intended installer command for Orquestrar is
`npx skills add J-Yoharu/skills --skill orquestrar`. It is **not available from this
draft source**. See [Versioning](docs/VERSIONING.md) for release and pinning boundaries.

## CI and publication

CI has a single stable `gate` job on pull requests and pushes to `main`. It always
validates repository contracts, runs maintenance regressions when shared code changes,
and tests/copies only affected skills. Missing Git history selects everything.
There are no paid larger runners, routine artifact uploads, or scheduled evaluations.
Release and external interoperability are manual and opt-in. See
[CI/CD and cost](docs/CI_CD.md); optimization is not a guarantee about account billing.

## Coding agents and evidence

[AGENTS.md](AGENTS.md) is the shared policy for Codex and Claude Code; [CLAUDE.md](CLAUDE.md)
imports it. Repository-maintained prose/code is English. Existing CLI identifiers and
explicit multilingual compatibility fixtures are preserved, not translated into a new API.

See [Verification](docs/VERIFICATION.md) for actual executed checks and limitations.
Older review reports are labeled historical; they do not attest this candidate.
