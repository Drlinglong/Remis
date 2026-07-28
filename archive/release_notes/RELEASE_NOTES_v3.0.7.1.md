# Project Remis v3.0.7.1

Released on 2026-07-28 as an urgent provider-routing hotfix for v3.0.7.

The public Git tag and GitHub Release are `v3.0.7.1`. Package manifests use
the valid SemVer equivalent `3.0.7+1` because npm, Cargo, and Tauri require
three numeric version components, and Windows MSI requires numeric build
metadata.

## English

### Fixed

- Restored Kimi, MiniMax, and Zhipu through their declared OpenAI-compatible
  endpoints and provider-specific API key environment variables.
- Added a native Anthropic Messages API adapter instead of accidentally sending
  Anthropic requests through Gemini.
- Corrected Anthropic's Claude 4.5 model identifiers.
- Replaced stale or cross-vendor Kimi and MiniMax model choices with their
  current official model identifiers.
- Removed the unsafe unknown-provider fallback to Gemini. Unsupported provider
  identifiers now fail explicitly instead of silently using another vendor.
- Made the shared OpenAI-compatible handler read each provider's declared
  `api_key_env`, fixing MiniMax requests that previously looked only for
  `OPENAI_API_KEY`.

### Regression protection

- Added a configuration-to-handler contract test covering every configured
  provider.
- Added a model-catalog contract requiring every configured default model to
  appear in that provider's selectable catalog.
- Added a turnkey cloud-provider matrix for Gemini, Anthropic, OpenAI, Qwen,
  Grok, DeepSeek, ModelScope, SiliconFlow, Kimi, MiniMax, Zhipu, and NVIDIA.
- Added provider-specific credential and base URL tests for all
  OpenAI-compatible routes.
- Added Anthropic request-shape, authentication, response parsing, and failure
  tests.
- Added release-metadata synchronization tests.

No paid model calls were made during hotfix validation. The provider tests use
mocked network clients and verify routing, credentials, endpoints, and request
contracts without sending prompts or API keys externally.

### Validation

- Provider and release contract suite: 32 tests passed.
- Backend suite: 475 tests passed and 2 were skipped; the one AppData SQLite
  case blocked by the restricted test sandbox passed when rerun with its normal
  filesystem access.
- Python compilation, fatal-error lint checks, and diff integrity passed.
- Desktop frontend: 158 tests passed; lint and production build passed.
- Rust/Tauri: formatting, locked dependency checks, release compilation, MSI
  packaging, and NSIS packaging passed.
- The frozen backend returned a real healthy response on an isolated localhost
  port before desktop packaging.
- Windows installer:
  `remis-mod-factory_3.0.7.1_x64-setup.exe` (41,913,399 bytes / 39.97 MiB).
- SHA-256:
  `BE0FA41E5C91014FFADFBD74A8B4ADCC09A1043B1FEB81FA2AA39AF81FD928B1`.
- A current production dependency audit reports two high-severity React Router
  findings. npm's available remediation is a forced route-stack version change,
  so it is not mixed into this narrowly scoped provider hotfix.

## 中文

### 修复

- 恢复 Kimi、MiniMax 和智谱的 OpenAI 兼容路由，并读取各自声明的 API
  密钥环境变量。
- 新增原生 Anthropic Messages API 适配器，不再把 Anthropic 请求意外发送
  给 Gemini。
- 更正 Anthropic Claude 4.5 模型标识符。
- 用当前官方模型标识替换 Kimi 与 MiniMax 中过时或跨供应商的模型选项。
- 删除未知供应商静默回退 Gemini 的行为。未支持的 provider 现在会明确
  报错，不会暗中改用另一家供应商。
- 通用 OpenAI 兼容处理器现在读取每家供应商声明的 `api_key_env`，修复
  MiniMax 之前只查找 `OPENAI_API_KEY` 的问题。

### 回归保护

- 新增配置到处理器的一致性测试，覆盖所有已配置供应商。
- 新增模型目录合同，要求每家供应商的默认模型必须出现在自己的可选目录中。
- 新增即用型云供应商矩阵，覆盖 Gemini、Anthropic、OpenAI、Qwen、
  Grok、DeepSeek、ModelScope、SiliconFlow、Kimi、MiniMax、智谱和 NVIDIA。
- 新增全部 OpenAI 兼容路由的供应商专属凭据与基础 URL 测试。
- 新增 Anthropic 请求结构、认证、响应解析和失败路径测试。
- 新增发布版本元数据同步测试。

本次热修验证没有发起任何付费模型调用。供应商测试全部使用模拟网络
客户端，在不向外发送提示词或 API 密钥的前提下验证路由、凭据、端点和
请求合同。

### 验证

- 供应商与发布合同测试：32 项通过。
- 后端全量：475 项通过，2 项跳过；受受限测试沙箱阻止的唯一 AppData
  SQLite 用例，在恢复正常文件系统权限后单独复跑通过。
- Python 编译、致命错误 lint 和差异完整性检查通过。
- 桌面前端：158 项测试通过；lint 与生产构建通过。
- Rust/Tauri：格式检查、锁定依赖检查、release 编译、MSI 与 NSIS
  打包通过。
- 冻结后端在桌面打包前于隔离的 localhost 端口返回真实健康响应。
- Windows 安装包：
  `remis-mod-factory_3.0.7.1_x64-setup.exe`（41,913,399 字节 / 39.97 MiB）。
- SHA-256：
  `BE0FA41E5C91014FFADFBD74A8B4ADCC09A1043B1FEB81FA2AA39AF81FD928B1`。
- 当前生产依赖审计报告 2 项 React Router 高危问题；npm 提供的修复需要
  强制更换路由栈版本，因此没有混入这次范围严格受限的供应商热修。
