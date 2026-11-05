# Metrics and continuous improvement

Running the battery is the easy part. This guide shows what to look at, how to tell a server defect from a model's choice, how to run the loop, and when to stop.

## Choose a focus

People care about different things, and the kit does not pick for you. Set `focus` in `eval.config.json`:

| Focus | Question | Stop criteria to set |
|---|---|---|
| `quality` | Is the result right? | `min_clean_rate`, `max_silent_failures` |
| `cost` | Can it spend fewer tokens? | `max_median_tokens`, `max_cost_per_case_usd`, `max_median_calls` |
| `speed` | Can it answer faster? | `max_median_seconds`, `max_median_calls` |
| `balanced` | A bit of everything | Any of them |

The focus moves its dimension to the top of the scorecard and of the opportunities, and tells the analyst what to prioritize. Everything is still measured.

## What to measure

`report_golden.py` delivers these per round, and `check_contract.py` delivers the surface. The report opens with a scorecard, one line per measure, with the baseline next to it when you pass `--baseline`. It also separates what the runs, the grading and the analysis cost. `report_golden.py --trend` writes one line per round to `trend.md`, to see the direction over time.

| Dimension | Metric | What it reveals |
|---|---|---|
| Result | ✔ ◐ ✘ by case and model, clean rate | Whether the request was met |
| Trust | Silent failures | Whether the answer claims what did not happen |
| Stability | The marks of each repetition, like `✔✔◐` | Whether success is a rule or luck |
| Grading | Grader disagreement | Borderline results and ambiguous rubrics |
| Flow | Tool sequence, calls against the ideal range | Whether the path was direct or lost |
| Friction | Errors, and how many were recovered on the next call | Whether the messages teach |
| Tokens | Output, cache read, cache write | Where the context weighs |
| Cost | Median and total, per model | What a request costs |
| Time | Duration per request, latency per tool | Whether the wait comes from the model or the server |
| Surface | `instructions`, descriptions and schemas, in characters | The fixed price of the server |

### Source of tokens and cost

**Use the `result` event of `stream-json`.** It carries `total_cost_usd`, `usage`, `modelUsage` per model, `num_turns`, `duration_ms`, `permission_denials` and `terminal_reason`. The cost is the client's estimate at list price, good for comparing rounds, but it is not an invoice.

Do not sum `usage` across transcript messages. One real round measured that way recorded 180 output tokens for 16,550 characters sent to the tools, which is impossible: a token is about 4 characters. The report raises an alert when that ratio appears.

### Read the sequence

The sequence tells a run's story. `!` marks an error:

```text
search_notes get_note                                          direct
search_notes search_notes search_notes get_note                weak search, or an unclear description
list_templates read_template read_template read_template       similar names with no tiebreak
replace! replace! replace! replace                             a message that does not teach
read                                                           stopped early, or asked for confirmation
```

Patterns worth investigating:

| Pattern | Hypothesis |
|---|---|
| The same tool many times with similar arguments | Search does not help refine |
| A repeated error on the same tool | The message does not say the way out |
| A read right after each write | The write does not say what it did |
| Stopped after one or two calls | The model thought it needed confirmation |
| More than double the ideal range | A tool that is too thin, or no batch operation |
| No calls | Name and description do not match the request |

### Read the tokens

Each call reads the whole conversation again, with cache. That is why cost grows with **calls × response size**, and cutting calls usually pays off more than shortening instructions.

- **High cache write** on every run: fixed startup cost. Measure it with a minimal case that barely uses the server, and compare with a real case.
- **High cache read**: many calls, or large responses.
- **High output**: the model writes a lot, whether legitimate content or reasoning.
- **Response column in the tool table**: the tool that returns the most characters is the first candidate to trim.

Always weigh cost against the result. One real fix cost about 7% more and took accuracy from 7 to 24 out of 24: more than worth it.

## Read the behavior

A correct answer can hide a problem: the model may have reached it the hard way. That is why the report reads what the agent did, not only what it answered.

The **Opportunities** section comes free with every report. It looks for these patterns in the calls:

| Pattern | What the agent did | What to look at |
|---|---|---|
| `pagination-walk` | Walked pages looking for something | A filter, a count, or a larger page |
| `fan-out` | One call per item | Accept a list of ids, or return it in the list |
| `search-churn` | Kept rephrasing a search | A more tolerant search, or a structured filter |
| `many-writes` | Many writes in a row | One larger call, or a batch |
| `repeated-call` | The same call twice in a row | A response that says more |
| `error-loop` | Errors in a row on one tool | A message that says the way out |
| `over-range` | More calls than the ideal range | Read the sequence |
| `no-calls` | Never called the server | Name, description, or a request for confirmation |
| `heavy-response` | A tool returns a lot | Trim it, or offer `fields` or `limit` |
| `slow-tool` | A tool takes long | Cache, index, or a lighter response |
| `unused-parameter` | A parameter nobody passes | If the agent walked pages on that tool, the filter exists and it does not know |
| `unused-tool` | A tool nobody calls | No case needs it, or its description hides it |

A pattern is a lead, not a verdict. Some of them are legitimate work, so read the sequence before acting. Thresholds live in `analysis`.

For a concrete proposal, one model call reads the same behavior, including what the agent said before each call:

```bash
python3 -B scripts/analyze_behavior.py --config eval.config.json --run r1              # free
MCP_EVAL_LIVE=1 python3 -B scripts/analyze_behavior.py --config eval.config.json --run r1 --live
```

It proposes the smallest change, with the exact parameter or tool, the evidence and the expected effect, and it is told what the client cut from the instructions. Its ideas enter the report. **They are hypotheses:** apply one, run again and compare with `--baseline`.

The demo server has a deliberate gap to show this: `list_notes` has no tag filter. On "how many of my notes are tagged purchasing?", all 4 runs walked 5 pages. The free detector flagged `pagination-walk`, and the analyst proposed a `tag` parameter and a `total`. With that change, the median fell from 5 calls to 1, tokens fell 62% and time fell 34%, with the answer still right.

## Find the cause

Every ◐ and ✘, and every ✔ with a caveat, gets a cause before any fix.

| Cause | Signal | Who solves it |
|---|---|---|
| **Server** | A feature was missing, the message misled, validation was wrong, the response left something out | You, in the code or the descriptions |
| **Model** | It had everything it needed and chose badly, and another model got it right | Usually accept it, document it, or recommend a model |
| **Infra** | A service went down, a timeout, a dirty environment | Fix the environment; the run does not even count (∅) |
| **Answer key** | The answer was right and the rule failed it, or the request was ambiguous | Fix the case, record why, and run again |

Start by suspecting the server. In real batteries, nearly every ◐ and ✘ of a capable model had its cause in the server, not in the model's understanding. The test is simple: if you explained to the person why the model failed, would the explanation be "the system did not say" or "the model ignored it"?

Prioritize by damage:

| Priority | Criterion | Example |
|---|---|---|
| P0 | Breaks the result silently | Content vanishes from the final file while validation says all is well |
| P1 | Limits what the model can do | An operation is missing and the model improvises |
| P2 | Friction and noise | A false warning the model learns to ignore |

Fill in the findings table of the report, with the case that proves each one and how to recheck it.

## The loop

```text
1. Baseline      run everything and keep the run id
2. Classify      cause and priority of each finding
3. Fix           P0 first, in small, separate changes
4. Recheck       only the affected cases, with --cases
5. Regression    full round, with --baseline
6. Decide        criteria met? if not, back to step 2
7. Holdout       run --holdout before declaring it done
```

Rules that keep the loop honest:

- **A fix without a model does not count.** It only counts after running. A unit test proves the logic, not that the model started getting it right.
- **Rechecking is not proving.** After running only the affected cases, run the full battery before claiming a score.
- **One hypothesis at a time**, when you can. Ten changes together do not say which one helped.
- **If a change made a case worse, investigate.** It can be noise or a regression, and repetitions tell which.
- **Update the contract snapshot on purpose**, so the diff goes through review.
- **Record what you decided not to touch**, with the reason. Otherwise the same finding returns every round.
- **Keep the reference rounds.** With no baseline there is no improvement, only an impression.

### Compare hypotheses with an A/B spike

To choose between two paths, run the same cases on both versions:

```bash
MCP_EVAL_LIVE=1 python3 -B scripts/run_golden.py --config eval.config.json --live --run-id before
# change one thing only
MCP_EVAL_LIVE=1 python3 -B scripts/run_golden.py --config eval.config.json --live --run-id after
python3 -B scripts/report_golden.py --config eval.config.json --run after --baseline before
```

To compare server versions on the same data, use two configurations pointing at two addresses. To test a client limit, change only `agent.env`. If the two sides use different data, the comparison is worth nothing.

Each round is graded separately, so the grader does not compare the two sides. In a close decision, put the runs from both sides in a single packet and grade by hand.

Write the limits next to the result: how many runs, whether grading was blind, and what was left out. An honest spike with limits is worth more than a number with no context.

Look beyond the score. In a real spike, the score barely moved (5 to 6 clean out of 8), but calls fell 35%, errors fell 75%, and documents started using the right components. And the delta flagged a regression in one case that, on opening the files, was noise from a single run: the "worse" result had the right components, with a finishing defect. That is why the cause always comes before the conclusion.

## When to stop

Set the criteria **before** starting, in `stop_criteria`:

```json
{
  "min_clean_rate": 0.9,
  "max_silent_failures": 0,
  "max_cost_per_case_usd": 0.25,
  "max_median_calls": 8
}
```

The report checks each item and declares them met only if nothing awaits a grade or a human review, and no run is invalid. Adjust the numbers to your risk:

- A server that **reads**: accept 90% clean with some slack. An error costs little and gets fixed in the conversation.
- A server that **writes**: go up to 95% and accept no silent failure.
- A server that **acts on the world**, like payments or sending: require 100% on the risky cases, and confirmation from the person by design.

Stop too if:

- Two rounds in a row find no server finding, and what remains is the model's choice.
- The next fix costs more than the problem bothers anyone.
- The measured gain fits within the variation between repetitions.

With the criteria met, run `--holdout`. If the result drops a lot, the server got tuned to the public cases, and the work continues.

## Repetitions and variation

Models are not deterministic: the same case oscillates. One run per case serves to find defects, not to prove stability.

| Goal | Repetitions | Reading |
|---|---|---|
| Spike and defect hunting | 1 | Look at the causes, not the score |
| Decision between two versions | 3 | Compare rate and cost |
| Fixture and release | 3 to 5 | Demand stability |

The mark `✔✔◐` shows the difference between passing once and passing always. To decide a release, count a case as clean only if **all** repetitions were clean. To measure capability, count the overall rate.

## Report

`report_golden.py` opens with a summary and prints it too: ✔ ◐ ✘ with their numbers by model, the sample size, the comparison with `--baseline`, and up to 3 possible improvements. That short answer is the default, and SKILL.md gives its exact shape. The numbers come from the script, not from anyone counting by hand. The rest of `report.md` is for when someone wants more.

When writing up a round for others, a good report says:

- What changed since the last one.
- The score, with the delta.
- The findings, with cause and priority.
- What was left out, and why.
- The limits of the evidence.
- The next step.

When declaring success, separate what was measured from what was inferred. "12 of 12 cases clean, one run per case, one model" is different from "it works". If a model was left out of the last round, say so.

## Keeping the net alive

- Every defect found in production becomes a golden case, with the real request anonymized.
- A new tool brings at least one new case.
- A changed description calls for rechecking the cases that use the tool.
- Review the cases after each big change of client or model: `claude --version` and the model are recorded in `manifest.json`, to explain a behavior change with no server change.
- A case that has not failed in months is a candidate to leave, so the cost of the net stays fair.
