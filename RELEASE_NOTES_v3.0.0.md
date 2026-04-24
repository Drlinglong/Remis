# Release Notes v3.0.0

## English

## Preview Notice

This is a preview release for a major `3.0.0` upgrade, not a stable rollout.

- The desktop workflow has been substantially reworked around project-based translation, guided onboarding, and a more complete Tauri desktop experience.
- Incremental translation is now backed by dedicated preparation, diff, snapshot, archive, build, package, and translation services.
- The frontend now includes a fuller initial-translation flow, stronger project validation, richer history/activity views, and better in-app guidance.
- Backend and integration coverage were expanded across project management, system utilities, archive handling, proofreading, and workshop flows.
- The repository was cleaned up for public presentation by removing tracked temporary artifacts, replacing machine-specific paths with configurable scripts, and shipping a safe `.env.example`.

## Notes for Preview Users

- Please treat this build as a major-version transition and expect some rough edges.
- Existing workflows should be more complete, but some behavior may differ from the `2.x` series because of the architecture refactor.
- If you run into bugs, migration issues, unclear UX, or unexpected translation results, please open an issue and include logs or reproduction steps when possible.
- If anything is confusing, that feedback is also valuable. Questions and bug reports are both welcome.

## 中文

## Preview 提示

这是一次面向重大升级的 `3.0.0` 预览版发布，不是稳定版正式发布。

- 桌面端工作流进行了较大重构，核心方向是项目化翻译、内置引导和更完整的 Tauri 桌面体验。
- 增量翻译链路已经拆分为 preparation、diff、snapshot、archive、build、package、translation 等独立服务模块。
- 前端补全了初始翻译流程、项目校验、历史/活动展示和更多引导式体验。
- 后端与集成测试覆盖扩展到了项目管理、系统能力、归档处理、校对能力和 workshop 流程。
- 为了让仓库更适合公开展示，也顺手清理了一批临时产物、本机硬编码路径和不必要的开发残留，并补充了安全的 `.env.example`。

## 给预览版用户的说明

- 请把这个版本视为一次大版本过渡，使用中可能仍会遇到边角问题。
- 相比 `2.x` 系列，很多流程已经更完整，但由于底层架构重构，部分行为和旧版可能会有所不同。
- 如果你遇到 bug、迁移异常、界面/交互疑问，或者翻译结果有不符合预期的地方，欢迎提交 issue，最好附上日志或复现步骤。
- 即使不是 bug，只是“哪里看不懂”或者“哪里用起来别扭”，也非常欢迎反馈。
