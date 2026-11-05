#!/usr/bin/env python3
"""Blind grading: separate what was done from who did it.

`prepare` builds one packet per case with shuffled labels A, B, C… and no model, cost
or time; the map stays outside the packet. `judge` hands each packet to independent
`claude -p` graders with no access to the server, and the majority decides. Each
grader works on a throwaway copy, so it cannot read the map or another grader's vote,
and reads the results in a different order, to dilute position bias.

To grade by hand, fill in `grade.json` with the same format.

Usage:
  grade_golden.py prepare --config eval.config.json --run <id>
  MCP_EVAL_LIVE=1 grade_golden.py judge --config eval.config.json --run <id> --live
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import statistics
import string
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

# Python's isolated mode (-I) leaves the script's own folder off the path, and the kit's modules live there.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kitlib.golden_common import ConfigError, from_base, guard_problems, load_cases, load_config, read_jsonl

VERDICT_ORDER = ["fail", "partial", "clean"]

GRADE_SCHEMA = {
    "type": "object",
    "required": ["labels"],
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "verdict", "fidelity", "silent_failure", "items", "summary"],
                "properties": {
                    "label": {"type": "string"},
                    "verdict": {"type": "string", "enum": VERDICT_ORDER},
                    "fidelity": {"type": "number"},
                    "silent_failure": {"type": "boolean"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["item", "status", "evidence"],
                            "properties": {
                                "item": {"type": "string"},
                                "status": {"type": "string", "enum": ["ok", "partial", "fail"]},
                                "evidence": {"type": "string"},
                            },
                        },
                    },
                    "summary": {"type": "string"},
                },
            },
        }
    },
}


def run_paths(config: dict, run_id: str) -> Path:
    run_dir = from_base(config, config["results_dir"]) / run_id
    if not (run_dir / "results.jsonl").exists():
        raise ConfigError(f"run not found: {run_dir}")
    return run_dir


def scrub(text: str, models: list[str]) -> str:
    """Remove model names from the text: a signature in the answer would break blindness."""
    for model in models:
        text = re.sub(re.escape(model), "[model]", text, flags=re.I)
    return text


def prepare(config: dict, run_id: str) -> None:
    run_dir = run_paths(config, run_id)
    records = read_jsonl(run_dir / "results.jsonl")
    cases = {case["id"]: case for case in load_cases(config, include_holdout=True)[0]}
    models = sorted({record["model"] for record in records})
    rng = random.Random(run_id)
    blind_map: dict[str, dict[str, str]] = {}
    grades_dir = run_dir / "grades"
    for case_id in sorted({record["case"] for record in records}):
        attempts = [record for record in records if record["case"] == case_id]
        rng.shuffle(attempts)
        case = cases[case_id]
        packet_dir = grades_dir / case_id
        packet_dir.mkdir(parents=True, exist_ok=True)
        lines = [f"# Case {case_id}", "", "## The person's request", "", case["prompt"], "", "## Items to grade", ""]
        lines += [f"- {item}" for item in case.get("rubric", [])] or ["- Was the request fully met?"]
        blind_map[case_id] = {}
        for label, record in zip(string.ascii_uppercase, attempts):
            blind_map[case_id][label] = record["attempt_dir"]
            source = run_dir / record["attempt_dir"]
            target = packet_dir / label
            target.mkdir(exist_ok=True)
            if (source / "artifacts").exists():
                shutil.copytree(source / "artifacts", target / "artifacts", dirs_exist_ok=True)
            final = (source / "final.md").read_text(encoding="utf-8") if (source / "final.md").exists() else ""
            calls = json.loads((source / "calls.json").read_text(encoding="utf-8")) if (source / "calls.json").exists() else []
            lines += ["", f"## Result {label}", "", "### Final answer to the person", "", scrub(final, models) or "(empty)", "", "### Tool calls", ""]
            for call in calls:
                lines.append(f"- {call['tool']}{' (error)' if call['error'] else ''}: {scrub(json.dumps(call['args'], ensure_ascii=False)[:600], models)}")
            files = sorted(str(path.relative_to(packet_dir)) for path in target.rglob("*") if path.is_file())
            lines += ["", "### Generated files", ""] + ([f"- {name}" for name in files] or ["- none"])
        (packet_dir / "packet.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (run_dir / "blind-map.json").write_text(json.dumps(blind_map, indent=2), encoding="utf-8")
    print(f"{len(blind_map)} packets in {grades_dir}; the map stays in {run_dir / 'blind-map.json'}, outside the packets")


def grader_prompt(config: dict) -> str:
    text = from_base(config, config["grader"]["prompt_file"]).read_text(encoding="utf-8")
    return re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S).strip()


def tally(votes: list[dict]) -> dict:
    """Merge independent votes on one label into a single grade."""
    verdicts = [vote["verdict"] for vote in votes]
    winner, count = Counter(verdicts).most_common(1)[0]
    has_majority = count * 2 > len(verdicts)
    # With no majority, take the middle verdict, or the lower of two, and send it to a person.
    verdict = winner if has_majority else sorted(verdicts, key=VERDICT_ORDER.index)[(len(verdicts) - 1) // 2]
    silent_votes = sum(1 for vote in votes if vote["silent_failure"])
    chosen = next(vote for vote in votes if vote["verdict"] == verdict)
    return {
        **chosen,
        "verdict": verdict,
        "fidelity": round(statistics.median(vote["fidelity"] for vote in votes), 2),
        "silent_failure": silent_votes * 2 > len(votes),
        "silent_failure_votes": silent_votes,
        "votes": verdicts,
        "agreement": f"{count}/{len(votes)}",
        # A single vote for silent failure is enough to ask a person: it is the worst defect.
        "needs_review": not has_majority or 0 < silent_votes < len(votes),
    }


def cast_vote(config: dict, packet_dir: Path, labels: list[str], vote: int) -> tuple[dict | None, float]:
    """Run one grader on a throwaway copy of the packet."""
    shift = (vote - 1) % len(labels)
    order = ", ".join(labels[shift:] + labels[:shift])
    prompt = f"Grade packet.md in this folder. Read the results in this order: {order}."
    command = [
        config["agent"]["claude_bin"], "-p", prompt,
        "--model", config["grader"]["model"],
        "--system-prompt", grader_prompt(config),
        "--strict-mcp-config",
        "--no-session-persistence",
        "--max-budget-usd", str(config["grader"]["budget_usd"]),
        "--tools", "Read",
        "--allowedTools", "Read",
        "--json-schema", json.dumps(GRADE_SCHEMA),
        "--output-format", "json",
    ]
    if config["agent"]["setting_sources"] is not None:
        command += ["--setting-sources", config["agent"]["setting_sources"]]
    with tempfile.TemporaryDirectory(prefix="mcp-eval-grade-") as scratch:
        work = Path(scratch) / "packet"
        shutil.copytree(packet_dir, work, ignore=shutil.ignore_patterns("grade.json"))
        done = subprocess.run(command, cwd=work, env=os.environ, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=config["agent"]["timeout_seconds"])
    try:
        result = json.loads(done.stdout)
        grade = result["structured_output"]
        if {item["label"] for item in grade["labels"]} != set(labels):
            raise KeyError("labels")
    except (ValueError, KeyError, TypeError):
        print(f"{packet_dir.name} vote {vote}: no usable grade; {(done.stdout + done.stderr)[-200:]}", file=sys.stderr)
        return None, 0
    return grade, result.get("total_cost_usd") or 0


def judge(config: dict, run_id: str) -> None:
    run_dir = run_paths(config, run_id)
    if not (run_dir / "blind-map.json").exists():
        raise ConfigError("run prepare before judge")
    blind_map = json.loads((run_dir / "blind-map.json").read_text(encoding="utf-8"))
    grader = config["grader"]
    wanted = grader["votes"]
    spent, reserved, skipped = 0.0, 0.0, 0
    for case_id, mapping in blind_map.items():
        packet_dir = run_dir / "grades" / case_id
        if (packet_dir / "grade.json").exists():
            continue
        labels = sorted(mapping)
        # Votes live outside the packet, so a later grader cannot read them.
        votes_dir = run_dir / "votes" / case_id
        votes_dir.mkdir(parents=True, exist_ok=True)
        for vote in range(1, wanted + 1):
            path = votes_dir / f"vote-{vote}.json"
            if path.exists():
                continue
            if reserved + grader["budget_usd"] > grader["total_usd"]:
                skipped += 1
                continue
            grade, cost = cast_vote(config, packet_dir, labels, vote)
            spent += cost
            # A vote with no usable grade reports no cost, yet it may have spent its cap.
            reserved += cost or grader["budget_usd"]
            if grade:
                path.write_text(json.dumps(grade, ensure_ascii=False, indent=2), encoding="utf-8")
        ballots = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(votes_dir.glob("vote-*.json"))]
        # Fewer than a majority of the requested votes decides nothing: the case stays pending.
        if len(ballots) < wanted // 2 + 1:
            print(f"{case_id}: {len(ballots)} of {wanted} votes, not enough to decide", file=sys.stderr)
            continue
        grade = {"labels": [{"label": label, **{k: v for k, v in tally([next(item for item in ballot["labels"] if item["label"] == label) for ballot in ballots]).items() if k != "label"}} for label in labels]}
        (packet_dir / "grade.json").write_text(json.dumps(grade, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{case_id}: " + ", ".join(f"{item['label']}={item['verdict']} ({item['agreement']}{', review' if item['needs_review'] else ''})" for item in grade["labels"]))
    ledger = run_dir / "grading.json"
    previous = json.loads(ledger.read_text(encoding="utf-8")).get("spent_usd", 0) if ledger.exists() else 0
    ledger.write_text(json.dumps({"spent_usd": round(previous + spent, 4), "votes": wanted}), encoding="utf-8")
    print(f"grading: US$ {spent:.4f}" + (f", {skipped} votes skipped by grader.total_usd" if skipped else ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["prepare", "judge"])
    parser.add_argument("--config", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--live", action="store_true", help="required by judge, which spends")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if args.action == "prepare":
            prepare(config, args.run)
            return 0
        problems = guard_problems(config)
        if not args.live:
            problems.insert(0, "judge calls a model: pass --live")
        if problems:
            print("Grading refused by the guard:", file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            return 2
        judge(config, args.run)
        return 0
    except (ConfigError, OSError, subprocess.TimeoutExpired) as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
