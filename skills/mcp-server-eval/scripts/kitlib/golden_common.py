#!/usr/bin/env python3
"""Pieces shared by the golden scripts.

Configuration, case loading, guards and `stream-json` transcript parsing. Standard
library only, so the kit fits any stack.
"""
from __future__ import annotations

import copy
import fnmatch
import json
import os
import re
import statistics
import subprocess
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

SCRIPTS_DIR = Path(__file__).resolve().parent.parent

DEFAULTS: dict = {
    "name": "mcp-eval",
    "mode": "spike",
    "focus": "balanced",
    "results_dir": ".mcp-eval/runs",
    "cases_dir": "golden/cases",
    "contract_snapshot": "golden/contract.snapshot.json",
    "server": {"mcp_config": "mcp.json", "name": None},
    "agent": {
        "claude_bin": "claude",
        "models": ["haiku"],
        "repetitions": 1,
        "builtin_tools": ["ToolSearch"],
        "system_append": "",
        "setting_sources": "project",
        "env": {},
        "extra_args": [],
        "timeout_seconds": 300,
    },
    "limits": {
        "instructions_chars": 4096,
        "upfront_description_chars": 4096,
        "tool_description_chars": 16384,
        "surface_chars": None,
    },
    "budget": {"per_run_usd": None, "total_usd": None},
    "guard": {
        "live_env": "MCP_EVAL_LIVE",
        "allowed_hosts": ["127.0.0.1", "localhost", "*.localhost", "::1"],
        "allow_ci": False,
    },
    "hooks": {"before_run": None, "before_case": None, "after_case": None, "after_run": None},
    "grader": {"model": "sonnet", "votes": 3, "budget_usd": 0.5, "total_usd": 5, "prompt_file": "agents/mcp-golden-grader.md"},
    "analysis": {
        "model": "sonnet",
        "budget_usd": 1,
        "prompt_file": "agents/mcp-behavior-analyst.md",
        "min_repeat": 3,
        "min_fan_out": 4,
        "heavy_response_chars": 8000,
        "slow_tool_ms": 2000,
    },
    "stop_criteria": {
        "min_clean_rate": 0.9,
        "max_silent_failures": 0,
        "max_cost_per_case_usd": None,
        "max_median_calls": None,
        "max_median_tokens": None,
        "max_median_seconds": None,
    },
}

FOCUSES = ("balanced", "quality", "cost", "speed")

# Required fields of each deterministic check.
CHECK_FIELDS: dict[str, tuple[str, ...]] = {
    "tool_called": ("tool",),
    "tool_not_called": ("tool",),
    "tool_order": ("first", "then"),
    "args_match": ("tool", "regex"),
    "final_matches": ("regex",),
    "final_not_matches": ("regex",),
    "max_calls": ("value",),
    "max_errors": ("value",),
    "max_cost_usd": ("value",),
    "command": ("run",),
}

# Claude Code variable that replaces the server text limits with a single number.
LIMIT_ENV = "CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH"

CASE_KINDS = {"create", "edit", "read", "vague", "missing-data", "recovery", "negative", "other"}
SUSPICIOUS_CHARS_PER_OUTPUT_TOKEN = 8


class ConfigError(RuntimeError):
    """A configuration or case problem that stops the run from starting."""


def _merge(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str | Path) -> dict:
    """Read the configuration; relative paths resolve from its folder."""
    config_path = Path(path).resolve()
    if not config_path.exists():
        raise ConfigError(f"configuration not found: {config_path}")
    config = _merge(DEFAULTS, json.loads(config_path.read_text(encoding="utf-8")))
    config["_base"] = str(config_path.parent)
    config["_path"] = str(config_path)
    if config["mode"] not in ("spike", "fixture"):
        raise ConfigError("mode must be spike or fixture")
    if config["focus"] not in FOCUSES:
        raise ConfigError(f"focus must be one of: {', '.join(FOCUSES)}")
    return config


def from_base(config: dict, value: str) -> Path:
    return (Path(config["_base"]) / value).resolve()


def server_env(config: dict, artifact_dir: str | Path) -> dict[str, str]:
    """Variables the server configuration and the hooks can reference."""
    return {
        "EVAL_KIT_DIR": config["_base"],
        "EVAL_SCRIPTS_DIR": str(SCRIPTS_DIR),
        "EVAL_ARTIFACT_DIR": str(artifact_dir),
    }


def effective_limits(config: dict, environ: dict | None = None) -> dict:
    """Return the limits in force for this configuration.

    The client uses one number for both limits, so raising it also replaces the
    larger limit, the one for descriptions loaded through tool search.
    """
    base = config["limits"]
    limits = {**base, "default_instructions_chars": base["instructions_chars"], "default_description_chars": base["tool_description_chars"], "override": None}
    env = {**(os.environ if environ is None else environ), **config["agent"]["env"]}
    raw = str(env.get(LIMIT_ENV, "")).strip()
    if raw.isdigit() and int(raw) > 0:
        value = int(raw)
        limits.update(instructions_chars=value, upfront_description_chars=value, tool_description_chars=value, override=value)
    return limits


def validate_case(case: dict) -> list[str]:
    """List what stops a case from working as an answer key. Empty means valid."""
    problems = [f"missing {field}" for field in ("id", "prompt") if not case.get(field)]
    if case.get("kind") and case["kind"] not in CASE_KINDS:
        problems.append(f"unknown kind: {case['kind']} (use {', '.join(sorted(CASE_KINDS))})")
    if case.get("tier", "public") not in ("public", "holdout"):
        problems.append("tier must be public or holdout")
    if not case.get("checks") and not case.get("rubric"):
        problems.append("no checks and no rubric: nothing decides whether the case passed")
    ideal = case.get("ideal_calls")
    if ideal is not None and not (isinstance(ideal, list) and len(ideal) == 2 and ideal[0] <= ideal[1]):
        problems.append("ideal_calls must be [min, max]")
    for check in case.get("checks", []):
        kind = check.get("type")
        if kind not in CHECK_FIELDS:
            problems.append(f"unknown check: {kind}")
            continue
        problems.extend(f"check {kind} missing {field}" for field in CHECK_FIELDS[kind] if field not in check)
        if "regex" in check:
            try:
                re.compile(check["regex"])
            except re.error as error:
                problems.append(f"invalid regex in {kind}: {error}")
    return problems


def load_cases(config: dict, include_holdout: bool = False, only: list[str] | None = None) -> tuple[list[dict], int]:
    """Return the cases for this run and how many were left out as holdout."""
    cases_dir = from_base(config, config["cases_dir"])
    files = sorted(cases_dir.glob("*.json"))
    if not files:
        raise ConfigError(f"no cases in {cases_dir}")
    cases, problems, seen, held_out = [], [], set(), 0
    for file in files:
        case = json.loads(file.read_text(encoding="utf-8"))
        problems.extend(f"{file.name}: {problem}" for problem in validate_case(case))
        if case.get("id") in seen:
            problems.append(f"{file.name}: repeated id {case['id']}")
        seen.add(case.get("id"))
        if only and case.get("id") not in only:
            continue
        if case.get("tier") == "holdout" and not include_holdout:
            held_out += 1
            continue
        cases.append(case)
    if problems:
        raise ConfigError("invalid cases:\n  " + "\n  ".join(problems))
    if only and (missing := set(only) - seen):
        raise ConfigError(f"cases not found: {', '.join(sorted(missing))}")
    return cases, held_out


def guard_problems(config: dict, environ: dict | None = None) -> list[str]:
    """Reasons to refuse a live run. An empty list releases the spend."""
    env = os.environ if environ is None else environ
    guard, budget = config["guard"], config["budget"]
    problems = []
    if env.get(guard["live_env"]) != "1":
        problems.append(f"{guard['live_env']}=1 is not set (the --live flag states intent, the variable states the place)")
    if env.get("CI") and not guard["allow_ci"]:
        problems.append("CI environment: guard.allow_ci is off")
    if not budget.get("per_run_usd") or not budget.get("total_usd"):
        problems.append("set budget.per_run_usd and budget.total_usd before spending")
    problems.extend(host_problems(config))
    return problems


def host_problems(config: dict) -> list[str]:
    """Refuse URLs outside the list: a run aimed at production by mistake costs dearly."""
    mcp_config = from_base(config, config["server"]["mcp_config"])
    if not mcp_config.exists():
        return [f"server configuration not found: {mcp_config}"]
    servers = json.loads(mcp_config.read_text(encoding="utf-8")).get("mcpServers", {})
    problems = []
    for name, entry in servers.items():
        if not entry.get("url"):
            continue
        host = urlsplit(entry["url"]).hostname or ""
        if not any(fnmatch.fnmatch(host, pattern) for pattern in config["guard"]["allowed_hosts"]):
            problems.append(f"server {name}: host {host} is outside guard.allowed_hosts")
    return problems


def parse_transcript(path: Path, server: str) -> dict:
    """Read one run's `stream-json`: calls, final text and the `result` event."""
    prefix = f"mcp__{server}__"
    init: dict = {}
    result: dict = {}
    pending: dict[str, dict] = {}
    calls: list[dict] = []
    other_tools: Counter = Counter()
    last_text = ""
    # What the model said right before a call is the cheapest clue to why it made it.
    last_said = ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind, moment = event.get("type"), event.get("_t")
        if kind == "system" and event.get("subtype") == "init":
            init = event
        elif kind == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "text" and not event.get("parent_tool_use_id"):
                    last_text = block.get("text", "")
                    last_said = last_text
                elif block.get("type") == "thinking":
                    last_said = block.get("thinking", "") or last_said
                elif block.get("type") == "tool_use":
                    name = block.get("name", "")
                    if name.startswith(prefix):
                        pending[block["id"]] = {
                            "tool": name[len(prefix):],
                            "args": block.get("input", {}),
                            "in_chars": len(json.dumps(block.get("input", {}), ensure_ascii=False)),
                            "said_before": last_said[-300:],
                            "_started": moment,
                        }
                        last_said = ""
                    else:
                        other_tools[name] += 1
        elif kind == "user":
            content = event.get("message", {}).get("content", [])
            for block in content if isinstance(content, list) else []:
                call = pending.pop(block.get("tool_use_id"), None) if block.get("type") == "tool_result" else None
                if call is None:
                    continue
                body = block.get("content")
                parts = body if isinstance(body, list) else [{"type": "text", "text": str(body or "")}]
                started = call.pop("_started")
                calls.append({
                    **call,
                    "error": bool(block.get("is_error")),
                    "out_chars": sum(len(part.get("text", "")) for part in parts if part.get("type") == "text"),
                    "images": sum(1 for part in parts if part.get("type") == "image"),
                    "ms": round((moment - started) * 1000) if moment is not None and started is not None else None,
                    "preview": next((part.get("text", "")[:200] for part in parts if part.get("type") == "text"), ""),
                })
        elif kind == "result":
            result = event
    return {"init": init, "result": result, "calls": calls, "other_tools": dict(other_tools), "final_text": result.get("result") or last_text}


def build_metrics(parsed: dict, server: str) -> dict:
    """Consolidate the metrics. Tokens and cost come ONLY from the `result` event.

    Summing `usage` across transcript messages undercounts output: the same
    message appears in parts, with partial counts.
    """
    calls, result = parsed["calls"], parsed["result"]
    usage = result.get("usage") or {}
    tokens = {
        "input": usage.get("input_tokens", 0),
        "output": usage.get("output_tokens", 0),
        "cache_read": usage.get("cache_read_input_tokens", 0),
        "cache_write": usage.get("cache_creation_input_tokens", 0),
        "thinking": (usage.get("output_tokens_details") or {}).get("thinking_tokens", 0),
    }
    tokens["total"] = tokens["input"] + tokens["output"] + tokens["cache_read"] + tokens["cache_write"]
    per_tool: dict[str, dict] = {}
    for call in calls:
        entry = per_tool.setdefault(call["tool"], {"calls": 0, "errors": 0, "ms": [], "out_chars": []})
        entry["calls"] += 1
        entry["errors"] += call["error"]
        entry["out_chars"].append(call["out_chars"])
        if call["ms"] is not None:
            entry["ms"].append(call["ms"])
    errors = [index for index, call in enumerate(calls) if call["error"]]
    recovered = sum(1 for index in errors if index + 1 < len(calls) and not calls[index + 1]["error"])
    in_chars = sum(call["in_chars"] for call in calls)
    connected = {entry.get("name"): entry.get("status") for entry in parsed["init"].get("mcp_servers", [])}
    alerts = []
    if not result:
        alerts.append("no result event: the run did not finish")
    if connected.get(server) != "connected":
        alerts.append(f"server {server} did not connect: {connected.get(server)}")
    if result and not calls:
        alerts.append("no calls to the server")
    if result.get("permission_denials"):
        alerts.append(f"{len(result['permission_denials'])} permission denials")
    if tokens["output"] and in_chars / tokens["output"] > SUSPICIOUS_CHARS_PER_OUTPUT_TOKEN:
        alerts.append("output tokens are implausibly low for the size of the arguments")
    return {
        "ok": result.get("subtype") == "success" and not result.get("is_error"),
        "answered": bool((parsed.get("final_text") or "").strip()),
        "terminal_reason": result.get("terminal_reason") or result.get("subtype"),
        "connected": connected.get(server) == "connected",
        "turns": result.get("num_turns"),
        "duration_s": round((result.get("duration_ms") or 0) / 1000, 1),
        "cost_usd": round(result.get("total_cost_usd") or 0, 5),
        "tokens": tokens,
        "calls": len(calls),
        "errors": len(errors),
        "recovered_errors": recovered,
        "sequence": " ".join(call["tool"] + ("!" if call["error"] else "") for call in calls),
        "in_chars": in_chars,
        "out_chars": sum(call["out_chars"] for call in calls),
        "images": sum(call["images"] for call in calls),
        "per_tool": {
            name: {
                "calls": entry["calls"],
                "errors": entry["errors"],
                "ms_median": round(statistics.median(entry["ms"])) if entry["ms"] else None,
                "out_chars_median": round(statistics.median(entry["out_chars"])),
            }
            for name, entry in per_tool.items()
        },
        "other_tools": parsed["other_tools"],
        "alerts": alerts,
    }


def run_check(check: dict, parsed: dict, metrics: dict, env: dict, cwd: str) -> tuple[bool, str]:
    """Evaluate one deterministic check and return the verdict with its evidence."""
    kind, calls, final = check["type"], parsed["calls"], parsed["final_text"] or ""
    names = [call["tool"] for call in calls]
    if kind == "tool_called":
        count = names.count(check["tool"])
        low, high = check.get("min", 1), check.get("max")
        return count >= low and (high is None or count <= high), f"{check['tool']}: {count} call(s)"
    if kind == "tool_not_called":
        return check["tool"] not in names, f"{check['tool']}: {names.count(check['tool'])} call(s)"
    if kind == "tool_order":
        first = names.index(check["first"]) if check["first"] in names else None
        then = len(names) - 1 - names[::-1].index(check["then"]) if check["then"] in names else None
        return first is not None and then is not None and first < then, f"sequence: {' '.join(names)}"
    if kind == "args_match":
        matched = [call for call in calls if call["tool"] == check["tool"] and re.search(check["regex"], json.dumps(call["args"], ensure_ascii=False))]
        return bool(matched), f"{len(matched)} call(s) to {check['tool']} matched"
    if kind == "final_matches":
        return bool(re.search(check["regex"], final, re.I)), f"regex {check['regex']}"
    if kind == "final_not_matches":
        return not re.search(check["regex"], final, re.I), f"forbidden regex {check['regex']}"
    if kind == "max_calls":
        return metrics["calls"] <= check["value"], f"{metrics['calls']} call(s)"
    if kind == "max_errors":
        return metrics["errors"] <= check["value"], f"{metrics['errors']} error(s)"
    if kind == "max_cost_usd":
        return metrics["cost_usd"] <= check["value"], f"US$ {metrics['cost_usd']}"
    if kind == "command":
        done = subprocess.run(check["run"], shell=True, cwd=cwd, env=env, capture_output=True, text=True, timeout=check.get("timeout", 120))
        return done.returncode == 0, (done.stdout + done.stderr).strip()[-300:] or f"exit code {done.returncode}"
    return False, f"unknown check: {kind}"


def git_ignore_state(path: Path) -> str:
    """Return `no-git`, `ignored` or `not-ignored` for a folder."""
    try:
        done = subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=path, capture_output=True)
    except OSError:
        return "no-git"
    return {0: "ignored", 1: "not-ignored"}.get(done.returncode, "no-git")


def storage_notice(results_dir: Path) -> str:
    """Tell the person what stayed on disk, so nothing is kept or committed by accident."""
    size = sum(path.stat().st_size for path in results_dir.rglob("*") if path.is_file()) / 1_000_000
    place = f"Runs are saved in {results_dir} ({size:.1f} MB)"
    state = git_ignore_state(results_dir)
    if state == "not-ignored":
        return f"{place}, and Git does NOT ignore them; transcripts can hold data. Add the folder to .gitignore, or delete it."
    return f"{place}{', ignored by Git' if state == 'ignored' else ''}. Delete the folder when you no longer need them."


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
