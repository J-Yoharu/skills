#!/usr/bin/env python3
"""Minimal MCP client, standard library only.

It powers the checks that need no model (contract and auth). It speaks JSON-RPC
over stdio or HTTP, reads the same `--mcp-config` file Claude Code uses, and
expands `${VAR}` and `${VAR:-default}` the same way, so the configuration under
check is the one the model will get.
"""
from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

CLIENT_INFO = {"name": "mcp-eval-kit", "version": "1.0.0"}
PROTOCOL_VERSION = "2025-11-25"

_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


class McpError(RuntimeError):
    """Transport failure, or a JSON-RPC error returned by the server."""


def expand_env(value: Any, env: dict[str, str] | None = None) -> Any:
    """Expand environment references in strings, lists and objects."""
    source = os.environ if env is None else env
    if isinstance(value, str):
        return _ENV_REF.sub(lambda m: source.get(m.group(1), m.group(2) if m.group(2) is not None else m.group(0)), value)
    if isinstance(value, list):
        return [expand_env(item, env) for item in value]
    if isinstance(value, dict):
        return {key: expand_env(item, env) for key, item in value.items()}
    return value


def load_server(mcp_config: Path, name: str | None = None, env: dict[str, str] | None = None) -> tuple[str, dict]:
    """Return the name and the expanded configuration of one server in the file."""
    servers = json.loads(Path(mcp_config).read_text(encoding="utf-8")).get("mcpServers", {})
    if not servers:
        raise McpError(f"{mcp_config} declares no server under mcpServers")
    chosen = name or next(iter(servers))
    if chosen not in servers:
        raise McpError(f"server '{chosen}' is not in {mcp_config}; available: {', '.join(servers)}")
    return chosen, expand_env(servers[chosen], env)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Return the 3xx as a response: following it would hide what the server said."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def http_request(method: str, url: str, headers: dict | None = None, body: bytes | None = None, timeout: float = 15) -> tuple[int, dict, bytes]:
    """Send a request without raising on HTTP status; header names come back lowercase."""
    request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read()
    except urllib.error.HTTPError as error:
        with error:
            return error.code, {k.lower(): v for k, v in error.headers.items()}, error.read()
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise McpError(f"no response from {url}: {error}") from error


class HttpClient:
    """HTTP transport: one JSON response or one SSE stream per POST."""

    def __init__(self, url: str, headers: dict | None = None, timeout: float = 20):
        self.url = url
        self.headers = dict(headers or {})
        self.timeout = timeout
        self.protocol_version: str | None = None
        self.session_id: str | None = None
        self._next_id = 0

    def _headers(self, method: str) -> dict:
        headers = {
            **self.headers,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Mcp-Method": method,
        }
        if self.protocol_version:
            headers["MCP-Protocol-Version"] = self.protocol_version
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    def request(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        request_id = self._next_id
        payload = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}).encode()
        http = urllib.request.Request(self.url, data=payload, headers=self._headers(method), method="POST")
        try:
            with _OPENER.open(http, timeout=self.timeout) as response:
                self.session_id = response.headers.get("Mcp-Session-Id") or self.session_id
                if "text/event-stream" in (response.headers.get("Content-Type") or ""):
                    return _unwrap(_read_sse(response, request_id))
                return _unwrap(json.loads(response.read()))
        except urllib.error.HTTPError as error:
            raise McpError(f"{method}: HTTP {error.code} {error.read()[:200].decode(errors='replace')}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise McpError(f"{method}: no response from {self.url}: {error}") from error

    def notify(self, method: str, params: dict | None = None) -> None:
        payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}}).encode()
        http_request("POST", self.url, self._headers(method), payload, self.timeout)

    def close(self) -> None:
        """HTTP holds no process; this exists so stdio and HTTP clients are interchangeable."""


def _read_sse(response: Any, request_id: int) -> dict:
    """Read the stream until the reply to this request; notifications in between are skipped."""
    data: list[str] = []
    for raw in response:
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if line.startswith("data:"):
            data.append(line[5:].strip())
        elif not line and data:
            message = json.loads("".join(data))
            data = []
            if message.get("id") == request_id:
                return message
    raise McpError("the SSE stream ended without a reply to the request")


def _unwrap(message: dict) -> dict:
    if "error" in message:
        raise McpError(f"JSON-RPC error: {message['error']}")
    return message.get("result", {})


class StdioClient:
    """Stdio transport: one child process, one JSON message per line."""

    def __init__(self, command: str, args: list[str] | None = None, env: dict | None = None, timeout: float = 20):
        self.timeout = timeout
        self.protocol_version: str | None = None
        self._next_id = 0
        self._lines: queue.Queue[str | None] = queue.Queue()
        try:
            self._process = subprocess.Popen(
                [command, *(args or [])],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env={**os.environ, **(env or {})},
                text=True,
                encoding="utf-8",
            )
        except OSError as error:
            raise McpError(f"could not start {command}: {error}") from error
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        for line in self._process.stdout:
            self._lines.put(line)
        self._lines.put(None)

    def _send(self, message: dict) -> None:
        try:
            self._process.stdin.write(json.dumps(message) + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            raise McpError(f"the server closed stdin: {error}") from error

    def request(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        request_id = self._next_id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        while True:
            try:
                line = self._lines.get(timeout=self.timeout)
            except queue.Empty as error:
                raise McpError(f"{method}: no response in {self.timeout}s") from error
            if line is None:
                raise McpError(f"{method}: the server exited without responding")
            try:
                message = json.loads(line)
            except ValueError:
                # Log noise on stdout breaks real clients; here we just move on.
                continue
            if message.get("id") == request_id:
                return _unwrap(message)

    def notify(self, method: str, params: dict | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def close(self) -> None:
        try:
            self._process.stdin.close()
            self._process.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            self._process.kill()


def connect(config: dict, timeout: float = 20) -> HttpClient | StdioClient:
    """Open the transport described by one `mcpServers` entry."""
    if config.get("url"):
        return HttpClient(config["url"], config.get("headers"), timeout)
    if config.get("command"):
        return StdioClient(config["command"], config.get("args"), config.get("env"), timeout)
    raise McpError("the server entry needs `url` or `command`")


def handshake(client: HttpClient | StdioClient) -> dict:
    """Run `initialize` and return the instructions, capabilities and server identity."""
    result = client.request(
        "initialize",
        {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO},
    )
    client.protocol_version = result.get("protocolVersion", PROTOCOL_VERSION)
    client.notify("notifications/initialized")
    return result


def list_tools(client: HttpClient | StdioClient) -> list[dict]:
    """Walk every page of `tools/list`."""
    tools: list[dict] = []
    cursor: str | None = None
    while True:
        page = client.request("tools/list", {"cursor": cursor} if cursor else {})
        tools.extend(page.get("tools", []))
        cursor = page.get("nextCursor")
        if not cursor:
            return tools
