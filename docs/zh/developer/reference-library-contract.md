# 官方参考语料库开发契约

本文记录 Issue #208 官方译文复用与系统维护任务的实现边界。产品决定见[产品意图](../product-intent-reference-library.md)，普通操作见[用户指南](../user-guides/reference-library.md)。

## 数据与匹配契约

`VanillaReferenceService` 使用应用数据目录中的 `vanilla_reference.sqlite`。`reference_sets_v2` 保存 `game_id`、游戏版本、根目录、统计指纹和内容指纹；`reference_entries_v2` 按 reference set、语言、逻辑文件身份和 key 保存文本及冲突标志；`active_reference_sets` 只为每个游戏选择一个活动集合。

解析保留 Paradox key 版本归一化、文件身份和重复项冲突。解析器不得把多文件扁平化成简单 `key -> text` 映射。

翻译前的唯一有效查询语义是：

```text
lookup(key, source_language, canonical_source_text, target_language)
```

源 key、源语言、规范化源文本和目标语言都满足时才命中。源或目标侧冲突、目标语言缺失、源文不同都不命中。相同源／目标文本是合法译文，不再作为“翻译失败”的安全带重新送模。

## 游戏档案与目录发现

Steam app id、安装目录名和官方本地化布局属于游戏档案元数据，不得在不同模块复制第二份常量。`official_localization_globs` 与 Mod 使用的 `source_localization_folder` 是不同概念：Victoria 3／CK3 使用 `game/localization`，Stellaris／HOI4／EU4 使用安装根目录的 `localisation`，EU5 则聚合 `game`、`jomini`、`clausewitz` 下的多个 `localization` 模块。

语言文件布局也不能假设统一：较新的游戏通常使用 `localization/<language>/*.yml`，EU4 则把 UTF-8 BOM 文件平铺在 `localisation` 根目录，并以 `*_l_<language>.yml` 区分语言。索引器必须同时支持两种布局，且不得以宽松解码掩盖错误的游戏档案编码。

自动发现只解析 Windows Steam 注册表、`libraryfolders.vdf` 和对应 `appmanifest_*.acf`，验证安装目录与游戏档案规定的本地化目录。它不得启动 Steam、遍历整块磁盘或接受任意 Mod localization 目录。`POST /api/system/reference-library/discover` 只读并返回候选，不启动建库。

Steam 库中没有某个受支持游戏的 `appmanifest` 是正常的负匹配，必须静默跳过；只有元数据路径实际存在但无法读取或解码时才记录警告。

## 维护任务 API

当前主要契约：

| 方法 | 路径 | 语义 |
|---|---|---|
| `GET` | `/api/system/reference-library` | 游戏档案、活动库状态及可用时的活动维护任务 |
| `POST` | `/api/system/reference-library/discover` | 只读返回自动检测候选 |
| `POST` | `/api/system/reference-library/jobs` | 对用户确认的 `operations` 启动批量建立／更新任务 |
| `GET` | `/api/system/reference-library/jobs/active` | 恢复当前活动维护任务 |
| `GET` | `/api/system/reference-library/jobs/{task_id}` | 读取准确任务快照 |
| `DELETE` | `/api/system/reference-library/libraries/{game_id}` | 启动该游戏的完整本地语料删除任务 |

旧的 `/auto-build` 和 `/build` 路由暂时保留，但必须进入同一个任务锁，不能绕过并发保护。

任务 `kind` 为 `reference_library_maintenance`，全局 dedupe key 为 `reference-library-maintenance`。`task_state` 和 `background_tasks` 保存任务快照；重复启动返回已有 `task_id`。页面挂载时先查活动任务，因此 React 局部 `loading` 状态不是互斥或恢复机制。

应用进程退出后，daemon worker 不可恢复；下次启动 hydration 必须把仍处于活动状态的 `reference_library_maintenance` 孤儿任务持久化为 `interrupted`，释放 dedupe，让用户可以安全重试。

逐文件进度更新属于高频传输事件：成功推送或没有订阅者时只允许写 DEBUG，连接建立／断开可写 INFO，真实发送异常写 ERROR。不得让一次大型索引用正常进度记录淹没桌面诊断日志。

## 进度与终态

`progress.games[]` 至少包含：

- `game_id`、`game_name`、`localization_path`；
- `stage` 与 `status`；
- `files_current` / `files_total`；
- `entries_current` / `entries_total`；
- 当前文件和安全的错误摘要。

索引器在收集文件、逐文件解析、激活和完成阶段调用进度回调；维护服务把更新持久化并推送。总进度由各游戏进度聚合，不允许只在一个游戏结束时跳变。

终态为 `completed`、`partial_failed` 或 `failed`。`partial_failed` 是终态，前端必须停止轮询并逐游戏显示结果；不能归一化成成功。成功游戏已经激活的库可继续使用。

## 更新、原子性与删除

建立新指纹集合后才切换活动绑定。显式强制重建同一指纹时，旧集合的删除与新集合写入在同一个 SQLite 事务内完成，失败应回滚，不能把半成品激活。

删除操作在事务中按以下范围执行：活动绑定、该 `game_id` 的所有 `reference_entries_v2`、该游戏的所有 `reference_sets_v2`。事务提交后执行 SQLite `VACUUM`，将空闲页归还文件系统。若数据删除成功但压缩失败，必须保留真实警告并把维护任务标记为失败，不能假装已完成完整空间回收。不得根据用户提供的路径删除磁盘文件；游戏目录只读。

数据库写操作共享进程级全局锁，同时由持久化任务 dedupe 拒绝第二个活动任务。两层保护分别防止并发请求竞态和 SQLite 双写。

## 前端职责边界

- `ReferenceLibraryMaintenanceCard` 只组合状态和展示入口；API、轮询与恢复由独立 hook 管理；
- 自动检测必须先显示候选确认弹窗，用户确认后才 POST jobs；
- 任务弹窗按游戏显示路径、阶段、文件／条目进度和错误；
- 切页再回来恢复活动任务，不自动重新 discover 或 start；
- 删除使用独立确认弹窗，明确“删除 Remis 本地索引，不碰游戏文件”；
- 手动选择仍按游戏档案验证 Steam 游戏根目录及全部官方 localization roots，不能在 UI 假设统一路径或只显示 EU5 的一个模块。

## 测试门禁

1. 自动发现覆盖 Steam library 转义、非 ASCII 路径、manifest 缺失／损坏、重复 app id、安装根目录 `localisation` 和 EU5 多模块聚合。
2. 页面挂载不自动扫描；点击检测先出候选，确认后才启动任务。
3. 一次 jobs 请求处理所有选中游戏。
4. 并发重复请求返回同一活动 `task_id`，只运行一个写入 worker。
5. 逐文件进度和条目数写入持久化快照；页面卸载／重挂载能恢复。
6. `partial_failed` 停止轮询，成功与失败游戏分别展示。
7. 强制重建同指纹真正替换集合，失败不激活半成品。
8. 删除一个游戏会清除其绑定、集合和条目，但保留其他游戏且不触碰源目录。
9. 初次／增量翻译对 reference 命中、冲突、缺目标语言和 opt-out 行为一致。
10. locale JSON、文本编码完整性、前端测试／lint／build、Python architecture guard 和全量 pytest 均通过。

## 代码证据

- `data/config/game_profiles.json`
- `scripts/core/services/paradox_installation_discovery.py`
- `scripts/core/services/reference_library_service.py`
- `scripts/core/services/vanilla_reference_service.py`
- `scripts/shared/task_state.py`
- `scripts/routers/system.py`
- `scripts/schemas/reference.py`
- `scripts/react-ui/src/components/settings/ReferenceLibraryMaintenanceCard.jsx`
- `scripts/react-ui/src/hooks/useReferenceLibraryMaintenance.js`
- `tests/test_reference_library_maintenance.py`
- `tests/test_vanilla_reference_service.py`
