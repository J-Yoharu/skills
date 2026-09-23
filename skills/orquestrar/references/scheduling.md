# Agents, dependencies, and resources

Use this reference for multi-unit dependency/ownership questions or stalled workers,
not for routine one-unit setup. The ordinary execution choice is in `SKILL.md`.

**Fixed root topology:** the current session coordinates and workers implement.
Only subagents use the catalog or escalation; there is no `coordinate` subagent or
delegated coordination, and the chat's model/effort never changes.

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

## Delegating work

Product units go to workers; the coordinator keeps coordination and integration and
edits directly only for small adjustments. Match the worker role to the unit:
`mechanical` for closed edits, `implement` for ordinary features, `deep` or
`critical` for hard algorithms, exactness, concurrency or high-risk contracts.
Reuse one worker for cohesive corrections and group tiny related units in one
order. Do not delegate an already solved lookup or duplicate reading. A worker may
run local tests and self-check, but this never replaces required independent review.

First establish whether a suitable native subagent exists. Apply
[model routing](model-routing.md) only when choosing an actual subagent. Model and
effort are separate decisions. Use suitable existing profiles and actually exposed
capacity. Uncertain rules, migrations, or concurrency bugs must not be downgraded
because the patch is short. Record the model you requested, or `inherited`.
Do not modify global settings to complete a unit.

## Dependencies and ownership

Defaults: up to two writers for independent units with disjoint write scopes in one
tree (otherwise one); up to two parallel readers when useful; one heavy process per
resource with unknown capacity. These are adjustable initial
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
Use the checkpoint's existing `active_agents` observations, not another registry:
`id, role, unit, checkout, input_revision, write_scope, state`; add a result reference
and model metadata when observed. Prepare these fields before spawn, then persist
the actual returned ID/state before unrelated work or waiting. See the inline entry
in the core; do not reverse-engineer the helper. Unknown spawn outcomes require
reconciliation before replacement. Confirmed terminal entries move to `agent_history`.

Use actual harness states to determine whether messaging or resuming is valid.
Avoid immediate repeated polling; wait with the appropriate tool. Failure or
timeout does not prove a process died: check before redispatch. An orphan agent
may keep writing; resolve ownership before creating a replacement writer.

Reuse workers for corrections and continuity in the same domain. Use fresh
context for changed objectives/contracts, contaminated context, or repeatedly
failed strategies. Close completed agents after collecting and persisting their
results. Persisted IDs identify observations; they do not guarantee native-agent
resumption in another session.

Two cycles without progress on a defect trigger diagnosis/escalation, not approval
of failure. Distinguish environmental failure from regression, verifying the base
when necessary. Without an evidenced path forward, block with a diagnosis while
other independent nodes remain eligible during normal execution.

## Integration and consumers

`worker_finished` does not satisfy a dependency. Inspect the diff, review, verify,
and make the result available in the consumer checkout through an authorized
mechanism. Then mark the piece `integrated` and record its commit or contract reference.

For stacked branches, record parent branch and parent SHA. Rebase, merge, and
cherry-pick follow project policy; do not rewrite published history for convenience.
A base change invalidates affected integration evidence and requires checking the
new diff. Without integration authorization, deliver the artifact and keep the
dependency blocked for consumers that do not yet have it.

## Dispatch during a pause

Check `control` before spawn, a follow-up starting a new unit, or a coordinator adjustment.
`draining` allows only closing the frozen IDs, including review/corrections, never
the batch's next card. `paused`/`interrupted` block dispatch until reconciled resume.
Free capacity does not override this rule. The protocol and exceptions live in
[state and delivery](state-delivery.md); do not create a second pause policy in
this scheduler or in agent presets.

For a batch, the same worker returns each unit before receiving coordinator
clearance for the next; pause blocks that clearance. No per-unit user approval is
required. If an already dispatched tool started another write before receiving
the pause, record the race and reconcile ownership. Do not hide the extra unit or
claim a clean pause. Explicitly replan only the stabilization needed for that
work without releasing the rest of the batch.

## Route the next decision, not a fixed ceremony

Before each step, ask what observable result would unblock this unit. If the
contract is missing, do one targeted investigation; do not launch an implementer
and reviewer to guess independently. Understood work gets one bounded implementer
with a precise work order; extra readers need distinct unanswered questions. Test/review stable outcomes rather
than have a reviewer chase a moving tree.

Check required review and test availability before coding. Missing independent
review is not repaired by raising reasoning effort, changing the coordinator,
retrying unsupported spawn fields or calling self-review independent. Useful
authorized implementation may proceed with that limitation disclosed, but its
acceptance stays pending. Once no ready work remains, produce a blocked result
with the completed diff/tests and the exact missing capability.

Every helper call, investigation or child needs a purpose and a return condition.
For optional profile/routing maintenance, allow one initial attempt and at most
one evidence-backed correction. No change in evidence means no identical retry.
Use native inherited subagents when appropriate, or live sources without cache;
keep actual mandatory gates intact. Model/runtime configuration is not a new
implementation task. These limits do not shorten legitimate tests or graceful
draining of already active units.

A completed worker becomes reusable context, not permission to start its next
card. Preserve per-unit authorization by the coordinator, including during pause.
Do not use a blocked successor as a reason to reimplement its already validated
producer.


Before the first writer, require the checkpoint round trip in
[state and delivery](state-delivery.md). Reuse its location and the scoped source
map thereafter. Keep long-run dependency outlines and detail the next frontier;
a one-unit task needs no separate planner. Persistence failure freezes new lanes,
not just the unit that happened to report it.
