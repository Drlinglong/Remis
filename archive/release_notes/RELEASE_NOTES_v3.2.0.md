# Project Remis v3.2.0

Released on 2026-09-04.

Version 3.2.0 consolidates Project Archive, Remis Agent/Copilot, checkpoint
recovery, and the reliability fixes from the v3.1.8 baseline into one release
channel. The stable build and the isolated Agent Preview build use the same
governed workflows with separate ports and data directories.

## English

### Highlights

- **Project Archive is available in the released channels.** Full archive
  analysis produces immutable published releases with source snapshots,
  entities, events, provenance, and route-aware context. A new draft inherits
  from a selected release; published releases are not edited in place and the
  original mod files are not rewritten by the archive workflow.
- **Remis Agent and Copilot are available behind governed boundaries.** Copilot
  answers from the user-document corpus and exposes only the server-owned
  Action Registry. The localhost Agent API exposes capability discovery,
  preflight, task operations, and read-only published-context inspection.
- **Checkpoint resume is restored around Task Center state.** Interrupted
  translation tasks retain their checkpoint, validate source/configuration
  compatibility before resuming, and use idempotency keys to avoid duplicate
  child tasks. When a checkpoint is not compatible, users can start over while
  the original task remains recoverable.
- **Translation cancellation and recovery are explicit.** Supported
  translation tasks can be cooperatively cancelled; the runner stops new
  batches, completes the safe boundary, and releases the project lock. Fatal
  provider failures fail fast instead of repeating the same error indefinitely.
- **Release metadata and channel gates are aligned.** Stable is 3.2.0;
  Agent Preview is 3.2.0-agent-preview.1. Unknown build channels fail closed
  for Project Archive and checkpoint/resume.
- **Format Repair now protects exact game structure.** Victoria 3, Crusader
  Kings III, Hearts of Iron IV, Stellaris, and Europa Universalis V repairs
  preserve formatting identity, runtime tokens, boundaries, and nesting before
  a candidate can be written back.

### Engineering quality and reliability

- Format Repair distinguishes hard structural corruption from review-only
  variation. Source-side format anomalies, reasonable repeated-token
  reductions, and damaged localization keys remain outside automatic repair.
- The release includes a deterministic multilingual Victoria 3 regression
  fixture covering English, French, Polish, Russian, Simplified Chinese, and
  Turkish cases. The fixture is test-only and does not call a model or modify a
  real Mod.
- Repair issues now carry stable identity and source/target snapshots, so stale
  or ambiguous requests are rejected before model-backed writeback.

### Validation evidence

- Backend: `python -m pytest -q` — 1618 passed, 3 skipped (1621 collected).
- Frontend: `npm.cmd test -- --run` — 222 files and 887 tests passed; lint has
  0 errors and 13 existing maintainability/Fast Refresh warnings; production
  build passed.
- Python architecture guard, `python -m compileall -q scripts tests`, JSON
  parsing, focused Format Repair regression tests, and `git diff --check`
  passed.

### Known boundaries

- Agent direct context-analysis planning/start is not exposed. Start archive
  analysis from the normal Remis archive workflow and Task Center.
- Pause is not supported because there is no safe cooperative pause boundary.
  Cancel is cooperative and limited to the translation task kinds advertised
  by `/api/agent/capabilities`.
- Copilot does not yet provide a general DAG for update checks, neologism
  mining, incremental translation, and cover generation. Its in-memory plan
  must be regenerated after an application restart.
- Model-backed translation, repair, export, and archive removal remain
  approval-gated. Export/overwrite paths and archive deletion require careful
  smoke testing with real persisted state.
- Entity merging, event-chain continuity, and source contamination in long
  archive analyses remain quality-review concerns. A successful task status is
  not a substitute for reviewing provenance and representative stories.
- The new exact structure-contract layer covers Victoria 3, Crusader Kings III,
  Hearts of Iron IV, Stellaris, and Europa Universalis V. Europa Universalis IV
  continues to use its existing validator rules and is not covered by this new
  contract layer.
- The multilingual fixture validates deterministic detection and expected
  cases; it does not prove model quality for every language or provider. Run a
  real approved Format Repair smoke test before packaging.

## 中文

### 主要更新

- **项目档案馆在发布通道上线。** 完整档案分析会生成带源快照、人物／地点／组织／事件、
  provenance 和路由化上下文的不可变发布版本；可以从发布版本创建独立草稿。发布版本不会
  原地编辑，档案馆工作流也不会改写原始 Mod 文件。
- **Remis Agent 与 Copilot 在受治理边界内上线。** Copilot 只从用户文档语料回答，并且只能
  使用服务端 Action Registry 中的 action。本机 Agent API 提供 capability、preflight、任务
  操作以及已发布档案的只读读取能力。
- **断点续传围绕 Task Center 状态机恢复。** 中断翻译会保留检查点，恢复前校验源文件／配置
  快照兼容性，并通过幂等键避免重复创建子任务。检查点不兼容时可以选择“从头开始”，原任务
  仍可找回。
- **翻译取消与恢复语义明确。** 支持的翻译任务可以协作式取消：停止新增 batch，安全完成当前
  边界后释放项目锁。致命 Provider 错误会快速终止，不再无限重复同一种错误。
- **版本与通道门禁统一。** stable 为 3.2.0；Agent Preview 为 3.2.0-agent-preview.1。
  未知构建通道会对项目档案馆和断点续传采取 fail-closed。
- **格式修复现在保护精确的游戏结构。** Victoria 3、Crusader Kings III、Hearts of Iron IV、
  Stellaris 和 Europa Universalis V 的修复，在候选写回前会保留格式身份、运行时 token、
  边界和嵌套关系。

### 工程质量与可靠性

- 格式修复会区分“确定的结构损坏”和“需要复核的合理变化”。源文格式异常、合理的重复
  token 减少以及损坏的 localization key 不会进入自动修复。
- 本版本加入确定性的 Victoria 3 多语言回归夹具，覆盖英语、法语、波兰语、俄语、简体中文
  和土耳其语。夹具只用于测试，不调用模型，也不会修改真实 Mod。
- 修复问题现在携带稳定身份以及源文／译文快照；过期或有歧义的请求会在模型写回前被拒绝。

### 验证证据

- 后端：`python -m pytest -q` —— 1621 项收集，1618 passed、3 skipped。
- 前端：`npm.cmd test -- --run` —— 222 个测试文件、887 个测试全部通过；lint 为 0 errors，
  保留 13 个既有的可维护性／Fast Refresh warnings；生产 build 通过。
- Python 架构闸门、`python -m compileall -q scripts tests`、JSON 解析、格式修复定向回归测试
  和 `git diff --check` 均通过。

### 已知边界与发版注意事项

- Agent 尚不能直接规划／启动档案馆分析；请从 Remis 档案馆页面进入普通工作流，并以 Task
  Center 状态为准。
- 暂停仍不支持；取消是协作式取消，且只对 `/api/agent/capabilities` 声明的翻译任务类型开放。
- Copilot 尚无可任意串联“检查更新 → 新词挖掘 → 增量翻译 → 生成封面”的通用 DAG；应用重启后，
  内存中的聊天计划必须重新生成。
- 翻译、修复、导出和删除档案数据仍需明确批准。导出／覆盖路径和档案删除必须用真实持久化
  状态进行冒烟测试。
- 长文本档案分析中的实体归并、事件链连续性和来源污染仍需人工抽查；任务成功不等于档案内容
  已经适合直接用于翻译上下文。
- 新的精确结构契约层覆盖 Victoria 3、Crusader Kings III、Hearts of Iron IV、Stellaris 和
  Europa Universalis V。Europa Universalis IV 继续使用既有验证规则，不在本次新契约层覆盖范围内。
- 多语言夹具验证的是确定性检测和预期案例，不代表每种语言或 Provider 的模型质量。打包前仍需
  用明确批准的真实格式修复流程完成一次冒烟测试。

### 发版前冒烟入口

详见 [3.2.0 发布冒烟与风险清单](../../docs/zh/developer/release-v3.2.0-smoke-test.md)。
重点覆盖 stable/preview 通道矩阵、重启恢复、重复恢复请求、项目并发锁、档案发布重试、Agent
批准门和导出边界。
