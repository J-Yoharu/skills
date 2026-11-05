# Golden tests for usability

A golden test puts a real model in front of the real server, with a real request, and compares the result with an answer key fixed before the run. It measures what no logic test measures: whether the server is usable by whoever will use it.

The answer key is the golden part. Without it, each round becomes opinion.

## Contents

- Fit what already exists
- Spike or fixture
- Guards
- Write a case
- Starting state and an observable result
- Why `claude -p` and not a subagent
- Run
- Grade blindly
- Alternative: `claude plugin eval`
- Pitfalls

## Fit what already exists

Start from `discover_project.py`, and reuse the project's structure instead of adding a parallel one:

| Discovery finds | Use it for |
|---|---|
| A test runner | The gate, with the matching snippet under Guards |
| A fixture folder near the server | The kit's home, so cases sit with the other fixtures |
| Seeds and factories | The `before_case` hook, to reset state with what the project already has |
| CI and Git hooks | The free checks: contract and case validation |
| An `.mcp.json` | The server entry for `mcp.json` |
| Signs of OAuth | Whether the auth lane applies, and which fit in [oauth-integration.md](oauth-integration.md) |

The engine stays in Python even in a project of another language: it needs only Python 3.9+, and the project's test runner calls it through the gate.

## Spike or fixture

The same structure serves two intentions. Decide before writing.

| | Spike | Fixture |
|---|---|---|
| For what | Answer a question now: does this change help? Is this format better? | Keep a usability net alive, as part of the system |
| Where it lives | A folder ignored by Git | Next to the tests, versioned |
| Lifetime | Deleted once it becomes a decision | Evolves with the server |
| Repetitions | 1, sometimes 2 | 3 or more |
| Who starts it | Whoever is investigating | A person, before a release or after a contract change |
| CI | Never | Never by default: only what is free |
| In Git | Out: `init_kit.py --ignore-locally` | In, except `.mcp-eval/` |
| Configuration | `"mode": "spike"` | `"mode": "fixture"` |

Start as a spike. Promote it when the cases prove they find real problems:

1. Move the kit to your system's fixtures folder, such as `tests/fixtures/mcp-golden/`.
2. Change `mode` to `fixture` and `repetitions` to 3.
3. Set some cases aside as `holdout`.
4. Version the cases, seed, contract snapshot and baseline report.
5. Never version `.mcp-eval/`: transcripts can hold data.
6. Turn on the guards of your test runner, as shown below.

## Guards

A fixture that runs by accident costs money and can point at the wrong place. The kit has independent layers:

| Layer | What it does |
|---|---|
| Plan by default | Without `--live`, nothing calls a model: the script shows runs and worst-case cost |
| Two keys | `--live` states the intent, `MCP_EVAL_LIVE=1` states the place. Missing either, it refuses |
| CI blocked | With the `CI` variable set, it refuses, unless `guard.allow_ci` is true |
| Required budget | Without `budget.per_run_usd` and `budget.total_usd`, it refuses |
| Total cap | Stops before a run that could pass the total. What was left out is recorded |
| Host list | A URL outside `guard.allowed_hosts` is refused. Production does not get in by mistake |
| Lock | One run at a time, so nothing fights over state or credentials |
| No overwrite | The same `--run-id` does not replace an earlier result |
| Check before spending | A server that is down fails before the first run |
| Grader cap | `grader.total_usd` stops the votes of a `judge` call before passing the total |

### In your test runner

Keep two things apart. What is free always runs. What spends only runs with the key.

```yaml
# CI: only what is free
- run: python3 -B tests/fixtures/mcp-golden/scripts/run_golden.py --config tests/fixtures/mcp-golden/eval.config.json --validate
- run: python3 -B tests/fixtures/mcp-golden/scripts/check_contract.py --config tests/fixtures/mcp-golden/eval.config.json
```

To trigger the battery from your application's test runner, use the same gate:

```ts
// Vitest or Jest
const live = process.env.MCP_EVAL_LIVE === '1' && !process.env.CI;
describe.skipIf(!live)('MCP server golden', () => {
  it('meets the stop criteria', () => { /* call run_golden.py and report_golden.py */ });
});
```

```python
# pytest
live = pytest.mark.skipif(os.getenv("MCP_EVAL_LIVE") != "1" or os.getenv("CI"), reason="spends model budget")
```

```xml
<!-- PHPUnit: a group outside the default run; use --group golden -->
<groups><exclude><group>golden</group></exclude></groups>
```

```go
// Go
//go:build golden
```

## Write a case

A case is a JSON file in `golden/cases/`:

```json
{
  "id": "read-detail",
  "title": "An answer that exists only in the full text of the note",
  "persona": "non-technical",
  "kind": "read",
  "tier": "public",
  "prompt": "who was in charge of the welcome guide again?",
  "ideal_calls": [2, 3],
  "checks": [
    { "type": "tool_order", "first": "search_notes", "then": "get_note" },
    { "type": "final_matches", "regex": "Marina" }
  ],
  "rubric": [
    "The answer says Marina is the owner.",
    "The answer makes up no detail that is not in the note."
  ]
}
```

| Field | Role |
|---|---|
| `prompt` | The request, in the words of whoever asks, typos and slang included. Never say which tool to use |
| `persona` | The same task asked in two ways finds different defects |
| `kind` | `create`, `edit`, `read`, `vague`, `missing-data`, `recovery`, `negative` or `other` |
| `tier` | `public` or `holdout` |
| `ideal_calls` | A reasonable range, set by thinking through the best path |
| `checks` | Deterministic rules, free and without opinion |
| `rubric` | Items for the grader to judge what a rule cannot |
| `attachments` | Files the person would attach. The kit turns on `Read` and adds their folders to the run |

### Checks

| Type | Fields | Use |
|---|---|---|
| `tool_called` | `tool`, `min`, `max` | The tool was used, how many times |
| `tool_not_called` | `tool` | It did not write when it should only read |
| `tool_order` | `first`, `then` | It checked before saving |
| `args_match` | `tool`, `regex` | The argument carried what it should |
| `final_matches` | `regex` | The answer has the right data |
| `final_not_matches` | `regex` | The answer does not claim what does not exist |
| `max_calls`, `max_errors`, `max_cost_usd` | `value` | Limit per run |
| `command` | `run` | Any command: exit code 0 passes. This is where your domain's verification comes in |

The `command` check runs with the variables listed under hooks below. Use it to query the database, open the generated file or call the API.

**Keep checks loose and the rubric demanding.** A strict regex fails good answers: in a missing-data case, a check that forbade any price failed a correct answer, which said there was no such note and quoted prices from another one. That cause is called answer key, and [metrics-and-improvement.md](metrics-and-improvement.md) shows how to handle it.

### Cover the kinds of failure

A battery of 10 cases usually has:

| Kind | Example | Defect it catches |
|---|---|---|
| Happy path, non-technical | A short, informal request | Vocabulary, descriptions |
| Happy path, technical | A precise request, with field names | Schema coverage |
| Edit | Change one part and keep the rest | Accidental destruction |
| Vague request | "make this better" | Judgment, overreach |
| False premise | Asks for what does not exist | Invention |
| Answer only in the detail | The data is in the read, not the search | Stopping too early |
| Similar names | Two items with similar names | Wrong pick, with no warning |
| Provoked error | A request that goes through a common error | Message quality |
| No use | A request that does not need the server | Needless calls |
| Volume | A case that needs pagination | Big responses, partial conclusions |

### Fix the answer key before running

- Write `checks` and `rubric` before seeing any result.
- Compute the key at the data source, not with the model. "How many contracts in October" is answered with a query.
- If you must correct the key later, record why and run the models again.
- If the case is about data that changes, fix the date in the request or the seed.

### Reserve a holdout

Improving descriptions while looking at the same cases skews the result. Mark 20% to 30% of the cases with `"tier": "holdout"`. Whoever tunes the server does not read those cases, and they run only with `--holdout`, to confirm the result at the end.

## Starting state and an observable result

Each run must start the same, and the result must survive the end of the process. This is where your application plugs in, through the hooks in `eval.config.json`:

| Hook | When | Example |
|---|---|---|
| `before_run` | Once, before everything | Start the server and issue the token |
| `before_case` | Before each run | Restore the seed, or truncate the test tables |
| `after_case` | After each run | Export what was generated to `$EVAL_ARTIFACT_DIR` |
| `after_run` | Once, at the end | Stop the server and revoke the token |

Hooks, `command` checks and the MCP configuration can read these variables:

| Variable | Value |
|---|---|
| `EVAL_KIT_DIR` | The folder of `eval.config.json` |
| `EVAL_SCRIPTS_DIR` | The kit's `scripts/` folder |
| `EVAL_ARTIFACT_DIR` | A folder that belongs to this run, for state and results |
| `EVAL_ATTEMPT_DIR` | The run's output folder |
| `EVAL_RUN_ID`, `EVAL_CASE_ID`, `EVAL_MODEL`, `EVAL_REP` | Which run this is |

If the server keeps work in memory, it dies with the process. In that case, ask in `agent.system_append` for the model to save when it finishes, and use `after_case` to collect the file.

On stdio, each run starts its own server. Reference `${EVAL_ARTIFACT_DIR}` in the MCP configuration to give each run an isolated folder.

## Why `claude -p` and not a subagent

A subagent would be handy, but it **does not receive the server's `instructions`**. Testing that way forces you to copy the instructions into the prompt, and the copy lies in three ways: it arrives whole even when the real client cuts it; it goes stale when the server changes; and it leaves the test green while the real user gets something else.

With `claude -p`, each run is a new process with no history that receives exactly what the client receives. If your server is used by subagents in production, then a dedicated case for that path is worthwhile.

The grader is a different matter. It does not use the server, so it can be a subagent: copy `agents/mcp-golden-grader.md` to `.claude/agents/` to grade inside an interactive session.

## Run

```bash
# 1. Free: check the cases and the contract
python3 -B scripts/run_golden.py --config eval.config.json --validate
python3 -B scripts/check_contract.py --config eval.config.json

# 2. Free: show the plan and the worst-case cost
python3 -B scripts/run_golden.py --config eval.config.json

# 3. Spends: one case, one model, to test the setup
MCP_EVAL_LIVE=1 python3 -B scripts/run_golden.py --config eval.config.json --live \
  --cases read-detail --models haiku --run-id smoke

# 4. Spends: the full round
MCP_EVAL_LIVE=1 python3 -B scripts/run_golden.py --config eval.config.json --live --run-id r1
```

If the plan warns that the `instructions` will be cut, tell the person and decide before spending. Changing nothing, the round measures what a user with the default limit receives. With `CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH` in `agent.env`, it measures the full text. Running both conditions makes a good A/B spike.

Each run writes to `.mcp-eval/runs/<id>/<case>/<model>-r<n>/`: the transcript, final text, calls, artifacts and stderr. `manifest.json` keeps what makes the round comparable: contract fingerprint, commit, client version and budget.

### Where the data goes

Everything stays in the kit folder, under `results_dir`, which defaults to `.mcp-eval/runs/`. Nothing goes to the skill folder or the agent; temporary folders are only for isolating runs and graders, and they are deleted.

Each round ends by saying where the data is and how much space it takes. In a Git repository it also says whether the folder is ignored. The kit's `.gitignore` covers `.mcp-eval/`, so the warning appears if you moved `results_dir` or removed that file. Then choose: add the folder to `.gitignore`, keep it, or delete it. Rounds are disposable, except the ones you use as a baseline.

### Choosing models

Run the model your users use, and a weaker one. The weaker model works as a magnifying glass: it stumbles first on ambiguous descriptions. In a real battery, the smaller model made 35% to 60% more calls than the larger one on the same cases, and the stumbles pointed at the server.

Change the scenario now and then too. One round through a different client found a serious defect the usual battery did not show, because the document already started open.

## Grade blindly

Whoever grades cannot know which model did what, or what it cost. Those who know tend to confirm what they expect.

```bash
python3 -B scripts/grade_golden.py prepare --config eval.config.json --run r1
MCP_EVAL_LIVE=1 python3 -B scripts/grade_golden.py judge --config eval.config.json --run r1 --live
```

`prepare` shuffles labels A, B, C per case and builds a packet with no model, cost or time. The map stays outside the packet, away from the grader.

`judge` runs **three independent graders** on each packet, and the majority decides:

- Each grader is a separate `claude -p` with no access to the server.
- Each one works on a throwaway copy, so it cannot read the map or another vote.
- Each one reads the results in a different order, which dilutes position bias.

| Votes | Result |
|---|---|
| ✔✔✔ | ✔, unanimous |
| ✔✔◐ | ✔, and the report lists it under grader disagreement |
| ✔◐✘ | ◐, and it goes to a person: the stop criteria stay closed until it is reviewed |
| One vote for silent failure | The verdict stands, and it goes to a person, because that is the worst defect |

Split votes are useful on their own: they point at a borderline result or an ambiguous rubric item. Set `grader.votes` to 1 for a cheap spike. Votes already cast are kept, so a rerun only casts the missing ones. Fewer than a majority of the votes leaves the case ungraded.

The verdict has three levels:

| Mark | Verdict | Meaning |
|---|---|---|
| ✔ | `clean` | All required items met |
| ◐ | `partial` | Right structure, one required item failed |
| ✘ | `fail` | Request not met, or the result is broken |

The grader also sets `silent_failure` when the answer claims success and the result does not match.

Grading cautions:

- Automatic graders make mistakes too. Check the ◐ and ✘ cases by hand, and a sample of the ✔.
- A grader can cost more than a small model under test. In a real round, three votes cost 2.2 times one grader and changed one verdict out of eight. Plan for it in the budget.
- To grade by hand, fill in `grades/<case>/grade.json` in the same format.
- **Look at the artifact.** If the server generates a file or a screen, open it. A model's answer does not prove what was produced.

Then build the report, which undoes the map:

```bash
python3 -B scripts/report_golden.py --config eval.config.json --run r1   # from the second round on, add --baseline <earlier run>
```

## Alternative: `claude plugin eval`

Claude Code has a native evaluation command for **plugins**. Its idea is to show what the plugin adds: each case runs with and without the plugin, 3 times per arm, and the difference is the score. It has free graders (`regex`, `tool_used`, `tool_order`, `file_exists`), model graders (`llm`, which passes on 2 of 3 votes, and `baseline`), mocks for MCP tools, and `--max-cost-usd`.

Consider it when the server ships inside a plugin, or to test tool choice cheaply with mocks and no backend. The kit stays the better fit for a real server: that command answers from mocks by default, and its documentation does not cover a server outside a plugin or a remote one. If you use it, pass `--no-publish` to keep the report local.

## Pitfalls

| Pitfall | Effect | Prevention |
|---|---|---|
| Copying instructions into the prompt | Measures text the user does not receive | `claude -p` and `check_contract.py` |
| Saying in the request how to use the tools | Hides exactly what should be measured | `prompt` holds only the request |
| The runner's environment leaking into the test | Hooks and personal instructions change the result | Empty folder, `--setting-sources project` and `--strict-mcp-config` |
| Built-in tools left on | The model bypasses the server | Restricted `--tools`, which the kit already applies |
| Dirty state between cases | One case contaminates another | `before_case` always restores |
| Old tool list | Tests yesterday's version | A new process per run; `manifest.json` keeps the contract |
| Fixing the key after seeing the result | The test passes with no proof | Record why and run again |
| `n=1` used as proof of stability | It oscillates on the next round | Fixture with 3 repetitions |
