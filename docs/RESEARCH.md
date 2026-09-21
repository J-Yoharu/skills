# Primary-source review

Reviewed for this revision on 2026-09-21. These sources explain design decisions; a linked
configuration is not proof that this repository's hosted workflows have run.

| Source | Observation used |
| --- | --- |
| [Agent Skills specification](https://agentskills.io/specification) | `SKILL.md`, supported metadata, and bundled scripts/references/assets; no prescribed root `tooling/` directory. |
| [Neon maintenance package](https://github.com/neondatabase/agent-skills/blob/main/package.json) | Root scripts validate skills, references, and versions. This supports the root `scripts/` convention, not a claim that every catalog uses pnpm. |
| [Vercel maintenance package](https://github.com/vercel-labs/agent-skills/blob/main/package.json) | A root development package is separate from distributed skills. |
| [Supabase release configuration](https://github.com/supabase/agent-skills/blob/main/release-please-config.json) | Independent skill components with an aggregate root release; component release pages can be skipped. |
| [Release Please manifest documentation](https://github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md) | Path-based components, root aggregation, component metadata, and release configuration semantics. |
| [pnpm 10 installation](https://pnpm.io/10.x/installation) | Explicit pnpm 10.33.4 pin and Node compatibility. This is a deliberately selected line, not a claim that pnpm 10 is the latest major. |
| [pnpm install](https://pnpm.io/cli/install) | Frozen lockfile behavior. pnpm does not install Python requirements. |
| [GitHub Actions workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) | Workflow configuration, permissions, and job output limits motivate compact shard descriptors. |

The repository does not include a speculative `skills.sh.json` manifest or claim a
`gh skill publish` command is required. Releases, CLI installation, and directory indexing
are distinct. No benchmark establishes one package manager as universally faster for
this repository, which currently has no external Node dependencies.

Pinned actions were checked against their upstream release/commit pages. Runtime/action
and dependency pins should be reviewed over time, not treated as permanent guarantees.
See [Verification](VERIFICATION.md) for what was actually executed locally.

## Agent instructions and Make facade (2026-09-21)

- OpenAI project instruction discovery: https://developers.openai.com/codex/guides/agents-md
- Claude Code native import and AGENTS.md compatibility: https://code.claude.com/docs/en/memory
- pnpm script execution: https://pnpm.io/10.x/cli/run

The native `@AGENTS.md` import is intentional: a prose link alone is not automatic
loading. No claim of identical native agent behavior or hosted execution is made.
Make recipes were exercised using GNU Make 4.4.1 locally. The GNU online manual could
not be fetched during this pass; actual local behavior and tests are the evidence
for the implemented facade, not a claim that a new external Make standard exists.
