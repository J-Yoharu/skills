# Contextual discovery without fixed providers

## When and how far

Read this reference only when the source/workspace boundary is unclear. Start with
live scope/instructions and the actual plan, not a library of skill references.
Reuse relevant profile sections; a first invocation does not require a full manual.
The profile speeds up navigation; it never replaces reading material requirements
for the current unit.

## Bounded search

1. Read the request and instructions already supplied by the harness. Resolve CWD
   and, in Git, `git -C <cwd> rev-parse --show-toplevel`. Without Git or a declared
   workspace, start at CWD; do not search its parent for a better-looking project.
2. Preserve native instruction hierarchy. For ancestor rules not already loaded,
   check only the harness's known filenames on the ancestor chain (for example
   `AGENTS.md` or `CLAUDE.md`), not their siblings/subtrees. Check applicable nested
   rules on paths actually being edited. Permission errors do not justify bypasses.
3. Read the root's relevant index/README and the specifically referenced plan,
   and profile. Start reuse discovery in the named module/test paths.
   Use filename/symbol search before full contents. Every recursive search has an
   explicit authorized root, a question and a bounded result set.
4. If that scope has no answer, narrow/refine the question once or use a targeted
   filename/symbol search in the **same checkout**. For each expansion beyond it,
   require a concrete workspace declaration, import, plan path or dependency, and
   verify the target is permitted. Follow only that target. A parent with many
   repositories, a remote URL or a symlink is not workspace/write authorization.
5. Follow external references through the repository's canonical access method
   and actual tool schemas; use [source contract](source-contract.md). Record the
   link and authority, not a full provider inventory or account-wide search.
6. Stop when the next outcome, acceptance, invariants, canonical capability,
   ownership, dependency contract and check command are clear. A missing material
   answer blocks its dependent unit; unrelated unknowns do not delay implementation.

Prefer repository search that respects ignores; load hidden instruction files by
known path rather than enabling unrestricted hidden/dependency scans. Do not use
`find ..`, `rg ... ..`, home-wide recursion, broad parent `glob`/`rglob`, or commands
with an accidentally implicit root for discovery. Do not list `.git`, dependency,
build, evidence or installed-skill trees as product source. Exact reads of an
installed skill resource or a linked evidence artifact remain legitimate.

Truncated/noisy output is a reason to narrow paths or queries, not to request the
same unbounded output again. Do not hide permission errors merely to make a wide
scan look successful. No recursive concatenation, credential reads, connector
installation or global configuration changes to complete discovery.

## Bounded does not mean single-repository

For a declared workspace, retain a compact map of repository identities and links
with their authority/permission boundaries. Read the coordinating instructions and
contract owners, then only the checkouts needed for the next unit and its actual
prerequisites. For a long approved plan, inspect its dependency outline and global
invariants early; progressively load unit detail, not every body or every diff.
An unresolved integration contract is an explicit dependency, not something left
for the final hour or guessed by parallel implementers.

On a warm profile or resume, reuse that map and verify the next paths/revisions.
Refresh only when a relevant anchor/link changes. Workers receive the bounded map
and relevant excerpts, not a request to rediscover the parent workspace. Record a
new useful link in existing profile/run state, never in another planning system.

## Project versus task

The profile stores conventions, locators, commands, and stable references. A work
order stores the unit's requirements, currently read revisions, ownership, and
contracts. The checkpoint stores progress, decisions, and evidence. Session
inventory, only when needed for delegation, stores observed tools/models. A short
capability note is sufficient when no selection controls exist; do not fabricate
JSON to exercise an optional helper.

Do not put full copies of all documents, a permanent board snapshot, or gate
results into the profile. An approved document does not lose precedence to a
newer draft. Record authority by subject, conflicts, and gaps; block only work
dependent on a material conflict.

## Context and reuse

The coordinator retains objective, decisions, graph, and source map. A worker
receives essential requirements, constraints, and accessible references; it does
not rediscover the entire workspace. Include necessary excerpts with origin and
revision when the worker cannot access a source; an inaccessible link is insufficient.

For each new capability, record:
`capability → canonical owner at file/symbol → reuse/extend/create + reason`.
A search with no results records where and what was searched. Revalidate this map
when related modules change. Before delivery, check for duplicate rules,
components, or flows; passing tests do not justify parallel architecture.

Use existing specialist skills when useful. They gain no permission to delegate,
publish, or expand scope. Do not reshape the repository's process merely because
this orchestration skill prefers another format.

## A concrete stopping point

An approved one-unit plan plus applicable rules, its canonical module and test
command may be enough. Do not scan the remaining repository, fill unused profile
sections or inventory every model before making that change. If an API contract
is uncertain, inspect that contract first; if a linked mandatory specification is
inaccessible, stop the dependent unit rather than infer product behavior.

Treat unknown facts by consequence: investigate an unknown that could change the
next implementation decision; record an irrelevant unknown and proceed. Do not
turn every unknown into a user question or every bounded search into an explorer.
