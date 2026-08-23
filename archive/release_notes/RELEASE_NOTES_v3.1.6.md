# Project Remis v3.1.6

Released on 2026-08-24.

Version 3.1.6 is a reliability update for proofreading saves, neologism mining
task recovery, and frontend API payload handling.

## English

### Highlights

- Proofreading saves now update the incremental translation baseline together
  with the edited file. If the baseline cannot be updated completely, Remis
  restores the previous file content instead of leaving the project in a
  partially saved state.
- Active neologism mining progress now recovers after a page refresh or project
  revisit. REST polling keeps the status current when WebSocket updates are
  silent or interrupted, and returning to the tab triggers an immediate refresh.
- Project, file, and proofreading validation responses now tolerate supported
  wrapped-list formats and safely ignore malformed records instead of breaking
  navigation or validation results.

### Engineering quality and reliability

- Archive translation updates are atomic: all requested proofreading keys are
  resolved before any database change is committed.
- Neologism task monitoring is isolated from the dashboard UI and guards
  project switches, reconnect races, duplicate terminal events, and cleanup.
- Regression tests cover archive rollback, refresh and disconnect recovery,
  terminal-event deduplication, wrapped API collections, and malformed payloads.

## 中文

### 主要更新

- 校对保存现在会同步更新增量翻译基线与已编辑文件。若基线无法完整更新，Remis
  会恢复保存前的文件内容，避免项目停留在只写入一部分的状态。
- 进行中的术语挖掘现在可在页面刷新或重新进入项目后恢复进度。当 WebSocket
  静默或中断时，REST 轮询会继续同步状态；重新切回页面时也会立即刷新。
- 项目、文件与校对校验接口现在兼容受支持的包裹数组格式，并会安全忽略异常
  记录，避免导航或校验结果因畸形 payload 中断。

### 工程质量与可靠性

- 归档翻译更新改为原子操作：所有待保存的校对 key 全部匹配后才提交数据库
  变更。
- 术语挖掘任务监控已与仪表盘 UI 分离，并处理项目切换、重连竞态、终态重复
  事件与资源清理。
- 新增回归测试，覆盖归档回滚、刷新与断线恢复、终态去重、包裹数组及畸形
  payload。
