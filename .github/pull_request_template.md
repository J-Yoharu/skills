## Change

Describe the problem, affected skills, and expected behavior. Use a Conventional Commit title.

## Scope and versions

- [ ] Shipped behavioral Markdown changes use an appropriate release intent, not merely `docs:`.
- [ ] Release Please-managed versions were not manually reset or bumped during ordinary development.
- [ ] Runtime skills remain independent of root maintenance code and sibling skills.
- [ ] Changed content has fresh evaluation cases, actual evidence, and the reviewed payload fingerprint.

## Verification

Record actual commands, results, and limitations. Do not claim an agent evaluation or
independent reviewer that did not run.

```text
make check
```

## Review

- [ ] Maintained docs, comments, messages, and generated templates are in English.
- [ ] No secrets, large test fixtures, or development dependencies entered a skill payload.
- [ ] Destructive behavior requires explicit user authorization and is documented.

For command or agent-policy changes, report `make test-launchers` results and whether
native Codex/Claude loading was actually exercised. Do not infer it from file checks.
