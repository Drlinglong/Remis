# Project Remis v3.1.7

Released on 2026-08-29.

Version 3.1.7 adds reusable official translation libraries, improves Victoria 3
semantic context, and strengthens long-running desktop maintenance workflows.

## English

### Highlights

- **Reuse official translations without repeated scanning.** Remis can detect
  supported Paradox games installed through Steam and build local reference
  libraries from their official localization files. Initial and incremental
  translation reuse only exact key, source-text, source-language, and
  target-language matches, reducing model calls while preserving official
  terminology.
- **One maintenance workflow for every supported game.** Settings > System
  Maintenance now lets you review detected installations, choose which games
  to index, follow per-game progress, rebuild after an update, or completely
  remove one game's local reference library. Tasks continue in the background
  when the progress window is closed or another page is opened.
- **A non-blocking reminder before translation.** If the selected game has no
  reference library, initial translation explains the benefit and links to
  System Maintenance, while still allowing translation to continue normally.
- **Better Victoria 3 country-adjective context.** Country-adjective
  definitions and references receive language-aware semantic guidance while
  Paradox variables, tags, and formatting remain protected.

### Engineering quality and reliability

- Reference reuse is performed before model submission. Matches can be
  reviewed and excluded individually, remain separate in provenance and
  statistics, and are protected from glossary, proofreading, repair, and
  Workshop rewrite stages.
- Official layouts are handled per game, including `localization` versus
  `localisation`, Europa Universalis IV's flat UTF-8 BOM files, and Europa
  Universalis V's localization modules across multiple directories.
- Reference-library jobs use a single persisted background task with
  cross-page recovery, per-game success or failure states, and protection
  against concurrent SQLite writers.
- Removing a library deletes its binding, reference sets, and indexed entries,
  then compacts SQLite to return freed space to the operating system. A failed
  compaction is reported instead of being silently hidden.
- Desktop logs no longer record one INFO line for every successful or skipped
  progress push, and absent Steam manifests are treated as normal discovery
  results. Real metadata read failures and WebSocket delivery errors remain
  visible for support diagnostics.
- Archives, project history, the project sidebar, and Model Arena normalize
  supported collection payloads and safely ignore malformed records.
- Bundled demo repair fills only missing package files without overwriting user
  edits. Proofreading saves no longer fail when source keys are newer than an
  existing archive cache.
- Translation jobs containing unresolved human-review items cannot be approved
  for export.

### Data and compatibility

- Official game localization files are not bundled with Remis. Reference
  libraries are created locally from the user's own Steam installations and
  remain on the user's computer.
- Supported games are Victoria 3, Stellaris, Hearts of Iron IV, Europa
  Universalis IV, Crusader Kings III, and Europa Universalis V.

## 中文

### 主要更新

- **官方译文无需反复扫描即可复用。** Remis 现在可以检测 Steam 中已安装的受支持
  Paradox 游戏，并从官方本地化文件建立本地参考语料库。初次翻译与增量翻译只会
  复用 key、源文本、源语言和目标语言均完全匹配的条目，在保持官方术语的同时
  减少模型调用。
- **所有受支持游戏统一维护。** “设置 → 系统维护”现在可以检查自动探测到的安装
  目录、选择要建立索引的游戏、查看逐游戏进度、在游戏更新后重建，或完全删除
  某个游戏的本地参考语料库。关闭进度窗口或切换页面后，任务仍会在后台继续。
- **翻译前提供非阻塞提醒。** 如果当前游戏尚未建立参考语料库，初次翻译页面会
  说明用途并提供前往系统维护的入口；用户仍可选择不使用参考库并正常继续翻译。
- **改进 Victoria 3 国家形容词语义上下文。** 国家形容词定义与引用会按目标语言
  获得相应语义提示，同时继续保护 Paradox 变量、标签和格式。

### 工程质量与可靠性

- 官方译文复用在模型提交前完成。命中项可以预览并逐条排除，其来源与统计独立
  记录，并受到保护，不会被术语表、校对、修复或 Workshop 写回阶段改写。
- 按游戏分别处理官方目录布局，包括 `localization` 与 `localisation` 的拼写差异、
  Europa Universalis IV 平铺的 UTF-8 BOM 文件，以及 Europa Universalis V 分布在
  多个目录中的本地化模块。
- 官方参考语料库使用唯一且持久化的后台任务，支持跨页面恢复、逐游戏成功／失败
  结果，并防止多个任务同时写入 SQLite。
- 删除语料库会移除绑定、参考集合与全部索引条目，并压缩 SQLite，将释放的空间
  归还操作系统；如果空间回收失败，任务会明确报告，而不是静默隐藏。
- 桌面日志不再为每次成功或跳过的进度推送写入一条 INFO；Steam 库中不存在某款
  游戏的 manifest 也不再被误报为警告。真正的元数据读取失败和 WebSocket 发送
  错误仍会保留，方便用户上传日志后定位问题。
- 归档、项目历史、项目侧栏和 Model Arena 会统一规范受支持的集合 payload，并
  安全忽略畸形记录。
- 内置 Demo 修复只补齐缺失的包内文件，不覆盖用户修改；当源 key 比现有归档缓存
  更新时，校对保存也不再因此失败。
- 含有未解决人工复核项的翻译任务，在问题处理完成前不能批准导出。

### 数据与兼容性

- Remis 不会打包或分发游戏官方本地化文件。参考语料库只从用户自己的 Steam 游戏
  安装中在本机建立，并始终保留在用户电脑上。
- 当前支持 Victoria 3、Stellaris、Hearts of Iron IV、Europa Universalis IV、
  Crusader Kings III 和 Europa Universalis V。
