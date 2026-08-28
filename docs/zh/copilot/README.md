# Remis Copilot 文档

> **Status:** 3.1.1 隐藏工程预览；公开版本仍需完成发布门禁
> **Related:** [Issue #132](https://github.com/Drlinglong/Remis/issues/132)

本目录存放 **Remis Agent / Copilot** 相关说明。两种职责通过同一个聊天入口交给用户：
Copilot 回答如何使用 Remis，Agent 把自然语言目标整理成待批准的 Remis 工作流。

## 两层检索语料，一份固定操作契约

| 材料 | 读者 / 消费者 | 进入哪里 | 说明 |
|------|------|------|------|
| [双层语料边界](rag-corpus-boundary.md) | 实现者 / 维护者 | 不进入检索 | 规定两层语料的白名单、优先级和排除项 |
| `docs/zh/user-guides/**` | 终端用户 / Help Copilot | `user-help` | 回答怎么用、失败后怎么办 |
| `docs/zh/product-intent-*.md` + `docs/zh/developer/*-contract.md` | Remis Agent | `agent-planning` | 理解功能目的、当前能力与不可越界事项 |
| [Agent 操作说明书](agent-operations.md) | Copilot（模型侧） | 固定 system/tool 附录 | 关键能力和禁止项不能依赖检索命中 |

## 原则（一句话）

- **`user-help`**：回答「Remis 怎么用」。
- **`agent-planning`**：回答「这个目标为什么存在，当前能怎样安全规划」。
- **Agent 操作说明书**：固定回答「我能建议系统做什么」，不能被检索内容覆盖。
- **其他开发者文档**：回答「代码怎么接」——默认不进任一运行时语料。

产品意图见 [Agent / Copilot 产品意图](../product-intent-agent-copilot.md)，当前实现见
[开发契约](../developer/agent-copilot-contract.md)。

## 产品形态前提

普通用户拿到的是 **Tauri 封装的安装版 / 便携客户端**，不是本仓库的开发工作区。

因此 Copilot：

- **不能**、也**不需要**修改 Remis 源代码；
- 遇到功能请求、程序缺陷、需要改软件本身的问题，应引导用户到 GitHub 反馈，而不是假装能改客户端。

反馈入口：

- Issues：<https://github.com/Drlinglong/Remis/issues>
- 讨论与评论：在对应 Issue 下留言（例如功能演进讨论 [#132](https://github.com/Drlinglong/Remis/issues/132)）

## 阅读顺序

1. [rag-corpus-boundary.md](rag-corpus-boundary.md) — 先分清 `user-help` 与 `agent-planning`
2. [agent-operations.md](agent-operations.md) — 再固定「Agent 能干什么」
3. `agent-planning`：按功能成对阅读[产品意图](../product-intent-agent-copilot.md)和
   [当前开发契约](../developer/agent-copilot-contract.md)；执行能力仍以 Action Registry 为准。
4. `user-help`（已进白名单、供答疑检索）：
   - [从零开始](../user-guides/getting-started.md)（**首读**：建项目 → 初次翻译 → 部署）
   - [项目管理](../user-guides/project-management.md)
   - [增量翻译](../user-guides/incremental-update.md)
   - [导入已有译文](../user-guides/import-existing-translations.md)
   - [Provider 速查](../user-guides/provider-setup-index.md)
   - [一键部署](../user-guides/one-click-deploy.md)
   - [假本地化](../user-guides/fake-localization.md)
   - [校对](../user-guides/proofreading.md)
   - [智能工坊](../user-guides/agent-workshop.md)
   - [词典与词汇表](../user-guides/glossary.md)
   - [模型竞技场](../user-guides/model-arena.md)
   - [任务中心](../user-guides/task-center.md)
   - [官方参考语料库](../user-guides/reference-library.md)
   - [Remis 小助手](../user-guides/remis-assistant.md)
   - [项目追踪](../user-guides/project-tracking.md)
   - [新词审判庭](../user-guides/neologism-tribunal.md)
   - [Steam 工坊发布](../user-guides/steam-workshop.md)
   - [工具：封面图生成器](../user-guides/tools-thumbnail-generator.md)
   - [设置](../user-guides/settings.md)
   - [日志与诊断](../user-guides/logs-and-diagnostics.md)
   - [错误目录](../user-guides/error-catalog.md)
   - 以及 FAQ 与各 Provider 补充专文

5. 新补齐的 `agent-planning` 功能对：
   - [项目管理产品意图](../product-intent-project-management.md) +
     [开发契约](../developer/project-management-contract.md)
   - [Mod 监控产品意图](../product-intent-project-tracking.md) +
     [开发契约](../developer/project-tracking-contract.md)
   - [封面图生成器产品意图](../product-intent-thumbnail-generator.md) +
     [开发契约](../developer/thumbnail-generator-contract.md)
   - [Steam 工坊产品意图](../product-intent-steam-workshop.md) +
     [开发契约](../developer/steam-workshop-contract.md)

产品意图描述目标，开发契约明确当前实现与差距。Agent 遇到“未实现”或“冲突”项时只能
解释或提出计划，不能把它登记成当前可执行 action。

## 非目标

- 不做可自由改用户目录的自治 Agent
- 不做开发者编码助手
- 不把架构 / CI / 重构文档当用户帮助内容
- 不把归档实施计划或未来愿景当成当前可执行能力
