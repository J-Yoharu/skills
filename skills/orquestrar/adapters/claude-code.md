# Adapter: Claude Code

## Coordinator fixed to the current session

The model running this skill in the open chat is the coordinator. Do not create a
coordinator subagent or change the main session's model/reasoning effort. Matrices,
overrides, presets, and dynamic selection apply exclusively to subagents. Do not
use global configuration, another CLI, or a chat-model change as fallback.
Observable chat model/effort is telemetry; on resume use the current session,
not the previous coordinator's recorded configuration.

Read this adapter only in Claude Code. It maps roles to observed capabilities;
it installs no agents, hooks, plugins, permissions, or global settings.

## Discovery and invocation

Install the entire skill folder at `.claude/skills/orquestrar` for a project or
`~/.claude/skills/orquestrar` for personal use. Invoke `/orquestrar <request>`.
Frontmatter allows implicit activation for implementation requests, not merely
reading or quoting the skill. Profile discovery/validation is automatic after
activation, without a prior user command. Asking to inspect/review this skill
does not authorize running its implementation workflow.

Confirm tools/types and descriptions **in this session**. The documentation cited
by earlier releases uses `Agent` for delegation; other versions/products may expose
different names. Use only registered types. Here, `implementer` and `reviewer`
are logical roles, not assumed `subagent_type` values.

Before delegation, record support for fresh context, inherited/forked context,
messaging/resume, waiting, interruption/closure, model/effort, tool restrictions,
worktrees, and agent limits. Unknown is not supported.

## Execution

Prefer fresh context with an explicit work order for bounded implementation and
review. Do not put `context: fork` in this skill's frontmatter: coordination must
stay in the main session. Do not inherit the whole history without a reason;
when inheritance is genuinely needed and supported, record why and retain scope limits.

Reuse existing agents that respect ownership and permissions. Skills invoked by
the coordinator may not reach the worker: include essential rules and accessible
references rather than duplicate whole documents. Check the instruction hierarchy
actually received, especially by specialized explorers.

Nested-agent support varies by version. The ban on worker delegation here is
**orchestration policy**, not a claim that Claude Code cannot nest agents. Restrict
the delegation tool when possible. Reviewers need read-only access; unrestricted
shell access is not a read-only sandbox. Without technical isolation, disclose
cooperative enforcement or use an isolated review environment before claiming
absence of writes.

[Model routing](../references/model-routing.md) maps models and efforts by role.
Native subagent configuration uses `model` and `effort` where the actual schema
accepts them. Current inventory takes precedence over the catalog. Environment
variables or organization caps may override files; confirm requested versus
effective settings from metadata, not a model name written in the prompt. Never
invent effort for unsupported models.

Optional installable examples are in `assets/native/claude-code/` inside this skill.
Installation in `.claude/agents/` or `~/.claude/agents/` requires authorization;
files inside the skill are not automatically loaded. Confirm registration and
version compatibility before use. Do not overwrite existing agents or disable
harness controls. Use a read-only profile for review even when selecting a model
from a different capacity tier. Shell-enabled agents have additional cooperative
restrictions, not a universal sandbox. Profile revalidation does not reinstall agents.

Use `isolation: worktree` only when supported and suitable. Returned results do
not prove integration. Worktrees do not isolate services. Do not presume processes
or worktrees were removed; check before transferring ownership.

## Continuity and safety

Follow the loop in the active session and persist checkpoints. `/goal`, loops,
agent teams, and hooks are optional mechanisms with their own semantics, not
requirements. Do not activate/install them or change permission modes to manufacture
autonomy. If the user already uses a confirmed mechanism, adapt reporting without
letting it expand scope, force publication, or replace evidence with a final phrase.

Do not hardcode `SendMessage`, `TaskStop`, or a return schema when this session
exposes a different contract. API failures require rediscovery, not guessed
parameters. Without delegation, use the generic adapter and disclose review limits.

## Pause and context

The referenced statusline documentation names `context_window.used_percentage`
and `remaining_percentage`, which may be null. Use them only when a current signal
from the same session is actually accessible to the coordinator. Statusline
configuration alone does not inject data into the prompt; do not install/change
it here. `/compact`, `/clear`, stop controls, and `/resume` have distinct semantics;
none replaces completing and validating a unit before a planned session transfer.

Use the portable [state and delivery](../references/state-delivery.md) pause
protocol, executed by the current coordinator only. Preserve `draining`/`paused`
through compaction, resume, and any existing loop. Do not install hooks/loops;
if an existing mechanism tries to continue, retain the pause and report the
conflict. Do not bypass harness limits to finish a drain.
