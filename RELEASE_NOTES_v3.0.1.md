# Release Notes v3.0.1

## English

## Stable Release

`v3.0.1` is the first stable release of the Remis 3.0 series. It focuses on startup reliability, backend lifecycle handling, and the UI responsiveness problems reported by preview users.

## Fixes and Improvements

- Fixed startup instability caused by stale backend processes and repeated launches.
- Moved the packaged backend from port `8081` to the lower-conflict Remis port `1453`.
- Added backend identity and health checks so the desktop app can reuse a healthy matching backend instead of blindly killing the port on every launch.
- Changed port cleanup to only terminate stale Remis backend processes, leaving unrelated programs untouched.
- Improved project page responsiveness by preventing inactive project tabs from mounting and loading data unnecessarily.
- Removed the development DevTools window from release startup.
- Updated API, WebSocket, Vite proxy, developer scripts, and packaged metadata for `v3.0.1`.

## Notes

- If you tested `v3.0.0 Preview` and saw slow project tabs, an unresponsive "new translation project" button, missing API key inputs, or startup behavior that only worked after reopening the app, please try this version.
- The default backend port is now `1453`. Advanced users can override it with `REMIS_BACKEND_PORT` / `VITE_BACKEND_PORT` when needed.
- This release includes a Windows installer: `remis-mod-factory_3.0.1_x64-setup.exe`.

## 中文

## 稳定版发布

`v3.0.1` 是 Remis 3.0 系列的第一个稳定版。这个版本主要修复预览版用户反馈的启动可靠性、后端残留进程、以及项目页交互卡顿问题。

## 修复与改进

- 修复了多次启动、旧后端残留、冷启动时可能导致 API 短时间不可用的问题。
- 将打包版后端默认端口从 `8081` 迁移到 Remis 早期使用过、冲突概率更低的 `1453`。
- 增加后端 identity 与 health check：如果已有后端健康且属于当前 Remis 版本/工作区，会复用它，而不是每次启动都粗暴清理端口。
- 端口清理现在只会终止识别为 Remis 自己的残留后端进程，不再误伤占用同端口的其他程序。
- 优化项目页 tab 响应速度，避免未激活的 tab 提前挂载并触发不必要的数据加载。
- 移除了正式版启动时自动弹出的开发者工具窗口。
- 同步更新 API、WebSocket、Vite 代理、开发脚本和打包元数据到 `v3.0.1`。

## 说明

- 如果你在 `v3.0.0 Preview` 中遇到项目页 tab 很慢、新建翻译项目按钮无响应、API key 输入框偶尔不出现、或需要重开软件才正常的问题，请尝试这个版本。
- 默认后端端口现在是 `1453`。高级用户仍可通过 `REMIS_BACKEND_PORT` / `VITE_BACKEND_PORT` 覆盖。
- 本版本提供 Windows 安装包：`remis-mod-factory_3.0.1_x64-setup.exe`。
