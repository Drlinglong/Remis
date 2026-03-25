# Release Notes v2.0.14 - Stability & Validator Update

## [English]

### 🚀 Performance & Stability

- **WebSocket Throttling**: Implemented a 200ms cooldown for UI updates to prevent "endless loading" hangs caused by massive validation error floods.
- **Log Capping**: Detailed validation error logs are now capped at 50 entries per file in the console to reduce I/O pressure. Full details remain available in the CSV report.
- **Memory Optimization**: Added limits to in-memory log history to prevent crashes during extremely large translation tasks.

### 🛡️ Validator Improvements

- **Game-Specific Rules**:
  - **HOI4 & Stellaris**: Now permits non-ASCII characters (Cyrillic, etc.) inside `$ $` variables, as these are often localized in these titles.
  - **Victoria 3**: Restored strict ASCII enforcement for `$ $` keys to prevent script corruption, matching the game's formatting requirements.
- **Improved Reporting**: Fixed a bug where the "Proofreading Progress Table" CSV sometimes ignored validation results. Now includes a clear summary and line-by-line notes.
- **Auto-Export**: A detailed `format_validation_report_{timestamp}.csv` is now automatically generated after every translation run.

### ⚙️ Settings & UI

- **Rate Limit Control**: Added a **30 RPM** option to the Global RPM Limit settings for better balance between speed and API stability.

---

## [简体中文]

### 🚀 性能与稳定性

- **WebSocket 节流机制**：实现了 200ms 的 UI 更新冷却时间，彻底解决了因瞬时海量验证错误导致的“无尽加载”假死问题。
- **日志上限控制**：控制台详细验证错误现在限制为每个文件最多 50 条，大幅降低了 I/O 压力。完整错误信息仍可在生成的 CSV 报告中查看。
- **内存优化**：为内存日志记录添加了硬上限，防止在超大型翻译任务中因日志堆积导致内存溢出。

### 🛡️ 验证器改进

- **游戏特定规则适配**：
  - **钢铁雄心4 (HOI4) & 群星 (Stellaris)**：现在允许在 `$ $` 变量内部出现非 ASCII 字符（俄文/中文），适配这些游戏中的本地化变量需求。
  - **维多利亚3 (Vic3)**：恢复了 `$ $` 变量的严格 ASCII 校验，防止因误翻译 Key 导致的游戏脚本崩溃。
- **报告功能修复**：修复了“校对进度表” CSV 忽略验证结果的 Bug。现在会正确导出详细的错误统计和行号备注。
- **自动导出报告**：每次翻译完成后会自动生成一份详尽的 `format_validation_report_{时间戳}.csv`。

### ⚙️ 设置与 UI

- **频率限制控制**：设置菜单中新增了 **30 RPM** 选项，让用户能更精细地平衡翻译速度与 API 稳定性。
