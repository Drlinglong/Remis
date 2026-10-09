# Remis v3.3.0 发布准备记录

准备日期：2026-10-10

状态：v3.3.0 构建与验证记录；正式发布信息以 GitHub Release 为准。

## 中文

## 主要更新

- **任务可靠性：**取消、启动失败和重启恢复更一致；未能启动的任务不再一直占用项目，保存进度失败会明确提示。
- **翻译文本完整性：**原文的语义标记、引号和换行完整传给模型；完善结构化返回及多行火星 CSV 的处理。
- **模型设置：**Claude 5.5 系列支持 `claude-opus-5-5`、`claude-sonnet-5-5` 和 `claude-haiku-5-5`；本版新增 Haiku，并完善三款的推理参数支持。新增／更新的其他目录代号包括 xAI `grok-4.7`、Qwen `qwen3.8-flash`、DeepSeek `deepseek-flash`、OpenRouter `openai/gpt-6.1-sol`、ModelScope `deepseek-ai/DeepSeek-V4-Pro-0813` 与 `deepseek-ai/DeepSeek-V4.1-Flash`、NVIDIA `deepseek-ai/deepseek-v4.1-flash`。完善已有 GPT-6／GPT-6.1、Muse Spark 等模型的推理参数支持，修复选择的推理参数未实际发送、采样参数冲突及冻结任务模型不一致的问题。保留用户已保存的设置；使用已迁移旧模型代号的用户需在设置中重新选择受支持的代号。
- **词典资源：**发布时附带火星求生英／简中及英／简中／正体词典 ZIP 和 SHA256 校验文件，可独立下载；条目保留来源、语境及审阅状态，不将候选译名宣称为全部人工认证。

## 高级 Agent 功能与开放边界

原生 OpenAI／OpenRouter Batch 和简繁／区域用语转换通过高级 Agent API 提供，没有新增普通用户 GUI。提交、应用与外发文本均遵守现有授权；持久任务与输入／原始返回／诊断保留，未知提交不自动重复收费。转换使用外部 zhconvert 服务，不等同于语义翻译或人工语言认证，也不会自动覆盖项目译文。

模型审阅、术语覆盖、即时模型试验与基础汉化补丁 API 的代码保留，但默认关闭。必须显式启用各自实验开关才能使用；默认请求拒绝、OpenAPI与能力发现不推荐，普通工作流不会自动调用。它们的试验结果不构成普通用户功能验收。

## 工程质量与可靠性

- 持久任务更新以SQLite ledger为准，防止旧诊断恢复pending状态、终态释放其他任务的锁；未启动任务回滚、检查点I/O失败与退出路径增加回归。
- 异步数据库引擎按事件循环隔离，避免同步worker新loop与主API loop共享初始化状态；shutdown释放引擎。
- 原生结构化输出与推理参数合并后保留schema及合法effort；OpenRouter保持严格schema，其他支持端点仅在明确能力拒绝时允许prompt JSON回退。
- Provider错误只传播安全摘要，保留致命／重试分类；不把上游回显正文写入任务警告、日志或异常链。
- 引号保护改用线性扫描，避免大量未闭合方括号造成耗时放大；嵌套／交叠语义token保持保守保护，新增50万括号输入回归。
- 前端拒绝畸形Archive A/B及增量预扫描payload，保留既有合集生命周期/CAS/路径边界，增加卸载和TaskRunner回归；已有hook拆分不重复计为本版新增。
- Python架构例外继续收紧，未提高既有上限。构建只使用仓库静态词典和已审阅数据库种子，不读取用户运行数据库。

## 兼容性与验证边界

高级 API 不提供新的普通用户操作页面。既有工作区和运行资料保持原样；旧版本任务不因升级被删除。禁用的实验任务需按高级开发指南启用后读取，不会在后台自动重新提交收费请求。

OpenRouter 翻译要求所选模型端点支持严格 JSON Schema；不支持时会明确失败，不再静默退回普通文本。遇到此类错误，请在设置中选择支持结构化返回的模型端点。

静态词典资源版本2026.10.08.1，英／简中1711条、完整三语278条，4条pending排除。JSON与UTF-8-BOM CSV保留概念／语境；导入载荷approved=false，不代表下载即批准导入。

本地测试使用模拟transport，不宣称每个云端账号模型都可访问，也不宣称实际游戏加载或Workshop上传已验收。正式Release仍以GitHub发布为准。

## English

## Highlights

- **More reliable tasks:** cancellation, failed startup and restart recovery stay consistent; tasks that never started release project ownership and failed progress saves are visible.
- **Text integrity:** semantic game tokens, quotes and line breaks remain visible to the model. Structured responses and multiline Surviving Mars CSV handling are improved.
- **Model settings:** the Claude 5.5 lineup supports `claude-opus-5-5`, `claude-sonnet-5-5` and `claude-haiku-5-5`; this release adds Haiku and improves reasoning support for all three. Other added or updated catalog IDs include xAI `grok-4.7`, Qwen `qwen3.8-flash`, DeepSeek `deepseek-flash`, OpenRouter `openai/gpt-6.1-sol`, ModelScope `deepseek-ai/DeepSeek-V4-Pro-0813` and `deepseek-ai/DeepSeek-V4.1-Flash`, and NVIDIA `deepseek-ai/deepseek-v4.1-flash`. Improved reasoning support for existing GPT-6/GPT-6.1 and Muse Spark models fixes missing selected parameters, conflicting sampling settings and frozen-model mismatches. Existing saved selections remain; users of migrated model IDs should select a supported replacement in Settings.
- **Glossary download:** releases include English/Simplified and English/Simplified/Traditional Surviving Mars glossary attachments with checksums, sources, context and review states.

## Advanced Agent APIs

Native OpenAI/OpenRouter Batch and Chinese script/regional conversion are available through advanced Agent APIs, without new GUI controls. Explicit authorization and durable idempotent submissions remain required. Conversion uses the external zhconvert service and does not automatically overwrite translations.

Model review, terminology coverage, immediate model trials and base-patch experiments are disabled by default. Their APIs require explicit feature opt-in; normal workflows do not discover or invoke them. Experimental output is not human certification.

OpenRouter translation requires an endpoint supporting strict JSON Schema. Unsupported endpoints fail explicitly instead of silently falling back to plain text; select a compatible endpoint in Settings if this occurs.

## Engineering quality and reliability

Task admission rollback, ledger-aware updates, owner-safe terminal transitions, loop-scoped database engines and checkpoint failure handling have focused regressions. Structured schemas and reasoning settings share the final request policy; provider failures retain safe retry classification without exposing upstream bodies. Quote protection scans malformed bracket input in linear time while conservatively preserving nested/overlapping semantic tokens, with a 500,000-bracket regression. Malformed review/prescan payloads are rejected. Release glossaries use reviewed static inputs rather than live user databases.

The integrated backend suite passes 2,843 tests with 19 environmental/optional skips; the frontend passes 1,088 tests. Lint has no errors and 13 existing warnings, the production dependency audit has no vulnerabilities, and the stable Windows installer builds successfully. Frozen-backend smoke checks confirm version 3.3.0 and the default experimental API gates. No real paid calls, game loading or Workshop upload acceptance is claimed by these checks.

## 最终验证与安装包

最终构建源码提交：`cfb927efebd2d9de59e7bcd2411a90dffed3632e`，包含发布前CodeQL发现的引号扫描修复。后续收尾仅修改发布文档，没有修改打包代码或资源。

| 检查 | 结果 |
| --- | --- |
| 完整后端 pytest | 2843通过、19跳过、746警告；206.53秒 |
| 完整前端 Vitest（独立锁定依赖） | 258文件、1088通过；53.88秒 |
| 前端 lint／生产依赖审计 | 0错误、13既有警告／0漏洞 |
| 构建与资源聚焦回归 | 35通过；新增种子导出到freezer调用链回归 |
| Python架构守卫、compileall、diff检查 | 通过；编译缓存与测试数据均隔离到TEMP |
| Stable打包 | PyInstaller、Vite、Tauri NSIS／MSI构建通过；正式附件选用NSIS EXE |
| 冻结后端冒烟 | 隔离AppData、随机localhost端口；health、适配器、Copilot、演示项目及FPK通过 |
| 冻结后端功能边界 | 版本3.3.0；Batch／转换可发现且gui=false；实验接口隐藏并403拒绝 |
| 词典附件 | CRC、内部SHA256、提交后LF哈希与数量一致；1711／278条，approved=false |

19个跳过项：14个需要本机未开放的符号链接权限，另外5个分别需要可选PZ样本、可选上游样本、完整参考档案、lupa及显式启用真实Gemini调用。没有执行真实收费翻译、实际游戏加载、Workshop上传或安装到用户现有数据目录。

前端职责复核：合集主hook保持142行，三个控制器59／50／60行；词典页面478→484行，编辑表单274→280行，新展示组件17／46行。没有新增state/effect；已有API／工作流边界保持分离。聚焦测试覆盖控制器卸载、畸形payload拒绝、TaskRunner及词典metadata展示，未提高冻结文件上限。

附件位于本地候选checkout的`archive/release/stable/`，另存于`J:\Remis-release-preparation\v3.3.0\release-assets\`；完整日志保存在同级`evidence/`。

| 附件 | 字节数 | SHA256 |
| --- | ---: | --- |
| remis-mod-factory_3.3.0_x64-setup.exe | 45722087 | `26c4410663ea78798309a8a6dfcf5498f9addfc2124d9b614bb56809ded2062f` |
| Remis-SurvivingMars-Glossary_3.3.0.zip | 415008 | `5430a7713eccad27aa703b6a1b094e5ecc78e3f88936c57be68fe62440d9ce97` |

发布时附带词典`.zip.sha256`和`SHA256SUMS`。生成本地附件不等于GitHub Release已发布；正式发版应把候选代码通过仓库分支保护和CI门禁合入main，并核对最终Release的精确commit。
