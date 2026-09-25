# 多游戏 Mod 本地化

Remis 桌面 Help Copilot 可以引导用户并展示初次翻译计划供用户审批；增量更新请使用项目界面或 Remis Agent API 的 `workflow: "incremental"`。Project Zomboid 和 RimWorld 会生成独立本地化 Mod。Surviving Mars / Relaunched 还支持从原始 Workshop `ModContent.fpk` 开始的隔离准备、英文源文翻译和多语言本地交付。按[火星求生重制版指南](surviving-mars.md)完成准备、选择 `text_only` 或 `source_copy`、安装与手动发布；Help Copilot 可以解释步骤，内置 Agent/Codex 可按该指南和 [Remis Agent Skill](../../../.agents/skills/remis-agent/SKILL.md) 操作，但聊天说明本身不会执行或导出。所有输出都需玩家在游戏中验收，且不自动安装或上传 Workshop。

普通资源项目的源语言由项目或用户选择决定；火星 FPK 准备流程当前提取英文源文，以返回的 `source_language` 为准。

## 已识别的格式

- **Project Zomboid**：JSON 字符串映射，以及受限的纯字面量 Lua 表 TXT。
- **RimWorld**：`Keyed`、`DefInjected`、`Strings`、已知规则覆盖的 Def 可翻译字段和 `rulesStrings`。
- **Surviving Mars: Relaunched**：沿用 ModItemLocTable CSV 初次翻译和增量流程；可从原始 Workshop FPK 隔离准备项目，并生成只含语言表、依赖原 Mod 的 `text_only` 包，或包含全部资源的 `source_copy`。完整流程和当前校对边界见[专属指南](surviving-mars.md)。

适配器只处理已识别的资源和字段。未知 JSON/Lua 结构、RimWorld 未知 Def 字段、继承、补丁操作、条件依赖、程序集或运行时动态生成文本可能无法离线解析，会作为诊断或人工复核项显示。不要把未显示的内容理解为已翻译。

## 更新与复核

增量更新按条目比较原文；Mod 版本或目录路径单独变化不代表所有条目都需要重译。原文发生变化时，Remis 会保留已有人工译文并要求复核。`needs_review` 项在人工处理前不能当作已确认译文。增量流程当前不支持从 checkpoint 恢复；需要新建增量计划重新检查当前源内容。dry-run 只检查就绪情况，不会执行增量差异或写出译文。

Project Zomboid、RimWorld 的多语言输出各自形成语言包。火星 FPK 项目按语言保留译文工作目录，在导出时选中多个输出，合并为一个多语言 Mod 包；只安装返回的包目录，不能把语言工作目录当作独立 Mod 安装。

## 手动安装边界

对 Project Zomboid 和 RimWorld，导出预览只列出 Remis 已生成、清单和资源记录有效的本地包，并标为 `manual_install`。`validation_scope: artifact_presence_only` 只表示产物存在检查，不代表游戏运行时已验证。预览不会复制到游戏目录；以明确批准方式调用 `approve-export` 会返回 `409 unsupported_game_deployment`，不会部署这些游戏的包。Surviving Mars 的普通 CSV 流程仍提供格式校验；专用可视化校对工作区尚未接入此新流程，Agent API 可按条目读取并在审批后定点保存译文。FPK 工作流的本地交付可选只含已完成语言 CSV 且依赖原 Mod 的 `text_only`，或含完整资源的 `source_copy`；多语言交付可在一次导出中选择各已完成语言输出。两种模式均先预览并审批，只写本地包，不覆盖、不安装、不发布；完整步骤和 `%APPDATA%/Surviving Mars Relaunched/Mods/<output_mod_id>` 安装结构见[火星专属指南](surviving-mars.md)。

格式支持表示 Remis 能识别并处理列出的本地化资源，不表示游戏已加载验证。需要确认覆盖顺序、条件加载或运行时行为时，请在备份和隔离的测试 Mod 上进行游戏内检查。
