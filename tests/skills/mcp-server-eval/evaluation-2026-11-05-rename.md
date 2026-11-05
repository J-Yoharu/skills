# MCP Server Eval evaluation after the rename — 2026-11-05

The skill was renamed from `mcp-server-playbook` to `mcp-server-eval` before its first release.
Only the frontmatter `name` and the title changed in the payload, yet the fingerprint changed, so
the cases ran again. The main risk was losing activation on connection and OAuth requests,
because the new name no longer suggests them.

Status: agent evaluation complete. The maintainer read the summary of this report and approved
this payload, without a separate line-by-line review.

## Candidate and setup

- Payload fingerprint: `8b0385a1d4c1d75e6a8dcbb92ceec3c18f6be43b620cc6fe197cb70801c362bf`.
- Previous payload: `527c2e94f31af968df57e67270397f1f1b4bf70cb3fec21b04499a4c39cc5cf3`.
- Same setup as [the previous evaluation](evaluation-2026-11-05.md): Claude Code 2.1.318,
  `claude-sonnet-5-5` and `claude-haiku-5-5`, through `claude -p`, on fresh fixture copies.
- The payload was copied straight into each fixture, because `make skill-preview` needs an
  approved record for an active skill.
- Answer keys did not change. Each deviation below was read by hand.

## Results

30 runs, US$ 1.06.

| Case | Should activate | Activated | Live |
| --- | --- | --- | --- |
| `test-my-mcp` | Yes | 7 of 7 | 0 |
| `set-up-a-spike` | Yes | 5 of 5 | 0 |
| `connect-without-certificate` | Yes | 3 of 3 | 0 |
| `truncated-instructions` | Yes | 3 of 3 | 0 |
| `oauth-login-fails` | Yes | 3 of 3 | 0 |
| `report-a-round` | Yes | 3 of 3 | 0 |
| `unrelated-unit-test` | No | 0 of 3 | 0 |
| `what-is-mcp` | No | 0 of 3 | 0 |

Totals: 24 of 24 positive runs activated, 0 of 6 negative runs activated, and no run went live.
All 5 `set-up-a-spike` runs ran the plan, and all 3 `report-a-round` runs ran the script.

### Deviations

- `set-up-a-spike`, 1 Haiku run: it kept the kit out of the repository by placing it in a
  temporary folder, instead of passing `--ignore-locally`.
- `oauth-login-fails`, 1 Sonnet run: it stated the Claude Code callback, which the guide marks as
  Observed, without that caveat. The same deviation appeared on the previous payload.

## Not repeated

The real-project run and the real golden round were not repeated. Scripts, kit and guides did
not change in this rename, so those results stand on the previous payload. The limitations in
the previous evaluation also still apply.
