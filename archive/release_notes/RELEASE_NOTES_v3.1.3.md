# Project Remis v3.1.3

Released on 2026-08-03.

Version 3.1.3 is the post-3.1.2 maintenance release for backend persistence,
localization integrity, and cross-theme readability.

## English

### Highlights

- Hardens SQLite migration bookkeeping, first-run seed handling, task-state
  persistence, and backend API response contracts.
- Replaces the two divergent Paradox localization readers with one canonical
  parser while preserving compatibility wrappers for existing callers.
- Makes parser spans available to writeback paths so quoted values, comments,
  variables, BOMs, and physical multiline entries survive parse and patch.
- Keeps completed translation reports readable when a dark theme uses a dark
  result surface.

### Validation

- Focused backend, database, router-contract, parser, and writeback tests pass.
- Python source compilation and the architecture gate pass without raising the
  existing baseline.
- The packaged backend passed its health check and the Windows Tauri NSIS
  installer was built and verified for publication.

## 中文

### 主要更新

- 加固 SQLite 迁移记录、首次启动 seed、任务状态持久化和后端 API 响应契约。
- 用唯一 canonical parser 统一两套 Paradox 本地化读取实现，同时保留兼容 wrapper。
- 让写回流程使用解析 span，确保带引号 value、注释、变量、BOM 和物理多行条目在
  parse 与 patch 后保持完整。
- 修复深色主题下翻译完成报告卡片的深色背景与深色文字冲突。

### 验证

- 后端、数据库、router 契约、解析器和写回相关聚焦测试通过。
- Python 源码编译与架构门禁通过，未提高既有 baseline。
- 冻结后端已通过健康检查，Windows Tauri NSIS 安装包已构建并完成发布前校验。
