# Frequently Asked Questions (FAQ)

For the **packaged Remis desktop client**.
Chinese users: prefer [docs/zh/user-guides/faq.md](../../zh/user-guides/faq.md) and [getting-started](../../zh/user-guides/getting-started.md).

> **First time?** Create a project under **Project management**, then run **Initial translation** on that project.
> Do not expect Initial translation alone to create the project.

> **Where do API keys go?** **Settings → API** in the client. See [Provider index (ZH)](../../zh/user-guides/provider-setup-index.md).

---

## 1. Install and start

### Q1.1: How do I download and start Remis?
1. Get a release from [GitHub Releases](https://github.com/Drlinglong/Remis/releases) (or your download channel).
2. Install or extract and launch the **Remis client**.
3. Use **Start a new translation project** or **Project management** to begin.

### Q1.2: Why do I need an API key?
Remis does not ship translation quota. Provide your own cloud API or a local model (e.g. Ollama).

- **Settings → API**: provider, key, model, base URL if needed → **Save**.
- Never post full keys in public issues or chat.

### Q1.3: Where are keys stored?
In the client’s local app data (managed by the app). Use the settings UI only.

---

## 2. Projects and mods

### Q2.1: Where do I put my mod?
In **Project management → Create project**, set the folder path to the **mod root** or Steam Workshop folder, choose **Copy into Remis** or **Use in place**, game, and source language.
Details: [getting-started (ZH)](../../zh/user-guides/getting-started.md).

### Q2.2: Workshop folders are numeric—rename?
Optional. Use a clear **project name** in Remis; the disk path can stay numeric.

### Q2.3: Create project fails?
Use a full mod root (with `localization` / `localisation`), correct game and source language, readable path. Logs: `%APPDATA%\RemisModFactory\logs\`.

---

## 3. Translation

### Q3.1: Games, languages, AI providers?
- Game / source language: when creating the project (or project settings).
- Target languages and provider/model: **Initial translation** after selecting the project.

### Q3.2: Glossary?
Terminology cheat sheet for consistent game terms. Enable in translation settings; manage under glossary tools.

### Q3.3: Where is the output?
Project management → translation output folder, or use **One-click deploy**.

### Q3.4: Mod updated—retranslate everything?
Prefer **Incremental translation** if an archive baseline exists. Half-finished packs: **Upload translations** under project history first.
See [incremental-update (ZH)](../../zh/user-guides/incremental-update.md).

---

## 4. In-game

### Q4.1: Install into the game?
Prefer **One-click deploy** ([ZH guide](../../zh/user-guides/one-click-deploy.md)).
Manual fallback: copy the pack into `Documents\Paradox Interactive\<Game>\mod`.

### Q4.2–Q4.3: Enable and load order
Enable **original + localization** mods; put localization so it overrides the original (often below the original in the launcher list).

### Q4.4: Fake localization?
Fake language folders in the **original** mod can hide your real patch. Prefer Remis **clean fake localization** inside the deploy dialog.
[Fake localization (ZH)](../../zh/user-guides/fake-localization.md).

---

## 5. Troubleshooting

### Q5.1: Crash / error
Check API key, full mod import, and `%APPDATA%\RemisModFactory\logs\remis_backend.log` (tail `ERROR`).
[Logs (ZH)](../../zh/user-guides/logs-and-diagnostics.md). Format issues: [error catalog (ZH)](../../zh/user-guides/error-catalog.md).

### Q5.2: No Chinese in game
Redeploy, clean fake localization, fix load order, disable other conflicting mods.

### Q5.3: Poor quality
Glossary, mod theme prompts, [proofreading (ZH)](../../zh/user-guides/proofreading.md), [agent workshop (ZH)](../../zh/user-guides/agent-workshop.md) for format.

### Q5.4: Invalid key / quota
Re-save key in Settings; check balance and rate limits; network/proxy.

### Q5.5: Bugs and features
https://github.com/Drlinglong/Remis/issues — include version, steps, redacted logs. The packaged client cannot modify Remis source code.

---

## Related (Chinese guides are the fullest set)

| Topic | Doc |
|-------|-----|
| First run | [getting-started](../../zh/user-guides/getting-started.md) |
| Deploy | [one-click-deploy](../../zh/user-guides/one-click-deploy.md) |
| Providers | [provider-setup-index](../../zh/user-guides/provider-setup-index.md) |
| Ollama | [using_ollama](using_ollama.md) |
