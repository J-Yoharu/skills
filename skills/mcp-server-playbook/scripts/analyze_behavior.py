#!/usr/bin/env python3
"""Read how the agent behaved and find what the server could do better.

Free detectors look for patterns in the calls: walking pages, rephrasing a search,
one call per item, error loops. They run with every report. With `--live`, one model
call reads the same behavior and proposes concrete changes, such as a new filter.
Everything it proposes is a hypothesis: only a new round proves it.

Usage:
  analyze_behavior.py --config eval.config.json --run <id>
  MCP_EVAL_LIVE=1 analyze_behavior.py --config eval.config.json --run <id> --live
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

# Python's isolated mode (-I) leaves the script's own folder off the path, and the kit's modules live there.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kitlib.golden_common import ConfigError, effective_limits, from_base, guard_problems, load_cases, load_config, read_jsonl

PAGINATION_KEYS = {"offset", "page", "cursor", "after", "before", "skip", "start", "next", "next_offset", "page_token", "pagetoken"}
ID_KEY = re.compile(r"(^|_)(id|ids|key|ref|slug|uuid)$", re.I)
# A search term is short; a longer value is content being written, not a rephrased query.
SEARCH_TERM_CHARS = 80
DIMENSION_ORDER = {"balanced": ("quality", "cost", "speed"), "quality": ("quality", "cost", "speed"), "cost": ("cost", "quality", "speed"), "speed": ("speed", "cost", "quality")}

SUGGESTION_SCHEMA = {
    "type": "object",
    "required": ["suggestions"],
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["kind", "tool", "change", "why", "evidence", "expected_effect", "dimension", "confidence"],
                "properties": {
                    "kind": {"type": "string", "enum": ["add_parameter", "new_tool", "batch_operation", "change_description", "change_error", "trim_response", "other"]},
                    "tool": {"type": "string"},
                    "change": {"type": "string"},
                    "why": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "expected_effect": {"type": "string"},
                    "dimension": {"type": "string", "enum": ["quality", "cost", "speed"]},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        }
    },
}


def finding(rule: str, dimension: str, tool: str, evidence: str, hint: str, wasted_calls: int = 0, wasted_chars: int = 0) -> dict:
    return {"rule": rule, "dimension": dimension, "tool": tool, "evidence": evidence, "hint": hint, "wasted_calls": wasted_calls, "wasted_chars": wasted_chars}


def varying_keys(calls: list[dict]) -> set[str]:
    """Arguments whose value changes between consecutive calls to a tool."""
    keys: set[str] = set()
    for left, right in zip(calls, calls[1:]):
        for key in set(left["args"]) | set(right["args"]):
            if left["args"].get(key) != right["args"].get(key):
                keys.add(key)
    return keys


def is_search_term(value: object) -> bool:
    return value is None or (isinstance(value, str) and len(value) <= SEARCH_TERM_CHARS)


def inspect_tool_calls(tool: str, calls: list[dict], limits: dict) -> list[dict]:
    """Patterns in the calls to one tool within one run."""
    found: list[dict] = []
    count, spare_chars = len(calls), sum(call["out_chars"] for call in calls[1:])
    keys = varying_keys(calls)
    if keys and keys <= PAGINATION_KEYS and count >= limits["min_repeat"]:
        found.append(finding("pagination-walk", "cost", tool, f"{count} pages walked through `{', '.join(sorted(keys))}`", "The model walks pages looking for something: offer a filter for it, a count, or a larger page.", count - 1, spare_chars))
    elif keys and all(ID_KEY.search(key) for key in keys) and count >= limits["min_fan_out"]:
        found.append(finding("fan-out", "cost", tool, f"{count} calls, one per `{', '.join(sorted(keys))}`", "One call per item: accept a list of ids, or return that data in the list.", count - 1, spare_chars))
    elif keys and count >= limits["min_repeat"] and all(is_search_term(call["args"].get(key)) for call in calls for key in keys):
        values = [str(next((call["args"][key] for key in sorted(keys) if key in call["args"]), ""))[:40] for call in calls]
        found.append(finding("search-churn", "quality", tool, f"{count} attempts varying `{', '.join(sorted(keys))}`: {' | '.join(values[:4])}", "The model keeps rephrasing: the search is too literal, or a structured filter is missing.", count - 1, spare_chars))
    elif keys and count >= limits["min_fan_out"]:
        found.append(finding("many-writes", "cost", tool, f"{count} calls with different content", "Check whether one larger call or a batch would do the same work.", count - 1, spare_chars))

    errors = sum(1 for left, right in zip(calls, calls[1:]) if left["error"] and right["error"])
    if errors:
        sample = next((call["preview"] for call in calls if call["error"]), "")[:120]
        found.append(finding("error-loop", "quality", tool, f"errors in a row: {sample}", "The error message does not lead out: say what to do next.", errors + 1))
    return found


def inspect_run(record: dict, calls: list[dict], limits: dict) -> list[dict]:
    by_tool: dict[str, list[dict]] = defaultdict(list)
    for call in calls:
        by_tool[call["tool"]].append(call)
    found = [item for tool, group in by_tool.items() for item in inspect_tool_calls(tool, group, limits)]
    # Only back-to-back calls count: the same `validate` after an edit is legitimate.
    for left, right in zip(calls, calls[1:]):
        if (left["tool"], left["args"]) == (right["tool"], right["args"]) and not left["error"]:
            found.append(finding("repeated-call", "cost", left["tool"], "the same call twice in a row", "The answer did not stick: make the response say more, or confirm the state, so the model does not ask again.", 1, right["out_chars"]))
    ideal = record.get("ideal_calls")
    if ideal and len(calls) > ideal[1]:
        found.append(finding("over-range", "cost", "(run)", f"{len(calls)} calls, ideal up to {ideal[1]}", "Read the sequence: the path is longer than the best one you planned.", len(calls) - ideal[1]))
    if not calls:
        found.append(finding("no-calls", "quality", "(run)", "the server was never called", "Name and description do not match the request, or the model thought it needed confirmation."))
    for item in found:
        item["case"] = record["case"]
    return found


def merge(found: list[dict]) -> list[dict]:
    """Group the same pattern across runs, so one problem shows up once."""
    groups: dict[tuple, dict] = {}
    for item in found:
        group = groups.setdefault((item["rule"], item["tool"]), {**item, "runs": 0, "wasted_calls": 0, "wasted_chars": 0, "cases": []})
        group["runs"] += 1
        group["wasted_calls"] += item["wasted_calls"]
        group["wasted_chars"] += item["wasted_chars"]
        if item.get("case") and item["case"] not in group["cases"]:
            group["cases"].append(item["case"])
    return [{key: value for key, value in group.items() if key != "case"} for group in groups.values()]


def inspect_round(records: list[dict], calls_by_attempt: dict[str, list[dict]], contract: dict | None, limits: dict) -> list[dict]:
    """Patterns that only show up across the whole round."""
    used_tools: dict[str, list[dict]] = defaultdict(list)
    for calls in calls_by_attempt.values():
        for call in calls:
            used_tools[call["tool"]].append(call)
    found: list[dict] = []
    for tool, calls in used_tools.items():
        slow = [call["ms"] for call in calls if call.get("ms") is not None]
        if slow and statistics.median(slow) > limits["slow_tool_ms"]:
            found.append(finding("slow-tool", "speed", tool, f"median of {round(statistics.median(slow))} ms", "Look at what the tool does on each call: cache, index or a lighter response."))
        sizes = [call["out_chars"] for call in calls]
        if statistics.median(sizes) > limits["heavy_response_chars"]:
            found.append(finding("heavy-response", "cost", tool, f"median response of {round(statistics.median(sizes))} characters", "Every later call reads this again: trim fields, or offer `fields` or `limit`.", 0, sum(sizes)))
    for tool in (contract or {}).get("tools", []):
        name = tool.get("name", "")
        if name not in used_tools:
            found.append(finding("unused-tool", "cost", name, "never called in this round", "Either no case needs it, or its name and description hide it. Unused tools still weigh on the context."))
            continue
        passed = {key for call in used_tools[name] for key in call["args"]}
        unused = sorted(set((tool.get("inputSchema") or {}).get("properties", {})) - passed)
        if unused:
            found.append(finding("unused-parameter", "quality", name, f"never passed: {', '.join(unused)}", "Check whether the description says when to use it. If the model walked pages on this tool, the filter exists and it does not know."))
    return found


def rank(items: list[dict], focus: str) -> list[dict]:
    """The chosen focus comes first; within it, what wastes the most."""
    order = DIMENSION_ORDER[focus]
    return sorted(items, key=lambda item: (order.index(item["dimension"]), -item["wasted_calls"], -item["wasted_chars"]))


def read_calls(run_dir: Path, records: list[dict]) -> dict[str, list[dict]]:
    calls = {}
    for record in records:
        path = run_dir / record["attempt_dir"] / "calls.json"
        calls[record["attempt_dir"]] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    return calls


def read_contract_file(config: dict, run_dir: Path) -> dict | None:
    for path in (run_dir / "contract.json", from_base(config, config["contract_snapshot"])):
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def detect(config: dict, run_dir: Path, records: list[dict]) -> list[dict]:
    limits = config["analysis"]
    calls = read_calls(run_dir, records)
    found = [item for record in records for item in inspect_run(record, calls[record["attempt_dir"]], limits)]
    return rank(merge(found) + [{**item, "runs": 1, "cases": []} for item in inspect_round(records, calls, read_contract_file(config, run_dir), limits)], config["focus"])


def load_behavior(config: dict, run_dir: Path, records: list[dict]) -> dict:
    """Detectors are always recomputed; saved model suggestions come along if they exist."""
    saved = run_dir / "behavior.json"
    extra = json.loads(saved.read_text(encoding="utf-8")) if saved.exists() else {}
    return {**extra, "findings": detect(config, run_dir, records)}


def behavior_lines(behavior: dict) -> list[str]:
    lines = ["## Opportunities", ""]
    findings = behavior.get("findings", [])
    if not findings and not behavior.get("suggestions"):
        return [*lines, "No pattern found.", ""]
    if findings:
        lines += ["| Dimension | Pattern | Tool | Runs | Wasted calls | Evidence | What to look at |", "|---|---|---|---|---|---|---|"]
        for item in findings:
            lines.append(f"| {item['dimension']} | {item['rule']} | {item['tool']} | {item['runs']} | {item['wasted_calls']} | {item['evidence']} | {item['hint']} |")
        lines.append("")
    for item in behavior.get("suggestions", []):
        lines.append(f"- **{item['kind']} on `{item['tool']}`** ({item['dimension']}, {item['confidence']} confidence): {item['change']} {item['why']} Expected: {item['expected_effect']} Evidence: {', '.join(item['evidence'])}.")
    if behavior.get("suggestions"):
        lines += ["", "Suggestions are hypotheses: apply one, run again, and compare with `--baseline`.", ""]
    return lines


def build_digest(config: dict, run_dir: Path, records: list[dict], findings: list[dict]) -> str:
    """Compact view of the round, for one model call."""
    prompts = {case["id"]: case for case in load_cases(config, include_holdout=True)[0]}
    calls = read_calls(run_dir, records)
    contract = read_contract_file(config, run_dir) or {}
    instructions = contract.get("instructions") or ""
    limit = effective_limits(config)["instructions_chars"]
    lines = [f"# Round, focus: {config['focus']}", "", "## Server instructions", ""]
    if len(instructions) > limit:
        lines += [f"The client cut these at {limit} of {len(instructions)} characters. The agent never saw the rest, so a rule that lives only past the cut is unknown to it:", "", instructions[limit:limit + 1500], ""]
    else:
        lines += [f"{len(instructions)} characters, delivered whole.", ""]
    lines += ["## Tools the server offers", ""]
    for tool in contract.get("tools", []):
        lines.append(f"- {tool.get('name')}({', '.join((tool.get('inputSchema') or {}).get('properties', {}))}): {(tool.get('description') or '')[:400]}")
    lines += ["", "## Patterns already detected", ""] + [f"- {item['rule']} on {item['tool']}: {item['evidence']}" for item in findings]
    for record in records:
        metrics = record["metrics"]
        case = prompts.get(record["case"], {})
        lines += ["", f"## Run {record['case']} ({record['model']} r{record['rep']})", "", f"Request: {case.get('prompt', '')}", f"Checks passed: {record['checks_passed']}. Calls: {metrics.get('calls')}. Tokens: {(metrics.get('tokens') or {}).get('total')}. Time: {metrics.get('duration_s')} s.", ""]
        for call in calls[record["attempt_dir"]][:40]:
            said = f' Said before: "{call["said_before"]}"' if call.get("said_before") else ""
            lines.append(f"- {call['tool']}({json.dumps(call['args'], ensure_ascii=False)[:200]}){' ERROR' if call['error'] else ''}: {call['out_chars']} chars. {call['preview'][:160]!r}{said}")
    return "\n".join(lines)[:120000] + "\n"


def propose(config: dict, run_dir: Path, records: list[dict], findings: list[dict]) -> tuple[list[dict], float]:
    """One model call that reads the behavior and proposes changes to the server."""
    analysis = config["analysis"]
    prompt_text = from_base(config, analysis["prompt_file"]).read_text(encoding="utf-8")
    system = re.sub(r"\A---\n.*?\n---\n", "", prompt_text, flags=re.S).strip()
    command = [
        config["agent"]["claude_bin"], "-p", "Analyze digest.md in this folder.",
        "--model", analysis["model"],
        "--system-prompt", system,
        "--strict-mcp-config",
        "--no-session-persistence",
        "--max-budget-usd", str(analysis["budget_usd"]),
        "--tools", "Read",
        "--allowedTools", "Read",
        "--json-schema", json.dumps(SUGGESTION_SCHEMA),
        "--output-format", "json",
    ]
    if config["agent"]["setting_sources"] is not None:
        command += ["--setting-sources", config["agent"]["setting_sources"]]
    with tempfile.TemporaryDirectory(prefix="mcp-eval-analysis-") as scratch:
        (Path(scratch) / "digest.md").write_text(build_digest(config, run_dir, records, findings), encoding="utf-8")
        done = subprocess.run(command, cwd=scratch, env=os.environ, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=config["agent"]["timeout_seconds"])
    try:
        result = json.loads(done.stdout)
        return result["structured_output"]["suggestions"], result.get("total_cost_usd") or 0
    except (ValueError, KeyError, TypeError) as error:
        raise ConfigError(f"the analyst returned no suggestions: {(done.stdout + done.stderr)[-200:]}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--live", action="store_true", help="also ask a model to propose changes; this spends")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        run_dir = from_base(config, config["results_dir"]) / args.run
        records = read_jsonl(run_dir / "results.jsonl")
        if not records:
            raise ConfigError(f"run has no results: {run_dir}")
        findings = detect(config, run_dir, records)
        for item in findings:
            print(f"{item['dimension']:7} {item['rule']:17} {item['tool']:20} runs {item['runs']}, wasted calls {item['wasted_calls']}: {item['evidence'][:110]}")
        if not findings:
            print("no pattern found")
        if not args.live:
            return 0
        if problems := guard_problems(config):
            print("Analysis refused by the guard:", file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            return 2
        suggestions, cost = propose(config, run_dir, records, findings)
        (run_dir / "behavior.json").write_text(json.dumps({"suggestions": suggestions, "analysis_cost_usd": round(cost, 4)}, ensure_ascii=False, indent=2), encoding="utf-8")
        for item in suggestions:
            print(f"\n{item['kind']} on {item['tool']} ({item['dimension']}, {item['confidence']}): {item['change']}\n  why: {item['why']}\n  expected: {item['expected_effect']}")
        print(f"\nanalysis: US$ {cost:.4f}")
        return 0
    except (ConfigError, OSError, subprocess.TimeoutExpired) as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
