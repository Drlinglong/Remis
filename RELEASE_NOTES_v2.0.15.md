# Release Notes v2.0.15 - Completion State Hotfix

## [English]

### Stability

- Fixed a long-standing issue where the translation UI could remain stuck at 100% even after the backend had already completed successfully.
- Added a forced final task-state push from the backend so `completed` and `failed` states always reach the frontend.
- Added defensive frontend status polling and automatic WebSocket recovery so temporary connection loss no longer traps the UI in a fake loading state.
- Ensured final task updates are re-sent after `result_path` changes, preventing stale completion screens.

### Packaging

- Bumped the application version to `2.0.15`.

---

## [简体中文]

### 稳定性

- 修复了一个长期存在的问题：后端实际上已经完成翻译，但前端界面仍可能卡在 `100%` 无法结束。
- 后端现在会在任务结束时强制推送最终状态，确保 `completed` 和 `failed` 能稳定送达前端。
- 前端新增防御性状态轮询与 WebSocket 自动重连，临时断连也不会再把界面卡死在假加载状态。
- 在 `result_path` 更新后会再次发送最终状态，避免完成页信息停留在旧状态。

### 打包

- 应用版本号更新为 `2.0.15`。
