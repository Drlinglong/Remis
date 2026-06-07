# Project Remis v3.0.4

## English

## Highlights

- Expanded the application UI from 3 supported languages to full 11-language support: English, Simplified Chinese, German, Spanish, French, Japanese, Korean, Polish, Brazilian Portuguese, Russian, and Turkish.
- Added structural safety checks before destructive cleanup operations. Fake-localization cleanup now only proceeds when the target looks like a Paradox mod folder with `localization/` or `localisation/` content.
- Improved the fake-localization cleanup window with a clearer three-action flow: cancel, auto-detect the original mod path from project/workshop metadata, or delete fake-localization files under the selected path.
- Added a native folder picker for the original mod directory and improved long path display in the cleanup window.
- Fixed Agent Workshop scan context so repairs target translated mod files while still preserving source-mod context for comparison.
- Fixed warning handling so format warnings are included in the repair pipeline instead of only sending hard errors.
- Removed misleading pre-write validation noise from the initial translation workflow. The final written file is now the authoritative validation target.
- Fixed archive/path lookup inconsistencies that could produce `[DB_MISSING]` placeholders during proofreading after initial translation.
- Added project metadata inspection/rebuild from project management, with clearer success/failure notifications that list what was rebuilt or updated.
- Fixed Victoria 3 demo localization color tags and validator behavior for supported Vic3 formatting commands.
- Kept the withdrawn `v3.0.3` hardening work and shipped it together with the follow-up `v3.0.4` audit fixes.

## Stability And Safety

- Cleanup and deploy paths are now guarded against obvious non-mod folders such as system directories or ordinary document folders.
- Workshop paths no longer require enumerating individual mod IDs; the application validates the directory structure instead.
- Agent Workshop retry/reflection logs now expose attempt counts, diagnostic reflection usage, fixed counts, and remaining issue counts more clearly.
- Translation-side validation now uses source-file context consistently across post-processing, project proofreading, and Agent Workshop rescans.

## Installer

- Windows installer: `remis-mod-factory_3.0.4_x64-setup.exe`

## 中文

## 重点更新

- 应用界面从原来的 3 种语言扩展为完整 11 语支持：英语、简体中文、德语、西班牙语、法语、日语、韩语、波兰语、巴西葡萄牙语、俄语、土耳其语。
- 为破坏性清理操作增加结构性安全检查。假本地化清理现在只会在目标目录看起来像 Paradox mod，并包含 `localization/` 或 `localisation/` 内容时执行。
- 优化“清理假本地化”窗口，改为更清晰的三步操作：取消、从项目/工坊元数据自动探测原始模组路径、删除所选路径下的假本地化文件。
- 原始模组目录现在支持系统目录选择器，并改善了长路径显示。
- 修复智能工坊扫描上下文：修复操作现在面向翻译 mod 文件，同时保留源 mod 上下文用于对照。
- 修复格式警告处理逻辑，warning 也会进入智能工坊修复流程，不再只处理 error。
- 移除初次翻译流程中具有误导性的写入前校验噪声。现在以最终写入文件作为权威校验对象。
- 修复初次翻译后归档路径与查库路径不一致的问题，避免校对阶段产生 `[DB_MISSING]` 占位文本。
- 在项目管理中加入项目元数据检查/重建能力，并优化通知内容，明确说明哪些缓存或元数据被重建/更新。
- 修复 Victoria 3 demo 本地化颜色标签，并校正 Vic3 支持的格式命令校验行为。
- 合并已撤回的 `v3.0.3` 加固内容与后续 `v3.0.4` 审计修复，作为稳定版发布。

## 稳定性与安全性

- 清理与部署路径现在会拒绝明显不是 mod 的目录，例如系统目录或普通文档目录。
- 工坊路径不需要维护具体 mod ID 列表；应用会改为验证目录结构是否符合 Paradox mod 形态。
- 智能工坊日志现在更清楚地显示重试次数、是否使用 diagnostic reflection、修复数量与剩余问题数。
- 翻译侧格式校验现在在后处理、项目校对、智能工坊重新扫描中统一使用源文件上下文。

## 安装包

- Windows 安装包：`remis-mod-factory_3.0.4_x64-setup.exe`
