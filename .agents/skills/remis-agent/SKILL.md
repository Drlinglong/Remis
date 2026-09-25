---
name: remis-agent
description: Operate Remis through its localhost Agent API to inspect or import supported game mods, plan and monitor localization, validate or repair results, and prepare outputs safely. Use when a user asks Codex to install, check, or control Remis; localize a mod; preserve game syntax; inspect failed entries; or prepare an installable localization package.
---

# Remis Agent Operator

Treat Remis as the execution plane. Use Codex to understand intent, inspect the
workspace, explain progress, and apply the user's authorization. Use Remis APIs
for bulk translation and managed workflow state changes. Reading source files,
translations and Mod metadata directly is allowed for inspection, comparison,
quality discussion and sampling; never read provider credential files.

For explicitly approved corrections to a few identified entries, prefer the
Remis proofreading save workflow so the translation archive stays synchronized.
Direct targeted edits are also allowed when authorized: preserve keys, semantic
tokens, encoding and layout, verify the exact diff, and reconcile the reusable
baseline. If synchronization is unavailable, report that the file is corrected
but the baseline is not yet synchronized. Never expand this permission into
bulk file translation or direct database writes.

## Explain things to players first

Default to plain language for players and other nontechnical users, including
when reading technical API references or developer contracts. Lead with what
the user may experience, why it matters, and the next action. Do not paste raw
API fields or terms such as archive identity, baseline, or custom into the
initial explanation. Expand into implementation details when the user asks,
or when their question explicitly concerns development. Keep approval scope,
costs, data-loss risks and uncertainty clear in either style.

For shell translation, say: "We strongly recommend a separate project for this
language. Switching shell languages in one project can mix up saved translations,
so later Mod updates may reuse the wrong text and need extra corrections. You
can still continue with this project." Do not imply inevitable database damage.
For corrections awaiting baseline synchronization, say that the file is fixed
but the saved translations used by future updates have not yet been updated.

## Establish the local boundary

1. Work only with the official repository or an installed Remis application.
2. Start the installed application, or run
   `scripts\developer_tools\windows\run-dev.bat` from the root of a development
   checkout. Respect the Python/Conda environment chosen by that launcher.
   For API-only work use `run-dev.bat --backend-only`; it reuses a healthy
   matching backend and starts no frontend or visible console. Do not repeatedly
   launch the full desktop environment to recover only the backend.
3. Verify `GET http://127.0.0.1:1453/api/health`.
4. Before every workflow, call
   `GET http://127.0.0.1:1453/api/agent/preflight`. Report whether the installed
   version is behind the latest GitHub Release. If GitHub cannot be reached,
   report that the check failed instead of claiming the version is current.
5. Read `GET http://127.0.0.1:1453/api/agent/capabilities` before choosing a
   game, language, provider, model, or action. Use each game's `game_support`
   projection, then inspect a candidate source or project with the game-support
   endpoint before planning. Support is limited to recognized resource formats
   and does not mean in-game runtime verification.
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
2. Inspect the mod folder with `POST /api/agent/projects/inspect`, including
   `game_id`, `source_language`, and `game_version` when known. Read the returned
   `inspection.game_support` diagnostics and recognized-resource coverage. A scan-time
   `game_version` is only a discovery hint; it does not alter project settings
   or runtime workflow configuration.
3. If needed, create an import plan with `POST /api/agent/projects/plan`.
4. Show the plan, source path, detected game evidence, and copy/reference mode.
5. Obtain explicit user approval, then call `POST /api/agent/projects`.
6. Create a translation plan with `POST /api/agent/jobs/plan`.
   Choose `workflow: "initial"` or `workflow: "incremental"`; omitted means
   `initial`. Incremental work compares recognized entries, not mod version
   alone. Dry-run checks readiness only and does not calculate the incremental
   diff. Incremental checkpoint resume is unsupported; make a fresh plan for
   incremental work. Custom shell languages are limited to Paradox initial translation.
7. Select one explicit `translation_context_mode`: `none`, `glossaries`, or
   `archive`. Never reconstruct this choice from legacy booleans.
8. Read and show `context_readiness`, including the source-snapshot match,
   published release, project glossary entry count, and pending candidate count.
   Do not describe `archive` as active or complete unless `can_start` is true.
9. Show target languages, provider/model, estimated risk, and whether model
   calls can incur cost.
10. For a zero-cost readiness check, set `dry_run: true`. Otherwise obtain
   explicit approval before `POST /api/agent/jobs`.
11. Poll `GET /api/agent/jobs/{job_id}` until a terminal or actionable state.
12. Inspect `GET /api/agent/jobs/{job_id}/validation`.
13. Retry deterministic failures first. Request approval before model-backed
    repair with `POST /api/agent/jobs/{job_id}/repair`.
14. Preview export with `GET /api/agent/jobs/{job_id}/export-preview`.
15. Follow that game's preview contract. For a deployment-enabled game, show
    overwrite and deployment risks, then obtain explicit approval before
    `POST /api/agent/jobs/{job_id}/approve-export`. For manual-install outputs,
    show the package and manual installation boundary; do not call
    `approve-export`.

For Project Zomboid and RimWorld, source resources remain read-only and outputs
are separate manual-install packages, one package per target language. Their
export preview lists existing valid local packages and uses
`export_mode: "manual_install"`; `approve-export` does not install or deploy
them. Surviving Mars preview lists existing CSV files that pass the table
header and parser checks. Consult the dynamic
`game_support` contract for recognized formats and limitations; keep unknown
fields, conditions, inherited values and runtime-generated text visible for
human review.

For Surviving Mars, use `game_support.csv_contract` and the dynamic scan to
confirm recognized CSV resources, entry counts, diagnostics, and runtime status.
Only `ModItemLocTable` CSV with the declared five-column header is supported;
IDs stay exact strings and only `Translation` is writable. Initial translation,
incremental update, and proofreading keep using the existing CSV project
workflow. A separate approved local-package workflow can wrap an existing
project translation output as a translation-only Mod; it does not translate
additional files or copy source assets. FPK cannot be read directly and
requires an editable source directory prepared with the official Mod Editor.
The built-in Remis chat can guide initial translation and explain this export,
but does not execute incremental updates or package export. Use the project UI
or this Agent API for incremental work; use the package options/plan/export API
below or the corresponding project UI for package generation.

For a separate package, call preflight, then
`GET /api/agent/projects/{project_id}/translation-package/options`; choose an
existing translation output and exact target language from those options.
Create a preview with
`POST /api/agent/projects/{project_id}/translation-package/plan`, show its
package identity, selected output, game-language token, output files, and risk
fields, and obtain explicit approval before
`POST /api/agent/projects/{project_id}/translation-package` with
`approved: true`. This is a local write only: it makes no paid provider call,
does not overwrite an existing package, and writes outside the game directory.
The package has a required dependency on the original Mod, contains only
translation CSV content and Mod metadata, and is not runtime-verified. Do not
call the standard `approve-export` deployment endpoint for this package.

Published Mod Archives can be removed through the approval-gated Agent endpoint
documented in the API reference. Archive removal deletes only regenerable
context releases, drafts, evidence aggregates, and analysis checkpoints. It
must preserve the project, source files, project glossary, and neologism
candidates.

Read [references/api-workflow.md](references/api-workflow.md) for payloads,
response fields, status handling, and error semantics.

## Respect approval gates

The following actions need explicit user authorization:

- starting a job that can spend model credits;
- running model-backed repair;
- exporting or deploying files;
- overwriting an existing localization folder.
- removing a published Mod Archive and its resumable analysis checkpoints.

Show the concrete plan or preview before execution. Existing explicit approval
in the conversation remains valid within its scope; do not repeatedly ask for
the same action. Ask only when authorization is missing or an action changes
the approved provider, model, language, destination or overwrite scope.

## Shell languages and Steam Workshop assets

For an unsupported game language, use `custom_lang_config` in the Agent plan.
Keep the actual translation language distinct from the game's loading language:
Italian content may use `l_english` as its shell. Read `shell_languages` from
capabilities and the returned plan's `translation` details; preserve this
configuration when retrying or resuming. A shell does not make Italian an
officially supported game language.

Strongly recommend a separate project for each actual shell language. Custom
languages share the `custom` archive identity within a project; changing the
free-text language name does not isolate a baseline. This is advice, not a
project-creation requirement or a ban on mixing languages. Officially supported
languages can coexist in one project. When the user chooses a separate project,
import a fresh source copy through Remis and do not inherit translation-directory
associations from the multilingual project.

Use `/api/agent/steam-workshop` for local publishing assets. The Workshop item ID
is explicit input, not mandatory project metadata. It may be read from source
metadata when available; otherwise ask the user. Fetch the source description,
generate the approved localized candidate, and save/select description and cover
versions through Remis. These operations save local candidates, not publish to
Steam. See the API reference for endpoints and payloads.

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
- Treat `409 project_context_not_ready` as a hard context-preparation boundary.
  Report the returned `context_readiness` details; do not silently downgrade to
  glossaries or no context.
- Treat `409 overwrite_confirmation_required` as a separate overwrite gate.
- Treat `404` as stale or unknown state; re-list projects or inspect registry
  recovery information before retrying.
- Keep ambiguous translations for human review.
- Never bypass path validation or deploy directly into a game directory.
  Follow the targeted-correction boundary above for approved small edits.
- If pause or cancel is not listed by the capabilities endpoint, say it is not
  safely supported in this build.

## Finish with an audit-ready summary

State what Remis actually did, what validation found, what remains for human
review, and whether any approval is still required. Keep provider secrets and
unrelated local paths out of the summary.
