# Remis localhost Agent API

Base URL: `http://127.0.0.1:1453/api/agent`

This is a technical reference for operating Remis, not ready-made player-facing
copy. Explain the practical consequence and next step in plain language first;
show internal identifiers and storage details when the user asks for them.
For shell translation, recommend a separate project because saved translations
can get mixed up and cause incorrect reuse during later Mod updates. Do not
describe this as inevitable database corruption.

The API returns structured JSON and never returns provider API keys. Agent
errors are raised through FastAPI's `HTTPException`, so the HTTP response wraps
the structured error payload in `detail`:

```json
{
  "detail": {
    "code": "approval_required",
    "message": "Explicit approval is required before starting this job.",
    "retryable": false
  }
}
```

Agent clients should inspect `response.detail.code`, display
`response.detail.message`, and only retry automatically when
`response.detail.retryable` is `true`. Do not expect an `error` envelope or a
`details` object.

## Discover the runtime

```powershell
Invoke-RestMethod http://127.0.0.1:1453/api/health
Invoke-RestMethod http://127.0.0.1:1453/api/agent/preflight
Invoke-RestMethod http://127.0.0.1:1453/api/agent/capabilities
```

Call `preflight` before every new workflow. It performs a live check against
the official GitHub latest-release endpoint and reports provider setup without
returning credentials. If `provider_setup.setup_required` is true, guide the
user to **Remis Settings > API Settings**. Offer to explain API keys, but never
ask the user to paste one into Agent chat. A deliberately selected keyless
local provider can be checked with:

```powershell
Invoke-RestMethod 'http://127.0.0.1:1453/api/agent/preflight?provider_id=lm_studio'
```

If `release_check.checked` is false, say the update check was unavailable. If
`update_available` is true, show the official `release_url` before continuing.

Use the identifiers returned by `capabilities`; do not infer game, language,
provider, or model identifiers from display labels.

### Game support and source coverage

`GET /capabilities` keeps the existing `games[].capabilities` fields and adds a
per-game `games[].game_support` contract. Read its `formats`, `limitations`,
`output_kind`, `export_mode`, `workflow_modes`, `incremental_checkpoint_resume_supported`,
`version_policy`, `incremental_policy`, `changed_translation_policy`,
`runtime_verified`, and `source_files_read_only` values. This is the static
adapter contract; it is not a claim that every file or runtime string in a Mod
is covered.

Inspect a candidate folder with optional game context:

```json
{
  "folder_path": "C:\\Mods\\Example",
  "game_id": "rimworld",
  "source_language": "en",
  "game_version": "1.6"
}
```

`POST /projects/inspect` returns the dynamic scan under
`inspection.game_support`. The project import-plan also returns its scan at
`inspection.game_support`. `game_version` is a scan hint only: it does not
modify project settings or configure later jobs. After import, call
`GET /projects/{project_id}/game-support` to scan the project's current source
tree; the top-level result includes recognized resources and entry counts,
diagnostics, coverage scope, read-only status, runtime verification status,
allowed actions, and a static support contract under `support`. The translation
plan returns top-level `game_support`: for structured games this contains the
dynamic scan and nests the static contract at `support`; for other games it is
the static contract. Inspect those diagnostics before approval.
Set `source_language` from the user's selected source or project metadata; do
not assume that source text must be English.

For Project Zomboid, recognized inputs include JSON string maps and restricted
literal Lua-table TXT. For RimWorld, recognized inputs include Keyed,
DefInjected, Strings, explicitly catalogued translatable Def fields, and
`rulesStrings`. Unknown shapes or fields are diagnosed rather than executed or
assumed translatable. RimWorld inheritance, patch effects, conditional load
selection and assembly/runtime text may need human review. Neither adapter runs
game assemblies or evaluates Lua. Source files remain unchanged.

Surviving Mars exposes a static `csv_contract` in `game_support` and a dynamic
scan in project inspection. Use the returned `recognized_resource_count`,
`recognized_entry_count`, `coverage_scope`, `diagnostics`, and
`runtime_verified`; do not infer full Mod coverage from a successful scan. The
contract includes `header`, `source_column`, `writable_column`,
`preserved_columns`, `id_policy`, `tag_policy`, `encoding`,
`preserve_relative_paths`, and `compressed_packages_supported`. The accepted
header is `ID,Text,Translation,VoiceActor,Context`.
`ID` is an ASCII decimal string and leading zeros remain significant. Only
`Translation` may change; `Text`, `ID`, `VoiceActor`, and `Context` are
preserved. Text between tags may be translated, but tag spelling, parameters,
case and multiplicity inside the tag are immutable. Invalid/no-table scans have
blocking diagnostics; ordinary plans reject them, while dry-run remains
available to inspect readiness and diagnostics. `runtime_verified` is false.
This game supports initial translation, incremental update and proofreading
through the existing CSV project workflow; it does not produce a separate
translation Mod. The desktop Copilot only prepares initial-translation plans.
Use the project UI or Agent API for incremental updates.

CSV output preserves source-relative paths. FPK is a compiled package and is
not readable by the adapter; use the official Mod Editor to prepare an editable
source directory. This adapter does not itself unpack/repack FPK or edit
ModItem metadata.

### Initial and incremental workflows

`POST /jobs/plan` accepts `workflow: "initial" | "incremental"`; omission
defaults to `initial`. Submit the approved plan through the existing
`POST /jobs` endpoint. Incremental mode compares recognized source entries, so
Mod metadata version changes alone do not trigger retranslations; source path
move reuse is not guaranteed across games. Follow
`game_support.incremental_policy` and `changed_translation_policy` for that
game. Project Zomboid and RimWorld retain translations for changed source with
`needs_review`; Surviving Mars uses its existing CSV incremental workflow.
`dry_run: true` is a readiness check only and does not run the entry diff. Check
`game_support.incremental_checkpoint_resume_supported`; for these adapters it
is false, so a fresh incremental plan is required instead of checkpoint resume.
Custom shell languages are unsupported for these adapters, including
incremental work.

The in-product desktop chat currently guides initial translation only. Use the
project UI or this Agent API with `workflow: "incremental"` for incremental
updates; do not infer chat execution support from API support.

`game_support` is dynamic policy data. Prefer the latest capabilities, inspect,
plan and job responses over a hard-coded local format list.

## Inspect and import a mod

```powershell
$body = @{ folder_path = 'C:\Mods\My Victoria 3 Mod' } | ConvertTo-Json
$inspection = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:1453/api/agent/projects/inspect `
  -ContentType application/json `
  -Body $body
```

Create an approval-bound import plan:

```powershell
$body = @{
  name = 'My Victoria 3 Mod'
  folder_path = 'C:\Mods\My Victoria 3 Mod'
  game_id = 'victoria3'
  source_language = 'en'
  import_mode = 'copy'
} | ConvertTo-Json

$plan = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:1453/api/agent/projects/plan `
  -ContentType application/json -Body $body
```

After the user approves the exact plan:

```powershell
$body = @{ plan_id = $plan.plan_id; approved = $true } | ConvertTo-Json
$project = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:1453/api/agent/projects `
  -ContentType application/json -Body $body
```

Plans expire. Create a new plan instead of reconstructing or editing an expired
one.

## Plan and start localization

```powershell
$body = @{
  project_id = $project.project_id
  target_lang_codes = @('zh-CN')
  api_provider = 'lm_studio'
  model = 'local-model'
  concurrency_limit = 1
  rpm_limit = 40
  use_resume = $true
  translation_context_mode = 'archive'
  dry_run = $false
} | ConvertTo-Json

$jobPlan = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:1453/api/agent/jobs/plan `
  -ContentType application/json -Body $body
```

For a readiness test with no model call or output, set `dry_run` to `true`.
The context modes are:

- `none`: no glossary and no Mod Archive context;
- `glossaries`: main, project, and explicitly selected glossaries;
- `archive`: the same glossaries plus the published Mod Archive release.

Always display `context_readiness` before approval. It reports the exact
project glossary entry count, pending candidate count, published release,
source-snapshot match, effective context item count, and warnings. A real
`archive` plan is rejected with `409 project_context_not_ready` when the
release is missing, stale, empty, or cannot be verified. Do not silently retry
with a lower mode. For a real job, display `summary`, `risk`, provider/model,
targets, context readiness, and expiry, then ask for approval:

```powershell
$body = @{ plan_id = $jobPlan.plan_id; approved = $true } | ConvertTo-Json
$job = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:1453/api/agent/jobs `
  -ContentType application/json -Body $body
```

## Monitor and validate

```powershell
$job = Invoke-RestMethod "http://127.0.0.1:1453/api/agent/jobs/$($job.job_id)"
$validation = Invoke-RestMethod "http://127.0.0.1:1453/api/agent/jobs/$($job.job_id)/validation"
```

Normalized statuses are `queued`, `running`, `awaiting_approval`, `completed`,
`failed`, `cancelled`, `interrupted`, and `unknown`. Prefer `allowed_actions`
over assumptions about the current state.

Validation separates:

- `errors`: deterministic violations that block a clean result;
- `warnings`: non-blocking findings;
- `human_review_items`: ambiguous content that should not be auto-fixed.

## Retry and repair

Ask Remis for a retry plan:

```powershell
$retryPlan = Invoke-RestMethod -Method Post `
  "http://127.0.0.1:1453/api/agent/jobs/$($job.job_id)/retry"
```

Model-backed repair is approval-gated:

```powershell
$body = @{
  approved = $true
  api_provider = 'lm_studio'
  api_model = 'local-model'
  concurrency_limit = 1
  max_retries = 3
} | ConvertTo-Json

$repair = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:1453/api/agent/jobs/$($job.job_id)/repair" `
  -ContentType application/json -Body $body
```

Never send ambiguous human-review items through a forced automatic repair.

## Remove a Mod Archive

Archive removal is project-scoped, destructive, and approval-gated. First read
the project from `GET /api/agent/projects` and display its exact name and ID.
After the user approves that exact project, send both values:

```powershell
$body = @{
  project_name = 'My Victoria 3 Mod'
  approved = $true
} | ConvertTo-Json

$result = Invoke-RestMethod -Method Delete `
  -Uri 'http://127.0.0.1:1453/api/agent/context/projects/project-id/archive' `
  -ContentType application/json -Body $body
```

The response reports `removed_counts`, `preserved`, and `allowed_actions`.
Verify that the latest-release endpoint now returns `404
context_release_not_found`. The project, source files, project glossary, and
neologism candidates must remain available. A running context analysis returns
`409 context_analysis_active`; do not cancel or bypass it.

## Preview and approve export

```powershell
$preview = Invoke-RestMethod `
  "http://127.0.0.1:1453/api/agent/jobs/$($job.job_id)/export-preview"
```

Display the returned output kind, local packages or files, paths, overwrite
state, and warnings before acting. Paradox deployment follows its approval
flow. For Project Zomboid and RimWorld, preview reports existing valid package
records (`packages`) with `export_mode: "manual_install"`, package root,
language, source mod ID and resource paths. The preview also reports
`validation_scope: "artifact_presence_only"`, `runtime_verified: false`, no
game target path, and only local-inspection actions when packages are
available. Install those packages manually using the game's Mod installation
process; after an explicit approval request, `POST /jobs/{job_id}/approve-export` returns
`409 unsupported_game_deployment` for these games and Surviving Mars.
Surviving Mars preview returns parsed CSV tables in `local_files` and
`export_mode: "local_files"` with the same `validation_scope`; invalid or
unrelated CSVs are omitted. It does not construct a separate translation Mod.

For a game with Paradox deployment, display `output_folder_name`, target paths,
overwrite state, and warnings. Then obtain export approval. If
`preview.requires_overwrite_confirmation` is true, separately confirm overwrite:

```powershell
$body = @{
  approved = $true
  confirm_overwrite = $true
  output_folder_name = $preview.output_folder_name
  game_id = 'victoria3'
} | ConvertTo-Json

$export = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:1453/api/agent/jobs/$($job.job_id)/approve-export" `
  -ContentType application/json -Body $body
```

The API restricts outputs to Remis-managed output folders and detected game mod
directories. Treat a rejected path as a safety boundary, not an instruction to
write it directly.

## Italian content using an English shell

Pass this configuration to `POST /api/agent/jobs/plan` alongside the project,
provider/model and explicit context mode. `name` is the language shown to the
translation model; `key` is the supported game language used in output files.
`folder_prefix` must be a safe, distinct output prefix ending in a hyphen.
This example is for Paradox initial translation. Multi-game adapters do not
support shell languages, and `workflow: "incremental"` rejects
`custom_lang_config` for every game.

```json
{
  "target_lang_codes": ["custom"],
  "custom_lang_config": {
    "name": "Italian",
    "code": "custom",
    "key": "l_english",
    "folder_prefix": "it-"
  }
}
```

Read the returned `translation` object before starting. The server binds this
configuration to the plan and retains it in the persisted job and retry plan.
Do not mix custom and standard targets or replace the actual target with `en`.
Existing project summaries include `source_path` for authorized local inspection.

## Local Steam Workshop publishing candidates

After explicitly approved, targeted file corrections, synchronize reviewed keys
with `POST /jobs/{job_id}/baseline/sync`: `approved: true`, `file_name` relative
to that completed job's output, `keys` (1–100 exact parser keys), and
`expected_sha256` of the reviewed file. This reads current file values and uses
the job's target identity (including `custom`), rather than guessing from the
shell filename. It never changes the output file and does not refresh validation.
Unknown keys, paths outside the registered output, and stale hashes are rejected.

Base: `/api/agent/steam-workshop`. Supply a Workshop ID explicitly; source metadata
may provide it, but projects are not required to have one. No route publishes to
Steam. Existing product workspaces and versions are shared with the desktop UI.

- `GET /items/{workshop_item_id}/description`: current source description and hash.
- `GET /workspaces?project_id=...`: find existing publishing workspaces.
- `POST /workspaces`: `name`, optional `game_id`, `project_id`, `workshop_item_id`.
- `GET /workspaces/{workspace_id}` and `/versions`: inspect persisted assets.
- `POST /workspaces/{workspace_id}/generate-description`: `workshop_item_id`
  (or use the workspace's ID), `user_template`, `target_language_name: "Italian"`,
  `language: "it"`, `provider`, `model`, and `approved: true`. Requires user
  authorization for model cost; returns the saved version and task ID.
- `POST /workspaces/{workspace_id}/versions/description`: `bbcode`, `language`,
  optional `source`, `metadata`, `parent_version_id` and source-description fields.
- `POST /workspaces/{workspace_id}/versions/cover`: `png_base64`, editable `canvas`,
  optional `source`, `metadata`, `parent_version_id`. Generate imagery separately
  and save the actual PNG through this endpoint.
- `GET /versions/{version_id}`: saved version; `/content`: cover PNG.
- `POST /workspaces/{workspace_id}/selections/{asset_type}`: `version_id`, where
  asset_type is `description` or `cover`. Selection stays local.

Generation is synchronous and may take time. If the connection is lost, inspect
workspace versions before retrying to avoid duplicate model charges. Errors use
the Agent `detail.code`, `detail.message`, `detail.retryable` envelope.
