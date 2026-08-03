# 术语表开发契约

本文把[术语表产品意图](../product-intent-glossary.md)转换成实现边界，并区分 3.1.0
已有行为、当前差距和未来约束。普通操作见
[词典与词汇表用户指南](../user-guides/glossary.md)。

## 范围

包含词典和词条 CRUD、项目绑定、翻译装载顺序、上下文匹配、合并与删除、新词审批写入。
不包含翻译文件重写、校对、格式修复、部署或词典历史版本。

## 当前入口

### 用户入口

- 侧栏“质量与术语 → 词汇表管理”：创建、查看、编辑和删除词典或词条；
- 项目管理“项目词典”：创建、绑定、解除绑定和打开项目词典；
- 初次／增量翻译高级选项：启用主词典并手动选择额外词典；
- 新词审判庭：审批候选后写入项目词典。

### 后端入口

| 入口 | 当前作用 |
|---|---|
| `GET /api/glossaries` | 返回词典概览；项目界面据此列出全部游戏词典并在前端筛选 |
| `POST /api/glossary` | 创建空词典 |
| `POST /api/glossary/{glossary_id}/entry` | 新增词条 |
| `PUT /api/glossary/entry/{entry_id}` | 更新词条 |
| `DELETE /api/glossary/entry/{entry_id}` | 删除词条；服务端自身没有确认参数 |
| `PUT /api/glossary/file/{glossary_id}` | 更新名称、类型和项目绑定 |
| `POST /api/glossaries/batch-delete/preview` | 只读预览整本删除影响 |
| `POST /api/glossaries/batch-delete` | 原子删除词典、词条和绑定 |
| `POST /api/glossaries/merge/preview` | 只读计算合并冲突和影响 |
| `POST /api/glossaries/merge` | 重新预览后创建后台合并任务 |
| `POST /api/neologisms/{candidate_id}/approve` | 用户审批候选并写入项目词典 |
| `POST/PUT/DELETE /api/neologisms/project-glossary/{project_id}` | 创建、绑定或解除项目词典 |

## 当前数据边界

SQLite 当前主要表：

- `glossaries`：词典名称、游戏、主词典标志、说明和元数据；
- `entries`：词条 ID、所属词典、各语言译法、缩写、变体和元数据；
- `project_glossary_bindings`：项目与词典的多对多绑定。

当前没有词典版本表、旧词条快照或回滚记录。所有读取都以数据库中的最新状态为准。

项目词典界面会取得全部游戏词典并允许用户先按游戏筛选；但
`GlossaryManager.bind_project_glossary()` 和元数据更新仍要求项目与词典属于同一游戏。
因此“能浏览其它游戏词典”不等于“当前能跨游戏绑定”。

## 当前翻译装载与优先级

`scripts/routers/translation.py` 当前按以下顺序构造 `final_glossary_ids`：

1. 当前游戏主词典；
2. 当前项目绑定的项目词典；
3. 用户手动选择的额外词典。

`load_selected_glossaries()` 用数组位置写入 `_glossary_priority`；
`_deduplicate_matches()` 对同一规范化源词选择优先级数值更高的候选。因此 3.1.0 当前实际
行为是：

> 用户手选额外词典 > 项目词典 > 全局主词典

`tests/test_routers_translation.py` 锁定三层装载顺序；
`tests/core/test_glossary_priority.py` 锁定后装载词典会赢得同源词冲突。

若未选择任何额外词典，`load_glossaries_for_run()` 会加载当前游戏主词典；翻译路由通常
已经把主词典放入最终 ID 列表。装载状态位于进程内共享的 `in_memory_glossary`，不是按
任务冻结的不可变快照。并发任务的隔离与可复现性尚未由本契约证明。

## 上下文匹配与提示词

`GlossaryManager.extract_relevant_terms()` 会检查：

- 精确匹配；
- 语音匹配；
- 变体；
- 缩写；
- 部分或模糊匹配。

匹配结果由 `create_dynamic_glossary_prompt()` 注入翻译提示词。当前提示词已经表达：

- 备注是适用条件；
- 上下文与备注冲突时不要强制采用词典目标；
- 无备注的多义词仍优先看上下文；
- 语音和模糊匹配只是参考。

这与产品决定一致。`docs/zh/developer/translation_quality_benchmark.md` 的 `silo`／
`missile silo` 最小对照是当前关键质量门禁。

词典保存成功只代表数据库写入成功。翻译是否遵循词典需由提示词注入测试和真实模型
基准分别验证，不能把模型输出当成 CRUD 成功条件。

## 写入与副作用

| 操作 | 当前写入 | 不应发生的副作用 |
|---|---|---|
| 新增／编辑词条 | `entries` 当前行 | 不修改翻译文件，不调用模型 |
| 删除词条 | 删除 `entries` 当前行 | 不级联修改翻译成果 |
| 修改词典元数据 | `glossaries` 与绑定关系 | 不自动提升为全局，不静默解除绑定 |
| 合并词典 | 目标词典词条及合并来源元数据 | 不删除源词典，不静默解决未选策略的冲突 |
| 删除整本词典 | 词典、词条和项目绑定 | 不触碰翻译文件 |
| 审批新词 | 项目词典词条和候选状态 | 未审批候选不得写入 |

词典模块没有写翻译文件的入口。修改词典不会自动重翻旧成果；用户需要重新处理相关
内容或人工校对。

## 当前确认边界

### 已实现

- 单条删除：`GlossaryManagerPage.jsx` 在调用无确认参数的 DELETE 前显示确认框；
- 整本／批量删除：先预览术语数、主词典和项目绑定影响；服务端要求主词典及绑定风险的
  显式布尔确认；
- 合并：前端先读取预览，服务端执行前再次做只读预览，随后进入后台任务；
- 新词写入：只发生在明确调用候选审批入口之后；
- 普通项目词典绑定与解绑直接执行，符合其低风险、可撤销的产品边界。

### 当前差距

- 单条删除只有前端确认，直接调用 API 可以绕过；
- `PUT /api/glossary/file/{id}` 能改变词典类型和绑定，服务端没有“提升为主／公共词典”
  的独立确认契约；
- 合并请求没有预览令牌或显式 `confirmed` 字段，确认主要由前端流程表达；
- 批量操作结果以整次事务或后台任务摘要为主，尚未定义逐词条成功／失败列表；
- 当前没有批量导入入口。

## 新词流程边界

Issue [#30](https://github.com/Drlinglong/Remis/issues/30) 定义的原始问题是：静态词典无法
覆盖动态出现的新专名或概念词，无状态模型会对同一新词产生不一致译法。当前实现把
“发现 → 确认 → 学习”拆成新词挖掘机、审判庭和项目词典。

新词挖掘可以自动创建或准备项目词典，但候选写入由
`POST /api/neologisms/{candidate_id}/approve` 触发。
`NeologismManager.approve_candidate()` 写入后把候选标为 `approved` 或 `new_meaning`，
并具有幂等测试。拒绝候选不写词典；恢复已审批候选只恢复审议状态，不删除已经写入的
词典条目。

“自动准备一本空项目词典”与“自动接受新词”是不同副作用，文档和 UI 不得混淆。

模组档案的候选治理会在全局别名归并与程序化覆盖计算后给出 `glossary_eligible`。该字段
只允许候选进入 review/save 管线，不能跳过审判庭审批。`incidental_concept` 默认
`audit_only`，不会进入候选 sidecar；核心或次要的 `glossary_term`、`named_phrase` 可以
进入候选池，但即使属于核心档也不会因此生成实体摘要。详见
[项目档案候选治理契约](context-candidate-governance.md)。

模型健康审查器只返回建议；任何模型建议要改变词条，仍需走明确的人类确认和写入入口。

产品要求新词挖掘机作为建议的译前步骤，审判庭作为所有 AI 候选的强制人工关口，项目
词典作为绑定 Mod 并在该项目翻译中默认使用的最终产物。3.1.x 不计划扩展这套流程，只
长期观察实际效果并优化稳定性。

## 成功、失败与部分成功

- CRUD 成功：数据库提交完成，API 返回保存后的内容或成功结果；
- CRUD 失败：返回 4xx/5xx，前端必须明确说明未保存；
- 批量删除：当前原子提交，不提供逐项部分成功；
- 合并：后台任务应在 Task Center 报告结果；冲突策略和计数来自执行前的新预览；
- 未来批量入口：必须返回成功项、失败项和可重试信息，不能只返回笼统成功。

已有持久化词条不得因另一个词条保存失败而消失，但当前没有可承诺的“旧词典版本”。

## 与产品意图的差距

| 产品意图 | 3.1.0 当前行为 | 状态 |
|---|---|---|
| 手选额外 > 项目 > 全局主词典 | 按低到高顺序装载并由手选词典最终覆盖 | 一致 |
| 删除词条必须确认 | 官方 UI 有确认，API 无确认字段 | 部分实现 |
| 合并必须确认 | 前端预览，后端重做预览，无确认令牌 | 部分实现 |
| 项目词典提升为公共／全局必须确认 | 通用元数据更新入口无独立确认 | 未实现 |
| 普通项目词典绑定与解绑无需确认 | 当前直接执行，且不删除词典 | 一致 |
| 修改后提示旧译文不变 | 用户指南说明，保存界面未核验到提示 | 可改进 |
| 批量结果列出成功与失败项 | 当前没有批量导入；删除原子化，合并任务只给摘要 | 未来契约 |
| 不保存历史版本 | 当前只保存最新状态 | 一致 |
| 上下文优先而非机械替换 | 当前动态提示词和基准已覆盖 | 一致 |

## 必须补充或保留的测试

1. 路由构造与实际去重共同验证“手选额外 > 项目 > 全局主词典”。
2. `silo` 农业／军事最小对照继续作为真实模型基准。
3. 单条删除、合并和提升公共／全局身份的确认不可由 API 调用绕过；普通绑定与解绑保持
   无二次确认。
4. 词条 CRUD 不修改任何翻译文件，也不调用模型。
5. 修改词典后已有翻译文件字节不变。
6. 未审批新词不写入；审批写入幂等；拒绝不写入。
7. 项目界面“全部游戏”筛选与后端同游戏绑定限制保持一致文案。
8. 批量删除预览与执行使用相同目标，主词典和项目绑定风险均需确认。
9. 合并执行前重新预览，冲突策略明确且源词典不被删除。
10. 若未来加入批量导入，部分失败返回逐项结果。

## 代码与测试证据

- `scripts/core/glossary_manager.py`
- `scripts/core/services/initial_translation_workspace_service.py`
- `scripts/routers/glossary.py`
- `scripts/routers/neologism.py`
- `scripts/routers/translation.py`
- `scripts/core/neologism_manager.py`
- `scripts/react-ui/src/pages/GlossaryManagerPage.jsx`
- `scripts/react-ui/src/components/project/ProjectGlossaryPanel.jsx`
- `scripts/react-ui/src/hooks/useGlossaryActions.js`
- `tests/core/test_glossary_priority.py`
- `tests/core/test_glossary_overview.py`
- `tests/core/test_neologism_manager.py`
- `tests/test_routers_glossary.py`
- `tests/test_routers_neologism.py`
- `docs/zh/developer/translation_quality_benchmark.md`
