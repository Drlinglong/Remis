# OpenRouter 结构化翻译要求

2026-10-09 起，OpenRouter 批量翻译和批量修复必须显式请求 JSON Schema，
不能只依赖提示词中的“返回 JSON”。响应为 `{"translations":["译文"]}`，
数组必须与输入条数一致、元素必须为字符串、对象不允许额外字段。

`BaseApiHandler._call_batch_api` 为批次提供独立的输出契约入口；其他供应商
继续使用各自适配器。OpenRouter 覆盖该入口，请求 `strict=true`、
`require_parameters=true`、`allow_fallbacks=false`，保留已有推理设置及路由限制。
已有 `generate_structured_with_messages` 同样禁止供应商自动回退。

批量翻译先用原生 JSON 和条数校验，再进入既有的占位符还原流程；不依靠
JSON 修复把违反契约的输出算作成功。批量翻译不启用 response-healing。
不兼容端点应返回错误，禁止删掉 schema 后改成纯文本重发。

这不取代翻译内容的硬校验和人工复核，也不改变自由文本交互接口的返回类型。
单条自由文本接口与 Model Arena 的历史执行配方不属于本次批次契约改动。

Aventine 新评测必须把该输出契约作为新版本记录；不能覆盖历史 prompt-only
成绩，也不能把旧版的代码块格式问题解读为严格结构化输出能力的失败。

参考：https://openrouter.ai/docs/guides/features/structured-outputs

## 其他供应商的批次输出契约（2026-10-09）

同一 `translation_output_contract` 现在也覆盖以下供应商；各适配器实现
`_call_schema_batch_api`，由 `call_batch_with_contract` 统一调度并做本地信封校验：

| 供应商 | 原生请求方式 | 模式 |
| --- | --- | --- |
| OpenRouter | `response_format` json_schema，`strict=true`，禁止回退 | `strict_json_schema` |
| OpenAI | `response_format` json_schema，`strict=true` | `json_schema_with_capability_fallback` |
| Gemini | `response_mime_type=application/json` + `response_json_schema` | 同上 |
| Anthropic | `output_config.format`（json_schema；数组条数在本地校验） | 同上 |
| LM Studio / vLLM | `response_format` json_schema | 同上 |
| Ollama（原生） | `format` 字段传入 JSON Schema | 同上 |

能力表见 `scripts/core/provider_structured_output.py`。只有当请求本身因输出格式字段被拒
（400/404/415/422/501 且错误信息提到 schema/format，或 SDK 不支持该字段）时，该 handler
才会放弃 schema 并改用提示词 JSON 重发一次，之后在本实例内保持提示词模式。契约违例、
限流、超时和 5xx 绝不触发降级；OpenRouter 仍然不降级。其余供应商（DeepSeek、Grok、
Qwen、Kimi、KoboldCpp 等）继续使用提示词 JSON 加本地校验。

## 停用 `[[_QT_]]` / `[[_NL_]]` 输入遮罩

- 输入不再遮罩引号和换行。批次原文以 JSON 字符串字面量呈现（只做序列化，不做替换），
  提示词附带 `SOURCE VALUE ENCODING` 说明。永久禁止用占位符替换语义 Paradox 记号。
- 输出统一经过 `normalize_model_output`：真实换行转为字面 `\n`；仅当直引号能无歧义
  成对时才按 `QUOTE_STYLES` 套用目标语言引号，否则保持原样。
- `restore_legacy_mask_tokens` 仍兼容历史输出中的规范与畸形遮罩片段（如 `[ [_QT_]]`、
  `[_QT_]]`）。当存档的原始模型输出（检查点、Model Arena 历史、基准重放）中扫描
  `_QT_` / `_NL_` 结果为零时，即可删除该兼容层。
- 新增仅供人工复核、不阻断、不进入修复队列的机械检查：`validation_unpaired_quotes`
  与 `validation_line_break_count_mismatch`。
- 用户自定义的提示词覆盖若仍提到旧记号，不影响运行，但建议删除该句。
