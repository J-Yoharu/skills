#!/usr/bin/env python3
"""Golden lane: run the cases with a real model, on the real client path.

Each run is an isolated `claude -p` process. It receives the server's `instructions`
and tools exactly as a client does, with nothing copied into a prompt. A subagent
does not work here, because it does not receive the server's `instructions`.

Without `--live` the script only prints the plan and exits. Spending needs the flag
AND the environment variable; budget, host list and run lock come after that.

Usage:
  run_golden.py --config eval.config.json                    # plan, calls no model
  run_golden.py --config eval.config.json --validate         # only checks the cases
  MCP_EVAL_LIVE=1 run_golden.py --config eval.config.json --live [--cases a,b] [--models haiku,sonnet] [--reps 3] [--holdout] [--run-id name]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

# Python's isolated mode (-I) leaves the script's own folder off the path, and the kit's modules live there.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_contract import contract_snapshot, cut_warning, fingerprint, read_contract
from kitlib.golden_common import (
    ConfigError,
    build_metrics,
    effective_limits,
    from_base,
    guard_problems,
    load_cases,
    load_config,
    parse_transcript,
    run_check,
    server_env,
    storage_notice,
)
from kitlib.mcp_client import McpError


def print_plan(config: dict, cases: list[dict], held_out: int, models: list[str], reps: int) -> None:
    runs = len(cases) * len(models) * reps
    per_run, total = config["budget"]["per_run_usd"], config["budget"]["total_usd"]
    print("Plan (nothing was run)")
    print(f"  mode: {config['mode']} | focus: {config['focus']}")
    print(f"  cases: {len(cases)}" + (f" (holdout left out: {held_out})" if held_out else ""))
    print(f"  models: {', '.join(models)}")
    print(f"  repetitions: {reps}")
    print(f"  runs: {runs}")
    if per_run and total:
        print(f"  cap per run: US$ {per_run} | total cap: US$ {total} | worst case: US$ {min(runs * per_run, total):.2f}")
    else:
        print("  budget: not set; a live run will be refused")
    try:
        init = read_contract(config)[1]
        if warning := cut_warning(len(init.get("instructions") or ""), effective_limits(config)):
            print(f"  warning: {warning}")
    except (ConfigError, McpError, OSError) as error:
        print(f"  warning: the server did not answer; a live run will stop before spending: {error}")
    print(f"To run: {config['guard']['live_env']}=1 {Path(sys.argv[0]).name} --config {config['_path']} --live")


def acquire_lock(results_dir: Path) -> Path:
    """One run at a time: parallel processes fight over state and rotating credentials."""
    results_dir.mkdir(parents=True, exist_ok=True)
    lock = results_dir / ".lock"
    if lock.exists():
        try:
            os.kill(int(lock.read_text()), 0)
            raise ConfigError(f"another run is in progress (pid {lock.read_text()}); lock at {lock}")
        except (ValueError, ProcessLookupError):
            lock.unlink()
    lock.write_text(str(os.getpid()))
    return lock


def run_hook(command: str | None, config: dict, env: dict, label: str) -> None:
    if not command:
        return
    done = subprocess.run(command, shell=True, cwd=config["_base"], env=env, capture_output=True, text=True, timeout=300)
    if done.returncode != 0:
        raise RuntimeError(f"hook {label} failed: {(done.stdout + done.stderr).strip()[-300:]}")


def build_command(config: dict, case: dict, model: str) -> list[str]:
    agent = config["agent"]
    attachments = [str(from_base(config, item)) for item in case.get("attachments", [])]
    prompt = case["prompt"]
    if attachments:
        prompt += "\n\nAttachments:\n" + "\n".join(attachments)
    tools = list(agent["builtin_tools"]) + (["Read"] if attachments else [])
    server = config["_server"]
    command = [
        agent["claude_bin"], "-p", prompt,
        "--model", model,
        "--strict-mcp-config",
        "--mcp-config", str(from_base(config, config["server"]["mcp_config"])),
        "--no-session-persistence",
        "--max-budget-usd", str(config["budget"]["per_run_usd"]),
        "--output-format", "stream-json", "--verbose",
        "--tools", ",".join(tools),
        "--allowedTools", ",".join([f"mcp__{server}", *tools]),
    ]
    if agent["setting_sources"] is not None:
        command += ["--setting-sources", agent["setting_sources"]]
    if agent["system_append"]:
        command += ["--append-system-prompt", agent["system_append"]]
    for directory in {str(Path(path).parent) for path in attachments}:
        command += ["--add-dir", directory]
    return command + list(agent["extra_args"])


def run_agent(command: list[str], cwd: str, env: dict, attempt_dir: Path, timeout: int) -> tuple[int, bool]:
    """Run `claude -p` and stamp each event with its arrival time (`_t`)."""
    started = time.monotonic()
    timed_out = threading.Event()
    with (attempt_dir / "transcript.jsonl").open("w", encoding="utf-8") as transcript, (attempt_dir / "stderr.log").open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=stderr, text=True, encoding="utf-8", errors="replace")

        def stop() -> None:
            timed_out.set()
            process.kill()

        timer = threading.Timer(timeout, stop)
        timer.start()
        for line in process.stdout:
            try:
                event = json.loads(line)
                event["_t"] = round(time.monotonic() - started, 3)
                transcript.write(json.dumps(event, ensure_ascii=False) + "\n")
            except ValueError:
                transcript.write(line)
        code = process.wait()
        timer.cancel()
    return code, timed_out.is_set()


def run_attempt(config: dict, run_dir: Path, case: dict, model: str, rep: int, base_env: dict) -> dict:
    """One full run: reset, agent, collection and checks."""
    attempt_dir = run_dir / case["id"] / f"{model}-r{rep}"
    artifact_dir = attempt_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    env = {
        **base_env,
        **server_env(config, artifact_dir),
        "EVAL_RUN_ID": run_dir.name,
        "EVAL_CASE_ID": case["id"],
        "EVAL_MODEL": model,
        "EVAL_REP": str(rep),
        "EVAL_ATTEMPT_DIR": str(attempt_dir),
    }
    record = {"case": case["id"], "model": model, "rep": rep, "attempt_dir": str(attempt_dir.relative_to(run_dir)), "ideal_calls": case.get("ideal_calls")}
    scratch = tempfile.mkdtemp(prefix="mcp-eval-run-")
    try:
        run_hook(config["hooks"]["before_case"], config, env, "before_case")
        code, timed_out = run_agent(build_command(config, case, model), scratch, env, attempt_dir, config["agent"]["timeout_seconds"])
        run_hook(config["hooks"]["after_case"], config, env, "after_case")
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        return {**record, "status": "infra", "detail": str(error), "checks_passed": False, "checks": [], "metrics": {"cost_usd": 0, "alerts": [str(error)]}}
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    parsed = parse_transcript(attempt_dir / "transcript.jsonl", config["_server"])
    metrics = build_metrics(parsed, config["_server"])
    (attempt_dir / "final.md").write_text(parsed["final_text"] or "", encoding="utf-8")
    (attempt_dir / "calls.json").write_text(json.dumps(parsed["calls"], ensure_ascii=False, indent=2), encoding="utf-8")
    checks = []
    for check in case.get("checks", []):
        passed, detail = run_check(check, parsed, metrics, env, config["_base"])
        checks.append({"type": check["type"], "passed": passed, "detail": detail})
    status = "timeout" if timed_out else "ok" if metrics["connected"] and metrics["ok"] else "infra" if not metrics["connected"] else "agent_error"
    return {**record, "status": status, "exit_code": code, "checks_passed": all(check["passed"] for check in checks), "checks": checks, "metrics": metrics, "init_tools": parsed["init"].get("tools", [])}


def git_state(base: str) -> dict:
    def git(*args: str) -> str:
        done = subprocess.run(["git", *args], cwd=base, capture_output=True, text=True)
        return done.stdout.strip() if done.returncode == 0 else ""

    return {"commit": git("rev-parse", "--short", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def claude_version(config: dict) -> str:
    try:
        done = subprocess.run([config["agent"]["claude_bin"], "--version"], capture_output=True, text=True, timeout=30)
        return done.stdout.strip()
    except OSError as error:
        raise ConfigError(f"could not find claude: {error}") from error


def run_battery(config: dict, cases: list[dict], models: list[str], reps: int, run_id: str) -> int:
    results_dir = from_base(config, config["results_dir"])
    lock = acquire_lock(results_dir)
    base_env = {**os.environ, **config["agent"]["env"]}
    run_dir = results_dir / run_id
    try:
        if run_dir.exists():
            raise ConfigError(f"run {run_id} already exists; use another --run-id")
        # Failing here is free: a server that is down must not cost a whole run.
        run_hook(config["hooks"]["before_run"], config, {**base_env, **server_env(config, results_dir)}, "before_run")
        config["_server"], init, tools = read_contract(config)
        limits = effective_limits(config)
        instructions_chars = len(init.get("instructions") or "")
        if warning := cut_warning(instructions_chars, limits):
            print(f"warning: {warning}")
        run_dir.mkdir(parents=True)
        manifest = {
            "run_id": run_id,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "mode": config["mode"],
            "server": config["_server"],
            "contract": fingerprint(contract_snapshot(init, tools)),
            "instructions_chars": instructions_chars,
            "instructions_limit": limits["instructions_chars"],
            "instructions_cut": instructions_chars > limits["instructions_chars"],
            "tools": len(tools),
            "claude_version": claude_version(config),
            "git": git_state(config["_base"]),
            "models": models,
            "repetitions": reps,
            "cases": [case["id"] for case in cases],
            "budget": config["budget"],
            "agent_env": config["agent"]["env"],
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "contract.json").write_text(json.dumps(contract_snapshot(init, tools), ensure_ascii=False, indent=2), encoding="utf-8")

        spent, reserved, skipped = 0.0, 0.0, 0
        per_run, total = config["budget"]["per_run_usd"], config["budget"]["total_usd"]
        with (run_dir / "results.jsonl").open("a", encoding="utf-8") as results:
            for case in cases:
                for model in models:
                    for rep in range(1, reps + 1):
                        if reserved + per_run > total:
                            skipped += 1
                            continue
                        record = run_attempt(config, run_dir, case, model, rep, base_env)
                        cost = record["metrics"].get("cost_usd", 0)
                        spent += cost
                        # A run that dies before the `result` event reports no cost, yet it may have spent its cap.
                        reserved += cost or per_run
                        results.write(json.dumps(record, ensure_ascii=False) + "\n")
                        results.flush()
                        metrics = record["metrics"]
                        mark = "ok" if record["checks_passed"] and record["status"] == "ok" else record["status"] if record["status"] != "ok" else "check failed"
                        print(f"{case['id']} {model} r{rep}: {mark} | {metrics.get('calls', 0)} calls, {metrics.get('errors', 0)} errors, US$ {metrics.get('cost_usd', 0)}, {metrics.get('duration_s', 0)} s | {metrics.get('sequence', '')}")
                        for alert in metrics.get("alerts", []):
                            print(f"  alert: {alert}")
        run_hook(config["hooks"]["after_run"], config, {**base_env, **server_env(config, results_dir)}, "after_run")
        manifest.update({"finished_at": datetime.now().isoformat(timespec="seconds"), "spent_usd": round(spent, 4), "skipped_by_budget": skipped})
        (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"run {run_id}: US$ {spent:.4f}" + (f", {skipped} runs skipped by the total cap" if skipped else ""))
        print(f"results in {run_dir}")
        print(storage_notice(results_dir))
        print(f"next: report_golden.py --config {config['_path']} --run {run_id}")
        return 0
    finally:
        lock.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True)
    parser.add_argument("--live", action="store_true", help="run for real and spend; without it, only print the plan")
    parser.add_argument("--validate", action="store_true", help="check the cases and exit")
    parser.add_argument("--cases", help="comma-separated ids")
    parser.add_argument("--models", help="comma-separated models")
    parser.add_argument("--reps", type=int)
    parser.add_argument("--holdout", action="store_true", help="include the reserved cases")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        cases, held_out = load_cases(config, args.holdout, args.cases.split(",") if args.cases else None)
        if args.validate:
            print(f"{len(cases) + held_out} valid cases")
            return 0
        models = args.models.split(",") if args.models else config["agent"]["models"]
        reps = args.reps or config["agent"]["repetitions"]
        if not args.live:
            print_plan(config, cases, held_out, models, reps)
            return 0
        if problems := guard_problems(config):
            print("Run refused by the guard:", file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            return 2
        return run_battery(config, cases, models, reps, args.run_id or datetime.now().strftime("%Y%m%d-%H%M%S"))
    except (ConfigError, McpError, RuntimeError) as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
