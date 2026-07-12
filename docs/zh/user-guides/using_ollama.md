# 使用 Ollama 进行本地化翻译

本文说明如何在 **Remis 客户端** 中使用 [Ollama](https://ollama.com/) 做本地模型翻译。  
总入口：[Provider 配置速查](provider-setup-index.md)。

## 为什么选择 Ollama？

- **隐私**：译文在本地处理  
- **可离线**：模型下载完成后可不依赖云端  
- **无云端 token 费用**（仍占用本机算力）  
- 可换用多种开源模型  

## 设置步骤

### 1. 安装 Ollama

1. 打开 [Ollama 官网](https://ollama.com/)，按系统安装。  
2. 安装后确认 Ollama 在后台运行。  

### 2. 下载足够强的模型

Remis 需要模型 **稳定按指令返回结构化结果**（常见为 JSON 批次）。过小的聊天模型容易报错。

推荐从指令遵循较好的模型起步，例如：

```bash
ollama pull llama3
```

若使用其它系列（如 `qwen`），请优先 **更大参数量** 的版本（例如 `7b` 而不是 `1b`/`4b`）。  
用 `ollama list` 查看本机已有模型名称，后面填写时须 **完全一致**。

### 3. 在 Remis 里配置

1. 打开 Remis → **设置 → API**。  
2. 在本地分组中找到 **Ollama**。  
3. 填写：  
   - **模型名**：与 `ollama list` 一致（如 `llama3:latest`）  
   - **服务地址 / Base URL**：本机默认多为 `http://localhost:11434`  
   - API Key：Ollama 通常 **不需要**  
4. **保存**。  
5. 在 **初次翻译** 或 **增量翻译** 的任务配置里，选择 Ollama 与同一模型，再开始翻译。  

### 4. 使用其它机器上的 Ollama（可选）

若 Ollama 跑在局域网另一台电脑上：

1. 在那台机器上确认服务已监听且防火墙放行。  
2. 在 Remis **设置 → API → Ollama** 的地址栏填写完整 URL，例如：  
   `http://192.168.1.100:11434`  
3. 保存后重试连接 / 翻译。  

## 故障排除

### 连接失败 或 `404 Not Found`

- Ollama 是否在运行？  
- 地址端口是否与设置页一致？  
- 模型名是否与 `ollama list` **逐字相同**？  
- 本机防火墙是否拦截 Remis 访问本地端口？  

更细日志见 [日志与诊断](logs-and-diagnostics.md)。

### `Invalid JSON` / 校验失败 / 解析失败

多半是 **模型能力不够**，没有按格式返回结果。

- 换成更强的模型（更大、更擅长指令）  
- 在 **设置 → API** 改模型名并保存，翻译任务里同步选用  
- 本地可适当 **降低并发 / RPM**  

## 相关文档

- [Provider 配置速查](provider-setup-index.md)  
- [从零开始](getting-started.md)  
- [FAQ](faq.md)  
