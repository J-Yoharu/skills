# State, delivery, and resumption

## A profile is not a checkpoint

Load the project profile on every invocation; it survives multiple runs. Reference
its digest in the run instead of copying it. Runtime inventory belongs to one
session; rediscover capabilities after restart. Execution does not edit human
overrides. See [project profile](project-profile.md).

## Minimal durable state

Reuse project artifacts. Do not create a second board or planning system. One
`run.json` suffices as a checkpoint; large evidence artifacts live alongside it
and are referenced. Only the coordinator writes this state. Use the existing
atomic replacement mechanism; otherwise, write a complete new checkpoint before
pointing to it. Do not delete the previous one prematurely.

Without an existing Git convention, use the absolute directory returned by
`git -C <checkout> rev-parse --path-format=absolute --git-common-dir`, under
`orquestrar/runs/<run-id>/`. Confirm installed-command support; resolve the relative
path manually if needed. This keeps operational files out of PRs and shares state
between a repository's worktrees. For multiple repositories, choose a coordinating
root and record checkouts by identity.

Without Git, use the user/project's designated state area; otherwise announce a
local state directory outside product files before writing. If only `/tmp` is
available, disclose volatility and preserve an authorized copy before the session
ends. Do not describe a temporary file as durable persistence.

Minimum state: schema version, run ID, objective, sources/revisions, decisions,
permissions, reuse map, repositories/bases, units/dependencies, session agents,
evidence, deliveries, pending synchronization, and next action. Do not store
tokens, `.env` contents, or unnecessary personal data.

## States and transitions

Unit state: `pending → running → implemented → reviewing → verified → integrated
→ delivered`. `blocked` and `paused` preserve the last step/evidence. When
self-review is allowed, record it and pass through `reviewing` without inventing an agent.

`verified` means the unit candidate passed its gate. `integrated` means the result
is available in the base/tree needed by consumers with sufficient integration
evidence. In solo/local mode in one checkout, these may coincide; explain the
evidence. `delivered` follows delivery policy, not necessarily merge or final
product acceptance.

Trackers have their own states; do not map them by name. Separate
`execution_status`, `delivery_status`, and `tracker_status` when necessary.
A synchronization failure is `sync_pending`; it does not reset code to `pending`.

`verify.py plan --file <run.json> [--until <id>]` validates IDs, dependencies,
cycles, and declared control. `dependency_ready` describes the graph;
`dispatch_ready` is empty unless `control.state` is `running`. Neither grants
resources/permissions nor observes processes. Closing a drain uses only
`drain_remaining`; this is not an automatic dispatch queue.

`control` is additive to schema 1: `state` is `running|draining|paused|interrupted`;
`reason` and `requested_at` record the pause; `drain_units` stores frozen IDs.
A clean pause requires empty, confirmed `active_agents` and `active_processes`;
retained services belong in `retained_resources`. These fields record observations,
not produce them. The helper rejects a declared pause with active units or an
incomplete drain; the coordinator still evaluates evidence and delivery.

## Permissions and Git strategy

Record scope and authorization origin for editing, testing, branch creation,
commit, push, PR creation/updates, tracker writes, task closure, merge, deployment,
and data operations. A convention explains how; it never overrides an explicit
prohibition. This skill grants no access denied by the harness. Do not enable
confirmation-free modes or remove hooks to keep the workflow moving.

Without a project decision, implement and verify locally; do not create issues or
publish. An explicit request for commit/push/PR delivery, or unambiguous delegation
in trusted project instructions, can authorize that flow within its limits.
Merge, release/deploy, and destructive operations require specific scope and
permission; never infer them from "finish the implementation".

Strategies are independent of the task provider:
- `local`: verified changes and checkpoint, without requiring a Git remote.
- `aggregate`: one branch/PR per run and repository, preserving unit traceability.
- `per-slice`: one branch/PR per unit and repository, respecting actual independence.
- `stacked`: dependent branches based on earlier PR branches, with order/revision recorded.

Preserve project merge strategy. Do not introduce squash/rebase where ancestry is
required. Run Git in the correct checkout and select files explicitly; never use
`git add -A` on a tree containing others' work. An unrelated dirty tree may be
preserved by using an authorized clean worktree; overlap or impossible isolation
requires stopping before editing.

## Publication and write-back

Before the first external write, record exact destination and authorized operation.
Before each attempt, check whether a delivery/record already exists for
`run-id + unit + repository + operation`. Use returned PR/comment IDs. Reread
state/revision before updating and use version preconditions where available.
Without CAS, read immediately before a minimal patch; do not promise atomicity.

Reconcile timeouts/ambiguous responses before retrying. Record results locally
before mirroring them to the tracker. Do not create a comment per token or update
status in a loop; prefer an identified run summary or material project events.

For partial/multi-repository pieces, use nonclosing references. Automatic closure
belongs only in the designated artifact after all acceptance/policy criteria are
met. Do not put `Closes` on every PR and later reopen the issue. Epic completion is
separate from child completion and still requires authorization.

A PR link does not prove merge; a board status does not prove tests. Check actual
revision/state. Deliver pending items and merge order at the end; do not execute
that order without recorded permission.

## Graceful pause: finish active work, not the remainder

A pause for review, session transfer, or another activity means **drain**: start no
new units and finish those that already crossed their start boundary. "Stop now"
means immediate interruption with preservation, not drain. This applies in solo,
delegated, and parallel modes. The current chat remains the coordinator.

### 1. Record before dispatch

In the same run checkpoint, write `control.state: draining`, reason, time, and
`drain_units`: IDs of started units not yet at a stable boundary. Include
implementation, running reviews/gates, and pending integration; exclude planned
work, a worker's queue, and unstarted consumers. Record active agents and ongoing
operations, including publication with an ambiguous result. Only the coordinator
writes, using the existing atomic-write policy. Do not add a daemon, queue, hook,
second control file, or another coordinator.

The set is **frozen**. Repeated pause requests are idempotent: they neither expand
the set nor redefine starts/acceptance to shorten work. Tell the user which units
will finish and which will not start. Check this latch before every dispatch and
before starting a unit in the coordinating chat.

### 2. Finish the frozen boundaries

Tell workers to finish their current unit, tests, and necessary corrections without
taking the next batch unit. Collect results from active readers without continuing
speculative exploration. A **reviewer**, specialist, or replacement worker may be
opened only when necessary to close a frozen unit; this authorizes neither new
objectives nor concurrent writers.

Apply normal acceptance, review, and verification. Resolve blocking findings and
verify required integration. Reuse valid gates; do not omit a required gate just
because it is slow. Preserve locks and serial integration. Do not start consumers
or successors, even in a free lane.

A multi-repository unit includes only pieces already defined as its coherent
boundary. Closing may finish those necessary pieces, not pull a new graph unit
into scope. If the boundary needs unplanned work, record a blocker rather than
silently expand the drain. Do not mark a card/epic complete while its other units
remain pending.

### 3. Quiescence, persistence, and report

After collecting results, confirm through the harness/processes that no agent is
actively writing, no run gate/build/generator is still changing files, and no
external operation has an unknown result. Wait for normal completion and safely
release only owned resources. Keep needed shared services stable and list them
as retained, not as processes still requiring completion. A timeout or lost ID
never proves termination.

A clean pause requires frozen units verified and integrated when applicable,
required reviews resolved, a coherent product tree, and deliveries **due at that
boundary** resolved. Do not publish an epic's aggregate delivery merely to pause.
`local` allows complete, tested, uncommitted content. Commit if already allowed
and required; otherwise preserve files and describe their state. Do not use
`reset`, `stash`, or WIP commits to disguise a supposedly "clean" tree. Do not
include others' work. Push/PR remain subject to original authorization.

Update the same checkpoint, not just the conversation, with:
- Finished units, checkouts/branches/HEAD, and content/evidence identities.
- Necessary decisions/contracts and pending synchronization/publication.
- Finished or unknown agents/processes, retained resources, and ownership.
- The next **unstarted** unit, first resume action, and constraints.

Reread the saved checkpoint. Save/reread the final version with
`control.state: paused`, then report a clean pause in the user's language with
results, evidence, actual/pending publication, checkpoint path, and resume command.
Do not say it is safe to change sessions with an active or unknown writer.
Without persistence, provide a conversational handoff and disclose the limitation
instead of claiming a verified durable pause.

### Honest exception: interruption

An immediate stop, unrecoverable error, missing authorization, failure without
progress, or actual context exhaustion requires `control.state: interrupted`, a
reason, and missing steps. Stop dispatch, use safe native interruption where
available, preserve files, and record agents/processes that could not be stopped.
Do not retry indefinitely to get green or bypass permissions. Do not unsafely
interrupt a noncancelable operation; state its risk and completion condition.
Explicitly distinguish an incomplete pause from a clean pause in the user's language.
If existing project hooks require literal phrases such as `Rodada concluída`,
`Pausa concluída`, or `Parada:`, preserve those phrases; do not translate the
integration contract. Otherwise, prose is localized and stored states stay unchanged.

## Session context

Manual pause needs no telemetry. The optional threshold is
`sections.resources.pause_context_used_percent` in project overrides/profile;
`null` or absence disables only the numeric trigger. No universal percentage is
imposed. An explicit request may set a threshold for this run; persist it as a
project preference only when requested.

The value is greater than 0 and less than 100 and means **context used**, not weekly
quota, cost, or progress. For example, 70 used means 30 remaining. Use only a
current, confirmed signal from the same session, available through a tool/metadata
or supplied by the user. Record value, unit, origin, and time. Without reliable
measurement, use `unknown`; do not estimate from conversation tokens. A statusline
visible to the user is not automatically visible to the model.

Check before a new unit/dispatch and after large returns, not by constant polling.
When the threshold is reached, use the same drain. This is a checkpoint observation,
not real-time monitoring or a guarantee of pausing at an exact percentage. Leave
headroom for review, corrections, and handoff; a large unit may exceed the reserve.
A real insufficient-context warning may trigger an earlier pause or interruption.
Do not change the coordinator's model/effort.

Compaction does not finish tests, transfer ownership, or cancel a recorded pause.
A later drop in context percentage does not release the latch. Do not automatically
invoke `/clear`, `/compact`, or another CLI to avoid pausing. Existing hooks or
telemetry may supply signals; this skill does not install monitoring by default.

## Resuming in the same or another session

"Review what you did", opening the repository, or reading the checkpoint does
**not** authorize continuation. An explicit natural-language or `--retomar` request
authorizes reconciliation; return to `running` only after the checks below.
If asked only to finish an interrupted pause, return to `draining` with the same
set, not to backlog execution.

Read local instructions, the validated profile, and the specified checkpoint.
Check source/checkout identities, changes since verification, permissions, and
pending operations. Resolve old agents/processes before claiming ownership.
Without access to the old harness, state is unknown; confirm quiescence or isolate
without competing for the same tree. Never presume an old agent ID can be reopened.

If a crash left `draining`, resume closure rather than new dispatch unless normal
continuation is explicitly requested. For `paused`, confirm the stable base.
For `interrupted`, prioritize the incomplete unit before the backlog. Legacy state
without `control` does not prove a clean pause; reconcile evidence and current intent.

Do not delete the checkpoint on resume. Update after reconciliation, preserving
pause history and pending work. Reuse existing work and valid evidence; revalidate
affected inputs only. Restart services only when required for the next step and
authorized.

Default `git-common-dir` persistence is **machine-local** and does not travel with
a clone/push. For another session in the same checkout, its path suffices. For
another machine, transfer the checkpoint **and** code/evidence absent from the
remote by an authorized method. A text summary does not transfer uncommitted files.
Do not promise remote backup when state is only local.

## Coordinator identity on resume

The coordinator is always the current session. Earlier model/effort metadata is
history, not configuration to restore. Reconcile the new session's agents and
capabilities; reusable routing remains subagent-only. Do not create an agent using
the old chat's model to resume coordination.
