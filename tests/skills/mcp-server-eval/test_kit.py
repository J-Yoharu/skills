#!/usr/bin/env python3
"""Regression tests for the skill's scripts, with no model and no cost.

A fake `claude` prints a fixed transcript and records that it was called. That proves
the guards really hold back the spend, instead of only looking safe.

These tests stay outside the payload: consumers get the engine, not its test suite.

Usage: make test-skills NAME=mcp-server-eval
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.dont_write_bytecode = True  # bytecode inside the payload fails repository validation
ROOT = Path(__file__).resolve().parents[3] / "skills" / "mcp-server-eval"
SCRIPTS = ROOT / "scripts"
KIT = ROOT / "assets" / "kit"
sys.path.insert(0, str(SCRIPTS))

from analyze_behavior import inspect_round, inspect_run, rank
from check_auth import Report, check_authorize_rejects
from check_contract import contract_snapshot, cut_warning, diff_snapshot, inspect_contract
from discover_project import discover, suggest_target
from kitlib.golden_common import DEFAULTS, LIMIT_ENV, build_metrics, effective_limits, git_ignore_state, guard_problems, load_config, parse_transcript, storage_notice, validate_case
from grade_golden import tally
from report_golden import verdict_of

FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, re, sys
if "--version" in sys.argv:
    print("0.0.0 (fake)")
    sys.exit(0)
marker = os.environ.get("FAKE_MARKER")
if marker:
    with open(marker, "a") as f:
        f.write(json.dumps({"argv": sys.argv, "cwd": os.getcwd(), "files": sorted(os.listdir("."))}) + "\n")
if "--json-schema" in sys.argv and os.path.exists("digest.md"):
    suggestion = {"kind": "add_parameter", "tool": "create_note", "change": "Add `tag`.", "why": "Because.", "evidence": ["create-reminder"], "expected_effect": "Fewer calls.", "dimension": "cost", "confidence": "high"}
    print(json.dumps({"structured_output": {"suggestions": [suggestion]}, "total_cost_usd": 0.02}))
    sys.exit(0)
if "--json-schema" in sys.argv:
    labels = re.findall(r"^## Result (\w)$", open("packet.md", encoding="utf-8").read(), re.M)
    counter = os.environ["FAKE_VOTE_COUNTER"]
    index = int(open(counter).read()) if os.path.exists(counter) else 0
    open(counter, "w").write(str(index + 1))
    verdicts = os.environ.get("FAKE_VOTES", "clean,clean,clean").split(",")
    verdict = verdicts[index % len(verdicts)]
    if verdict == "broken":
        print("not json")
        sys.exit(0)
    grade = {"labels": [{"label": label, "verdict": verdict, "fidelity": 0.9, "silent_failure": False, "items": [], "summary": "summary"} for label in labels]}
    print(json.dumps({"structured_output": grade, "total_cost_usd": 0.01}))
    sys.exit(0)
cost = float(os.environ.get("FAKE_COST", "0.01"))
final = os.environ.get("FAKE_FINAL", "Saved the note.")
events = [
    {"type": "system", "subtype": "init", "mcp_servers": [{"name": "demo", "status": os.environ.get("FAKE_STATUS", "connected")}], "tools": ["ToolSearch"]},
    {"type": "assistant", "message": {"id": "m1", "usage": {"output_tokens": 1}, "content": [{"type": "tool_use", "id": "t1", "name": "mcp__demo__create_note", "input": {"title": "Call", "body": "accountant"}}]}},
    {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": [{"type": "text", "text": "error that teaches"}]}]}},
    {"type": "assistant", "message": {"id": "m2", "content": [{"type": "tool_use", "id": "t2", "name": "mcp__demo__create_note", "input": {"title": "Call", "body": "accountant"}}]}},
    {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t2", "content": [{"type": "text", "text": "{\"id\":\"n4\"}"}]}]}},
    {"type": "assistant", "message": {"id": "m3", "content": [{"type": "text", "text": final}]}},
    {"type": "result", "subtype": "success", "is_error": False, "num_turns": 3, "duration_ms": 2000, "total_cost_usd": cost, "result": final, "terminal_reason": "completed",
     "usage": {"input_tokens": 10, "output_tokens": 500, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 200, "output_tokens_details": {"thinking_tokens": 50}}},
]
for event in events[:-1] if os.environ.get("FAKE_NO_RESULT") else events:
    print(json.dumps(event))
'''


def run_script(name: str, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    clean = {key: value for key, value in os.environ.items() if key not in ("CI", "MCP_EVAL_LIVE", LIMIT_ENV)}
    return subprocess.run([sys.executable, "-B", str(SCRIPTS / name), *args], capture_output=True, text=True, env={**clean, **(env or {})})


class KitCase(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="mcp-kit-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        shutil.copytree(KIT, self.dir / "kit", ignore=shutil.ignore_patterns(".mcp-eval", "scripts", "__pycache__"))
        self.fake = self.dir / "claude"
        self.fake.write_text(FAKE_CLAUDE)
        self.fake.chmod(self.fake.stat().st_mode | stat.S_IEXEC)
        self.marker = self.dir / "called.log"
        self.config = self.dir / "kit" / "eval.config.json"
        self.write_config()

    def write_config(self, **changes: object) -> None:
        config = json.loads((self.dir / "kit" / "eval.config.example.json").read_text(encoding="utf-8"))
        config["agent"]["claude_bin"] = str(self.fake)
        for key, value in changes.items():
            if isinstance(value, dict):
                config[key] = {**config.get(key, {}), **value}
            else:
                config[key] = value
        self.config.write_text(json.dumps(config), encoding="utf-8")

    def live_env(self, **extra: str) -> dict:
        return {"MCP_EVAL_LIVE": "1", "FAKE_MARKER": str(self.marker), "FAKE_VOTE_COUNTER": str(self.dir / "votes.count"), **extra}

    def live(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        return run_script("run_golden.py", "--config", str(self.config), "--live", "--cases", "create-reminder", *args, env=self.live_env(**env))

    def run_dir(self, run_id: str = "r1") -> Path:
        return self.dir / "kit" / ".mcp-eval" / "runs" / run_id

    def results(self, run_id: str) -> list[dict]:
        path = self.run_dir(run_id) / "results.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def relax_case(self) -> None:
        """The fake `claude` writes no note: the case only asks for the call, to focus on grading."""
        case_path = self.dir / "kit/golden/cases/create-reminder.json"
        case = json.loads(case_path.read_text(encoding="utf-8"))
        case["checks"] = [{"type": "tool_called", "tool": "create_note"}]
        case_path.write_text(json.dumps(case), encoding="utf-8")

    def graded_run(self, **env: str) -> subprocess.CompletedProcess:
        self.relax_case()
        self.live("--run-id", "r1")
        run_script("grade_golden.py", "prepare", "--config", str(self.config), "--run", "r1")
        return run_script("grade_golden.py", "judge", "--config", str(self.config), "--run", "r1", "--live", env=self.live_env(**env))


class GuardTests(KitCase):
    def test_without_live_only_plans(self) -> None:
        done = run_script("run_golden.py", "--config", str(self.config), env=self.live_env())
        self.assertEqual(done.returncode, 0)
        self.assertIn("nothing was run", done.stdout)
        self.assertFalse(self.marker.exists(), "the plan must not call claude")

    def test_live_flag_without_env_refuses(self) -> None:
        done = run_script("run_golden.py", "--config", str(self.config), "--live", env={"FAKE_MARKER": str(self.marker)})
        self.assertEqual(done.returncode, 2)
        self.assertIn("MCP_EVAL_LIVE", done.stderr)
        self.assertFalse(self.marker.exists())

    def test_ci_refuses_by_default(self) -> None:
        done = self.live(CI="true")
        self.assertEqual(done.returncode, 2)
        self.assertIn("CI", done.stderr)
        self.assertFalse(self.marker.exists())

    def test_missing_budget_refuses(self) -> None:
        self.write_config(budget={"per_run_usd": None, "total_usd": None})
        done = self.live()
        self.assertEqual(done.returncode, 2)
        self.assertIn("budget", done.stderr)

    def test_host_outside_allowlist_refuses(self) -> None:
        production = {"mcpServers": {"demo": {"type": "http", "url": "https://production.example.com/mcp"}}}
        (self.dir / "kit" / "mcp.example.json").write_text(json.dumps(production))
        done = self.live()
        self.assertEqual(done.returncode, 2)
        self.assertIn("production.example.com", done.stderr)
        self.assertFalse(self.marker.exists())

    def test_subdomain_of_localhost_is_allowed(self) -> None:
        local = {"mcpServers": {"demo": {"type": "http", "url": "http://tenant-a.localhost:8000/mcp"}}}
        (self.dir / "kit" / "mcp.example.json").write_text(json.dumps(local))
        config = load_config(self.config)
        self.assertEqual(guard_problems(config, {"MCP_EVAL_LIVE": "1"}), [])

    def test_judge_needs_live_too(self) -> None:
        self.assertEqual(self.live("--run-id", "r1").returncode, 0)
        done = run_script("grade_golden.py", "judge", "--config", str(self.config), "--run", "r1", env=self.live_env())
        self.assertEqual(done.returncode, 2)
        self.assertIn("--live", done.stderr)


class RunTests(KitCase):
    def test_full_run_records_metrics_from_result_event(self) -> None:
        done = self.live("--run-id", "r1")
        self.assertEqual(done.returncode, 0, done.stderr)
        record = self.results("r1")[0]
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["metrics"]["calls"], 2)
        self.assertEqual(record["metrics"]["errors"], 1)
        self.assertEqual(record["metrics"]["recovered_errors"], 1)
        self.assertEqual(record["metrics"]["sequence"], "create_note! create_note")
        self.assertEqual(record["metrics"]["tokens"]["output"], 500, "totals come from result, not from a partial message")
        self.assertEqual(record["metrics"]["tokens"]["thinking"], 50)

    def test_command_uses_real_client_path_with_isolation(self) -> None:
        self.live("--run-id", "r1")
        argv = json.loads(self.marker.read_text().splitlines()[0])["argv"]
        for flag in ("--strict-mcp-config", "--mcp-config", "--no-session-persistence", "--max-budget-usd", "--setting-sources"):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index("--tools") + 1], "ToolSearch")
        self.assertNotIn("Flow:", " ".join(argv), "server instructions are never copied into the prompt")

    def test_total_budget_stops_the_battery(self) -> None:
        self.write_config(budget={"per_run_usd": 1, "total_usd": 2.5})
        done = self.live("--run-id", "r1", "--reps", "5", FAKE_COST="1")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(self.results("r1")), 2)
        manifest = json.loads((self.run_dir() / "manifest.json").read_text())
        self.assertEqual(manifest["skipped_by_budget"], 3)

    def test_plan_and_run_warn_only_when_the_model_gets_cut_text(self) -> None:
        quiet = run_script("run_golden.py", "--config", str(self.config), env=self.live_env())
        self.assertNotIn(LIMIT_ENV, quiet.stdout + quiet.stderr)
        self.write_config(limits={"instructions_chars": 100})
        plan = run_script("run_golden.py", "--config", str(self.config), env=self.live_env())
        self.assertIn(LIMIT_ENV, plan.stdout + plan.stderr)
        run = self.live("--run-id", "r1")
        self.assertIn(LIMIT_ENV, run.stdout + run.stderr)

    def test_a_run_that_reports_no_cost_counts_as_its_whole_cap(self) -> None:
        # Regression: a run killed before the `result` event spent money that the total cap never saw.
        self.write_config(budget={"per_run_usd": 1, "total_usd": 2})
        done = self.live("--run-id", "r1", "--reps", "5", FAKE_NO_RESULT="1")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(self.results("r1")), 2)
        self.assertEqual(json.loads((self.run_dir() / "manifest.json").read_text())["skipped_by_budget"], 3)

    def test_ipv6_loopback_is_allowed_by_default(self) -> None:
        # Regression: the default was "[::1]", which fnmatch reads as a character class.
        servers = self.dir / "kit" / "mcp.ipv6.json"
        servers.write_text(json.dumps({"mcpServers": {"demo": {"type": "http", "url": "http://[::1]:8000/mcp"}}}), encoding="utf-8")
        config = load_config(self.config)
        config["guard"]["allowed_hosts"] = DEFAULTS["guard"]["allowed_hosts"]
        config["server"]["mcp_config"] = str(servers)
        self.assertEqual(guard_problems(config, {"MCP_EVAL_LIVE": "1"}), [])

    def test_server_not_connected_is_infra_not_a_failed_case(self) -> None:
        self.live("--run-id", "r1", FAKE_STATUS="failed")
        record = self.results("r1")[0]
        self.assertEqual(record["status"], "infra")
        self.assertEqual(verdict_of({**record}, None), "invalid")

    def test_second_run_with_same_id_refuses(self) -> None:
        self.assertEqual(self.live("--run-id", "r1").returncode, 0)
        self.assertEqual(self.live("--run-id", "r1").returncode, 2)

    def test_lock_blocks_a_concurrent_run(self) -> None:
        results = self.dir / "kit" / ".mcp-eval" / "runs"
        results.mkdir(parents=True)
        (results / ".lock").write_text(str(os.getpid()))
        done = self.live("--run-id", "r1")
        self.assertEqual(done.returncode, 2)
        self.assertIn("another run", done.stderr)

    def test_blind_packet_hides_the_model(self) -> None:
        self.live("--run-id", "r1", "--models", "secret-model", FAKE_FINAL="Saved by Secret-Model.")
        done = run_script("grade_golden.py", "prepare", "--config", str(self.config), "--run", "r1")
        self.assertEqual(done.returncode, 0, done.stderr)
        packet = (self.run_dir() / "grades/create-reminder/packet.md").read_text(encoding="utf-8")
        self.assertNotIn("secret-model", packet.lower())
        self.assertIn("Saved by [model].", packet)
        self.assertFalse(list((self.run_dir() / "grades").rglob("blind-map.json")), "the map must stay out of the grader's reach")

    def test_a_run_says_where_the_data_stayed(self) -> None:
        self.assertIn("Runs are saved in", self.live("--run-id", "r1").stdout)

    def test_failed_check_never_counts_as_clean(self) -> None:
        record = {"status": "ok", "checks_passed": False}
        self.assertEqual(verdict_of(record, {"verdict": "clean"}), "partial")
        self.assertEqual(verdict_of(record, None), "fail")


class VoteTests(KitCase):
    def grade(self) -> dict:
        return json.loads((self.run_dir() / "grades/create-reminder/grade.json").read_text(encoding="utf-8"))["labels"][0]

    def graders(self) -> list[dict]:
        calls = [json.loads(line) for line in self.marker.read_text().splitlines()]
        return [call for call in calls if "--json-schema" in call["argv"]]

    def test_three_independent_votes_and_majority_wins(self) -> None:
        done = self.graded_run(FAKE_VOTES="clean,partial,clean")
        self.assertEqual(done.returncode, 0, done.stderr)
        grade = self.grade()
        self.assertEqual(len(self.graders()), 3)
        self.assertEqual(grade["verdict"], "clean")
        self.assertEqual(grade["agreement"], "2/3")
        self.assertEqual(grade["votes"], ["clean", "partial", "clean"])
        self.assertFalse(grade["needs_review"])

    def test_graders_cannot_see_the_map_or_each_other(self) -> None:
        self.graded_run()
        for call in self.graders():
            self.assertNotIn(str(self.dir), call["cwd"], "each grader works on a throwaway copy outside the run")
            self.assertNotIn("grade.json", call["files"])
            self.assertNotIn("blind-map.json", call["files"])
            self.assertNotIn("votes", call["files"])

    def test_three_way_split_goes_to_a_person(self) -> None:
        self.graded_run(FAKE_VOTES="clean,partial,fail")
        grade = self.grade()
        self.assertEqual(grade["verdict"], "partial", "no majority takes the middle verdict")
        self.assertTrue(grade["needs_review"])

    def test_report_shows_disagreement_and_blocks_the_stop_criteria_on_review(self) -> None:
        self.graded_run(FAKE_VOTES="clean,partial,fail")
        done = run_script("report_golden.py", "--config", str(self.config), "--run", "r1")
        self.assertIn("stop criteria not met", done.stdout)
        report = (self.run_dir() / "report.md").read_text(encoding="utf-8")
        self.assertIn("## Grader disagreement", report)
        self.assertIn("✔◐✘", report)

    def test_unanimous_grade_meets_the_stop_criteria(self) -> None:
        self.graded_run()
        done = run_script("report_golden.py", "--config", str(self.config), "--run", "r1")
        self.assertIn("stop criteria met", done.stdout)
        report = (self.run_dir() / "report.md").read_text(encoding="utf-8")
        self.assertNotIn("## Grader disagreement", report)
        self.assertIn("create_note! create_note", report)

    def test_too_few_valid_votes_leave_the_case_pending(self) -> None:
        done = self.graded_run(FAKE_VOTES="clean,broken,broken")
        self.assertIn("not enough to decide", done.stderr)
        self.assertFalse((self.run_dir() / "grades/create-reminder/grade.json").exists())

    def test_a_rerun_only_casts_the_missing_votes(self) -> None:
        self.graded_run(FAKE_VOTES="clean,broken,broken")
        self.assertEqual(len(self.graders()), 3)
        run_script("grade_golden.py", "judge", "--config", str(self.config), "--run", "r1", "--live", env=self.live_env(FAKE_VOTES="clean"))
        self.assertEqual(len(self.graders()), 5, "only the 2 unusable votes are cast again")
        self.assertEqual(len(list((self.run_dir() / "votes/create-reminder").glob("vote-*.json"))), 3)
        self.assertEqual(self.grade()["verdict"], "clean")

    def test_grader_budget_stops_voting(self) -> None:
        self.write_config(grader={"budget_usd": 1, "total_usd": 0.5})
        done = self.graded_run()
        self.assertIn("skipped by grader.total_usd", done.stdout)
        self.assertEqual(self.graders(), [])

    def test_an_unusable_vote_counts_as_its_whole_cap(self) -> None:
        # Regression: a vote that returned no grade had spent money that the total cap never saw.
        self.write_config(grader={"budget_usd": 1, "total_usd": 2})
        done = self.graded_run(FAKE_VOTES="broken,broken,broken")
        self.assertIn("1 votes skipped by grader.total_usd", done.stdout)
        self.assertEqual(len(self.graders()), 2)

    def test_one_silent_failure_vote_asks_for_review(self) -> None:
        base = {"fidelity": 0.9, "items": [], "summary": "s"}
        votes = [{**base, "verdict": "clean", "silent_failure": flag} for flag in (False, False, True)]
        grade = tally(votes)
        self.assertFalse(grade["silent_failure"])
        self.assertEqual(grade["silent_failure_votes"], 1)
        self.assertTrue(grade["needs_review"])

    def test_two_votes_that_disagree_take_the_lower_verdict(self) -> None:
        base = {"fidelity": 0.9, "items": [], "summary": "s", "silent_failure": False}
        self.assertEqual(tally([{**base, "verdict": "clean"}, {**base, "verdict": "partial"}])["verdict"], "partial")


def call(tool: str, error: bool = False, out_chars: int = 100, ms: int = 10, preview: str = "", **args: object) -> dict:
    return {"tool": tool, "args": args, "error": error, "out_chars": out_chars, "ms": ms, "preview": preview}


class BehaviorTests(unittest.TestCase):
    LIMITS = DEFAULTS["analysis"]

    def rules(self, calls: list[dict], ideal: list[int] | None = None) -> dict:
        record = {"case": "c", "ideal_calls": ideal}
        return {item["rule"]: item for item in inspect_run(record, calls, self.LIMITS)}

    def test_walking_pages_points_to_a_missing_filter(self) -> None:
        found = self.rules([call("list", offset=value) for value in (0, 5, 10, 15, 20)])
        self.assertEqual(found["pagination-walk"]["wasted_calls"], 4)
        self.assertIn("filter", found["pagination-walk"]["hint"])

    def test_one_call_per_item_points_to_a_batch(self) -> None:
        found = self.rules([call("get", id=f"n{value}") for value in range(5)])
        self.assertEqual(found["fan-out"]["wasted_calls"], 4)
        self.assertNotIn("fan-out", self.rules([call("get", id="n1"), call("get", id="n2")]))

    def test_rephrased_search_is_churn(self) -> None:
        found = self.rules([call("search", q=value) for value in ("europe", "trip", "travel partners")])
        self.assertIn("search-churn", found)

    def test_long_content_is_not_a_rephrased_search(self) -> None:
        found = self.rules([call("insert", markup="x" * 300 + str(value)) for value in range(5)])
        self.assertNotIn("search-churn", found)
        self.assertIn("many-writes", found)

    def test_same_check_after_an_edit_is_not_repeated(self) -> None:
        found = self.rules([call("validate"), call("replace", id="b1"), call("validate")])
        self.assertNotIn("repeated-call", found)

    def test_same_call_twice_in_a_row_is_repeated(self) -> None:
        self.assertIn("repeated-call", self.rules([call("read", id="a"), call("read", id="a")]))

    def test_errors_in_a_row_are_a_loop(self) -> None:
        found = self.rules([call("write", error=True, preview="bad", id="a"), call("write", error=True, preview="bad", id="b")])
        self.assertIn("error-loop", found)
        self.assertIn("bad", found["error-loop"]["evidence"])

    def test_more_calls_than_the_ideal_range(self) -> None:
        self.assertEqual(self.rules([call("a"), call("b"), call("c")], [1, 1])["over-range"]["wasted_calls"], 2)

    def test_no_calls_is_flagged(self) -> None:
        self.assertIn("no-calls", self.rules([]))

    def round_rules(self, calls: list[dict], tools: list[dict]) -> dict:
        found = inspect_round([], {"a": calls}, {"tools": tools}, self.LIMITS)
        return {item["rule"]: item for item in found}

    def test_a_parameter_nobody_passes_is_flagged(self) -> None:
        tool = {"name": "list", "inputSchema": {"properties": {"offset": {}, "tag": {}}}}
        self.assertIn("tag", self.round_rules([call("list", offset=0)], [tool])["unused-parameter"]["evidence"])

    def test_a_tool_nobody_calls_is_flagged(self) -> None:
        self.assertIn("unused-tool", self.round_rules([], [{"name": "ghost"}]))

    def test_heavy_response_and_slow_tool(self) -> None:
        found = self.round_rules([call("read", out_chars=50000, ms=9000)], [])
        self.assertIn("heavy-response", found)
        self.assertIn("slow-tool", found)

    def test_focus_decides_what_comes_first(self) -> None:
        items = [{"dimension": "cost", "wasted_calls": 9, "wasted_chars": 0}, {"dimension": "speed", "wasted_calls": 0, "wasted_chars": 0}, {"dimension": "quality", "wasted_calls": 1, "wasted_chars": 0}]
        self.assertEqual(rank(items, "speed")[0]["dimension"], "speed")
        self.assertEqual(rank(items, "quality")[0]["dimension"], "quality")
        self.assertEqual(rank(items, "cost")[0]["dimension"], "cost")


class ObservabilityTests(KitCase):
    def report(self, *flags: str) -> str:
        done = run_script("report_golden.py", "--config", str(self.config), "--run", "r1", *flags)
        self.assertEqual(done.returncode, 0, done.stderr)
        return (self.run_dir() / "report.md").read_text(encoding="utf-8")

    def test_scorecard_covers_every_angle(self) -> None:
        self.live("--run-id", "r1")
        report = self.report()
        for measure in ("Clean", "Answered", "Silent failures", "Tokens per run", "Cost per run", "Calls per run", "Time per run", "Slowest tool", "Stable cases", "Errors recovered", "## Opportunities"):
            self.assertIn(measure, report)

    def test_focus_moves_its_dimension_to_the_top(self) -> None:
        self.write_config(focus="speed")
        self.live("--run-id", "r1")
        scorecard = self.report().split("## Scorecard")[1]
        self.assertLess(scorecard.index("Time per run"), scorecard.index("Clean"))

    def summary(self, *flags: str) -> str:
        return run_script("report_golden.py", "--config", str(self.config), "--run", "r1", *flags).stdout

    def test_summary_shows_each_mark_with_its_number(self) -> None:
        self.graded_run(FAKE_VOTES="partial")
        output = self.summary()
        self.assertIn("| haiku | ✔ 0 | ◐ 1 | ✘ 0 |", output)
        self.assertIn("1 case(s), 1 repetition(s) per case and model.", output)
        self.assertIn("report.md, or ask.", output)
        self.assertNotIn("Not graded", output)

    def test_summary_says_when_grading_did_not_run(self) -> None:
        self.relax_case()
        self.live("--run-id", "r1")
        output = self.summary()
        self.assertIn("? 1", output)
        self.assertIn("only the automatic checks decided", output)

    def test_summary_compares_only_with_a_baseline(self) -> None:
        self.live("--run-id", "r0")
        self.live("--run-id", "r1")
        self.assertNotIn("Against", self.summary())
        self.assertIn("Against `r0`: clean 0 to 0, median calls 2 to 2", self.summary("--baseline", "r0"))

    def test_summary_keeps_at_most_three_improvements_and_prefers_the_analyst(self) -> None:
        self.live("--run-id", "r1")
        item = {"tool": "t", "change": "Add `tag`.", "evidence": ["c"], "kind": "add_parameter", "why": "w", "expected_effect": "e", "dimension": "cost", "confidence": "high"}
        (self.run_dir() / "behavior.json").write_text(json.dumps({"suggestions": [item] * 5}))
        output = self.summary()
        self.assertIn("3. `t`: Add `tag`.", output)
        self.assertNotIn("4. `t`", output)

    def test_summary_opens_the_report(self) -> None:
        self.live("--run-id", "r1")
        report = self.report()
        self.assertLess(report.index("## Summary"), report.index("## Scorecard"))

    def test_unknown_focus_is_refused(self) -> None:
        self.write_config(focus="vibes")
        self.assertIn("focus", self.live("--run-id", "r1").stderr)

    def test_token_and_speed_criteria_can_block_the_stop(self) -> None:
        self.graded_run()
        for criterion in ("max_median_tokens", "max_median_seconds"):
            with self.subTest(criterion):
                self.write_config(stop_criteria={criterion: 0.001})
                done = run_script("report_golden.py", "--config", str(self.config), "--run", "r1")
                self.assertIn("stop criteria not met", done.stdout)

    def test_report_separates_run_grading_and_analysis_costs(self) -> None:
        self.graded_run()
        run_script("analyze_behavior.py", "--config", str(self.config), "--run", "r1", "--live", env=self.live_env())
        report = self.report()
        self.assertRegex(report, r"on runs, US\$ 0\.03 on grading, US\$ 0\.02 on analysis")

    def test_analyst_needs_the_guard_and_its_ideas_reach_the_report(self) -> None:
        self.live("--run-id", "r1")
        free = run_script("analyze_behavior.py", "--config", str(self.config), "--run", "r1", "--live", env={"FAKE_MARKER": str(self.marker)})
        self.assertEqual(free.returncode, 2)
        run_script("analyze_behavior.py", "--config", str(self.config), "--run", "r1", "--live", env=self.live_env())
        self.assertIn("add_parameter on `create_note`", self.report())

    def test_detectors_alone_call_no_model(self) -> None:
        self.live("--run-id", "r1")
        calls_before = self.marker.read_text().count("\n")
        done = run_script("analyze_behavior.py", "--config", str(self.config), "--run", "r1", env=self.live_env())
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.marker.read_text().count("\n"), calls_before)

    def test_trend_has_one_line_per_round(self) -> None:
        self.live("--run-id", "r1")
        self.live("--run-id", "r2")
        run_script("report_golden.py", "--config", str(self.config), "--trend")
        trend = (self.dir / "kit/.mcp-eval/runs/trend.md").read_text(encoding="utf-8")
        self.assertIn("| r1 |", trend)
        self.assertIn("| r2 |", trend)


class StorageNoticeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="mcp-kit-storage-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.results = self.dir / ".mcp-eval" / "runs"
        self.results.mkdir(parents=True)
        (self.results / "x.txt").write_text("data")

    def git_init(self) -> None:
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)

    def test_without_git_it_only_says_where_the_data_is(self) -> None:
        self.assertEqual(git_ignore_state(self.results), "no-git")
        notice = storage_notice(self.results)
        self.assertIn(str(self.results), notice)
        self.assertNotIn("Git", notice)

    def test_warns_when_git_would_pick_the_runs_up(self) -> None:
        self.git_init()
        self.assertEqual(git_ignore_state(self.results), "not-ignored")
        self.assertIn("does NOT ignore", storage_notice(self.results))

    def test_stays_calm_when_the_folder_is_ignored(self) -> None:
        self.git_init()
        (self.dir / ".gitignore").write_text(".mcp-eval/\n")
        self.assertEqual(git_ignore_state(self.results), "ignored")
        self.assertIn("ignored by Git", storage_notice(self.results))


class DiscoveryTests(unittest.TestCase):
    def project(self, files: dict[str, str]) -> Path:
        root = Path(tempfile.mkdtemp(prefix="mcp-kit-discover-"))
        self.addCleanup(shutil.rmtree, root, True)
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return root

    def test_reads_a_node_project(self) -> None:
        root = self.project({
            "package.json": json.dumps({"devDependencies": {"vitest": "1"}, "dependencies": {"@modelcontextprotocol/sdk": "1", "next-auth": "4"}}),
            "src/server.ts": "const s = new McpServer({});",
            "src/__fixtures__/a.json": "{}",
            ".github/workflows/ci.yml": "on: push",
        })
        found = discover(root)
        self.assertEqual(found["test_runners"], ["vitest"])
        self.assertEqual(found["gate_snippets"], ["describe.skipIf"])
        self.assertEqual(found["mcp_dependencies"], ["@modelcontextprotocol/sdk"])
        self.assertEqual(found["mcp_server_code"], ["src/server.ts"])
        self.assertEqual(found["auth_dependencies"], ["next-auth"])
        self.assertEqual(found["ci"], [".github/workflows/ci.yml"])
        self.assertEqual(found["suggested_target"], "src/__fixtures__/mcp-golden")

    def test_reads_a_python_project(self) -> None:
        root = self.project({"pyproject.toml": '[tool.pytest.ini_options]\ndependencies = ["fastmcp>=2"]\n', "app/main.py": "mcp = FastMCP('x')", "tests/test_a.py": ""})
        found = discover(root)
        self.assertIn("pytest", found["test_runners"])
        self.assertEqual(found["suggested_target"], "tests/mcp-golden")

    def test_empty_project_falls_back_to_a_tools_folder(self) -> None:
        self.assertEqual(discover(self.project({"README.md": "hi"}))["suggested_target"], "tools/mcp-eval")

    def test_prefers_the_folder_next_to_the_server(self) -> None:
        target = suggest_target(["packages/mcp/src/server.ts"], ["apps/web/e2e/fixtures", "packages/mcp/src/__fixtures__"], ["apps/web/tests"])
        self.assertEqual(target, "packages/mcp/src/__fixtures__/mcp-golden")

    def test_only_reads(self) -> None:
        root = self.project({"package.json": "{}"})
        before = sorted(path.name for path in root.rglob("*"))
        discover(root)
        self.assertEqual(sorted(path.name for path in root.rglob("*")), before)


class MetricsTests(unittest.TestCase):
    def test_flags_output_tokens_too_low_for_the_arguments(self) -> None:
        parsed = {
            "calls": [{"tool": "write", "error": False, "out_chars": 1, "in_chars": 16000, "ms": 10, "images": 0}],
            "result": {"subtype": "success", "usage": {"output_tokens": 180}},
            "init": {"mcp_servers": [{"name": "s", "status": "connected"}]},
            "other_tools": {},
        }
        self.assertTrue(any("implausibly" in alert for alert in build_metrics(parsed, "s")["alerts"]))

    def test_unfinished_transcript_is_flagged(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as file:
            file.write('{"type":"system","subtype":"init","mcp_servers":[{"name":"s","status":"connected"}]}\nnot json\n')
        self.addCleanup(os.unlink, file.name)
        metrics = build_metrics(parse_transcript(Path(file.name), "s"), "s")
        self.assertFalse(metrics["ok"])
        self.assertTrue(any("result" in alert for alert in metrics["alerts"]))


class CaseTests(unittest.TestCase):
    def test_case_without_any_decision_is_invalid(self) -> None:
        self.assertTrue(validate_case({"id": "a", "prompt": "b"}))

    def test_unknown_check_is_invalid(self) -> None:
        self.assertTrue(validate_case({"id": "a", "prompt": "b", "checks": [{"type": "nope"}]}))

    def test_broken_regex_is_invalid(self) -> None:
        self.assertTrue(validate_case({"id": "a", "prompt": "b", "checks": [{"type": "final_matches", "regex": "("}]}))

    def test_example_cases_are_valid(self) -> None:
        for file in (KIT / "golden" / "cases").glob("*.json"):
            self.assertEqual(validate_case(json.loads(file.read_text(encoding="utf-8"))), [], file.name)


class IsolatedModeTests(unittest.TestCase):
    def test_every_script_runs_in_python_isolated_mode_from_any_folder(self) -> None:
        for name in ("run_golden.py", "grade_golden.py", "report_golden.py", "analyze_behavior.py", "check_contract.py", "check_auth.py", "discover_project.py", "init_kit.py"):
            done = subprocess.run([sys.executable, "-B", "-I", str(SCRIPTS / name), "--help"], cwd=tempfile.gettempdir(), capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, f"{name}: {done.stderr[-200:]}")


class DemoGapTests(unittest.TestCase):
    def tools(self, *flags: str) -> dict:
        request = '{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n'
        done = subprocess.run([sys.executable, "-B", str(SCRIPTS / "demo_server.py"), "--stdio", *flags], input=request, capture_output=True, text=True)
        return {tool["name"]: tool for tool in json.loads(done.stdout)["result"]["tools"]}

    def test_the_deliberate_gap_is_there_and_the_flag_closes_it(self) -> None:
        self.assertNotIn("tag", self.tools()["list_notes"]["inputSchema"]["properties"])
        self.assertIn("tag", self.tools("--with-tag-filter")["list_notes"]["inputSchema"]["properties"])


class ContractTests(unittest.TestCase):
    TOOL = {"name": "search", "description": "Searches items by word and returns the id and title of each one.", "inputSchema": {"type": "object", "properties": {"q": {"type": "string", "description": "A word."}}}}

    def findings(self, init: dict, tools: list[dict]) -> dict:
        return {finding.rule: finding for finding in inspect_contract(init, tools, DEFAULTS["limits"])}

    def limits_with(self, value: str | None) -> dict:
        config = {"limits": DEFAULTS["limits"], "agent": {"env": {LIMIT_ENV: value} if value else {}}}
        return effective_limits(config, {})

    def test_instructions_over_the_limit_fail_and_name_what_is_lost(self) -> None:
        text = "a" * 4100 + "\n## Design\nrules"
        finding = self.findings({"instructions": text}, [self.TOOL])["instructions-too-long"]
        self.assertEqual(finding.severity, "ERROR")
        self.assertIn("## Design", finding.message)

    def test_over_the_limit_warns_of_the_cut_and_suggests_raising_it(self) -> None:
        message = self.findings({"instructions": "a" * 8000}, [self.TOOL])["instructions-too-long"].message
        self.assertIn("will cut", message)
        self.assertIn(f"{LIMIT_ENV}=16384", message, "16384 raises the short limit without lowering the long one")

    def test_suggestion_covers_text_bigger_than_the_search_limit(self) -> None:
        message = self.findings({"instructions": "a" * 20000}, [self.TOOL])["instructions-too-long"].message
        self.assertIn(f"{LIMIT_ENV}=20480", message)

    def test_raised_limit_passes_but_keeps_warning_about_other_people(self) -> None:
        rules = {f.rule: f for f in inspect_contract({"instructions": "a" * 8000}, [self.TOOL], self.limits_with("16384"))}
        self.assertNotIn("instructions-too-long", rules)
        self.assertEqual(rules["instructions-need-raised-limit"].severity, "WARN")
        self.assertIn("without that variable", rules["instructions-need-raised-limit"].message)

    def test_raised_limit_still_too_small_fails(self) -> None:
        rules = {f.rule for f in inspect_contract({"instructions": "a" * 9000}, [self.TOOL], self.limits_with("8192"))}
        self.assertIn("instructions-too-long", rules)

    def test_raised_limit_below_the_search_limit_warns(self) -> None:
        rules = {f.rule for f in inspect_contract({"instructions": "a" * 8000}, [self.TOOL], self.limits_with("8192"))}
        self.assertIn("raised-limit-lowers-search", rules)

    def test_one_number_replaces_both_limits(self) -> None:
        limits = self.limits_with("8192")
        self.assertEqual((limits["instructions_chars"], limits["tool_description_chars"]), (8192, 8192))

    def test_run_warns_before_spending_only_when_there_is_a_cut(self) -> None:
        self.assertIn(LIMIT_ENV, cut_warning(8000, self.limits_with(None)))
        self.assertIsNone(cut_warning(8000, self.limits_with("16384")))
        self.assertIsNone(cut_warning(4096, self.limits_with(None)))

    def test_instructions_within_the_limit_pass(self) -> None:
        self.assertNotIn("instructions-too-long", self.findings({"instructions": "a" * 4096}, [self.TOOL]))

    def test_output_schema_warns(self) -> None:
        self.assertIn("output-schema", self.findings({"instructions": "x"}, [{**self.TOOL, "outputSchema": {"type": "object"}}]))

    def test_undocumented_parameter_warns(self) -> None:
        tool = {**self.TOOL, "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}}}
        self.assertIn("param-undocumented", self.findings({"instructions": "x"}, [tool]))

    def test_snapshot_diff_names_the_change(self) -> None:
        old = contract_snapshot({"instructions": "x"}, [self.TOOL])
        new = contract_snapshot({"instructions": "y"}, [{**self.TOOL, "description": "other"}, {**self.TOOL, "name": "get"}])
        changes = diff_snapshot(old, new)
        self.assertIn("instructions changed", changes)
        self.assertIn("new tool: get", changes)
        self.assertIn("changed tool: search", changes)


class LaxAuthorize(BaseHTTPRequestHandler):
    """Lax server: sends the person to login even without PKCE."""

    def do_GET(self) -> None:
        self.send_response(302)
        self.send_header("Location", "/login")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_: object) -> None:
        """Silence the default log."""


class AuthorizeProbeTests(unittest.TestCase):
    def probe(self, handler: type[BaseHTTPRequestHandler]) -> Report:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        report = Report()
        with contextlib.redirect_stdout(io.StringIO()):
            check_authorize_rejects(report, f"http://127.0.0.1:{server.server_port}/oauth/authorize", "http://app/mcp", "client", "http://localhost/callback")
        return report

    def test_authorize_that_skips_pkce_fails(self) -> None:
        self.assertEqual(self.probe(LaxAuthorize).failed, 2)

    def test_authorize_that_refuses_passes(self) -> None:
        class Strict(LaxAuthorize):
            def do_GET(self) -> None:
                self.send_response(302)
                self.send_header("Location", "http://localhost/callback?error=invalid_request")
                self.send_header("Content-Length", "0")
                self.end_headers()

        self.assertEqual(self.probe(Strict).failed, 0)


class AuthTests(unittest.TestCase):
    def start(self, *flags: str) -> str:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        process = subprocess.Popen([sys.executable, "-B", str(SCRIPTS / "demo_server.py"), "--http", "--port", str(port), *flags], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        for _ in range(50):
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    return f"http://127.0.0.1:{port}/mcp"
            time.sleep(0.05)
        self.fail("the demo server did not start")

    def test_conforming_discovery_passes(self) -> None:
        url = self.start("--oauth-metadata", "--token", "dev")
        done = run_script("check_auth.py", "--url", url, "--token", "dev")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("auth passed", done.stdout)

    def test_server_without_oauth_metadata_fails(self) -> None:
        url = self.start("--token", "dev")
        done = run_script("check_auth.py", "--url", url)
        self.assertEqual(done.returncode, 1)
        self.assertIn("resource-metadata", done.stdout)

    def test_open_server_fails_the_challenge(self) -> None:
        done = run_script("check_auth.py", "--url", self.start())
        self.assertEqual(done.returncode, 1)
        self.assertIn("challenge-401", done.stdout)


class InitKitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="mcp-kit-init-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.target = self.dir / "tools" / "mcp-eval"

    def init(self, *flags: str) -> subprocess.CompletedProcess:
        return run_script("init_kit.py", "--target", str(self.target), *flags)

    def test_copies_a_project_that_works_on_its_own(self) -> None:
        self.assertEqual(self.init().returncode, 0)
        for name in ("README.md", "eval.config.json", "project-profile.md", ".gitignore", "golden/cases/read-detail.json", "scripts/run_golden.py"):
            self.assertTrue((self.target / name).exists(), name)
        done = subprocess.run([sys.executable, "-B", "scripts/check_contract.py", "--config", "eval.config.json"], cwd=self.target, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_the_copied_engine_runs_from_the_project_alone(self) -> None:
        # Regression: the shared modules live in scripts/kitlib, so the copy must bring them along.
        self.init()
        self.assertTrue((self.target / "scripts/kitlib/golden_common.py").exists())
        for script, expected in (("run_golden.py", "Plan (nothing was run)"), ("check_contract.py", "contract passed")):
            done = subprocess.run([sys.executable, "-B", "-I", f"scripts/{script}", "--config", "eval.config.json"], cwd=self.target, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertIn(expected, done.stdout)

    def test_a_stock_gitignore_keeps_every_kit_file_versionable(self) -> None:
        # Regression: shared modules in a folder named lib/ vanished from the commit and broke CI.
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)
        (self.dir / ".gitignore").write_text("build/\ndist/\nlib/\nlib64/\nvar/\nenv/\nvenv/\n", encoding="utf-8")
        self.init()
        files = "\n".join(str(path) for path in self.target.rglob("*") if path.is_file())
        done = subprocess.run(["git", "check-ignore", "--stdin"], cwd=self.dir, input=files, capture_output=True, text=True)
        self.assertEqual(done.stdout, "")

    def test_the_project_gets_the_engine_without_its_test_suite(self) -> None:
        self.assertNotIn("test_kit", self.init().stdout)
        self.assertEqual(list(self.target.rglob("test_*.py")), [])

    def test_update_brings_the_shared_modules_too(self) -> None:
        self.init()
        shutil.rmtree(self.target / "scripts/kitlib")
        self.assertEqual(self.init("--update-scripts").returncode, 0)
        self.assertTrue((self.target / "scripts/kitlib/mcp_client.py").exists())

    def test_inside_git_it_asks_for_a_decision(self) -> None:
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)
        self.assertIn("not ignored", self.init().stdout)

    def test_ignore_locally_leaves_the_repository_untouched(self) -> None:
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)
        done = self.init("--ignore-locally")
        self.assertIn(".git/info/exclude", done.stdout)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.dir, capture_output=True, text=True)
        self.assertEqual(status.stdout, "", "the kit must not appear as a change")

    def test_ignore_locally_without_git_says_so(self) -> None:
        self.assertIn("not a Git repository", self.init("--ignore-locally").stdout)

    def test_refuses_to_overwrite_an_existing_kit(self) -> None:
        self.init()
        done = self.init()
        self.assertEqual(done.returncode, 2)
        self.assertIn("not empty", done.stderr)

    def test_update_refreshes_the_engine_and_keeps_the_cases(self) -> None:
        self.init()
        case = self.target / "golden/cases/read-detail.json"
        case.write_text('{"edited": true}')
        (self.target / "scripts/run_golden.py").write_text("# old")
        self.assertEqual(self.init("--update-scripts").returncode, 0)
        self.assertEqual(case.read_text(), '{"edited": true}')
        self.assertIn("Golden lane", (self.target / "scripts/run_golden.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
