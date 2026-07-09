# Project Remis v3.0.6

## English

## Highlights

- Closed the remaining tail of GitHub issue #138, the long-running frontend/control-state cleanup tracker. `ConfigStep.jsx` is no longer a single large settings surface: resume settings, embedded workshop settings, and collapsible settings framing now live in focused components.
- Kept the conservative Mantine workaround path intact while adding interaction coverage for the two riskiest Initial Translation state edges: selected project source language filtering and embedded workshop independent-mode defaults.
- Moved Agent Workshop run orchestration further backend-side, tightened validation scope handling, and preserved resume/polling behavior around backend run tasks.
- Hardened frontend payload recovery for wrapped array responses and malformed WebSocket messages so project management and incremental translation views fail more gracefully.
- Hardened proofreading key detection so patch-mode editing reports invalid key edits clearly and avoids loading proofreading data from stale or missing project/file records.
- Added focused regression coverage for project tracking, initial translation settings, payload recovery, proofreading key handling, and provider removal paths.

## Compatibility Notes

- Removed Gemini CLI as a selectable translation provider. Google transitioned the individual/free/Google AI Pro/Ultra Gemini CLI experience to Antigravity CLI on June 18, 2026, so the old no-API-key Gemini CLI path can no longer be treated as a reliable Remis provider.
- Google Gemini API support remains available. Users who want to keep using Gemini models in Remis should select the Google Gemini provider and configure `GEMINI_API_KEY`.
- Existing saved projects that still reference `gemini_cli` now fail with an explicit removal message instead of silently falling back to another provider.

## UI And Setup

- Removed Gemini CLI from the frontend provider list, API settings grouping, setup guidance, and localized provider descriptions.
- Removed the old runtime probe that checked for a local `gemini` command during startup.
- Moved release notes out of the repository root and into `archive/release_notes/` so future patch notes have a stable home.

## Validation

- `npm run lint`
- `npm run test -- InitialTranslation.test.jsx`
- `npm run build`
- `python -m pytest tests/test_api_handler_provider_removal.py tests/test_initial_translation_run_service.py tests/utils/test_structured_parser.py -q`

## 中文

## 重点更新

- 收尾关闭 GitHub issue #138，也就是长期追踪的前端状态 / 控件技术债。`ConfigStep.jsx` 不再是一个巨大的配置面板：断点续传设置、嵌入式智能工坊设置、可折叠设置卡片已经拆到更清晰的组件边界中。
- 保留目前更稳的 Mantine 绕行方案，同时补了两个最高风险的 Initial Translation 交互测试：项目源语言不会出现在目标语言选择中，以及嵌入式智能工坊独立模式会正确继承主翻译 provider/model 默认值。
- Agent Workshop 的 run orchestration 继续向后端收敛，并加固 validation scope 与后端 run task 的恢复 / 轮询行为。
- 加固前端 payload recovery：包裹数组响应、畸形 WebSocket 消息现在不会轻易拖垮项目管理和增量翻译视图。
- 加固校对编辑器的 key 检测：补丁模式下的 key 修改会得到更明确的提示，同时避免从已失效或缺失的项目 / 文件记录中加载校对数据。
- 补充项目追踪、初始翻译设置、payload recovery、校对 key 处理和 provider 移除路径的聚焦回归测试。

## 兼容性说明

- 移除了 Gemini CLI 作为可选翻译供应商。Google 已在 2026-06-18 将个人 / 免费 / Google AI Pro / Ultra 的 Gemini CLI 体验迁移到 Antigravity CLI，旧的“无需 API Key、通过 Gemini CLI 调用”的路径不再适合作为 Remis 的稳定供应商。
- Google Gemini API 支持仍然保留。仍想在 Remis 中使用 Gemini 模型的用户，可以选择 Google Gemini 供应商并配置 `GEMINI_API_KEY`。
- 如果旧项目配置里仍保存着 `gemini_cli`，现在会得到明确的“已移除”错误提示，不会再静默回退到其他供应商。

## 界面与配置

- 从前端供应商列表、API 设置分组、配置向导和多语言供应商描述中移除了 Gemini CLI。
- 移除了启动阶段对本地 `gemini` 命令的旧探测逻辑。
- 将 release notes 从仓库根目录迁入 `archive/release_notes/`，以后 patch note 有固定位置，不再散落在根目录。

## 已验证

- `npm run lint`
- `npm run test -- InitialTranslation.test.jsx`
- `npm run build`
- `python -m pytest tests/test_api_handler_provider_removal.py tests/test_initial_translation_run_service.py tests/utils/test_structured_parser.py -q`
