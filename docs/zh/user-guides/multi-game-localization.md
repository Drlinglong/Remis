# Project Zomboid 与 RimWorld 本地化

Remis 桌面 Help Copilot 可以引导用户并展示初次翻译计划供用户审批；增量更新请使用项目界面或 Remis Agent API 的 `workflow: "incremental"`。Project Zomboid 和 RimWorld 会生成独立本地化 Mod。源 Mod 保持只读；每个目标语言会生成自己的可安装子目录。导出预览用于查看现有本地输出，安装时由玩家按游戏说明手动放入 Mod 目录。Remis 不会替这些游戏执行 Paradox 部署，也没有在游戏运行时验证输出。

源语言由项目或用户选择决定，不要求必须是英语。

## 已识别的格式

- **Project Zomboid**：JSON 字符串映射，以及受限的纯字面量 Lua 表 TXT。
- **RimWorld**：`Keyed`、`DefInjected`、`Strings`、已知规则覆盖的 Def 可翻译字段和 `rulesStrings`。
- **Surviving Mars: Relaunched**：沿用现有 ModItemLocTable CSV 初次翻译、增量更新和校对流程；本轮不生成独立翻译 Mod。

适配器只处理已识别的资源和字段。未知 JSON/Lua 结构、RimWorld 未知 Def 字段、继承、补丁操作、条件依赖、程序集或运行时动态生成文本可能无法离线解析，会作为诊断或人工复核项显示。不要把未显示的内容理解为已翻译。

## 更新与复核

增量更新按条目比较原文；Mod 版本或目录路径单独变化不代表所有条目都需要重译。原文发生变化时，Remis 会保留已有人工译文并要求复核。`needs_review` 项在人工处理前不能当作已确认译文。增量流程当前不支持从 checkpoint 恢复；需要新建增量计划重新检查当前源内容。dry-run 只检查就绪情况，不会执行增量差异或写出译文。

多语言输出保存在各自独立的语言子目录中。检查每个目录里的包清单和语言标识，避免把某种语言的包安装到另一种语言目录。

## 手动安装边界

对 Project Zomboid 和 RimWorld，导出预览只列出 Remis 已生成、清单和资源记录有效的本地包，并标为 `manual_install`。`validation_scope: artifact_presence_only` 只表示产物存在检查，不代表游戏运行时已验证。预览不会复制到游戏目录；以明确批准方式调用 `approve-export` 会返回 `409 unsupported_game_deployment`，不会部署这些游戏的包。查看预览后，按对应游戏的 Mod 安装方式手动安装。Surviving Mars 预览只列出通过 CSV 表头和结构解析的本地产物，不代表游戏加载已验证或可以自动部署。

格式支持表示 Remis 能识别并处理列出的本地化资源，不表示游戏已加载验证。需要确认覆盖顺序、条件加载或运行时行为时，请在备份和隔离的测试 Mod 上进行游戏内检查。
