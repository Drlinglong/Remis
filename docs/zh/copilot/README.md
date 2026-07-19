# Remis Copilot 文档

> **Status:** Design draft（#132 地基）
> **Related:** [Issue #132](https://github.com/Drlinglong/Remis/issues/132)

本目录存放 **Remis 产品 Copilot** 相关说明，与「开发者如何改代码」无关。

## 三类读者，三类材料

| 材料 | 读者 | 是否进入用户 Micro-RAG | 说明 |
|------|------|------------------------|------|
| [用户语料边界](rag-corpus-boundary.md) | 实现者 / 维护者 | 否（这是索引规则本身） | 规定 RAG **可以**和**不可以**索引什么 |
| [Agent 操作说明书](agent-operations.md) | Copilot（模型侧） | 否（走 system / tool 说明，不是用户文档检索） | 只描述能提议的操作、禁止项、如何引导用户 |
| `docs/zh/user-guides/**` 等 | 终端用户 | **是** | 真正的答疑语料 |

## 原则（一句话）

- **用户 RAG**：回答「Remis 怎么用」。
- **Agent 说明书**：回答「我能建议系统做什么」。
- **开发者文档**（`docs/zh/developer/**`、`docs/zh/technical/**`）：回答「代码怎么接」——**默认不进用户 RAG，也不塞进 Agent 长上下文。**

## 产品形态前提

普通用户拿到的是 **Tauri 封装的安装版 / 便携客户端**，不是本仓库的开发工作区。

因此 Copilot：

- **不能**、也**不需要**修改 Remis 源代码；
- 遇到功能请求、程序缺陷、需要改软件本身的问题，应引导用户到 GitHub 反馈，而不是假装能改客户端。

反馈入口：

- Issues：<https://github.com/Drlinglong/Remis/issues>
- 讨论与评论：在对应 Issue 下留言（例如功能演进讨论 [#132](https://github.com/Drlinglong/Remis/issues/132)）

## 阅读顺序

1. [rag-corpus-boundary.md](rag-corpus-boundary.md) — 先定「喂什么」
2. [agent-operations.md](agent-operations.md) — 再定「Agent 能干什么」
3. 用户语料（已进白名单、供 Micro-RAG 索引）：
   - [从零开始](../user-guides/getting-started.md)（**首读**：建项目 → 初次翻译 → 部署）
   - [增量翻译](../user-guides/incremental-update.md)
   - [导入已有译文](../user-guides/import-existing-translations.md)
   - [Provider 速查](../user-guides/provider-setup-index.md)
   - [一键部署](../user-guides/one-click-deploy.md)
   - [假本地化](../user-guides/fake-localization.md)
   - [校对](../user-guides/proofreading.md)
   - [智能工坊](../user-guides/agent-workshop.md)
   - [词典与词汇表](../user-guides/glossary.md)
   - [项目追踪](../user-guides/project-tracking.md)
   - [新词审判庭](../user-guides/neologism-tribunal.md)
   - [工具：封面图生成器](../user-guides/tools-thumbnail-generator.md)
   - [设置](../user-guides/settings.md)
   - [日志与诊断](../user-guides/logs-and-diagnostics.md)
   - [错误目录](../user-guides/error-catalog.md)
   - 以及 FAQ 与各 Provider 补充专文

## 非目标

- 不做可自由改用户目录的自治 Agent
- 不做开发者编码助手
- 不把架构 / CI / 重构文档当用户帮助内容
