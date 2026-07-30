# 智能工坊开发契约

本文把[智能工坊产品意图](../product-intent-agent-workshop.md)转换成实现契约，并区分
3.1.0 已实现行为、高风险差距和后续测试门禁。当前操作见
[智能工坊用户指南](../user-guides/agent-workshop.md)。

## 范围

智能工坊包含：

- 初次／增量翻译后的 sidecar 问题导出；
- 默认启用的内嵌扫描和修复；
- 独立格式修复台的项目扫描、单条修复与后台批量修复；
- 模型调用、有限反思重试、确定性验证；
- 逐条文件写回、修复报告、剩余问题与 Task Center 状态。

不包含文风校对、术语管理、整文件重翻、key 修复或部署。

## 当前入口

- 侧栏“质量与术语 → 格式修复台”，路由 `/agent-workshop`；
- 初次翻译和增量翻译高级设置中的内嵌格式修复；
- 项目格式问题入口和 Task Center 的返回工作流入口；
- API 前缀 `/api/agent-workshop`。

主要接口：

| 接口 | 当前行为 |
|---|---|
| `GET /load-cached` | 读取当前项目／sidecar 的未解决问题 |
| `GET /scan` | 使用缓存或强制扫描，并创建 `agent_workshop_scan` 任务记录 |
| `POST /fix` | 确认后修复并立即写回单条 |
| `POST /fix-batch` | 确认后同步修复并写回一批 |
| `POST /fix-run` | 创建后台父任务，分批并发修复和写回 |

前端常规批量入口使用 `/fix-run`；单条弹窗使用 `/fix`。

## 检测与问题 sidecar

`WorkshopIssueExportService` 和 `PostProcessValidator` 根据源译文对照、游戏规则及动态标签
生成 `workshop_issues.json`。问题记录包含文件、key、行号、源文、当前译文、错误代码、
目标语言、来源和尝试状态。

当前主要可修类别包括：

- 变量数量／内容不一致；
- 颜色和格式标签不一致；
- 源语言标点残留；
- 其它验证器返回的 error 级格式问题。

扫描还会单独解析正常 parser 拒绝的损坏 key，并报告
`validation_invalid_key_format`。这类记录没有可靠的正常 key 定位，产品规则要求只报告，
不进入模型修复。

缓存扫描结果可以加快打开速度；用户要求重新扫描时，必须按当前翻译目录重建 sidecar，
删除已经不存在的陈旧假阳性。扫描不得修改翻译文件或调用模型。

## 内嵌工坊

初次翻译：

- `EmbeddedWorkshopConfig` 未提供时，服务默认
  `enabled=true`、`follow_primary_settings=true`；
- 每个目标语言先导出问题，再执行 `run_embedded_workshop()`；
- 没有活动问题时直接返回，不初始化模型。

增量翻译在收到启用的 `embedded_workshop` 配置时执行同一服务；当前前端默认开启并提交
配置。默认继承主翻译供应商、模型、批大小、并发和 RPM；关闭 follow-primary 后才读取
独立工坊设置。

内嵌服务把问题分批，按并发与 RPM 调度 `ReflexionFixAgent.fix_batch_loop()`。只对返回
`SUCCESS` 的项目调用 `_apply_translation_fix_to_file()`，然后重新导出问题 sidecar，报告
`detected_count`、`fixed_count`、`failed_count` 和 `remaining_count`。

## 独立工坊确认与任务治理

`WorkshopRepairApproval` 必须与以下字段精确一致：

- `approved=true`
- `issue_count`
- `api_provider`
- `api_model`

不一致返回 409 `approval_required`，并说明该操作会写项目翻译文件且可能产生模型费用。
确认范围还应在 UI 中展示项目；后端项目 ID来自请求和任务 fingerprint。

`FixRunRequest` 还要求 8–128 字符幂等键。相同键和相同 fingerprint 返回原任务；相同键
绑定不同项目、配置或问题列表时返回冲突。项目级
`project_translation_write:{project_id}` 去重锁阻止同一项目出现冲突写任务。

后台父任务 kind 为 `agent_workshop`，子批次为 `agent_workshop_batch`。批量限制：

- batch size：1–50，默认 10；
- concurrency：1–5，默认 1；
- RPM：至少 1，默认 40；
- 每条问题最多尝试 1–5 次，前端当前固定提交 3。

父任务最终为 `completed` 或 `partial_failed`；批次异常可为 `failed`。结果包含成功／失败
数量、逐条结果、尝试摘要和报告路径。

## 模型修复与验证

`ReflexionFixAgent.fix_batch_loop()` 每轮只处理尚未通过的问题：

1. 第一次根据错误、源文和损坏译文生成候选；
2. 用 `PostProcessValidator.validate_entry()` 验证；
3. 通过的条目退出活动集合；
4. 后续轮次为剩余条目生成诊断 reflection，再调用模型；
5. 达到 `max_retries` 后返回 `FAILED`。

目标产品契约要求 prompt 只做最小必要格式修复。源文用于恢复变量、标签和目标语言标点，
不能成为主动纠正错译或润色的授权。

## 逐条写回

当前 `apply_translation_fix_to_file()`：

1. 解析目标文件并按完整 key 或去掉版本号后的 base key 找行；
2. 读取整个文件；
3. 只替换该行第一对／最后一对引号之间的译文；
4. 以 `utf-8-sig` 重写文件。

独立工坊随后读回该 key，并再次运行验证。成功时把 ValidationLogger 状态改为 `fixed`，
写入 `.agent_workshop_reports` 报告；失败时记下 failure reason 和最后候选。

产品要求将一次条目修复视为小事务：

```text
旧译文
  → 生成候选
  → 候选内存验证通过
  → 写入目标 key
  → 读回相同
  → 最终验证通过
       ├─ 是：提交并标记 fixed
       └─ 否：恢复旧译文并标记 failed
```

不得写原始 Mod 或创意工坊文件。目标路径必须解析到项目登记的翻译输出目录。

## Issue #34 与标点规则

[Issue #34](https://github.com/Drlinglong/Remis/issues/34) 已关闭。当前实现包含：

- 翻译构建阶段的源语言标点检测／清理；
- `PostProcessValidator._check_residual_punctuation()`；
- 工坊 `validation_residual_punctuation_found` 呈现；
- 英文目标的工坊 prompt 标点规则；
- 目标语言参数向验证器传递。

规则必须基于源语言和目标语言，只处理残留源语言标点，并保护 `$...$`、`[...]`、`§...§!`
等游戏语法。不能把旧 Issue 中面向中文到英文的示例扩张成无条件全局替换。

## 当前高风险差距

### 1. Prompt 越过产品范围

`ReflexionFixAgent._build_batch_prompt()` 当前允许三类模式：

- format repair；
- failed-chunk recovery；
- limited source-aware revision。

它还明确允许纠正明显误译、极性、强度、遗漏和生硬表达。后两类超出玲珑确认的产品范围：
智能工坊只应处理规则检出的格式问题，不承担语义修订。

**目标修复**：删除语义重写授权；prompt 只允许为恢复被验证规则要求的变量、标签、结构和
标点而做最小修改。增加测试，确保无格式错误的普通译文不会进入或被工坊改写。

### 2. 最终校验失败没有回滚

`_apply_fix_with_confirmation()` 当前先调用 `apply_translation_fix_to_file()`，然后读回并做
最终验证。若读回缺失、不一致或最终验证失败，函数返回失败并更新日志，但不会恢复旧行。
测试 `test_fix_batch_marks_post_validation_failure_with_diagnostics` 也没有锁住文件回滚。

这与“所有格式错误解决后才自动写回”冲突，并可能把失败候选留在项目译文中。

**目标修复**：写前验证候选；写入采用临时内容／原值快照；读回或最终验证失败时恢复旧值。
测试必须断言失败后文件仍为原译文。

### 3. 单条“应用修复”文案与真实时序不一致

单条前端点击“分析并修复”时，`requestAgentWorkshopIssueFix()` 已携带批准并调用 `/fix`；
后端成功响应前已经写回文件。结果弹窗之后显示的“应用修复”按钮只关闭弹窗并从问题列表
移除，没有再次写文件。

这不是产品要求的逐条人工批准，但当前文案会让用户误以为结果仍是预览。

**目标修复**：把操作表述为“确认并自动修复”，结果页表述为“已修复／关闭”；或者拆分
真正的 preview API。按产品决定，前者更符合无需浪费用户时间的定位。

### 4. 损坏 key 仍可触发 AI

扫描和 UI 正确识别损坏 key，人工校对入口会提示无法按 key 跳转；但“AI 修复”按钮仍然
显示。请求可能产生费用，之后才因 parser 无法定位 key 而写回失败。

**目标修复**：`validation_invalid_key_format` 不进入批量 issues，单条 AI 修复按钮禁用，
直接提示“Remis 不能自动修 key”。

### 5. 独立与内嵌写回保障不统一

独立路径有读回和最终验证，内嵌路径只在模型候选验证通过后写入，再通过重新扫描统计剩余
问题；两者都直接重写文件，没有统一的原值回滚事务。

**目标修复**：提取单一的安全条目写回服务，统一路径约束、候选验证、原值快照、写入、
读回、最终验证和失败回滚。

### 6. 写回目标缺少目录硬边界

`_resolve_issue_target_path()` 当前优先接受请求中任何存在的 `file_path`；随后才查找项目
`translation_dirs`，最后还会回退到 `project.source_path / issue_file_name`。正常 UI 扫描生成的
路径通常位于翻译输出目录，但后端没有 containment 检查来证明目标一定属于登记的翻译成果。

这与“绝不能修改原始 Mod 或创意工坊文件”的产品边界冲突，也使 API 调用者能够扩大批准
范围。

**目标修复**：忽略客户端提供的任意绝对路径，使用项目登记的 translation root 与规范化
相对路径重新解析；`resolve()` 后验证目标仍位于允许根目录中，拒绝 source path、创意工坊
路径、路径穿越和符号链接逃逸。增加针对任意外部路径与 source fallback 的 409／400 测试。
## 用户界面当前行为

- 项目扫描可使用缓存或重新扫描；
- 摘要展示错误类型、文件和条目；
- 批量开始前弹窗展示问题数量、供应商、模型及费用／写回提示；
- 批量运行进入 Task Center，可跨页面恢复；
- 完成页展示成功数、失败数、耗时和写回后的 before／after 证据；
- 单条弹窗在调用前选择模型并提示费用，响应后显示分析和候选；
- key 损坏的人工校对入口给出无法自动定位提示。

现有用户指南中“先预览再应用”的说法与批量流程及单条真实写回时序不一致，需要纠正。

## 失败语义

- 全部成功：所有选定问题通过验证并写回，任务 `completed`；
- 部分成功：成功项保留，失败项留在问题记录，任务 `partial_failed`；
- 完全失败：未产生可提交修复或运行异常，任务 `failed`；
- 再试：用户重新扫描／重新进入工坊，可换模型后发起新确认；
- 诊断：记录每轮 active、fixed、remaining、reflection 和 API 错误；
- 禁止：到达上限后继续后台调用模型。

报告必须说明成功数量和剩余数量。key 损坏、模型不足、验证失败、目标不存在、写回失败和
源上下文缺失应尽量使用结构化 failure reason。

## 数据与副作用

| 操作 | 读取 | 写入 | 外部副作用 | 确认 |
|---|---|---|---|---|
| 扫描 | 项目、翻译输出、源文、sidecar | sidecar、扫描任务记录 | 无模型调用 | 不需要 |
| 内嵌修复 | 本次翻译输出和问题 | 通过验证的目标条目、报告 | 使用已选模型 | 随翻译流程确认 |
| 独立单条／批量修复 | 选定问题和项目译文 | 目标条目、日志、报告、任务 | 可能产生费用 | 精确范围确认 |
| 重新扫描 | 当前翻译输出 | 替换问题 sidecar | 无模型调用 | 不需要 |

任何工坊路径都不得写源 Mod、创意工坊目录、部署目录、词典或项目文件状态。

## 测试门禁

必须保留并补充：

1. 扫描只读翻译内容，缓存与强制刷新作用域正确。
2. Issue #34 标点残留按源／目标语言检测，特殊标记不被破坏。
3. 无问题时内嵌工坊不初始化模型。
4. 内嵌默认跟随翻译配置，关闭或独立配置行为明确。
5. 单条、批量和后台 run 缺少精确 approval 时返回 409。
6. 幂等键复用相同 run，拒绝不同 fingerprint；同项目冲突写被阻止。
7. 重试最多 3 次（或 schema 允许的 1–5），只处理尚未成功条目。
8. Prompt 不允许普通错译、遗漏、文风或整句重写。
9. 候选验证通过后才写回；读回／最终验证失败恢复旧译文。
10. 写回只改变目标 key，保持其它条目与 key 原样。
11. 损坏 key 不调用模型、不进入批量写回。
12. 部分成功保留成功项，并在 Task Center 展示成功／失败数量。
13. 单条结果 UI 不把已写回内容伪装成尚待应用的预览。
14. 任意 `file_path`、source path fallback、路径穿越或链接逃逸不能越过登记的翻译目录。
15. 工坊不部署、不写原始 Mod、不静默换模型。

## 代码证据

- `scripts/core/services/workshop_issue_export_service.py`
- `scripts/core/services/embedded_workshop_service.py`
- `scripts/core/services/initial_translation_workshop_service.py`
- `scripts/core/agents/fix_agent.py`
- `scripts/utils/post_process_validator.py`
- `scripts/utils/punctuation_handler.py`
- `scripts/routers/agent_workshop.py`
- `scripts/workflows/initial_translate.py`
- `scripts/workflows/update_translate.py`
- `scripts/react-ui/src/components/initialTranslation/EmbeddedWorkshopSettingsCard.jsx`
- `scripts/react-ui/src/hooks/useAgentWorkshopController.js`
- `scripts/react-ui/src/services/agentWorkshopWorkflowService.js`
- `scripts/react-ui/src/pages/AgentWorkshopPage.jsx`
- `tests/test_initial_translation_workshop_service.py`
- `tests/test_routers_agent_workshop.py`
- `tests/test_workshop_issue_export_service.py`
- `tests/test_demo_repair_logic.py`
- `scripts/react-ui/src/pages/AgentWorkshop.issue-fix-modal.test.jsx`
- `scripts/react-ui/src/pages/AgentWorkshop.invalid-key.test.jsx`
- `scripts/react-ui/src/services/agentWorkshopWorkflowService.test.js`
