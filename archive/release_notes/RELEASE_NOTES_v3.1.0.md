# Project Remis v3.1.0

Release candidate prepared on 2026-07-30.

Version 3.1.0 consolidates the work originally developed under the 3.0.8
feature branches. The minor-version increase reflects the breadth of the
workflow, data, and interface changes.

## English

### Highlights

- **A persistent Task Center.** Long-running work no longer disappears when you
  leave a page. See what is running, what needs attention, and what recently
  finished, then return to the exact task when you are ready.
- **Rebuilt glossary asset management.** Browse and maintain all glossaries in
  one place, review their health, copy or merge them, and manage project
  bindings with clearer safeguards.
- **The anonymous Model Arena.** Compare two or three models on representative
  text from your own Mod before committing to a full translation. Vote without
  seeing model names, then review and optionally share the results.
- **A calmer, more readable workflow.** Project pages now place the most useful
  next action first, make deployment available as soon as a usable translation
  exists, and reduce visual and decision-making friction across all five
  themes.
- **Navigation organized around the work.** The sidebar now groups mature
  features under Projects, Translation Workflow, and Quality & Terminology
  instead of hiding unrelated workflows under a generic More menu. Task Center
  and the global Remis assistant keep their separate roles.

### Technical details for maintainers

- Initial translation, incremental translation, proofreading, deterministic
  format scans, and Agent Workshop repairs now use persisted tasks with precise
  run details, structured outcomes, recovery paths, and project write-conflict
  protection.
- Agent Workshop protects localization keys, requires explicit provider/model
  confirmation, and records item-level repair results.
- Model Arena keeps runs and votes in an independent database and provides a
  privacy-aware export preview before anything is shared.
- Neologism review now preserves sessions across recoverable batch rejection
  and presents clearer source evidence.
- Project file rediscovery, stable file identity, lifecycle contracts, project
  monitors, and archive/deployment state handling were hardened.
- Semantic surface and contrast contracts were expanded across task, project,
  glossary, neologism, settings, and Workshop interfaces.

### Platform and security

- Upgraded the desktop frontend to React Router 8 and Vite 8, with Node.js
  22.22.0 or newer required for frontend development and release builds.
- Preserved the v3.0.7.1 provider-routing fixes: provider-specific credentials
  and endpoints, native Anthropic routing, and explicit failure for unsupported
  providers instead of silent fallback.
- Upgraded the main database through migration 10. Existing databases retain
  migrations 1 through 9 and receive the new lifecycle/status constraints
  incrementally.

### Pre-release validation

- Backend: 633 tests passed, 1 skipped; Python compilation passed.
- Desktop frontend: 459 tests passed; locale consistency, text-encoding
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

- **新增持久化任务中心。** 离开页面后，长时间运行的工作不再凭空消失。您可以
  随时查看正在运行、需要处理和最近完成的任务，并准确返回对应任务。
- **重做术语表资产管理。** 现在可以在统一入口浏览和维护全部术语表，检查健康
  状态、复制或合并词典，并通过更清晰的保护措施管理项目绑定。
- **新增匿名 Model Arena。** 在正式翻译整个 Mod 前，从自己的 Mod 中抽取代表性
  文本，对 2 或 3 个模型进行匿名比较；揭晓模型后还可检查并自愿分享结果。
- **让日常流程更易读、更省心。** 项目页面会优先展示最有用的下一步；只要已有
  可用译文，就能选择继续校对或直接部署。五套主题下的视觉层级和说明文字也得到
  统一改善，降低操作时的判断负担。
- **按照工作目标整理导航。** 侧栏现在以“项目”“翻译工作流”“质量与术语”
  组织成熟功能，不再把无关工作流藏在笼统的“更多功能”中；任务中心和全局
  Remis 小助手继续承担各自独立的职责。

### 面向维护者的技术细节

- 初始翻译、增量翻译、校对、确定性格式扫描和 Agent Workshop 修复统一接入持久化
  任务，提供精确运行详情、结构化结果、恢复路径和项目写入冲突保护。
- Agent Workshop 会保护本地化键，要求明确确认提供商与模型，并记录逐项修复结果。
- Model Arena 使用独立数据库保存运行与投票，并在分享前提供隐私感知的导出预览。
- 新词审查可从批量拒绝等可恢复状态继续，并保留会话及更清晰的来源证据。
- 加固项目文件重新发现、稳定文件身份、生命周期合同、项目监控以及归档/部署状态。
- 将语义表面和对比度合同扩展到任务、项目、术语表、新词、设置和 Workshop 界面。

### 平台与安全

- 桌面前端升级到 React Router 8 和 Vite 8；前端开发与发布构建要求 Node.js
  22.22.0 或更高版本。
- 保留 v3.0.7.1 的供应商路由修复：供应商专属凭据和端点、原生 Anthropic
  路由，以及对未支持供应商明确报错而非静默回退。
- 主数据库升级到迁移 10。现有数据库保留迁移 1 至 9，并增量应用新的生命周期/
  状态约束。

### 发布前验证

- 后端：633 项通过，1 项跳过；Python 编译通过。
- 桌面前端：459 项通过；语言包一致性、文本编码完整性、lint 与生产构建通过。
- 产品网站：55 项通过；lint 与生产构建通过。
- 发布 seed 只读取仓库内受审资产，严格限制为三个固定 Demo，并从首次初始化
  SQL 中排除任务、Arena、监控、活动日志和项目历史等运行期数据。
- 发布版本同步检查和差异完整性检查通过。
- 集成验证期间没有发起付费模型调用、面向用户的项目/模型导出、部署或项目文件
  覆盖操作。

正式发布前仍需由发布操作者完成 Windows 安装包构建、打包后端烟雾测试和最终
桌面渲染巡检。
