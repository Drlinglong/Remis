# 使用 ModelScope (魔搭) 和 SiliconFlow (硅基流动)

> **发布版客户端（推荐）**  
> 在 **设置 → API** 中找到魔搭 / 硅基流动（或同类国内供应商），填写 Token 与 **模型 ID**，保存后在翻译任务中选用。  
> 总入口：[Provider 配置速查](provider-setup-index.md)。  
> 下文 `setup.bat` / 修改 `app_settings.py` 面向开发或历史流程；**打包客户端以设置页为准。**

本文档将指导您如何配置并使用 ModelScope (魔搭) 和 SiliconFlow (硅基流动) 这两个与 OpenAI API 兼容的服务商。

## 核心优势：自由选择模型

与调用官方API的服务商不同，ModelScope 和 SiliconFlow 的最大优势在于它们提供了海量的、不同规模和特性的开源大语言模型。您可以像“点菜”一样，自由选择最适合您需求和预算的模型进行翻译。

---

## 设置流程

### 第一步：设置 API 密钥

这是使用一切功能的前提。您可以通过运行 `setup.bat` 来方便地设置环境变量。

1.  运行项目根目录下的 `setup.bat` 文件。
2.  根据菜单提示，选择 `ModelScope (魔搭)` 或 `SiliconFlow (硅基流动)`。
3.  根据指引，粘贴您从相应平台获取的 API 密钥或 Token。
    - **ModelScope (魔搭)**: 密钥在个人中心的 [AccessKey 管理](https://modelscope.cn/my/my-accesstoken) 页面。
    - **SiliconFlow (硅基流动)**: 密钥在您的 [账户信息](https://siliconflow.cn/) 中。

`setup.bat` 会为您自动创建和设置所需的环境变量 (`MODELSCOPE_API_KEY` 或 `SILICONFLOW_API_KEY`)。

### 第二步：选择并配置模型 (关键！)

这是发挥这两个平台优势最重要的一步。您需要手动指定您想使用的模型。

1.  **浏览并选择模型**:
    - 访问 [ModelScope 模型库](https://modelscope.cn/models) 或 [SiliconFlow 模型列表](https://siliconflow.cn/pricing)。
    - 寻找一个您喜欢的、支持对话或指令遵循的模型（通常名字里带 `Instruct` 或 `Chat`）。复制它的模型ID/名称。

2.  **修改配置文件**:
    - 打开文件: `scripts/app_settings.py`。
    - 找到 `API_PROVIDERS` 字典中的 `modelscope` 或 `siliconflow` 条目。
    - 将您刚刚复制的模型ID，粘贴到 `default_model` 字段的值中。

#### ModelScope 示例 (修改为您选择的模型)
```python
# scripts/app_settings.py
"modelscope": {
    "api_key_env": "MODELSCOPE_API_KEY",
    "base_url": "https://api-inference.modelscope.cn/v1/",
    "default_model": "deepseek-ai/DeepSeek-V3.2-Exp",  # <-- 修改这里为你选择的模型ID
    "description": "通过魔搭（ModelScope）调用AI模型"
},
```

#### SiliconFlow 示例 (修改为您选择的模型)
```python
# scripts/app_settings.py
"siliconflow": {
    "api_key_env": "SILICONFLOW_API_KEY",
    "base_url": "https://api.siliconflow.cn/v1",
    "default_model": "DeepSeek-R1", # <-- 修改这里为你选择的模型名称
    "description": "通过硅基流动（SiliconFlow）调用AI模型"
},
```

### 第三步：启动程序

完成以上所有配置后，现在您可以启动翻译流程了。

1.  运行 `run.bat`。
2.  在选择AI服务商时，选择您刚刚配置好的 `ModelScope` 或 `SiliconFlow`。
3.  之后按正常流程操作即可。程序将会使用您指定的模型进行翻译。

---

## 故障排除

- **认证失败 (Authentication Error)**: 您的API密钥有误。请重新运行 `setup.bat` 设置正确的密钥。
- **404 Not Found (模型未找到)**: 您在 `app_settings.py` 中填写的 `default_model` 名称有误或在平台上不可用。请仔细检查拼写。