# 高级 Agent API 与实验功能边界

原生 OpenAI/OpenRouter Batch 和简繁／地域用词转换在高级 Agent API 可用，
没有新增 GUI。普通翻译流程保持原入口，不自动切换至这些工作流。
提交 Batch 前需要明确付费授权；转换发送文本前需要授权；两者均不自动重试或应用结果。

以下未成熟 API 默认关闭，不出现在普通安装的 OpenAPI 中；capabilities 返回
`supported: false`，直接请求返回 `403 experimental_feature_disabled`。
模型审阅代码保留不表示该功能向普通用户开放。

| 实验范围 | 显式开发者开关 |
| --- | --- |
| 模型审阅 | `REMIS_ENABLE_LOCALIZATION_REVIEWS=1` |
| 术语覆盖 | `REMIS_ENABLE_TERMINOLOGY_COVERAGE=1` |
| 火星本体补丁 | `REMIS_ENABLE_MARS_BASE_PATCH=1` |
| 即时翻译试验 | `REMIS_ENABLE_TRANSLATION_TRIALS=1` |

只有用户明确要求开发实验时才说明相关开关；Agent 不应自行设置它们。
开发者在启动 Remis 前设置相应环境变量并重启，随后重新读取
`/api/agent/preflight` 和 `/api/agent/capabilities` 确认启用。
显式启用不代替付费、文本外发、导出或覆盖的操作授权。
即时模式也不能借 `/batch-jobs/plan` 或历史 Batch plan 绕过开关。
实验接口不承诺成熟度或质量认证，不新增面向普通用户的审阅入口。

词典人工决定展示仍复用现有编辑界面；模型复核与人工确认是分开的数据，
没有新增收费模型审阅按钮。发布词典附件来自静态仓库资源，打包不读取用户数据库。
