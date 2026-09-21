# Agents, dependencies, and resources

**Fixed root topology:** the current session's model is the coordinator. `auto`,
`solo`, and `delegado` change work distribution, never who coordinates or the chat's
model/effort. Only subagents use the catalog or escalation; there is no
`coordinate` subagent or delegated coordination.

## Units and execution path

Plan an acyclic graph of outcomes, not just API ordering. A dependency records
what must be available: contract, commit, generated artifact, or environment.
Ordered issue numbers do not prove dependencies. Cycles are planning conflicts:
group inseparable work or clarify contracts rather than pretend an impossible
graph is executable.

External IDs and internal IDs differ. A multi-repository unit has traceable pieces;
it finishes only when all meet acceptance and integration requirements. A worker
batch may cover small cohesive cards while retaining evidence per card. Sharing
context does not dictate one PR: delivery policy is separate.

`--ate X` includes X and the transitive closure of its prerequisites. Verify
already delivered prerequisites; do not redo them. Do not execute descendants
beyond that boundary. User/board priorities precede local optimization; among
equivalent items, prefer work that unblocks consumers. Do not invent estimates.

## Deciding whether to delegate

Delegate a bounded outcome with at least one concrete benefit: context isolation,
independent investigation, review separate from the author, specialist capability,
or overlap between independent work.

Do not delegate an already solved lookup, duplicate reading, fragment a three-line
edit, or meet a subagent quota. In `solo`, the coordinator implements; in
`delegado`, it retains coordination and integration. A worker may implement, run
local tests, and self-review, but this never replaces required independent review.

Apply [model routing](model-routing.md) before choosing a native agent. Model and
effort are separate decisions. Use suitable existing profiles and actually exposed
capacity. Uncertain rules, migrations, or concurrency bugs must not be downgraded
because the patch is short. Record `requested`, `effective`, and confirmation
origin; `effective: unknown` is better than unverifiable claims. Do not modify
global settings to complete a unit.

## Safe parallelism

Conservative defaults: one writer; up to two parallel readers when useful; one
heavy process per resource with unknown capacity. These are adjustable initial
ceilings, not slot-filling requirements. Increase only with observed capacity and
authorization; reduce for low memory, contention, instability, or excessive rework.

Before starting additional authorized writers, verify:
- Independent trees/branches, nonoverlapping file ownership, and compatible contracts.
- Shared integration contract, available dependencies, and recorded bases.
- Ports, Compose project names, databases, queues, writable caches, emulators, and
  external resources are isolated or protected by mutual exclusion.
- Serial integration has an owner and a gate for the combined candidate.

Never run concurrent writers in a shared tree, even when they claim different
files: Git's index, generators, and formatters may overlap. Different worktrees
of one repository still carry semantic risk. A worktree is neither a security
sandbox nor database isolation.

Preserve native project locks. If a lock serializes all containers/E2E, obey it;
apparent restrictiveness is not evidence that it is obsolete. Do not introduce
`flock` where unavailable. Without a verifiable lock, coordinate exclusion and
allow one active heavy process per resource. If another agent/session can touch
the resource without real exclusion, do not promise safety: serialize, isolate,
or mark the step blocked.

Acquire resources in a stable order, or all before starting, to avoid deadlock.
Never kill another person's/run's process to free memory. Waiting must be visible
and monitored. Without an active tool that can wait, persist the pause rather
than promise autonomous continuation after responding.

## Agent lifecycle

Only the coordinator starts/stops agents, including reviewers and specialists.
Keep a registry: `session_agent_id, role, unit, checkout, input_revision,
write_scope, state, result_ref, model_requested, model_effective`.

Use actual harness states to determine whether messaging or resuming is valid.
Avoid immediate repeated polling; wait with the appropriate tool. Failure or
timeout does not prove a process died: check before redispatch. An orphan agent
may keep writing; resolve ownership before creating a replacement writer.

Reuse workers for corrections and continuity in the same domain. Use fresh
context for changed objectives/contracts, contaminated context, or repeatedly
failed strategies. Close completed agents after collecting and persisting their
results. Session IDs are not durable state.

Two cycles without progress on a defect trigger diagnosis/escalation, not approval
of failure. Distinguish environmental failure from regression, verifying the base
when necessary. Without an evidenced path forward, block with a diagnosis while
other independent nodes remain eligible during normal execution.

## Integration and consumers

`worker_finished` does not satisfy a dependency. Inspect the diff, review, verify,
and make the result available in the consumer checkout through an authorized
mechanism. Then mark the piece `integrated` and record its commit or contract fingerprint.

For stacked branches, record parent branch and parent SHA. Rebase, merge, and
cherry-pick follow project policy; do not rewrite published history for convenience.
A base change invalidates affected integration evidence and requires checking the
new diff. Without integration authorization, deliver the artifact and keep the
dependency blocked for consumers that do not yet have it.

## Dispatch during a pause

Check `control` before spawn, a follow-up starting a new unit, or a `solo` unit.
`draining` allows only closing the frozen IDs, including review/corrections, never
the batch's next card. `paused`/`interrupted` block dispatch until reconciled resume.
Free capacity does not override this rule. The protocol and exceptions live in
[state and delivery](state-delivery.md); do not create a second pause policy in
this scheduler or native presets.

For a batch, the same worker returns each unit before receiving coordinator
clearance for the next; pause blocks that clearance. No per-unit user approval is
required. If an already dispatched tool started another write before receiving
the pause, record the race and reconcile ownership. Do not hide the extra unit or
claim a clean pause. Explicitly replan only the stabilization needed for that
work without releasing the rest of the batch.
