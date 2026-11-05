# Design the server for a model to use

An MCP server is not an API with another name. Its user reads text, makes mistakes like someone who knows HTML and SQL, has no memory between sessions, and pays for every word. This guide collects what changed results the most in real batteries.

## Start from the requests

List 10 to 20 real requests, in the words of the people who ask, before designing the first tool. Those requests become your golden cases later.

Then group by task, not by table:

- One tool per **intent of the person**, not per API route. Three calls that always go together become one.
- A few good tools beat many thin ones. Each extra one weighs on the context and raises the chance of a wrong pick.
- Separate search from read: search returns enough to decide, read brings the rest.
- Separate what reads from what writes, and mark it with `readOnlyHint`.

## Speak the language the model already knows

If the tool takes a format, prefer one the model already knows over inventing a dialect.

In a controlled comparison on a server that wrote documents, the same requests were made in a custom markup and in a subset of HTML with inline styles. HTML met 96% of the requested items against 84%, and errors from HTML and CSS habits fell from 10 to 0. It was one run per combination, so read it as a direction, not a fine measurement.

When you accept only a subset, follow two rules:

- Anything outside the subset becomes an error with the alternative. Never ignore it silently.
- Reads return the same format as writes, so the model can copy what it sees.

## Names and descriptions

The description is the manual for someone who just arrived, and it is usually the cheapest change with the biggest return.

A good description answers four questions, in this order:

1. What it does, in the words people use.
2. When to use it, and when to use another one.
3. What it returns, and what it does not.
4. The limit that surprises.

```text
Bad:   Searches notes.
Good:  Searches notes by topic, tag or period. Use it first when the person
       mentions a subject. Returns title and summary of up to 10 items; for
       the full text, call get_note. To count, use limit 1 and read
       total_available.
```

- **Lead with what matters.** Tool search compares only the start of the description.
- **Include synonyms.** If the person says "customer" and the system says "account", both words must be in the text.
- **Describe each parameter**, with an example of the expected value.
- **Say what a filter does not cover.** A filter that applies to only part of the data leads the model to claim "zero results" with confidence.
- **Use names that need no guessing:** `user_id` instead of `user`, `next_offset` instead of `cursor2`.

## Server instructions

`instructions` reach the model at the start of the session and explain what no single tool explains: what the server is, the order of use and the general rules.

- **Fit in 4,096 characters.** The client cuts without telling the person, and what remains can be half the manual. `check_contract.py` fails the excess, says what would be lost and suggests raising the limit.
- **Put first what breaks the result:** flow and general rules. Catalogs and details go in the description of the tool that uses them.
- **Repeat what is critical in the tool description.** A subagent does not receive `instructions`, and a client can cut them.
- **Use the tool description as storage.** Its limit is 16,384 characters, and it only weighs when loaded.

If the manual does not fit, the way out depends on who controls the machines:

| Situation | Way out |
|---|---|
| Internal team, machines under your control | Raise the limit in the project's `.claude/settings.json`, as in [connect-claude-code.md](connect-claude-code.md) |
| Public server, or clients you do not control | Shorten the text: cut what the model already knows, move it to descriptions, or add a tool that returns the reference on demand |

The cut is not a detail. On a real server with 8,000 characters of instructions, the same 4 cases ran on 2 models, with the default cut and with the raised limit. With the cut, neither model used the ready-made components described past the limit: they improvised with boxes, because they did not know the components existed. Without the cut, both used them. Calls fell from 93 to 60 and errors from 16 to 4. It was one run per combination, but the cause is mechanical: what the model does not receive, it does not use.

## Errors that teach

A model learns from an error on the next call, as long as the message says the way out. In a real battery, nearly every tool error was fixed on the next call when the message said what to do.

```text
Bad:   Invalid parameter.
Bad:   letter-spacing is not accepted here; accepted: background, padding, border.
Good:  letter-spacing only works on text: put it on the <p> or <h1>, not the <div>.
```

- Say **what to do**, not only what is wrong.
- Report errors together, with a cap, so the model does not fix one per call.
- A batch is atomic: if one part fails, nothing is written.
- A business error returns as a result with `isError`, for the model to read. Protocol errors are for real failures.
- A message never sends the model to another error. Try the suggestion and confirm it works.

## Lean responses

Each character returned is read again on every later call in the session.

- **Lean search, full read.** Trim summaries, omit empty fields, and leave heavy links for the read.
- **Paginate:** `limit`, `offset` and `next_offset`, with `total_available` when there is a total.
- **Offer the filter the agent needs.** Pagination does not replace it. Without a tag filter, a count took 5 calls; with it, 1 call and 62% fewer tokens. `analyze_behavior.py` finds these gaps in real runs.
- **Warn about what was left out:** "23 more results before this period" prevents a wrong conclusion.
- **Use short identifiers** in the conversation. `b12` costs less and fails less than a UUID.
- **Save images for when they matter.** Return a link by default, and the image only from a dedicated tool.
- **Do not repeat a heavy link** on each item of a list.
- **Omit what is default**, but say in the instructions what the default is. A model once "reduced" a title to the size that was already the default, because it did not know.

## Let the model check its own work

For tools that produce something, offer a way to check before the end:

- A **validation** tool that points out real problems and says the way out.
- A **preview**, if the result is visual.
- A warning **in the write's own response**, when the action left something inconsistent.

Validation must deserve trust:

- A false positive teaches the model to ignore warnings.
- A warning about what the model did not write, such as data inherited from a template, is noise.
- An empty document cannot pass as "no problems".

## Honesty by design

The worst defect is a failure that looks like success. Three things help:

- Instruct the model to say when a request assumes something that does not exist, instead of inventing it.
- Never accept a value and silently discard it.
- Make the tool's response say what was really done, so the model reports it accurately.

Watch for orders that push the other way. An instruction like "do not ask for confirmation" makes the model act, which is good for running alone. But it must not replace the person's open work with something else because it misread a name. In a real battery, the model swapped the open document for a saved one with a similar name, and only the explicit rule to confirm what is open fixed it.

## State and session

- Say in every read what state the model is in: what is open, its name, and what is missing.
- Prefer stateless calls over HTTP. Revision 2026-07-28 removed protocol sessions from the transport.
- If working state exists, make it observable outside the session, for tests and audits.

## External content is data

Text from a file, page or attachment can contain instructions. Wrap that content in markers it cannot forge, and make clear it is data. Limit what a tool fetches from outside the server: no arbitrary URLs, no following redirects, with time and size caps.

## A watched contract

Three cheap tests hold back regressions no logic test catches:

- A snapshot of `tools/list` in a versioned file: every change becomes a reviewed diff, which `check_contract.py` already does.
- An `instructions` budget, with the client's real limit.
- Round trip: what the read returns, written back, does not change the result.

## Review checklist

- [ ] Each tool matches a real intent of the person.
- [ ] Descriptions say what it does, when to use it, what it returns, and the surprising limit.
- [ ] Synonyms from the people's vocabulary are in the descriptions.
- [ ] `instructions` under 4,096 characters, with what is critical first.
- [ ] Critical rules are also in the tool description.
- [ ] Every error says the way out, and that way out was tested.
- [ ] Nothing is silently ignored.
- [ ] Search returns little, read returns everything, and there is pagination.
- [ ] Responses are well under 10 thousand tokens in the common case.
- [ ] There is a way to check the result before the end.
- [ ] `tools/list` does not change with permission.
- [ ] `outputSchema` only where it is always valid.
