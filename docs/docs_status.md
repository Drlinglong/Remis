# Documentation Status

这份文件用于说明 `docs/` 中哪些文档更适合当作当前入口，哪些更适合当作历史记录或专题实现笔记。

## 轻量状态字段

本页是文档状态的中央登记入口。为了避免每份文档复制一套容易漂移的元数据，优先按路径
和下表登记；只有历史文档需要在文件开头额外写明替代文档。

| 字段 | 可用值 | 含义 |
|---|---|---|
| `status` | `current` / `draft` / `historical` | 文档能否作为当前事实使用；不等同于功能是否已向用户开放 |
| `audience` | `user` / `product` / `developer` / `agent` | 主要读者 |
| `canonical_for` | 功能或规则名 | 该文档负责回答的唯一问题 |
| `superseded_by` | 相对路径 | 历史文档的现行替代；当前文档可省略 |
| `copilot_scope` | `user-help` / `agent-planning` / `excluded` | 可进入哪一层语料 |
| `last_verified` | 版本号或日期 | 最近一次按实现核验的基线 |

### 路径默认值

| 路径 | status | audience | copilot_scope | canonical_for |
|---|---|---|---|---|
| `docs/zh/user-guides/**` | `current` | `user` | `user-help` | 用户何时使用、如何操作、失败后怎么办 |
| `docs/zh/product-intent-<feature>.md` | `current` | `product`, `agent` | `agent-planning` | 为什么存在、产品边界、明确非目标 |
| `docs/zh/product-intent-template.md` | `current` | `product`, `agent` | `excluded` | 文档治理模板，不是具体功能事实 |
| `docs/zh/developer/*-contract.md` | `current` | `developer`, `agent` | `agent-planning` | 当前实现、实现差距、回归门禁 |
| `docs/zh/copilot/agent-operations.md` | `current` | `agent` | `excluded` | 固定 system/tool 能力说明，不通过 RAG 检索 |
| `docs/zh/copilot/rag-corpus-boundary.md` | `current` | `developer`, `agent` | `excluded` | 语料准入规则本身 |
| `docs/archive/**` | `historical` | 按文档而定 | `excluded` | 历史背景，不作为当前事实 |

未被明确登记的专题文档默认是参考材料，`copilot_scope: excluded`。需要进入语料时，先把它
改造成对应的用户指南、产品意图或开发契约，而不是直接扩大目录白名单。

第一轮治理完成的核心模块以 3.1.0 为 `last_verified`：翻译主流程、部署、校对、术语表、
Model Arena、Task Center、智能工坊，以及 Agent / Copilot 隐藏预览。

第二轮功能覆盖以 2026-07-31 代码为 `last_verified`：项目管理、Mod 监控与封面图生成器。
这三组文档已分别形成产品意图、用户指南和开发契约；契约中的“当前差距”不是当前能力，
不得被 Copilot 当作已经实现。

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
- `docs/zh/product-intent-project-management.md` — 长期项目身份、生命周期、删除和 Agent 边界
- `docs/zh/developer/project-management-contract.md` — 项目当前数据流、删除副作用与实现差距
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
- `docs/zh/product-intent-reference-library.md` — 官方译文复用、维护交互与数据删除边界
- `docs/zh/developer/reference-library-contract.md` — 精确匹配、SQLite 索引、进度任务与回归门禁
- `docs/zh/product-intent-agent-workshop.md` — 格式安全护栏、自动写回、有限重试与明确非目标
- `docs/zh/developer/agent-workshop-contract.md` — 扫描、模型修复、逐条写回、实现差距与测试门禁
- `docs/zh/product-intent-project-tracking.md` — 本地化文件只读监控、告警与 Agent 边界
- `docs/zh/developer/project-tracking-contract.md` — SHA 快照、调度、确认和生命周期差距
- `docs/zh/product-intent-thumbnail-generator.md` — 封面编辑、项目资产与禁止写源目录
- `docs/zh/developer/thumbnail-generator-contract.md` — 当前前端实现、输出格式与项目集成门禁

### 当前协作与维护

- `docs/zh/developer/refactor_decision_guide.md`
- `docs/zh/developer/ci-setup.md`
- `docs/zh/developer/development-setup.md`
- `docs/zh/developer/build-release-script-guide.md`
- `docs/zh/developer/feature_flags.md`

### Remis Agent / Copilot 产品契约与隐藏工程预览（#132）

面向普通用户的同一聊天入口：Copilot 负责帮助答疑，Agent 负责把自然语言目标整理成待批准
的 Remis 工作流。它不是开发者编码助手，也不能直接改文件。3.1.1 保留代码与测试作为隐藏
工程预览；公开版本仍需完成发布门禁，当前尚未支持通用多步骤编排和聊天内终态总结。

- `docs/zh/product-intent-agent-copilot.md` — 用户价值、统一入口、确认、成功标准与公开目标
- `docs/zh/user-guides/remis-assistant.md` — 普通用户如何提问、批准计划和判断真实完成
- `docs/zh/developer/agent-copilot-contract.md` — 当前入口、Registry、计划执行、终态与差距
- `docs/zh/copilot/README.md` — 双层语料与固定操作契约入口
- `docs/zh/copilot/rag-corpus-boundary.md` — `user-help` 与 `agent-planning` 双层语料边界
- `docs/zh/copilot/agent-operations.md` — Agent 可提议的操作、禁止项、GitHub 反馈引导

注意：`docs/zh/developer/**` **不进入用户答疑语料**。只有命名为 `*-contract.md` 的现行
开发契约可进入独立的 `agent-planning` 语料；其他开发文档默认排除。

与 #132 Help 语料直接相关的用户短文（优先索引）：

- `docs/zh/user-guides/getting-started.md`（项目制入门，先建项目再翻译）
- `docs/zh/user-guides/project-management.md`
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
- `docs/zh/user-guides/reference-library.md`
- `docs/zh/user-guides/remis-assistant.md`
- `docs/zh/user-guides/project-tracking.md`
- `docs/zh/user-guides/tools-thumbnail-generator.md`
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
- 已弃用的 `incremental_update_mvp_checklist.md`
- 增量更新 MVP 状态、Model Arena 实施计划和格式提示词改造等阶段快照

## 使用原则

- 当前行为与实现事实以代码和测试为准。
- 仓库协作、安全边界和验证要求以根目录 `AGENTS.md` 为准。
- 当某份文档明显描述的是一次重构或一次版本演进，应将其视为“历史决策记录”，而不是永久规范。
- 当一份文档已移动到 `docs/archive/`，说明它已退出主入口，不再作为默认阅读材料。
- Copilot 答疑只读 `user-help`；Agent 规划只读 `agent-planning`，并以当前开发契约限制可执行能力。
