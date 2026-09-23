# State, delivery and recovery

The ordinary save/read contract is in `SKILL.md`; do not read this file to repeat
that contract. Use **Persistence recovery** for a storage problem, **Graceful pause** or
**Resuming in the same or another session** when control changes, **Delivery** for an authorized nonlocal delivery.
Read other sections only for a current state/dependency question.

## Persistence recovery

Use project state, otherwise the workspace `.orquestrar/runs/<run-id>/run.json`.
Project state still passes each status change through `verify.py checkpoint-check`
with the previous and next run documents (see `SKILL.md`); a project rule against
state files never disables the unit gates.
Resolve the real path/permissions including symlinks. Known protected paths such as
`.git` are not new write candidates. Readable legacy state is not write permission.
One coordinator owns each run; a different worktree does not imply shared ownership.

If the first destination fails, disclose it and try **one known permitted** workspace
fallback. An exclusive project destination forbids fallback. Do not search for
writable directories, widen permissions, change ignore rules or follow an escaping
symlink. Save and parse/compare the real content before any product writer. If this
cannot succeed, stop recovery-dependent work; never silently select a nonresumable
mode because a task is small. Only the user can explicitly choose that exception.

On relocation, reconcile sources, checkout and writer quiescence first. Preserve
the original bytes, record the origin in the new copy and announce its new path.
On mid-run write failure, freeze new dispatch, preserve the last readable version
and code, safely close active work where possible, and report the unpersisted delta.
Without a successful new save/read, no durable completion or clean resumable pause.

Use the project's tested atomic API or `verify.py checkpoint-save` as specified in
`SKILL.md`. The bundled helper validates before replacement, requires the prior
state token and a cooperative local lock, flushes, replaces on the same filesystem,
and validates read-back. A directory fsync failure after replacement is reported as
an uncertain save, never success. Reread and reconcile before retrying. A crash can
leave `run.json.lock` with `owner.json` (PID, time, run); never remove it on age alone. Confirm owner termination and
inspect the checkpoint/owned temporary first. It is not a distributed lock or a
sandbox against hostile filesystem mutations. Respect native sandbox permissions.

**Malformed/legacy checkpoint:** first preserve the original bytes. Do not fix
schema errors until the existing record is overwritten, loop on validation, or map
`verified` to delivered without evidence. Recover actual sources, checkouts,
permissions, units and pending writers. If the original cannot pass its reader,
write a reconciled canonical record to a new authorized path using `--expected
missing`, recording `recovered_from` with original locator and hash. Announce the
new canonical path, keep the original, and do not continue unless the recovered
facts and required quality gates support it. No automatic completion or migration.

## Proportional state and output

A single unit needs identity/objective, source revisions, permissions, checkout,
criteria/scope, control, current status and next action; add evidence and reviewer
observations when known. The [run example](../assets/run.example.json) illustrates optional multi-unit
fields; do not load or copy the whole example for one unit. Preserve unknown legacy fields/history.
No fake coordinator metadata, empty specialist maps or duplicate copies of profile
sections. Observed agent/model details belong only to agents that actually ran.

The helper parses/compares the full saved update and returns path, run ID,
result/control, task counts, next action and a state token. The token refers to
observed bytes; do not regenerate it to conceal a concurrent edit. Do not `cat run.json` after
every update or print accumulated logs. On resume load the stable decision/permission
map and active/next units; open referenced older evidence when relevant. Never infer
that unprinted fields were checked without actually parsing/comparing them.

Keep large evidence and completed-unit details by reference once useful; use the
existing project format, not a new storage framework. No forced file splitting or
arbitrary line/token caps. Do not erase history to save context. One write/read may
cover both the last unit and final closure. Persist before a long worker/gate or an
ambiguous remote operation so its identity/result can be reconciled after a crash.
Checkpoint updates alone do not invalidate tests. A profile failure does not
waive a required checkpoint.

## States and transitions

Unit state: `pending → running → implemented → reviewing → verified → integrated
→ delivered`. `blocked` and `paused` preserve the last step/evidence. When
self-review is allowed, record it and pass through `reviewing` without inventing an agent.

`verified` means the unit candidate passed its gate. `integrated` means the result
is available in the base/tree needed by consumers with sufficient integration
evidence. In local mode in one checkout, these may coincide; explain the
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

`result` is additive to schema 1: absent legacy values read as `open`; new saves
must write `open|completed`. It is independent of the control latch. A completed
result requires all selected units at stable integration/delivery boundaries,
per-unit evidence references and empty confirmed active agents/processes. It
suppresses dispatch even though control stays `running`. Keep remaining graph
units pending using `selected_tasks` only when that scope was authorized (for
example `--ate`). New scope after completion starts a linked run, not silent reopening.

`control` is additive to schema 1: `state` is `running|draining|paused|interrupted`;
`reason` and `requested_at` record the pause; `drain_units` stores frozen IDs.
Only unresolved/current activity belongs in `active_agents`/`active_processes`;
move finished observations to `agent_history`/`process_history`. A clean pause
requires empty, confirmed `active_agents` and `active_processes`;
retained services belong in `retained_resources`. These fields record observations,
not produce them. The helper rejects a declared pause with active units or an
incomplete drain; the coordinator still evaluates evidence and delivery.

## Delivery

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

## Graceful pause

A pause for review, session transfer, or another activity means **drain**: start no
new units and finish those that already crossed their start boundary. "Stop now"
means immediate interruption with preservation, not drain. This applies to serial
and parallel work. The current chat remains the coordinator.

### 1. Record before dispatch

In the same run checkpoint, write `control.state: draining`, reason, time, and
`drain_units`: IDs of started units not yet at a stable boundary. Include
implementation, running reviews/gates, and pending integration; exclude planned
work, a worker's queue, and unstarted consumers. Record active agents and ongoing
operations, including publication with an ambiguous result. Only the coordinator
writes, using the existing atomic-write policy and a brief read-back confirmation. Do not add a daemon, queue, hook,
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
- Finished units, checkouts/branches/HEAD, and evidence references.
- Source locators **with observed revisions**, applicable test command/environment,
  and whether required review actually ran; paths alone cannot establish freshness.
- Necessary decisions/contracts and pending synchronization/publication.
- Finished or unknown agents/processes, retained resources, and ownership.
- The next **unstarted** unit, first resume action, and constraints.

Save the final version once with `control.state: paused`, `result: open`, using
the previous state token and the helper/API; return its compact receipt, then report a clean pause in the user's language with
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

## Resuming in the same or another session

"Review what you did", opening the repository, or reading the checkpoint does
**not** authorize continuation. An explicit natural-language or `--retomar` request
authorizes reconciliation; return to `running` only after the checks below.
With the bundled writer, pass `--resume` on that one transition. This is an
acknowledgment of the user's request, not a source of authorization.
If asked only to finish an interrupted pause, return to `draining` with the same
set, not to backlog execution.

Read local instructions, the specified checkpoint, and relevant usable profile
sections (or their live source locators when cache is unavailable).
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

Default workspace persistence is **machine-local** unless explicitly transferred;
it does not automatically travel with a clone/push. For another session in the same checkout, its path suffices. For
another machine, transfer the checkpoint **and** code/evidence absent from the
remote by an authorized method. A text summary does not transfer uncommitted files.
Do not promise remote backup when state is only local.


The current chat always resumes coordination; previous model/effort is history,
not configuration. Do not create a coordinator agent. Cache maintenance never
precedes latching a pause or becomes a prerequisite to recovering finished work.
