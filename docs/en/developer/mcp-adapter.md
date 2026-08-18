# Experimental Remis MCP adapter

> **Status:** branch-only experiment. This adapter is not merged, pushed,
> released, or part of a supported Remis build.

The adapter is a small standard Model Context Protocol (MCP) server that lets
an MCP host discover a deliberately limited set of Remis operations. It does
not contain a second localization engine. Every operation is an HTTP request to
the running Remis localhost Agent API, which remains the authority for plans,
approval, expiry, one-time consumption, idempotency, path containment, task
state, validation, and allowed actions.

```text
Codex / Claude / MCP host
          | stdio MCP
          v
scripts.mcp_adapter.server
          | HTTP, fixed to 127.0.0.1
          v
Remis /api/agent -> existing services, registry, tasks, validators
```

This boundary avoids direct SQLite access, arbitrary filesystem access, shell
execution, internal function imports, secret retrieval, and automatic exposure
of unrelated FastAPI routes.

## SDK and transport

The implementation targets the official MCP Python SDK stable line released on
2026-07-28 and pins `mcp==2.0.0`. It uses the v2 `MCPServer` API. The first
phase runs only over local `stdio`, the SDK default for a host-launched local
server. The Starlette constraint remains compatible with the current Remis
FastAPI backend.

References:

- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Official server transport guide](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/index.md)
- [Official MCP Inspector](https://github.com/modelcontextprotocol/inspector)

## Install and start

From the repository root in the Python environment used by Remis:

```powershell
python -m pip install -r requirements.txt
scripts\developer_tools\windows\run-dev.bat
```

The development launcher selects the supported Python environment and starts
the backend. Confirm the service before connecting a host:

```powershell
Invoke-RestMethod http://127.0.0.1:1453/api/health
Invoke-RestMethod http://127.0.0.1:1453/api/agent/preflight
```

The MCP process is normally launched by its host. To wait for a host manually:

```powershell
python -m scripts.mcp_adapter.server
```

It intentionally prints nothing to stdout because stdout is the MCP wire.
Diagnostics use stderr. The adapter uses `REMIS_BACKEND_PORT`, the existing
Remis port override, and otherwise connects to
`http://127.0.0.1:1453/api/agent`. It does not accept a remote base URL, follow
redirects, use proxy environment variables, or start Remis automatically.

## Host configuration

Use an absolute repository path for `cwd` and the Python executable containing
the pinned dependency:

```json
{
  "mcpServers": {
    "remis": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "scripts.mcp_adapter.server"],
      "cwd": "J:\\V3_Mod_Localization_Factory-worktrees\\remis-mcp-adapter",
      "env": {
        "REMIS_BACKEND_PORT": "1453"
      }
    }
  }
}
```

Do not put provider keys, cookies, or authorization headers in this
configuration. Configure providers only through Remis Settings.

## Tools and Agent API mappings

| MCP tool | Agent API | Side effect and approval boundary |
| --- | --- | --- |
| `remis_preflight` | `GET /api/agent/preflight` | Read-only release and provider readiness check. |
| `remis_capabilities` | `GET /api/agent/capabilities` | Read-only sanitized allowlist; secret-bearing fields are removed. |
| `remis_list_projects` | `GET /api/agent/projects` | Read-only project summaries. |
| `remis_inspect_project` | `GET /api/agent/projects/{project_id}/status` | Read-only registered project state, validation summary, and allowed actions. |
| `remis_create_translation_plan` | `POST /api/agent/jobs/plan` | Creates an expiring plan only; it does not run a model or write translation output. |
| `remis_start_approved_plan` | `POST /api/agent/jobs` | Potentially paid/writing action. The exact plan requires explicit `approved=true`; the backend enforces TTL and one-time consumption. |
| `remis_get_job` | `GET /api/agent/jobs/{job_id}` | Read-only persisted status, progress, validation, result, output paths, and allowed actions. |

All workflow tools run preflight first and include its sanitized result in the
MCP structured output. An update notice, missing provider setup, or unavailable
release check remains visible to the host. HTTP 4xx/5xx responses keep the
Agent API error code where available. Unreachable service, timeout, redirects,
and invalid identifiers become stable `isError=true` MCP results with an
actionable, sanitized error object.

Planning success means only that Remis created a plan. Start success means only
that Remis accepted or safely reused the governed start operation. It is not a
claim that translation completed. Poll `remis_get_job` and rely on persisted
terminal state: `completed`, `partial_failed`, `failed`, `cancelled`, or
`interrupted`. Preserve `allowed_actions`; do not infer retry, repair, or export
permission from status alone.

## Inspector verification

Create a temporary Inspector config using the host configuration above, then
run these commands from any directory. The target comes from the read-only
config, which is required because the Python `-m` argument cannot be passed as
an ad-hoc Inspector CLI target.

```powershell
npx -y @modelcontextprotocol/inspector --cli `
  --config C:\path\to\remis-mcp-inspector.json --server remis `
  --method tools/list

npx -y @modelcontextprotocol/inspector --cli `
  --config C:\path\to\remis-mcp-inspector.json --server remis `
  --method tools/call --tool-name remis_preflight
```

The first result must show exactly the seven allowlisted tools. The second must
return a real Remis preflight result or an actionable `remis_unreachable`
error; neither outcome permits fabricated success.

## Known limits and future transport evaluation

- Remis must already be running; the adapter never launches an unknown service.
- Phase one exposes translation planning/start/status only. Project import,
  repair, export, deployment, generic files, SQL, shell, and Python execution
  are intentionally absent.
- There is no MCP-level remote authentication because there is no remote MCP
  listener. Provider configuration remains inside Remis.
- A host process must use the same local machine and a Python environment with
  the pinned SDK.
- MCP success does not collapse background task states or replace Remis task
  persistence.

Streamable HTTP should be evaluated only after this allowlist, error contract,
approval semantics, and host interoperability are stable. A future evaluation
must add explicit authentication, origin/host protection, session and
multi-client threat modelling, TLS/reverse-proxy guidance, concurrency tests,
and a deliberate bind policy. It must still call the localhost Agent API rather
than moving localization logic into the MCP process. SSE is not a target for
new work.
