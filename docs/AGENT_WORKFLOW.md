# Codex and Claude Code workflow

## One source of repository policy

[AGENTS.md](../AGENTS.md) contains the shared rules. Codex discovers that file through
its project instruction mechanism. [CLAUDE.md](../CLAUDE.md) contains the native
`@AGENTS.md` import, rather than a link that requires the agent to decide to open it.
No rule generator, symlink, global configuration change, or agent-specific duplicate
policy is required.

The Claude import is retained for compatibility with sessions that do not load
`AGENTS.md` directly. Native behavior varies with agent versions, managed settings,
and trust choices; a repository cannot override those controls. Instruction files
are guidance, not an operating-system sandbox or a guarantee of model behavior.

Keep policy in AGENTS.md and operational details in the linked guides. Do not add
per-skill copies of AGENTS.md or CLAUDE.md: they would pollute installed payloads and
create conflicting maintenance rules. New skills inherit repository maintenance
policy without generating any agent instruction files inside their product directory.
If a real future need requires more scoped policy, review its scope for both agents
and the product boundary before adding it. Do not assume identical nested loading.

## Opening the checkout

Start either agent at the repository root, after reviewing the checkout and granting
only the permissions needed for the task. `make help` works without pnpm or Python.
Use [Setup](SETUP.md) for explicit dependency installation and first-push steps.

In Codex, ask it to list the instruction sources it loaded and summarize the shared
product boundaries. Restart the session after changing instruction files. In Claude
Code, use `/context` or `/memory` to inspect project memory and ask it to summarize
the imported rules. Confirm this checkout's AGENTS.md is included. Global/user or
managed instructions, overrides, trust settings, and disabled imports can change
what a session loads; inspect those rather than silently editing global settings.

No Codex or Claude Code executable is a development dependency of this repository.
Normal checks do not open model sessions, consume model credits, install hooks, or
contact either provider. Native agent loading must be verified in an actual authorized
session; tests of file structure are not a substitute for that observation.

## Task handoff

Give either agent the goal, affected scope, acceptance criteria, and allowed side
effects. A useful request is: "Read AGENTS.md, discover the existing implementation,
make the smallest change for this issue, add regression coverage, and report the
commands actually run. Do not activate or publish any skill."

The shared rules require discovery/reuse before implementation, English maintained
content, protection of user changes, and a review pass. For a separate reviewer,
provide the diff, invariants, observed test results, and unresolved questions. A
self-review must not be described as a second agent. The final handoff distinguishes
routing/unit tests, copied-skill checks, real model evaluations, and hosted execution.

## Commands and permissions

The public menu is [Makefile](../Makefile); see [Operations](OPERATIONS.md).
`make setup` is explicitly network-capable. `make check` runs local validation,
regression tests, copied-skill smoke tests, and preview packaging without activating
or publishing a skill. Smoke tests execute repository-supplied code: review untrusted
changes and use the agent's existing sandbox/permissions before running them.

Keep pnpm's existing aliases as a no-Make fallback, not a second implementation.
No unrestricted command allowlist, automatic post-edit hook, custom agent mode,
remote-write permission, or MCP integration is installed by this scaffold.
Per-user settings and session/credential files are ignored; shared policy is tracked.

## Maintaining this contract

`make test-launchers` checks the native Claude import, shared policy entry points,
Make aliases and guards, help/default behavior, and automatic launcher-test discovery.
CI runs those tests through `make test-launchers` when maintenance changes. Changes
to Makefile or shared agent instructions select all skills because their impact is
repository-wide. Make invokes Python/Node directly, not through pnpm.

These checks detect wiring regressions. They cannot prove that an agent followed every
instruction or that a human review occurred. Record native session checks and genuine
skill evaluations separately.

## Primary references

Verified on 2026-09-21:

- [OpenAI: custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
- [Claude Code: project memory and sharing AGENTS.md](https://code.claude.com/docs/en/memory)
- [pnpm 10: running package scripts](https://pnpm.io/10.x/cli/run)
