# Operations

## One command menu, direct runtime execution

`make help` derives its menu from comments beside targets in the [Makefile](../Makefile).
Run from the repository root, or `make -C "/path/with spaces/repo" TARGET`.
Do not use `make -f /other/repo/Makefile` from an unrelated directory.

```text
Makefile
  +-- Python: .venv/bin/python -m scripts ...
  +-- Bootstrap: python3.13 scripts/bootstrap.py
  +-- Node: node --test tests/launchers/*.test.mjs
  +-- Optional JavaScript install: pnpm install --frozen-lockfile

Optional pnpm aliases -> scripts/run.mjs -> the same Python modules/bootstrap
```

Make is not a proxy to pnpm. Business rules are implemented once in `scripts/`;
Make composes tasks and validates arguments. Python bootstrap is stdlib-only so it
can create the environment before installing maintenance dependencies. No automatic
installation takes place during validation, tests, planning, preview, or publishing.

## Routine commands

```bash
make setup
make validate
make test-python
make test-skills NAME=orquestrar
make test-launchers
make test
make isolate SKILLS_JSON='["orquestrar"]'
make check
```

`make test` runs launcher, maintenance, and skill unit suites. `make check` also
validates contracts, runs copied-skill smoke tests, and builds active-only preview
artifacts. Neither command is a native-agent behavioral evaluation.

`tests/skills/<name>/test_*.py` suites are discovered automatically and executed in
separate Python subprocesses to avoid module-name collisions across skills. No suite
is reported as passed when none exists; its result is `no_unit_suite`. Smoke tests
execute the copied product from both its folder and an unrelated directory, with
credentials/search paths removed. This is dependency isolation, not an OS sandbox.

## Skill lifecycle and local evaluation

```bash
make skill-new NAME=example-skill DISPLAY_NAME="Example Skill"
make skill-preview NAME=orquestrar
make skill-fingerprint NAME=orquestrar
make catalog-update
make release-sync
```

`skill-preview` copies only the requested payload under `dist/skill-preview/<name>`
and materializes `SKILL.md` there. It rejects redirected output paths, preserves the
source fingerprint, and never changes source lifecycle, version, or evaluation evidence.
Use this disposable copy in a dedicated native-agent evaluation project. `make check`
rebuilds `dist` and may remove preview copies; regenerate them after the gate.

`make skill-activate NAME=orquestrar` requires real evaluation evidence and explicit
authorization. Successful tests, preview generation, or an editing-version label do
not justify activation or a stable release. See [Adding skills](ADDING_SKILLS.md).

## CI scope and scaling

```bash
BASE_SHA=<base-commit> HEAD_SHA=<head-commit> make plan
BASE_SHA=<base-commit> HEAD_SHA=<head-commit> make ci-check
```

`plan` reports selected skill names and whether maintenance regressions are required.
`ci-check` always validates repository/documentation contracts, runs maintenance tests
when shared code changes, then executes the selected skill suites and smoke tests.
The hosted workflow conditionally adds the Node/Make regression suite. Missing or
unresolvable history selects everything. Standalone `make check` always runs everything.

The default CI has one Linux `gate` job, not a matrix per skill. Existing compact shard
helpers remain available for a future measured bottleneck; `ci.max_shards` is initially
1 and does not automatically enable hosted parallelism. See [CI/CD](CI_CD.md).

## Arguments, safety, and publication

Inputs such as `NAME`, `DISPLAY_NAME`, `REPO`, and `TAG` are exported and expanded as
quoted shell arguments. `PYTHON`, `BOOTSTRAP_PYTHON`, `NODE`, and `PNPM` may name trusted
executables. GNU Make evaluates its own expressions: do not accept arbitrary Make
expressions from untrusted sources. Command guards prevent mistakes, not malicious use.
Top-level mutations are serialized even when `-j` is supplied.

```bash
make build-preview
make build-release TAG=v1.2.0
make publish-assets TAG=v1.2.0 CONFIRM_PUBLISH=yes
```

Release builds require the exact clean tagged commit, synchronized versions, and
approved active skills. The publisher reconstructs artifacts, preflights remote asset
and component-tag conflicts, and refuses incompatible overwrites. Network operations
are not transactions: a network failure can leave some valid assets uploaded. Repair
using the same immutable tag, never `--clobber` or a moved tag.

All workflows call this command menu. They install Python dependencies once per job;
they do not add pnpm/Node dependency installation to Python-only maintenance work.
