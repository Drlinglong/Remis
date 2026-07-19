# Project Remis v3.0.7

Release candidate refreshed on 2026-07-20 after installed-app smoke testing exposed two production-only startup failures. The replacement Windows installer is awaiting one final local install smoke test before the GitHub Release is published.

## English

## Highlights

- **Mine and review new terminology inside Remis.** The strengthened Neologism Tribunal finds source-grounded candidate terms, keeps them separated by project, and carries approved terminology into the project glossary.
- **Use Remis with Codex.** A repository-discoverable Remis Agent Skill and a governed localhost Agent API let Codex inspect projects, prepare plans, monitor jobs, read validation results, and request approved operations while Remis remains responsible for execution and every write.
- **Explore Remis on its new multilingual website.** The GitHub Pages site presents the product, engineering architecture, beginner guide, roadmap, Aventine evaluation work, and a dedicated Remis for Codex setup page.
- **See the engineering story directly in the repository.** The English and Chinese READMEs now explain the desktop architecture, controlled AI workflows, CI and security posture, and the Remis for Codex entry points.

## New Word Mining And Review

- The file picker and progress display use the backend's exact eligible source-file set, excluding project metadata, checkpoints, caches, and generated files.
- Mining forwards the selected project, provider, model, and target language, including LM Studio's `local-model` alias.
- Structured extraction is bounded, validated, and allowed one contextual repair attempt. Candidate evidence remains linked to the source text.
- Live progress is delivered over WebSocket with reconnection and task snapshot recovery. Completed runs open the Tribunal automatically; failed runs return to a retryable state.
- Review decisions distinguish project approval, known duplicates, and separate meanings. Approved project terminology takes precedence over selected game glossaries and the global glossary.
- Candidate storage is project-scoped and atomic, with one active mining run per project and idempotent approval handling.

## Remis For Codex

- Added the `/api/agent` contract for capability discovery, release and provider preflight, project inspection and import planning, translation plans, normalized job progress, persisted recovery snapshots, validation categories, bounded repair, export preview, deployment, and overwrite confirmation.
- Added a repository-discoverable Remis Agent Skill, `AGENTS.md`, bilingual Agent API quickstarts, and a Build Week demo guide.
- Added a dedicated `/codex/` website page with a focused installation prompt and first-run API-key guidance.
- Every consequential operation remains approval-gated. Paid translation, model-backed repair, export, deployment, and overwrite require explicit, plan-specific approval.
- Provider secrets remain in Remis Settings. The Agent contract does not ask users to paste API keys into chat.

## Website And Repository

- Added a React/Vite product website deployed through GitHub Pages, with dedicated Home, Engineering, Aventine, Guide, Roadmap, and Remis for Codex routes.
- Added all 11 Remis languages, lazy-loaded translation catalogs, localized page metadata, responsive layouts, accessibility and reduced-motion handling.
- Added product screenshots, animated engineering diagrams, vendor logo catalog, search metadata, sitemap, robots manifest, and route fallbacks.
- Updated the English and Chinese READMEs with the product architecture, controlled Agent workflow, download path, and developer entry points.
- Added GitHub Actions CI, dependency review, Dependabot configuration, contribution and security guidance, and a Pages deployment workflow.

## Reliability And Compatibility

- Fixed an installed-app white screen caused by a circular production chunk between React and Mantine. These UI dependencies now ship in one ordered chunk, and future circular-chunk warnings fail the production build.
- Fixed a packaged-backend startup crash caused by missing `genai_prices` package metadata. The hidden Copilot no longer loads as a normal packaged startup dependency, while Remis for Codex remains available through `/api/agent`.
- The release pipeline now starts the frozen `web_server.exe` on an isolated local port and requires a real `/api/health` response before Tauri packaging can continue.
- Frozen-backend smoke processes are cleaned up as a Windows process tree, and only the current-version NSIS installer is copied into the release output.
- Translation prompts now consistently honor persistent global instructions and project glossary context, including the Hunyuan provider path.
- SQLite foreign keys are enforced for managed connections, with migration coverage for project glossary bindings, stale metadata, indexes, and legacy databases.
- Local LLM connection diagnostics now distinguish host availability and provider errors more clearly.
- Updated supported Python and frontend dependency families and kept CI compatible with Python 3.10.

## Feature Availability

- **Included in v3.0.7:** Neologism Tribunal, Remis for Codex Agent/API integration, GitHub Pages website, README and engineering documentation updates.
- **Not exposed in the v3.0.7 desktop UI:** Remis Copilot / Remis Helper remains in development and is hidden behind the release feature flag.
- The in-app Copilot and approval-gated embedded Agent experience are planned for v3.0.8 after further product testing.

## Release Candidate Validation

- Branch integration, version synchronization, and the final build dependency alignment are merged into `main`.
- Backend: 440 tests passed and 1 was skipped locally; Python compilation and the focused Agent/startup/build-pipeline suites passed.
- Desktop frontend: 149 tests passed; lint and the production build passed.
- Website: 54 tests passed; lint, production build, GitHub Pages deployment, and live Home, Engineering, and Remis for Codex route checks passed.
- Rust/Tauri: formatting, locked dependency checks, release compilation, MSI packaging, and NSIS packaging passed.
- Fresh release executable: the frozen backend returned healthy, the WebView mounted the splash UI, and a reload produced no runtime exceptions or console errors.
- Security gates: CodeQL passed for Actions, JavaScript/TypeScript, Python, and Rust with all 26 release-review findings resolved. Dependency Review passed.
- Windows installer candidate: `remis-mod-factory_3.0.7_x64-setup.exe` (`41,847,090` bytes / `39.91 MiB`).
- SHA-256: `E13FE7A9EFDF4DD9B57991222147C827208BD4A3773393040BA17E526D434D0A`.
- The installer has version resources `3.0.7` and is not Authenticode-signed, so Windows may display an unknown-publisher warning.
- Final acceptance still requires the local installed-app smoke test before publishing the GitHub Release.

## 中文

## 重点

- **在 Remis 内挖掘和审判新术语。** 补强后的新词审判庭会从原文中提取有证据的候选术语，按项目隔离保存，并把用户批准的术语写入项目词典。
- **让 Codex 安全操作 Remis。** 仓库可发现的 Remis Agent Skill 与受控的本机 Agent API，让 Codex 可以检查项目、准备计划、追踪任务、读取校验结果并申请已批准的操作；真正执行工作和写入文件的仍然是 Remis。
- **通过新的多语言网站了解 Remis。** GitHub Pages 网站集中展示产品能力、工程架构、新手指南、路线图、Aventine 评估工作，以及专门的 Remis for Codex 配置页面。
- **直接从仓库看到完整工程故事。** 中英文 README 现已补充桌面架构、受控 AI 工作流、CI 与安全治理，以及 Remis for Codex 入口。

## 新词挖掘与审判

- 文件列表和进度统一使用后端确认的可挖掘源文件集合，排除项目元数据、检查点、缓存和生成文件。
- 挖掘任务会传递当前项目、Provider、模型和目标语言，包括 LM Studio 的 `local-model` 别名。
- 结构化提取流程有明确上限、严格校验，并允许一次携带上下文的修复重试；候选术语始终保留原文证据。
- 任务进度通过 WebSocket 实时推送，并支持断线重连和任务快照恢复。完成后自动进入审判庭，失败后恢复为可重试状态。
- 审判操作明确区分“批准到项目词典”“已有重复项”和“同词新义”。项目术语优先于已选游戏词典与全局词典。
- 候选数据按项目隔离并原子写入；同一项目仅允许一个挖掘任务运行，重复审批不会重复写入术语。

## Remis for Codex

- 新增 `/api/agent` 合同：能力发现、Release 与 Provider preflight、项目检查和导入计划、翻译计划、统一任务进度、持久恢复快照、校验分类、有界修复、导出预览、部署和覆盖确认。
- 新增仓库可发现的 Remis Agent Skill、`AGENTS.md`、中英文 Agent API 快速开始，以及 Build Week 演示指南。
- 网站新增专门的 `/codex/` 页面，提供聚焦的安装提示词与首次 API key 配置说明。
- 所有重要操作继续受审批门槛保护。付费翻译、模型修复、导出、部署和覆盖都需要针对当前计划的明确批准。
- Provider 密钥只保存在 Remis 设置中；Agent 合同不会要求用户把 API key 粘贴到聊天里。

## 网站与仓库展示

- 新增基于 React/Vite 的 GitHub Pages 产品网站，包含首页、工程、Aventine、新手指南、路线图和 Remis for Codex 独立页面。
- 网站支持 Remis 全部 11 种语言，并加入按需加载翻译目录、本地化页面 metadata、响应式布局、无障碍和 reduced-motion 处理。
- 新增产品截图、动态工程流程图、Vendor Logo 目录、搜索 metadata、sitemap、robots manifest 和路由 fallback。
- 中英文 README 已补充产品架构、受控 Agent 工作流、下载入口与开发者入口。
- 新增 GitHub Actions CI、依赖审查、Dependabot、贡献与安全说明，以及 Pages 部署工作流。

## 稳定性与兼容性

- 修复安装版白屏：生产构建曾把 React 与 Mantine 拆成相互依赖的循环 chunk，导致页面在 React 挂载前崩溃。现在两者会进入同一个有序 chunk，未来只要再次出现循环 chunk，production build 会直接失败。
- 修复打包后端启动崩溃：PyInstaller 曾漏打包 `genai_prices` 的包 metadata。隐藏中的 Copilot 不再作为普通安装包启动时的硬依赖，而 Remis for Codex 继续通过 `/api/agent` 提供。
- 发布流水线现在会在隔离的本机端口实际启动冻结后的 `web_server.exe`，只有 `/api/health` 返回成功后才允许继续 Tauri 打包。
- 冻结后端冒烟进程会按 Windows 进程树完整清理；release 输出也只复制当前版本的 NSIS 安装包。
- 翻译 Prompt 现在会一致应用持久全局指令与项目词典上下文，包括 Hunyuan Provider 路径。
- 受管 SQLite 连接会强制启用外键，并覆盖项目词典绑定、陈旧 metadata、索引和旧数据库迁移场景。
- 本地 LLM 连接诊断能更清楚地区分宿主服务状态与 Provider 错误。
- 更新受支持的 Python 与前端依赖家族，并保持 Python 3.10 CI 兼容性。

## 功能可用性

- **3.0.7 正式包含：** 新词审判庭、Remis for Codex Agent/API 集成、GitHub Pages 网站、README 与工程文档更新。
- **3.0.7 桌面界面暂不开放：** Remis 小助手 / Copilot 仍在开发中，并已通过发布功能开关隐藏。
- 应用内 Copilot 与需要审批的内置 Agent 体验计划在完成更多产品测试后，于 v3.0.8 上线。

## 发布候选版验证

- 分支整合、版本同步与最终构建依赖对齐均已合入 `main`。
- 后端：本地 440 项测试通过、1 项跳过；Python 编译以及聚焦的 Agent、启动与构建流水线测试通过。
- 桌面前端：149 项测试通过；lint 与 production build 通过。
- 网站：54 项测试通过；lint、production build、GitHub Pages 部署，以及线上首页、工程页和 Remis for Codex 路由检查均通过。
- Rust/Tauri：格式检查、锁定依赖检查、release 编译、MSI 打包与 NSIS 打包均通过。
- 全新 release 可执行文件：冻结后端健康检查通过，WebView 成功挂载启动界面，重载后没有运行时异常或控制台错误。
- 安全门槛：Actions、JavaScript/TypeScript、Python 与 Rust 的 CodeQL 均通过，发布审查中发现的 26 项告警已全部解决；Dependency Review 通过。
- Windows 安装候选包：`remis-mod-factory_3.0.7_x64-setup.exe`（`41,847,090` 字节 / `39.91 MiB`）。
- SHA-256：`E13FE7A9EFDF4DD9B57991222147C827208BD4A3773393040BA17E526D434D0A`。
- 安装包版本资源为 `3.0.7`，目前未进行 Authenticode 签名，因此 Windows 可能显示未知发布者提示。
- 正式发布 GitHub Release 前，仍需完成本地安装后的应用冒烟测试。
