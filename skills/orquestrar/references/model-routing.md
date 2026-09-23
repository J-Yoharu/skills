# Model routing — subagents only

Use **Select one subagent** only for an actual child. The current chat remains the
coordinator, including resumption. There is no selectable
`coordinate`/`coordinator` role. Never change the chat's model or effort, launch a
replacement coordinator or restore a previous session's settings.

## Select one subagent

1. Inspect the native spawn tool and only the controls needed for this role:
   context, permissions, model/effort and wait/follow-up. No spawn tool means no
   inventory or policy lookup. No selection fields means the child inherits; record
   `inherited` and never invent native arguments.
2. Use [model-catalog.json](../assets/model-catalog.json) for the **one** role and
   harness, with the profile's `sections.models` when present. Read/filter that role's choices and
   referenced families; do not load all presets or create JSON just to launch one
   child. `review` stays review, never `mechanical` to save tokens. The catalog is
   policy, not an availability inventory or measured quality equivalence.
3. Apply an allowed supported choice through native fields or an existing matching
   preset. An inherited model still gives a genuinely independent context.
4. Record role, real agent ID and the model you requested (or `inherited`) in the
   agent entry. Reuse what you learned about the spawn tool for the rest of the
   session. Do not run test inference or change global settings to learn more.

Default roles are `lookup`/`mechanical` for closed, low-ambiguity contracts,
`explore` for bounded code questions, `implement` for ordinary work and `review`
for independent assessment. `critical` and `deep` require corresponding material
risk or unresolved reasoning, not a long conversation alone. The catalog's opt-in
`frontier` families require explicit authorization and observed availability in
any role, including one changed by an override (`opt_in: true` in the policy view).
These roles route workers only. An implementer also performing self-review is not
an independent reviewer.

## Native mechanics when unclear

Read only the applicable adapter's **Subagents** section:
[Codex](../adapters/codex.md#subagents),
[Claude Code](../adapters/claude-code.md#subagents), or
[generic](../adapters/generic.md#subagents). Installation sections are not needed
for a running implementation. Never register new presets as an incidental fix.

Only the coordinator spawns or requests follow-ups. Preserve read-only review and
writer ownership even when increasing capacity. A prompt is not permission
isolation; use native restrictions when available and disclose limitations.

## Read only the policy you need

```bash
python3 <skill>/scripts/route.py --show-policy --harness codex --role review
```

Substitute the actual harness/role, not the coordinator. The command returns that
role's choices and matching bindings only. It does not call a model, assert
availability or configure anything. Add `--overrides` (the profile path) only
when it has `sections.models`. Use this instead of printing
`harnesses`, all families or every preset. If these exact facts are already in
context, reuse them rather than run another lookup. If the spawn tool rejects the
chosen model, make at most one supported correction, then use adequate inherited
capacity or report a concrete blocker; do not loop on metadata repair.

## Escalation and continuity

Two cycles without progress require diagnosis: more effort cannot supply a missing
contract or environment. Reuse a worker for cohesive fixes. If a necessary model
change requires replacement, confirm the old writer stopped and transfer a faithful
handoff. For review, never use a writable critical/deep preset merely for its model.
After the difficult part, normal subsequent units can use the ordinary route.
Model changes do not relax acceptance, review, permissions or usage consent.

`--atualizar-modelos` revalidates only subagent routes; it neither installs profiles
nor changes the chat. Catalog age may justify explicit maintenance, not rediscovery
on every task.
