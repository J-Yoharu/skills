# Codex adapter

Read **Subagents** only when needed to use this session's native API. Portable
execution/checkpoint rules are already in `SKILL.md`. Model identity does not imply
which tools a CLI, IDE, desktop or hosted session exposes.

## Subagents

Use actual spawn/wait/message/closure schemas. Never assume fields such as `model`,
`fork_turns`, `agent_type` or `followup_task` exist because another harness had them.
Use fresh review context and a complete bounded work order when supported. Only
the coordinator delegates; workers/reviewers do not spawn other agents.

Select model and `model_reasoning_effort` separately through exposed native fields
or an existing compatible agent configuration. Fixed presets can override requested
values; permission overrides can override preset sandbox settings. Record what was
requested and what metadata confirms, or unknown. A prompt naming a model does not
switch it. Reuse capability observations instead of inventorying every role.

One writer per tree. Use actual isolation or serialize. Reviewers must not edit;
use native read-only permission where supported. A writable shell with a read-only
prompt is not technical enforcement; disclose the boundary. Reuse implementer
context for cohesive fixes, not review context. Wait/reconcile actual agent state
before replacement; a timeout does not prove the writer stopped.

Without a native independent context, leave required review pending. Without model
selection, adequate inherited capacity may be used, with the limitation explicit.
Never change the current chat, global config, or launch another CLI as a workaround.
The current chat remains coordinator on resume; old IDs/settings are not restored.

## Installation — only when explicitly requested

Project skills use `.agents/skills/orquestrar`; personal skills may use
`~/.agents/skills/orquestrar`. Invocation is `$orquestrar <request>` and
`agents/openai.yaml` allows implicit activation; it grants no tools or permissions.
Confirm the installed version's configuration format and preserve existing
profiles; never register agent profiles during an implementation or update globals
without permission. Source catalogs may retain a draft `SKILL.md.template`; use their
disposable preview workflow rather than changing lifecycle to test installation.

## Pause and sandbox

Use the portable pause/resume protocol when that event occurs. Preserve the pause
through compaction; no hook/loop installation. Workspace-write does not imply access to `.git` or agent settings. Use authorized
workspace state; never relax sandbox permissions to save a checkpoint. Read ancestor
rules by exact path, not recursive parent discovery.
