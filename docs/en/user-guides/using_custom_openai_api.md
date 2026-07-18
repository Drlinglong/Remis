# Custom OpenAI-Compatible API

Use this when your endpoint speaks the **OpenAI-compatible** API (gateways, proxies, self-hosted stacks) and is not a dedicated preset card.

## Configure in the client (recommended)

1. Collect **API key**, **Base URL** (e.g. `https://api.example.com/v1`), and **model name**.
2. Open Remis → **Settings → API**.
3. Choose the **custom / OpenAI-compatible** provider (label may vary by version).
4. Fill key, base URL, and model → **Save**.
5. Select that provider in **Initial translation** or **Incremental translation**.

Do not paste full API keys into public issues or chat.

## Tips

| Field | Notes |
|-------|--------|
| Base URL | Whether `/v1` is required depends on the provider docs |
| Model | Must match the console ID exactly |
| Key | Re-save after rotation |

## Troubleshooting

| Symptom | Check |
|---------|--------|
| 401 / auth | Key saved? Correct provider selected? |
| Connection / timeout | URL, network, proxy, firewall |
| 404 model | Model name; account access to that model |
| Parse failures | Stronger instruct model; smaller batches |

Windows packaged logs: `%APPDATA%\RemisModFactory\logs\remis_backend.log`.

## Related

- [Provider index (ZH)](../../zh/user-guides/provider-setup-index.md)
- [Using Ollama](using_ollama.md)
- [FAQ](faq.md)
