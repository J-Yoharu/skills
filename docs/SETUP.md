# Setup

## Prerequisites and local bootstrap

Use GNU Make 3.81+ with a POSIX shell, Git, Python 3.13 with venv/pip, and Node.js in
the `package.json` engine range. Make's full test gate uses Node for launcher/command
regressions; Python-only commands do not need Node or pnpm. On Windows, WSL provides
the documented Make environment. Native Windows pnpm aliases remain available but
native Windows/macOS integration is not claimed by Linux tests.

```bash
make help
make setup
make check
```

`make setup` runs the stdlib-only `scripts/bootstrap.py` with `python3.13`, creates
`.venv`, installs exact `requirements-dev.txt` versions, and runs `pip check`.
Use `make setup BOOTSTRAP_PYTHON=/path/to/python3.13` for a custom interpreter.
Normal tasks use `.venv/bin/python` (or `.venv/Scripts/python.exe` on Windows).
Override with `PYTHON=/path/to/verified/python` when an environment is managed externally.
Overrides are executable paths, not command strings with flags.

The current identity is already `J-Yoharu/skills`; `.github/CODEOWNERS` names `@J-Yoharu`.
`make verify-identity REPO=J-Yoharu/skills` checks that locally, without a GitHub request.
Use `make configure REPO=OWNER/REPO CODEOWNER=@OWNER` only to adopt a different repository.

## Optional pnpm interface

There are currently no third-party root JavaScript dependencies. pnpm is not a
prerequisite for Make or CI. To use its alternate command interface:

```bash
npm install --global pnpm@10.33.4
make install
pnpm bootstrap
pnpm check
```

`make install` invokes `pnpm install --frozen-lockfile`; it does not manage Python
packages. The root package and lockfile preserve the pinned interface. Skills are
not artificial npm packages. Without Make, use the documented pnpm aliases in
`package.json`; neither interface calls the other recursively.

## First push to the existing empty repository

Review the included MIT license and attribution before publishing any source.
From the extracted repository directory, provided it has no existing Git history:

```bash
git init --initial-branch=main
git add .
git commit -m "feat(orquestrar): integrate unreleased candidate and catalog tooling"
git remote add origin https://github.com/J-Yoharu/skills.git
git push -u origin main
```

For an existing checkout, inspect `git status` and `git remote -v` instead of repeating
initialization or overwriting an existing remote. The delivered archive excludes `.git`.
No remote-write commands were executed to prepare the archive.

Check the first hosted CI run. Require the stable `gate` check under repository rules.
Use squash merges retaining the Conventional Commit PR title; protect against force
pushes. For a solo-maintainer repository, do not require an impossible self-approval:
choose review rules consistent with the actual contributors and available GitHub plan.

## Manual releases

The first catalog and Orquestrar release, `v0.1.0`, was published on 2026-10-04.
Future releases remain manual; a current `RELEASES_ENABLED=true` value and
GitHub PR-creation capability must be checked before every dispatch. Follow
the [release runbook](VERSIONING.md#release-runbook) for exact preflight,
version PR, two-dispatch workflow, verification, and repair steps. Do not
assume a successful workflow published assets until the remote release and
tags are verified. Never commit credentials.

## Optional interoperability and updates

Set `INTEROP_ENABLED=true`, then manually dispatch **External interoperability**.
It uses the pinned external validator/installer and network access. No schedule or
LLM/API evaluation is configured. Review source and privileges before enabling it.

Dependabot groups each ecosystem into monthly update PRs, with one open PR per
ecosystem. Security notifications and maintainer-initiated updates remain important;
a monthly version-update schedule is not a substitute for responding to vulnerabilities.
