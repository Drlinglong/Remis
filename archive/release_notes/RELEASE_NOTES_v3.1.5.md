# Project Remis v3.1.5

Released on 2026-08-18.

Version 3.1.5 is a maintenance update for current cloud model catalogs,
translation archive safety, and game-specific format repair.

## English

### Highlights

- Cloud provider catalogs now use current model IDs, including Gemini 3.7
  Flash, Claude 5, GPT-5.6, Qwen 3.8, Grok 4.6, DeepSeek V4, Kimi K3,
  MiniMax M3, and GLM 5.3. Aggregator catalogs use platform-verified slugs.
- Translation archive upload now scans every eligible source file before it
  creates or updates archive records. Invalid or unreadable sources return a
  structured error without creating a partial source version.
- Format repair now applies Victoria 3, Crusader Kings III, and Hearts of Iron
  IV rules only where their syntax requires them.

### Engineering quality and reliability

- Built-in reasoning presets remain provider- and model-specific. ModelScope,
  SiliconFlow, OpenRouter, and NVIDIA NIM do not inherit speculative reasoning
  syntax from their upstream models.
- User-defined model IDs and advanced JSON parameters remain available for
  OpenAI-compatible providers.
- Regression tests lock cloud catalogs, archive write-before-validation
  behavior, router error contracts, and game-specific repair prompts.

## 中文

### 主要更新

- 云端服务商目录更新为当前模型 ID，包括 Gemini 3.7 Flash、Claude 5、
  GPT-5.6、Qwen 3.8、Grok 4.6、DeepSeek V4、Kimi K3、MiniMax M3 与
  GLM 5.3；聚合平台只使用平台自身已核验的精确 slug。
- 翻译归档上载会在创建或更新归档记录前完成全部源文件扫描。遇到损坏或不可读
  文件时返回结构化错误，不再生成半完成的 source version。
- 格式修复会根据 Victoria 3、Crusader Kings III 与 Hearts of Iron IV 的
  实际语法分别应用规则，避免跨游戏错误套用。

### 工程质量与可靠性

- 内置推理档位继续按“服务商 + 模型”管理；ModelScope、SiliconFlow、
  OpenRouter 与 NVIDIA NIM 不会从上游模型推定未经平台验证的推理参数。
- OpenAI-compatible 服务商仍支持用户自定义模型 ID 与高级 JSON 参数。
- 新增回归测试锁定云端模型目录、归档写入前门禁、Router 错误契约与游戏专属
  修复提示词。
