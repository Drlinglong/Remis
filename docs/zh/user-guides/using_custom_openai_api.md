# (高级)连接到自定义OpenAI兼容API

> **发布版客户端（推荐）**  
> 在 **设置 → API** 中配置自定义 / OpenAI 兼容供应商：填写 **API Key**、**Base URL**、**模型名** 并保存。  
> 总入口：[Provider 配置速查](provider-setup-index.md)。  
> 下文「环境变量 + 改 `app_settings.py`」适用于开发环境或旧流程；**普通用户不必改源码。**

本文档为掌握基本技术知识的用户准备，旨在指导您如何使用本程序的通用接口，连接到**任何兼容OpenAI API标准**的AI服务。

## 核心功能

我们提供了一个名为 `your_favourite_api` 的通用接口。您可以将它配置为连接到任何您想使用的、兼容OAI的服务，例如某个新兴的AI平台、您朋友的本地服务器，或是其他未被官方预设支持的服务。

**此功能完全依赖于您手动、正确地进行配置。**

---

## 配置流程

### 第一步：手动设置API密钥

您必须手动为您的服务设置API密钥。程序不会通过 `setup.bat` 引导您完成这一步。

1.  获取您要使用的服务的API密钥。
2.  **手动在您的操作系统中**，创建一个名为 `YOUR_FAVOURITE_API_KEY` 的环境变量，并将您的密钥作为其值。

> **警告**：如果您不知道如何设置环境变量，请先自行搜索“Windows/macOS 如何设置环境变量”。这是使用本功能的前提。

### 第二步：配置API地址和模型名称 (关键！)

您必须在配置文件中，明确告知本程序您的API地址（Base URL）和要使用的模型名称。

1.  打开文件: `scripts/app_settings.py`。
2.  找到 `API_PROVIDERS` 字典中的 `your_favourite_api` 条目。
3.  **修改以下两个占位符的值**：
    - `base_url`: 替换为您服务的API地址 (例如 `https://api.example.com/v1`)。
    - `default_model`: 替换为您要使用的模型名称 (例如 `some-model-name-v1`)。

**修改示例：**
```python
# scripts/app_settings.py

"your_favourite_api": {
    "api_key_env": "YOUR_FAVOURITE_API_KEY",
    "base_url": "https://api.example.com/v1",  # <-- 替换成你的API地址
    "default_model": "some-model-name-v1", # <-- 替换成你的模型名称
    "description": "（需要技术知识）连接到您自选的任何兼容OpenAI的API服务"
},
```

> **警告**：如果您不修改这两个占位符，程序在运行时会因找不到有效地址和模型而报错。

### 第三步：启动程序

完成以上所有配置后，即可启动翻译流程。

1.  运行 `run.bat`。
2.  在选择AI服务商时，选择 `your_favourite_api`。
3.  之后按正常流程操作即可。程序将会使用您指定的自定义服务进行翻译。

---

## 故障排除

- **认证失败 (Authentication Error)**: 检查您的 `YOUR_FAVOURITE_API_KEY` 环境变量是否设置正确。
- **连接错误 (Connection Error)**: 检查您在 `app_settings.py` 中填写的 `base_url` 是否正确，以及您的网络是否能访问该地址。
- **404 Not Found (模型未找到)**: 检查您在 `app_settings.py` 中填写的 `default_model` 名称是否正确，以及该模型在您的服务上是否可用。
