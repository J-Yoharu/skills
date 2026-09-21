# Persistent project profile

## Three lifetimes

**Profile:** reusable project conventions and evidence. **Run:** one implementation's
progress. **Runtime:** capabilities observed in a session. Do not store task status,
tokens, credentials, secret-bearing executed commands, temporary permissions, or
assumed model identities in a shareable profile.

Reuse existing files when the project defines equivalent conventions. Otherwise:

```text
<coordinating-root>/.orquestrar/profile.json    # generated, readable, replaceable
<coordinating-root>/.orquestrar/overrides.json  # optional, user-maintained
<git-common-dir>/orquestrar/runs/<id>/         # checkpoints/evidence
<git-common-dir>/orquestrar/runtime/<session-id>.json # ephemeral inventory
```

Without Git, use the designated state area; fall back to `.orquestrar/local/` and
announce it. Do not modify `.gitignore`, AGENTS.md, CLAUDE.md, or global settings
as a side effect. Do not commit these files without authorization. When checkout
metadata is prohibited, store the profile in the project's state area and record
its locator through existing conventions. Never silently switch locations.

Profile paths are relative to the coordinating root. In multi-repository
workspaces, record each repository's identity and rule scope. Reuse a root profile
in a sub-repository only when the relationship is declared. Stricter local rules
still apply. Revalidate anchors and context in a new worktree/clone; absolute paths,
permissions, and another machine's runtime are not portable.

## Automatic loading

1. On every invocation/resume, resolve current scope/instructions, profile, and overrides.
2. Check schema, accidental corruption, and referenced evidence. A hash is not
   authentication: also check the profile's origin and trustworthiness.
3. Compare anchor content and monitored path sets. Detect new/removed files,
   new rules, and changes to workspace relationships.
4. Reread invalidated sections and dependents only. A code commit does not by
   itself invalidate the whole workflow; it invalidates dependent reuse/evidence.
5. Revalidate relevant external sources before material use. An unchanged local
   profile does not imply an unchanged remote document. Without a revision API,
   reread the necessary excerpt.
6. Apply human overrides field by field, without authorizing what policy prohibits.
7. Save the updated profile before delegation when local writes are allowed.
8. Generate/validate session inventory and effective model policy separately.

The default **7-day TTL** is an adjustable initial policy: it requests section
revalidation, not a full scan. Cheap file checks still apply before use within
that period. Age never overrides a detected change. `check` alone does not renew
TTL; only `save` after real revalidation renews evidence. A failed check cannot
mark a section current. Mid-run changes invalidate affected units before the next
spawn/delivery without deleting completed work.

## Content and editing

Typical sections: `instructions`, `workflow`, `sources`, `repositories`,
`verification`, `delivery`, `resources`, `reuse`, `models`. Store concise values,
evidence, and confirmed/inferred/unknown confidence. Model settings point to
policy; account availability belongs to runtime.

See [profile.example.json](../assets/profile.example.json). Anchors are paths/globs
limited to scope; do not read secrets to generate a cache. Sections without anchors
or known revisions require semantic revalidation, never automatic validity.
New relevant directories require updating anchors. The helper cannot infer what
you forgot to monitor.

Overrides are JSON objects by section. Maps merge recursively; lists and scalars
replace values. `null` is an explicit value, not authorization. Use `[]` to remove
a list. Validate the result and conflicts with current instructions. Honor a
different override filename when the project points to it.

This skill does not edit overrides. When a generated profile has human edits,
stop automatic replacement: show differences and preserve content. Prefer moving
human intent into overrides; regeneration that discards edits requires an explicit
request. Expired TTL does not permit erasing customizations. `--redescobrir`
preserves overrides and runs; it is not a destructive project reset.

## Writes and optional helper

Use atomic writes and optimistic concurrency. Concurrent coordinators must not
lose each other's updates. `scripts/profile.py` uses an exclusive-create lock,
expected digest, previous-version backup, and atomic replacement. An existing
lock causes an error; never delete someone else's lock to continue. These locks
protect metadata only, not tests or code writers.

```bash
python3 <skill>/scripts/profile.py check --root <root> --profile <profile>
python3 <skill>/scripts/profile.py save --root <root> --draft <draft.json> \
  --profile <profile> --expected missing
```

For updates, `--expected` is the SHA-256 of the bytes read, returned by `check`.
Create a draft after revalidating sections; do not use `save` just to renew dates.
For selective invalidation, `save` preserves timestamps/baselines of sections not
listed in `--sections` and rejects their modification. Do not rewrite an external
profile with an unknown schema; follow its own format. The helper neither
interprets Markdown nor reads external sources; those remain agent work.

`--descobrir` saves a profile without creating an implementation run, branch, or
publication. `--inspecionar` never writes. `--sem-cache` bypasses only the generated
profile, not project rules. Disclose all persistence failures; do not claim a
resumable checkpoint that does not exist.

## Boundary of the models section

`sections.models` holds **subagent** policy/overrides only, explicitly marked
`selection_scope: subagents`. Do not persist a preferred coordinator model/effort
or reconfigure the chat when loading a profile.

Observable coordinator model/effort may appear in `runtime.parent` or a run's
observation record with actual metadata; unavailable values remain null. These
are observations, not configuration or authorization. In a new session, observe
again instead of restoring the previous model. Subagent presets remain reusable.

Version 2.1 profiles without `selection_scope` remain readable. The resolver treats
policy as subagent-only, ignores legacy `coordinate` entries with a warning, and
rejects routing them. Preserve files/overrides and mention optional cleanup;
this correction does not require full rediscovery.
