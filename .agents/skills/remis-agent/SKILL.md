---
name: remis-agent
description: Operate Remis through its localhost Agent API to inspect or import Paradox mods, plan and monitor localization, validate or repair results, and export safely. Use when a user asks Codex to install, check, or control Remis; localize a mod; preserve game syntax; inspect failed entries; or prepare an installable localization package.
---

# Remis Agent Operator

Treat Remis as the execution plane. Use Codex to understand intent, inspect the
workspace, explain progress, and request approvals; use the Remis API for all
localization state changes.

## Establish the local boundary

1. Work only with the official repository or an installed Remis application.
2. Start the installed application, or run
   `scripts\developer_tools\windows\run-dev.bat` from the root of a development
   checkout. Respect the Python/Conda environment chosen by that launcher.
3. Verify `GET http://127.0.0.1:1453/api/health`.
4. Before every workflow, call
   `GET http://127.0.0.1:1453/api/agent/preflight`. Report whether the installed
   version is behind the latest GitHub Release. If GitHub cannot be reached,
   report that the check failed instead of claiming the version is current.
5. Read `GET http://127.0.0.1:1453/api/agent/capabilities` before choosing a
   game, language, provider, model, or action.
6. On first setup, inspect `provider_setup` from preflight. If no cloud
   credential is configured, immediately guide the user to Remis Settings >
   API Settings before planning cloud translation. Offer to explain that an API
   key is a secret provider credential tied to authentication and often
   billing. Never ask the user to paste the key into chat.
7. A deliberately selected local provider may be keyless; verify its local
   connection instead of demanding a cloud key.
8. Never read, print, transmit, or ask Remis to return a provider API key.
9. Never expose Remis beyond localhost.

If the service or capability endpoint is unavailable, diagnose that boundary
before touching a mod.

## Follow the governed workflow

Use this sequence:

1. Run the preflight release and provider-setup checks.
2. Inspect the mod folder with `POST /api/agent/projects/inspect`.
3. If needed, create an import plan with `POST /api/agent/projects/plan`.
4. Show the plan, source path, detected game evidence, and copy/reference mode.
5. Obtain explicit user approval, then call `POST /api/agent/projects`.
6. Create a translation plan with `POST /api/agent/jobs/plan`.
7. Show target languages, provider/model, estimated risk, and whether model
   calls can incur cost.
8. For a zero-cost readiness check, set `dry_run: true`. Otherwise obtain
   explicit approval before `POST /api/agent/jobs`.
9. Poll `GET /api/agent/jobs/{job_id}` until a terminal or actionable state.
10. Inspect `GET /api/agent/jobs/{job_id}/validation`.
11. Retry deterministic failures first. Request approval before model-backed
    repair with `POST /api/agent/jobs/{job_id}/repair`.
12. Preview export with `GET /api/agent/jobs/{job_id}/export-preview`.
13. Show overwrite and deployment risks. Obtain explicit approval before
    `POST /api/agent/jobs/{job_id}/approve-export`.

Read [references/api-workflow.md](references/api-workflow.md) for payloads,
response fields, status handling, and error semantics.

## Respect approval gates

Stop and ask before:

- starting a job that can spend model credits;
- running model-backed repair;
- exporting or deploying files;
- overwriting an existing localization folder.

Approval is specific to the displayed plan or preview. Do not reuse a past
approval for a changed path, provider, model, target language, or overwrite.

## Report progress without guessing

Use the API response as the source of truth. Report:

- project and job identifiers;
- normalized status and stage;
- completed and total files;
- validation errors, warnings, and human-review items;
- `allowed_actions`;
- output paths only after Remis reports them.

Do not claim that a task completed because a request was accepted. Do not
invent percentages, translated entry counts, validation results, or exports.

## Handle failure safely

- Treat `409 approval_required` as a prompt to show the plan and ask the user.
- Treat `409 overwrite_confirmation_required` as a separate overwrite gate.
- Treat `404` as stale or unknown state; re-list projects or inspect registry
  recovery information before retrying.
- Keep ambiguous translations for human review.
- Never bypass path validation, write directly into a game directory, or edit
  generated localization files behind Remis.
- If pause or cancel is not listed by the capabilities endpoint, say it is not
  safely supported in this build.

## Finish with an audit-ready summary

State what Remis actually did, what validation found, what remains for human
review, and whether any approval is still required. Keep provider secrets and
unrelated local paths out of the summary.
