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
