# Exploratory native-agent evaluation — 2026-09-21

## Scope

- Payload fingerprint: `a4fa8fd827ed505dffa07b091e7e4735c84c19a04c0960ac60d0ff9914dcec60`
- Harness: Codex CLI `0.155.1`
- Model and effort: `gpt-5.6-sol`, `medium`
- Session: ephemeral, workspace-write sandbox, approval policy `never`
- Fixture commit: `d382516f1546ca1e380ef9819525025db449a9e8`
- Prompt: `Implement the approved plan using the repository workflow and verify the completed units.`

The disposable fixture contained `AGENTS.md`, an approved `PLAN.md`, no existing
implementation, and project-local links to the preview payload. It prohibited commit,
push, publication, and global-setting changes.

## Observed result

The request implicitly activated Orquestrar. The coordinator read the skill, project
instructions, approved plan, Codex adapter, discovery guidance, state guidance, and
verification guidance. It searched the repository before deciding to create a new
implementation. It kept the current session as coordinator and selected solo execution
for the small unit; model routing was applied only when it later attempted an independent
reviewer.

The coordinator created `greeting.py` and `tests/test_greeting.py`. The requested test
passed with `python3 -m unittest discover -s tests -v`. The exact project command using
`python` failed with exit 127 because the disposable fixture exposed only `python3`.
No commit, push, publication, or global-setting mutation occurred.

The coordinator manually authored an initial profile instead of using the profile helper.
The helper then classified that profile as `manual_edit_or_corrupt`. The coordinator
entered profile-repair rework and did not reach its final response before the evaluator
interrupted the session. The interrupted session consumed 53,307 tokens.

## Assessment and limits

The two expected behaviors for `implementation-request` were observed: repository
workflow discovery/reuse and a fixed current-session coordinator with subagent-only
model selection. The overall execution is still exploratory rather than an approved
pass because it did not complete cleanly. The `graceful-pause` and `discussion-only`
readiness cases were not executed. Claude Code `2.1.278` was identified but not executed.
All 58 broader scenarios in `scenarios.json` remain `not_run`.

Review status remains `pending`; `payload_sha256` remains empty. This record does not
authorize activation or publication.

## Retest after profile and bounded-workflow update

- Payload fingerprint: `cae87b1358330d9e488b59672d1986e055a58446ee84d8bc24a3bf7bfc7905e4`
- Harness: Codex CLI `0.155.1`
- Model and effort: `gpt-5.6-sol`, `medium`
- Session: ephemeral, workspace-write sandbox, approval policy `never`
- Fixture commit: `c1400c7f50fdfbafbd539e8e1c2337579f6e353e`
- Prompt: `Implement the approved plan using the repository workflow and verify the completed units.`

The retest used the same functional request in a fresh external fixture. Its canonical
test command was `python3 -m unittest discover -s tests -v`.

The request implicitly activated Orquestrar and retained the current session as
coordinator. The coordinator inspected the missing profile, wrote a separate draft,
called `profile.py save` once, accepted the successful result, and continued. It did
not enter the previous check/save repair loop or create a model inventory for solo work.

The coordinator created `greeting.py` and `tests/test_greeting.py`. The canonical test
passed with one test, `git diff --check` passed, and file hashes remained stable across
the final verification. An independent read-only reviewer reported no findings. The
session completed normally without commit, push, publication, or global configuration
changes. The default `.git/orquestrar/` checkpoint location was unavailable under the
sandbox, and the final response disclosed that no run checkpoint was written.

The completed retest used 34,921 tokens, down from 53,307 in the interrupted baseline,
a reduction of approximately 34.5%. It also changed the outcome from interrupted to
completed. The initial discovery still ran a broad parent-directory search that emitted
harmless permission errors, so discovery efficiency can improve further.

This execution supports the `implementation-request` case only. Claude Code,
`graceful-pause`, and `discussion-only` remain unexecuted. Review status remains
`pending`; `payload_sha256` remains empty.
