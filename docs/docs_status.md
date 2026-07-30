# Documentation Status

这份文件用于说明 `docs/` 中哪些文档更适合当作当前入口，哪些更适合当作历史记录或专题实现笔记。

## 建议优先阅读

### 当前入口

- 根目录 `AGENTS.md`（仓库协作与安全规则）
- `docs/documentation-center.md`
- `docs/zh/index.md`
- `docs/en/index.md`
- `docs/archive/README.md`

### 产品意图与开发契约

- `docs/zh/product-intent-template.md` — 产品负责人问答与 Agent 核验模板
- `docs/zh/product-intent-project-file-discovery.md` — 已填写的文件发现示例
- `docs/zh/product-intent-translation-workflows.md` — 初次与增量翻译产品意图
- `docs/zh/developer/translation-workflow-contract.md` — 当前代码事实、目标边界与测试门禁
- `docs/zh/product-intent-deployment.md` — 部署目标、确认边界与明确非目标
- `docs/zh/developer/deployment-contract.md` — 部署当前实现、产品差距与测试门禁
- `docs/zh/product-intent-proofreading.md` — 校对目标、人工定稿优先级与功能边界
- `docs/zh/developer/proofreading-contract.md` — 文件级保存、冲突保护、Issue #149 与已知缺陷
- `docs/zh/product-intent-glossary.md` — 术语范围、上下文优先、确认边界与非目标
- `docs/zh/developer/glossary-contract.md` — 当前优先级、数据副作用、实现差距与测试门禁
- `docs/zh/product-intent-model-arena.md` — 小样选模、人工投票、确认与禁止副作用
- `docs/zh/developer/model-arena-contract.md` — 抽样、执行、匿名、历史、导出与当前边界
- `docs/zh/product-intent-task-center.md` — 后台任务收件箱、处理语义与主页信息架构边界
- `docs/zh/developer/task-center-contract.md` — 持久化状态、详情摘要、历史与 Agent 消费契约
- `docs/zh/product-intent-agent-workshop.md` — 格式安全护栏、自动写回、有限重试与明确非目标
- `docs/zh/developer/agent-workshop-contract.md` — 扫描、模型修复、逐条写回、实现差距与测试门禁

### 当前协作与维护

- `docs/zh/developer/refactor_decision_guide.md`
- `docs/zh/developer/ci-setup.md`
- `docs/zh/developer/development-setup.md`
- `docs/zh/developer/build-release-script-guide.md`
- `docs/zh/developer/feature_flags.md`

### Remis Agent / Copilot 产品契约与隐藏工程预览（#132）

面向普通用户的同一聊天入口：Copilot 负责帮助答疑，Agent 负责把自然语言目标整理成待批准
的 Remis 工作流。它不是开发者编码助手，也不能直接改文件。3.1.0 保留代码与测试作为隐藏
工程预览；下一版本目标是公开第一版，当前尚未支持通用多步骤编排和聊天内终态总结。

- `docs/zh/product-intent-agent-copilot.md` — 用户价值、统一入口、确认、成功标准与公开目标
- `docs/zh/user-guides/remis-assistant.md` — 普通用户如何提问、批准计划和判断真实完成
- `docs/zh/developer/agent-copilot-contract.md` — 当前入口、Registry、计划执行、终态与差距
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
- `docs/zh/user-guides/model-arena.md`
- `docs/zh/user-guides/task-center.md`
- `docs/zh/user-guides/remis-assistant.md`
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

- 当前行为与实现事实以代码和测试为准。
- 仓库协作、安全边界和验证要求以根目录 `AGENTS.md` 为准。
- 当某份文档明显描述的是一次重构或一次版本演进，应将其视为“历史决策记录”，而不是永久规范。
- 当一份文档已移动到 `docs/archive/`，说明它已退出主入口，不再作为默认阅读材料。
