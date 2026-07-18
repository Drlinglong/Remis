# Remis agent instructions

Remis is a complete local localization application. Its Codex Skill is an
operator guide over the product; it is not the product itself.

## Safe operating boundary

- Bind the backend to `127.0.0.1`.
- Never read, print, log, or return provider API keys.
- Use `/api/agent` for Agent-driven operations instead of bypassing Remis with
  direct filesystem edits.
- Call `/api/agent/preflight` before every workflow. Report release-check
  failure honestly, and surface any newer official GitHub Release.
- On first setup, prompt for provider configuration in Remis Settings. Offer to
  explain API keys, but never ask the user to paste a secret into chat.
- Require explicit approval before paid translation, model-backed repair,
  export, deployment, or overwrite.
- Preserve Paradox keys, variables, formatting, encoding, and folder structure.
- Leave ambiguous text for human review.

## Repository workflow

- Backend: Python FastAPI under `scripts/`.
- Desktop frontend: React/Tauri under `scripts/react-ui/`.
- Product website: React/Vite under `website/`.
- Codex operator Skill: `.agents/skills/remis-agent/`.

Run focused verification for the area changed:

```powershell
python -m pytest -q tests/test_agent_api.py
python -m compileall -q scripts tests

Set-Location website
npm test
npm run lint
npm run build
```

For a development checkout, use `run-dev.bat`; do not guess a different Python
environment or backend port. The default local service is
`http://127.0.0.1:1453`, unless `REMIS_BACKEND_PORT` overrides it.

Do not claim a workflow completed from request acceptance alone. Use persisted
job state, validation results, output paths, and `allowed_actions` returned by
Remis.
