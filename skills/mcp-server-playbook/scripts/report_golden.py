#!/usr/bin/env python3
"""Run report: scorecard, flow, opportunities, delta and stop criteria.

Usage:
  report_golden.py --config eval.config.json --run <id> [--baseline <id>]
  report_golden.py --config eval.config.json --trend
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

# Python's isolated mode (-I) leaves the script's own folder off the path, and the kit's modules live there.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_behavior import behavior_lines, load_behavior
from kitlib.golden_common import ConfigError, from_base, load_config, read_jsonl

MARKS = {"clean": "✔", "partial": "◐", "fail": "✘", "pending": "?", "invalid": "∅"}


def load_grades(run_dir: Path) -> dict[str, dict]:
    """Return each run's grade, with the blind map undone."""
    map_path = run_dir / "blind-map.json"
    if not map_path.exists():
        return {}
    grades: dict[str, dict] = {}
    for case_id, labels in json.loads(map_path.read_text(encoding="utf-8")).items():
        grade_path = run_dir / "grades" / case_id / "grade.json"
        if not grade_path.exists():
            continue
        for item in json.loads(grade_path.read_text(encoding="utf-8")).get("labels", []):
            attempt = labels.get(item.get("label"))
            if attempt:
                grades[attempt] = item
    return grades


def verdict_of(record: dict, grade: dict | None) -> str:
    """Infra does not count against the server; a failed check is never clean."""
    if record["status"] in ("infra", "timeout"):
        return "invalid"
    if not record["checks_passed"] or record["status"] != "ok":
        return "fail" if not grade or grade.get("verdict") == "fail" else "partial"
    return grade["verdict"] if grade else "pending"


def load_run(config: dict, run_id: str) -> tuple[Path, dict, list[dict]]:
    run_dir = from_base(config, config["results_dir"]) / run_id
    records = read_jsonl(run_dir / "results.jsonl")
    if not records:
        raise ConfigError(f"run has no results: {run_dir}")
    grades = load_grades(run_dir)
    for record in records:
        record["grade"] = grades.get(record["attempt_dir"])
        record["verdict"] = verdict_of(record, record["grade"])
    return run_dir, json.loads((run_dir / "manifest.json").read_text(encoding="utf-8")), records


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0


def summarize(records: list[dict]) -> dict:
    """An invalid run leaves the count: it measures infrastructure, not the server."""
    valid = [record for record in records if record["verdict"] != "invalid"]
    metrics = [record["metrics"] for record in valid]
    decided = [record for record in valid if record["verdict"] != "pending"]
    clean = sum(1 for record in valid if record["verdict"] == "clean")
    return {
        "runs": len(records),
        "invalid": len(records) - len(valid),
        "pending": len(valid) - len(decided),
        "clean": clean,
        "partial": sum(1 for record in valid if record["verdict"] == "partial"),
        "fail": sum(1 for record in valid if record["verdict"] == "fail"),
        "clean_rate": clean / len(decided) if decided else None,
        "calls": median([metric["calls"] for metric in metrics]),
        "errors": sum(metric["errors"] for metric in metrics),
        "recovered": sum(metric["recovered_errors"] for metric in metrics),
        "duration": median([metric["duration_s"] for metric in metrics]),
        "cost": median([metric["cost_usd"] for metric in metrics]),
        "answered": sum(1 for metric in metrics if metric.get("answered", metric["ok"])),
        "valid": len(valid),
        "tokens": median([metric["tokens"].get("total") or sum(metric["tokens"].get(key, 0) for key in ("input", "output", "cache_read", "cache_write")) for metric in metrics]),
        "cost_total": sum(metric["cost_usd"] for metric in metrics),
        "out_tokens": median([metric["tokens"]["output"] for metric in metrics]),
        "cache_read": median([metric["tokens"]["cache_read"] for metric in metrics]),
        "cache_write": median([metric["tokens"]["cache_write"] for metric in metrics]),
        "silent": sum(1 for record in valid if (record["grade"] or {}).get("silent_failure")),
        "needs_review": sum(1 for record in valid if (record["grade"] or {}).get("needs_review")),
    }


def percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def slowest_tool(records: list[dict]) -> str:
    speeds = [(entry["ms_median"], name) for record in records for name, entry in record["metrics"].get("per_tool", {}).items() if entry["ms_median"] is not None]
    if not speeds:
        return "n/a"
    ms, name = max(speeds)
    return f"{name}, {ms} ms"


def stable_cases(records: list[dict]) -> str:
    """A case is stable when every repetition of each model got the same verdict."""
    groups: dict[tuple, set] = defaultdict(set)
    for record in records:
        groups[(record["case"], record["model"])].add(record["verdict"])
    return f"{sum(1 for verdicts in groups.values() if len(verdicts) == 1)} of {len(groups)}"


def scorecard_lines(records: list[dict], baseline: list[dict] | None, focus: str) -> list[str]:
    """One table for every angle; the chosen focus comes first."""
    now = summarize(records)
    before = summarize(baseline) if baseline else None

    def row(dimension: str, name: str, key: str, render: object) -> tuple[str, str, str, str]:
        value = render(now[key])
        return dimension, name, value, render(before[key]) if before else ""

    money = lambda value: f"US$ {value:.4f}"
    plain = lambda value: f"{value:g}"
    rows = [
        row("quality", "Clean", "clean_rate", percent),
        ("quality", "Answered", f"{now['answered']} of {now['valid']}", f"{before['answered']} of {before['valid']}" if before else ""),
        row("quality", "Silent failures", "silent", plain),
        row("cost", "Tokens per run (med.)", "tokens", plain),
        row("cost", "Cost per run (med.)", "cost", money),
        row("cost", "Calls per run (med.)", "calls", plain),
        row("speed", "Time per run (med.)", "duration", lambda value: f"{value:g} s"),
        ("speed", "Slowest tool", slowest_tool(records), slowest_tool(baseline) if baseline else ""),
        ("reliability", "Stable cases", stable_cases(records), stable_cases(baseline) if baseline else ""),
        ("reliability", "Errors recovered", f"{now['recovered']} of {now['errors']}", f"{before['recovered']} of {before['errors']}" if before else ""),
    ]
    rows.sort(key=lambda item: item[0] != focus)
    header = "| Dimension | Measure | Now |" + (" Baseline |" if before else "")
    divider = "|---|---|---|" + ("---|" if before else "")
    body = [f"| {dimension} | {name} | {value} |" + (f" {old} |" if before else "") for dimension, name, value, old in rows]
    return [header, divider, *body]


def score_table(by_model: dict[str, dict]) -> list[str]:
    lines = [
        "| Model | ✔ | ◐ | ✘ | ? | ∅ | Clean | Calls (med.) | Errors (recovered) | Time (med.) | Cost (med.) | Total cost | Output (med.) | Cache read (med.) | Cache write (med.) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for model, s in by_model.items():
        lines.append(
            f"| {model} | {s['clean']} | {s['partial']} | {s['fail']} | {s['pending']} | {s['invalid']} | {percent(s['clean_rate'])} | {s['calls']:g} | {s['errors']} ({s['recovered']}) | {s['duration']:g} s | US$ {s['cost']:.4f} | US$ {s['cost_total']:.4f} | {s['out_tokens']:g} | {s['cache_read']:g} | {s['cache_write']:g} |"
        )
    return lines


def case_table(records: list[dict], models: list[str]) -> list[str]:
    lines = ["| Case | " + " | ".join(models) + " | Calls per run | Ideal range |", "|---|" + "---|" * (len(models) + 2)]
    for case_id in dict.fromkeys(record["case"] for record in records):
        rows = [record for record in records if record["case"] == case_id]
        marks = ["".join(MARKS[record["verdict"]] for record in rows if record["model"] == model) or "-" for model in models]
        calls = "/".join(str(record["metrics"].get("calls", 0)) for record in rows)
        ideal = rows[0].get("ideal_calls")
        lines.append(f"| {case_id} | " + " | ".join(marks) + f" | {calls} | {'-'.join(map(str, ideal)) if ideal else '-'} |")
    return lines


def tool_table(records: list[dict]) -> list[str]:
    totals: dict[str, dict] = defaultdict(lambda: {"calls": 0, "errors": 0, "ms": [], "out": []})
    for record in records:
        for name, entry in record["metrics"].get("per_tool", {}).items():
            total = totals[name]
            total["calls"] += entry["calls"]
            total["errors"] += entry["errors"]
            total["out"].append(entry["out_chars_median"])
            if entry["ms_median"] is not None:
                total["ms"].append(entry["ms_median"])
    lines = ["| Tool | Calls | Errors | Latency (med.) | Response (med., characters) |", "|---|---|---|---|---|"]
    for name, total in sorted(totals.items(), key=lambda item: -item[1]["calls"]):
        lines.append(f"| {name} | {total['calls']} | {total['errors']} | {median(total['ms']):g} ms | {median(total['out']):g} |")
    return lines


def flow_lines(records: list[dict]) -> list[str]:
    lines = []
    for record in records:
        metrics = record["metrics"]
        lines.append(f"- `{record['case']}` {record['model']} r{record['rep']} {MARKS[record['verdict']]}: {metrics.get('sequence') or '(no calls)'}")
        lines += [f"  - failed `{check['type']}`: {check['detail']}" for check in record["checks"] if not check["passed"]]
        lines += [f"  - alert: {alert}" for alert in metrics.get("alerts", [])]
    return lines


def disagreement_lines(records: list[dict]) -> list[str]:
    """Split votes point at a borderline result or an ambiguous rubric: look here first."""
    lines = []
    for record in records:
        grade = record["grade"] or {}
        votes = grade.get("votes") or []
        if len(set(votes)) > 1 or grade.get("needs_review"):
            marks = "".join(MARKS[vote] for vote in votes)
            lines.append(f"- `{record['case']}` {record['model']} r{record['rep']}: {marks} ({grade.get('agreement')}){', needs review' if grade.get('needs_review') else ''}. {grade.get('summary', '')}")
    if not lines:
        return []
    return ["## Grader disagreement", "", *lines, ""]


def delta_lines(records: list[dict], baseline: list[dict], baseline_id: str) -> list[str]:
    lines = [f"## Delta against `{baseline_id}`", ""]
    now, before = group_by_model(records), group_by_model(baseline)
    for model in now:
        if model not in before:
            continue
        a, b = summarize(before[model]), summarize(now[model])
        lines.append(f"- {model}: clean {percent(a['clean_rate'])} to {percent(b['clean_rate'])}; calls {a['calls']:g} to {b['calls']:g}; median cost US$ {a['cost']:.4f} to US$ {b['cost']:.4f}")
    old = {(record["case"], record["model"]): record["verdict"] for record in baseline}
    regressions = sorted({f"{record['case']} ({record['model']})" for record in records if old.get((record["case"], record["model"])) == "clean" and record["verdict"] in ("partial", "fail")})
    lines.append(f"- regressions: {', '.join(regressions) if regressions else 'none'}")
    return lines + [""]


def group_by_model(records: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[record["model"]].append(record)
    return dict(grouped)


def stop_lines(summary: dict, criteria: dict) -> tuple[list[str], bool]:
    """The criteria only close with every run graded and none invalid."""
    rows = []
    if (value := criteria.get("min_clean_rate")) is not None:
        rows.append((f"clean ≥ {value:.0%}", summary["clean_rate"] is not None and summary["clean_rate"] >= value, percent(summary["clean_rate"])))
    if (value := criteria.get("max_silent_failures")) is not None:
        rows.append((f"silent failures ≤ {value}", summary["silent"] <= value, str(summary["silent"])))
    if (value := criteria.get("max_cost_per_case_usd")) is not None:
        rows.append((f"median cost ≤ US$ {value}", summary["cost"] <= value, f"US$ {summary['cost']:.4f}"))
    if (value := criteria.get("max_median_calls")) is not None:
        rows.append((f"median calls ≤ {value}", summary["calls"] <= value, f"{summary['calls']:g}"))
    if (value := criteria.get("max_median_tokens")) is not None:
        rows.append((f"median tokens ≤ {value}", summary["tokens"] <= value, f"{summary['tokens']:g}"))
    if (value := criteria.get("max_median_seconds")) is not None:
        rows.append((f"median time ≤ {value} s", summary["duration"] <= value, f"{summary['duration']:g} s"))
    rows.append(("nothing awaiting a grade", summary["pending"] == 0, str(summary["pending"])))
    rows.append(("no grade awaiting human review", summary["needs_review"] == 0, str(summary["needs_review"])))
    rows.append(("no invalid runs", summary["invalid"] == 0, str(summary["invalid"])))
    lines = ["| Criterion | Status | Measured |", "|---|---|---|"] + [f"| {name} | {'met' if passed else 'not met'} | {measured} |" for name, passed, measured in rows]
    return lines, all(passed for _, passed, _ in rows)


def lead_lines(behavior: dict, limit: int = 3) -> list[str]:
    """The few things worth doing next, already in the order of the focus."""
    suggestions = behavior.get("suggestions") or []
    if suggestions:
        return [f"{index}. `{item['tool']}`: {item['change']} Evidence: {', '.join(item['evidence'])}." for index, item in enumerate(suggestions[:limit], 1)]
    # General symptoms say little on their own: the specific patterns come first.
    findings = [item for item in behavior.get("findings", []) if item["rule"] not in ("over-range", "unused-tool")]
    return [f"{index}. `{item['tool']}`: {item['evidence']}. {item['hint']}" for index, item in enumerate(findings[:limit], 1)]


def summary_lines(records: list[dict], manifest: dict, baseline: list[dict] | None, baseline_id: str | None, behavior: dict, report_path: Path) -> list[str]:
    """The short answer. Numbers come from here, so nobody has to count them by hand."""
    grouped = group_by_model(records)
    overall = summarize(records)
    columns = [("Clean", "clean", "✔"), ("Partial", "partial", "◐"), ("Failed", "fail", "✘")]
    if overall["pending"]:
        columns.append(("Not graded", "pending", "?"))
    if overall["invalid"]:
        columns.append(("Invalid", "invalid", "∅"))
    lines = ["| Model | " + " | ".join(name for name, _, _ in columns) + " |", "|---|" + "---|" * len(columns)]
    for model, rows in grouped.items():
        summary = summarize(rows)
        lines.append(f"| {model} | " + " | ".join(f"{mark} {summary[key]}" for _, key, mark in columns) + " |")
    cases = len({record["case"] for record in records})
    lines += ["", f"{cases} case(s), {manifest['repetitions']} repetition(s) per case and model."]
    if overall["pending"]:
        lines.append("Not everything is graded: for the ? runs, only the automatic checks decided.")
    if baseline:
        before = summarize(baseline)
        lines.append(f"Against `{baseline_id}`: clean {before['clean']} to {overall['clean']}, median calls {before['calls']:g} to {overall['calls']:g}, median tokens {before['tokens']:g} to {overall['tokens']:g}.")
    leads = lead_lines(behavior)
    lines += ["", "Possible improvements:", "", *(leads or ["No improvement stands out."]), "", f"Details in {report_path}, or ask."]
    return lines


def cut_note(manifest: dict) -> str:
    """Make it explicit whether the run measured the full text or the cut one."""
    return f", **cut at {manifest['instructions_limit']}**" if manifest.get("instructions_cut") else ""


def build_report(config: dict, run_id: str, baseline_id: str | None) -> tuple[Path, bool, list[str]]:
    run_dir, manifest, records = load_run(config, run_id)
    grouped = group_by_model(records)
    models = list(grouped)
    overall = summarize(records)
    criteria_lines, reached = stop_lines(overall, config["stop_criteria"])
    baseline = load_run(config, baseline_id)[2] if baseline_id else None
    ledger = run_dir / "grading.json"
    grading = json.loads(ledger.read_text(encoding="utf-8")).get("spent_usd", 0) if ledger.exists() else 0
    behavior = load_behavior(config, run_dir, records)
    analysis = behavior.get("analysis_cost_usd", 0)
    path = run_dir / "report.md"
    summary = summary_lines(records, manifest, baseline, baseline_id, behavior, path)
    lines = [
        f"# Run `{run_id}` of {config['name']}",
        "",
        f"Mode {manifest['mode']}, contract `{manifest['contract']}`, commit `{manifest['git'].get('commit') or 'n/a'}`{' with local changes' if manifest['git'].get('dirty') else ''}, {manifest['claude_version']}, instructions with {manifest['instructions_chars']} characters{cut_note(manifest)}.",
        f"Spent: US$ {manifest.get('spent_usd', 0)} on runs, US$ {grading} on grading, US$ {analysis} on analysis. Repetitions per case: {manifest['repetitions']}. Focus: {config['focus']}.",
        "",
        "Legend: ✔ clean, ◐ partial, ✘ failed, ? not graded, ∅ invalid (infrastructure).",
        "",
        "## Summary",
        "",
        *summary,
        "",
        "## Scorecard",
        "",
        *scorecard_lines(records, baseline, config["focus"]),
        "",
        *behavior_lines(behavior),
        "## Score by model",
        "",
        *score_table({model: summarize(rows) for model, rows in grouped.items()}),
        "",
        "## By case",
        "",
        *case_table(records, models),
        "",
        "## Tools",
        "",
        *tool_table(records),
        "",
        *disagreement_lines(records),
    ]
    if baseline_id:
        lines += delta_lines(records, baseline, baseline_id)
    lines += ["## Flow", "", *flow_lines(records), "", "## Stop criteria", "", *criteria_lines, "", f"**{'Criteria met.' if reached else 'Criteria not met.'}**", ""]
    lines += [
        "## Findings (fill in)",
        "",
        "| Finding | Cause (server, model, infra, answer key) | Priority (P0, P1, P2) | Action | Recheck in |",
        "|---|---|---|---|---|",
        "|  |  |  |  |  |",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path, reached, summary


def build_trend(config: dict) -> Path:
    """One line per round, to see the direction over time."""
    results_dir = from_base(config, config["results_dir"])
    lines = [
        f"# Trend of {config['name']}",
        "",
        "| Round | Started | Contract | Clean | Tokens (med.) | Cost (med.) | Calls (med.) | Time (med.) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    rounds = sorted((path for path in results_dir.iterdir() if (path / "manifest.json").exists()), key=lambda path: json.loads((path / "manifest.json").read_text(encoding="utf-8")).get("started_at", ""))
    for path in rounds:
        _, manifest, records = load_run(config, path.name)
        s = summarize(records)
        lines.append(f"| {path.name} | {manifest.get('started_at', '')} | `{manifest.get('contract')}` | {percent(s['clean_rate'])} | {s['tokens']:g} | US$ {s['cost']:.4f} | {s['calls']:g} | {s['duration']:g} s |")
    target = results_dir / "trend.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run")
    parser.add_argument("--baseline")
    parser.add_argument("--trend", action="store_true", help="write one line per round to trend.md")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if args.trend:
            print(f"trend in {build_trend(config)}")
            return 0
        if not args.run:
            raise ConfigError("pass --run <id> or --trend")
        path, reached, summary = build_report(config, args.run, args.baseline)
    except (ConfigError, OSError) as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 2
    print("\n".join(summary))
    print()
    print("stop criteria met" if reached else "stop criteria not met")
    return 0


if __name__ == "__main__":
    sys.exit(main())
