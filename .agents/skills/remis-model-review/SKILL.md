---
name: remis-model-review
description: Disabled developer experiment. Load only after an explicit experimental workflow request and verification that live localization_reviews capabilities report supported=true. Never propose or enable this workflow for ordinary users.
---

# Remis Model Review

This workflow is disabled by default. Check `/api/agent/capabilities` first and stop
when `supported` is false. Do not enable environment flags automatically. The developer
must explicitly opt in and restart Remis; paid operations still require authorization.
See [experimental API policy](../../../docs/zh/developer/advanced-agent-policy.md).

Read [the quality API guide](../../../docs/zh/developer/localization-quality-agent-api.md).
Use `/api/agent/localization-reviews`, not proofreading save as a bulk translation shortcut.
This Skill reviews retained candidates; it does not authorize overwriting them or publishing a Mod.

1. Preflight the active localhost Remis and check review capabilities. Select the completed source
   translation job, retained candidate entry IDs and a frozen dictionary. Optionally select an official
   reference project; references must match the same ID and English, and English governs meaning.
   First list `/api/agent/localization-reviews?project_id=PROJECT_ID&limit=50&offset=0` and inspect matching
   jobs. Recover their saved artifacts rather than submitting a duplicate paid review.
2. Choose the exact native model ID, execution mode, Pro mode and effort explicitly. The current
   default is `gpt-6-luna`, `pro + max`, groups of up to 20; preserve the user's choice instead of treating
   this default as a permanent rule. For long Pro evaluation use `execution_mode: background`: it calls
   ordinary `/v1/responses` with `background=true, store=true`, persists each response ID and polls with GET.
   This is ordinary pricing, not Batch. Preserve a user's ordinary-interface choice; do not switch to Batch.
   `immediate` keeps a foreground connection; `batch` uses the separate Files + Batches workflow.
3. Create and inspect a review plan. Record scopes and artifact IDs. Carry existing paid-review
   authorization forward; use a stable idempotency key when starting the job.
4. Send complete English, original candidate, matched reference, relevant terminology and available
   context. Never mask semantic game tokens. Do not send prior judge verdicts or a known-error answer
   key when measuring independent detection.
5. The model returns only problematic short labels, brief explanations, severity/confidence and
   minimal find/replace edits. Do not demand copied paragraphs, complete rewrites or pass records for
   every entry. Remis keeps the full original inputs and reconstructs proposed text locally.
6. Read raw responses and the report. Separate remote failure, empty output, parser failure, foreign
   labels, unreviewed entries, reported issues and no-reported-issue entries. Silence is not certification.
   Check whether proposed edits match uniquely and preserve structure; retain rejected suggestions too.

There is no automatic paid retry or automatic application. Existing candidate translations remain
unchanged. For ordinary jobs, each response is saved, but an interrupted in-flight response may be unknown;
inspect `saved_results` and do not blindly repeat charges. Batch recovery follows the native Batch guide.
For ordinary background review, reuse the persisted job and POST `/{job_id}/refresh`; it retrieves known
response IDs and never creates new responses. Terminal responses are cached locally. Unknown acceptance
can only be reconciled through `/{job_id}/responses/reconcile` with exact persisted metadata and approval.
Missing IDs are not an invitation to resubmit; distinguish `not_submitted`, unknown and accepted requests.
Check `shutdown_recovery_ready=true` before promising shutdown recovery. Interrupted dispatch is surfaced
and never silently continued; fully persisted accepted IDs let Remis derive dispatch completion safely.

For an evaluation, compare findings with a withheld issue inventory only after the run. Count omissions
and false positives as well as detections. User spot checks can complement automatic review without
requiring them to read every string. Keep the model's confidence qualitative, not a claimed accuracy.
