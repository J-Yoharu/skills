# Connect to Claude Code

How to go from a server to Claude Code: which transport, how to register it, how to authenticate, and how to test locally without a certificate.

Behaviors marked **Observed** were tested with Claude Code 2.1.318 in November 2026 and can change. Check `claude --version` and the [Claude Code MCP documentation](https://code.claude.com/docs/en/mcp) before relying on a number.

## Contents

- Choose the transport
- Register the server
- Authenticate
- Test locally without a certificate
- Headless mode
- What the client does with your server
- When the instructions exceed the limit
- Common problems
- Connecting from Claude on web, desktop and mobile

## Choose the transport

| Situation | Transport | Why |
|---|---|---|
| Local tool, runs on the person's machine | stdio | No port, no certificate, one process per session |
| Remote service, many people, data on the server | HTTP | What connectors and teams use |
| Legacy SSE server | Migrate to HTTP | SSE is deprecated in Claude Code |

On stdio, stdout belongs to the protocol. Send every log to stderr, because a stray line on stdout breaks the client.

## Register the server

```bash
# HTTP
claude mcp add --transport http my-app https://app.example.com/mcp

# HTTP with a fixed header
claude mcp add --transport http my-app http://localhost:8000/mcp \
  --header "Authorization: Bearer $MY_TOKEN"

# stdio: everything after -- is the server command
claude mcp add my-app -- node ./dist/server.js --stdio
```

The scope decides who sees the connection:

| Scope | Where it is written | Use for |
|---|---|---|
| `local` (default) | `~/.claude.json`, per project | An experiment of your own |
| `project` | `.mcp.json` at the root, versioned | A server the whole team uses |
| `user` | `~/.claude.json`, global | Your server in every project |

In a versioned file, never write the secret. Use an environment reference, accepted in `command`, `args`, `env`, `url` and `headers`:

```json
{
  "mcpServers": {
    "my-app": {
      "type": "http",
      "url": "${APP_URL:-http://localhost:8000}/mcp",
      "headers": { "Authorization": "Bearer ${MCP_EVAL_TOKEN}" }
    }
  }
}
```

**Observed:** the same expansion works in files passed to `--mcp-config`.

Well-known credential variables, such as `ANTHROPIC_API_KEY`, read as empty in `url` and `headers` of remote servers. Use a name of your own for the test token.

## Authenticate

| Mode | When | How |
|---|---|---|
| No auth | Local stdio, no sensitive data | Nothing to do |
| Fixed token in a header | Tests, automation, internal services | `--header`, or `headers` in the configuration |
| OAuth | Real people connecting their account | The client runs the flow; [oauth-integration.md](oauth-integration.md) covers the server side |

For OAuth, login works like this:

```bash
claude mcp add --scope user --transport http my-app https://app.example.com/mcp
claude mcp login my-app
```

- Inside an interactive session, `/mcp` lists the servers and offers **Authenticate**.
- On a machine with no browser, `claude mcp login my-app --no-browser` prints the URL.
- **Observed:** the `!` prefix inside a session offers no interactive terminal, and `claude mcp login` fails there. Use `/mcp` or another terminal.
- `claude -p` does not run OAuth. The login has to happen beforehand.

## Test locally without a certificate

Only the OAuth flow requires a certificate. A usability test does not need OAuth, so the fast path is a fixed token over plain HTTP.

**Observed:** all of these connected without TLS, using `claude -p` and `--mcp-config`:

```json
{
  "mcpServers": {
    "local-ip":       { "type": "http", "url": "http://127.0.0.1:8000/mcp",
                        "headers": { "Authorization": "Bearer ${MCP_EVAL_TOKEN}" } },
    "tenant-url":     { "type": "http", "url": "http://tenant-a.localhost:8000/mcp",
                        "headers": { "Authorization": "Bearer ${MCP_EVAL_TOKEN}" } },
    "tenant-by-host": { "type": "http", "url": "http://127.0.0.1:8000/mcp",
                        "headers": { "Authorization": "Bearer ${MCP_EVAL_TOKEN}",
                                     "Host": "tenant-b.localhost" } }
  }
}
```

The last form solves the application that finds the account from the subdomain: the `Host` header reaches the server as written, with no DNS or `/etc/hosts` changes.

**Observed:** a server with DNS rebinding protection refuses `tenant-a.localhost` with a 403, even with the right token. In development, add the host to the server's allowed list, or use `127.0.0.1` if the application does not depend on the subdomain.

### Where the test token comes from

Issue a **real** token, through the same service login uses, for a fixture user. The production guard validates it like any other token.

```bash
# General shape: a development command of your application
export MCP_EVAL_TOKEN="$(<command that issues a token for the fixture user>)"
```

Rules for that command:

- It exists only in development, and refuses to run in production.
- The fixture user holds only test data.
- The token is short-lived, or revoked at the end of the round.

> **Do not add a bypass to the middleware**, such as `if (env == local) allow`. That kind of shortcut has reached production in many systems, and it makes the test run through code that differs from the real path. With a real token, the path under test is the production path.

If the application cannot issue a token, keep a list of development tokens in local configuration only, never in code, and have a test prove that production refuses them.

### When you really need OAuth locally

Prefer testing OAuth on stage, where a certificate already exists. To do it locally:

- **Observed:** Claude Code refuses an HTTP `token_endpoint` outside `localhost`, `127.0.0.1` and `::1`. `http://localhost:8000` works; `http://tenant-a.localhost:8000` does not.
- For a local subdomain, put a TLS proxy in front and start the client with `NODE_EXTRA_CA_CERTS=/path/ca.pem claude`.

## Headless mode

`claude -p` runs a whole session with no interaction, and it is the base of the golden lane. This is the isolated form, which `run_golden.py` builds for you:

```bash
claude -p "<the person's request>" \
  --model haiku \
  --strict-mcp-config --mcp-config mcp.json \
  --tools "ToolSearch" --allowedTools "mcp__my-app,ToolSearch" \
  --setting-sources project \
  --no-session-persistence \
  --max-budget-usd 0.50 \
  --output-format stream-json --verbose
```

| Flag | Why it is there |
|---|---|
| `--strict-mcp-config` | Ignores the other servers on the machine |
| `--tools "ToolSearch"` | Removes built-in tools; otherwise the model can bypass your server with Bash or Read |
| `--allowedTools "mcp__my-app,..."` | Allows the whole server without asking |
| `--setting-sources project` | Run from an empty folder, it leaves out the hooks, plugins and personal instructions of whoever runs it |
| `--no-session-persistence` | Keeps test sessions out of the history |
| `--max-budget-usd` | Spend cap per run |
| `--output-format stream-json --verbose` | Records each event, ending with the `result` event |

`ToolSearch` must be allowed because, by default, the client loads tools on demand. **Observed:** with these flags and an empty folder, fixed context dropped from about 22 thousand to 4 thousand tokens, and results stopped depending on the machine.

The `--bare` flag isolates further, but it requires `ANTHROPIC_API_KEY`, since it reads no login or keychain.

## What the client does with your server

These limits shape the server design. `check_contract.py` verifies what can be verified without a model.

| Behavior | Number or rule | Consequence |
|---|---|---|
| Server `instructions` | Cut at 4,096 characters. **Observed:** cut between 3,900 and 4,300, with `[truncated]` | What passes the limit does not exist for the model. See the next section |
| Tool description | 4,096 when loaded upfront; 16,384 through tool search | Search reads only the start: put the important words first |
| Tool search | On by default; only names and `instructions` load at start | A clear tool name is worth more than it seems |
| Subagent | **Observed:** does not receive the server's `instructions` | Critical rules must also be in the tool description |
| Tool output | Warning at 10 thousand tokens, cap at 25 thousand (`MAX_MCP_OUTPUT_TOKENS`) | Paginate and summarize |
| Text over 50 thousand characters | Goes to a file | The model does not get the text directly |
| `tools/list` | **Observed:** a connection keeps the list if the server announces no change | Changed a description or tool? Reconnect, or you test yesterday's version |
| `outputSchema` | **Observed:** Claude Code validates `structuredContent` and refuses the whole response if a field has the wrong type | A `null` where the schema says `string` kills the call. Publish only what is always valid |
| Startup time | `MCP_TIMEOUT`, 30 s in `-p` with `--mcp-config` | A slow server counts as a failure |

## When the instructions exceed the limit

The limit belongs to Claude Code, not to the protocol: the MCP specification sets no size for `instructions`. The client cuts without telling the person, and what passes the limit does not exist for the model.

`check_contract.py` compares the size of the `instructions` with the limit and, if it passes, fails the contract, shows where the text stops and suggests the value:

```text
ERROR instructions-too-long: 8000 characters: Claude Code will cut at 4096 and the model
never sees the rest; the text stops at '…'. Raise the limit with
CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH=16384, or shorten the text
```

`run_golden.py` repeats the warning in the plan and in the run, and the report records whether the run measured the cut text.

**To raise the limit**, pick where the variable lives. **Observed:** all three work.

```bash
# 1. This session only
CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH=16384 claude
```

```jsonc
// 2. For you, in ~/.claude/settings.json
// 3. For the team, in the project's versioned .claude/settings.json
{ "env": { "CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH": "16384" } }
```

In the battery, put the variable in `agent.env` of `eval.config.json`. `check_contract.py` then compares against that value and keeps a warning, because anyone without the variable still gets the cut text.

Four cautions:

- **Use 16384 or more.** The client applies one number to both limits. `8192` raises the `instructions` limit but lowers the tool search description limit from 16,384 to 8,192. **Observed:** with `8192`, a marker at position 12,000 was cut; with `16384`, it passed.
- **It applies to every server in the session.** Larger instructions weigh on the context of every conversation.
- **The server author does not control this.** The variable lives on the user's machine. If your server needs it, say so in the install instructions.
- **It needs Claude Code 2.1.280 or newer.** Before 2.1.296, the default was 2,048 characters.

Raising the limit works when you control the machines, as in an internal team. For a public server, shorten the text: [server-design.md](server-design.md) shows how.

## Common problems

| Symptom | Likely cause | What to do |
|---|---|---|
| `Needs authentication` in `claude -p` | No login, or the failure mark is cached | Log in during an interactive session. **Observed:** if no request reaches the server, delete only that server's entry in `~/.claude/mcp-needs-auth-cache.json` |
| 403 `Host not allowed` or similar | The server's DNS rebinding protection | Add the host to the allowed list in development, or use `127.0.0.1` |
| Connects, but with old tools | Cached list | Reconnect through `/mcp`, or open a new session |
| Credential disappears after parallel tests | Rotating refresh token fought over by processes | Do not run parallel processes with OAuth. Use a fixed token |
| `failed` in `system/init` | Server down, wrong port, or a startup error | Run `check_contract.py`, which shows the error at no cost |
| Login opens, but the return fails | `redirect_uri` with a port other than the registered one | See loopback in [oauth-integration.md](oauth-integration.md) |
| Model calls nothing | Tool not allowed, or name and description do not say when to use it | Check `permission_denials` in the `result` event and [server-design.md](server-design.md) |
| Response refused with no server error | `outputSchema` violated | Remove the schema, or fix the field |

To inspect without a model, use the MCP Inspector too, which needs Node 22.19 or newer:

```bash
npx @modelcontextprotocol/inspector --cli --server-url http://localhost:8000/mcp --transport http --method tools/list
npx @modelcontextprotocol/inspector --cli node server.js --method tools/call --tool-name search --tool-arg q=test
```

## Connecting from Claude on web, desktop and mobile

For people to use the server outside Claude Code, they add a **custom connector** in Claude. Three differences matter:

- The connection starts from Anthropic's infrastructure, so the server must be reachable from the internet. Private networks and VPNs do not work without allowing the published IPs.
- If the server requires login, the path is OAuth. The fixed token in this guide is for testing and automation, not for people.
- **Observed:** the same server can work in the connector and fail in Claude Code, because only one side validates `outputSchema`. Test on both clients before announcing.
