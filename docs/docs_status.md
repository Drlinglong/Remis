# Documentation Status

这份文件用于说明 `docs/` 中哪些文档更适合当作当前入口，哪些更适合当作历史记录或专题实现笔记。

## 建议优先阅读

### 当前入口

- 根目录 `GEMINI.md`
- `docs/documentation-center.md`
- `docs/zh/index.md`
- `docs/en/index.md`
- `docs/archive/README.md`

### 当前协作与维护

- `docs/zh/developer/refactor_decision_guide.md`
- `docs/zh/developer/ci-setup.md`
- `docs/zh/developer/development-setup.md`
- `docs/zh/developer/build-release-script-guide.md`
- `docs/zh/developer/feature_flags.md`

### 产品 Copilot 设计（#132，未实现）

面向「用户帮助 + 结构化操作建议」，**不是**开发者编码助手。普通用户使用 Tauri 打包客户端，Copilot 不能改 Remis 源码。

- `docs/zh/copilot/README.md` — 入口与三类材料划分
- `docs/zh/copilot/rag-corpus-boundary.md` — 用户 Micro-RAG 白名单/黑名单（开发者文档默认不进索引）
- `docs/zh/copilot/agent-operations.md` — Agent 可提议的操作、禁止项、GitHub 反馈引导

注意：`docs/zh/copilot/` 与 `docs/zh/developer/**` **默认不作为用户 RAG 语料**；用户答疑语料以 `docs/zh/user-guides/**` 为主。

与 #132 Help 语料直接相关的用户短文（优先索引）：

- `docs/zh/user-guides/getting-started.md`（项目制入门，先建项目再翻译）
- `docs/zh/user-guides/incremental-update.md`
- `docs/zh/user-guides/import-existing-translations.md`
- `docs/zh/user-guides/provider-setup-index.md`
- `docs/zh/user-guides/one-click-deploy.md`
- `docs/zh/user-guides/fake-localization.md`
- `docs/zh/user-guides/proofreading.md`
- `docs/zh/user-guides/agent-workshop.md`
- `docs/zh/user-guides/glossary.md`
- `docs/zh/user-guides/logs-and-diagnostics.md`
- `docs/zh/user-guides/error-catalog.md`
- `docs/zh/user-guides/faq.md`（已按客户端工作流修订）

## 作为专题参考阅读

这类文档通常有价值，但更适合在修改对应模块时按需查阅：

- 响应解析相关重构说明
- 并行处理相关实现说明
- 标点处理、动态验证器、Gemini CLI 集成等专题文档

## 作为历史记录阅读

以下文档可能仍有背景价值，但不应默认当作“当前事实”：

- `docs/agent.md`
- `docs/en/agent.md`
- 一些较早的架构总览文档
- 某些面向特定版本或特定发布阶段的报告
- `docs/archive/` 下的归档文档
- `docs/archive/developer-history/` 下的开发历史文档

## 使用原则

- 当文档与当前代码冲突时，以当前代码为准。
- 当文档与根目录 `GEMINI.md` 冲突时，以 `GEMINI.md` 为准。
- 当某份文档明显描述的是一次重构或一次版本演进，应将其视为“历史决策记录”，而不是永久规范。
- 当一份文档已移动到 `docs/archive/`，说明它已退出主入口，不再作为默认阅读材料。
