# Another or partially capable harness

The current chat coordinates. A new adapter maps native capabilities; it does not
change product policy, add a second orchestrator or replace the chat's model/effort.

## Subagents

Observe only what the next assignment needs: native spawn/context, permissions,
model/effort controls, lifecycle and isolation. Do not infer APIs from model names.
No subagents means sequential work and a pending independent-review gate where
required. Native agents without model controls inherit the session model; record
`inherited`. Do not create a runtime to hide
a missing capability or call another CLI as a workaround.

Only the coordinator delegates. Review is a genuinely separate context, full scoped
diff and criteria, with read-only tools where supported. A prompt does not enforce
permissions. Confirm ownership/quiescence; timeouts and stale IDs are not proof.
Use the shared catalog policy only where native controls support it.

## Storage and control

Reuse project state or the authorized workspace default. Save/read before product
writes; project state still checks each status change with `verify.py checkpoint-check`. Without file/API persistence, do not promise recovery or a clean pause.
Map native events to portable `running`, `draining`, `paused`, `interrupted`
semantics without changing stored contracts. Read only relevant pause/recovery
sections when the event occurs.
No auto-installation, extra coordinator, timers or global configuration is required.
