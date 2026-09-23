# Project profile

The profile remembers how this repository works so each run does not rediscover it.
It is a cache of observed facts, not task state, permissions or session capabilities.
If the project already has its own equivalent, use that instead.

## Missing: discover and save once

After reading the project's actual rules and plan, write a draft with only the
sections that help future runs and the files those facts came from:

```json
{
  "project_id": "<observed-project-id>",
  "sections": {
    "workflow": {"summary": "<how work is planned, delivered and reviewed here>"},
    "verification": {"command": "<canonical test command>"},
    "conventions": {"summary": "<reuse points, language, forbidden patterns>"}
  },
  "sources": ["AGENTS.md", "<file that defines the test command>"]
}
```

```bash
python3 "$SKILL_DIR/scripts/profile.py" save --root "$ROOT" --draft "$DRAFT" --profile "$ROOT/.orquestrar/profile.json"
```

`sources` are paths inside the project that already hold these facts, not files this
run is about to edit. The helper records a hash of each one, so
listing a file that does not exist yet is fine: creating it later marks the profile stale.
One save is enough; do not re-check it in the same run.

## Existing: check, then reuse or refresh

```bash
python3 "$SKILL_DIR/scripts/profile.py" check --root "$ROOT" --profile "$ROOT/.orquestrar/profile.json"
```

- `fresh`: reuse it. Still read the current task's requirements and permissions.
- `stale`: reread only `changed_sources`, update the affected sections starting from
  the existing file (keep anything the user wrote), and save once.
- `missing`: discover and save as above.

An unrelated product change does not make the profile stale. The profile never
overrides the live instructions it summarizes; when they disagree, the source wins.

## Model policy

Optional `sections.models` holds subagent routing overrides in the format of
[model-overrides.example.json](../assets/model-overrides.example.json). Pass the profile
to `route.py --overrides`. It never selects the coordinator's model.

## When it fails

A profile error is never a product blocker. Say so once, continue with live sources
(`--sem-cache` behavior) and do not loop on repairs. `--inspecionar` never writes it.
