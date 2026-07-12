# 使用 ModelScope（魔搭）与 SiliconFlow（硅基流动）

二者均提供大量可选开源模型，适合在国内网络环境下按预算与效果「点菜」。  
总入口：[Provider 配置速查](provider-setup-index.md)。

## 核心优势

- 模型选择多，可换不同规模与价位  
- 在 Remis 里与其它供应商一样：在 **设置 → API** 填 Key 与模型即可  

## 设置步骤

### 1. 获取密钥

| 平台 | 密钥位置（以官网为准） |
|------|------------------------|
| **ModelScope（魔搭）** | 个人中心 [AccessToken](https://modelscope.cn/my/my-accesstoken) 等页面 |
| **SiliconFlow（硅基流动）** | 账户 / API 密钥相关页面，见 [siliconflow.cn](https://siliconflow.cn/) |

### 2. 选择模型 ID

1. 在 [ModelScope 模型库](https://modelscope.cn/models) 或 SiliconFlow 模型/价目页浏览。  
2. 选择支持对话 / 指令的模型，**复制完整模型 ID 或名称**。  

### 3. 在 Remis 中填写

1. 打开 **设置 → API**。  
2. 找到 **ModelScope** 或 **SiliconFlow**（国内供应商分组内）。  
3. 粘贴 **Token / API Key** 与 **模型 ID**。  
4. **保存**。  
5. 在 **初次翻译 / 增量翻译** 中选用对应供应商与模型。  

## 故障排除

| 现象 | 处理 |
|------|------|
| 认证失败 | 回设置页检查 Token 是否完整、是否保存；是否过期 |
| 404 模型未找到 | 模型 ID 拼写；该平台上是否仍提供该模型 |
| 限流 / 配额 | 控制台额度；翻译任务中降低并发与 RPM |
| 解析失败 | 换指令遵循更好的模型 |

详见 [日志与诊断](logs-and-diagnostics.md)、[FAQ](faq.md)。

## 相关文档

- [Provider 配置速查](provider-setup-index.md)  
- [从零开始](getting-started.md)  
