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
- Write Git commit messages in English using
  `<type>(<scope>): <subject>`.

## Frontend maintainability

- Treat any production React component or hook above 500 lines as requiring a
  responsibility review before adding behavior.
- New production JavaScript and JSX files have a hard 600-line limit enforced
  by ESLint. Existing files above that limit have frozen per-file ceilings in
  `scripts/react-ui/eslint.config.js`; never raise those ceilings.
- A component or hook that acquires a third independent responsibility must be
  split into focused components, hooks, or controllers instead of gaining more
  state and JSX.
- Do not add a new responsibility to a legacy file already above 600 lines.
  Refactor it in the same change, or report the architectural blocker before
  claiming the feature complete. A narrowly scoped fix may remain in place only
  when it does not increase the file's frozen ceiling.
- Treat ESLint warnings for function length, cyclomatic complexity, and
  statement count as review findings. Resolve new warnings or document why the
  affected logic cannot yet be safely extracted.
- Frontend completion reports must include relevant file-size changes, added
  state/effects, whether API or workflow state is separated from presentation,
  and the focused tests covering extracted hooks or controllers.
- Passing tests, lint, and build checks does not by itself establish
  maintainability. Review component boundaries before declaring completion.

## Backend maintainability

- New Python production modules have an 800-line hard limit, functions and
  methods have a 120-line hard limit, and McCabe complexity has a hard limit of
  20. CI enforces these limits through
  `scripts/developer_tools/check_python_architecture.py`.
- Existing Python hotspots are frozen at their current values in
  `scripts/developer_tools/python_architecture_baseline.json`. Never raise a
  ceiling to accommodate growth.
- The Python architecture baseline is a ratchet. When a refactor reduces an
  existing exception, lower or remove that exception in the same change so the
  code cannot grow back to its previous size.
- Treat a production module above 500 lines or a function above 80 lines as
  requiring a responsibility review before adding behavior, even when it is
  still below the hard limit.
- Do not add orchestration, persistence, transport, and presentation concerns
  to the same module merely because focused tests pass. Extract stable service,
  repository, policy, or workflow boundaries before declaring completion.
- `scripts/developer_tools` is excluded from the production architecture scan.
  Tests, migrations, and operational scripts remain subject to human review
  even when a numerical exception is recorded.

## Text integrity

- Scripts that read or write source, locale, or configuration files must set
  UTF-8 explicitly. Do not round-trip non-ASCII text through terminal output.
- Before committing locale changes, parse the edited JSON, scan for runs of
  replacement question marks or mojibake, and run
  `scripts/react-ui/src/__tests__/textEncodingIntegrity.test.js`.

Run focused verification for the area changed:

```powershell
python -m pytest -q tests/test_agent_api.py
python -m compileall -q scripts tests

Set-Location website
npm test
npm run lint
npm run build
```

For a development checkout, run
`scripts\developer_tools\windows\run-dev.bat` from the repository root; do not
guess a different Python environment or backend port. The default local service is
`http://127.0.0.1:1453`, unless `REMIS_BACKEND_PORT` overrides it.

Do not claim a workflow completed from request acceptance alone. Use persisted
job state, validation results, output paths, and `allowed_actions` returned by
Remis.
