# Project Remis v3.0.4 Pre-release

## English

## Pre-release Notice

`v3.0.4` is published as a pre-release for smoke testing. It supersedes the withdrawn `v3.0.3` release notes and includes both the `v3.0.3` release-hardening work and the follow-up `v3.0.4` audit fixes.

The main reason this is marked pre-release is safety: the previous `v3.0.3` candidate did not yet include the stricter delete-operation guardrails that are now included here. Please smoke test this build before treating it as the stable 3.0.x baseline.

## Highlights

- Added structural safety checks before destructive project cleanup/deploy operations. Cleanup targets must now look like real Paradox mod folders with `localization/` or `localisation/` content instead of accepting arbitrary directories.
- Fixed Vic3 demo localization syntax and validator behavior so Vic3 color tags use the correct `#...#!` style rather than HOI-style `§...§!`.
- Hardened incremental translation follow-ups and added regression coverage for project import and incremental translation behavior.
- Fixed Agent Workshop scans so repair runs target translation-side files while still showing source-mod context clearly.
- Fixed batch repair prompts so the agent respects the archived target language instead of applying English-specific punctuation rules to non-English targets.
- Surfaced Agent Workshop retry/reflection telemetry in the execution log, including attempt counts, diagnostic reflection use, fixed counts, and remaining issues.
- Added a project metadata repair action for checking/rebuilding project-side metadata and caches after project schema or database changes.
- Improved metadata repair notifications so success/failure messages state what changed, which metadata files were updated, and whether warnings were produced.
- Expanded locale consistency coverage and cleaned up several incorrect or hardcoded UI strings across non-English locales.
- Kept the deploy/refactor cleanup from the withdrawn 3.0.3 candidate while preserving the safer cleanup boundary added in this release.

## Notes for Testers

- This release is intended for smoke testing the 3.0.4 branch before a stable release.
- Please pay special attention to deploy cleanup, fake-localization cleanup, Agent Workshop scan/fix flows, project metadata repair, and existing project migration behavior.
- The Windows installer is `remis-mod-factory_3.0.4_x64-setup.exe`.

## 中文

## Pre-release 提示

`v3.0.4` 先作为预发布版本发布，用于冒烟测试。它合并了已撤回的 `v3.0.3` release note 内容，以及后续 `v3.0.4` 审计修复。

这次先标为 pre-release 的主要原因是安全性：之前的 `v3.0.3` 候选版本还没有包含更严格的删除操作安全护栏。现在这些护栏已经补上，但仍建议先完成冒烟测试，再把它视为稳定的 3.0.x 基线版本。

## 重点更新

- 为项目清理/部署前的破坏性操作增加结构性安全检查。清理目标现在必须像一个真实的 Paradox mod 目录，并包含 `localization/` 或 `localisation/` 内容，不再接受任意普通目录。
- 修复 Vic3 演示本地化语法与校验器行为：Vic3 示例现在使用正确的 `#...#!` 颜色标签，而不是 HOI 风格的 `§...§!`。
- 加固增量翻译重构后的边角问题，并补充项目导入与增量翻译相关回归测试。
- 修复智能工坊扫描逻辑：修复操作现在面向翻译 mod 文件，同时仍然清楚展示源 mod 上下文。
- 修复批量修复 prompt 的目标语言处理，避免对非英文目标语言错误套用英文标点规则。
- 智能工坊执行日志现在会显示重试/反思过程，包括第几轮尝试、是否使用 diagnostic reflection、修复数量和剩余问题数。
- 在项目概览中新增项目元数据检验/重建操作，用于数据库逻辑或项目侧缓存结构升级后的自检和修复。
- 优化元数据修复通知：成功/失败都会明确说明结果、哪些元数据文件被更新、是否存在警告。
- 扩展 I18N 一致性测试，并清理多个非英文语言文件中的错误翻译或硬编码文本。
- 保留已撤回 3.0.3 候选版本中的部署/重构清理工作，同时补齐本版本新增的更安全清理边界。

## 测试说明

- 这个版本用于对 `3.0.4` 分支进行冒烟测试，暂不标为稳定版。
- 请重点测试部署清理、假本地化清理、智能工坊扫描/修复流程、项目元数据修复，以及旧项目迁移后的行为。
- Windows 安装包为：`remis-mod-factory_3.0.4_x64-setup.exe`。
