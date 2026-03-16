# Release Notes - v2.0.11 (2026-03-17)

## English

### 🚀 New Features & Improvements
- **Improved Error Reporting**: Explicit API error summaries (429, 403, 401, etc.) are now displayed directly on the translation page.
- **Robust Rate Limiting**: Implemented exponential backoff for 429 (Too Many Requests) errors (30s, 60s, 120s...).
- **Enhanced Model Flexibility**: Removed hardcoded `max_tokens=4000` limit; the system now adapts to model capabilities.
- **Direct Model Selection**: Explicitly passed `model_id` parameters now bypass fallback validation, allowing full control over specialized models.

### 🛠️ Bug Fixes
- **Checkpoint Reliability**: Fixed a critical issue where failed files were incorrectly marked as completed. They will now be correctly re-processed in subsequent runs.

---

## 中文 (Chinese)

### 🚀 新功能与改进
- **改进的错误报告**：翻译页面现在会直接显示具体的 API 错误摘要（如 429 频率超限、403 权限被拒等），方便快速排障。
- **更强的速率限制防御**：针对 429 (Too Many Requests) 错误实现了指数退避重试逻辑（从 30s 开始翻倍递增）。
- **增强的模型灵活性**：移除了硬编码的 `max_tokens=4000` 限制，充分利用长文本模型的处理能力。
- **直接模型指定**：明确传入的 `model_id` 参数现在将跳过回退校验，允许直接使用任何有效的 API 模型。

### 🛠️ Bug 修复
- **断点记录可靠性**：修复了翻译失败的文件也会被标记为执行完成的问题。现在只有成功的文件会被记录，失败的文件在下次启动时会自动重试。
