# Project Remis v3.0.6

## English

## Highlights

This release has two major changes:

- **Gemini CLI support has ended.** Remis no longer offers Gemini CLI as a translation provider. If you still want to use Gemini models, the Google Gemini API provider remains available with a `GEMINI_API_KEY`.
- **The Proofreading page has been rebuilt.** The new entry-by-entry layout is cleaner, easier to scan, and more reliable for long files. It protects unsaved work, restores session drafts, warns about external file changes, and links validation issues directly to the affected entry. The old Raw Monaco editor has been removed from Proofreading, leaving one clear and dependable editing workflow.

In short: proofreading is simpler and safer, while the discontinued Gemini CLI path has been removed.

## Technical Details

- Closed the remaining tail of GitHub issue #138, the long-running frontend/control-state cleanup tracker. `ConfigStep.jsx` is no longer a single large settings surface: resume settings, embedded workshop settings, and collapsible settings framing now live in focused components.
- Kept the conservative Mantine workaround path intact while adding interaction coverage for the two riskiest Initial Translation state edges: selected project source language filtering and embedded workshop independent-mode defaults.
- Moved Agent Workshop run orchestration further backend-side, tightened validation scope handling, and preserved resume/polling behavior around backend run tasks.
- Hardened frontend payload recovery for wrapped array responses and malformed WebSocket messages so project management and incremental translation views fail more gracefully.
- Hardened proofreading key detection so patch-mode editing reports invalid key edits clearly and avoids loading proofreading data from stale or missing project/file records.
- Rebuilt the primary Proofreading experience around an entry-level row model. Source text, AI draft, and final translation now share one measured row, while TanStack Virtual keeps large localization files responsive. The legacy raw Monaco path has been removed so rows are the single reliable editing model.
- Preserved non-translation file structure in the row model: consecutive comments and blank lines are grouped into readable entries, comments can be edited with an explicit save/discard confirmation, and saving still patches values without changing keys or unrelated structure.
- Fixed false "modified" states caused by comparing existing disk translations with AI drafts or by treating Paradox escaped quotes as visible text. "Modified" now means the user changed the row during the current editing session, and quote round-trips no longer risk duplicate escaping.
- Simplified the proofreading layout with compact file selectors, localized column help, fully expanding long translations, one shared vertical scrollbar, and theme-aware high-contrast dropdowns across all five visual themes.
- Added advisory variable-integrity warnings that can always be explicitly overridden, session draft recovery, unsaved-change navigation guards, and an in-app Tauri close dialog.
- Added revision-based external file change detection and atomic saves. Remis now warns when another editor changes the file and refuses to overwrite a newer disk version.
- Added stable links from Project Validation and Agent Workshop directly to the affected proofreading entry, including correct resolution when historical translation versions contain the same relative filename.
- Localized the new proofreading, conflict, draft, and navigation surfaces across all 11 release locales.
- Added focused regression coverage for project tracking, initial translation settings, payload recovery, proofreading key handling, and provider removal paths.

## Compatibility Notes

- Removed Gemini CLI as a selectable translation provider. Google transitioned the individual/free/Google AI Pro/Ultra Gemini CLI experience to Antigravity CLI on June 18, 2026, so the old no-API-key Gemini CLI path can no longer be treated as a reliable Remis provider.
- Google Gemini API support remains available. Users who want to keep using Gemini models in Remis should select the Google Gemini provider and configure `GEMINI_API_KEY`.
- Existing saved projects that still reference `gemini_cli` now fail with an explicit removal message instead of silently falling back to another provider.

## UI And Setup

- Removed Gemini CLI from the frontend provider list, API settings grouping, setup guidance, and localized provider descriptions.
- Removed the old runtime probe that checked for a local `gemini` command during startup.
- Moved release notes out of the repository root and into `archive/release_notes/` so future patch notes have a stable home.
- Improved the Proofreading page typography, control sizing, scrolling behavior, loading transitions, and request race handling. Switching projects or files no longer surfaces stale 404 notifications from an earlier selection.

## Validation

- `npm run lint`
- `npm run test -- InitialTranslation.test.jsx`
- `npm run build`
- `npm test` (38 files, 126 tests)
- `python -m pytest tests/test_validation_sidecar_file_ids.py tests/test_routers_proofreading.py tests/test_proofreading_service.py tests/test_routers_projects.py tests/test_routers_agent_workshop.py -q` (54 tests)
- `python -m pytest tests/test_api_handler_provider_removal.py tests/test_initial_translation_run_service.py tests/utils/test_structured_parser.py -q`

## 中文

## 重点

本次版本有两项最重要的变化：

- **停止支持 Gemini CLI。** Remis 不再提供 Gemini CLI 翻译供应商。如果仍希望使用 Gemini 模型，可以继续使用 Google Gemini API 供应商并配置 `GEMINI_API_KEY`。
- **校对页面全面重构。** 新的逐条目编辑布局更加简洁工整，更容易浏览，在处理长文件时也更可靠；同时加入了未保存内容保护、会话草稿恢复、外部文件变更提醒，以及从格式校对问题直达对应条目的能力。旧的 Raw Monaco 编辑器已从校对流程移除，现在只保留一套清晰可靠的编辑方式。

简单来说：校对页面变得更好用、更安全，已经停止维护的 Gemini CLI 路径则被移除。

## 技术细节

- 收尾关闭 GitHub issue #138，也就是长期追踪的前端状态 / 控件技术债。`ConfigStep.jsx` 不再是一个巨大的配置面板：断点续传设置、嵌入式智能工坊设置、可折叠设置卡片已经拆到更清晰的组件边界中。
- 保留目前更稳的 Mantine 绕行方案，同时补了两个最高风险的 Initial Translation 交互测试：项目源语言不会出现在目标语言选择中，以及嵌入式智能工坊独立模式会正确继承主翻译 provider/model 默认值。
- Agent Workshop 的 run orchestration 继续向后端收敛，并加固 validation scope 与后端 run task 的恢复 / 轮询行为。
- 加固前端 payload recovery：包裹数组响应、畸形 WebSocket 消息现在不会轻易拖垮项目管理和增量翻译视图。
- 加固校对编辑器的 key 检测：补丁模式下的 key 修改会得到更明确的提示，同时避免从已失效或缺失的项目 / 文件记录中加载校对数据。
- 将“校对”主界面重构为 entry-level 行模型。源文本、AI 初稿和最终译文现在共享同一个实测行高；长文件由 TanStack Virtual 虚拟渲染。旧 Raw Monaco 编辑路径已移除，rows 成为唯一可靠的编辑模型。
- 将注释、空行和其他非键值结构纳入条目视图：连续注释与空行会合并成可读对象，注释支持编辑并在保存时明确选择保留或丢弃，同时保存仍只补丁式替换 value，不会修改 key 或无关文件结构。
- 修复“已修改”误报：页面不再把磁盘译文与 AI 初稿的历史差异，或 P 社格式中的转义引号差异，当成本次手动编辑。“已修改”现在只表示用户进入页面后确实改动了该条目，引号写回也不会重复转义。
- 精简校对页面：文件选择器压缩为一行，四列说明改为本地化问号提示，超长译文完整展开并统一使用页面主滚动条；五套视觉主题的下拉菜单也都有稳定的高对比配色。
- 新增可明确绕过的变量完整性警告、当前会话草稿恢复、未保存离开保护，以及符合 Remis 视觉风格的 Tauri 关闭确认框。
- 新增基于 revision 的外部文件变更检测和原子保存。其他编辑器修改文件后，Remis 会主动提示，并拒绝用旧页面内容覆盖较新的磁盘版本。
- Project Validation 与 Agent Workshop 现在可直接跳到具体校对条目；即使历史翻译版本中存在同名相对路径，也会优先定位当前精确文件。
- 新校对、冲突、草稿和导航文案已覆盖全部 11 个 release locale。
- 补充项目追踪、初始翻译设置、payload recovery、校对 key 处理和 provider 移除路径的聚焦回归测试。

## 兼容性说明

- 移除了 Gemini CLI 作为可选翻译供应商。Google 已在 2026-06-18 将个人 / 免费 / Google AI Pro / Ultra 的 Gemini CLI 体验迁移到 Antigravity CLI，旧的“无需 API Key、通过 Gemini CLI 调用”的路径不再适合作为 Remis 的稳定供应商。
- Google Gemini API 支持仍然保留。仍想在 Remis 中使用 Gemini 模型的用户，可以选择 Google Gemini 供应商并配置 `GEMINI_API_KEY`。
- 如果旧项目配置里仍保存着 `gemini_cli`，现在会得到明确的“已移除”错误提示，不会再静默回退到其他供应商。

## 界面与配置

- 从前端供应商列表、API 设置分组、配置向导和多语言供应商描述中移除了 Gemini CLI。
- 移除了启动阶段对本地 `gemini` 命令的旧探测逻辑。
- 将 release notes 从仓库根目录迁入 `archive/release_notes/`，以后 patch note 有固定位置，不再散落在根目录。
- 改善校对页面的字号、控件尺寸、滚动、加载状态与请求竞态处理；快速切换项目或文件时，不会再弹出属于上一个选择的陈旧 404 提示。

## 已验证

- `npm run lint`
- `npm run test -- InitialTranslation.test.jsx`
- `npm run build`
- `npm test`（38 个测试文件，126 项测试）
- `python -m pytest tests/test_validation_sidecar_file_ids.py tests/test_routers_proofreading.py tests/test_proofreading_service.py tests/test_routers_projects.py tests/test_routers_agent_workshop.py -q`（54 项测试）
- `python -m pytest tests/test_api_handler_provider_removal.py tests/test_initial_translation_run_service.py tests/utils/test_structured_parser.py -q`
