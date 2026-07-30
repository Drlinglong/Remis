# Remis Agent / Copilot 开发契约

本文把[产品意图](../product-intent-agent-copilot.md)转换成实现契约。用户说明见
[Remis 小助手](../user-guides/remis-assistant.md)。

## 名称与边界

面向终端用户的一个聊天产品包含两个职责：

- Help Copilot：基于用户文档回答问题、解释页面并建议下一步；
- Workflow Agent：把自然语言目标转换成受控 Remis 计划。

它们共享会话和呈现，但不应把“回答文本”与“获得执行权”混为一层。

仓库中的 `/api/agent` 是给 Codex 等外部本机控制层使用的独立 Agent API。它可以复用相同
业务服务和安全原则，但不能把外部 API 的能力自动暴露给终端用户聊天模型。

## 3.1.0 当前入口

前端：

- `FEATURES.ENABLE_REMIS_COPILOT=false`；
- `/copilot` 页面由 feature registry 控制；
- 全局浮动助手使用同一 feature flag；
- 会话保存在浏览器 `localStorage`；
- 当前页面可提供经过清理的 `page_context`。

后端：

- 开发态默认注册 `/api/copilot`；
- frozen 打包态默认不注册，除非显式设置 `REMIS_ENABLE_COPILOT`；
- `/api/agent` 始终是另一套本机 API，不等同于公开 Copilot。

因此 3.1.0 必须标记为内部／隐藏工程预览。下一版本公开需要同时翻转前端和后端发布策略，
不能只显示按钮却让打包后端返回 404。

## Help Copilot 契约

`POST /api/copilot/chat` 接受：

- 对话消息；
- Provider／模型；
- locale；
- 可选上下文预算；
- 经过清理的页面上下文。

服务：

1. 识别少量确定性能力意图；
2. 路由到用户 Help Skill／Micro-RAG 语料；
3. 调用模型生成结构化回答；
4. 用服务端 Action Registry 过滤建议；
5. 返回 reply、sources、confidence、grounding 和上下文裁剪信息。

用户语料只允许用户指南等白名单内容。开发者文档、源码、密钥、用户 Mod 全文和本机隐私
路径不得进入 Help 索引。

模型不可决定 action 的标签、风险或确认要求；这些字段由服务端 Registry 覆盖。

## 当前 Action Registry

3.1.0 实际注册：

- `open_api_settings`
- `open_log_folder`
- `open_github_issues`
- `open_github_issue_132`
- `open_project_management`
- `open_create_project`
- `open_initial_translation`
- `open_proofreading`
- `open_agent_workshop`
- `open_glossary_manager`
- `open_provider_docs`
- `open_deploy_dialog`
- `start_localization_workflow`

除最后一项外，当前都是导航、打开日志或打开 URL。`start_localization_workflow` 只打开受控
工作流 UI，本身不产生写入；真正执行另走 plan approval。

现有 `docs/zh/copilot/agent-operations.md` 还列出 `deploy_mod`、`translate`、
`repair_selected_entries`、`validate_project` 等目标 action，但它们不在当前代码 Registry。
模型提示、文档表格、API `/actions` 和前端 handler 必须区分“已实现”与“未来候选”。

## 当前工作流

当前唯一端到端聊天工作流是 `localize_mod_v1`：

1. 用户从聊天中的结构化 action 打开 `InlineLocalizationWorkflow`；
2. UI 收集 Mod 路径、项目名、游戏、源／目标语言、Provider、模型及限制；
3. `/workflows/localize-mod/plan` 只读扫描允许根目录下的 Mod；
4. 服务端保存 30 分钟有效、单次执行的内存计划；
5. UI 展示创建项目、复制／引用和初次翻译风险；
6. 用户点击批准；
7. Remis 创建项目，再创建并启动初次翻译任务；
8. 任务标记 `created_by=remis_agent` 并返回准确 task ID。

计划参数由服务端保存；execute 只接受 plan ID，不能让模型在批准后替换参数。双击／重复
执行由 executed reservation 阻止。

## 确认契约

任何执行计划至少包含：

- 用户目标和作用项目；
- 原子步骤及顺序；
- 每步读取／写入范围；
- Provider、模型及可能费用；
- 创建、复制、覆盖、删除、部署和不受支持能力的边界；
- 跳过条件和失败策略；
- 预计创建的任务。

确认门：

- 只读查询、导航和计划生成：无需确认；
- 包含实际执行的工作流：完整展示后，对整份计划确认一次；
- 已经完整展示的付费调用和部署：由整份计划批准涵盖，不增加节点级确认；
- 删除等已有功能是否保留模块级确认：服从对应功能契约；
- 执行中新增步骤或扩大已展示范围：暂停、重新生成计划并确认；
- 不扩大范围的实现参数变化：必须重新校验，但不因此自动要求第二次用户确认；
- Registry 中不存在的能力：直接拒绝，不能通过确认获得执行权；
- 已过期或应用重启丢失的内存计划：重新检查，不能重建旧批准。

当前 Registry 没有通用“修改原始 Mod／创意工坊文件”action，也没有可直接执行的
`deploy_mod`。文档中的未来候选不得被模型当作现有能力。

## 执行器边界

语言模型只输出严格 Schema 下的意图或计划建议。执行层必须：

- 拒绝未知 action 和多余参数；
- 从服务端 Registry 取得风险与 handler；
- 调用已有 Remis 业务 API／service，而不是直接写文件或数据库；
- 使用业务模块自己的 approval、idempotency 和路径限制；
- 为每个后台步骤保存准确任务 ID；
- 将任务创建者标记为 Remis Agent；
- 不把模型自然语言当作文件路径、SQL、函数名或命令执行。

## 终态与成功

当前 `buildWorkflowCompletionMessage()` 实际生成的是“已批准并启动翻译”，只保存 task ID 并
引导查看进度。它没有证明翻译完成。

公开版本需要一个计划运行记录：

```text
workflow_run_id
plan_snapshot
step_id -> task_id
step status: pending | running | skipped | completed | partial_failed | failed
result summary
allowed_next_actions
```

助手必须从 Task Center／业务结果读取终态。最终回复至少区分：

- 完成；
- 正常跳过，例如没有检测到更新；
- 部分成功；
- 失败；
- 等待用户再次确认。

不能从请求成功、任务创建或聊天记录推断完成。

## 多步骤编排目标

用户示例“检查更新 → 有更新才挖新词 → 增量翻译 → 生成封面”需要受限 DAG：

- 节点只能来自版本化 Tool Registry；
- 边可以表达成功、没有更新、部分成功和失败条件；
- 每个节点声明输入、输出、副作用、确认类别和幂等规则；
- 计划由 Remis 校验后渲染；
- 模型不能加入任意代码节点；
- 下游使用上游的结构化结果，不能从日志文本猜状态；
- 整体计划和每个任务都可在 Task Center 找回。

3.1.0 尚无此通用 DAG。当前只支持硬编码的创建项目 + 初次翻译组合。

## 当前主要差距

1. 前端和 packaged API 均关闭，尚未形成公开发布配置。
2. 页面显示 `Phase 1.1`，状态 API 返回 phase 2，版本语义不一致。
3. 只有初次翻译组合，没有增量翻译、新词挖掘、更新检查、封面生成等通用节点。
4. 聊天只报告任务启动，没有终态监控和逐步骤最终总结。
5. 工作流计划只存在内存，重启即丢失，不足以支撑长期复杂任务。
6. 文档候选 action 多于实际 Registry，存在模型承诺未实现能力的风险。
7. 当前 provider／model 选择仍主要硬编码在预览 UI，公开前需要与设置和费用提示统一。
8. 创建项目成功、翻译启动失败时可能形成部分副作用，最终结果必须如实表达并提供恢复入口。
9. 缺少一套跨模块、版本化、可测试的工作流节点契约。

## 测试门禁

1. packaged 构建的公开／隐藏策略与前后端一致。
2. 同一聊天同时支持帮助回答和计划建议，但文字回复没有执行权。
3. 未知 action、额外参数和模型伪造风险字段被拒绝或覆盖。
4. 帮助检索不读取 developer、源码、密钥或用户 Mod 全文。
5. 计划生成只读；执行只接受仍有效且未使用的服务端计划。
6. 所有付费／写入步骤在执行前有可验证批准。
7. 计划参数变化、过期和重复执行不能复用旧批准。
8. 业务副作用只通过既有 Remis 工作流。
9. 每个后台步骤绑定准确 task ID，并从持久化状态恢复。
10. 最终回复严格对应 completed、skipped、partial_failed 或 failed。
11. 应用重启后不会把仅存在聊天 localStorage 的任务当作已完成。
12. 多步骤计划拒绝未注册节点、循环、越权路径和不合法条件。
13. Agent 不直接修改本地化文件、词典、数据库或 Remis 源码。
14. 一份已批准计划中的部署不会触发第二次确认。
15. 新增步骤或扩大范围必须重新确认；未知的原始 Mod 修改 action 必须拒绝。

## 代码证据

- `scripts/react-ui/src/config/features.js`
- `scripts/react-ui/src/config/pageRegistry.js`
- `scripts/react-ui/src/components/copilot/RemisCopilotThread.jsx`
- `scripts/react-ui/src/components/copilot/InlineLocalizationWorkflow.jsx`
- `scripts/react-ui/src/services/copilotService.js`
- `scripts/react-ui/src/services/copilotSessionStore.js`
- `scripts/core/copilot/actions.py`
- `scripts/core/copilot/service.py`
- `scripts/core/copilot/workflow.py`
- `scripts/routers/copilot.py`
- `scripts/routers/agent.py`
- `scripts/web_server.py`
- `tests/test_copilot_phase1.py`
- `tests/test_copilot_workflow.py`
- `tests/test_agent_api.py`
- `tests/test_web_server_startup.py`
