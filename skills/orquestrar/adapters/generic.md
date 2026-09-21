# Adapter: another harness or partial capabilities

## Coordinator fixed to the current session

The model running this skill in the open chat is the coordinator. Do not create a
coordinator subagent or change the main session's model/reasoning effort. Matrices,
overrides, presets, and dynamic selection apply exclusively to subagents. Do not
use global configuration, another CLI, or a chat-model change as fallback.
Observable chat model/effort is telemetry; on resume use the current session,
not the previous coordinator's recorded configuration.

Shared policy stays in SKILL.md. For a new harness, map only:
1. Skill installation/invocation and supported frontmatter extensions.
2. Project instruction loading and permission boundaries.
3. Actual tools to read/edit/test and delegate/wait/close.
4. **Subagent** model/effort selection and effective identity, if available; add
   a mapping block to model-catalog.json without changing the workflow.
5. File, service, context, and review isolation.

Document capabilities as supported, unavailable, or unknown, citing the installed
version's schema/documentation. Do not assume equivalent hooks/lifecycles, build
a universal RPC layer, or invent tool names.

Without subagents, the coordinator works sequentially under the same criteria,
limits, and checkpoints. A second pass in the same context is self-review, not
independent review. When risk requires independence, use a real allowed resource
(another context, human, or approved service) or keep that gate pending.

Without Git, use available file/revision identifiers and checksums; local delivery
requires no PR. Without Python, use equivalent native project evidence/scripts;
helpers are optional. Without a connector, use the user-supplied export, state its
revision, and block work requiring missing data.

Permissions are enforced by the harness/sandbox, not Markdown. Do not claim
technical read-only access or isolation based solely on cooperative instructions.
Do not install other harnesses, launch secondary CLIs, or bypass restrictions to
simulate subagents.

For permanent support, add a self-contained adapter, link it from SKILL.md, and
run portability/permission scenarios. Workflow, sources, and quality criteria
need not be duplicated.

Project profiles and overrides are reusable; runtime is fresh per session. Apply
[automatic profile loading](../references/project-profile.md) and the generic
[source contract](../references/source-contract.md), without provider adapters.

## Pause and context

Without reliable context metrics, leave the percentage trigger unavailable and
accept manual pause; never guess a percentage. Without cooperative worker messaging,
use native results/waiting, check the unit, and do not dispatch another. Without
agent control/waiting, disclose the limitation and do not claim quiescence.

Use the portable [state and delivery](../references/state-delivery.md) pause
protocol, executed by the current coordinator only. Preserve `draining`/`paused`
through compaction, resume, and any existing loop. Do not install hooks/loops;
if an existing mechanism tries to continue, retain the pause and report the
conflict. Do not bypass harness limits to finish a drain.
