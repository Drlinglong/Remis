# Project Remis v3.1.1

Release candidate prepared on 2026-07-31.

Version 3.1.1 integrates the post-3.1.0 documentation, usability, maintainability,
and Steam Workshop publishing work into one release line. It is a patch release,
but it contains a substantial new local publishing workspace; final desktop and
installer smoke testing is still required before publication.

## English

### Highlights

- **A versioned Steam Workshop publishing workspace.** Create a publishing
  workspace with or without a linked Remis project or Workshop ID, maintain
  description and cover candidates, inspect their history, and explicitly mark
  the version currently selected for publishing.
- **Description preparation with reviewable history.** Configure a model for
  description generation, preview BBCode, preserve previous versions, and keep
  generation separate from selection. Model-backed generation remains an
  explicit user action and can incur provider cost.
- **A recoverable cover editor.** Build a 512 × 512 Workshop cover from
  backgrounds, flags, text, and custom images; save editable candidate versions,
  reload an earlier canvas, choose the active version, or download the PNG.
  Linked workspaces can reuse a project's original thumbnail, text can be edited
  directly on the canvas, and reset versus clear now have distinct behavior.
- **More faithful Steam BBCode preview.** Horizontal rules and Steam-style list
  items now render as separators and list entries instead of leaking BBCode into
  the preview. HTTP(S) and mail links render as safe, clickable links without
  injecting raw HTML.
- **A guided, predictable publishing workflow.** An in-product tutorial now
  covers workspace setup, cover editing, description preparation, and history.
  Workspace games are selected from Remis-supported profiles instead of entered
  as arbitrary text, and individual unselected history versions can be deleted.
- **A bundled publishing demo.** `Demo - 测试工作区` is installed once with the
  Victoria 3 demo project, its original 512 × 512 Remis thumbnail, and two
  prepared description versions; later user edits are not overwritten.
- **Readable themed workflows.** Semantic surfaces restore contrast throughout
  incremental translation and the API, prompt, and version settings pages,
  including the Byzantine, Medieval, and World War II themes.
- **Clearer navigation and project handoff.** Steam publishing is available as
  a dedicated workflow and from project management, while the former thumbnail
  and Workshop tools have been separated into focused screens.
- **More reliable localized UI.** The ten non-source locale packs no longer
  depend on a duplicate-value exception list, and the new Workshop navigation
  is present across all eleven supported locales.

### Maintainability and governance

- Split Agent Workshop backend orchestration into validation policy, run
  service, task projection, and router boundaries. The frontend run lifecycle
  now lives in a focused controller hook with dedicated tests.
- Extracted the initial-translation language selector from its configuration
  step and added focused selection tests.
- Reduced the legacy thumbnail and Workshop generator responsibilities instead
  of adding more behavior to oversized components. New production JavaScript,
  JSX, and Python modules remain within the repository architecture limits.
- Added product intent, developer contracts, and user guidance for project
  management, project tracking, thumbnail generation, and Steam Workshop
  publishing. Copilot help-pack registration now includes the project-management
  guide.
- Classified active documentation separately from historical implementation
  notes, and documented the approval boundary for high-risk Agent plans and
  Workshop writeback.

### Data, platform, and security

- Main database migration 11 adds publishing workspaces plus versioned
  description and cover assets. Migration 12 records one-time bundled seed
  installation so existing databases receive the canonical demo without
  overwriting later user edits.
- Restored the post-3.1.0 frontend and website validation baseline, including
  the ESLint security upgrade and current Python architecture ratchets.
- Made `run-dev.bat --check` genuinely non-mutating; launcher validation no
  longer terminates an existing stale Remis backend before reporting success.
- Dependabot now leaves ordinary version upgrades for deliberate maintenance
  while continuing to group security updates. Major dependency changes require
  manual review.

### Deliberate boundaries

- Remis does not upload to Steam in this release. Downloaded assets must still
  be uploaded by the user, and saving a candidate never modifies the original
  Mod or the Steam listing.
- The in-product Remis Copilot remains a hidden engineering preview in normal
  3.1.1 builds. The localhost Agent API and repository operator Skill remain the
  supported Agent integration.
- Ambiguous localization text remains for human review. Paid model calls,
  exports, deployment, and overwrite operations still require explicit user
  approval.

### Pre-release validation

- Backend: 668 tests passed, 1 skipped; Python architecture guard and source
  compilation passed.
- Desktop frontend: 550 tests across 145 files passed. Locale consistency,
  text encoding, lint (0 errors; 15 existing complexity/length warnings), and
  production build passed.
- Product website: 55 tests across 7 files passed; lint and production build
  passed.
- Rust/Tauri: formatting and locked dependency compilation passed.
- Release-version synchronization, all eleven locale JSON parses, and
  diff-integrity checks passed.
- Rendered theme checks passed for 20 incremental-workflow combinations and 15
  settings combinations. Live browser smoke covered the canonical demo,
  supported-game selection, the guided tour, project-thumbnail tooltip, narrow
  canvas text selection/drag/edit, protected history deletion, and clickable
  BBCode links. The restricted browser blocked the existing Google Fonts
  request, but no application runtime exception occurred.
- Installer packaging and the native Tauri Save As dialog still require the
  release operator's final desktop verification.
- No paid model call, export, deployment, Steam upload, or project-file
  overwrite was performed during integration.

## 中文

### 主要更新

- **新增版本化 Steam 工坊发布工作区。** 可以创建独立工作区，也可以关联 Remis
  项目或 Workshop ID；描述与封面均保留候选版本，并由用户明确选择当前采用版本。
- **让工坊描述可生成、可预览、可追溯。** 可配置描述生成模型、预览 BBCode、保留
  历史版本，并把“生成候选”与“采用版本”分开。模型生成仍是用户主动发起且可能产生
  供应商费用的操作。
- **新增可恢复的封面编辑流程。** 可用背景、旗帜、文字和自定义图片制作 512 × 512
  封面，保存可继续编辑的候选版本，重新载入旧画布，选择当前版本或下载 PNG。关联项目后
  可以直接复用项目原始封面，文本可在画布上直接编辑，“重置”和“清空”也有了明确区分。
- **改进 Steam BBCode 预览。** 分隔线和 Steam 风格列表项会正确渲染，不再把 `[hr]`
  或 `[*]` 等标记直接泄漏到预览中；HTTP(S) 与邮件链接会以安全、可点击的新窗口链接
  呈现，不注入原始 HTML。
- **补充可预测的发布引导。** 产品内教学覆盖工作区、封面、描述和版本历史；游戏改为从
  Remis 已支持列表中选择，未采用的单条封面或描述历史也可以删除。
- **内置标准发布 Demo。** `Demo - 测试工作区` 会一次性安装，绑定维多利亚 3 演示项目，
  使用项目原始 512 × 512 Remis logo 缩略图，并预置两份描述；用户后续编辑不会被覆盖。
- **修复主题化工作流的可读性。** 增量翻译以及 API、Prompt、版本信息设置页改用明确的
  语义表面；拜占庭、中世纪和二战主题中的文字与背景对比度已恢复。
- **整理发布入口和项目衔接。** Steam 发布成为独立工作流，也可从项目管理进入；原有
  缩略图与工坊描述工具被拆成职责更清晰的界面。
- **提高多语言界面可靠性。** 十个非源语言包不再依赖“重复译文允许列表”，Steam
  工坊入口也已覆盖全部十一种受支持语言。

### 可维护性与治理

- 将 Agent Workshop 后端编排拆成验证策略、运行服务、任务投影和路由边界；前端运行
  生命周期也抽取为独立控制器 hook，并配有聚焦测试。
- 从初次翻译配置步骤中抽出目标语言选择器，补充独立选择测试。
- 没有继续向超大组件堆叠职责，而是缩减旧缩略图与工坊生成器；新增 Python、JavaScript
  和 JSX 生产文件均受仓库架构上限约束。
- 补齐项目管理、项目跟踪、缩略图和 Steam 工坊的产品意图、开发契约与用户指南；
  Copilot 帮助语料也注册了项目管理说明。
- 区分当前有效文档与历史实现记录，并明确高风险 Agent 计划及 Workshop 写回的批准边界。

### 数据、平台与安全

- 主数据库迁移 11 新增发布工作区、描述版本和封面版本；迁移 12 记录一次性内置种子状态，
  让已有 3.1.0 数据库获得标准 Demo，同时不覆盖用户后续修改。
- 恢复 3.1.0 发布后的前端与官网验证基线，包括 ESLint 安全升级和当前 Python 架构棘轮。
- `run-dev.bat --check` 现在是真正的无副作用检查，不会在报告成功前终止已有的旧 Remis
  后端。
- Dependabot 继续合并安全更新，但普通版本升级改由维护者主动安排；主版本升级必须人工审查。

### 明确保留的边界

- 本版本不会直接上传到 Steam。下载后的素材仍由用户上传；保存候选版本不会修改原 Mod，
  也不会改动线上工坊条目。
- 产品内 Remis Copilot 在普通 3.1.1 构建中仍是隐藏工程预览。当前受支持的 Agent 集成
  仍是本机 Agent API 与仓库内 operator Skill。
- 含义不清的翻译文本继续交给人工审核；付费模型调用、导出、部署和覆盖仍需用户明确批准。

### 发布前验证

- 后端：668 项通过、1 项跳过；Python 架构门禁与源码编译通过。
- 桌面前端：145 个测试文件、550 项测试通过；语言包一致性、文本编码、lint（0 error，
  15 个既有复杂度／函数长度 warning）和生产构建通过。
- 产品官网：7 个测试文件、55 项测试通过；lint 和生产构建通过。
- Rust/Tauri：格式检查与锁定依赖编译通过。
- 发布版本同步、十一份语言 JSON 解析和差异完整性检查通过。
- 主题实渲染检查覆盖 20 组增量翻译组合和 15 组设置页组合；浏览器实机冒烟覆盖标准
  Demo、游戏下拉选择、产品教学、项目封面 tooltip、窄视口文字选择／拖拽／再编辑、
  历史删除保护和可点击 BBCode 链接。受限浏览器拦截了既有 Google Fonts 请求，但未出现
  应用运行时异常。
- 安装包构建和 Tauri 原生“另存为”窗口仍需发布操作者进行最终桌面验证。
- 集成期间没有发起付费模型调用、导出、部署、Steam 上传或项目文件覆盖。
