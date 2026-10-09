---
name: remis-native-batch
description: Submit and retrieve native OpenAI Batch localization jobs through Remis, including restart recovery and frozen terminology. Use only when advanced users explicitly request asynchronous Batch translation that can finish while their computer is off. Model review is a separately disabled developer experiment.
---

# Remis Native Batch

Remis executes and persists the job; this Skill operates its Agent API. Read the
[native workflow guide](../../../docs/zh/developer/native-openai-localization-trials.md)
for translation payloads. Model review is disabled by default; only an explicitly
requested developer experiment with supported=true may use the quality API guide.
Do not recommend model review as an ordinary Batch translation step.

1. Discover the active localhost backend, call `/api/agent/preflight`, and inspect capabilities.
   This advanced API has no GUI. A version label alone cannot prove capability;
   verify batch_jobs.supported=true on the actual backend. Unfinished immediate
   trials and model reviews require separate explicit developer opt-in.
   Prefer existing jobs before creating a plan: translation uses `/api/agent/batch-jobs`, review uses
   `/api/agent/localization-reviews`, with project and pagination filters from the API guide.
2. Use registered project source files and a frozen `term_release_id`. Record the source snapshot,
   dictionary maturity, exact native model ID, `reasoning.mode` and `reasoning.effort` separately.
   Pro is an execution mode; highest effort is `max`, not an implied property of Pro.
3. Create the appropriate plan with `execution_mode: batch`. Show its concrete scope and carry
   forward existing user authorization. A named-model translation/review request authorizes that
   scoped paid run; do not ask for the same authorization again.
4. Submit through Remis with `approved: true` and a stable business idempotency key. Save the returned
   local job ID, remote Batch ID, input file ID, app-data directory and backend in a local handoff record.
   Confirm cloud acceptance only after the durable remote ID and submitted state are present.
5. After reboot, reuse the same Remis storage, query the saved job and refresh it. Collect/download
   results before relying on local review artifacts. No new paid submission is needed for retrieval.
   Expired, cancelled or failed batches can contain paid partial results; retrieve available output
   and error files and keep missing requests explicitly unreviewed. Never treat a terminal status as
   evidence that every request succeeded or that no results exist.
6. Inspect parser, entry mapping and validation diagnostics. Report returned candidates, accepted
   entries and applicable files separately. A review report is not a replacement translation output.

Never read or copy credential files; reuse Remis Settings internally. Do not blindly resubmit
`submission_unknown`: reconcile only a verified remote job with matching persisted request IDs.
Do not delete the active worktree, app-data, source, translation outputs or artifacts. Applying,
exporting, installing and publishing are separate actions outside a Batch submission by itself.

Batch runs remotely after acceptance; ordinary immediate requests do not have this shutdown guarantee.
Persist raw responses and local downloads, not just a link to the provider dashboard.
