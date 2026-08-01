# Project Remis v3.1.1

Released on 2026-08-01.

Version 3.1.1 brings the work completed after 3.1.0 together as a single desktop
release, led by a new local Steam Workshop preparation workflow.

## English

### Highlights

- **Prepare Steam Workshop releases in one place.** Create a publishing
  workspace, link it to an existing Remis project, prepare cover images and
  descriptions, keep useful revisions, and choose exactly which version is
  ready to publish.
- **Create and reuse Workshop covers more easily.** Build a cover from a
  background, flags, text, and custom images, or reuse the linked Mod project's
  original thumbnail. Text selection, dragging, editing, reset, clear, and PNG
  download now behave consistently.
- **Preview Workshop descriptions with confidence.** The preview more closely
  reproduces how BBCode will appear on Steam, including links, lists, and
  separators. Description history can be reviewed and individual unused
  versions can be removed.
- **Learn the workflow inside Remis.** A guided tour explains workspace setup,
  cover creation, description preparation, and version history. A ready-to-use
  demo workspace is included, and the game is selected from Remis-supported
  titles instead of entered manually.
- **Clearer and more readable screens.** Steam publishing has a dedicated entry
  point and can also be opened from project management. Incremental translation,
  API settings, prompt settings, version information, and the tutorial are now
  readable across the Byzantine, Medieval, and World War II themes.

### What existing users should know

- Existing local projects and databases are retained. Remis applies the new
  workspace data automatically and installs the demo only once without
  overwriting later edits.
- Remis prepares assets but does not upload them to Steam in this release.
  Saving a cover or description candidate does not modify the original Mod or
  its live Workshop listing.
- Model-backed description generation remains an explicit action and may incur
  provider charges. Ambiguous translations remain available for human review.

### Engineering quality and reliability

- Workshop descriptions are rendered through a restricted BBCode preview that
  supports safe HTTP(S) and email links without accepting arbitrary HTML.
- Publishing workspaces, description history, cover history, selected versions,
  and one-time demo installation are persisted through database migrations 11
  and 12. Protected or currently selected history entries cannot be deleted.
- Agent Workshop orchestration, translation language selection, cover editing,
  and publishing screens were separated into focused services, controllers, and
  components, with architecture limits retained for new production code.
- Documentation governance now distinguishes active user and developer guidance
  from historical implementation notes. Help content covers project management,
  project tracking, thumbnail generation, and Steam Workshop preparation.
- The development launcher check is non-mutating, dependency automation keeps
  security updates visible without forcing ordinary major upgrades, and all
  eleven interface languages include the Workshop navigation.
- The release date shown in Settings > Version Info now comes from release
  metadata. Packaging tests require the application version, release note date,
  and displayed Last Updated value to stay synchronized.

### Validation and installer

- Backend: 669 tests passed and 1 was skipped; Python architecture and source
  compilation checks pass.
- Desktop frontend: 550 tests across 145 files passed; locale and encoding
  checks, lint, and the production build pass. Product website validation from
  the integrated release candidate also passes.
- Rust formatting and locked dependency compilation pass. Theme rendering was
  checked across incremental translation and settings views.
- Desktop smoke testing confirmed the native Save As dialog and saved image,
  canvas text selection/drag/edit, demo persistence, protected history deletion,
  selected-version persistence, guided tour readability, and clickable BBCode
  links.
- No paid model call, Steam upload, deployment, or project-file overwrite was
  performed during release preparation.
- Windows installer: packaging details are recorded after the final build below.

## 中文

### 主要更新

- **在一个工作区内准备 Steam 创意工坊发布内容。** 可以创建发布工作区、关联现有
  Remis 项目、制作封面和描述、保留有用的历史版本，并明确选择准备发布的版本。
- **更轻松地制作和复用工坊封面。** 可用背景、国旗、文字和自定义图片制作封面，
  也可直接采用所关联 Mod 项目的原始缩略图。文字选择、拖拽、编辑、重置、清空和
  PNG 下载现在都有一致、明确的行为。
- **更放心地检查工坊描述。** 预览区域能更准确地还原 BBCode 在创意工坊页面下的
  显示效果，包括超链接、列表和分隔线等格式。用户可以查看描述历史，并删除不再需要
  且未采用的单条版本。
- **直接在 Remis 中学习新流程。** 新手引导会介绍工作区设置、封面制作、描述准备和
  版本历史；安装后还会提供一个可直接查看的演示工作区。创建工作区时，游戏改为从
  Remis 已支持的游戏中选择，无需手动填写 ID。
- **界面入口更清晰，各主题下也更易阅读。** Steam 发布既有独立入口，也可以从项目
  管理进入。增量翻译、API 设置、Prompt 设置、版本信息和新手引导在拜占庭、中世纪
  与二战主题下均恢复了清晰的可读性。

### 已有用户需要了解

- 已有本地项目和数据库会保留。Remis 会自动加入新的工作区数据，并且只安装一次演示
  工作区，不会覆盖用户之后的修改。
- 本版本负责准备发布素材，但不会直接上传到 Steam。保存封面或描述候选不会改动原始
  Mod，也不会修改线上工坊条目。
- 使用模型生成描述仍需要用户主动发起，并可能产生供应商费用。含义不清的翻译文本仍会
  留给人工复核。

### 工程质量与可靠性

- 工坊描述使用受限制的 BBCode 预览器，支持安全的 HTTP(S) 与邮件链接，同时不会接收
  任意原始 HTML。
- 数据库迁移 11 和 12 负责保存发布工作区、描述历史、封面历史、当前采用版本及一次性
  Demo 安装状态；受保护或当前采用的历史版本不能被删除。
- Agent Workshop 编排、翻译语言选择、封面编辑和发布界面被拆分为职责明确的服务、
  控制器与组件；新增生产代码继续遵守仓库的架构限制。
- 文档治理区分了当前有效的用户／开发者指南与历史实现记录；帮助内容覆盖项目管理、
  项目跟踪、缩略图生成和 Steam 工坊准备流程。
- 开发启动器检查现在不会修改运行状态；依赖自动化继续突出安全更新，但不会强制合入
  普通主版本升级；全部十一种界面语言均包含工坊入口。
- 设置 > 版本信息中的“最后更新”现由发布元数据统一提供。发布门禁会检查应用版本、
  Release Note 日期与界面显示日期保持一致。

### 验证与安装包

- 后端：669 项测试通过、1 项跳过；Python 架构检查和源码编译通过。
- 桌面前端：145 个测试文件中的 550 项测试通过；语言包与编码检查、lint 和生产构建
  通过。集成候选版本的产品官网验证也已通过。
- Rust 格式检查和锁定依赖编译通过；增量翻译与设置页面已完成多主题渲染检查。
- 桌面冒烟测试已确认原生“另存为”窗口和图片保存、画布文字选择／拖拽／编辑、Demo
  持久化、历史删除保护、采用版本持久化、新手引导可读性及可点击 BBCode 链接。
- 发布准备期间未发起付费模型调用、Steam 上传、部署或项目文件覆盖。
- Windows 安装包：最终构建完成后在下方记录打包信息。

## Final package / 最终安装包

- File / 文件：`remis-mod-factory_3.1.1_x64-setup.exe`
- Size / 大小：40,499,663 bytes (38.62 MiB)
- SHA-256：`D7C1E7DE50646B241FDE0B29BC71F6260D10F554A74FA0725A4B7254E742B906`
- Version resource / 版本资源：Product version `3.1.1`; file version `3.1.1`
- Frozen backend smoke / 冻结后端冒烟：passed on an isolated localhost port
- Code signing / 代码签名：not signed
