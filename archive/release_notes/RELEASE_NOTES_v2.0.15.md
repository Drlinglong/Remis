# Release Notes v2.0.15 - Stability Hotfix

## English

### Fixed

- Fixed a long-standing issue where the translation UI could remain stuck at 100% even after the backend had already finished successfully.
- Added a forced final task-state push from the backend so `completed` and `failed` states reliably reach the frontend.
- Added defensive frontend status polling and automatic WebSocket recovery so temporary connection loss no longer traps the UI in a fake loading state.
- Ensured final task updates are re-sent after `result_path` changes, preventing stale completion screens.
- Fixed the `Open Folder` button on the translation completion screen in packaged builds.
- The completion screen now focuses on the translated output folder itself and falls back to its parent directory only when needed.
- Improved backend path opening on Windows so packaged builds can open directories more reliably.

### Version

- Application version updated to `2.0.15`.

---

## 简体中文

### 修复内容

- 修复了一个长期存在的问题：后端实际上已经完成翻译，但前端界面仍可能卡在 `100%` 无法结束。
- 后端现在会在任务结束时强制推送最终状态，确保 `completed` 和 `failed` 能稳定送达前端。
- 前端新增防御性状态轮询与 WebSocket 自动重连，临时断连也不会再把界面卡死在假加载状态。
- 在 `result_path` 更新后会再次发送最终状态，避免完成页信息停留在旧状态。
- 修复了安装包版本中，翻译完成界面的 `打开文件夹` 按钮无反应的问题。
- 完成界面现在会优先打开翻译结果目录本身，仅在必要时回退到其父目录。
- 改进了 Windows 下的路径打开逻辑，使安装包环境中的目录打开更稳定。

### 版本

- 应用版本更新为 `2.0.15`。
