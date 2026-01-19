# Remis v2.0.5 Release Notes

## ✨ New Features / 新增功能

### 🤖 LLM Support / 模型支持
- **Integrate TranslateGemma**:
  - Added support for `translategemma` and `translategemma:27b` in the Ollama provider.
  - Added `Modelfile.translategemma` configuration file for one-click model importation into Ollama.
  
  **中文说明**：
  - **集成 TranslateGemma**：在 Ollama 提供商中新增了对 `translategemma` 和 `translategemma:27b` 的支持。
  - 新增了 `Modelfile.translategemma` 配置文件，支持在本地 Ollama 中一键导入该专用翻译模型。

---

## 🛡️ Architecture & Stability / 架构与稳定性

### 🗄️ Database Layer (Critical) / 数据库层加固
- **Async SQLModel Refactor**:
  - Completely migrated all Project Management database operations from native `sqlite3` to **Async SQLModel (Async SQLAlchemy)**.
  - Significantly improved stability under high concurrency (e.g., simultaneous multi-file status updates).
  - Fixed `AttributeError: 'coroutine' ...` during project creation in `FileService`.
  - Fixed `500 Internal Server Error` in Dashboard stats API (`/api/system/stats`) caused by missing `await`.
  - Completed missing statistical methods in `GlossaryManager`.

  **中文说明**：
  - **异步架构重构**：将所有项目管理相关的数据库操作从原生 `sqlite3` 全面迁移到了 **Async SQLModel (Async SQLAlchemy)**。
  - 显著提升了高并发场景下的稳定性（如多文件并行写入状态时）。
  - 修复了 `FileService` 中的异步调用错误，解决了创建项目时偶发的 `AttributeError: 'coroutine'` 奔溃问题。
  - 修复了仪表盘统计接口 (`/api/system/stats`) 因缺少 `await` 导致的 500 错误。
  - 补全了词典管理器 (`GlossaryManager`) 中缺失的统计方法。

### 📦 Workflow & Compatibility / 工作流与兼容性
- **Wrapper Mode Fixes**:
  - Fixed `AttributeError` caused by missing `create_fallback_file` in the translation workflow.
  - Ensured correct generation of fallback files in mixed "raw/translated" translation modes.
- **Enhanced Test Coverage**:
  - Added `tests/core/test_project_repository.py` for automated testing of DB CRUD and statistics.

  **中文说明**：
  - **套壳模式修复**：修复了翻译工作流中因缺少 `create_fallback_file` 方法导致的错误，确保在混合模式下能正确生成兜底文件。
  - **测试覆盖**：新增了对数据库基础操作和统计功能的自动化测试。

---

## 🛠️ Translation & UI Fixes / 翻译与界面修复

### 🧠 Logic Core (Translation Engine) / 翻译引擎逻辑
- **Prompt Refactoring**: 
  - Standardized all game prompts (Vic3, HOI4, EU4, Stellaris, CK3, EU5) to strictly forbid literal newlines.
  - Simplified instructions to "Keep the translation on a single line" to prevent AI hallucinations.
  - Clarified distinction between **Script Variables** (Keep as is) and **Formatting Tags** (Translate content).
  - Fixed Victoria 3 `[Concept]` handling to prevent internal key translation.

  **中文说明**：
  - **Prompt 优化**：统一了所有游戏的提示词，严禁 AI 输出实体换行符，减少解析错误。
  - 明确区分了【脚本变量】和【格式标签】的处理规则。
  - 修复了 Vic3 中 `[Concept]` 内部键名被错误翻译的问题。

### 🔌 Data Parsing & UI / 数据解析与界面
- **Multi-line YAML Support**: Rewrote `QuoteExtractor` with a state-machine to correctly parse multi-line legacy localization values.
- **UI Cache Conflict Fix**: Disabled "Automatic Draft Restoration" in the Proofreading UI to ensure the latest disk content is always displayed first.

  **中文说明**：
  - **多行解析支持**：重写了解析器，现在能正确读取含有实体换行符的旧 YML 文件，解决了校对界面显示“未翻译”的问题。
  - **缓存优化**：禁用了自动恢复草稿功能，确保网页始终优先显示最新的磁盘文件。

---

## 🐛 Known Issues / 已知问题
- **Stale UI Content**: In rare cases, the Proofreading UI may still display outdated content for complex multi-line entries. A manual refresh or cache clear may be required.
  **中文说明**：特定复杂条目下界面内容可能存在滞后，建议手动刷新。
