# Project Remis v3.0.6

## English

## Compatibility Notes

- Removed Gemini CLI as a selectable translation provider. Google transitioned the individual/free/Google AI Pro/Ultra Gemini CLI experience to Antigravity CLI on June 18, 2026, so the old no-API-key Gemini CLI path can no longer be treated as a reliable Remis provider.
- Google Gemini API support remains available. Users who want to keep using Gemini models in Remis should select the Google Gemini provider and configure `GEMINI_API_KEY`.
- Existing saved projects that still reference `gemini_cli` will now fail with an explicit removal message instead of silently falling back to another provider.

## UI And Setup

- Removed Gemini CLI from the frontend provider list, API settings grouping, setup guidance, and localized provider descriptions.
- Removed the old runtime probe that checked for a local `gemini` command during startup.

## 中文

## 兼容性说明

- 移除了 Gemini CLI 作为可选翻译供应商。Google 已在 2026-06-18 将个人 / 免费 / Google AI Pro / Ultra 的 Gemini CLI 体验迁移到 Antigravity CLI，旧的“无需 API Key、通过 Gemini CLI 调用”的路径不再适合作为 Remis 的稳定供应商。
- Google Gemini API 支持仍然保留。仍想在 Remis 中使用 Gemini 模型的用户，可以选择 Google Gemini 供应商并配置 `GEMINI_API_KEY`。
- 如果旧项目配置里仍保存着 `gemini_cli`，现在会得到明确的“已移除”错误提示，不会再静默回退到其他供应商。

## 界面与配置

- 从前端供应商列表、API 设置分组、配置向导和多语言供应商描述中移除了 Gemini CLI。
- 移除了启动阶段对本地 `gemini` 命令的旧探测逻辑。
