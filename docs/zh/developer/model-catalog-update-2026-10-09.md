# 模型目录及推理参数更新（2026-10-09）

按用户明确指定的模型进行更新，沿用工作树 `J:\V3_Mod_Localization_Factory-worktrees\gpt6-reasoning-presets`、分支 `codex/gpt6-reasoning-presets`，修改基于本地提交 `bd821505`。交付范围为本地代码、测试与审计资料；未推送或部署，没有付费推理请求，也没有读取 Provider 密钥。

## 目录与默认值

| Provider | 本次变更 | 默认模型 |
| --- | --- | --- |
| Anthropic | 添加 `claude-opus-5-5`、`claude-haiku-5-5`、`claude-sonnet-5-5`，保留既有三款模型 | 保留 `claude-sonnet-5` |
| Grok | 添加 `grok-4.7`，保留 `grok-4.6` | 保留 `grok-4.6` |
| Qwen | `qwen3.8-flash-next` 替换为 `qwen3.8-flash` | 保留 `qwen3.8-max` |
| DeepSeek | `deepseek-v4-flash` 替换为 `deepseek-flash`；保留 `deepseek-v4-pro` | 改为 `deepseek-flash` |
| ModelScope | Flash 改为 `deepseek-ai/DeepSeek-V4.1-Flash`，Pro 改为 `deepseek-ai/DeepSeek-V4-Pro-0813` | 改为新 Flash ID |
| NVIDIA NIM | 删除旧 Flash/Pro/MiniMax 三个目录项，改为 `deepseek-ai/deepseek-v4.1-flash` | 改为新 Flash ID |

所有 Provider 的 `available_models` 与 `reasoning.models` 保持一一对应。既有推理开关、默认档位和 API 地址保持不变；未写入用户持久化设置或改动已冻结的运行任务。已保存的模型选择优先于内置默认值，升级后的旧选择应在 Remis 设置中改选新 ID。

## 推理合同与迁移依据

Claude 5.5 三款均注册 `low/medium/high/xhigh/max`，请求字段为 `output_config.effort`。Opus/Haiku 的 API 省略 effort 默认值为 medium，Sonnet 为 high；Remis 启用内置预设时仍发送用户选择的档位。思考开启行为由 API 模型默认值决定，关闭 Remis 预设不代表关闭思考。[官方 effort 文档](https://platform.claude.com/docs/en/build-with-claude/effort)

三款均接入已有采样兼容策略，移除 `temperature/top_p/top_k`，同时覆盖直接 Messages handler、自定义参数合并和 PydanticAI 小助手；不会注册 `thinking: disabled`。保留 Opus 4.6 的采样控制。[Opus 5.5 迁移](https://platform.claude.com/docs/en/models/opus-5-5/migration-guide)、[Haiku 5.5 迁移](https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide)、[Sonnet 5.5 迁移](https://platform.claude.com/docs/en/models/sonnet-5-5/migration-guide)

Grok 4.7 注册 `reasoning_effort` 的 low/medium/high/xhigh，沿用 Chat 兼容请求路径；不注册 none/max。官方模型页和推理文档分别确认精确 ID 与档位；Responses 使用 `reasoning.effort`。[模型页](https://docs.x.ai/developers/models/grok-4.7)、[推理参数](https://docs.x.ai/developers/model-capabilities/text/reasoning)

Qwen 官方明确托管调用 ID 为 `qwen3.8-flash`，深度思考指南将其列为 hybrid thinking 模型。注册与 Max 同类的 `high → enable_thinking: true` 单档开关，不虚构可调 reasoning_effort。[托管 ID](https://help.aliyun.com/en/model-studio/qwen3-8-flash)、[思考开关](https://help.aliyun.com/en/model-studio/deep-thinking)

DeepSeek 2026-09-10 日志确认旧 Flash ID 是临时路由，正式 ID 为 `deepseek-flash`；同页确认 V4 Pro 继续提供 API。Flash 更新为当前合同：minimal/low → low，medium/high/xhigh → high，max → max，均带 `thinking.type: enabled`。V4 Pro 的既有映射保留，没有用新 Flash 参数覆盖它。DeepSeek handler 的兜底 ID 也同步更新。[更新日志](https://api-docs.deepseek.com/updates/)、[当前思考参数](https://api-docs.deepseek.com/guides/thinking_mode/)

ModelScope 在本次公开 `GET /v1/models` 中返回 35 个模型，两个新 ID 均实际存在。模型详情页元数据的 `SupportApiInference` 为 false，与推理目录不一致，因此以当前推理端点目录作为 ID 的直接证据。目录没有列出可调 effort 合同，两个 reasoning 项继续为 null，保留自定义 JSON 能力；未执行生成验收。[推理目录](https://api-inference.modelscope.cn/v1/models)、[本地过滤证据](modelscope-catalog-2026-10-09.json)

NVIDIA 的 hosted infer 参考明确给出 `https://integrate.api.nvidia.com/v1/chat/completions` 和精确默认 ID `deepseek-ai/deepseek-v4.1-flash`。公开目录本次返回 80 个 ID，新 ID 存在，三个旧 ID 均缺席。infer 页未列 `reasoning_effort`，新 ID 不能继承旧 V4 的 none/high/max 字符串合同；设为 null，待取得该端点的具体参数证据再注册。模型卡的推理能力不等同于 hosted API 接受某个字段或取值。[Hosted infer](https://docs.api.nvidia.com/nim/reference/nvidia-deepseek-v4_1-flash-infer)、[过滤目录证据](nvidia-catalog-2026-10-09.json)

本次只读取公开目录与官方文档，没有鉴权推理、质量评测或账号权限验收。NVIDIA 未鉴权目录探测的结果记录在验证结论中。

## 验证与维护边界

使用 `K:\MiniConda\envs\local_factory\python.exe`，新增模型所有内置预设经离线 SDK 请求测试；Claude 5.5 三款额外通过 PydanticAI 小助手发送链验证。迁移后的 ModelScope/NVIDIA 请求测试检查精确 ID，并确认不继承旧模型参数；DeepSeek Flash 和保留 Pro 分开断言。

受影响生产模块：`chat_request_policy.py` 从 60 到 64 行，`deepseek_handler.py` 行数不变。请求约束仍独立于传输实现。没有新前端状态或 effect，没有提高任何架构基线，也没有改动 API 密钥处理。

```powershell
& K:/MiniConda/envs/local_factory/python.exe -m pytest -q tests/test_reasoning_request_contracts.py tests/test_copilot_reasoning_transport.py tests/test_anthropic_handler.py tests/test_copilot_settings.py tests/test_copilot_phase1.py tests/test_copilot_workflow.py tests/test_reasoning_policy.py tests/test_api_provider_routing.py tests/test_gemini_handler.py tests/test_custom_provider_runtime_snapshot.py tests/test_app_settings_static_config.py tests/test_routers_config.py tests/test_agent_api.py
& K:/MiniConda/envs/local_factory/python.exe scripts/developer_tools/check_python_architecture.py
& K:/MiniConda/envs/local_factory/python.exe -m compileall -q scripts tests
git diff --check
```

本次 preflight 官方 Release 检查成功；当前运行服务返回版本 3.2.1、`attention_required`，最新官方版本为 [v3.2.2](https://github.com/Drlinglong/Remis/releases/tag/v3.2.2)。已向用户报告；没有升级或重启服务。初次报告中的 preflight 记录为当时观察，不替代本次状态。

最终相关套件共 427 项：426 通过、1 项既有帮助清单失败（11.17 秒）。失败仍为 `test_every_packaged_user_guide_is_agent_selectable` 漏登记 `zh/user-guides/surviving-mars-mod-editor-upload-preflight.md`，与初次修复相同。本次没有修改帮助清单。Python 架构检查、compileall、JSON 解析、目录/推理表一致性、指定默认值迁移和 UTF-8 完整性检查均通过；`git diff --check` 通过。
