# 使用 Ollama 进行本地化翻译

> **发布版客户端（推荐）**  
> 1. 本机安装 Ollama 并 `pull` 合适模型。  
> 2. 在 Remis **设置 → API** 中选择 Ollama，填写模型名与服务地址（常见 `http://localhost:11434`），保存。  
> 3. 在初次翻译 / 增量翻译任务中选用 Ollama。  
> 总入口：[Provider 配置速查](provider-setup-index.md)。  
> 下文中修改 `scripts/app_settings.py` 的步骤面向 **开发/源码运行**；打包客户端一般 **不需要** 改源码。

本文档将指导您如何设置并在 Project Remis 中使用 [Ollama](https://ollama.com/) 来运行本地大语言模型（LLM）进行翻译。

## 为什么选择 Ollama？

- **隐私与安全**：所有翻译都在您的本地计算机上进行，确保了源代码和内容的隐私。
- **离线工作**：一旦模型下载完成，您可以在没有互联网连接的情况下进行翻译。
- **成本效益**：使用本地模型无需支付API调用费用。
- **高度可定制**：您可以选择并运行各种针对特定任务优化的开源模型。

## 设置步骤

### 1. 安装 Ollama

首先，您需要在您的计算机上安装 Ollama。

- 访问 [Ollama 官方网站](https://ollama.com/)。
- 根据您的操作系统（Windows, macOS, 或 Linux）下载并安装相应的程序。
- 安装程序会自动将 Ollama 设置为后台服务。

### 2. 下载一个有能力的语言模型

安装完 Ollama 后，您需要下载一个语言模型。模型的**遵循复杂指令的能力**至关重要。本程序要求模型以严格的 JSON 格式返回翻译结果，许多小模型或闲聊模型无法做到这一点，从而导致报错。

- **推荐模型**：我们强烈建议从一个强大的、擅长遵循指令的模型开始，例如 `llama3`。
  ```bash
  ollama pull llama3
  ```
- **关于模型选择的警告**：如果您选择其他模型（例如 `qwen`），请确保使用更大、更有能力的版本（例如 `qwen:7b` 而不是 `qwen:4b`）。使用能力不足的模型是导致程序报错的最常见原因。

您可以通过 `ollama list` 命令查看已下载的所有模型。

### 3. 在程序中配置模型

您必须手动在配置文件中，明确告知本程序要使用哪一个 Ollama 模型。

1.  打开文件：`scripts/app_settings.py`。
2.  找到 `API_PROVIDERS` 字典变量。
3.  在 `ollama` 条目下，修改 `default_model` 的值为您已下载好的模型的确切名称。

**示例：**
```python
# scripts/app_settings.py

API_PROVIDERS = {
    # ... 其他服务商
    "ollama": {
        "base_url_env": "OLLAMA_BASE_URL",
        "default_model": "llama3:latest",  # <-- 修改这个值
        "enable_thinking": False,
        "description": "本地Ollama模型，无需API密钥"
    },
}
```

### 4. 故障排除

#### 错误：连接失败 或 `404 Not Found`

这个错误意味着本程序无法连接到您的 Ollama 服务。
- **Ollama 运行了吗？** 请确保 Ollama 程序正在您的电脑上运行。
- **地址对吗？** 程序默认连接 `http://localhost:11434`。如果您在其他地址上运行 Ollama，则必须设置 `OLLAMA_BASE_URL` 环境变量，详情请见下面的“高级”部分。
- **模型名称正确吗？** 这是导致 `404 Not Found` 的另一个常见原因。请确保您在 `scripts/app_settings.py` 中设置的 `default_model` 名称，与您通过 `ollama list` 命令看到的已安装模型列表中的名称完全一致。
- **被防火墙或代理挡住了吗？** 检查您系统的防火墙或代理设置，确保它们没有阻止 Python 程序的网络连接。

#### 错误：`Pydantic validation failed` 或 `Invalid JSON`

这是最常见的错误，它几乎总是意味着**您选择的模型能力不足**。

- **错误解释**：本程序会发送一段复杂的指令，要求模型必须返回一个完美格式的 JSON 数组。这个报错意味着模型没能听懂或遵循这个指令，而是返回了普通的文本或格式错误的数据。
- **解决方案**：您**必须**更换一个更强大的模型。
    - 编辑 `scripts/app_settings.py` 文件，将 `default_model` 修改为您下载好的、能力更强的模型，例如 `llama3`。
    - 如果您在使用 `qwen` 或 `mistral` 等模型系列，请尝试参数量更大的版本（例如 `7b` 而不是 `1b` 或 `4b`）。

### 5. （高级）自定义 Ollama 服务地址

如果您的 Ollama 服务运行在不同的 IP 地址或端口上（例如，在另一台局域网内的机器上），您可以通过设置环境变量来指定连接地址。

- 设置一个名为 `OLLAMA_BASE_URL` 的环境变量。
- 将其值设置为您的 Ollama 服务的完整 URL。

**示例：**

- 在 Windows 上：
  ```cmd
  set OLLAMA_BASE_URL=http://192.168.1.100:11434
  ```
- 在 macOS 或 Linux 上：
  ```bash
  export OLLAMA_BASE_URL=http://192.168.1.100:11434
  ```

设置完成后，重新启动本程序，它将自动使用您指定的新地址。

---

现在您已经准备好使用 Ollama 在本地进行安全、高效的 Mod 本地化翻译了！
