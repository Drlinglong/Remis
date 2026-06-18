# Project Remis v3.0.5

## English

## Highlights

- Project Tracking is now available for the first time. You can add a local mod folder, link it to the matching Remis translation project, and let Remis watch that folder for localization file changes.
- Tracked folders are designed for real mod workflows, including Steam Workshop paths such as `SteamLibrary\steamapps\workshop\content\game_id\workshop_item_id`.
- When Remis detects changed localization files, the project can jump directly into incremental translation so you can refresh only the content that changed.
- Scheduled scanning can now be enabled per tracked project, with minute, hour, and day intervals.
- The add-tracking window now explains what each field means, including the monitored path, the linked Remis project, and what scheduled scanning does while Remis is running.
- Remis only monitors tracked folders. It does not modify or delete files in the watched mod directory.
- Project Tracking ships with 11-language UI support and first-run guidance. This is the first public release of the feature, and feedback is very welcome.

## Stability And Safety

- The unfinished Neologism Tribunal feature is hidden again while it waits for more testing.
- Release-time I18N validation now checks that every translation leaf key is populated across all 11 supported languages and catches duplicate localized values outside explicit technical exceptions.
- The most urgent duplicate-value I18N debt was fixed for the home page, forms, common buttons, settings/API settings, navigation/page titles, and glossary strings.
- Remaining duplicate-value I18N exceptions are tracked separately in GitHub issue #146 so technical constants stay visible and real localization debt can be paid down module by module.
- Incremental translation, initial translation, project management, and archive handling include additional hardening and test coverage from the 3.0.5 branch.

## Installer

- Windows installer: `remis-mod-factory_3.0.5_x64-setup.exe`

## 中文

## 重点更新

- “项目追踪”功能首次上线。你可以添加本地 mod 文件夹，把它关联到 Remis 内对应的翻译项目，并让 Remis 持续关注该文件夹里的本地化文件变化。
- 追踪路径面向真实 mod 工作流设计，包括 Steam 创意工坊路径，例如 `SteamLibrary\steamapps\workshop\content\游戏ID\创意工坊物品ID`。
- 当 Remis 检测到本地化文件发生变化后，可以直接跳转到增量更新页面，只刷新发生变化的内容。
- 每个追踪项目都可以单独启用定时扫描，并支持分钟、小时、天作为扫描间隔单位。
- “添加需要追踪的新项目”窗口现在会解释每个字段的含义，包括被监控路径、关联的 Remis 项目，以及 Remis 运行期间定时扫描会做什么。
- Remis 只会监控被追踪的文件夹，不会修改或删除该 mod 文件夹中的任何文件。
- 项目追踪已经补齐 11 语种界面文案和新手引导。这是该功能第一次公开上线，欢迎反馈使用中的问题和改进建议。

## 稳定性与安全性

- 尚未充分测试的“新词审判庭”功能已重新隐藏，等待后续打磨。
- 发布前 I18N 校验现在会检查所有 leaf key 是否在 11 个支持语言中都有值，并在明确技术例外之外拦截重复的本地化值。
- 已优先修复首页、表单、通用按钮、设置页 / API 设置、导航 / 页面标题、术语表中的紧急重复值 I18N 技术债。
- 剩余重复值 I18N 豁免已经记录到 GitHub issue #146，区分技术常量、专有名词与需要逐步偿还的真实技术债。
- 3.0.5 分支还包含增量翻译、初始翻译、项目管理、归档处理相关的稳定性加固和测试覆盖。

## 安装包

- Windows 安装包：`remis-mod-factory_3.0.5_x64-setup.exe`
