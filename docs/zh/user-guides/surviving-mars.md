# 火星求生重制版本地化

Remis 支持 Surviving Mars / Relaunched 现有的 `ModItemLocTable` CSV 初次翻译、增量更新和校对流程，也可以从已有的项目翻译输出生成一个只包含本地化表的独立翻译 Mod。创建项目时，游戏选择“Surviving Mars / Relaunched（火星求生重制版）”。

Remis 桌面聊天助手当前可以引导初次翻译并展示计划供你审批。增量更新请在项目界面操作，或使用 Remis Agent API 并将 `workflow` 设为 `incremental`。聊天助手可以解释独立翻译 Mod 导出，但不会替你调用导出接口。Codex 用户可按仓库中的 [Remis Agent Skill](../../../.agents/skills/remis-agent/SKILL.md) 和 [API 技术参考](../../../.agents/skills/remis-agent/references/api-workflow.md) 操作；以能力接口和本次扫描返回的 `game_support` 为准。

## 支持的文件

Remis 只会自动发现表头完全匹配下面五列的 `.csv` 文件：

```text
ID,Text,Translation,VoiceActor,Context
```

官方 Mod Editor 导出的文件可以在表头前有一行 `sep=,`；Remis 会识别并保留它。
可直接复制导入 `%APPDATA%/Surviving Mars Relaunched/Mods/<Mod 名称>` 中的可编辑 Mod，
该路径支持不开放 AppData 下其他应用目录。

- `ID` 必须是 ASCII 十进制数字，并作为字符串保留精确身份，包括前导零；不能改名、重排或重复。
- `Text` 是源文本，`Translation` 是唯一写回列。
- `VoiceActor` 和 `Context` 原样保留。
- 包含逗号、引号、换行或火星游戏标签的字段会按标准 CSV 解析，不使用字符串切分。
- 普通 CSV 文件会被忽略，不会误当作翻译表。

火星文本中的 `<em>`、`<resource(res)>`、`<image UI/... 2000>` 等标签必须在译文中保持精确一致，包括拼写、参数、大小写和数量。标签与标签之间的正文可以翻译；尖括号内部的标签名称和参数不可翻译或改写。标签缺失或新增会在最终校验中报错并进入人工复核。

## 输出和游戏使用

段落换行必须保存为 CSV 单元格内的真实换行，不能写成反斜杠和字母 n 组成的 `\n`。
Remis 按火星格式还原换行，并检查原文与译文的分段结构；丢失分段或新增字面换行转义会阻断独立包导出。
原文中有意使用的字面 `\n` 不会被全局替换；这种文本与真正的换行分别处理。

输出会保留 CSV 相对于项目根目录的路径和原文件名，不会创建 Paradox 风格的 `l_english` 目录或重命名文件。输出文件使用 UTF-8，并且只写入第三列 `Translation`。

在原 Mod 中，ModItem 的 `Filename` 指向 CSV，`Language` 决定它在哪个游戏语言下加载。若使用游戏尚未支持的语言制作汉化表，按官方 ModTools 文档在原 ModItem 中手动将 `Language` 设为 English，并在游戏中运行 English。这是游戏侧设置，不是 Agent 的 `custom_lang_config` 套壳能力。Remis 不修改原 Mod；独立翻译包会在自己的包目录生成注册文件和 `ModItemLocTable`，不会上传 Workshop。

## 从现有译文生成独立翻译 Mod

独立包以已经生成的某个目标语言 CSV 输出为输入，不会再次翻译内容，也不会复制原 Mod 的脚本、图片或其他资产。使用项目页面对应的本地导出操作，或按 API 参考调用：

1. 每个新工作流先调用 preflight，再读取 `GET /api/agent/projects/{project_id}/translation-package/options`。从 `translation_outputs` 选择已有输出目录，从 `languages` 选择目标语言；`game_language` 是 ModItem 要用的游戏语言 token。
2. 调用 `POST /api/agent/projects/{project_id}/translation-package/plan` 创建预览。检查项目、所选译文、目标语言、包内容和风险字段。它明确不调用付费 API、不覆盖已有包，也不写入游戏目录。
3. 把具体预览交给用户并取得明确批准后，才调用 `POST /api/agent/projects/{project_id}/translation-package`，传入该 `plan_id` 和 `approved: true`。结果给出本地包路径、文件清单和手动安装说明，`runtime_verified` 仍为 `false`。

CSV 文件保留所选输出中的相对目录和文件名；包内 `metadata.loctables` 与 `items.lua` 使用 SDK 虚拟资源路径 `Mod/<生成包ID>/Localization/...` 登记该 CSV，而不是裸文件路径。包在自己的目录生成 `metadata.lua` 和含 `ModItemLocTable` 的 `items.lua`，并把原 Mod 声明为必需的 `ModDependency`；依赖版本的 major/minor 默认值保持 `0`。安装步骤：将返回的整个包目录复制到 `%APPDATA%/Surviving Mars Relaunched/Mods`，在启动器中同时启用原 Mod 和翻译 Mod，然后在游戏中选择对应目标语言。包不复制原 Mod 资产，不修改原 Mod，也不写入硬编码绝对路径。简体中文的 Remis 语言代码 `zh-CN` 对应 SDK 的 `Schinese` token；始终使用 options 返回的 `game_language`，不要把显示名称当作 token。若 plan 的 `warnings` 提示本机没有对应语言包，token 可识别不代表该游戏安装包含此语言包。

本机 Relaunched SDK 的 `ModItemLocTable.md.html` 说明表格使用 CSV 第三列提供译文、以 UTF-8 保存，并通过 `Filename` 和 `Language` 加载；`Mod.lua` 的 `UpdateLocTables` 与 `ModsLoadLocTables` 展示表格注册和按 Mod 加载顺序读取；`ModItem.lua` 提供语言枚举，`localization.lua` 将 `zh-CN` 映射到 `Schinese`。SDK 的 `ModDependency` 默认 `required=true`、major/minor 版本为 `0`。Remis 按这些本地 SDK 契约生成轻量包，但尚未在游戏中验证加载成功。

## 如果手上的 Mod 是 Workshop 压缩包

Steam Workshop 和游戏的 `PdxMods` 缓存通常只留下 `ModContent.fpk`，它是已编译的 Mod 包，Remis 不能直接把它当作 CSV 源目录读取。需要先在官方 Mod Editor 中把它复制/解包到可编辑的 `AppData/Mods/<Mod 名称>` 目录，再把可读的 Mod 源目录交给 Remis。

需要使用压缩 Mod 时，请用官方 Mod Editor 的 Pack Mod 动作生成 `ModContent.fpk`。请对副本操作，不要覆盖 Workshop 缓存；Remis 当前不自动执行解包、打包或发布。游戏内验收时需确认 ModItem `Filename`、`Language` 和加载顺序与目标设置相符；Remis 的扫描不验证游戏实际加载行为。

## 已知边界

当前实现覆盖 CSV 发现、初次翻译、增量快照/写回、人工校对、格式校验和问题导出；独立包只为已有译文生成自己的 ModItem 与注册文件，不覆盖原 Mod，不处理字体、部署或 Workshop 发布。硬编码 `Untranslated(...)` 内容不在 CSV 扫描覆盖范围内。动态支持扫描报告识别到的资源与条目数、覆盖范围、诊断和 `runtime_verified: false`；没有可用 CSV 或表结构无效时会阻断普通翻译计划，dry-run 仍可用于查看诊断。安装后请在游戏内检查语言、ModItem 文件引用和加载顺序；Remis 未验证运行时加载。
