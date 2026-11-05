# MCP Server Eval evaluation — 2026-11-05

This record predates the rename: the skill was `mcp-server-playbook` when these runs happened.

Status: agent evaluation complete. On 2026-11-05 the maintainer read the summary of this report and
authorized activation, without a separate line-by-line review of the payload.

## Candidate and setup

- Payload fingerprint: `527c2e94f31af968df57e67270397f1f1b4bf70cb3fec21b04499a4c39cc5cf3`.
- Claude Code 2.1.318, `claude-sonnet-5-5` and `claude-haiku-5-5`, through `claude -p`.
- The skill was installed from `make skill-preview` into `.claude/skills/` of each fixture. No
  global copy existed, so nothing had to be uninstalled.
- Each run used a fresh copy of the fixture, `--setting-sources project`, `--strict-mcp-config`
  and an empty MCP configuration. The `init` event listed the skill and no personal skills.
- The main fixture is a fictional Git project: a small TypeScript "orders" MCP server with stub
  tools and no entry point. `report-a-round` used the same project with a finished round.
- Each answer was read by hand. Commands were checked from the transcripts.
- Answer keys were written before the first run. One key changed later; see below.

## Results on the final payload

31 runs, US$ 1.09: 30 in this table and the real-project run described below. "Live" counts
commands that passed `--live` or set `MCP_EVAL_LIVE`.

| Case | Should activate | Activated | Live | Result |
| --- | --- | --- | --- | --- |
| `test-my-mcp` | Yes | 7 of 7 | 0 | Passed |
| `set-up-a-spike` | Yes | 5 of 5 | 0 | 4 of 5 ran the plan; see deviations |
| `connect-without-certificate` | Yes | 3 of 3 | 0 | Passed |
| `truncated-instructions` | Yes | 3 of 3 | 0 | Passed |
| `oauth-login-fails` | Yes | 3 of 3 | 0 | 1 of 3 stated an Observed value as fact |
| `report-a-round` | Yes | 3 of 3 | 0 | 2 of 3 ran the script; see deviations |
| `unrelated-unit-test` | No | 0 of 3 | 0 | Passed: added the test, created no kit files |
| `what-is-mcp` | No | 0 of 3 | 0 | Passed: answered and changed no files |

Totals, with the real-project run: 25 of 25 positive runs activated, 0 of 6 negative runs
activated, and no run spent on a live round. Each case ran twice on Sonnet and at least once on Haiku. `test-my-mcp` and
`set-up-a-spike` had extra Haiku repetitions to test the spending rule.

### Deviations

- `set-up-a-spike`, 1 Sonnet run: it set up the kit and ran the contract check, but stopped
  before the plan because the fixture server cannot start. It spent nothing and named the
  blocker, yet it did not end with the plan, as the case expects.
- `test-my-mcp`, 1 Haiku run: same stop before the plan. That case does not require the plan.
- `report-a-round`, 1 Haiku run: it read `report.md` instead of running `report_golden.py`, and
  it added sections beyond the requested shape. The table and numbers were correct.
- `oauth-login-fails`, 1 Sonnet run: it stated the Claude Code callback, which the guide marks
  as Observed, without that caveat. The other two runs did not use Observed values.

## Spending rule: a failure this evaluation found

On the first payload (`e98447fa…`), one Haiku run of `test-my-mcp` wrote its own cases, set
`MCP_EVAL_LIVE=1` and ran a live round with no approval. That payload said to run live only
after the person had seen the plan, and Sonnet followed it. A wording test followed:

| Haiku, `test-my-mcp`, 5 runs each | Went live | Ran the plan |
| --- | --- | --- |
| Original wording | 1 | 3 |
| "Stop at the plan" wording, and a step that ends the turn | 0 | 5 |

The new wording shipped. On the final payload, Haiku went live in 0 of 8 runs and Sonnet in
0 of 4 across the two cases. Before the change, the count was 2 of 6 Haiku runs, so these
samples show a clear direction, not a rate.

## Baseline without the skill

Both baseline runs used Sonnet on the first pass. The fixture and prompts did not change.

- `test-my-mcp`: no kit and no plan. It wrote its own probe script outside the project and
  stated that it did not run a model.
- `truncated-instructions`: it answered 2,048 characters, an old value, and suggested no
  variable. With the skill, every run answered 4,096 and `16384`.

## Real project and real round

- **Real project.** A throwaway clone of a private TypeScript monorepo with a real stdio MCP
  server, Sonnet, `set-up-a-spike` prompt, US$ 0.30. The agent ran discovery, set up the kit with
  `--ignore-locally`, built the server, pointed the kit at it and wrote cases. The contract
  check found instructions of 8,000 characters that Claude Code cuts at 4,096. The agent then
  showed the plan and asked for approval. No tracked file changed.
- **Real round.** From the installed copy, on the demo server: `init_kit.py`, contract check,
  live round on Haiku, blind grading with 3 votes, free analysis and report. It cost US$ 0.24.
  The report named `list_notes` pagination, which is the demo's deliberate gap.

## Deterministic checks

- `make check` passed: 179 maintenance tests, 99 skill tests, 7 Orquestrar tests, and 18
  copied-payload smoke executions.
- `test_kit.py` also passed on Python 3.9.25, 3.11 and 3.13.
- Eight planted defects each made the suite fail. They covered the moved modules, the budget
  caps, the model scrubbing, repeated votes, the truncation warning and the IPv6 host.

## Review pass

A separate agent in the same session reviewed the migration, read-only. Fixed from its report:

- A shared-module folder named `lib/` was dropped by common `.gitignore` files, which broke
  the kit in a fresh clone. It is now `scripts/kitlib/`, with a regression test.
- The run and grader caps ignored runs that reported no cost. Those now count as their whole cap.
- The default IPv6 host could never match.
- The kit README's first-round command failed.
- A warning pointed at a guide that the kit does not ship.
- Guide examples kept private-looking vocabulary.
- Four tests stayed green with the behavior broken.

Not fixed, because they are low risk:

- Several documented behaviors have no test: label shuffle, grader reading order, the holdout
  gate, `tool_order`, `final_not_matches`, stale-lock recovery, `before_case` execution, and
  `--update-scripts` leaving configuration alone.
- `init_kit.py` is copied into the kit, where it cannot run.
- `AuthTests` has a port race that was never observed to fail.

## Answer key change

`test-my-mcp` first required `init_kit.py`. Sonnet instead stopped to ask the spike or fixture
question, which `SKILL.md` tells it to do, so the key contradicted the skill. The key now accepts
either, and `set-up-a-spike` covers the setup with those answers given. All cases ran again.

## Prior evidence

These came from the pre-migration draft, not this payload. They stand as background only.

| Test | Result |
| --- | --- |
| Local connection without TLS | Plain HTTP, `.localhost` subdomain and `Host` header connected with a fixed token |
| Instruction limit | Default cut between 3,900 and 4,300 characters; `8192` lost a marker at 12,000; `16384` kept it |
| Subagent | Did not receive server instructions (n=1) |
| Real server, cut against full instructions | Calls 93 to 60, tool errors 16 to 4 (n=1) |
| Demo tag filter gap | Median calls 5 to 1, tokens 38,940 to 14,975 (n=2 per model) |
| 3 grader votes | 6 unanimous, 2 split, 1 of 8 verdicts changed, cost 2.2 times |

## Limitations

- `check_auth.py` has not run against a real OAuth server, only against fakes and a server
  without OAuth.
- Nobody but the author has followed the guide from scratch.
- `claude plugin eval` was not run. Its flags were checked against `--help`.
- Claude values such as the CIMD prefix and callback remain Observed, with no official source.
- Without the skill installed, an agent ignores the kit README's report format. This is accepted.
- Repetitions are small, so these numbers show direction, not rates.
- The live rule depends on the model following it: an agent can still set both keys.
