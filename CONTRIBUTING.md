# Contributing

Read [Setup](docs/SETUP.md), [Architecture](docs/ARCHITECTURE.md), and [AGENTS.md](AGENTS.md).
Use the Makefile task menu (native Python/Node commands; pnpm aliases are optional) and keep all maintained content in English. Use the scaffold command for new skills.

Open a focused pull request with a Conventional Commit title, the affected skills, actual
test evidence, and known limitations. Prefer one behavior change per PR. Run `make check`.
CI uses the PR title as the intended squash commit, so use squash merges and retain that title.

Changes to shipped instructions, references, assets, or scripts need an appropriate version
intent. `docs:` is for non-behavioral documentation, not a shortcut around releases.
Do not edit generated release configuration or versions manually during ordinary development.
Use `make release-sync` to register configuration changes without resetting existing versions.

Update evaluation cases and actual evidence when skill content changes. The recorded
fingerprint must identify the reviewed payload. Do not mark a fabricated review as approved.
Maintenance unit tests use clearly labeled synthetic approvals only inside temporary fixtures.

Runtime code belongs inside its skill. Test harnesses, large fixtures, and development
dependencies stay outside the payload. Never commit secrets, proprietary examples, or
third-party code without an appropriate license. See [Security](SECURITY.md) for reporting.

For Codex/Claude Code, follow [Agent workflow](docs/AGENT_WORKFLOW.md). Update shared
policy only in AGENTS.md. Run `make test-launchers` after changing command/agent wiring.
