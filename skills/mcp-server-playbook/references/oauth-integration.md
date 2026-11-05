# Plug in OAuth

How to plug **your** authorization server into an MCP server, so any compatible client connects with no special setup. Follow the MCP authorization specification and nothing client-specific: the same work serves Claude and whoever comes next.

Reference: [authorization in revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization), the current one in November 2026.

## Contents

- The flow the client runs
- Choose the fit
- The contract
- Step by step
- Client registration
- Many accounts on one server
- Token lifecycle
- Security
- Stable tool list
- Verify
- Pitfalls

## The flow the client runs

```text
Client                                 Your MCP server              Your authorization server
  | POST /mcp, no token                      |                                 |
  |----------------------------------------->|                                 |
  | 401 + WWW-Authenticate: resource_metadata|                                 |
  |<-----------------------------------------|                                 |
  | GET /.well-known/oauth-protected-resource/mcp                              |
  |----------------------------------------->|                                 |
  | resource + authorization_servers         |                                 |
  |<-----------------------------------------|                                 |
  | GET /.well-known/oauth-authorization-server                                |
  |--------------------------------------------------------------------------->|
  | endpoints, S256, CIMD                                                      |
  |<---------------------------------------------------------------------------|
  | browser: /authorize with PKCE and resource                                 |
  |--------------------------------------------------------------------------->|
  |                                     the person logs in and consents        |
  | code at the redirect_uri                                                   |
  |<---------------------------------------------------------------------------|
  | POST /token with code_verifier and resource                                |
  |--------------------------------------------------------------------------->|
  | access token (and refresh, if any)                                         |
  |<---------------------------------------------------------------------------|
  | POST /mcp with Bearer                    |                                 |
  |----------------------------------------->|  validates issuer, audience,    |
  | response                                 |  expiry and account state       |
  |<-----------------------------------------|                                 |
```

There are two roles. The **MCP server** is the protected resource. The **authorization server** handles login and issues tokens. They can live in the same process or not.

## Choose the fit

| Fit | When | What you build |
|---|---|---|
| **A. Ready-made authorization server** | Your provider (Auth0, Keycloak, Okta, Entra and others) covers PKCE, metadata and `resource` | Only the resource side: the RFC 9728 document, the 401 and token validation |
| **B. Your own server with a library** | The application already manages users and no external provider issues the token | OAuth endpoints with a mature library for your stack |
| **C. Facade over the existing login** | People sign in through your own login, or through a provider that lacks what MCP asks for | Your own server, as in B, that delegates identification to the current login and issues its own token |

Before choosing A, check the provider for: public metadata, PKCE with S256, acceptance of the `resource` parameter, and a token with the right audience. Many providers fall short on `resource` or client registration, and the way out becomes C.

In fit C, the flow usually goes like this: `/authorize` validates the request and stores it in a cache, redirects to a screen of your application, the person signs in with the usual login and approves, and only then the `code` is issued, tied to user, account and `resource`.

## The contract

Fill in this table for your application. `check_auth.py` verifies the rows marked ✓ automatically.

| | Item | Rule | Your value |
|---|---|---|---|
| ✓ | 401 with no token | `WWW-Authenticate: Bearer resource_metadata="<url>"` | `<…>` |
| ✓ | Resource document (RFC 9728) | `/.well-known/oauth-protected-resource/<path>` with `resource` and `authorization_servers` | `<…>` |
| ✓ | Server metadata (RFC 8414 or OIDC) | `issuer` **identical** to the one used to build the URL; endpoints on HTTPS | `<…>` |
| ✓ | PKCE | `code_challenge_methods_supported` contains `S256`. If the field is missing, the client refuses to continue | `<…>` |
| ✓ | Response type | `code`, with `authorization_code` and, preferably, `refresh_token` | `<…>` |
| ✓ | Client registration | `client_id_metadata_document_supported: true` (CIMD). `registration_endpoint` only for compatibility | `<…>` |
| ✓ | Mix-up (RFC 9207) | `iss` in the authorization response, announced in the metadata | `<…>` |
| ✓ | Invalid token | 401, never 403 or 500, so the client tries to refresh | `<…>` |
| | `resource` (RFC 8707) | Required at `/authorize` and `/token`, and recorded in the token | `<…>` |
| | Audience | The resource accepts only tokens issued for it | `<…>` |
| | Insufficient scope | 403 with `error="insufficient_scope"`, `scope` and `resource_metadata` | `<…>` |
| | Rate limit | 429 with `Retry-After`. Never 401, which would trigger a refresh | `<…>` |

Changes in revision 2026-07-28 worth checking if you followed older material:

- DCR (dynamic registration) is **deprecated**. New implementations go with CIMD.
- The client must validate the `iss` of the response, and the authorization server should send it.
- The metadata `issuer` must be identical to the identifier used in the URL.
- The client cannot assume it gets a refresh token, and the server should not put `offline_access` in the `WWW-Authenticate` scope.
- HTTP transport lost protocol sessions and the GET stream. Each POST carries `MCP-Protocol-Version` and `Mcp-Method`, and the server must implement `server/discover`.

## Step by step

1. **Choose the address.** Use the URL the person already knows. In a multi-account application, `https://<account>.example.com/mcp` beats a universal address, because the person does not need to say which account they use.
2. **Publish the resource document**, without touching a database. Answer at the root too (`/.well-known/oauth-protected-resource`), because some clients try it first.
3. **Publish the authorization server metadata**, or point to the provider's.
4. **Return the right 401** at the MCP address. The header must wrap the guard, so it also goes out when a token is refused.
5. **Implement `/authorize`:** validate client, `redirect_uri`, PKCE S256 and `resource`, in that order, before showing any screen.
6. **Show the consent screen:** who is asking, whether they are verified, and what they will access.
7. **Issue the `code`** tied to user, account and `resource`, single-use and short-lived.
8. **Implement `/token`:** code exchange and refresh, always checking `code_verifier` and `resource`.
9. **Implement revocation**, and the screen where the person sees and ends connections.
10. **Validate at the resource:** issuer, audience, expiry and, on each call, the account state.
11. **Run `check_auth.py`** and do one real login on stage.

## Client registration

The client's order of preference is: pre-registration, CIMD, DCR and, finally, asking the person.

- **CIMD (recommended).** The `client_id` is a URL pointing to a public document. Fetch that document only from hosts on an allowed list, because this is a fetch by your server based on data from outside.
- **DCR (legacy).** Accept only `redirect_uri` values from a list, limit by IP and clean up orphan clients.
- **Pre-registration.** For a small number of known clients.

When fetching a CIMD document, protect against SSRF:

- A list of allowed hosts and prefixes, not any URL.
- Resolve DNS and refuse private, loopback and cloud metadata IPs.
- Connect to the validated IP, to avoid DNS swapping.
- Do not follow redirects.
- Limits on time and size, and a cache with expiry.

**Observed for Claude clients.** These values worked in production, but the official documentation does not publish them; check before hardcoding:

| Item | Value |
|---|---|
| CIMD `client_id` prefix | `https://claude.ai/oauth/` |
| Claude Code example | `https://claude.ai/oauth/claude-code-client-metadata` |
| Web connector callback | `https://claude.ai/api/mcp/auth_callback` |
| Claude Code callback | `http://localhost/callback` with an ephemeral port |

### Loopback

The client document declares `http://localhost/callback` with no port, and the application uses an ephemeral port. Compare `redirect_uri` exactly, ignoring **only** the port, and only for `http` with host `localhost` or `127.0.0.1` (RFC 8252, section 7.3). Many libraries ignore the port only for `127.0.0.1`, and login fails on the way back. Refuse a URI with control characters, spaces or backslashes, which the browser normalizes into something else.

## Many accounts on one server

When the account comes from the subdomain:

- Resolve the account from the `Host` header, not `Origin`, because command-line clients send no `Origin`.
- Accept only suffixes on a list.
- `issuer` and `resource` are per account, so each account has its own metadata.
- Store tokens so that a token from one account is worthless in another.
- At the load balancer, send `/mcp`, `/.well-known/oauth-*` and `/oauth/*` to the application, even if the rest of the host goes to the front end.

## Token lifecycle

| Item | Recommendation |
|---|---|
| Access token | Short, about 1 hour |
| Refresh token | Rotating, with reuse detection |
| Refresh validity | By inactivity, with no absolute deadline, so people log in again only for a real reason |
| Revocation by state | Check on every call and refresh: active user, active account, feature enabled |
| Password change or reset | Revokes the person's connections |
| Turning the feature off | Revoke for real, or the token works again when it is turned back on |
| Identity provider down | Temporary error. Do not revoke |

## Security

- [ ] No token passthrough: the MCP server does not forward the received token to another service.
- [ ] Audience checked on every call.
- [ ] Single-use, short-lived `code`, and PKCE with no exceptions.
- [ ] Consent shows who is asking, and tells verified from unverified clients.
- [ ] Admin impersonation does not authorize connections.
- [ ] Per-IP limits on the OAuth endpoints, which are open.
- [ ] Limits on `tools/call`, per connection, person and account. `initialize` and `tools/list` do not count.
- [ ] A refreshed token does not reset the limit: the key uses user and client, not the token.
- [ ] Every tool call is logged (who, tool, truncated arguments, duration, status) with a retention period.
- [ ] Widening the client list is a security decision, because that is how a third party receives your users' authorization codes.

## Stable tool list

Keep `tools/list` the same for everyone and check permission **inside the tool**, at call time. If the list changes with permission, everyone already connected must reconnect on each change, because the client keeps the list. When the person has no access, the tool answers with a result that explains it.

A new tool or a new description requires reconnection by whoever is already connected. Group those changes and tell people.

## Verify

Without a browser:

```bash
python3 -B scripts/check_auth.py --url https://stage.example.com/mcp
python3 -B scripts/check_auth.py --url https://stage.example.com/mcp --token "$TOKEN"
python3 -B scripts/check_auth.py --url https://stage.example.com/mcp --client-id "$CLIENT" --redirect-uri "$REDIRECT"
```

The last form confirms `/authorize` refuses requests without PKCE or with `plain`.

Then a manual test on stage, once per auth change:

1. `claude mcp add --transport http app-stage https://stage.example.com/mcp`.
2. In an interactive session, `/mcp` and **Authenticate**.
3. Log in, approve, and check the tools.
4. Call a tool.
5. Wait for the access token to expire, or shorten its lifetime on stage, and confirm the refresh is silent.
6. Revoke the connection on your screen and confirm the 401 on the next call.
7. Repeat the connection through the Claude web connector.

## Pitfalls

| Pitfall | Effect | Way out |
|---|---|---|
| `resource` in the document differs from the real URL | Client gives up at discovery | Build the value from the request host, or a single configuration |
| Metadata behind auth or the front end | 404, or HTML where JSON is expected | Its own open route, with no database |
| 401 without `resource_metadata` | Client has no hint where to authenticate | Middleware that wraps the guard |
| 429 answered as 401 | Refresh loop | The right status, with `Retry-After` |
| Rotating refresh with many processes | The second process invalidates the credential | One session at a time, and a fixed token for automation |
| Permission flag changing `tools/list` | Reconnection on each change | Stable list, permission at call time |
| `outputSchema` with an optional field of the wrong type | Response refused by one client and accepted by another | Do not publish it, or validate before responding |
| Testing only in the developer's browser | An old session masks the failure | Private window and a test user |
