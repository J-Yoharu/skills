# MCP golden kit

Tests whether a model can really use this MCP server. Cases are in `golden/cases/`, the configuration is in `eval.config.json`, and this application's context is in `project-profile.md`.

```bash
python3 -B scripts/check_contract.py --config eval.config.json    # free
python3 -B scripts/run_golden.py --config eval.config.json        # plan only, free
MCP_EVAL_LIVE=1 python3 -B scripts/run_golden.py --config eval.config.json --live --run-id r1
python3 -B scripts/grade_golden.py prepare --config eval.config.json --run r1
MCP_EVAL_LIVE=1 python3 -B scripts/grade_golden.py judge --config eval.config.json --run r1 --live
python3 -B scripts/report_golden.py --config eval.config.json --run r1   # from the second round on, add --baseline <earlier run>
```

Runs with `--live` spend money, so show the plan to the person first. Results stay in `.mcp-eval/runs/`.

## Reporting a round

When someone asks how a round went, run `report_golden.py` and answer with what it prints, in the person's language:

1. The summary table, with each mark next to its number: ✔ clean, ◐ partial, ✘ failed, by model.
2. The line with how many cases and repetitions, and the warning if grading did not run.
3. The comparison with the previous round, when there is a baseline.
4. Up to 3 possible improvements, each with its evidence in one sentence.
5. Where the report is, and an offer to go into detail.

Keep it to that. Copy the numbers instead of counting them. The details stay in `report.md` until the person asks for them.
