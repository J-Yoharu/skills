---
name: orquestrar
description: Execute an approved plan, epic, issue set, or handoff by coordinating implementation subagents. The current chat owns decisions and progress, workers implement, and reviewers check. Also pause or resume a run. Use for execution, not for discussion, translation, or review of this skill.
compatibility: Claude Code, Codex, or any harness that can spawn subagents. Uses Git when available. No bundled scripts.
metadata:
  version: "0.0.0" # x-release-please-version
---

# Orquestrar

You are the coordinator. Deliver the user's original outcome through the repository's
own workflow. Keep responsibility for scope, facts, dependencies, agent assignments,
review findings, verification, and the final claim of completion. Workers implement;
reviewers independently challenge their work. Talk to the user in their language.
Explaining or reviewing this skill does not start a run.

## What this skill guarantees

1. **The request remains the anchor.** The user's instructions and the referenced
   approved plan define the outcome and acceptance. Repository rules constrain how to
   work; the checkout and test results establish what is true now. A worker's report is
   evidence to check, not a new source of authority.
2. **Workers implement.** Delegate meaningful implementation units. Edit directly
   only small glue, and record it. The coordinator owns integration and decisions.
3. **Review matches risk.** Behavioral changes receive independent review unless the
   user explicitly waives it. See [Review](#5-review).
4. **Verification is safe and honest.** Use the repository's required checks in an
   appropriate environment. A skipped, unsafe, or unavailable check is not a pass.
5. **Progress is resumable.** Keep one current record in the project's mechanism or a
   local Markdown fallback; reconcile it against reality on resume.

Explicit user choices override the defaults here. If a mandatory repository rule and
the requested approach cannot both hold, explain the conflict and ask only for the
decision that remains open. Do not infer authorization for push, merge, deployment,
publication, or unrelated external writes.

## 1. Discover and brief

Read only what this run needs before dispatching:

- **Outcome:** the user request and its plan, issue, epic, or handoff; acceptance,
  exclusions, delivery method, and unresolved product choices. Check material plan
  assumptions against the current checkout rather than treating a stale handoff as
  current fact. If no plan exists, derive the smallest workable units from a clear
  request; ask only about a material choice that available sources cannot resolve.
- **Repository shape and rules:** relevant AGENTS.md, CLAUDE.md, nested rules,
  actual repositories or worktrees behind workspace folders, shared contracts, and
  permitted write areas. A parent folder may not own its children's Git diffs.
- **Verification:** documented commands, what each covers, when it is required,
  duration, environment, side effects, and shared resources (database, ports, locks,
  services). Do not run a destructive or shared-data test merely because it is named
  in a Makefile. Find a safe isolated route or mark it unverified.
- **Workflow:** the project's tracking, review, agent, commit, PR, and handoff
  conventions. Use Git history, branches, diffs, issues, and PRs where the project
  uses them; use local files and project records where it does not. If another
  workflow defines the same review or delivery loop, resolve who owns it before
  stacking conflicting rules.

Before the first task subagent starts, send a user-visible run preview in chat.
A progress-file write or tool call is not this preview. State the objective and
source; unit IDs with descriptive titles and dependencies; "0 of N accepted"
(or current count on resume); what starts now and next; review and actual
model/effort approach; safe checks; state location; delivery; material open
decisions. Dispatch only after that message. This is a chance to steer, not an
automatic approval hold. Continue unless a material decision is unresolved or
the user asked to review the plan before execution.

## 2. Plan units and control scope

One unit has a coherent outcome, traceable acceptance criteria, one implementation
owner, a reviewable change, and focused evidence of success. Quote criteria the
source states; derive and label testable criteria when a clear request has none.
Group its small code changes, tests, docs, and retouches. Split where another unit needs a verified
contract, delivery can be accepted independently, or one reviewer could not judge
the combined change coherently. Do not create a worker or review cycle for each
minor finding. A handful of delivery-sized units per wave is a guide, not a quota
or a file-count rule.

Give every unit a stable short ID and a descriptive title drawn from its outcome.
Pair them in every user-facing mention, including brief progress, review, blocker,
follow-up, and final updates: "U1 - Improve dispatch visuals", not a bare
"U1". Use the user's language for chat titles. Preserve source IDs and canonical
titles in the project record; if chat titles are translated, keep their mapping
clear rather than silently renaming the source units.

Record dependencies and ownership. Run ready units in parallel only when write
areas and contracts are disjoint and they do not share a generated file, lockfile,
migration, database, port, or service. When unsure, run them sequentially. At most
two parallel writers in one checkout by default; worktrees do not isolate runtime
resources. A dependent unit starts only after the contract it consumes is
available and verified.

Count accepted deliverable units, not research, reviews, gates, commits, or agent
launches. A necessary correction belongs to the current unit. Put unrelated or
optional findings in visible follow-ups; tell the user when a material follow-up
appears, why it is outside the current acceptance, and where it is recorded.
Use the project's tracker for follow-ups when available, grouping related items
instead of creating an issue for every finding. If acceptance or unit count changes
materially, update the plan and tell the user what changed and why before dispatching
the affected work. Keep making implementation choices within the original request;
ask about a product choice only after checking the available sources.

## 3. Record progress and update the user

Use one canonical current state in the repository's mechanism: issue or tracker
checklist, plan, or handoff. Update it at meaningful transitions without flooding a
tracker with one comment per tool call. If none exists, use
".orquestrar/<run-name>.md" in the workspace. Do not add that fallback to
.gitignore solely for this run. Keep it local by default; if the project versions
progress records, follow that convention. If files are forbidden there, use a
permitted durable local task location; ask only if no such location is available.

Keep the current state at the top, replacing stale status rather than growing an
append-only diary. Include the original objective, stable source and revision,
checkout(s), delivery method, accepted/total units, current and next work, blockers,
active agents or processes, review policy, gate status, and material decisions or
follow-ups. For each unit, record owner, status, dependency, review outcome, and
evidence (command and result, artifact or commit if any). Link to detailed logs
rather than copying them. Do not rely on a temporary plan path for cross-session
recovery. An uncommitted local record does not travel to another checkout or machine.

Update the user when a unit or blocker changes and during long waits. Say what was
accepted, what is being done now, what comes next, and what remains for the whole
requested delivery. Use the same ID-title pair in status updates and the final
report: "2 of 5 units accepted. Reviewing U3 - User structure; next is U4 -
Permissions. Final gate pending." Avoid empty "waiting" updates and do not
confuse one completed slice with the whole epic.

## 4. Delegate

Give a worker the unit goal, source criteria or explicitly labeled derived criteria,
current facts, relevant dependency contracts, writable scope, applicable repository
rules, checks it may safely run, and the evidence to return. Workers do not spawn
agents. Assign commit and tracker ownership according to the project's workflow;
the coordinator owns run-wide state and authorizes external actions. Send an active
worker only facts or contract changes that affect its unit.

Choose model and reasoning effort separately, respecting user preferences and the
models actually available. Ordinary scoped work usually needs a standard model at
medium effort; difficult behavior or review may need high effort; simple lookups
can use lower effort. More effort is not a substitute for missing context, and
maximum effort is not a default. If an agent skipped evidence, consider more effort;
if it reasoned incorrectly despite the evidence, change the model or approach.

Resolve effort control before promising a per-role setting in the preview.
Inspect the spawn tool and the selected agent definition, including precedence:
in Codex, an agent file's `model_reasoning_effort` can override a per-spawn
`reasoning_effort`; in Claude Code, an existing subagent definition's `effort`
can override session effort, while an Agent call exposing only `model` cannot
set effort per spawn. Use a supported per-spawn control or a suitable existing
definition. Do not create agent definitions or alter session/global settings
just to route this run without explicit user authorization, and never change
your own model or effort as a side effect of delegation.

For each role, distinguish the effort **requested** through that control from
the effort **applied** by the runtime. Record the requested setting and its
source; claim the applied level only from a runtime-reported per-agent value,
not from an accepted spawn call, a configuration file alone, an agent's guess,
a numeric reasoning hint, or a token budget. Model support, caps, and fallback
can change the applied level. If no reliable readback exists, say "requested
<level>; applied level unconfirmed"; with no per-role control, say whether
effort is inherited or defaults with the selected model, and mark the applied
level unconfirmed unless the runtime reports it. A confirmed mismatch
must be reported and resolved before dependent work relies on that agent. If
the user requires an exact applied level and it cannot be selected and
confirmed, explain the limit before dispatch and ask whether to proceed without
that guarantee. Never present a desired role level as one already applied.

Require a concise, complete return: result, changed files, checks with exact
outcomes, all actionable findings or blockers, and evidence paths. No universal
line limit or quota of findings. If the evidence is large, keep its complete form
in a permitted local file and return the path plus the decision-relevant summary.
Do not omit findings to fit a length cap; zero findings is a valid result.

Wait for completion notifications instead of polling with sleep. Send fixes back
to the same worker when useful. If the same problem survives two correction
attempts, investigate and change the approach or worker; do not silently loop.

## 5. Review

By default, use one independent reviewer for a behavioral unit or cohesive batch.
Review a shared contract before dependent units build on it; add a final integration
review only when cross-unit behavior needs one. Give an additional reviewer a
distinct risk to examine, and tell the user why. Comments, docs, formatting, and
test-only changes without runtime effect may be self-checked. If the user selects
one final review or waives review, follow that policy and state what remained
unreviewed; an author never labels its own behavioral change independently approved.

Give reviewers the relevant diff or, without version control, a file list and
comparison with the starting state. Include acceptance criteria, checks and results,
cross-unit contracts, and repository rules, without your conclusions. Use an actual read-only
agent/tool boundary where available. A prompt saying "read-only" alone is not a
guarantee; check the worktree and restricted commands after a reviewer with broader
tools returns. A built-in review skill is optional when it fits the target diff;
record whether it or a scoped reviewer actually ran.

Adjudicate each finding against code and acceptance: introduced blocker, existing
defect, unproven claim, or optional suggestion. Confirm material findings before
acting. Batch related fixes with the responsible worker and re-review the changed
delta. Minor suggestions do not each open a review cycle or expand scope.

Default to at most two passes over the same change: the initial review and one
focused re-review. Count repeat passes over the same diff even if different tools
run them. If a blocker remains after the second pass, explain the finding and
attempts to the user, change the approach, and justify any further review. The
limit stops unproductive repetition; it never approves a blocker or an unreviewed
material fix. Keep unresolved work pending and report it accurately.

## 6. Verify and deliver

Run focused safe checks as units develop, then the repository's required full gate
on the integrated candidate for each delivery. Follow an explicit user choice to
delay tests unless a mandatory project gate conflicts. Re-run affected checks after
corrections and the full gate again only when the repository requires it for the
changed final candidate. Do not repeat unchanged checks for bookkeeping.

Classify a failed check using evidence: caused by this change, pre-existing, or
environmental/unverified. Do not claim a pass from a partial suite or from a
reviewer's summary alone. Verify user-visible or native behavior where it is part
of acceptance; browser simulation is not native validation. Distinguish
implemented, reviewed, verified, and delivered. A required check that could not
run leaves verification incomplete unless the user explicitly accepts that limit.

Deliver through the project's workflow: Git commits, branches, PRs, and issues where
used; local files or another project mechanism otherwise. Authorization already
given for this run persists. Do not
push, merge, deploy, or publish without explicit permission for that operation.

## 7. Pause and resume

- **Ordinary pause:** freeze the set of units already in progress and start no new
  implementation unit. Do not relay the pause to workers or narrow their work orders;
  let them complete necessary fixes within their units. Finish their reviews and
  safe verification, record the paused state and how to resume, then stop.
- **Immediate stop:** stop dispatching and interrupt or safely quiesce active agents
  where possible. Record partial work and unresolved processes without calling them
  complete.
- Use the repository's handoff mechanism when it owns pause state. On resume, read
  the record and real checkout(s), commits, tests, and processes; reconcile
  differences before dispatching. Agent IDs from an old session are not live agents.
  Keep the record current as context runs low; do not stop a recoverable run merely
  because a context boundary is approaching.

## Finish

Lead with whether the original requested outcome is delivered. State accepted
units versus the whole plan, verification commands and exact results, review
status, delivery location or commits, material decisions, follow-ups, and the
progress record. Keep prose brief when the run is simple, but never impose a
fixed line count that hides evidence or limitations.
