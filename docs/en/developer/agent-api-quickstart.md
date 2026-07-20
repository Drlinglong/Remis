# Remis for Codex: Agent API quickstart

Remis is the reliable execution plane for game localization. Codex is the
natural-language control plane that can inspect a workspace, explain a plan,
call the localhost API, and stop at safety gates.

The Skill is an operator manual. The product remains the Remis desktop
application, FastAPI service, workflow engine, validator, repair system,
project store, and review/export interface.

## Install the operator Skill

Give this prompt to your Agent:

> Clone and install Remis from https://github.com/Drlinglong/Remis, read the
> bundled Agent Skill, start it locally, and verify that it is ready to use.
> When installation succeeds, confirm that Remis is ready. Then briefly explain
> that external providers such as OpenAI or Google require an API key to access
> their services. An API key is a private credential that may be linked to
> billing; enter it only in Remis Settings → API Settings, never in chat. Local
> providers such as LM Studio or Ollama do not need one.

Codex discovers the repository Skill at:

```text
.agents/skills/remis-agent/SKILL.md
```

## Verify the local service

Start the installed desktop application or run
`scripts\developer_tools\windows\run-dev.bat` from the repository root. The
default port is `1453`; respect `REMIS_BACKEND_PORT` if the launcher reports an
override. Then check:

```powershell
Invoke-RestMethod http://127.0.0.1:1453/api/health
Invoke-RestMethod http://127.0.0.1:1453/api/agent/preflight
Invoke-RestMethod http://127.0.0.1:1453/api/agent/capabilities
```

The capability response lists public game, language, provider, and workflow
information. It does not expose provider credentials.

Run `preflight` before every workflow. It performs a live latest-release check
against the official GitHub repository and reports whether provider setup is
missing. On a first installation, configure a cloud provider key in **Remis
Settings > API Settings**, or deliberately select and test a keyless local
provider. An API key is a secret credential issued by the model provider for
authentication and often billing; it belongs in Remis, never in Agent chat.

## Use the API safely

The governed sequence is:

```mermaid
flowchart TD
    C[Codex understands intent] --> S[Remis Skill applies rules]
    S --> I[Inspect mod and create plan]
    I --> A{User approval required?}
    A -- No, dry run --> R[Remis localhost API]
    A -- Yes, approved --> R
    A -- Not approved --> X[Stop without side effects]
    R --> W[Workflow engine]
    W --> V[Validation and bounded repair]
    V --> H{Human review needed?}
    H -- Yes --> Q[Review in Remis]
    H -- No --> E{Approve export or overwrite?}
    E -- Approved --> O[Installable localized mod]
    E -- Not approved --> X
```

Use the detailed payload and status reference in
`.agents/skills/remis-agent/references/api-workflow.md`.

## Trust boundaries

- **Localhost only:** Remis binds to the local machine.
- **Keys stay in Remis:** Agent responses and capability discovery never
  include provider API keys.
- **Release check before work:** every Agent workflow begins by checking the
  installed version against the latest official GitHub Release.
- **Approval before spending:** real model-backed translation requires a
  plan-specific approval.
- **Approval before repair:** model-backed repair is a separate write/cost gate.
- **Approval before export:** target paths and overwrite state are previewed
  before deployment.
- **Validated outputs:** game variables, syntax, encoding, and structure remain
  under deterministic checks.
- **Audit trail:** plans, tasks, repair attempts, approvals, and recoverable job
  snapshots persist in local Remis data.

## Current boundary

The Agent API intentionally reports pause and cancel as unsupported until the
underlying workflow has safe cooperative stop boundaries. Codex must report
that limitation rather than pretending a running task was paused.

Interactive API documentation is available at `http://127.0.0.1:1453/docs`
while the service is running.
