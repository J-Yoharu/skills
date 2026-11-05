#!/usr/bin/env python3
"""Contract lane: what the client receives from the server, with no model and no cost.

It runs in seconds and fits CI. It checks the size budget of the instructions and
descriptions, the quality of the schemas, and contract changes against the saved
snapshot.

Usage:
  check_contract.py --config eval.config.json
  check_contract.py --config eval.config.json --update-snapshot
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
import tempfile
from collections import namedtuple

# Python's isolated mode (-I) leaves the script's own folder off the path, and the kit's modules live there.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kitlib.golden_common import LIMIT_ENV, ConfigError, effective_limits, from_base, load_config, server_env
from kitlib.mcp_client import McpError, connect, handshake, list_tools, load_server

Finding = namedtuple("Finding", "severity rule message")

TOOL_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SHORT_DESCRIPTION_CHARS = 40


def suggested_limit(instructions: str, tools: list[dict], limits: dict) -> int:
    """Smallest value that cuts nothing and does not lower the tool search limit."""
    longest = max((len(tool.get("description") or "") for tool in tools), default=0)
    needed = max(len(instructions), longest, limits.get("default_description_chars", limits["tool_description_chars"]))
    return -(-needed // 1024) * 1024


def cut_warning(instructions_chars: int, limits: dict) -> str | None:
    """Short sentence warning, before any spend, that the model will get cut text."""
    if instructions_chars <= limits["instructions_chars"]:
        return None
    return f"instructions have {instructions_chars} characters: Claude Code cuts them at {limits['instructions_chars']}, so this run measures the cut text; shorten them, or set {LIMIT_ENV} to 16384 or more"


def inspect_instructions(instructions: str, tools: list[dict], limits: dict) -> list[Finding]:
    """Warn when the client will cut the instructions, and suggest how to avoid it."""
    if not instructions:
        return [Finding("WARN", "instructions-empty", "the server publishes no instructions; the flow depends on descriptions alone")]
    size, budget = len(instructions), limits["instructions_chars"]
    default = limits.get("default_instructions_chars", budget)
    override = limits.get("override")
    suggestion = suggested_limit(instructions, tools, limits)
    findings: list[Finding] = []
    if size > budget:
        lost = re.findall(r"^#{1,6} .*", instructions[budget:], re.M)
        detail = f"; sections lost: {', '.join(lost)}" if lost else ""
        findings.append(Finding(
            "ERROR",
            "instructions-too-long",
            f"{size} characters: Claude Code will cut at {budget} and the model never sees the rest; the text stops at '…{instructions[budget - 40:budget]}'{detail}. "
            f"Raise the limit with {LIMIT_ENV}={suggestion}, or shorten the text",
        ))
    elif size > default:
        findings.append(Finding("WARN", "instructions-need-raised-limit", f"{size} characters exceed the default of {default}: {LIMIT_ENV}={override} avoids the cut here, but anyone connecting without that variable gets the cut text"))
    search_limit = limits.get("default_description_chars", limits["tool_description_chars"])
    if override and override < search_limit:
        findings.append(Finding("WARN", "raised-limit-lowers-search", f"{LIMIT_ENV}={override} also lowers the tool search description limit from {search_limit} to {override}; prefer {suggestion}"))
    return findings


def inspect_contract(init: dict, tools: list[dict], limits: dict) -> list[Finding]:
    """Compare what the server announces with the client limits and good practice."""
    findings = inspect_instructions(init.get("instructions") or "", tools, limits)
    for tool in tools:
        name = tool.get("name", "")
        description = tool.get("description") or ""
        if not TOOL_NAME.match(name):
            findings.append(Finding("ERROR", "tool-name", f"invalid name: {name!r}"))
        if len(description) < SHORT_DESCRIPTION_CHARS:
            findings.append(Finding("WARN", "tool-description-short", f"{name}: a description of {len(description)} characters does not say when to use the tool"))
        if len(description) > limits["tool_description_chars"]:
            findings.append(Finding("ERROR", "tool-description-too-long", f"{name}: {len(description)} characters, cut at {limits['tool_description_chars']}"))
        elif len(description) > limits["upfront_description_chars"]:
            findings.append(Finding("WARN", "tool-description-upfront", f"{name}: {len(description)} characters; without tool search the cut is at {limits['upfront_description_chars']}"))
        schema = tool.get("inputSchema") or {}
        if schema.get("type") != "object":
            findings.append(Finding("ERROR", "tool-schema", f"{name}: inputSchema must be an object"))
        for prop, spec in (schema.get("properties") or {}).items():
            if not isinstance(spec, dict) or not spec.get("description"):
                findings.append(Finding("WARN", "param-undocumented", f"{name}.{prop}: parameter has no description"))
        if tool.get("outputSchema"):
            findings.append(Finding("WARN", "output-schema", f"{name}: outputSchema is published; one field of the wrong type makes the client refuse the whole response"))
    surface = surface_chars(tools)
    if limits.get("surface_chars") and surface > limits["surface_chars"]:
        findings.append(Finding("ERROR", "surface-too-large", f"surface of {surface} characters exceeds the budget of {limits['surface_chars']}"))
    return findings


def surface_chars(tools: list[dict]) -> int:
    """Size of what the model reads from the tools: name, description and schema."""
    return sum(len(tool.get("name", "")) + len(tool.get("description") or "") + len(json.dumps(tool.get("inputSchema") or {}, ensure_ascii=False)) for tool in tools)


def contract_snapshot(init: dict, tools: list[dict]) -> dict:
    return {"instructions": init.get("instructions") or "", "tools": sorted(tools, key=lambda tool: tool.get("name", ""))}


def fingerprint(snapshot: dict) -> str:
    """Identify the contract version a run measured."""
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def diff_snapshot(old: dict, new: dict) -> list[str]:
    changes = []
    if old.get("instructions") != new.get("instructions"):
        changes.append("instructions changed")
    before = {tool["name"]: tool for tool in old.get("tools", [])}
    after = {tool["name"]: tool for tool in new.get("tools", [])}
    changes.extend(f"new tool: {name}" for name in sorted(after.keys() - before.keys()))
    changes.extend(f"removed tool: {name}" for name in sorted(before.keys() - after.keys()))
    changes.extend(f"changed tool: {name}" for name in sorted(before.keys() & after.keys()) if before[name] != after[name])
    return changes


def read_contract(config: dict) -> tuple[str, dict, list[dict]]:
    """Connect the way a client would and return the name, `initialize` and the tools."""
    with tempfile.TemporaryDirectory(prefix="mcp-eval-contract-") as scratch:
        env = {**server_env(config, scratch), **config["agent"]["env"]}
        name, entry = load_server(from_base(config, config["server"]["mcp_config"]), config["server"]["name"], {**os.environ, **env})
        entry["env"] = {**env, **entry.get("env", {})}
        client = connect(entry)
        try:
            init = handshake(client)
            return name, init, list_tools(client)
        finally:
            client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True)
    parser.add_argument("--update-snapshot", action="store_true", help="save the current contract as the accepted one")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        name, init, tools = read_contract(config)
    except (ConfigError, McpError) as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 2

    snapshot = contract_snapshot(init, tools)
    limits = effective_limits(config)
    findings = inspect_contract(init, tools, limits)
    snapshot_path = from_base(config, config["contract_snapshot"])
    if args.update_snapshot:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"snapshot saved to {snapshot_path}")
    elif snapshot_path.exists():
        changes = diff_snapshot(json.loads(snapshot_path.read_text(encoding="utf-8")), snapshot)
        findings.extend(Finding("ERROR", "contract-changed", f"{change}; if intended, rerun with --update-snapshot and remember clients keep the old list") for change in changes)
    else:
        findings.append(Finding("WARN", "snapshot-missing", "no contract snapshot; run with --update-snapshot to start watching for changes"))

    print(f"server {name}: {len(tools)} tools, instructions at {len(init.get('instructions') or '')} of {limits['instructions_chars']} characters, surface of {surface_chars(tools)} characters, contract {fingerprint(snapshot)}")
    for finding in findings:
        print(f"  {finding.severity:5} {finding.rule}: {finding.message}")
    errors = sum(1 for finding in findings if finding.severity == "ERROR")
    print("contract failed" if errors else "contract passed")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
