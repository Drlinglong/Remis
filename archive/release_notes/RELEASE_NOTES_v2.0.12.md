# Release Notes v2.0.12

## 简体中文 (Chinese)

### 🚀 新功能与改进
- **统一 API 超时时间**：将 NVIDIA NIM、OpenAI 和 Gemini 的超时时间统一延长至 **300秒 (5分钟)**。旨在彻底解决在翻译大型批次或服务器负载较高时出现的 `TimeoutError` 问题，减少回退到英文原文的情况。
- **优化 WebSocket 稳定性**：修复了前端状态更新导致的 WebSocket “连接洪水”问题。现在连接更加稳定，显著降低了后端日志负载和前端重绘开销。

### 🐞 Bug 修复
- **HOI4 规则优化**：修复了 HOI4 验证规则中对 `£` 字符（Text Icons 标识符）的误报。现在 `£GFX_...` 等格式会被正确识别为合法字符，不再触发假警报。
- **前端状态管理**：修复了 `usePersistentState` 钩子导致的组件不必要的重新渲染。

---

## English

### 🚀 Features & Improvements
- **Standardized API Timeouts**: Extended timeouts for NVIDIA NIM, OpenAI, and Gemini to **300 seconds (5 minutes)**. This is designed to eliminate `TimeoutError` issues during large batch translations or high server loads, reducing fallbacks to original English text.
- **WebSocket Stability Optimization**: Resolved the WebSocket "connection flood" issue caused by frequent frontend state updates. Connections are now stable, significantly reducing backend log load and frontend re-rendering overhead.

### 🐞 Bug Fixes
- **HOI4 Rule Optimization**: Fixed false positives for the `£` character (Text Icon identifier) in HOI4 validation rules. Tags like `£GFX_...` are now correctly recognized as valid.
- **Frontend State Management**: Fixed unnecessary component re-renders caused by the `usePersistentState` hook.
