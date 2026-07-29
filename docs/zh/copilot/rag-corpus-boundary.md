# 用户 Micro-RAG 语料边界

> **Status:** Design draft（#132）
> **Audience:** 实现者 / 维护者
> **Purpose:** 规定 Help Copilot 的检索语料 **白名单与黑名单**。
> **Note:** 本文档本身 **不要** 编入用户 RAG 索引。

## 1. 定位

Micro-RAG 服务于 **终端用户**（汉化者、玩家、非开发者），回答例如：

- API Key / Provider / Base URL 怎么配？
- 日志在哪里？
- 什么是假本地化？
- 某条校验报错是什么意思？
- 翻译好的 Mod 怎么放进游戏？

它 **不是** 开发者文档搜索，也 **不是** 代码库问答。

## 2. 索引白名单（允许）

仅索引 **面向用户、描述产品用法** 的材料。

### 2.1 默认纳入

| 路径 / 来源 | 说明 |
|-------------|------|
| `docs/zh/user-guides/**` | 中文用户指南（主语料） |
| `docs/en/user-guides/**` | 英文用户指南（若启用多语言答疑） |
| `docs/zh/glossary/**` 中面向使用者的说明 | 词典是什么、怎么用（勿索引纯工具链内部细节若与用户无关） |
| `docs/README_ZH.md` / `README.md` 中的用户可见章节 | 安装、功能概览、获取方式；跳过纯开发贡献说明（若整文件索引，需在分块时降权或裁剪） |
| 面向用户的发布说明摘要 | 可选：`archive/release_notes/` 中 **用户可见变更**；过时条目应标记或排除 |

### 2.2 已补齐、应优先纳入索引的用户文档

| 主题 | 路径 | 期望读者问题 |
|------|------|----------------|
| 从零开始 | `docs/zh/user-guides/getting-started.md` | 「怎么开始汉化？」「要不要先点初次翻译？」；强调 **先项目管理建项** |
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

### 2.3 仍建议后续补强的用户文档

| 主题 | 期望读者问题 |
|------|----------------|
| Provider 速查总表 | 「Gemini / Ollama / OpenRouter / 自定义 OpenAI 填哪里？」（可从现有 `using_*.md` 提炼索引页） |
| 客户端数据位置（用户版表述） | 「我的项目数据在哪？」（仅安装版通用路径，不用开发机绝对路径） |

### 2.4 分块与语言

- 优先中文用户语料；用户界面语言为英文时再检索英文 user-guides。
- 分块粒度：以「一个完整 FAQ 问答」或「一个配置小节」为宜，避免整本大文件无标题硬切导致答非所问。
- 检索结果应能回传 **可读的来源标题/相对路径**（给 `sources` 字段），不要回传本机绝对路径。

## 3. 索引黑名单（禁止）

以下内容 **默认不得** 进入用户 Micro-RAG。

### 3.1 开发者与工程文档

| 路径 / 类型 | 原因 |
|-------------|------|
| `docs/zh/developer/**` | 架构、CI、重构、功能开关、增量实现备忘等，面向维护者 |
| `docs/en/developer/**` | 同上 |
| `docs/zh/technical/**` | 如 RAG 选型、数据库迁移等工程方案 |
| `docs/agent.md`、`docs/en/agent.md` | 已降级的旧 Agent/协作规章，不是产品帮助 |
| `docs/archive/**`、开发历史、专题实现笔记 | 易过时，易误导用户 |
| `AGENTS.md` 及仓库协作规章 | 给写代码的 Agent/人，不是终端用户手册 |

### 3.2 源码与构建产物

| 类型 | 原因 |
|------|------|
| `scripts/**`、`tests/**`、前端源码 | 用户客户端不可改、也不应据此答「怎么改软件」 |
| `build/**`、`dist/**`、`venv/**` | 无用户帮助价值 |
| 规格说明 / 打包脚本细节 | 易诱导「自己改源码」 |

### 3.3 敏感与用户私有数据

| 类型 | 原因 |
|------|------|
| API Key、Token、Cookie、环境变量真实值 | 安全 |
| 任意用户 Mod 全文（默认） | 隐私与体积；Help 语料不是项目翻译内容 |
| 本机绝对路径、开发者用户名路径 | 如 `J:\...`、`C:\Users\某开发者\...` 不应出现在通用语料中 |
| 密钥配置文件、本地数据库全文 | 安全 |

### 3.4 错误示范：不要用开发者文档「顶替」用户语料

| 用户问题 | 错误语料 | 正确做法 |
|----------|----------|----------|
| 日志在哪？ | `docs/zh/developer/user_data_paths.md`（含开发机路径） | 用户向「日志与诊断」短文，只写安装版/便携版通用路径与 UI 入口 |
| Remis 架构？ | `architecture.md` | **不回答工程架构**；说明这是用户工具，功能问题去 GitHub 反馈 |
| 怎么改翻译逻辑？ | 任意 `scripts/core/**` | 说明客户端无法改源码，引导 GitHub Issue |

## 4. 与「项目内容检索」的边界

| 通道 | 数据 | 用途 |
|------|------|------|
| **用户 Micro-RAG（本文）** | 产品文档 | Help Copilot 答疑 |
| **Translation QA（另案）** | 用户项目 localization / glossary 等 | 只读质量评估；**不是**产品文档索引 |
| **命令意图** | 无文档检索或仅辅助 | 输出结构化 `CommandIntent`，执行走 Action Registry |

不要把「翻译项目全文」默认并入 Help 的文档索引。

## 5. 索引构建检查清单

发布或重建用户知识库前确认：

- [ ] 白名单路径均存在且为用户向表述
- [ ] 黑名单路径未混入
- [ ] 无 API Key / 密钥样例真值
- [ ] 无开发机绝对路径、无内部用户名
- [ ] 过时 FAQ（例如仅适用于已废弃启动方式）已更新或降权
- [ ] 抽检：对「怎么改 Remis 代码」类问题，检索结果不应指向源码树

## 6. 维护规则

1. **新增用户帮助** → 放在 `docs/zh/user-guides/`（或明确的用户向路径），再加入索引。
2. **新增开发设计** → 放在 `docs/zh/developer/` 或 `docs/zh/technical/`，**默认不索引**。
3. **Copilot 设计/能力说明** → 放在 `docs/zh/copilot/`；其中操作说明书给模型配置用，**不作为用户浏览语料全文检索的主体**（用户不需要读 Registry 表）。
4. 语料变更后应重建或增量更新向量索引，并做少量黄金问题回归（见后续 benchmark 文档）。
