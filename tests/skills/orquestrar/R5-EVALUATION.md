# R5 evaluation additions — pending native execution

Keep the existing `implementation-request` ID and prompt. These observations refine
its acceptance; they do not create a different fixture or authorize activation.
Keep historical eval records and the current approval fingerprint unchanged/pending.

## Same implementation-request, stronger observation

Check the trace and actual files, not only the final message:

- The current chat coordinates and loads task/repository facts before conditional
  references. It does not select a new model for itself or inventory models for solo work.
- Before the first product edit, there is a successful validated checkpoint save
  and read-back. A later file existence check is not evidence of this order.
- Current state passes `verify.py checkpoint-read --strict`; the final result is
  completed, selected units have coherent acceptance/evidence, and no completed
  reviewer remains in active arrays. State validity is necessary, not sufficient.
- Save errors must halt the save operation and cannot produce a successful receipt.
  A token conflict is reconciled, not overwritten with an automatically refreshed token.
- The actual reviewer sees scoped requirements/diff and test evidence. Policy-only
  lookup does not pretend model availability or effectiveness. Missing reviewer
  rollout/model metadata stays explicitly unknown, not confirmed by a preset.
- Evidence is accepted once tests/review are resolved and candidate inputs are
  unchanged. There is no optional cleanup that manufactures another test cycle.
- No commit, push, publication or global-setting change by the tested agent.

No new hints belong in the fixture or user prompt. Compare native outcomes with
quality requirements unchanged. State the exact tested fingerprint, CLI version,
requested/effective settings where observed, elapsed time and usage scope.

## Separate cases, not claimed by implementation-request

| Case | Decision and artifact to observe | R5 status |
| --- | --- | --- |
| graceful-pause then new-session resume | Freeze active IDs; finish/review only those; durable paused state; new context reads the same schema, reconciles sources/writers and resumes only on request | not_run natively |
| unknown live worker after interruption | No second writer until confirmed quiescent or safely isolated; retain unresolved ID | not_run natively |
| multiple repositories with dependency | Integrated status plus actual contract available in consumer checkout; graph readiness alone is insufficient | not_run natively |
| source revision changes after verification | Reopen affected acceptance/evidence, preserve unaffected work; do not replay the entire run | not_run natively |
| failing save / stale token | Preserve old state before replace; report uncertain post-replace failure; no blind retry or fabricated receipt | tested as local CLI/storage failures, not native model decisions |
| invalid legacy checkpoint | Preserve it, reconcile live facts, use a new explicit canonical path if needed; no guessed status migration | tested as rejection only; native recovery not_run |
| large dependency outline | Correct ready frontier with bounded summaries; completed history remains on disk | 1,000-unit storage test only; hours-long native orchestration not_run |
| discussion-only / Claude Code | No accidental activation / same operational guarantees in Claude | not_run natively |

A repeated same-session author walkthrough is not an independent agent review.
Approval requires the repository's actual evaluation/review process; unit counts
and fingerprints alone never constitute that approval.
