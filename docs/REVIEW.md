> Historical review of the preceding archive. Superseded by [current verification](VERIFICATION.md).

# Separate repository review

Historical report for the preceding pnpm revision. See [the current agent/Make review](AGENT_MAKE_REVIEW.md) for the latest delivery.

## Scope and method

This revision started from the delivered ZIP, extracted an untouched baseline, and ran
its original 106 Python tests. All 106 passed. A separate audit pass then exercised
contracts not covered by those tests: PR release exceptions, evaluation freshness,
documentation links, version progression, and matrix output size. Those probes reproduced
concrete defects despite the green suite. The before/after results are included
in [audit probes](review-probes.json).

The review was performed as a separate phase by the same assistant. It is **not** a claim
that a second autonomous agent or a different model independently approved the repository.
The final regression suite includes synthetic repositories and real local Git operations.
No remote repository, token, branch, release, or skill activation was modified.

## Findings and disposition

| Finding | Correction |
| --- | --- |
| A release-looking branch/title bypassed payload commit policy. | Limit exceptions to metadata/changelog paths and verify version-only `SKILL.md` diffs against actual commits. |
| Approved evaluation records survived behavioral payload changes. | Bind review evidence to a deterministic payload fingerprint; reject stale active reviews. |
| Root documentation targets were not checked. | Validate maintained root/docs/form/evaluation Markdown file targets within repository boundaries. |
| Component/catalog version rollback was not explicitly rejected. | Reject decreasing versions relative to reachable prior catalog releases. |
| Bounded job count still emitted every skill name in the matrix. | Emit constant-size shard descriptors and recompute selection from identical Git refs in each job. |
| A top-level Python module directory could hide a missing nested module. | Validate complete dotted bundled module paths, retaining legitimate bundled packages. |
| Local archive checksums alone did not bind artifacts to the release source. | Rebuild and compare exact artifacts from the verified clean tag before publication. |
| Asset writes could begin before later conflicts were checked. | Complete read-only asset and component-ref preflight before any upload or ref creation. |
| Local tags were treated as evidence of remote tags. | Read remote refs, resolve annotated tags, and fail on conflicting or unavailable history. |
| Maintained/generated prose mixed Portuguese and English. | Rewrite maintained docs/forms/templates/diagnostics in English while preserving identifiers and contracts. |
| npm aliases obscured a Python operational dependency. | Make pnpm canonical, add a tested explicit Node-to-venv launcher, and document the dual dependency boundary. |

The original 10,000-name matrix example serialized to 1,360,774 bytes when counted as
UTF-16 code units, exceeding GitHub's approximately 1 MB per-job output budget. Compact
matrix regression tests exercise a much larger synthetic name list without claiming a
full-catalog throughput benchmark.

## Naming decisions

Root `scripts/`, `tests/`, and `docs/` are common conventions. `tooling/` was not incorrect
and was not required by the user or format; it has been renamed for familiarity.
`catalog/` and `schemas/` remain explicit local concepts. Runtime `skills/<name>/scripts/`
remains separate from root maintenance code. No validator-only repository is needed.

pnpm does not make Python disappear. Keeping the tested Python engine avoids a broad
rewrite unrelated to the user's language requirement. English refers to natural-language
content, not a forced change from Python to JavaScript. No npm package per skill, task
orchestrator framework, or monorepo framework was added.

## Remaining limitations

Read [Verification](VERIFICATION.md) and [Security](../SECURITY.md). Static gates are not
an LLM evaluation or security sandbox. The fingerprint cannot prove the honesty of evidence.
The language review covers current content and generated templates; it does not magically
detect every possible future non-English sentence. Maintainers must enforce the language
policy in reviews. Remote integrations and actual package-manager installation require an
online environment and were not claimed as completed here.
