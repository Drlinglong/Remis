# 推理预设与发送链审计（2026-10-09）

GPT-6 的根因是精确模型 ID 未进入内置能力表：即使用户选择 `high`，解析结果仍为不支持且参数为空。本次将官方确认的 GPT-6 模型加入模型目录和推理表，并修复发送链中的参数丢失及不兼容采样字段。

工作树：`J:\V3_Mod_Localization_Factory-worktrees\gpt6-reasoning-presets`；分支：`codex/gpt6-reasoning-presets`；基线：`bbd61637`。主工作区已有修改保留。交付范围为本地代码、测试与审计资料；未推送、部署或执行付费模型调用。

开发前读取现有服务的 `/api/agent/preflight`：ready，官方 Release 检查成功，当前与最新版本均为 v3.2.2。未启动工作树后端或替换现有服务。

## OpenAI 精确参数

| 模型 | 本次注册的合法 effort | 请求字段 | 官方来源 |
| --- | --- | --- | --- |
| `gpt-6-luna` | none / low / medium / high / xhigh / max | Chat: `reasoning_effort`；Responses: `reasoning.effort` | [模型页](https://developers.openai.com/api/docs/models/gpt-6-luna) |
| `gpt-6-sol` | none / low / medium / high / xhigh / max | 同上 | [模型页](https://developers.openai.com/api/docs/models/gpt-6-sol) |
| `gpt-6.1-sol` | low / medium / high / xhigh / max | 同上 | [模型页](https://developers.openai.com/api/docs/models/gpt-6.1-sol) |
| `gpt-6-astra` | low / medium / high / xhigh / max | 同上 | [模型页](https://developers.openai.com/api/docs/models/gpt-6-astra) |

以上 GPT-6 模型均不注册 `minimal`；Astra 和 6.1 Sol 不注册 `none`。模型页列出的省略 effort 默认值为 medium。关闭 Remis 内置预设表示不注入该字段，不能理解为关闭模型自身推理。

按 [OpenAI 部署检查表](https://developers.openai.com/api/docs/guides/deployment-checklist)，有效 effort 不是 `none` 时移除 `temperature`、`top_p`、`top_logprobs`，Chat 还移除 `logprobs`。检查在自定义 JSON 合并之后进行，覆盖顶层及 `extra_body`。规划 Agent 和 OpenAI 小助手原本就使用 Responses，保留该接口；GPT-6 的工具推理应使用 Responses。

已配置的 GPT-5.6 Sol/Terra/Luna 保留原来的五档正向推理映射，并接入采样兼容规则。其官方模型页也支持 `none`，本次未扩展原生 GPT-5.6 的该档位。OpenRouter 的 GPT-5.6 Luna 则按该网关的实际元数据注册 `none`。

## 全部配置 Provider 的审计结论

检查范围为配置文件中的 20 个 Provider：14 个云端 Provider，以及五个本地运行时和一个自定义入口。参数支持按具体端点和模型 ID 判断。

| Provider / 模型 | 发现与处理 | 证据 |
| --- | --- | --- |
| OpenAI | 补四个 GPT-6 精确 ID；原先 high 解析为空，现能序列化到 Chat/Responses 请求；处理采样冲突 | 上述四个模型页及部署检查表 |
| Anthropic / Opus 5、Sonnet 5、Opus 4.6 | 补前两者 xhigh/max、后者 max；Opus 4.6 不注册 xhigh；原生小助手接入 `anthropic_effort`；Opus 5 / Sonnet 5 两条 Messages 调用链移除不兼容采样字段 | [effort](https://platform.claude.com/docs/en/build-with-claude/effort)、[模型弃用与参数限制](https://platform.claude.com/docs/en/docs/about-claude/model-deprecations)、[Sonnet 5 变化](https://platform.claude.com/docs/en/docs/about-claude/models/whats-new-sonnet-5) |
| Gemini / 3.8、3.7、3.6 Flash | 3.7 删除不支持的 minimal；3.8/3.7 仅 low/medium/high，3.6 保留 minimal；多轮调用从冻结配置读取模型，避免发到全局默认模型；原生小助手接入 `google_thinking_config` | [thinking](https://ai.google.dev/gemini-api/docs/thinking) |
| Grok / 4.6 | 原先 null；注册 `reasoning_effort` low/medium/high/xhigh | [推理指南](https://docs.x.ai/developers/model-capabilities/text/reasoning)、[模型页](https://docs.x.ai/developers/models/grok-4.6) |
| Kimi / K3 | 原先 null；注册 `reasoning_effort` low/high/max；移除固定采样字段 temperature/top_p/n/presence_penalty/frequency_penalty | [K3 快速开始](https://platform.kimi.ai/docs/guide/kimi-k3-quickstart) |
| Kimi / K2.7 Code | 文档说明思考始终开启，未确认可调 effort；保留 null，不把模型会思考等同于支持预设 | [K2.7 Code](https://platform.kimi.ai/docs/guide/kimi-k2-7-code-quickstart) |
| Meta / Muse Spark 1.2、1.3 | 原先 null；1.2 注册 minimal/low/medium/high/xhigh，1.3 再加 max；参数为 `reasoning_effort` | [推理指南](https://dev.meta.ai/docs/reasoning)、[模型目录](https://dev.meta.ai/docs/models) |
| Qwen / 3.8 Max | 已有 `enable_thinking: true` 二态预设可到达请求；官方例子支持非流式，保留 high 作为开关标签 | [深度思考](https://help.aliyun.com/en/model-studio/deep-thinking) |
| Qwen / 3.8 Flash Next | 未找到此精确 ID 的官方端点参数证据；保留 null；不能用新 Flash ID 的说明替代 | [当前 Flash 文档](https://help.aliyun.com/en/model-studio/qwen3-8-flash) |
| DeepSeek 原生 / V4 Flash、Pro | 现有 thinking 与 effort 的 JSON 放置没有丢失；旧 ID 映射保留。当前指南改以 deepseek-flash/pro 为例，并有新的 low/high/max 规则；旧 V4 ID 的别名/退役与 effort 合同需要单独复核，不能据新 ID 宣称已认证旧 ID | [当前推理指南](https://api-docs.deepseek.com/guides/thinking_mode/) |
| OpenRouter | 精确公开目录证明九个已配置/新增路由支持 reasoning；注册网关 `reasoning.effort`，补四个 GPT-6 ID；五个 OpenAI 路由不声明采样支持，发送时移除采样字段；qwen/qwen3.8-max 未在目录找到，保留 null | [网关推理指南](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)、[公开模型元数据](https://openrouter.ai/api/v1/models) |
| SiliconFlow / DeepSeek V4 Flash | 原先 null；精确 ID 支持 `enable_thinking: true` 与 `reasoning_effort` high/max，已注册；已配置的 Pro ID 与文档支持 ID 不同，继续保持 null | [Chat API](https://docs.siliconflow.cn/docs/api/chat-completions-post) |
| NVIDIA / DeepSeek V4 Flash、Pro | 原先 null；两份 hosted infer 参考都明确对应 integrate.api.nvidia.com/v1/chat/completions，注册 none/high/max；此为参数合同证据，本次未验证账号模型访问权限 | [Flash infer](https://docs.api.nvidia.com/nim/reference/deepseek-ai-deepseek-v4-flash-infer)、[Pro infer](https://docs.api.nvidia.com/nim/reference/deepseek-ai-deepseek-v4-pro-infer) |
| NVIDIA / MiniMax M3 | 精确 infer 页没有确认可调 effort；保留 null | [M3 infer](https://docs.api.nvidia.com/nim/reference/minimaxai-minimax-m3-infer) |
| MiniMax / M3、M2.7、M2.7-highspeed | M3 有 adaptive/disabled 思考模式，M2.x 始终思考；当前文档将可调 reasoning_effort 指向更晚的 M3.1 Flash Preview，不能外推给已配置 ID；保留 null | [OpenAI 兼容接口](https://platform.minimax.io/docs/api-reference/text-openai-api) |
| Zhipu / GLM 5.3 Flash | 已有 max 与 thinking enabled 序列化正确；官方推荐 max，thinking 不能关闭；本次保留此单档合同 | [模型参数](https://docs.z.ai/guides/vlm/glm-5.3-flash) |
| ModelScope / DeepSeek V4 Flash、Pro | 未获得 hosted 推理端点针对精确 ID 的参数合同；模型权重说明不足以证明 API 接受 effort，保留两个 null | 端点级支持未确认 |
| Ollama、LM Studio、vLLM、KoboldCpp、Oobabooga、自定义入口 | 模型/端点由用户指定；不推断内置能力，自定义 JSON 沿用原有验证和合并规则 | 本地运行时与自定义端点没有统一模型合同 |

OpenRouter 证据保存为 [过滤后的公开目录快照](reasoning-openrouter-catalog-2026-10-09.json)，仅含相关模型的 ID、reasoning 元数据和支持字段，没有账号信息或密钥。`null` 表示当前未登记经过核验的可调预设，不表示模型不具备推理能力。

## 代码边界

- `data/config/api_providers.json` 记录合法档位、参数映射、官方来源和核对日期；所有既有默认模型、默认档位和默认开关均保留。
- 新的 `scripts/core/chat_request_policy.py` 只处理经核验的请求字段兼容约束；OpenAI/Anthropic handler 与 PydanticAI 模型设置共用它。
- `scripts/core/copilot/settings.py` 负责将同一预设解析结果转为 OpenAI、Anthropic、Google 的原生模型设置；小助手工厂不再跳过后两者。
- `scripts/core/gemini_handler.py` 修复冻结请求的模型一致性；Copilot 更新 schema 允许 `none`。
- 未修改 React 生产代码，没有新增前端 state/effect。参数策略与 handler 传输、Agent 组装保持分离，未向 BaseApiHandler 热点添加责任或提高架构基线。

生产模块行数（基线 → 当前）：请求策略 0 → 60；OpenAI handler 95 → 100；Anthropic handler 111 → 113；Gemini handler 113 → 112；Copilot settings 184 → 193；小助手模型工厂 131 → 129；规划 Agent 149 → 152。所有受影响模块均低于需要责任复审的 500 行门槛，Python 架构检查通过。

现有最大输出预算保留；注册 high/max 不表示原有 token 上限一定足够，也不构成质量、延迟或费用的实测结论。未知 ID 的参数支持和模型目录迁移仍按上表单独标记。

## 验证

使用开发启动脚本选定的解释器 `K:\MiniConda\envs\local_factory\python.exe`，未安装依赖。所有生成接口测试均采用虚拟测试密钥和 MockTransport/Mock，没有真实生成请求。OpenRouter 仅读取无需鉴权的公开目录。

```powershell
& K:/MiniConda/envs/local_factory/python.exe -m pytest -q tests/test_reasoning_request_contracts.py tests/test_copilot_reasoning_transport.py tests/test_anthropic_handler.py tests/test_copilot_settings.py tests/test_copilot_phase1.py tests/test_copilot_workflow.py tests/test_reasoning_policy.py tests/test_api_provider_routing.py tests/test_gemini_handler.py tests/test_custom_provider_runtime_snapshot.py tests/test_app_settings_static_config.py tests/test_routers_config.py tests/test_agent_api.py
& K:/MiniConda/envs/local_factory/python.exe scripts/developer_tools/check_python_architecture.py
& K:/MiniConda/envs/local_factory/python.exe -m compileall -q scripts tests
git diff --check
```

传输测试遍历所有已登记 Chat 预设，检查真实 OpenAI SDK 序列化 JSON；另覆盖 Anthropic 两条调用链、Gemini 冻结模型、内置开关与自定义覆盖、采样冲突、Copilot none 保存、规划 Agent 构建，以及小助手经 PydanticAI 和真实 SDK 发送的 OpenAI Responses、OpenRouter、Claude Opus/Sonnet、Gemini 请求。

最终相关套件共 400 项：399 通过、1 项下述基线失败（12.20 秒）。Python 架构检查、compileall、JSON 解析、模型目录/能力表一致性、既有默认值保持、UTF-8 完整性扫描及 `git diff --check` 均通过。本次无 locale 或前端改动，未运行前端构建和 locale 专项测试。

已知基线失败：`test_every_packaged_user_guide_is_agent_selectable`，帮助清单漏登记 `zh/user-guides/surviving-mars-mod-editor-upload-preflight.md`。本次未改动清单、该测试或用户指南；通过读取 `git show HEAD:scripts/core/copilot/help_pack.py` 并执行其未修改实现，复现同一缺项。该失败不能归因于推理修改，也不计为通过。
