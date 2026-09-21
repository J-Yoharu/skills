# Adapter: Codex

## Coordinator fixed to the current session

The model running this skill in the open chat is the coordinator. Do not create a
coordinator subagent or change the main session's model/reasoning effort. Matrices,
overrides, presets, and dynamic selection apply exclusively to subagents. Do not
use global configuration, another CLI, or a chat-model change as fallback.
Observable chat model/effort is telemetry; on resume use the current session,
not the previous coordinator's recorded configuration.

Read this adapter only in Codex. Separate portable skill instructions from the
subagent API exposed by the CLI, IDE, desktop, or hosted session. Model identity
does not determine available capabilities.

## Discovery and installation

The documentation referenced by earlier releases specifies `.agents/skills/orquestrar`
for projects and `~/.agents/skills/orquestrar` for personal installation, invoked
as `$orquestrar <request>`. `agents/openai.yaml` enables implicit invocation and
presentation; it creates no workers, connectors, or permissions. Discovery is
automatic after activation. The request must ask for execution: quoting/reviewing
the skill does not authorize implementation. Claude's activation policy does not
replace Codex's policy.

Inspect actual delegation tools, configured agent profiles, and current rules and
permissions. Record fresh context, model/effort controls, tree isolation, tool
restrictions, waiting, messaging, resuming, and closure as supported, unsupported,
or unknown, with evidence.

## Capability mapping

Logical `implementer` needs scoped edit/test access; `reviewer` reads diffs/code
without editing or delegating; `researcher` gets a bounded question. These roles
are not automatically registered types.

Use actual names/schemas for spawn, wait, message, resume, and closure. Do not
copy parameters such as `fork_turns`, `agent_type`, or `model`, or names such as
`followup_task`, from another environment without confirming support. Prefer
fresh context plus a complete work order when inheritance options exist;
otherwise do not send an invented option to suppress inheritance.

Local clients may support separate model/effort agent configuration. Use an
existing profile or a spawn field **only when exposed**. Without selection, use
available inheritance; do not claim a "cheaper worker" because the prompt says
so. Record requested/effective values. Unknown effective configuration is not
itself a failure, but invalidates optimization claims based on that selection.

Do not create global profiles or edit `config.toml` as an implementation side effect.
[Model routing](../references/model-routing.md) already maps roles in a separate
catalog. Apply `model` and `model_reasoning_effort` only through confirmed native
mechanisms. Unit risk takes precedence over size.

Optional examples live in `assets/native/codex/`. The referenced documentation
describes standalone agent TOML files in `.codex/agents/` or `~/.codex/agents/`, with
`name`, `description`, and `developer_instructions`. Copying them requires explicit
installation authorization, not discovery. Earlier versions may use a different
structure: honor the installed version and avoid conflicting registrations.
Fixed profile model/effort may override spawn values; select a matching profile
or a native mechanism without that conflict. Runtime permission overrides may
supersede preset `sandbox_mode`. Confirm actual read-only enforcement before
claiming review isolation. Never invent selection or install another CLI to
bypass restrictions.

## Isolation, corrections, and closure

Check whether workers share a tree. This skill defaults to one writer. Without
native isolation, use authorized worktrees or serialize; specifying another path
in a prompt is not isolation. Keep shared services within project resource limits.

Only the coordinator delegates. Restrict reviewers to reads when supported.
Prompt instructions do not technically block a writable shell: disclose that
limit or isolate the environment. Do not assume `explorer` can perform every
review depth; select the necessary capacity and context.

Resume the same worker for findings when API state/contract allows. Without
resume support, create a replacement with a verifiable handoff. Never presume
old IDs from another session remain usable. Wait in the active session, persist
results, and close finished agents. Do not end the final response with workers
supposedly continuing without an execution tool supporting that claim.

Do not use `/goal` or Claude commands as fallback. Without subagents, use the
generic sequential path while keeping mandatory independent review pending.

## Pause and context

Context may appear in session/statusline controls depending on version. Use only
current metrics exposed to the coordinator or supplied by the user. Do not invent
telemetry commands/APIs; a UI percentage may be unreadable to the model. Convert
remaining to used context only when semantics are explicit. `/compact` summarizes
history; it is not an orchestration pause. Immediate-stop controls do not promise
unit completion.

Use the portable [state and delivery](../references/state-delivery.md) pause
protocol, executed by the current coordinator only. Preserve `draining`/`paused`
through compaction, resume, and any existing loop. Do not install hooks/loops;
if an existing mechanism tries to continue, retain the pause and report the
conflict. Do not bypass harness limits to finish a drain.
