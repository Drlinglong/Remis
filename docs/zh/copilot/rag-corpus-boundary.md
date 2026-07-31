# Copilot 与 Agent 双层语料边界

> **Status:** Current governance contract（3.1.0 文档基线，#132）
> **Audience:** 实现者 / 维护者
> **Purpose:** 分开规定 `user-help` 与 `agent-planning` 的检索语料。
> **Note:** 本文档是准入规则本身，**不要** 编入任一检索语料。

## 1. 定位

Remis 使用两层目的不同的语料，不能把所有文档混成一个知识库。

`user-help` 服务于 **终端用户**（汉化者、玩家、非开发者），回答例如：

- API Key / Provider / Base URL 怎么配？
- 日志在哪里？
- 什么是假本地化？
- 某条校验报错是什么意思？
- 翻译好的 Mod 怎么放进游戏？

`agent-planning` 服务于 Remis Agent 理解功能目的、当前能力和不可越过的边界。它帮助
Agent 把用户目标整理成可批准计划，但不会因此获得新的 action，也不能绕过 Action Registry。

## 2. 两层语料

| 语料层 | 回答的问题 | 主要来源 | 不应回答 |
|---|---|---|---|
| `user-help` | “这个功能怎么用、失败后怎么办？” | 用户指南 | 源码怎么改、未来功能能否执行 |
| `agent-planning` | “用户为什么需要它、当前允许怎样规划、边界是什么？” | 产品意图 + 现行开发契约 | 把设计愿景冒充已实现 action |

两层都必须排除 `docs/archive/**`、秘密、本机路径和用户私有项目全文。检索结果不能改变
system instructions、工具 schema、`allowed_actions` 或审批要求。

## 3. `user-help` 白名单（允许）

仅索引 **面向用户、描述产品用法** 的材料。

### 3.1 默认纳入

| 路径 / 来源 | 说明 |
|-------------|------|
| `docs/zh/user-guides/**` | 中文用户指南（主语料） |
| `docs/en/user-guides/**` | 英文用户指南（若启用多语言答疑） |
| `docs/zh/glossary/**` 中面向使用者的说明 | 词典是什么、怎么用（勿索引纯工具链内部细节若与用户无关） |
| `docs/README_ZH.md` / `README.md` 中的用户可见章节 | 安装、功能概览、获取方式；跳过纯开发贡献说明（若整文件索引，需在分块时降权或裁剪） |
| 当前版本的用户发布摘要 | 只有整理为当前用户向短文后才纳入；不直接读取 `docs/archive/**` |

### 3.2 已补齐、应优先纳入索引的用户文档

| 主题 | 路径 | 期望读者问题 |
|------|------|----------------|
| 从零开始 | `docs/zh/user-guides/getting-started.md` | 「怎么开始汉化？」「要不要先点初次翻译？」；强调 **先项目管理建项** |
| 项目管理 | `docs/zh/user-guides/project-management.md` | 「项目是什么？」「移动目录后怎么办？」「归档和删除有什么区别？」 |
| 增量翻译 | `docs/zh/user-guides/incremental-update.md` | 「Mod 更新了」「只翻新的」；需归档基线 |
| 翻译上载 / 半成品 | `docs/zh/user-guides/import-existing-translations.md` | 「别人的汉化怎么导入」 |
| Provider 速查 | `docs/zh/user-guides/provider-setup-index.md` | 「API 填哪里」「Ollama 怎么配」→ **设置 → API** |
| 一键部署 | `docs/zh/user-guides/one-click-deploy.md` | 「怎么装进游戏」「部署点哪里」 |
| 假本地化 | `docs/zh/user-guides/fake-localization.md` | 「假中文是什么」；**优先内置清理**，手动备用 |
| 校对 | `docs/zh/user-guides/proofreading.md` | 「怎么手改译文」「补丁模式」 |
| 智能工坊 | `docs/zh/user-guides/agent-workshop.md` | 「扫描修复格式」「变量批量修」 |
| 词典 / 词汇表 | `docs/zh/user-guides/glossary.md` | 「术语不统一」「主词典怎么开」；UI 向，非 developer glossary 工具链 |
| 日志与诊断 | `docs/zh/user-guides/logs-and-diagnostics.md` | 「日志在哪？」「闪退看什么？」 |
| 错误目录 | `docs/zh/user-guides/error-catalog.md` | 「变量被翻译是什么意思？」「格式标签怎么修？」 |
| 项目追踪 | `docs/zh/user-guides/project-tracking.md` | 「项目追踪是干什么的？」「怎么监控创意工坊更新？」 |
| 新词审判庭 | `docs/zh/user-guides/neologism-tribunal.md` | 「怎么挖新词？」「审判庭怎么批词？」 |
| 封面图生成器 | `docs/zh/user-guides/tools-thumbnail-generator.md` | 「工具里能做什么？」「怎么做工坊封面？」 |
| 设置 | `docs/zh/user-guides/settings.md` | 「设置里有什么？」「RPM / 重置数据库是什么？」 |

### 3.3 本轮补齐的 `agent-planning` 登记

下列功能已形成产品意图与当前开发契约，按本页第 5 节的通配白名单进入
`agent-planning`：

| 功能 | 产品意图 | 当前开发契约 |
|---|---|---|
| 项目管理 | `docs/zh/product-intent-project-management.md` | `docs/zh/developer/project-management-contract.md` |
| Mod 监控 | `docs/zh/product-intent-project-tracking.md` | `docs/zh/developer/project-tracking-contract.md` |
| 封面图生成器 | `docs/zh/product-intent-thumbnail-generator.md` | `docs/zh/developer/thumbnail-generator-contract.md` |

其中项目归档影响监控、监控去重与纯移动告警、项目删除历史，以及封面项目集成均是
**当前差距**。检索层必须保留段落标题和状态语义，不能把目标态句子裁成“当前已支持”。

### 3.4 仍建议后续补强的用户文档

| 主题 | 期望读者问题 |
|------|----------------|
| Provider 速查总表 | 「Gemini / Ollama / OpenRouter / 自定义 OpenAI 填哪里？」（可从现有 `using_*.md` 提炼索引页） |
| 客户端数据位置（用户版表述） | 「我的项目数据在哪？」（仅安装版通用路径，不用开发机绝对路径） |

### 3.5 分块与语言

- 优先中文用户语料；用户界面语言为英文时再检索英文 user-guides。
- 分块粒度：以「一个完整 FAQ 问答」或「一个配置小节」为宜，避免整本大文件无标题硬切导致答非所问。
- 检索结果应能回传 **可读的来源标题/相对路径**（给 `sources` 字段），不要回传本机绝对路径。

## 4. `user-help` 黑名单（禁止）

以下内容 **默认不得** 进入用户 Micro-RAG。

### 4.1 开发者与工程文档

| 路径 / 类型 | 原因 |
|-------------|------|
| `docs/zh/developer/**` | 架构、CI、重构、功能开关、增量实现备忘等，面向维护者 |
| `docs/en/developer/**` | 同上 |
| `docs/zh/technical/**` | 如 RAG 选型、数据库迁移等工程方案 |
| `docs/agent.md`、`docs/en/agent.md` | 已降级的旧 Agent/协作规章，不是产品帮助 |
| `docs/archive/**`、开发历史、专题实现笔记 | 易过时，易误导用户 |
| `AGENTS.md` 及仓库协作规章 | 给写代码的 Agent/人，不是终端用户手册 |

### 4.2 源码与构建产物

| 类型 | 原因 |
|------|------|
| `scripts/**`、`tests/**`、前端源码 | 用户客户端不可改、也不应据此答「怎么改软件」 |
| `build/**`、`dist/**`、`venv/**` | 无用户帮助价值 |
| 规格说明 / 打包脚本细节 | 易诱导「自己改源码」 |

### 4.3 敏感与用户私有数据

| 类型 | 原因 |
|------|------|
| API Key、Token、Cookie、环境变量真实值 | 安全 |
| 任意用户 Mod 全文（默认） | 隐私与体积；Help 语料不是项目翻译内容 |
| 本机绝对路径、开发者用户名路径 | 如 `J:\...`、`C:\Users\某开发者\...` 不应出现在通用语料中 |
| 密钥配置文件、本地数据库全文 | 安全 |

### 4.4 错误示范：不要用开发者文档「顶替」用户语料

| 用户问题 | 错误语料 | 正确做法 |
|----------|----------|----------|
| 日志在哪？ | `docs/zh/developer/user_data_paths.md`（含开发机路径） | 用户向「日志与诊断」短文，只写安装版/便携版通用路径与 UI 入口 |
| Remis 架构？ | `architecture.md` | **不回答工程架构**；说明这是用户工具，功能问题去 GitHub 反馈 |
| 怎么改翻译逻辑？ | 任意 `scripts/core/**` | 说明客户端无法改源码，引导 GitHub Issue |

## 5. `agent-planning` 白名单与优先级

只纳入已经通过文档治理的稳定材料：

| 路径 / 类型 | 用途 |
|---|---|
| `docs/zh/product-intent-*.md` | 理解用户目标、产品边界、明确非目标 |
| `docs/zh/developer/*-contract.md` | 核验 3.1.0 当前能力、实现差距、失败语义和测试门禁 |

`docs/zh/product-intent-template.md` 是治理模板，不是具体功能事实，默认不参与运行时检索。
`docs/zh/copilot/agent-operations.md` 应作为固定 system/tool 能力附录加载，不通过 RAG
召回，避免关键禁止项因检索排序而丢失。

同一功能的材料发生差异时按下面顺序解释：

1. `allowed_actions`、工具 schema 与持久化任务状态决定“现在能否执行、是否完成”；
2. 现行开发契约决定“当前实现怎样工作、有哪些差距”；
3. 产品意图决定“为什么存在、绝不能越过什么边界”；
4. 用户指南只提供面向用户的表达，不扩大 Agent 能力。

以下材料即使与功能相关，也不进入 `agent-planning`：

- 普通 `docs/zh/developer/**` 实现笔记、一次性计划和专题总结；
- `docs/zh/technical/**` 选型文档；
- `docs/archive/**` 历史材料；
- 根目录 `AGENTS.md` 和旧 `docs/agent.md`（仓库协作规则不属于产品 Agent）；
- 尚未整理成产品意图或现行契约的愿景草稿。

## 6. 与「项目内容检索」的边界

| 通道 | 数据 | 用途 |
|------|------|------|
| **`user-help`（本文）** | 用户指南 | Help Copilot 答疑 |
| **`agent-planning`（本文）** | 产品意图与现行开发契约 | 把用户目标整理成受限计划 |
| **Translation QA（另案）** | 用户项目 localization / glossary 等 | 只读质量评估；**不是**产品文档索引 |
| **命令意图** | 无文档检索或仅辅助 | 输出结构化 `CommandIntent`，执行走 Action Registry |

不要把「翻译项目全文」默认并入 Help 的文档索引。

## 7. 索引构建检查清单

发布或重建用户知识库前确认：

- [ ] 白名单路径均存在且为用户向表述
- [ ] `user-help` 与 `agent-planning` 使用不同集合、不同检索过滤
- [ ] 黑名单与 `docs/archive/**` 未混入
- [ ] 无 API Key / 密钥样例真值
- [ ] 无开发机绝对路径、无内部用户名
- [ ] 过时 FAQ（例如仅适用于已废弃启动方式）已更新或降权
- [ ] 抽检：对「怎么改 Remis 代码」类问题，检索结果不应指向源码树
- [ ] 抽检：Agent 不会把产品愿景中的未来能力说成当前可执行 action
- [ ] 抽检：任务是否完成只依据持久化状态，不依据文档叙述

## 8. 维护规则

1. **新增用户帮助** → 放在 `docs/zh/user-guides/`，进入 `user-help`。
2. **新增产品判断** → 先填写 `product-intent-*.md`，经确认后才进入 `agent-planning`。
3. **新增当前实现事实** → 整理成 `*-contract.md`；普通设计笔记默认不索引。
4. **Copilot 固定能力说明** → 维护 `agent-operations.md`，作为 system/tool 附录而非 RAG。
5. **文档退出当前入口** → 移入 `docs/archive/**`，并从两层语料中排除。
6. 语料变更后分别重建或增量更新两层索引，并各做黄金问题回归。
