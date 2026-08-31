# Project Remis v3.1.8

Released on 2026-08-31.

Version 3.1.8 is a stability-focused hotfix for translation task recovery,
provider failures, and project locking. It also adds reusable Custom Provider
profiles and temporarily removes unfinished stateful modules from the stable
channel.

## English

### Highlights

- **Save and switch between multiple Custom Provider profiles.** OpenAI-compatible
  endpoints can now be created as separately named profiles with their own URL,
  model, inference settings, and protected API-key reference. Existing single
  Custom Provider settings migrate automatically.
- **Translation failures stop instead of locking a project indefinitely.** Invalid
  models, authentication failures, and other fatal provider errors now abort the
  workflow instead of repeating the same failure for every batch.
- **Cancel an active translation safely.** Initial translation tasks can be
  cancelled from Task Center. Remis stops scheduling new batches, waits for the
  current provider request to finish safely, then releases the project lock.
- **Recover honestly after an interrupted desktop session.** Translation workers
  that no longer exist are reported as interrupted rather than remaining shown as
  active. Task Center now presents fatal provider errors and recovery actions more
  clearly.
- **Unsaved settings are harder to lose.** API Settings and Assistant Settings warn
  before leaving when edited values have not been saved.
- **A major desktop interface refresh.** The dashboard, project workspace,
  terminology tools, task details, themes, motion, and keyboard interactions now
  share a clearer and more consistent workflow-focused design.
- **Updated provider model choices.** The built-in cloud model candidate lists have
  been refreshed for currently supported providers.

### Temporary stable-channel limits

- Checkpoint resume is temporarily disabled in the stable build while its state
  machine is redesigned around Task Center as the single source of truth. Existing
  checkpoint files are preserved, but v3.1.8 does not consume them.
- Project Archive is temporarily hidden and its stable API routes are disabled.
  Neologism Tribunal remains available. The Remis Agent entry also remains hidden
  in the stable build.
- These modules will return in a later release after their task ownership,
  cancellation, restart recovery, and project-lock transitions have been rebuilt
  and verified together.

### Engineering quality and reliability

- Provider configuration is snapshotted when a task starts, so editing a profile
  cannot silently switch endpoints halfway through a running translation.
- Provider selectors store stable profile identifiers. Deleting the selected
  profile never silently chooses an unrelated replacement.
- Invalid or incomplete Custom Provider profiles now show actionable validation
  guidance instead of exposing a raw settings-page error.
- API keys continue through the existing protected secret-storage path and remain
  masked in UI, logs, exports, and diagnostics.
- Cancellation is cooperative and terminal: a cancelling task cannot be changed
  back to running or completed by a late worker update, and its project lock is
  retained until cancellation is acknowledged.
- Stable translation requests cannot re-enable checkpoint resume or Project
  Archive by bypassing the UI.
- Removing one official reference corpus keeps the other game entries visible
  while SQLite cleanup continues in the background.

## 中文

### 主要更新

- **保存并切换多个 Custom Provider 配置。** OpenAI-compatible 端点现在可以保存为
  多张独立命名的配置卡，每张卡分别保存 URL、模型、推理设置和受保护的 API Key
  引用。旧版单一 Custom Provider 设置会自动迁移，无需重新配置。
- **翻译失败不再长时间锁死项目。** 无效模型、鉴权失败及其他不可恢复的 Provider
  错误现在会直接终止整个工作流，不再让每个 batch 重复同一种失败。
- **安全取消正在运行的翻译。** 用户可以从任务中心取消初次翻译任务。Remis 会停止
  调度新的 batch，等待当前 Provider 请求安全结束，然后释放项目锁。
- **桌面端意外退出后如实恢复状态。** 已经失去执行线程的翻译任务会显示为“已中断”，
  而不是继续伪装成运行中；任务中心也会更清楚地展示致命 Provider 错误和恢复操作。
- **未保存的设置不再容易丢失。** API 设置和小助手设置存在未保存修改时，离开页面前
  会明确提示返回检查或放弃改动。
- **桌面端界面迎来大幅更新。** 首页仪表盘、项目工作区、术语工具、任务详情、主题、
  动效和键盘交互现在采用更清晰、更一致且更聚焦工作流的设计。
- **更新 Provider 模型候选。** 内置云端 Provider 的模型候选列表已同步到当前支持范围。

### 稳定版临时限制

- 稳定版暂时禁用断点续传，后续会以任务中心为唯一事实来源重新设计其状态机。
  现有断点文件会保留，但 v3.1.8 不会读取并续跑这些断点。
- 稳定版暂时隐藏项目档案馆，同时关闭对应的稳定版 API 路由。新词审判庭继续可用；
  Remis Agent 入口也仍然保持隐藏。
- 后续版本会在任务归属、取消、重启恢复和项目锁状态迁移完成统一重构与验证后，
  重新开放这些模块。

### 工程质量与可靠性

- 翻译任务启动时会保存 Provider 配置快照，因此运行过程中编辑配置不会让同一任务
  中途静默切换到另一个端点。
- Provider 选择器保存稳定的配置 ID；删除当前选中的配置后，不会静默切换到无关配置。
- Custom Provider 配置不完整或端点格式无效时，会显示可操作的校验提示，不再直接
  暴露设置页错误。
- API Key 继续沿用既有受保护密钥存储路径，并在 UI、日志、导出和诊断信息中保持掩码。
- 取消采用协作式终态处理：进入“正在取消”的任务不会被迟到的工作线程改回运行中或
  已完成，并且只有在取消得到确认后才释放项目锁。
- 即使绕过前端，稳定版翻译请求也无法重新启用断点续传或项目档案馆。
- 删除单个官方参考语料库时，其他游戏条目会在 SQLite 后台清理期间保持可见。
