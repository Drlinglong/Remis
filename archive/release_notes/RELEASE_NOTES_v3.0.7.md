# Project Remis v3.0.7

## English

## Highlights

- **Remis Copilot is now available as an in-app help chat.** Ask how to start a localization project, configure a model provider, proofread translations, deploy a Mod, diagnose errors, or use other Remis features without leaving the application.
- **Answers are grounded in the help documents shipped with Remis.** The model decides which relevant help skills to open for each conversation instead of relying on keyword matching or loading every document at once.
- **Local-first operation.** LM Studio can use its native Responses API function-calling protocol to select help material. Other configured providers retain a compatibility path.
- **The Neologism Tribunal is ready for real project workflows.** Mining now produces source-grounded candidates through a bounded, validated LLM workflow, then carries them into a project-aware review and glossary approval flow.

This release completes the conversational help foundation. Copilot can explain and navigate, but it does not yet execute localization workflows. Plan approval and workflow orchestration are the next development stage.

## User Experience

- Added a dedicated Remis Copilot chat page and a compact floating assistant entry.
- Added persistent local chat sessions and safe navigation suggestions to relevant Remis pages.
- Added user guides for Project Tracking, Neologism Tribunal, Settings, and the Mod thumbnail generator.
- Added honest capability boundaries: the assistant does not claim to edit Mod files, change the Remis client, or perform write operations that have not happened.
- Added source and confidence metadata so unsupported questions do not silently turn into invented product instructions.

## Neologism Tribunal

- Mining now uses the selected project, provider, and model, including LM Studio's `local-model` alias.
- The file picker and progress display use the backend's exact eligible source-file set, excluding project metadata, checkpoints, caches, and generated files.
- Live status is delivered through WebSocket with reconnection and task snapshot recovery. Completed runs open the Tribunal automatically; failed runs return the page to a retryable state.
- Review decisions distinguish project approval, known duplicates, and separate meanings. Approved project terminology takes precedence over selected game glossaries and the global glossary.
- Candidate storage is project-scoped and atomic, with one active mining run per project and idempotent approval handling.

## Technical Details

- Replaced keyword-based document routing with an allowlisted, model-controlled `read_help_skill` selection stage.
- Added native `/v1/responses` function calling for LM Studio, including required tool selection, a no-match tool, low-temperature routing, output limits, and validation that the provider returned a real `function_call`.
- Kept the JSON selection protocol only as a compatibility path for providers without native function calling.
- Split provider documentation into focused skills so an Ollama question does not load unrelated provider guides.
- Added manifest coverage checks for every packaged Chinese user guide.
- Added routing mode, selected skills, loaded source count, routing time, and answer time to Copilot context diagnostics.
- Bundled `docs/zh/user-guides` in both release and debug builds.
- Rebuilt neologism mining as a bounded extraction-and-review workflow with strict structured-output validation and one contextual repair attempt.
- Added source-evidence aggregation, safe path validation, provider/model forwarding, duplicate indexing, project-level concurrency protection, and deterministic candidate limits.
- Enabled WebSocket proxying in the frontend development server and added regression coverage for terminal failure recovery, localized model labels, and stable completion callbacks.

## Current Limitations And Next Step

- Copilot suggestions are limited to safe UI navigation in this phase.
- It cannot yet propose an executable multi-step localization plan and wait for the user to approve it.
- The next phase will introduce workflow planning, an explicit **Approve and Execute** gate, progress reporting, and controlled Remis operations.

## Validation

- `python -m pytest tests/test_copilot_phase1.py -q` (18 tests)
- Live LM Studio native tool-selection smoke test with `google/gemma-4-31b-qat`: returned a real `read_help_skill(ollama_setup)` function call in 6.62 seconds.
- Neologism backend regression suite: 29 tests passed; frontend suite: 130 tests passed.
- Live Stellaris fixture evaluation through LM Studio `local-model`: 100% golden-term recall and 100% source-evidence grounding.
- Full UI smoke test completed 3/3 eligible source files, reached a terminal completed state over WebSocket, and opened the Tribunal with the expected golden terms visible.
- `git diff --check`

## 中文

## 重点

- **Remis 小助手现已提供应用内聊天帮助。** 无需离开 Remis，就可以询问如何开始汉化项目、配置模型供应商、校对译文、部署 Mod、诊断错误，以及使用其他 Remis 功能。
- **回答基于安装包随附的帮助文档。** 模型会结合对话自行决定打开哪些帮助技能，不再依赖关键词匹配，也不会每次把全部文档一起塞进上下文。
- **本地优先。** 使用 LM Studio 时，小助手可以通过原生 Responses API 工具调用选择帮助资料；其他已配置供应商继续保留兼容路径。
- **新词审判庭现已能够用于真实项目工作流。** 新词挖掘改为有界、可校验且保留原文证据的 LLM 工作流，并与项目级审判和术语审批流程完整衔接。

本次版本完成了聊天问答帮助机器人的基础能力。小助手目前可以解释功能并引导用户前往相关页面，但还不会直接执行汉化工作流。“提出计划—用户批准—受控执行”的工作流编排是下一阶段。

## 用户体验

- 新增独立的 Remis 小助手聊天页面和紧凑的悬浮入口。
- 新增保存在本地的聊天会话，以及前往 Remis 相关页面的安全导航建议。
- 新增项目追踪、新词审判庭、设置和 Mod 封面图生成器用户指南。
- 明确能力边界：小助手不会声称已经修改 Mod 文件、改动 Remis 客户端，或执行实际上没有发生的写操作。
- 新增来源与可信度信息；文档没有覆盖的问题不会被静默包装成虚构的产品说明。

## 新词审判庭

- 新词挖掘会使用当前选择的项目、供应商和模型，包括 LM Studio 的 `local-model` 别名。
- 文件列表与进度统一采用后端确认的可挖掘源文件集合，排除项目元数据、检查点、缓存和生成文件。
- 任务状态通过 WebSocket 实时推送，并支持断线重连和任务快照恢复。完成后自动进入审判庭，失败后恢复为可重试状态。
- 审判操作明确区分“批准到项目术语库”“已有重复项”和“同词新义”。项目术语优先于已选游戏术语库与全局术语库。
- 候选数据按项目隔离并原子写入；同一项目仅允许一个挖掘任务运行，重复审批不会重复写入术语。

## 技术细节

- 用白名单约束、由模型自主控制的 `read_help_skill` 选材阶段替代关键词文档路由。
- 为 LM Studio 接入原生 `/v1/responses` function calling，包括强制工具选择、无匹配工具、低温路由、输出上限，以及真实 `function_call` 返回校验。
- 仅对不支持原生工具调用的供应商保留 JSON 兼容选材协议。
- 将 Provider 文档拆成更精确的帮助技能；询问 Ollama 时不会再加载无关供应商指南。
- 为安装包中的全部中文用户指南增加 manifest 覆盖校验。
- 在 Copilot 上下文诊断中增加路由模式、已选技能、已加载来源数量、路由耗时与回答耗时。
- release 与 debug 构建都会打包 `docs/zh/user-guides`。
- 将新词挖掘重构为有界的“提取—复核”工作流，加入严格结构化输出校验和一次携带上下文的修复重试。
- 新增原文证据聚合、安全路径校验、供应商与模型转发、重复术语索引、项目级并发保护和确定性候选上限。
- 为前端开发服务器启用 WebSocket 代理，并补充失败终态恢复、本地化模型标签和稳定完成回调的回归测试。

## 当前边界与下一步

- 当前阶段的小助手 action 仅限安全的界面导航。
- 它还不能生成可执行的多步骤汉化计划并等待用户批准。
- 下一阶段将加入工作流规划、明确的 **批准并执行** 门槛、进度反馈，以及受控的 Remis 操作调用。

## 已验证

- `python -m pytest tests/test_copilot_phase1.py -q`（18 项测试）
- 使用 `google/gemma-4-31b-qat` 完成 LM Studio 原生工具选择冒烟：6.62 秒返回真实的 `read_help_skill(ollama_setup)` function call。
- 新词审判庭后端回归测试 29 项通过，前端测试 130 项通过。
- 使用 LM Studio `local-model` 完成 Stellaris 固定样本评估：黄金术语召回率 100%，原文证据落地率 100%。
- 完整 UI 冒烟成功处理 3/3 个有效源文件，通过 WebSocket 到达完成终态，并自动进入审判庭显示预期黄金术语。
- `git diff --check`
