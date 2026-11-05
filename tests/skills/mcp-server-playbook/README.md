# MCP Server Playbook verification

`test_kit.py` covers the scripts with a fake `claude`, so it spends nothing. Run it with
`make test-skills NAME=mcp-server-playbook`. It lives here, not in the payload: a project
that copies the kit receives the engine, not the engine's test suite.

`catalog/mcp-server-playbook.json` registers every script at the top of `scripts/`. Its
smoke tests run against a copied skill, without network or model. Shared modules live in
`scripts/kitlib/`; they have no command line, so they are not entrypoints.

Behavioral evidence comes from real agent runs recorded in `evaluation-*.md` and summarized
in [evals.json](evals.json). Those records are sanitized: this repository is public, so they
name no private project. Any payload change makes the review stale; set `review.status` to
`approved` only after a real human review of the current fingerprint.
