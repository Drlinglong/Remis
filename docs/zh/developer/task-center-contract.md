# Task Center 开发契约

本文把 [Task Center 产品意图](../product-intent-task-center.md)转换成当前实现边界，并记录主页任务摘要、项目活动流、任务历史和未来 Agent 消费运行状态时必须遵守的约束。普通操作见[任务中心用户指南](../user-guides/task-center.md)。

## 范围与信息架构

Task Center 包含四个不同表面：

| 表面 | 数据源 | 职责 |
|---|---|---|
| 顶栏抽屉 | `/api/tasks` | 当前可行动任务与最近一次成功任务 |
| 主页“正在进行的工作” | `TaskCenterContext` | 同一任务队列的最多 3 条摘要 |
| 任务详情 | `/api/tasks/{task_id}` | 阶段、结果、下一步、最小身份、事件和业务返回入口 |
| 全部日志 | `/api/tasks?include_archived=true` | 按日期分页的任务历史 |

主页“近期活动”不是任务系统。它来自 `/api/system/stats` 中的 `project_manager.repository.get_recent_logs(limit=10)`，内容是 `project_history` 的项目变化。产品目标是改称“近期项目变更”并收窄语义；不能另造一套任务状态。

## 当前登记的任务类型

当前代码调用 `task_state.create_task()` 登记：

- `initial_translation`
- `incremental_translation`
- `model_arena`、`model_arena_retry`
- `agent_workshop_scan`、`agent_workshop`、`agent_workshop_batch`
- `neologism_mining`
- `deployment`
- `glossary_health_check`、`glossary_merge`
- 内部 `dry_run`

`agent_registry` 还会把 Agent translation／repair 快照合并进同一查询。哪些短操作必须纳入 Task Center 尚无最终产品决定；新增类型前应先判断离开原页面后是否仍有跟踪价值。

子任务默认不出现在主列表。`include_children=false` 让一次用户动作由父任务代表；详情页再汇总子任务数量、活动数、注意数和平均进度。

## 持久化与查询

`task_state` 同时维护进程内快照和 `TaskRepository`。持久层使用：

- `background_tasks` 保存最新任务快照；
- `task_events` 保存递增序号事件；
- migration 004 建立任务与事件表；migration 006 和 007 补充摘要查询、诊断与保留策略索引。

列表页只读任务摘要，不加载事件，避免 N+1；详情页按 `task_id` 单独读取事件。持久化任务与遗留 Agent registry 快照按更新时间合并，不能让旧内存快照覆盖较新的数据库状态。

默认排序为 `updated_at DESC, created_at DESC`。按日期查询历史时按 `COALESCE(created_at, started_at)` 倒序，总数在分页前计算。

## 状态语义

API 归一化：

| 原始状态 | 通用状态 |
|---|---|
| pending / starting / queued | queued |
| running / processing / in_progress | running |
| awaiting_approval / waiting_approval | awaiting_approval |
| completed / complete / success | completed |
| failed / partial_failed | failed |
| cancelled / canceled | cancelled |
| interrupted | interrupted |

这里存在有意的通用展示压缩：`partial_failed` 进入 `failed` 注意队列。业务详情仍必须通过结构化 `result.metadata`、`summary_code` 或所属页面说明部分成功，不能让通用状态覆盖原始业务语义。未来若 Agent 需要区分，API 应新增结构化终态字段，而不是解析日志文本。

`active_count` 统计排队、运行和等待批准；`attention_count` 统计等待批准、失败、`partial_failed` 和中断。任务进入任一终态就停止执行，但不代表用户已经处理。

## 收件箱与“已处理”

`POST /api/tasks/{task_id}/archive` 只允许终态任务，写入 `archived_at`。未带 `include_archived=true` 的列表会排除它；历史页仍返回并标记“已处理”。

`POST /api/tasks/{task_id}/restore` 清空 `archived_at`。归档与恢复：

- 不改变任务 `status`；
- 不删除任务或事件；
- 不删除业务成果；
- 不允许归档活动任务。

产品允许“已处理”一键执行，因此这个动作不需要删除式确认。真正删除历史目前没有 API；未来若增加，必须单独命名、明确影响范围并要求确认。

## 列表刷新与恢复

`TaskCenterContext` 并行请求：

1. `active_only=true&limit=200`，取得活动或需要注意的父任务；
2. `status=completed&limit=1`，补最近一次成功任务。

它在挂载时刷新，页面可见期间每 4 秒轮询，切回可见状态或收到 `remis:task-created` 时立即刷新。抽屉再次按最近活动排序；主页从相同数组选择最多两条可行动任务和最近一次完成任务，总数不超过 3。

这保证主页任务摘要与 Task Center 共用事实源。不得让主页单独计算另一套状态或保存另一份已处理标记。

## 详情呈现契约

`TaskDetailPage` 当前展示：

- “阶段—结果—下一步”三栏摘要；
- 项目名称、游戏、任务流程、创建者、起止时间；
- 折叠的 `task_id` 与 `project_id`；
- 结构化结果、输出路径、checkpoint 和子任务汇总（若存在）；
- 默认折叠的用户事件日志，诊断事件按需加载／导出；
- 由 `source_route`、`workflow_context` 和 `project_id` 计算的业务返回入口。

当前不展示目标语言、供应商或模型。产品决定不是把完整进度页复制进来，而是维持最小身份：如果某类任务只靠项目、游戏和任务类型无法可靠区分，应在该类任务的结构化摘要中补一个短标签。完整配置仍由业务页面负责。

结构化 `stage_code`、`attention_reason_code` 和结果元数据优先。对旧任务的英文日志匹配只是兼容层；新流程不得继续依赖自由文本判断阶段。失败终态不得回显 “Translating” 等旧活动阶段。

## 操作与确认边界

当前通用 `allowed_actions` 只提供：

- 活动任务：`view_task`
- 失败／中断：`view_task`、`return_to_workflow`、`archive_task`
- 完成／取消：`view_task`、`archive_task`
- 已处理：`view_task`、`restore_task`

3.1.0 没有通用重试、取消、删除或整次重跑 API。此缺口符合“不同流程拥有不同参数与确认边界”的安全策略，但不代表未来永远不做。

若增加这些操作：

- 重试和整次重跑必须由所属业务流程重新校验输入；付费调用要求新确认与新幂等键；
- 取消必须确认，并只在工作流提供可靠取消语义时开放；
- 删除必须确认，且与“已处理”分开；
- 创建的新任务返回新 `task_id`，记录 `parent_task_id` 或等价来源关系；
- Task Center 不得伪造一个无法被执行层兑现的通用动作。

## 错误与事件

详情默认只返回 `audience=user` 事件。`include_diagnostics=true` 才包含诊断事件；导出文件显式标记是否含诊断，文件名中的任务 ID 会先清洗。

用户首屏不能只展示原始日志。工作流应提供：

- `stage_code`；
- 人能理解的结果摘要或 `summary_code`；
- 失败／注意原因及结构化代码；
- 安全的下一步路由；
- 可用时提供批次、文件或条目级影响数量。

3.1.0 没有跨页面失败弹窗。主页只在 `attentionCount > 0` 时显示注意提示；后续实现通知时必须去重、绑定准确 `task_id`，且不能自动重试。

## 与项目活动流的边界

`/api/system/stats` 的 `recent_activity` 读取项目历史，当前可能包含 `translate`、`source_advanced`、`path_registered`、`file_update` 等事件，因此视觉上会与任务列表重复。

目标契约：

- UI 文案改为“近期项目变更”；
- 只描述已持久化的项目事实，不展示实时百分比或“正在运行”；
- 不提供重试、取消或任务“已处理”操作；
- 同一后台任务可以产生一条项目结果事件，但活动流不复制任务阶段和诊断；
- 需要处理失败时链接准确任务详情，不能仅凭项目历史反推任务状态。

该 UI 收敛尚未实现，本轮只记录边界。

## Agent 消费边界

未来 Agent 可以读取 Task Center 的结构化摘要，回答项目当前运行状态，并提出下一步。它必须：

- 保留精确 `task_id`、`project_id` 和父子关系；
- 把 unknown 或缺失字段如实呈现，不从日志猜成确定事实；
- 区分执行终态与已处理状态；
- 不因具有读取能力而自动获得重试、取消、删除或修改成果权限；
- 任何会付费或改变数据的动作继续走所属业务流程确认。

Agent/Copilot 在 3.1.0 仍是内部／隐藏工程预览，不得向普通用户承诺已经开放。

## 当前差距

| 产品意图 | 当前实现 | 状态 |
|---|---|---|
| 失败时明显通知 | 只有页面注意提示，无独立弹窗 | 3.1.x 待完善 |
| 详情是摘要而非重复业务页 | 已有三栏摘要和最小项目身份，不含语言／模型 | 基本一致；逐任务观察辨识度 |
| “已处理”不删除 | `archived_at` 过滤，可从历史恢复 | 一致 |
| 重试、取消、删除、重跑必须确认 | 通用动作尚未实现，只返回所属流程 | 安全缺口，不是静默行为 |
| 最新任务优先 | repository 与抽屉按最近活动倒序 | 一致 |
| 主页不维护第二套任务状态 | “正在进行的工作”复用 Context | 一致 |
| “近期活动”只表达项目变化 | 数据确为项目历史，但名称和部分事件与任务近似 | 信息架构待收敛 |
| Agent 随时知道项目发生什么 | 已有结构化查询基础；普通用户 Agent 尚未开放 | 未来方向 |
| 进入 Task Center 的任务范围明确 | 当前已有长任务和部署等短任务 | 待玲珑确认 |

## 测试门禁

必须保留或补充：

1. repository 分页只加载摘要，排序、总数、active／attention 统计正确。
2. 持久化任务在内存清空或重启后仍可查，旧快照不覆盖新状态。
3. 父任务默认进入列表，子任务只在详情聚合。
4. 任务详情严格绑定请求的 `task_id` 和该任务自己的事件。
5. 诊断默认隐藏，显式请求和导出才包含。
6. `partial_failed` 进入注意队列，同时业务结果仍能表达部分成功。
7. 终态可标记已处理和恢复，活动任务归档返回 409。
8. Task Center Context 在定时、页面恢复可见和任务创建事件后刷新并清理监听器。
9. 主页与抽屉打开准确任务，不跳到共享或错误运行。
10. 失败终态不显示活动阶段；结构化代码优先于日志兼容匹配。
11. 未来新增重试、取消、删除、重跑时覆盖确认、新 ID 和作用域。
12. 主页项目活动流与任务流使用不同数据契约和文案。

## 代码证据

- `scripts/shared/task_state.py`
- `scripts/core/repositories/task_repository.py`
- `scripts/schemas/tasks.py`
- `scripts/routers/tasks.py`
- `scripts/routers/system.py`
- `scripts/react-ui/src/context/TaskCenterContext.jsx`
- `scripts/react-ui/src/components/tasks/TaskCenterDrawer.jsx`
- `scripts/react-ui/src/components/tasks/TaskSummaryCard.jsx`
- `scripts/react-ui/src/pages/TaskDetailPage.jsx`
- `scripts/react-ui/src/pages/TaskHistoryPage.jsx`
- `scripts/react-ui/src/pages/HomePage.jsx`
- `scripts/react-ui/src/components/RecentActivityList.jsx`
- `scripts/react-ui/src/utils/taskPresentation.js`
- `tests/test_tasks_api.py`
- `tests/core/test_task_repository.py`
- `scripts/react-ui/src/context/TaskCenterContext.test.jsx`
- `scripts/react-ui/src/components/tasks/TaskCenterDrawer.test.jsx`
- `scripts/react-ui/src/pages/TaskDetailPage.test.jsx`
- `scripts/react-ui/src/pages/TaskHistoryPage.test.jsx`
- `scripts/react-ui/src/pages/HomePage.test.jsx`
- `scripts/react-ui/src/components/RecentActivityList.test.jsx`
