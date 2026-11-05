#!/usr/bin/env python3
"""Demo MCP server: a fictional notebook, standard library only.

It serves two purposes: trying the kit before plugging in your server, and showing in
a few lines what the guides recommend (errors that teach the way out, lean search
with full reads, short instructions).

It has one deliberate gap: `list_notes` cannot filter by tag, so counting notes by tag
means walking every page. `--with-tag-filter` closes the gap, to compare before and
after.

Usage:
  demo_server.py --stdio --data notes.json
  demo_server.py --stdio --data notes.json --with-tag-filter
  demo_server.py --http --port 8799 --token dev-token --data notes.json
  demo_server.py --http --port 8799 --oauth-metadata    # exposes fake OAuth discovery
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

INSTRUCTIONS = """The person's notebook. Only the notes stored here exist.

Flow:
1. To find a note, use search_notes; it returns the title and a summary.
2. To read the full text, use get_note with the id from the search.
3. To store a new note, use create_note, then check it with get_note.

If the person mentions a note the search cannot find, say so instead of making it up."""

TOOLS = [
    {
        "name": "search_notes",
        "description": "Searches notes by a word in the title, text or tag. Use it first when the person mentions a topic. Returns the id, title and summary of up to 5 notes; for the full text, call get_note.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Word or phrase to look for, as the person said it."}},
            "required": ["query"],
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "get_note",
        "description": "Reads a whole note by the id returned from search_notes. Never make up an id.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Note identifier, such as n1."}},
            "required": ["id"],
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "create_note",
        "description": "Stores a new note. Use it only when the person asks to create or save something. Returns the new id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title, up to 80 characters."},
                "body": {"type": "string", "description": "Full text of the note."},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Lowercase tags."},
            },
            "required": ["title", "body"],
        },
    },
]


PAGE_SIZE = 5

LIST_NOTES = {
    "name": "list_notes",
    "description": "Lists notes page by page, 5 at a time, with id, title and tags. Use it to go through the notebook; pass the next_offset from the previous page to continue.",
    "inputSchema": {
        "type": "object",
        "properties": {"offset": {"type": "integer", "description": "Position of the first note; 0 for the first page."}},
    },
    "annotations": {"readOnlyHint": True},
}

TAG_PARAMETER = {"tag": {"type": "string", "description": "Return only notes with this tag. The response carries `total`, so counting needs a single call."}}


class NoteStore:
    """Keeps notes in a JSON file, so the result survives the end of the process."""

    def __init__(self, path: Path | None):
        self.path = path

    def _load(self) -> list[dict]:
        if self.path and self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return []

    def _save(self, notes: list[dict]) -> None:
        if self.path:
            self.path.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")

    def search(self, query: str) -> list[dict]:
        needle = query.lower()
        found = [n for n in self._load() if needle in f"{n['title']} {n['body']} {' '.join(n.get('tags', []))}".lower()]
        return [{"id": n["id"], "title": n["title"], "summary": n["body"][:80]} for n in found[:5]]

    def page(self, offset: int, tag: str | None) -> dict:
        notes = [n for n in self._load() if tag is None or tag.lower() in n.get("tags", [])]
        items = [{"id": n["id"], "title": n["title"], "tags": n.get("tags", [])} for n in notes[offset:offset + PAGE_SIZE]]
        following = offset + PAGE_SIZE
        return {"notes": items, "next_offset": following if following < len(notes) else None, **({"total": len(notes)} if tag else {})}

    def get(self, note_id: str) -> dict | None:
        return next((n for n in self._load() if n["id"] == note_id), None)

    def create(self, title: str, body: str, tags: list[str]) -> str:
        notes = self._load()
        note_id = f"n{len(notes) + 1}"
        notes.append({"id": note_id, "title": title, "body": body, "tags": tags})
        self._save(notes)
        return note_id


def call_tool(store: NoteStore, name: str, args: dict) -> dict:
    """Run the tool; an error always says the way out, so the model can recover."""

    def text(value: object, is_error: bool = False) -> dict:
        body = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        return {"content": [{"type": "text", "text": body}], "isError": is_error}

    if name == "search_notes":
        query = str(args.get("query", "")).strip()
        if not query:
            return text("Empty query: pass the word the person used.", True)
        results = store.search(query)
        return text({"results": results} if results else f"No note with '{query}'. Try a shorter word, or tell the person there is no such note.")
    if name == "list_notes":
        return text(store.page(int(args.get("offset") or 0), args.get("tag")))
    if name == "get_note":
        note = store.get(str(args.get("id", "")))
        return text(note) if note else text(f"Note {args.get('id')!r} does not exist. Use an id returned by search_notes.", True)
    if name == "create_note":
        title, body = str(args.get("title", "")).strip(), str(args.get("body", "")).strip()
        if not title or len(title) > 80:
            return text("title must have 1 to 80 characters: shorten it and call again.", True)
        if not body:
            return text("Empty body: pass the text of the note.", True)
        return text({"id": store.create(title, body, list(args.get("tags") or []))})
    return text(f"Tool {name} does not exist. Available: {', '.join(t['name'] for t in tools_for(True))}.", True)


def tools_for(with_tag_filter: bool) -> list[dict]:
    listing = {**LIST_NOTES, "inputSchema": {"type": "object", "properties": {**LIST_NOTES["inputSchema"]["properties"], **TAG_PARAMETER}}} if with_tag_filter else LIST_NOTES
    return [*TOOLS, listing]


def handle_rpc(store: NoteStore, message: dict, with_tag_filter: bool = False) -> dict | None:
    """Answer one JSON-RPC message; notifications get no reply."""
    if "id" not in message:
        return None
    method, params = message.get("method"), message.get("params") or {}
    if method == "initialize":
        result: dict = {
            "protocolVersion": params.get("protocolVersion", "2025-11-25"),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "demo-notes", "version": "1.0.0"},
            "instructions": INSTRUCTIONS,
        }
    elif method == "tools/list":
        result = {"tools": tools_for(with_tag_filter)}
    elif method == "tools/call":
        result = call_tool(store, params.get("name", ""), params.get("arguments") or {})
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": f"unknown method: {method}"}}
    return {"jsonrpc": "2.0", "id": message["id"], "result": result}


def serve_stdio(store: NoteStore, with_tag_filter: bool) -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        reply = handle_rpc(store, json.loads(line), with_tag_filter)
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()


def oauth_documents(origin: str) -> dict[str, dict]:
    """Fake OAuth discovery: only for exercising the kit's auth check."""
    return {
        "/.well-known/oauth-protected-resource/mcp": {
            "resource": f"{origin}/mcp",
            "authorization_servers": [origin],
            "bearer_methods_supported": ["header"],
        },
        "/.well-known/oauth-authorization-server": {
            "issuer": origin,
            "authorization_endpoint": f"{origin}/oauth/authorize",
            "token_endpoint": f"{origin}/oauth/token",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "client_id_metadata_document_supported": True,
            "authorization_response_iss_parameter_supported": True,
        },
    }


def make_handler(store: NoteStore, token: str | None, oauth: bool) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            """Silence the default log: the kit's output must stay readable."""

        def _origin(self) -> str:
            return f"http://{self.headers.get('Host', '127.0.0.1')}"

        def _json(self, status: int, payload: dict, headers: dict | None = None) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            document = oauth_documents(self._origin()).get(self.path) if oauth else None
            if document:
                self._json(200, document)
            else:
                self.send_response(405 if self.path == "/mcp" else 404)
                self.send_header("Content-Length", "0")
                self.end_headers()

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            message = json.loads(self.rfile.read(length) or b"{}")
            if (token or oauth) and self.headers.get("Authorization") != f"Bearer {token}":
                metadata = f'{self._origin()}/.well-known/oauth-protected-resource/mcp'
                self._json(401, {"error": "invalid_token"}, {"WWW-Authenticate": f'Bearer resource_metadata="{metadata}"'})
                return
            reply = handle_rpc(store, message)
            if reply is None:
                self.send_response(202)
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                self._json(200, reply)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stdio", action="store_true")
    parser.add_argument("--http", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8799)
    parser.add_argument("--token")
    parser.add_argument("--data", type=Path)
    parser.add_argument("--oauth-metadata", action="store_true")
    parser.add_argument("--with-tag-filter", action="store_true", help="close the deliberate gap in list_notes")
    args = parser.parse_args()
    store = NoteStore(args.data)
    if args.http:
        ThreadingHTTPServer((args.host, args.port), make_handler(store, args.token, args.oauth_metadata)).serve_forever()
    else:
        serve_stdio(store, args.with_tag_filter)


if __name__ == "__main__":
    main()
