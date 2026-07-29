# Project Remis v3.1.0

Release candidate prepared on 2026-07-29.

Version 3.1.0 consolidates the work originally developed under the 3.0.8
feature branches. The minor-version increase reflects the breadth of the
workflow, data, and interface changes.

## English

### Highlights

- Added a persistent Task Center with paginated history, per-run details,
  structured stage/result/next-step presentation, project identity, event
  history, and recovery links.
- Added task-backed initial and incremental translation flows, deterministic
  format scans, proofreading handoff, project write-conflict protection, and
  resumable review paths.
- Added the Agent Workshop format-repair workflow with explicit provider/model
  confirmation, protected localization keys, persisted repair tasks, and
  item-level repair results.
- Added the anonymous Model Arena for two- or three-model comparison, persisted
  runs and votes, privacy-aware export preview, and independent database
  history.
- Overhauled glossary asset management, project bindings, health review,
  duplication, safe batch deletion, and task-detail recovery.
- Completed the neologism review recovery flow, including recoverable batch
  rejection, session preservation, clearer source evidence, and theme-aware
  review surfaces.
- Added project file rediscovery, stable file identity, lifecycle status
  contracts, project monitors, and more reliable archive/deployment state.
- Expanded theme and contrast contracts across task, project, glossary,
  neologism, settings, and workshop surfaces.

### Platform and security

- Upgraded the desktop frontend to React Router 8 and Vite 8, with Node.js
  22.22.0 or newer required for frontend development and release builds.
- Preserved the v3.0.7.1 provider-routing fixes: provider-specific credentials
  and endpoints, native Anthropic routing, and explicit failure for unsupported
  providers instead of silent fallback.
- Upgraded the main database through migration 10. Existing databases retain
  migrations 1 through 9 and receive the new lifecycle/status constraints
  incrementally.
- Production dependency audits for both the desktop frontend and product
  website report zero known vulnerabilities.

### Pre-release validation

- Backend: 630 tests passed, 1 skipped; Python compilation passed.
- Desktop frontend: 442 tests passed; locale consistency, text-encoding
  integrity, lint, and production build passed.
- Product website: 55 tests passed; lint and production build passed.
- Rust/Tauri: formatting and locked dependency compilation passed using the
  repository's CI sidecar contract.
- Release seed generation reads only repository-reviewed assets, enforces the
  fixed three-Demo allowlist, and excludes runtime task, Arena, monitor,
  activity, and project-history data from first-run SQL.
- Release-version synchronization and diff-integrity checks passed.
- No paid model calls, user-facing project/model export, deployment, or
  project-file overwrite operation was performed during integration validation.

Windows installer packaging, a packaged-backend smoke test, and final rendered
desktop QA remain release-operator gates before publication.

## 中文

### 主要更新

- 新增持久化任务中心：支持分页历史、单次运行详情、结构化“阶段—结果—下一步”、
  项目身份、事件历史与恢复入口。
- 初始翻译和增量翻译全面接入任务合同，新增确定性格式扫描、校对交接、项目写入
  冲突保护和可恢复的审阅路径。
- 新增 Agent Workshop 格式修复工作流：明确确认提供商与模型，保护本地化键，
  持久化修复任务，并展示逐项修复结果。
- 新增匿名 Model Arena：支持 2 或 3 个模型对比、运行与投票持久化、隐私感知的
  导出预览，以及独立的数据库历史记录。
- 重做术语表资产管理、项目绑定、健康检查、复制、安全批量删除和任务详情恢复。
- 完成新词审查恢复流程，包括可恢复的批量拒绝、会话保留、更清晰的来源证据和
  适配主题的审查界面。
- 新增项目文件重新发现、稳定文件身份、生命周期状态合同和项目监控，并增强归档
  与部署状态的可靠性。
- 扩展任务、项目、术语表、新词、设置和 Workshop 界面的主题与对比度合同。

### 平台与安全

- 桌面前端升级到 React Router 8 和 Vite 8；前端开发与发布构建要求 Node.js
  22.22.0 或更高版本。
- 保留 v3.0.7.1 的供应商路由修复：供应商专属凭据和端点、原生 Anthropic
  路由，以及对未支持供应商明确报错而非静默回退。
- 主数据库升级到迁移 10。现有数据库保留迁移 1 至 9，并增量应用新的生命周期/
  状态约束。
- 桌面前端与产品网站的生产依赖审计均为 0 个已知漏洞。

### 发布前验证

- 后端：630 项通过，1 项跳过；Python 编译通过。
- 桌面前端：442 项通过；语言包一致性、文本编码完整性、lint 与生产构建通过。
- 产品网站：55 项通过；lint 与生产构建通过。
- 发布 seed 只读取仓库内受审资产，严格限制为三个固定 Demo，并从首次初始化
  SQL 中排除任务、Arena、监控、活动日志和项目历史等运行期数据。
- 发布版本同步检查和差异完整性检查通过。
- 集成验证期间没有发起付费模型调用、面向用户的项目/模型导出、部署或项目文件
  覆盖操作。

正式发布前仍需由发布操作者完成 Windows 安装包构建、打包后端烟雾测试和最终
桌面渲染巡检。
