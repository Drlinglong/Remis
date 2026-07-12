# AI 服务商 / 本地模型配置速查

> 打包客户端用户：**密钥与模型优先在应用内配置**。  
> 路径：**设置 → API**（或设置页中的 API 页签）。  
> **不要**为了改模型去改 Remis 源码；也 **不要** 把完整 API Key 发到公开 Issue 或聊天。

旧文档里若仍写 `setup.bat`、环境变量、`scripts/app_settings.py`，那是 **开发者 / 历史** 路径，仅作补充参考。

---

## 1. 通用步骤（所有供应商）

1. 打开 Remis → 左侧 **「设置」**。  
2. 进入 **API** 配置区。  
3. 按地区/类型找到供应商卡片（界面常分组为海外、国内、本地等）。  
4. 填写：  
   - **API Key**（本地无 Key 的方案可留空或按说明）  
   - **模型** 名称  
   - **Base URL**（本地与自定义 OpenAI 兼容接口通常必填）  
5. **保存**。  
6. 回到 **初次翻译 / 增量翻译**，在任务配置里选择同一供应商与模型。  
7. 失败时看 [日志与诊断](logs-and-diagnostics.md)，搜索 `401`、`403`、`429`、`timeout`。

翻译任务里的供应商列表，取决于你在设置中已配置/启用的项。

---

## 2. 我该选哪一类？

| 你的情况 | 建议方向 | 备注 |
|----------|----------|------|
| 有国外云 API，要质量与省事 | Gemini / OpenAI / Anthropic / Grok 等 | 需网络与合规访问；注意费用 |
| 有国内云 API | 通义、DeepSeek、Kimi、硅基流动、魔搭等 | 以设置页实际列表为准 |
| 想离线、隐私、不付 token 费 | **Ollama** 或其它本地服务 | 模型要够大，能稳定吐结构化结果 |
| 列表里没有的 OpenAI 兼容中转 | **自定义 / your favourite** 类通用接口 | 需正确 Base URL + Key + 模型名 |
| 只有游戏、没有 AI 账号 | 先装 Ollama 或申请任一云服务 | Remis 不自带翻译额度 |

---

## 3. 供应商速查表

下列名称以客户端分组为准；具体是否出现以你安装的版本为准。

### 3.1 海外云（示例）

| 设置中的方向 | 你需要准备 | 详细文档 |
|--------------|------------|----------|
| Gemini 等 | 官网 API Key | 以设置页说明为准；通用问题见 [FAQ](faq.md) |
| OpenAI | API Key；注意账号与地区 | 同上 |
| Anthropic / NVIDIA / Grok 等 | 对应平台 Key | 同上 |

### 3.2 国内云与聚合（示例）

| 方向 | 你需要准备 | 详细文档 |
|------|------------|----------|
| 硅基流动 SiliconFlow | 平台 Token + 模型 ID | [ModelScope 与 SiliconFlow](using_modelscope_and_siliconflow.md)（**配置方式以设置页为准**，文中改 py 文件为旧述） |
| 魔搭 ModelScope | AccessToken + 模型 ID | 同上 |
| 通义 / DeepSeek / Kimi 等 | 各平台 Key 与模型名 | 设置页填写；无单独专文时以官方文档 + 本速查通用步骤为准 |

### 3.3 本地与兼容端点

| 方向 | 你需要准备 | 详细文档 |
|------|------------|----------|
| **Ollama** | 本机安装 Ollama、pull 模型；URL 常见 `http://localhost:11434` | [使用 Ollama](using_ollama.md)（优先设置页选 Ollama 与模型名；**勿依赖改源码**） |
| LM Studio / vLLM / 其它本地 OpenAI 兼容 | 服务已启动；Base URL 常见形如 `http://localhost:1234/v1`；模型名与服务端一致 | 设置页填 URL + 模型；可参考 [自定义 OpenAI API](using_custom_openai_api.md) 的概念说明 |
| 自定义中转 / 任意 OAI 兼容 | Key + Base URL + 模型名 | [自定义 OpenAI 兼容 API](using_custom_openai_api.md)（**客户端用设置页**，不必设系统环境变量，除非你在开发模式） |

### 3.4 填写时注意

- **模型名** 必须与服务商控制台 / `ollama list` 一致，多一个空格都会失败。  
- **本地小模型** 容易无法遵守 JSON/批量格式 → 翻译报错；宁可选更大、指令遵循更好的模型（见 Ollama 文档中的警告）。  
- **Base URL** 不要多抄或少抄路径（有的要到 `/v1`，有的只要根地址，以该服务文档为准）。  
- **密钥**：只保存在本机设置中；反馈 Bug 时打码。  

---

## 4. 常见失败对照

| 现象 | 先检查 |
|------|--------|
| Key 无效 / 401 | 设置页是否保存成功；是否选对供应商；Key 是否过期 |
| 429 / 配额 | 控制台额度；降低翻译里的并发与 RPM |
| 连接失败 / 超时 | 网络、代理、防火墙；本地服务是否已启动；URL 端口 |
| 返回解析失败 | 模型太弱或不支持指令格式；换模型或减小批次 |
| 翻译页没有该供应商 | 是否在设置中配置/启用；重启客户端后再看 |

更细的日志位置：[日志与诊断](logs-and-diagnostics.md)。

---

## 5. 与翻译流程的关系

```text
设置 → API（配好 Key/模型/URL）
        ↓
项目管理 → 创建项目
        ↓
初次翻译 / 增量翻译（任务里再选供应商与模型）
```

只配设置、不在任务里选对应模型，或只在任务里选、设置里 Key 为空，都会失败。

---

## 6. 相关文档

- [从零开始](getting-started.md)  
- [FAQ](faq.md)  
- [使用 Ollama](using_ollama.md)  
- [自定义 OpenAI 兼容 API](using_custom_openai_api.md)  
- [ModelScope 与 SiliconFlow](using_modelscope_and_siliconflow.md)  
- [日志与诊断](logs-and-diagnostics.md)  

> 下方三篇旧专文可能仍含 `setup.bat` / 改配置文件步骤；**发布版客户端请始终以「设置 → API」为准**，专文仅补充概念与平台链接。  
