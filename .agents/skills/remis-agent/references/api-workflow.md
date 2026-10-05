# Remis localhost Agent API

For Surviving Mars, the user's request to localize the Mod or create its
translation project already authorizes the bundled FPK tool, isolated extraction,
candidate inspection and preparation/import via Remis APIs. Review the plan and
send `approved: true` using this authorization, without asking again to unpack.
See the operator Skill's standing authorization for scope and technical blockers.

> Historical-checkout reference (2026-09-29). This file describes the older
> local checkout, not all capabilities in official v3.2.1. For `ModContent.fpk`,
> use the released `mars-pipeline/prepare/plan` and approved preparation flow
> backed by `tools/remis_fpk`; do not send a packed Workshop folder to the
> generic CSV importer. See the [released API reference](https://github.com/Drlinglong/Remis/blob/v3.2.1/.agents/skills/remis-agent/references/api-workflow.md).
> Verify the checkout's actual Git commit before starting its backend. An older
> checkout can carry the same version string while lacking these routes.

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
`inspection.game_support`. A version on inspect is a one-time scan hint. Include
a known version in `POST /projects/plan` to persist it with the approved project;
discovery and translation then use the same version. After import, call
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
through the existing CSV project workflow. A separate package exporter can
wrap a selected existing translation output as a translation-only Mod; it does
not translate more content or copy original Mod assets. The desktop Copilot
can guide initial-translation planning and explain package export, but does not
execute incremental updates or package export. Use the project UI or Agent API
for incremental updates.

The `game_support.translation_package` capability describes this local,
manual-install package format: `metadata.loctables` and an `items.lua`
`ModItemLocTable` reference the selected CSV. The package declares the source
Mod as a required `ModDependency`; it includes no assets and remains
`runtime_verified: false`. The original Mod must remain installed and enabled.
The target's game-language token is returned by package `options`; use it
exactly. In the installed Relaunched SDK, `zh-CN` maps to `Schinese`.
The contract returns `options_endpoint`, `plan_endpoint`, and
`export_endpoint`, so clients can discover these paths instead of constructing
them from a hard-coded game list.

Surviving Mars support inspection now includes `hardcoded_lua`: `scan_complete`,
`scope`, `files_scanned`, `candidate_count`, `literal_count`, `dynamic_count`,
`candidates`, and warning diagnostics. Each candidate records a relative source
path, line, decoded-text call offsets, source/call SHA-256, provisional binding
key and review reason. File SHA-256 covers exact input bytes; offsets refer to
UTF-8 decoded text without BOM. All candidates require review and remain outside
the ordinary CSV translation job. The separate FPK preparation workflow below
can turn reviewed candidates into a CSV project and source-copy rewrites.
Aliases and ordinary Lua strings are not exhaustively scanned;
partial scans or zero candidates must not be described as whole-Mod coverage.
Copilot receives bounded counts and limitations rather than candidate source text.

### Prepare an FPK and deliver an internationalized Mod

Discover routes from `game_support.source_pipeline`. Run preflight first. In
Create Project, select Surviving Mars, then use its separate FPK preparation
window; it explains the choices before inspecting an archive. The default
`delivery_mode` is `source_copy`; `text_only` creates a CSV-only project without
Lua rewrites and leaves the original Mod as a required dependency. Never write
to Steam Workshop caches.

For “how do I localize a Surviving Mars Mod?”, start with the canonical
[player guide](../../../../docs/zh/user-guides/surviving-mars.md). The input is
the original author's downloaded `ModContent.fpk`, not a Workshop URL and not
the user's translated copy. The built-in chat guides the preparation window;
Codex operates the following preparation endpoints. Do not send an FPK to the
generic folder import/translation planner.

**Authorization:** a request to localize this Mod or create its translation
project already authorizes bundled FPK inspection, isolated extraction and
project preparation. Review the plan and submit `approved: true` under that
existing authorization; do not ask again just to use `tools/remis_fpk` or
unpack it. A feasibility-only request permits isolated inspection, not project
creation. See the operator Skill's standing preparation authorization for
scope, existing paid-translation approval, and compatibility-failure handling.
Validation failures remain technical blockers; permission to unpack does not
remove them.

1. `POST /api/agent/mars-pipeline/prepare/plan` with `archive_path`, `name`,
   the actual `source_language`, optional `source_table` (an inspected
   archive-relative CSV path), and `source_column` (`Text` or `Translation`).
   With no language selected, inspection returns samples but preparation is
   blocked. `English.csv` may contain Spanish `Text` and English `Translation`:
   choose `source_language: "en"`, `source_table: "Localization/English.csv"`,
   `source_column: "Translation"` to translate from English. Review returned
   `source_tables`, `source_selection`, `source_blockers` and diagnostics.
   Translation-column selection requires an explicit table and nonempty values;
   never fill gaps from a different language. Text-only selection scopes IDs to
   that table, including CSV-only entries; report Lua IDs outside its scope.
   Original Lua fallback text, CSV bytes and stable IDs remain unchanged; the
   new prepared CSV uses the chosen source and the receipt records provenance.
   Plans with source blockers have no `approve_preparation` action.
   Other request fields are
   optional `previous_run_id`, optional reviewed `approved_ids`, and optional
   `delivery_mode` (`source_copy` or `text_only`). The
   validated FLPK v1 archive is inspected in temporary isolated storage.
   Read file/entry counts, `review_items`, diagnostics and source fingerprint.
   Unknown archive profiles fail explicitly. The Mod's Lua is never executed.
2. Review proposed text changes and recreate the plan with approved candidate
   IDs. In `text_only`, entries still pending review are excluded from the CSV.
   In `source_copy`, only approved and safely renderable candidates are rewritten;
   unresolved changes remain visible as blockers. Preserve internal option
   values and gameplay.
3. With user authorization, `POST /api/agent/mars-pipeline/prepare` using
   `plan_id` and `approved: true`. It rechecks the archive, extracts the
   resources selected by the delivery mode, writes a standard five-column CSV
   and creates a normal referenced project. The user's localization/project
   request supplies preparation authorization; do not require a duplicate
   confirmation. Preparation alone does not approve translation or delivery.
   Read the persisted receipt via `GET /api/agent/mars-pipeline/runs/{run_id}`.
   A successful result has `status: prepared`, `project_id`, source/prepared
   paths, manifest, archive hashes and allowed actions. A failed receipt is not
   a successful import. Save `run_id` for identity matching on future updates.
4. Use the existing `/jobs/plan` and `/jobs` translation workflow, selecting
   the user's provider/model/languages and context settings. Preparation alone
   does not authorize paid translation; an explicit translation request naming
   that provider/model already does, within its scope and stated budget. Review
   the concrete plan and carry that approval forward. Check persisted job state
   and validation.
5. Read `GET /api/agent/projects/{project_id}/mars-pipeline`. Select only the
   project's own translation outputs. The normal UI offers `source_copy` and
   `text_only`; runtime `overlay` is advanced API configuration and requires a
   reviewed binding profile. Preview with
   `POST /api/agent/projects/{project_id}/mars-pipeline/export/plan`:
   `{"mode":"source_copy","outputs":[{"language_code":"zh-CN","output_folder_name":"zh-CN-example"}]}`.
   Multiple language outputs share the same stable IDs and Lua source.
   To build one multilingual Mod, include every intended language in that
   same `outputs` array; do not export one package per language. For example:
   `{"mode":"source_copy","outputs":[{"language_code":"zh-CN","output_folder_name":"zh-CN-prepared"},{"language_code":"fr","output_folder_name":"fr-prepared"},{"language_code":"de","output_folder_name":"de-prepared"}]}`.
   These names are illustrative: select actual names returned by options.
   Language work folders remain project translation inputs for future exports
   and updates; they are not temporary files or installation destinations.
6. `source_copy` carries all original assets, gets a new Mod ID and a
   `[Remis i18n]` title prefix, and replaces the enabled original. `text_only`
   contains localized CSVs and requires the original Mod. The `overlay` mode
   is API-only advanced configuration, requires a reviewed runtime binding
   profile, and is not a normal UI option. Do not export with blockers or a
   non-ready status. Prefer `source_copy` when hard-coded text must be covered;
   upstream author acceptance is not a delivery mode.
7. With export authorization, call
   `POST /api/agent/projects/{project_id}/mars-pipeline/export` with `plan_id`
   and `approved: true`. Plans freeze source and translation fingerprints.
   Output is a new local directory; no overwrite, installation, FPK repacking
   or publication occurs. Read the returned package path, receipt and file
   hashes. All outputs retain `runtime_verified: false`; source-copy save
   compatibility and in-game loading remain unverified until game checks.

For a project-owned Workshop ID on a complete source copy, read
`GET /api/agent/projects/{project_id}/mars-pipeline/publication`. This returns
the source/output Mod IDs and `status`, `revision`, `steam_id`, and `url`; an
unbound project has `revision: 0`. The binding applies only to `source_copy`.
It is a local identity record: Remis does not verify Workshop ownership and
does not upload or publish anything. Confirm that the ID belongs to your own
published copy before saving it. Submit the displayed revision with
`PUT /api/agent/projects/{project_id}/mars-pipeline/publication`, for example
`{"approved":true,"expected_revision":0,"steam_id":"76561198000000000"}`.
The ID is write-once through this API; it cannot be silently replaced or
cleared. Re-read the GET endpoint before relying on the binding.

Export plans may include optional `metadata_overrides` for a reviewed title,
`description`, `short_description`, `last_changes`, and cover image. Text-only
packages use their generated `[Remis text]` title when no title override is
provided; source-copy packages retain the normal `[Remis i18n]` prefix. Supplying a cover requires both an absolute
local `cover_asset_path` and its `cover_asset_sha256`; only bounded PNG/JPEG
assets are accepted. The preview lists the copied cover path and hash, and
export rechecks the hash so a changed image invalidates the plan. The output
metadata points to the copied image under the new Mod ID, keeps the original
author, and omits the source's top-level Workshop publication IDs. These
overrides only build a local package; they do not publish or install it.
`short_description` is retained as Paradox metadata; the publisher uses the
local `title`, `description`, and `last_changes` values when updating a
Workshop item. Keep any update target bound to the user's own published copy,
never the original author’s Workshop item.

For text-only delivery, optional `additional_project_outputs` can combine
approved keyed translations from other prepared Surviving Mars projects into
the same package. Each entry is `{ "project_id", "language_code",
"output_folder_name" }`; select a target language also present in the base
project's `outputs`. Companion CSVs load only while their source Mod IDs are
enabled. The package keeps the base Mod ID and its single required dependency.
The preview returns `additional_project_snapshots` with each companion run,
source fingerprint, and translation-output fingerprint; export rechecks them.
Duplicate IDs must have identical source and target text. The package does not
copy companion metadata, assets, or source files. Runtime activation still
requires an in-game check.

When installing a source copy, disable the original and previous translation
patches; do not enable duplicate Mod identities. Keep the Steam archive intact.
On Windows Relaunched, copy the contents of the returned `package_path` into
`%APPDATA%/Surviving Mars Relaunched/Mods/<output_mod_id>/`, so `metadata.lua`
is directly inside that folder. A multilingual package keeps all registered
`Localization/<game_language>/` directories together. A `text_only` delivery
uses the same local Mods root but requires both the original and translation
Mod enabled; a `source_copy` is enabled on its own. This location is specifically
for Relaunched; do not silently install to the legacy game's folder.

Uploading to Steam still requires the game's own Mod Editor. For the first
upload, publish a new copy, then save its returned item ID in the project's
publication binding. For later updates, export a new package carrying that
same ID and manually update through the editor. Remis does not automate FPK
packing/upload. Keep reviewed title/description/cover in local Mod metadata;
the editor may resend these fields during updates. Use the user's own item,
never the source author's publication identity.

Format validation is separate from the unfinished Mars-specific proofreading
UI. If a project badge reports an issue, inspect its file path, language,
timestamp and current text before interpreting it as a defect in the latest
package. An old language work folder's saved report can remain visible after
new corrected output was generated elsewhere. Do not delete that report or
claim it resolved solely because a different export passes checks.

The standalone unpacker lives in `tools/remis_fpk`; its source distribution
contains no game/Mod assets. Community publishing remains a separate action.

### Generate a local Surviving Mars translation package

This workflow wraps an already-generated project translation output. It is a
local write, does not call a translation provider, does not overwrite an
existing package, and does not install or publish anything. Run `preflight`
before this workflow and obtain explicit approval before package generation.
The Agent routes are `GET /api/agent/projects/{project_id}/translation-package/options`,
`POST /api/agent/projects/{project_id}/translation-package/plan`, and
`POST /api/agent/projects/{project_id}/translation-package`; GUI clients use
the same suffixes under `/api/projects/{project_id}`.

```powershell
$projectId = 'project-id'
$base = "http://127.0.0.1:1453/api/agent/projects/$projectId/translation-package"
$options = Invoke-RestMethod "$base/options"
$options | ConvertTo-Json -Depth 8
```

Choose an existing `translation_outputs[].output_folder_name` and one exact
`languages[].code` from the options response. `languages[].game_language` is
the game's `ModItemLocTable.Language` token. The options response also reports
the source Mod ID/title, warnings, limitations, and runtime status.
If a selected token has no matching language pack in the inspected local
installation, the plan returns a warning; a recognized SDK token does not prove
the game has that language pack installed.

Create and inspect a plan; optional source metadata overrides should only be
sent when explicitly requested or verified:

```powershell
$planBody = @{
  output_folder_name = 'zh-CN-Example'
  target_language = 'zh-CN'
} | ConvertTo-Json
$plan = Invoke-RestMethod -Method Post -Uri "$base/plan" `
  -ContentType 'application/json' -Body $planBody
$plan | ConvertTo-Json -Depth 10
```

Show the generated package `package.mod_id` and title, selected output/language,
`package.files`, translated-entry count, warnings, and installation steps. The
plan risk fields must show
`may_use_paid_api: false`, `overwrites_existing_output: false`, and
`exports_to_game_directory: false`; the plan requires explicit approval. Only
after approval, submit:

```powershell
$exportBody = @{ plan_id = $plan.plan_id; approved = $true } | ConvertTo-Json
$result = Invoke-RestMethod -Method Post -Uri $base `
  -ContentType 'application/json' -Body $exportBody
$result | ConvertTo-Json -Depth 10
```

The result contains the local `package_path`, generated `files`, manual
`installation_steps`, and `runtime_verified: false`. CSV files are stored under
package-relative `Localization/<game_language>/...` paths; `metadata.loctables`
and `items.lua` reference `Mod/<generated_mod_id>/Localization/...` virtual
mounted paths. The package references the original Mod as a required dependency
and does not change the original Mod. Relaunched SDK source documents the loader contract:
`ModItemLocTable.md.html`, `Mod.lua` (`UpdateLocTables` and
`ModsLoadLocTables`), `ModItem.lua` (`GetAllLanguages`), and `localization.lua`
(language-token mapping). `ModDependency` defaults `required` to true and
major/minor versions to zero; keep those version requirements at zero so an
unrelated small version change does not pin the translation package. Copy the
generated Mod directory into the game's user Mods folder, then enable both Mods
and select the matching game language.
This guidance follows the SDK code; Remis has not verified the generated Mod
in a live game. Hard-coded `Untranslated(...)` text is outside CSV coverage.
The GUI-compatible routes use the same contract under `/api/projects/{project_id}`.

CSV output preserves source-relative paths. An FPK archive is not input for
this CSV-only exporter. Route it through
[FPK preparation](#prepare-an-fpk-and-deliver-an-internationalized-mod):
`POST /api/agent/mars-pipeline/prepare/plan`, followed by approved preparation.
Remis uses `tools/remis_fpk` to extract supported FLPK v1 archives into isolated
storage; manual Mod Editor extraction is not a prerequisite. The original Mod
remains unchanged. Final FPK repacking and Workshop upload still use the game's
official Mod Editor.

### Initial and incremental workflows

`POST /jobs/plan` accepts `workflow: "initial" | "incremental"`; omission
defaults to `initial`. Submit the approved plan through the existing
`POST /jobs` endpoint. Incremental mode compares recognized source entries, so
Mod metadata version changes alone do not trigger retranslations; source path
move reuse is not guaranteed across games. Follow
`game_support.incremental_policy` and `changed_translation_policy` for that
game. Project Zomboid and RimWorld retain translations for changed source with
`needs_review`; Surviving Mars uses its existing CSV incremental workflow.
Before planning, an optional zero-cost, read-only preview is available at
`POST /api/agent/projects/{project_id}/incremental-preview` with optional
`custom_source_path` and `target_lang_codes` (for example `["zh-CN"]`). It
requires no provider configuration or key and does not write provider data,
project state, archives, or outputs. It returns an aggregate `summary`, a
`per_language` list with flat counts and per-language `deleted_entries`,
`file_summaries` whose entries include `dirty_entries`, plus `fingerprint`,
`source_path`, and `source_language`. Use the reviewed fingerprint as
`expected_preview_fingerprint` in `POST /jobs/plan`; the paid plan reports
`translation.incremental_preview`, and execution rejects a stale preview.
`custom_source_path` lets a prepared source attach to an existing project; with
`translation_context_mode: "none"`, reuse still compares against the project's
archive baseline. Prefer the original author's `Text` and confirm its
language. Use `Translation` as the source only when the user explicitly selects
it as the translation source. An English baseline must not silently switch to
Spanish `Text`, which would make all entries appear changed.

For incremental jobs, `dry_run: true` now executes the entry diff without a
provider call. Initial-translation `dry_run: true` remains a readiness check.
Read `GET /api/agent/jobs/{job_id}` and inspect `result.metadata`: execution
dry-runs expose `incremental_preview` and `diff_executed: true`; completed jobs expose
`entry_summary` and `file_summaries`. Keep counts for source-changed entries,
model-submitted entries, and entries requiring review distinct. Check
`game_support.incremental_checkpoint_resume_supported`; for these adapters it
is false, so a fresh incremental plan is required instead of checkpoint resume.
Custom shell languages are unsupported for these adapters, including
incremental work.

The in-product desktop chat currently guides initial translation only. Use the
project UI or this Agent API with `workflow: "incremental"` for incremental
updates; do not infer chat execution support from API support.

### Save approved proofreading edits

For a Mars project whose output was lost but translations remain in Remis,
`POST /api/agent/projects/{project_id}/translation-recovery/plan` with
`languages: ["fr", "de"]` previews deterministic archive recovery. It currently
requires exactly one recognized source CSV, complete archived key/source matches,
and absent destination directories. It accepts one to nine distinct supported
Mars language codes; diagnostics may still require targeted corrections after
recovery. After approval, POST `plan_id` and `approved: true` to
`/api/agent/projects/{project_id}/translation-recovery`. It rechecks source and
archive fingerprints, writes separate language outputs, and returns indexed
`registered_files` for the proofreading route below. It makes no model calls,
does not overwrite outputs, and does not establish game-runtime verification.

Use the Agent aliases when an Agent is saving user-approved proofreading
changes; do not call the GUI-only route or write files directly. Fetch the
current document with `GET /api/agent/proofread/{project_id}/{file_id}`, retain
its `document_revision`, and present edits for explicit user approval. Submit
the approved entries and any structure patches through
`POST /api/agent/proofread/save` with `approved: true` and that non-empty value
as `base_revision`. A changed target returns HTTP 409
`proofreading_revision_conflict`; reload and review the new document before
trying again. The route delegates to the existing proofreading service so its
archive synchronization and rollback behavior remain in effect. Agent saves
are restricted to files currently indexed as `translation` in the requested
project; source files and IDs not belonging to that project are rejected.

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

## Translation collections

Call preflight before each collection workflow. The desktop API uses base
`/api/translation-collections`; the Agent mirror is
`/api/agent/translation-collections`. Both operate on the same persisted
collection records. A collection combines selected existing output folders
from distinct projects of one game; it does not run translation jobs.

Core routes:

| Method | Path | Purpose |
|---|---|---|
| `GET`, `POST` | `/api/translation-collections` | List or create collections |
| `GET`, `PUT`, `DELETE` | `/api/translation-collections/{id}` | Read, revision-guarded update, or delete a collection record |
| `GET` | `/api/translation-collections/project-options/{project_id}` | Read project-owned output folders available for selection |
| `POST` | `/api/translation-collections/{id}/plan` | Validate member selections and create an export preview |
| `POST` | `/api/translation-collections/{id}/export` | Execute a previously approved local export |
| `PUT` | `/api/translation-collections/{id}/publication` | Save the collection's own Steam publication ID |
| `GET` | `/api/translation-collections/{id}/history` | Read persisted export receipts |

Use the same suffixes under `/api/agent/translation-collections` for Agent
operations. `POST` create accepts `game_id`, `title`, optional `description`,
`target_languages`, and `members`. Each member contains `project_id` and
`outputs`; each output selects a `language_code` and exact
`output_folder_name` returned by `project-options`:

```json
{
  "game_id": "rimworld",
  "title": "My translated mod set",
  "description": "Optional notes",
  "target_languages": ["zh-CN"],
  "members": [
    {
      "project_id": "project-id",
      "outputs": [
        {"language_code": "zh-CN", "output_folder_name": "zh-CN-output"}
      ]
    }
  ]
}
```

`PUT /{id}` accepts the same collection fields plus `expected_revision` from
the latest read. `DELETE /{id}` requires that revision as the
`expected_revision` query parameter. Collection IDs and generated `mod_id`
remain stable across edits; members are references to projects, not copies.

Plan with `POST /{id}/plan` and inspect `plan_id`, `inspection.mode`,
`inspection.can_export`, diagnostics, members and fingerprint before taking an
action. If any input changes after planning, discard the stale plan and make a
new one. Mars incomplete or unapproved text-only outputs and hard-coded/source-
copy gaps block export. Other games require one selected output per target
language and report unverified translation completeness as a warning. Paradox
global key conflicts are preview diagnostics; remove conflicting members or
choose a compatible set before exporting. Never work around blockers by copying
or altering a member project directly.

Only after the user explicitly approves the shown local export, call
`POST /{id}/export` with `{"plan_id":"<returned plan_id>","approved":true}`.
Verify the persisted receipt and `package_path`. Export writes a new local
package; it does not install it, call a translation model, or upload to Steam.

Surviving Mars collections render one multilingual optional Mod. Its loader
applies a member's selected translations only while that member Mod is enabled
and the game language matches; keep the original Mods enabled. Mars preview
blocks incomplete or unapproved text-only coverage, including hard-coded and
source-copy gaps. For other games, the bundle keeps separate member directories
and does not create one merged Mod. Portable translation completeness is
unverified and is a warning. For Paradox games, inspect preview diagnostics for
global localization key conflicts and the affected member pairs; separate
directories do not make conflicting keys safe to enable together. Remove
conflicting members or choose a compatible set before export. All outputs have
`runtime_verified: false` and require manual installation and in-game checks.

For Surviving Mars, bind publication only after the user has manually published
their own collection in the game's Mod Editor and supplied that collection's
Steam ID. For Paradox games, users follow each game's own Mod upload workflow;
Remis does not provide a Paradox Mod Editor.
`PUT /{id}/publication` requires `expected_revision`, `steam_id`, and
`approved: true`; the approval records the identity binding only. It does not
publish or upload files. Never use a member's or original author's Steam ID.

For the user-facing flow, see
`docs/zh/user-guides/translation-collections.md`.

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
