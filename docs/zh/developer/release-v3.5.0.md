# Remis v3.5.0

准备日期：2026-11-25

## 中文

### 主要更新

- 《火星求生》和《深空当铺》词典随 Remis 安装。在词典管理中按游戏查看、编辑和选用，已有词典和项目绑定保留。《火星求生》含 1,711 条简中术语和 278 条含正体译法的术语，《深空当铺》含 851 个术语和 8 种语言。两款游戏的内置词典均为可选参考库。
- 《维多利亚 3》可在已验证的目标语言词典归档基础上做套壳增量。同日重跑会保留先前产物，失败文件可重试。
- Model Arena 在切换导出模式或场次时只接受当前预览。项目追踪和 Archive A/B 的表单遇到无效输入时给出提示，并保留草稿以便修改。

### 工程质量与可靠性

- 隔离共享 SQLite 归档连接上的事务，启用外键检查。
- 套壳增量要求源归档具有匹配的语言身份。缺少身份的旧归档仍可查看，需要先建立已验证基线才能用于增量。
- 《深空当铺》的内置词典可单独浏览和编辑。此版本尚未加入该游戏的翻译适配器。
- 《火星求生》词典仍提供独立下载。资源版本为 `2026.10.08.1`。
- 创意工坊上传继续作为测试功能提供。

## English

### Highlights

- Remis installs optional reference glossaries for Surviving Mars and Probably Stolen. Browse, edit and select them in Glossary Manager. Existing glossaries and project bindings are preserved. Surviving Mars includes 1,711 Simplified Chinese terms and 278 entries with Traditional Chinese wording. Probably Stolen includes 851 terms across eight languages.
- Victoria 3 shell-language projects can translate incremental updates using a verified matching baseline. Same-day reruns preserve previous packages, and files that fail can be retried.
- Model Arena uses the current export preview when you switch modes or runs. Project Tracking and Archive A/B show validation errors and preserve drafts so that you can correct and resubmit.

### Engineering quality and reliability

- Isolated operations on the shared SQLite archive connection and enabled foreign key checks.
- Shell-language incremental reuse requires a matching recorded language identity. Older unidentified archives remain readable and require a verified baseline before reuse.
- The Probably Stolen glossary can be browsed and edited independently. The game translation adapter is still pending.
- The Surviving Mars glossary remains a separate download at resource version `2026.10.08.1`.
- Steam Workshop upload remains a beta feature.
