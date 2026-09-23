# Generic source contract

There is no provider enum, brand-based precedence, or product-specific adapter.
The base repository defines locators, access methods, and rules. Discover them in
instructions, indexes, plans, scripts, and explicit references. Reuse an existing
project skill/script before building a client or duplicating integration logic.

A source may have one or more roles: `work`, `requirements`, `decisions`,
`engineering`, `delivery`, `verification`, `progress`. A role does not require a
service: one file may serve every role.

Record only what is necessary:
- Stable ID and nonsecret locator; open-ended resource type, not a brand enum.
- Subjects for which it is authoritative and evidence of approval/precedence.
- Relationship to the request/repository; canonical read method and capabilities.
- Revision/ETag/modification time when available; read time and outcome.
- Relevant sections, direct relationships, and write-reconciliation method.

A title or shortened URL is insufficient identity. Local paths are relative to
the specified root; external URLs/IDs must match the actual tool schema. Scripts
are referenced, not automatically executed merely because a profile lists them.
Confirm commands and authorization against current instructions.

## Reading and invalidation

Read the referenced resource and its direct links first. Expand only to resolve
material gaps. Use actual pagination/filters for the scope; never treat a partial
response as a complete list. Store version information, not indiscriminate full
copies. Bind acceptance to the observed revision in the checkpoint or immutable
referenced evidence; a pointer to a profile that will be refreshed is not enough.
Reuse provider revisions, commits for unchanged files, or existing content digests.
Hash only relevant unversioned inputs when needed, not the repository or every
source. If no version is available, record that limit and reread the required
excerpt before reuse; a read timestamp does not establish unchanged content.

A cache remembers where to look; it does not certify unchanged remote state.
A document update invalidates the affected subject and dependent work orders,
not every repository. An inaccessible source is `unverified`; an export covers
only its supplied revision. Missing indispensable requirements block the unit.

## Writes

Finding a tool does not authorize writes. Only the coordinator publishes within
current permissions. Discover IDs, fields, and statuses from actual data. Read
before writing, apply a minimal patch, use revision preconditions when available,
and reconcile ambiguous responses. Preserve `sync_pending` and returned IDs.
Do not create another task because a comment failed. `Done` depends on project
criteria, not a state's name. See [state and delivery](state-delivery.md).
