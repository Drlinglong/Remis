# Project Remis v3.2.0

Released on 2026-09-09.

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
  original mod files are not rewritten by the archive workflow. Workflow v3
  adds stale-release choices, published source evidence, traceable workflow
  telemetry, and a card-based terminology review surface.
- **Remis Agent and Copilot are available behind governed boundaries.** Copilot
  answers from the user-document corpus and exposes only the server-owned
  Action Registry. The localhost Agent API exposes capability discovery,
  preflight, task operations, and read-only published-context inspection. The
  assistant points API/model changes to Settings > Copilot Settings.
- **Meta AI Platform is available as a provider.** The provider catalog and
  setup flow include Meta's OpenAI-compatible endpoint and Muse Spark models,
  alongside the refreshed Gemini 3.8 model catalog.
- **Checkpoint resume now works at batch level for initial translation.** Each
  accepted successful batch is atomically saved before file reconstruction
  finishes. After a restart, only missing batches are sent to the provider
  again, provided the relative file path, batch range, source-entry mapping,
  source snapshot, and provider runtime still match. Failed or fallback batches
  are never reused. Starting a translation now checks the selected project for
  recoverable work automatically and opens a clear continue-or-start-over
  dialog when a compatible checkpoint exists. A resumed run is represented as
  a new visible task rather than a hidden child operation. A project-level clear
  action is available only when no translation is active.
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
- The archive A/B evaluation workbench is available only as a developer tool
  in Agent Preview with an explicit local flag. Its dry-run runner uses fake
  provider/judge adapters, preserves blind-review boundaries, and never
  writes production translations or calls a paid provider.
- Repair issues now carry stable identity and source/target snapshots, so stale
  or ambiguous requests are rejected before model-backed writeback.
- Initial-translation batch checkpoints use stable relative paths and source
  hashes, so same-named files in different directories cannot reuse one
  another's batches. Completed-file checkpoints remain readable and can be
  upgraded while retaining cumulative progress; incremental translation is
  outside this batch-level recovery contract.
- Checkpoint reads and writes remain independent: every run persists accepted
  progress, while starting a later run automatically discovers compatible
  recovery state and asks the user whether to continue or start over. Clearing
  a project's target-language slots is confirmation-gated and rejects active
  translations.
- Task Center and project task views now converge on cancelled and interrupted
  terminal states. Cancelled tasks persist their finish time, and successful
  zero-issue format validation is recorded as information rather than an error.
- Frontend dependency locks were refreshed to resolve the Browserslist,
  `@humanfs/node`, and nanoid security advisories included in the release scan.
- Agent documentation now records the token-safety rule: semantically
  meaningful Paradox tokens remain visible in complete source context, while
  only non-semantic serialization delimiters may be masked. The project
  creation dialog also has a tested theme-readable input treatment.

### Validation evidence

- Backend: `python -m pytest -q` — 1730 passed, 3 skipped (1733 collected); the
  suite emitted 357 existing deprecation warnings.
- Desktop frontend: `npm test -- --run` — 231 files and 934 tests passed; lint has
  0 errors and 13 existing maintainability/Fast Refresh warnings; production
  build passed.
- Product website: 9 files and 63 tests passed; lint and production build passed.
- Desktop and website dependency audits reported 0 known vulnerabilities after
  the release lockfile updates. Rust formatting and locked compilation passed.
- Python architecture guard, `python -m compileall -q scripts tests`, JSON
  parsing, focused Format Repair regression tests, and `git diff --check`
  passed.

### Known boundaries

- Agent direct context-analysis planning/start is not exposed. Start archive
  analysis from the normal Remis archive workflow and Task Center.
- Archive A/B review is not a production translation workflow. Enable it only
  in Agent Preview with `REMIS_ENABLE_ARCHIVE_AB_REVIEW=1`; missing persisted
  archive artifacts are reported explicitly instead of being fabricated from
  fixture text.
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
- Batch-level checkpoint recovery in this release covers initial translation.
  Do not treat it as equivalent support for incremental translation.
- The multilingual fixture validates deterministic detection and expected
  cases; it does not prove model quality for every language or provider. Run a
  real approved Format Repair smoke test before packaging.

## 中文

### 主要更新

- **项目档案馆在发布通道上线。** 完整档案分析会生成带源快照、人物／地点／组织／事件、
  provenance 和路由化上下文的不可变发布版本；可以从发布版本创建独立草稿。发布版本不会
  原地编辑，档案馆工作流也不会改写原始 Mod 文件。workflow v3 增加过期 release 选择、
  已发布源证据、可追踪工作流 telemetry 和卡片式术语审阅界面。
- **Remis Agent 与 Copilot 在受治理边界内上线。** Copilot 只从用户文档语料回答，并且只能
  使用服务端 Action Registry 中的 action。本机 Agent API 提供 capability、preflight、任务
  操作以及已发布档案的只读读取能力。需要修改小助手的 Provider、模型或 API 时，界面会引导
  用户前往“设置 → 小助手设置”。
- **支持 Meta AI Platform。** Provider 目录和设置流程加入 Meta OpenAI 兼容接口及 Muse
  Spark 模型，同时更新 Gemini 3.8 模型目录。
- **初次翻译支持批次级断点续传。** 每个成功且被接受的 batch 会在完整文件重建前原子保存。
  重启后只有缺失 batch 会再次调用 Provider，并且会校验稳定相对路径、批次范围、源条目映射、
  源快照和 Provider runtime 是否一致。失败或回退 batch 不会被复用。开始翻译时会自动检查所选
  项目是否存在可恢复进度；发现兼容 checkpoint 后，会弹出明确的“继续翻译／重新开始”对话框。
  续传会创建一个用户可见的新任务，不再隐藏为内部子任务。只有没有活动翻译时才允许清空项目
  checkpoint。
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
- 档案馆 A/B 评测工作台仅作为 developer-only 工具存在于 Agent Preview，并且必须显式开启本地
  开关。dry-run 使用 fake Provider／judge，保持盲评边界，不写入生产译文，也不调用付费 Provider。
- 修复问题现在携带稳定身份以及源文／译文快照；过期或有歧义的请求会在模型写回前被拒绝。
- 初次翻译批次检查点按稳定相对路径和源文 hash 保存，因此不同目录下的同名文件不会串用批次。
  已完成文件的旧 checkpoint 仍可读取并升级，同时保留累计进度；增量翻译不属于本次批次级恢复
  合同。
- checkpoint 的读取与写入保持解耦：每次任务都会保存本次已接受的进度；以后再次开始翻译时，
  Remis 会自动发现兼容的恢复状态，并询问用户继续还是从头开始。项目级清空需要确认，活动翻译
  期间会被拒绝。
- Task Center 与项目任务视图现在会正确收敛 cancelled 和 interrupted 终态。取消任务会持久化完成
  时间；格式验证为零问题时记录为普通信息，不再误报为错误。
- 本次发布扫描更新了前端依赖锁，修复 Browserslist、`@humanfs/node` 和 nanoid 对应的安全公告。
- Agent 文档补充 token 安全治理：有语义的 Paradox token 必须保留在完整源文上下文中，只有不承载
  语义身份的序列化分隔符允许遮罩；项目创建弹窗同时修复了主题下输入框的可读性，并加入契约测试。

### 验证证据

- 后端：`python -m pytest -q` —— 1733 项收集，1730 passed、3 skipped；测试套件产生 357 条
  既有 deprecation warnings。
- 桌面前端：`npm test -- --run` —— 231 个测试文件、934 个测试全部通过；lint 为 0 errors，
  保留 13 个既有的可维护性／Fast Refresh warnings；生产 build 通过。
- 产品官网：9 个测试文件、63 个测试通过；lint 与生产 build 通过。桌面端和官网更新锁文件后，
  依赖审计均为 0 个已知漏洞；Rust 格式检查和 locked 编译通过。
- Python 架构闸门、`python -m compileall -q scripts tests`、JSON 解析、格式修复定向回归测试
  和 `git diff --check` 均通过。

### 已知边界与发版注意事项

- Agent 尚不能直接规划／启动档案馆分析；请从 Remis 档案馆页面进入普通工作流，并以 Task
  Center 状态为准。
- A/B 评测不是生产翻译工作流，只能在 Agent Preview 设置 `REMIS_ENABLE_ARCHIVE_AB_REVIEW=1`
  后使用；缺少持久化档案 artifact 时会明确报告缺失，不会拿 fixture 说明文字冒充档案内容。
- 暂停仍不支持；取消是协作式取消，且只对 `/api/agent/capabilities` 声明的翻译任务类型开放。
- Copilot 尚无可任意串联“检查更新 → 新词挖掘 → 增量翻译 → 生成封面”的通用 DAG；应用重启后，
  内存中的聊天计划必须重新生成。
- 翻译、修复、导出和删除档案数据仍需明确批准。导出／覆盖路径和档案删除必须用真实持久化
  状态进行冒烟测试。
- 长文本档案分析中的实体归并、事件链连续性和来源污染仍需人工抽查；任务成功不等于档案内容
  已经适合直接用于翻译上下文。
- 新的精确结构契约层覆盖 Victoria 3、Crusader Kings III、Hearts of Iron IV、Stellaris 和
  Europa Universalis V。Europa Universalis IV 继续使用既有验证规则，不在本次新契约层覆盖范围内。
- 本版本的批次级 checkpoint 恢复只覆盖初次翻译，不应理解为增量翻译也具备同等能力。
- 多语言夹具验证的是确定性检测和预期案例，不代表每种语言或 Provider 的模型质量。打包前仍需
  用明确批准的真实格式修复流程完成一次冒烟测试。

### 发版前冒烟入口

详见 [3.2.0 发布冒烟与风险清单](../../docs/zh/developer/release-v3.2.0-smoke-test.md)。
重点覆盖 stable/preview 通道矩阵、重启恢复、重复恢复请求、项目并发锁、档案发布重试、Agent
批准门和导出边界。
