# Using Ollama for Localization

How to run local models with [Ollama](https://ollama.com/) inside the **Remis desktop client**.
See also the Chinese [Provider setup index](../../zh/user-guides/provider-setup-index.md) if you use the ZH UI.

## Why Ollama?

- Local processing (privacy)
- Works offline after models are pulled
- No cloud token fees (uses your hardware)
- Many open-source models to choose from

## Setup

### 1. Install Ollama

Install from [ollama.com](https://ollama.com/) and keep the service running.

### 2. Pull a capable model

Remis expects models that follow structured output instructions. Tiny chat models often fail.

```bash
ollama pull llama3
```

Prefer larger instruct-style variants (e.g. `7b` over `1b`/`4b`). Check names with `ollama list`.

### 3. Configure in Remis

1. Open **Settings → API**.
2. Select **Ollama** (local providers group).
3. Set **model name** (exact match to `ollama list`) and **URL** (default often `http://localhost:11434`).
4. API key is usually not required.
5. **Save**, then pick Ollama in **Initial translation** or **Incremental translation** jobs.

### 4. Remote Ollama (optional)

If Ollama runs on another machine, put the full URL (e.g. `http://192.168.1.100:11434`) in the Ollama URL field in **Settings → API**, then save.

## Troubleshooting

- **Connection / 404**: service running? URL correct? model name exact?
- **Invalid JSON / parse errors**: use a stronger model; lower concurrency/RPM for local runs.
- Logs: `%APPDATA%\RemisModFactory\logs\` on Windows packaged builds (`remis_backend.log`).

## Related

- [Getting started (ZH)](../../zh/user-guides/getting-started.md)
- [FAQ (this folder)](faq.md)
