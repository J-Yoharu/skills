# Models and reasoning effort — subagents only

## The current chat is the coordinator

The model in the open session runs this skill. It handles discovery, planning,
delegation, integration, and communication. There is no routable
`coordinate`/`coordinator` role, coordinator preset, or higher orchestration layer.
Do not launch another agent, fork, or CLI to take over coordination.

This policy manages neither the chat's model **nor** its reasoning effort. Do not
change them, propose automatic replacement, or restore settings from an earlier
profile/run. When the user changes harness settings or resumes in another session,
use the current session and update runtime observations only when available.
Unknown data remains null, never inferred.

In `solo` or without delegation, do not resolve an `implement` route for the chat:
execute with its current configuration or record the relevant capacity/review
limitation. Unavailable subagent configuration leads to inheritance or an explicit
blocker, never to reconfiguring the coordinator.

## Catalog, subagent roles, and runtime

Reusable policy lives in [model-catalog.json](../assets/model-catalog.json). It
maps **subagent** choices for Claude Code and Codex and declares
`selection_scope: subagents`. It is neither an installed-model inventory nor a
benchmark ranking. Model changes require catalog/override updates and route
revalidation, not workflow changes.

| Role | Initial Claude Code preference | Initial Codex/GPT preference |
|---|---|---|
| lookup | Haiku, no effort field | GPT-5.6 Luna, medium |
| mechanical | Sonnet, medium | GPT-5.6 Luna, medium |
| explore | Sonnet, medium | GPT-5.6 Terra, medium |
| implement | Sonnet, high | GPT-5.6 Sol, medium |
| review | Opus, high | GPT-5.6 Sol, high |
| critical | Opus, high | GPT-5.6 Sol, high |
| deep | Opus, xhigh when supported | GPT-5.6 Sol, xhigh when supported |
| frontier, opt-in | Fable, high | GPT-6 Astra, high |

These are **role** counterparts, not proven equivalents in intelligence, price,
effort scale, or quality. Do not convert Claude High into GPT High by rule.
The catalog keeps native fields separate. Do not invent effort for Haiku: omit
unsupported fields. Claude aliases may resolve differently by provider; record
the resolved version when observable.

The initial GPT family is retained from earlier releases. The additional
`frontier` family requires explicit authorization and observed availability. Do
not replace settings just to follow a release or unexpectedly increase spending.
`max`, Ultra, ultracode, and additional native autonomy are not defaults here;
they may change topology/usage and require a separate decision.

## Choose before spawning

This procedure applies only to delegated work, never to the coordinator.

1. Classify by risk, ambiguity, judgment, and coupling, not line count or labels.
   `lookup` and `mechanical` require clear contracts without uncertain product
   decisions; never downgrade reviewers to these roles merely to save usage.
2. Load the catalog and model overrides from the **effective** profile. Do not
   edit an installed skill for one project's preference. Record session overrides
   in the run; persistent human overrides belong to the project.
3. Read this session's actual inventory: selectable IDs, supported effort levels,
   registered agents, organization limits, and spawn controls. A model in a file
   is not proof of availability. Do not make paid inference calls to list models.
4. Resolve the first allowed, supported choice. Capability fallbacks are already
   in the catalog; if none is suitable, do not silently downgrade the work.
5. Send model/effort through actual schema fields or select a native agent whose
   effective configuration matches the route. A fixed agent configuration may
   override dynamic requests: check harness precedence.
6. Record role, reason, requested model/effort, mechanism, and effective model/effort
   confirmed by metadata. Missing confirmation means unknown, not "optimized".
   Caps and environment variables may affect configuration.

[route.py](../scripts/route.py) is an optional deterministic resolver. It does not
query accounts, install agents, run models, or change the main session.
`--target subagent` is the only accepted target and the default. `--role coordinate`
is an error, even with old catalogs or overrides. Unused legacy coordinator entries
are ignored with a warning, without erasing human profiles.
`--session-id` must match a recent inventory observation. Catalog age does not
invalidate newly observed availability; report its age and review policy after
30 days without searching the web on every task.

```bash
python3 <skill>/scripts/route.py --runtime <runtime.json> \
  --session-id <current-id> --role implement
```

The helper's model overrides are the `sections.models` object **after** human
overrides are merged; see `model-overrides.example.json`. This is logical policy,
not native TOML/YAML configuration. Output suggests native fields and leaves
effective configuration unknown; only harness metadata confirms actual execution.

## Native application and fallback

Reuse existing repository agents/profiles first. Optional configuration examples
live in `assets/native/claude-code/` and `assets/native/codex/`. Their presence in
this skill does not register them. Copying them to agent directories requires
authorized installation/configuration and a compatible version. Do not overwrite
an existing profile by name. Check each file's route, especially after changing
overrides; never select a stale preset contradicting the new mapping. Without a
matching preset, use native fields when supported; with neither, record
`configuration_required`.

When the session cannot select a subagent's model/effort, the helper returns
`uncontrolled_inheritance`. Continue only after checking inherited capacity against
the role and recording the limitation; resolver output does not authorize spawn.
Do not use another CLI, global configuration, model-switch command, fork, or
coordinator subagent as a workaround. The chat's configuration remains outside
this policy even when the harness exposes controls to change it.
`--atualizar-modelos` updates subagent routes only.

## Escalation and continuity

Start with `implement` for normal implementation. Material ambiguity, security,
migrations, concurrency, or difficult integration call for `critical`; unresolved
deep analysis may justify `deep`. Two cycles without progress require diagnosis
before another call: effort does not fix missing requirements or environments.
Independent reviewers use `review` with fresh context. Increase review effort
through a real mechanism while preserving read-only access; never use writer
presets `orq-critical`/`orq-deep` as reviewers. Capacity policy does not change role permissions.

When the current **subagent** cannot actually change configuration, finish or
safely interrupt it and create a replacement with a faithful handoff. This never
applies to the coordinating session. Do not leave two writers active. After the
difficult part is resolved, return subsequent units to the normal profile;
do not switch models on every message. Fall back only to adequate capacity,
without bypassing safety refusals, organization limits, or usage consent.

Model changes never relax tests, review, ownership, authorization, or DoD.
Time, tokens, and corrections are metrics only when measured. Do not promise
quality preservation without evaluation in the project.
