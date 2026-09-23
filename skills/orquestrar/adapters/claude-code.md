# Claude Code adapter

Use **Subagents** for unclear native mechanics, not as a mandatory startup read.
The current chat is the coordinator; never select its model/effort or configure
a forked coordinator. Ordinary execution and persistence follow `SKILL.md`.

## Subagents

Use the native Agent tool and parameters actually exposed by this installation.
A general-purpose implementation needs scoped write/test access; a reviewer needs
a genuinely separate context, scoped code/criteria and no writes/delegation. Logical
roles in the skill are not necessarily registered native agent names.

Use supported model fields or existing compatible agents. Set reasoning effort
only through controls supported by both the harness and that model; do not invent
an effort field for a model without one. Pass the Agent tool's `model` field from
the role policy and record it; without that field, record `inherited`. Read only the
selected catalog role. Never reconfigure the chat.

Prevent recursive delegation, use tool permissions for read-only review where
available, and disclose limitations of prompt-only restrictions. Confirm whether
trees/services are shared; a different path in a prompt is not isolation. Only one
writer may own a tree. Reuse an implementer for cohesive corrections, use a fresh
reviewer context, wait with actual native tools and reconcile before replacement.
Old IDs from a previous session are not proof of a resumable/stopped worker.

## Installation — only when explicitly requested

Project/personal skills use `.claude/skills/orquestrar` or
`~/.claude/skills/orquestrar`; invoke `/orquestrar <request>`. Automatic selection
still depends on a matching execution request; discussion or quotation is not
execution. Confirm version-specific configuration and preserve existing agents. No `context:
fork`, `agent`, model setting or global mutation is required for the coordinating
skill. Do not add hooks, `/goal` or other autonomous loops as an implementation step.

## Pause and context

Use the portable pause protocol, not stop hooks as substitute evidence. An existing
loop cannot release a saved pause or broaden the frozen set. Immediate interruption
may leave incomplete work. Resumption uses the
current session and reconciles actual sources, files, permissions and old processes.
