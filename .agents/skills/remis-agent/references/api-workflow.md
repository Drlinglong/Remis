# Remis localhost Agent API

Base URL: `http://127.0.0.1:1453/api/agent`

The API returns structured JSON and never returns provider API keys. Error
responses use:

```json
{
  "error": {
    "code": "approval_required",
    "message": "Explicit approval is required before starting this job.",
    "details": {}
  }
}
```

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
  use_main_glossary = $true
  dry_run = $false
} | ConvertTo-Json

$jobPlan = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:1453/api/agent/jobs/plan `
  -ContentType application/json -Body $body
```

For a readiness test with no model call or output, set `dry_run` to `true`.
For a real job, display `summary`, `risk`, provider/model, targets, and expiry,
then ask for approval:

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

## Preview and approve export

```powershell
$preview = Invoke-RestMethod `
  "http://127.0.0.1:1453/api/agent/jobs/$($job.job_id)/export-preview"
```

Display target paths, overwrite state, and warnings. Then obtain export
approval. If `preview.overwrite_required` is true, separately confirm overwrite:

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
