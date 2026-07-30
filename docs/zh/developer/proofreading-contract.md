# 校对工作流开发契约

本文把[校对产品意图](../product-intent-proofreading.md)转换成实现边界，并区分：

- 3.1.0 已经实现的行为；
- 当前实现与产品决定的差距；
- Issue #149 中尚未实现的候选增强。

它不是面向普通用户的操作教程。操作步骤见
[校对用户指南](../user-guides/proofreading.md)。

## 范围

包含：

- 项目和文件选择；
- 校对数据加载；
- 条目行模型和上下文；
- 文件级人工修改；
- 当前会话草稿；
- 外部修改检测和修订冲突；
- 原子写入；
- 保存与项目文件状态的边界；
- Issue #149 的未来接口约束。

不包含：

- 初次或增量翻译；
- 词典编辑和术语传播；
- Agent Workshop 批量格式修复；
- 部署；
- 项目管理的完整状态机。

## 当前公共入口

### 后端

| 入口 | 当前作用 |
|---|---|
| `GET /api/proofread/{project_id}/{file_id}` | 加载校对行、文件位置和修订版本 |
| `GET /api/proofread/{project_id}/{file_id}/revision` | 轻量检查磁盘文件是否变化 |
| `POST /api/proofread/save` | 按文件提交条目和注释补丁 |
| `PUT /api/project/{project_id}/file/{file_id}/status` | 用户显式修改项目文件状态 |

### 前端

- `ProofreadingPage.jsx`
  - 选择项目和文件；
  - 防止带未保存修改离开或关闭；
  - 提供独立的“标记完成并继续”动作；
  - 保留来源任务精确返回入口。
- `useProofreadingState.js`
  - 协调加载、验证、保存、草稿和文件状态动作；
  - 普通保存提交整个当前文件；
  - `markCurrentFileDone()` 是独立的项目状态请求。
- `useEditorContent.js`
  - 以 `rows` 作为唯一可编辑状态；
  - 计算修改数量；
  - 保存成功后更新基线并清除脏状态；
  - 轮询轻量修订接口检测外部修改。
- `proofreadingSession.js`
  - 把当前文件的修改补丁、筛选、焦点和滚动位置保存在 `sessionStorage`；
  - 只在同一文档修订版本上恢复；
  - 修订不同则进入草稿冲突，不套用旧补丁。
- `ProofreadingEntryWorkspace.jsx`
  - 展示翻译条目和结构行；
  - 支持搜索、筛选、行号、Key、原文、AI 值和最终值。

## 当前数据模型

### 翻译条目行

每个翻译行包含：

```text
entry_id
row_type = "translation"
line_number
key
source_value
ai_value
final_value
editable = true
issues
raw_source_line
```

### 结构行

注释、空行、语言头和其它原始结构也会被投影为行：

```text
entry_id
row_type = "structure"
structure_type = comment | blank | header | raw
line_start
line_end
source_value
final_value
editable
```

当前只有注释结构行可编辑。语言头、空行和其它原始结构保持只读。

### 三份文本来源

- `source_value`：源语言文件中的原文；
- `ai_value`：翻译归档中的 AI 结果；
- `final_value`：当前翻译文件在磁盘上的实际值。

当前人工编辑以 `final_value` 为准。数据库缺少 AI 译文时，界面会显示显式
`DB_MISSING` 参考标记，但最终值优先读取磁盘翻译。

## 当前加载边界

`ProofreadingService._resolve_target_file_path()` 要求：

- 项目存在；
- `file_id` 存在于当前项目文件索引；
- 文件索引中有实际路径；
- 路径当前存在。

服务根据目标文件语言寻找源语言模板，用于只读原文参考。如果找不到独立源文件，当前
实现会退回目标文件作为模板。

这项回退不得被解释成“校对允许修改原始 Mod”。目标写入始终由项目文件索引选定的当前
翻译文件决定。未来应补充“只有源文件、没有翻译文件”时的明确资格测试。

## 当前文件级保存流程

前端提交：

- `project_id`；
- `file_id`；
- 当前加载时的 `base_revision`；
- 当前文件全部翻译条目的 `key + translation`；
- 用户修改过的注释补丁；
- 目标语言字段。

后端保存流程：

1. 重新解析项目和目标文件；
2. 计算目标文件当前 SHA-256 修订值；
3. 如果与 `base_revision` 不同，返回修订冲突；
4. 从源模板构建整份目标文件；
5. 按 Key 应用前端提交的译文；
6. 保留或应用合法注释补丁；
7. 在目标文件所在目录写临时文件并 `fsync`；
8. 使用 `os.replace()` 原子替换目标文件；
9. 返回新的 `document_revision`。

### 完整快照语义

虽然用户在界面中逐条修改，当前 API 保存的是整个文件的条目快照。服务对请求中缺失的
Key 会退回源文本。因此调用方必须提交当前文件全部翻译条目，而不能把接口当作单条
PATCH 使用。

如果未来开放新的调用方，应：

- 明确保持完整快照契约；或
- 另建真正的单条补丁接口。

不能让部分请求静默把未提交条目改回原文。

## 当前修订冲突与草稿

### 外部修改检测

前端在以下时机检查轻量修订：

- 页面重新获得焦点；
- 页面从隐藏变为可见；
- 每十五秒一次。

检测到磁盘修订变化时，界面提示外部修改。

### 保存冲突

保存请求带有加载时的 `base_revision`。如果磁盘文件已经变化，后端返回
`409 proofreading_revision_conflict`，不执行写入。

前端保留当前编辑状态并提示用户重新加载和检查冲突。

### 当前会话草稿

未保存修改以补丁形式写入当前应用会话的 `sessionStorage`。只有文件 ID 和修订版本都
匹配时才恢复。修订不匹配时显示草稿冲突并使用磁盘新版本，不自动套用旧草稿。

该能力不是跨程序、跨版本或跨设备的持久草稿同步。

## 当前保存确认

普通译文修改直接点击保存即可。

以下情况当前会弹出额外确认：

- 变量或括号标记变化；
- 可编辑注释发生变化。

用户可以返回编辑、放弃注释修改或确认继续保存。离开页面和关闭 Tauri 窗口时，如果
存在未保存修改，也必须选择继续编辑、保存、保留会话草稿或明确放弃。

## 必须移除的历史遗留副作用

### 缺陷：普通保存会自动把文件标记为完成

`ProofreadingService.save_proofread_data()` 在原子写入成功后调用：

```text
project_manager.update_file_status_with_kanban_sync(
    project_id,
    file_id,
    "done",
)
```

与此同时，前端已经把 `markCurrentFileDone()` 做成独立动作，并在“标记完成并继续”时
显式调用项目状态接口。

产品决定是：

- 普通保存不得改变项目文件状态；
- 用户可以在项目管理或明确组合动作中手动标记完成；
- 用户修改多少条、是否修改，都不能自动推进文件状态。

产品负责人已确认这次隐式状态更新是历史遗留副作用，不是需要继续权衡的设计。
它必须从普通保存事务中移除，不能通过改文案或隐藏状态变化保留。修复时需要新增
回归测试证明：

1. 普通保存只写文件；
2. 普通保存不调用任何项目状态更新；
3. 明确“标记完成”仍能单独更新状态；
4. “保存并标记完成”只有在两个动作都成功时才向用户显示完整成功。

本次文档治理只固定缺陷和修复契约，不修改运行代码。后续实现应把它作为独立、小范围
修复，而不是重构整个校对流程。

## 数据写入和副作用

### 当前会写

- 当前目标翻译文件；
- 当前会话 `sessionStorage` 草稿；
- 当前实现还会隐式把项目文件状态改成 `done`。

### 当前不会写

- 原始源语言文件；
- 翻译归档数据库；
- 词典；
- 其它项目文件；
- 部署目录。

### 目标契约

普通校对保存只允许：

- 原子更新用户选定的当前翻译文件；
- 更新当前会话的编辑基线和保存结果；
- 写必要诊断。

项目状态、翻译归档、词典、模型任务、格式修复和部署都必须保持独立动作。

## 保存成功与失败

### 成功

后端返回：

```text
status = "success"
document_revision = <new sha256>
```

前端随后：

- 把当前值设为新的编辑基线；
- 清除已保存修改的脏状态；
- 清除当前文件的会话草稿；
- 显示保存成功通知。

### 修订冲突

返回结构化 409，不写文件，不清除用户草稿。

### 其它失败

当前服务把大多数异常记录到日志后返回 `False`，路由转换为通用 500：

```text
Failed to save proofreading data
```

目标契约要求用户能明确知道保存没有成功，并保留草稿。后续可以增加结构化错误码，但
不要求普通用户阅读技术日志才能判断是否保存。

## 人工修改权威性

当前校对保存只更新磁盘翻译文件，不更新翻译归档数据库。后续增量翻译怎样识别和保护
人工定稿，需要与翻译归档契约保持一致。

不论内部实现选择磁盘、归档标记或显式上载：

- AI 初稿不能覆盖当前磁盘人工定稿；
- 校对页面重新加载时 `final_value` 必须优先反映磁盘；
- 自动工作流不能把人工定稿当成未确认模型结果；
- 若人工定稿需要进入正式增量基线，必须通过明确、可测试的归档路径。

## 与词典、格式和部署的隔离

校对保存不得：

- 调用 LLM；
- 接受或修改词典条目；
- 把一条修改传播到整个项目；
- 启动 Agent Workshop 修复；
- 自动改变文件完成状态；
- 自动部署。

当前前端“验证”只构造当前条目的虚拟本地化内容并调用校验入口。它不自动保存或修复。

## Issue #149 开发边界

Issue
[#149](https://github.com/Drlinglong/Remis/issues/149)
是开放的体验增强，不阻塞当前校对正式功能。

### 可读变量预览

实现必须区分：

- `raw_value`：唯一可保存的原始脚本文本；
- `display_hint`：可读解释；
- `known`：是否能可靠解释。

提示不得改写 `final_value`。未知变量、异常脚本或原作者错误不得自动阻止保存。

### 内联词典术语

按当前条目按需查询并返回只读提示，例如：

```text
matched_text
canonical_term
preferred_translation
short_note
glossary_id
```

校对页不得直接编辑词典，不自动接受建议，也不建设不必要的全文术语索引。

### 性能门禁

新增提示不得明显降低：

- 大文件首次打开速度；
- 虚拟列表滚动；
- 输入响应；
- 保存延迟。

## 与产品意图的当前差距

| 产品意图 | 3.1.0 当前行为 | 状态 |
|---|---|---|
| 普通保存不改变文件状态 | 后端保存后隐式写 `done` | 明确冲突 |
| 只有翻译文件才能进入校对 | 当前有目标文件索引检查，但源模板可回退到目标文件 | 需补资格测试 |
| 保存失败明确说明是否写入 | 冲突清楚；其它错误较笼统 | 可改进 |
| 术语提示只读展示 | 尚未实现 | Issue #149 |
| 游戏变量提供可读预览 | 只有变量变化警告 | Issue #149 |
| 人工定稿在后续工作流中受保护 | 磁盘值优先展示，但归档衔接未在本模块闭环 | 需跨契约核验 |

## 已有测试覆盖

- 原文、译文和结构行的行模型；
- 注释块保留和合法补丁；
- 非注释结构拒绝修改；
- 原子写入改变修订值且不遗留临时文件；
- 轻量修订读取；
- 旧修订保存被拒绝且原文件不变；
- 路由转发完整条目、结构补丁和修订值；
- 修订冲突映射为结构化 409；
- 数据加载错误保留结构化原因；
- 当前会话草稿恢复和修订冲突；
- 未保存离开/关闭保护；
- 条目编辑、筛选和虚拟滚动相关前端行为。

## 必须补充的测试

1. 普通保存成功时项目状态更新方法未调用。
2. 明确标记完成只通过项目状态入口执行。
3. 只有源语言文件、没有翻译成果时不能进入可写校对。
4. 部分快照请求不得把缺失 Key 静默写回源文。
5. 通用保存失败时草稿保留，界面明确显示未保存。
6. 人工定稿不会被 AI 初稿或页面重载覆盖。
7. Issue #149 提示只读，不改变最终保存值。
8. Issue #149 未知变量不阻止用户确认后保存。
9. Issue #149 大文件滚动和输入性能不明显退化。

## 代码证据

- `scripts/schemas/proofreading.py`
- `scripts/routers/proofreading.py`
- `scripts/core/services/proofreading_service.py`
- `scripts/react-ui/src/pages/ProofreadingPage.jsx`
- `scripts/react-ui/src/hooks/useProofreadingState.js`
- `scripts/react-ui/src/hooks/useEditorContent.js`
- `scripts/react-ui/src/hooks/proofreadingSession.js`
- `scripts/react-ui/src/components/proofreading/ProofreadingWorkspace.jsx`
- `scripts/react-ui/src/components/proofreading/ProofreadingEntryWorkspace.jsx`
- `tests/test_proofreading_service.py`
- `tests/test_routers_proofreading.py`
- `scripts/react-ui/src/hooks/useProofreadingState.workflow.test.js`
- `scripts/react-ui/src/hooks/proofreadingSession.test.js`
- `scripts/react-ui/src/components/proofreading/ProofreadingEntryWorkspace.test.jsx`
- `scripts/react-ui/src/pages/ProofreadingPage.test.jsx`
