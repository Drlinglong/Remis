# Issue #198 项目档案失败恢复报告

日期：2026-08-04

工作树：`J:\V3_Mod_Localization_Factory-worktrees\3.1.1-issue-198-mod-context`

项目：`毒圣骑士- #198模组档案测试`

项目 ID：`d0939675-6803-4b30-ae6b-208cdb1aa6a7`

## 结论

第一次发布任务确实死在最后的发布步骤，而不是抽取或摘要阶段。第一次只存在于进程内存中的 4 批摘要正文无法原样取回；13:13 的恢复任务已经重新生成并持久化了完整的 29 条治理内摘要。

当前恢复边界是：下一次相同配置重试会复用 8 个抽取批次、1 个审核批次、9 个聚合批次和 4 个摘要批次。29 条摘要已经有在线数据库和独立救援快照两份副本，不需要再次调用供应商。

## 失败时间线

- 12:17:47：任务 `270b010d-a6cb-4296-b343-7caccfa5a2d0` 开始。
- 12:20:49：第一次失败。原始模型异常响应正文没有被保留；对应的非对象 contribution/evidence 容错和失败详情持久化已由提交 `bcd02157` 修复。
- 12:39:31：任务 `b06faa43-e5dd-4a32-a189-43dbe84cff6c` 使用同一分析运行恢复执行。
- 12:41:31：4 个摘要请求均返回 HTTP 200。
- 12:41:39：进度 99%，在 `publishing:1` 失败，错误为 `no such column: analysis_run_id`。
- 13:13:50：任务 `8a05a832-79d4-4a34-94db-94a10abc5e14` 恢复到发布阶段；4 个摘要批次保存 10 + 16 + 2 + 1 条，共 29 条，随后因发布层未识别治理排除项而失败。
- 13:16:40：创建一致性 SQLite 救援快照，SHA-256 为 `58E252DBBA4AA989F763E80D03F58A26D11E49704D7AC17FEAAB3E2939293969`。

第二次任务从连接到失败约 2 分 9 秒，但它复用了前一次中间结果，不能作为完整端到端性能数据。

## 数据完整性盘点

| 数据层 | 状态 | 数量/体积 |
| --- | --- | ---: |
| 源条目 | 可重建且快照一致 | 421 |
| local units | 可重建 | 201 |
| 抽取批次 | 已持久化、可恢复 | 8；428,786 bytes |
| 候选审核批次 | 已持久化、可恢复 | 1；825 bytes |
| 全局聚合批次 | 已持久化、可恢复 | 9；94,956 bytes |
| Contributions | 已持久化 | 1,237 |
| Aggregates | 已持久化 | 111 |
| Entity aggregates | 已持久化 | 94 |
| Event aggregates | 已持久化 | 16 |
| Project aggregate | 已持久化 | 1 |
| 术语候选缓存 | 已持久化 | 77 |
| 未发布草稿 | 已持久化 | 2 |
| 摘要正文 | 已持久化、可恢复 | 4 批；29 条 |
| Context release | 未创建，事务已回滚 | 0 |

77 个候选目前全部为 `pending`；其中频次为 1 的有 65 个，频次至少为 2 的有 12 个。候选缓存分类为 concept 25、place 16、faction 12、person 11、technology 11、other 2。

聚合层仍保留 94 个 entity aggregates。这是审计和证据层数量，不等于最终应该展示或注入 94 个实体摘要。后续基准应单独验证治理策略是否把低覆盖普通概念挡在摘要、词典和翻译上下文之外。

## 根因

Migration 19 负责为 `context_releases` 增加 `analysis_run_id` 并建立原子发布约束。旧实现完成 DDL 后执行了全数据库 `PRAGMA foreign_key_check`。数据库中已有与项目档案无关的历史孤儿引用，位于 `activity_log` / `project_history`；全局检查因此判定 migration 19 失败并回滚了新增列。

应用启动没有因为这项迁移回滚而停止，工作流仍按新代码运行。直到最终发布查询 `context_releases.analysis_run_id` 时才暴露缺列，形成“进度条跑满后失败”。

本次修复将 migration 19 的完整性检查限定到它实际创建和修改的 `context_release*` 表。历史无关外键债务不会被删除或伪装修复，同时项目档案自身的外键错误仍会阻断迁移。

## 已落地修复

1. 修复 migration 19 的检查范围，避免无关历史外键债务回滚项目档案 DDL。
2. 新增 migration 20，为 `synthesis` 建立正式批次状态和 SQLite 检查约束。
3. 新增独立 `ContextSynthesisExecutionService`，负责摘要规划、并发执行、恢复和持久化。
4. 每个成功摘要批次在模型返回后立即写入分析批次仓库；发布失败后的相同重试不再调用模型。
5. 摘要失败也会持久化错误类型和截断后的诊断信息。
6. 保留原子发布：release、聚合快照、摘要、投递关系、manifest、run 状态和 seal 仍在同一事务内完成。

运行中的 Dev 数据库现已应用：

- migration 19：`add_atomic_context_publication`
- migration 20：`add_context_synthesis_checkpoints`
- `context_releases.analysis_run_id` 已存在
- 原有 8 + 1 + 9 个成功批次和 111 个 aggregates 在迁移后保持不变

## 第二次发布失败根因

模型返回是完整的。治理层要求摘要的对象恰好为 29 个：12 个实体、16 个事件和 1 个项目；SQLite 中保存的结果也是 29/29，没有缺失、重复或越界引用。

其余 82 个 entity aggregates 本来就不应生成摘要，其中 71 个明确为 `summary_eligible=false`，11 个不是候选治理对象。`ContextReleaseAssembler` 没有把这项排除决定写入 aggregate payload，发布器沿用旧默认，把 82 个对象误报为“缺少摘要”。修复后每个 aggregate 都携带显式 `synthesis_required`，发布校验与发送给模型的名单使用同一契约。

救援快照：`recovery\issue-198\remis-synthesis-rescue-20260804-131640.sqlite`，14,667,776 bytes。

## 验证

- Context / Neologism 回归：148 passed。
- 迁移、发布、工作流聚焦回归：58 passed。
- Python architecture guard：passed。
- `python -m compileall -q scripts tests`：passed。
- `git diff --check`：passed。
- 本地后端健康检查：Remis 3.1.3，绑定 `127.0.0.1:1453`，`app_root` 指向 #198 工作树。
- Agent preflight：ready；当前版本和最新 Release 均为 3.1.3。

## 恢复操作与限制

没有自动发起下一次重试。相同配置下 4 个摘要批次已经持久化，工作流应直接恢复 29 条摘要并重新发布；若项目、source snapshot、scope 或配置指纹变化，Remis 会创建新运行并可能再次调用模型，因此仍由用户在 UI 中决定是否启动。

恢复成立的身份条件包括：项目、source snapshot、analysis scope 和配置指纹完全一致。若源文件或关键配置发生变化，Remis 会创建新运行并重新分析，这是数据安全行为。

本次恢复运行的模型用量报告只会统计重试后实际发生的调用，无法还原第一次任务已经消费但未持久化的完整 token/cost 元数据。因此恢复结果可以用于内容验收，不能作为完整端到端成本或时延基准。正式性能评估应使用一个新的隔离项目或新的分析配置，从零开始计时和采集用量。

## 仍需后续处理

- 后端重启后，`/api/tasks/b06faa43-e5dd-4a32-a189-43dbe84cff6c` 返回 Task not found；任务详情没有像分析批次一样可靠恢复。
- 恢复运行沿用了分析 run，但 `context_analysis_runs.task_id` 仍指向第一次任务 `270b010d-...`，任务追踪关系未更新。
- 数据库中保留一个失败事务前创建的 open draft；它没有发布内容，不影响恢复，但后续应增加失败草稿复用或清理策略。
- 历史 `activity_log` / `project_history` 外键债务仍存在。本次修复有意不在项目档案迁移中跨域删除旧数据。
- 12:41 的旧摘要正文无法逐字恢复；13:13 的替代摘要已经完整持久化并独立备份。
