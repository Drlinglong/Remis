# 火星求生重制版本地化

Remis 支持 Surviving Mars / Relaunched 现有的 `ModItemLocTable` CSV 初次翻译、增量更新和校对流程。创建项目时，游戏选择“Surviving Mars / Relaunched（火星求生重制版）”。它沿用项目中的源语言、目标语言与翻译流程；不会新建独立翻译 Mod。

Remis 桌面聊天助手当前可以引导初次翻译并展示计划供你审批。增量更新请在项目界面操作，或使用 Remis Agent API 并将 `workflow` 设为 `incremental`。Codex 用户可按仓库中的 [Remis Agent Skill](../../../.agents/skills/remis-agent/SKILL.md) 和 [API 技术参考](../../../.agents/skills/remis-agent/references/api-workflow.md) 操作；以能力接口和本次扫描返回的 `game_support` 为准。

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

输出会保留 CSV 相对于项目根目录的路径和原文件名，不会创建 Paradox 风格的 `l_english` 目录或重命名文件。输出文件使用 UTF-8，并且只写入第三列 `Translation`。

游戏 ModItem 的 `Filename` 指向这个 CSV，`Language` 决定它在哪个游戏语言下加载。若使用游戏尚未支持的语言制作汉化表，按官方 ModTools 文档在 ModItem 中手动将 `Language` 设为 English，并在游戏中运行 English。这是游戏侧设置，不是 Agent 的 `custom_lang_config` 套壳能力；Remis 不会替用户自动修改 ModItem、创建 Lua 或上传 Workshop。

## 如果手上的 Mod 是 Workshop 压缩包

Steam Workshop 和游戏的 `PdxMods` 缓存通常只留下 `ModContent.fpk`，它是已编译的 Mod 包，Remis 不能直接把它当作 CSV 源目录读取。需要先在官方 Mod Editor 中把它复制/解包到可编辑的 `AppData/Mods/<Mod 名称>` 目录，再把可读的 Mod 源目录交给 Remis。

需要使用压缩 Mod 时，请用官方 Mod Editor 的 Pack Mod 动作生成 `ModContent.fpk`。请对副本操作，不要覆盖 Workshop 缓存；Remis 当前不自动执行解包、打包或发布。游戏内验收时需确认 ModItem `Filename`、`Language` 和加载顺序与目标设置相符；Remis 的扫描不验证游戏实际加载行为。

## 已知边界

当前实现覆盖 CSV 发现、初次翻译、增量快照/写回、人工校对、格式校验和问题导出；它不会读取或修改游戏安装文件，也不会替用户完成 ModItem 创建、字体处理、部署或 Workshop 发布。动态支持扫描报告识别到的资源与条目数、覆盖范围、诊断和 `runtime_verified: false`；没有可用 CSV 或表结构无效时会阻断普通翻译计划，dry-run 仍可用于查看诊断。
