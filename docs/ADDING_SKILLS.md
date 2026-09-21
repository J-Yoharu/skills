# Adding and activating skills

## Create a draft

```bash
make skill-new NAME=example-skill DISPLAY_NAME="Example Skill"
```

The scaffold creates one skill folder, operational record, evaluation contract, copied
license, resource folders, and changelog. It updates the generated catalog and preserves
existing versions. Failed creation or activation rolls back the affected local files.

Implement the behavior in `SKILL.md.template`. Write instructions, references, comments,
and generated text in English. Keep the folder name and frontmatter `name` identical.
Do not rename the `orquestrar` identity as part of a language cleanup.
Keep the single `metadata.version` marker line: release automation uses it.

## Runtime helpers

Only place code under the skill when consumers need it. Put helpers used exclusively by
the repository under root `scripts/`, and test fixtures under `tests/skills/<name>/`.
Runtime dependencies in this baseline are limited to standard-library Python, Node built-ins,
bundled modules, or Bash. This is a repository policy, not a universal Agent Skills restriction.
Extend the policy and isolated tests deliberately before requiring additional runtimes/packages.

Register every top-level runtime entrypoint and assert meaningful stdout in its smoke test:

```json
{
  "entrypoints": ["scripts/inspect.py"],
  "smoke_tests": [{
    "name": "inspect-fixture",
    "command": ["python", "{skill}/scripts/inspect.py", "{work}/result.txt"],
    "timeout_seconds": 10,
    "expected_exit": 0,
    "stdout_contains": "inspection-complete"
  }]
}
```

This is an excerpt to merge into the generated catalog record, not a complete record.
The second command argument must be the bundled entrypoint. `{skill}` and `{work}` are
the supported placeholders. A smoke test runs from the copied skill and an unrelated
working directory. Write generated outputs to `{work}`, not into the installed payload.
Nested helper modules need not be separate entrypoints.

## Real behavioral review

Add at least one positive and one negative activation case to the generated `evals.json`.
Include concrete expected behaviors and safety boundaries. Run the cases in the intended
agent environment. Record the date, agent/model/runtime, observed results, and limitations
in `review.evidence`; store longer sanitized logs alongside the evaluation contract.

```bash
make skill-fingerprint NAME=example-skill
```

Record that digest in `review.payload_sha256` only for the content actually reviewed.
Set `review.status` to `approved` after a real human review. Changed content invalidates
the record. The checker verifies consistency, not whether a human or agent truly ran cases.
Maintenance unit tests use explicit synthetic fixtures; they are not evaluation evidence
for your real skill.

Fingerprinting includes instructions and bundled runtime resources. It normalizes the
release-only metadata version line and the draft-to-active filename, and excludes root
`version.txt`, `CHANGELOG.md`, and `.gitkeep` files. A normal release bump therefore does
not require repeating a behavioral evaluation; changing actual content does.

## Activate

```bash
make validate
make skill-activate NAME=example-skill
make check
```

The command rejects remaining scaffold markers, pending/stale evaluation records,
missing resources, and failing smoke tests. Activation only renames the template and
updates local registration. Commit an appropriate `feat(example-skill): ...` change;
Release Please handles the first nonzero version. Never manually activate an empty shell.

## Imported candidates and deterministic suites

An implementation can remain `draft` after import. Its editing-version labels are
not automatically releases. Keep `0.0.0` and pending review until actual evaluation.
Use `make skill-preview NAME=example-skill` for an installable disposable copy without
making the tracked source discoverable. Never commit `dist/`.

Keep optional deterministic suites in `tests/skills/<name>/test_*.py`; the shared runner
discovers them automatically. Register product entrypoints and copied-payload smoke
checks in `catalog/<name>.json`. Tests and evaluation harnesses must not become runtime
imports of the product. The imported Orquestrar demonstrates this separation.
