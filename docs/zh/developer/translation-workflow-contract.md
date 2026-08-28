# 初次翻译与增量翻译：开发契约

这份文档把
[翻译主流程产品意图](../product-intent-translation-workflows.md)
转换成实现边界和回归测试。它同时记录 3.1.0 当前代码事实与目标契约；标为“差异”的
项目不能被用户指南描述为已经实现。

## 适用范围

- 初次翻译任务创建、执行、输出和归档；
- 增量翻译预扫描、执行、输出和归档；
- 部分失败的状态与用户摘要；
- 原文回退在输出文件和数据库中的不同语义；
- 正式增量基线的晋升条件。

不包含部署文件复制和假本地化删除的完整实现契约；完整部署边界见
[部署开发契约](deployment-contract.md)。本文件只约束部分完成结果交给部署之前必须
携带的信息。

Victoria 3 官方国家 `TAG_ADJ` 定义与引用的语义路由、目标语言 morphology policy、
人工复核和 fail-open 边界见
[Victoria 3 国家形容词语义上下文](vic3-country-adjective-context.md)。该能力属于翻译
任务构造与 prompt 组装的一部分，但不会改变本文件规定的输出、失败和基线语义。

## 当前公共入口

| 能力 | 当前入口 | 主要结果 |
|---|---|---|
| 初次翻译 | `POST /api/translate/start` | 后台任务、输出目录、翻译归档 |
| 初次翻译状态 | `/api/status/{task_id}`、任务 WebSocket | 进度、错误数、日志、终态 |
| 增量归档检查 | `GET /api/project/{project_id}/check-archive` | 可用基线和已归档语言 |
| 增量预扫描/执行 | `POST /api/project/{project_id}/incremental-update` | 预扫描摘要或后台执行任务 |
| 任务结果 | Task Center、初次/增量结果组件 | 用户摘要、警告、输出路径、诊断入口 |

正式翻译任务必须携带准确的项目、目标语言、供应商和模型。重复的项目写任务应继续由
项目级去重边界拦截。

## 数据表示契约

同一次部分完成必须维护两种不同表示：

```text
模型调用
  ├─ 成功 → 输出文件写译文 → 数据库写译文
  └─ 失败 → 输出文件写源文 → 数据库译文为空
                                      │
                                      └─ 后续仍视为待翻译
```

### 输出文件

输出文件以“用户仍能进入游戏”为目标。失败批次可以回退到源语言原文，但必须保留
Paradox key、变量、格式、编码和目录结构。

### 翻译数据库

数据库以“未来仍能准确判断哪些内容翻译成功”为目标。

- 成功译文正常持久化；
- 失败条目的译文字段必须为空；
- 禁止把源文复制到译文字段；
- 禁止仅凭字符串等于源文推断失败，因为合法译文可能与源文相同；
- 成功或失败必须来自结构化执行结果，而不是事后比较文本。

实现可以使用空字符串或数据库 `NULL` 表示缺失译文，但同一数据访问边界必须规范化为
统一的“未翻译”语义，查询和增量 diff 不得把它当作有效译文。

## 初次翻译契约

### 当前已对齐

- `BaseHandler.translate_batch()` 在最终重试失败后设置结构化失败标记，并为输出返回源文。
- `finalize_translated_file()` 会写出回退文件。
- 当 `is_failed=True` 时，不标记 checkpoint 完成、不更新项目文件成功状态，也不调用
  `archive_translated_results()`。
- 现有 `test_finalize_failed_file_writes_fallback_without_success_side_effects` 锁住了文件级
  “可写输出但不写归档”的边界。

### 当前差异

- 文件失败后，语言流程会抛出 `RuntimeError`，任务通常进入 `failed`。
- 前端 `TaskRunner` 已能渲染 `partial_failed` 结果，但当前初次翻译链路未稳定地产生该终态。
- 进度结构包含批次和文件相关字段，但并非所有成功/失败统计都由后端填充。

### 目标行为

当至少有一部分可用输出时：

- 终态必须表达“部分完成”而不是完全成功；
- 用户摘要必须明确说明存在失败并要求检查；
- 可以使用已有的文件错误数、失败批次、警告数或其他结构化范围；
- 不要求为了统一统计单位重写后端；
- 成功文件继续归档，失败文件或失败条目不写译文；
- 输出可进入校对，并在部署前触发额外确认。

完全没有可信输出时才进入完全失败。

## 增量翻译契约

### 预扫描

预扫描只读取项目、源文件和已确认基线，返回可复用、新增、修改及文件范围。
预扫描不得调用翻译模型、写译文、创建新翻译基线或推进项目源版本。

### 正式执行

正式执行可以：

- 复用旧的有效译文；
- 调用用户确认的供应商和模型处理新增或修改条目；
- 写独立输出包；
- 保存本次成功译文；
- 记录结构化警告、任务结果和诊断。

### 当前实现差异

当前 `IncrementalBuildService.build_language_output()` 使用
`entry["translation"] or entry["source"]` 同时构建输出和 `archive_results`。
这会让原文回退进入归档候选。

随后 `IncrementalArchiveService.archive_language_result()` 会创建新源版本并归档整组结果；
`ProjectManager.run_incremental_update_workflow()` 只要收到 `status="success"`，还可能推进项目
源路径。源路径推进可以保留，但必须与“翻译基线是否完整”解耦，不能据此推断失败条目
已经翻译。路由层即使存在运行警告也会把任务标为 `completed`。

上述归档和完成状态行为适合生成“勉强可玩”的输出，但不满足数据库和正式基线契约。

### 目标行为

增量构建必须分别产生：

- `output_translations`：允许失败位置使用源文回退；
- `archive_translations`：只包含结构化标记为成功的译文，失败位置为空；
- `failure_summary`：表示是否有失败及其可定位范围；
- `baseline_eligible`：只有没有待处理翻译失败时才为真。

若 `baseline_eligible=false`：

- 成功译文可以保存；
- 失败译文必须为空；
- 不得用回退原文覆盖旧的有效译文；
- 不得自动把本次运行晋升为完整正式基线；
- 不得因为输出包成功写出就把数据层描述为完整成功。

## 任务状态与用户报告

产品不规定唯一统计单位。实现可按批次、文件或条目报告，只要同时满足：

1. 使用结构化状态或字段判断存在失败，不依赖解析日志文案；
2. 普通用户第一眼能看到“有些失败了，需要检查”；
3. 至少提供一种数量或范围；
4. 给出校对、任务详情、重试或诊断入口；
5. 技术日志默认不是理解结果的必要条件。

建议终态语义：

| 终态 | 含义 | 是否有输出 | 是否可晋升完整基线 |
|---|---|---:|---:|
| `completed` | 所有必需翻译成功 | 是 | 是 |
| `partial_failed` | 有可用输出，但部分翻译失败 | 是 | 否 |
| `failed` | 没有可信可用结果或流程无法继续 | 不保证 | 否 |

字段名可以随现有任务契约演进，但不得把带有翻译失败的任务仅以绿色“完成”呈现。

## 部署交接

部分完成输出允许部署，目的是让用户可以接受少量源语言文本并先进入游戏。
部署动作必须：

- 显示仍有原文回退的醒目警告；
- 明确建议先校对或查看任务详情；
- 在真正写入部署目录前再次要求用户确认；
- 不因用户确认部署而改变数据库失败条目的空值。

## 清理源文件

当前产品决定接受现有交互边界：

- 位于初次翻译高级选项；
- 默认关闭；
- 红色告警明确说明删除范围；
- 用户主动开启后再启动流程视为授权。

开发契约不要求判断项目源目录是 Remis 副本还是创意工坊目录，也不要求移除此功能。
必须锁住“默认关闭、不会隐式继承开启状态、未开启时不调用清理服务”。

## 回归测试门禁

### 已有测试应长期保留

- 初次翻译成功文件写 checkpoint、项目状态和归档；
- 初次翻译失败文件写回退输出，但不写 checkpoint、项目成功状态和归档；
- provider 失败携带 `fallback_to_source` 结构化警告；
- 增量结果向任务保存 warning 数量和输出路径。

### 必须新增或补强

1. 增量翻译混合成功和失败时，输出文件包含源文回退。
2. 同一运行的数据库只保存成功译文，失败译文为空。
3. 回退原文不覆盖旧的有效译文。
4. 有翻译失败时 `baseline_eligible=false`，不推进完整基线。
5. 部分完成结果页显示明确警告和检查入口。
6. 部分完成部署前要求再次确认。
7. 报告使用批次、文件或条目任一口径时，均能稳定表达存在失败。
8. 清理源文件默认关闭，只有显式启用才调用删除服务。

## 非目标

- 不为了文档一致性强制统一批次、文件和条目统计；
- 不禁止用户选择昂贵模型；
- 不强制先运行 Model Arena 或新词挖掘；
- 不限制“清理源文件”只能处理 Remis 管理的副本；
- 不在本契约中重新设计整个任务系统或归档数据库。

## 代码证据入口

- `scripts/core/base_handler.py`
- `scripts/core/services/initial_translation_language_service.py`
- `scripts/core/services/initial_translation_file_service.py`
- `scripts/core/services/incremental_build_service.py`
- `scripts/core/services/incremental_archive_service.py`
- `scripts/workflows/update_translate.py`
- `scripts/core/project_manager.py`
- `scripts/routers/translation.py`
- `scripts/routers/projects.py`
- `scripts/react-ui/src/components/TaskRunner.jsx`
- `scripts/react-ui/src/components/incrementalTranslation/ExecutionStep.jsx`
- `tests/test_initial_translation_file_service.py`
- `tests/core/test_translation_failure_propagation.py`
- `tests/test_routers_projects.py`
