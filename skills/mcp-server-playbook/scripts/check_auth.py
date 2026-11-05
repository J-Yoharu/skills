#!/usr/bin/env python3
"""Auth lane: check MCP OAuth discovery with no browser and no model.

It follows a real client's path from the 401 and compares each document with the
authorization specification. It only reads metadata; `--token` and `--client-id`
add the negative probes.

Usage:
  check_auth.py --url https://app.example.com/mcp
  check_auth.py --url https://app.example.com/mcp --token "$TOKEN"
  check_auth.py --url https://app.example.com/mcp --client-id ID --redirect-uri URI
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

# Python's isolated mode (-I) leaves the script's own folder off the path, and the kit's modules live there.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kitlib.mcp_client import PROTOCOL_VERSION, McpError, http_request

LOOPBACK = {"localhost", "127.0.0.1", "::1"}
INITIALIZE = json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "mcp-eval-kit", "version": "1.0.0"}},
}).encode()
MCP_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "Mcp-Method": "initialize"}


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, status: str, rule: str, detail: str) -> None:
        self.rows.append((status, rule, detail))
        print(f"  {status:5} {rule}: {detail}")

    def check(self, passed: bool, rule: str, detail: str, severity: str = "FAIL") -> bool:
        # A warning's text explains the risk, so it only makes sense when the warning fires.
        self.add("OK" if passed else severity, rule, "" if passed and severity == "WARN" else detail)
        return passed

    @property
    def failed(self) -> int:
        return sum(1 for status, _, _ in self.rows if status == "FAIL")


def is_secure(url: str) -> bool:
    parts = urlsplit(url)
    host = parts.hostname or ""
    return parts.scheme == "https" or host in LOOPBACK or host.endswith(".localhost")


def get_json(url: str) -> dict | None:
    try:
        status, _, body = http_request("GET", url, {"Accept": "application/json"})
    except McpError:
        return None
    if status != 200:
        return None
    try:
        return json.loads(body)
    except ValueError:
        return None


def resource_metadata_urls(mcp_url: str, challenge: str) -> list[str]:
    """The challenge's address first, then the well-known paths of RFC 9728."""
    announced = re.search(r'resource_metadata="?([^",\s]+)', challenge or "")
    parts = urlsplit(mcp_url)
    origin = f"{parts.scheme}://{parts.netloc}"
    urls = [announced.group(1)] if announced else []
    path = parts.path.rstrip("/")
    urls.extend([f"{origin}/.well-known/oauth-protected-resource{path}", f"{origin}/.well-known/oauth-protected-resource"])
    return urls


def server_metadata_urls(issuer: str) -> list[str]:
    """RFC 8414 and OIDC lookup order, for issuers with and without a path."""
    parts = urlsplit(issuer)
    origin, path = f"{parts.scheme}://{parts.netloc}", parts.path.rstrip("/")
    if path:
        return [
            f"{origin}/.well-known/oauth-authorization-server{path}",
            f"{origin}/.well-known/openid-configuration{path}",
            f"{origin}{path}/.well-known/openid-configuration",
        ]
    return [f"{origin}/.well-known/oauth-authorization-server", f"{origin}/.well-known/openid-configuration"]


def check_challenge(report: Report, url: str) -> str:
    status, headers, _ = http_request("POST", url, MCP_HEADERS, INITIALIZE)
    report.check(status == 401, "challenge-401", f"without a token, the server answered {status}")
    challenge = headers.get("www-authenticate", "")
    report.check(challenge.lower().startswith("bearer"), "challenge-bearer", f"WWW-Authenticate: {challenge[:120] or 'missing'}")
    report.check("resource_metadata" in challenge, "challenge-resource-metadata", "the challenge should point to the resource document", "WARN")
    return challenge


def check_resource(report: Report, url: str, challenge: str) -> dict | None:
    document = None
    for candidate in resource_metadata_urls(url, challenge):
        document = get_json(candidate)
        if document:
            report.add("OK", "resource-metadata", f"read from {candidate}")
            break
    if not document:
        report.add("FAIL", "resource-metadata", "no address returned the RFC 9728 document")
        return None
    report.check(document.get("resource", "").rstrip("/") == url.rstrip("/"), "resource-match", f"resource = {document.get('resource')}")
    report.check(bool(document.get("authorization_servers")), "resource-authorization-servers", f"{document.get('authorization_servers')}")
    return document


def check_server(report: Report, issuer: str) -> dict | None:
    document = None
    for candidate in server_metadata_urls(issuer):
        document = get_json(candidate)
        if document:
            report.add("OK", "server-metadata", f"read from {candidate}")
            break
    if not document:
        report.add("FAIL", "server-metadata", f"no metadata document for {issuer}")
        return None
    report.check(document.get("issuer") == issuer, "server-issuer", f"issuer = {document.get('issuer')} (must be identical to {issuer})")
    for endpoint in ("authorization_endpoint", "token_endpoint"):
        value = document.get(endpoint, "")
        report.check(bool(value) and is_secure(value), f"server-{endpoint}", value or "missing")
    report.check("S256" in document.get("code_challenge_methods_supported", []), "server-pkce-s256", f"code_challenge_methods_supported = {document.get('code_challenge_methods_supported')}")
    report.check("code" in document.get("response_types_supported", []), "server-response-code", f"{document.get('response_types_supported')}")
    grants = document.get("grant_types_supported", ["authorization_code"])
    report.check("authorization_code" in grants, "server-grant-code", f"{grants}")
    report.check("refresh_token" in grants, "server-grant-refresh", "without refresh, the person logs in again whenever the token expires", "WARN")
    cimd = bool(document.get("client_id_metadata_document_supported"))
    report.check(cimd or bool(document.get("registration_endpoint")), "server-client-registration", "without CIMD or DCR, only pre-registered clients can connect", "WARN")
    report.check(cimd, "server-cimd", "CIMD is the recommended path; DCR is deprecated in the current revision", "WARN")
    report.check(bool(document.get("authorization_response_iss_parameter_supported")), "server-iss-param", "RFC 9207: returning `iss` in the authorization response protects against mix-up", "WARN")
    return document


def check_token(report: Report, url: str, token: str) -> None:
    good, _, _ = http_request("POST", url, {**MCP_HEADERS, "Authorization": f"Bearer {token}"}, INITIALIZE)
    report.check(good == 200, "token-valid", f"a valid token got {good}")
    bad, _, _ = http_request("POST", url, {**MCP_HEADERS, "Authorization": "Bearer invalid-probe-token"}, INITIALIZE)
    report.check(bad == 401, "token-invalid", f"an invalid token got {bad} (403 or 500 stop the client from refreshing)")


def check_authorize_rejects(report: Report, endpoint: str, resource: str, client_id: str, redirect_uri: str) -> None:
    """A request without PKCE, or with `plain`, must not reach the login screen."""
    base = {"response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri, "resource": resource, "state": "probe"}
    probes = {
        "authorize-requires-pkce": base,
        "authorize-rejects-plain": {**base, "code_challenge": "a" * 43, "code_challenge_method": "plain"},
    }
    for rule, params in probes.items():
        status, headers, _ = http_request("GET", f"{endpoint}?{urlencode(params)}")
        location = headers.get("location", "")
        has_error = "error" in parse_qs(urlsplit(location).query)
        report.check(status >= 400 or has_error, rule, f"status {status}, location {location[:100] or 'empty'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", required=True, help="protected MCP address")
    parser.add_argument("--token", help="valid token for the 200 and 401 probes")
    parser.add_argument("--client-id", help="registered client for the /authorize probes")
    parser.add_argument("--redirect-uri")
    args = parser.parse_args()

    report = Report()
    print(f"discovery of {args.url}")
    try:
        report.check(is_secure(args.url), "transport", "address uses HTTPS or loopback")
        challenge = check_challenge(report, args.url)
        resource = check_resource(report, args.url, challenge)
        servers = (resource or {}).get("authorization_servers") or []
        server = check_server(report, servers[0]) if servers else None
        if args.token:
            check_token(report, args.url, args.token)
        if server and args.client_id and args.redirect_uri:
            check_authorize_rejects(report, server["authorization_endpoint"], args.url, args.client_id, args.redirect_uri)
    except McpError as error:
        report.add("FAIL", "connection", str(error))
    print("auth failed" if report.failed else "auth passed")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
