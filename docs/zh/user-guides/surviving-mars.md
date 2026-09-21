# 火星求生重制版本地化

Remis 现在可以把 Surviving Mars / Relaunched 的 `ModItemLocTable` CSV 当作普通翻译项目处理。创建项目时，游戏选择“Surviving Mars / Relaunched（火星求生重制版）”，之后沿用现有的源语言、目标语言、翻译、校验和增量更新流程。

## 支持的文件

Remis 只会自动发现表头完全匹配下面五列的 `.csv` 文件：

```text
ID,Text,Translation,VoiceActor,Context
```

- `ID` 会按不透明字符串保留，不能改名、重排或重复。
- `Text` 是源文本，`Translation` 是唯一写回列。
- `VoiceActor` 和 `Context` 原样保留。
- 包含逗号、引号、换行或火星游戏标签的字段会按标准 CSV 解析，不使用字符串切分。
- 普通 CSV 文件会被忽略，不会误当作翻译表。

火星文本中的 `<em>`、`<resource(res)>`、`<image UI/... 2000>` 等标签必须在译文中保持精确一致，包括参数、大小写和数量；标签内部的可见文本仍然可以翻译。标签缺失或新增会在最终校验中报错并进入人工复核。

## 输出和游戏使用

输出会保留 CSV 相对于项目根目录的路径和原文件名，不会创建 Paradox 风格的 `l_english` 目录或重命名文件。输出文件使用 UTF-8，并且只写入第三列 `Translation`。

游戏 ModItem 的 `Filename` 指向这个 CSV，`Language` 决定它在哪个游戏语言下加载。若使用游戏尚未支持的语言制作汉化表，按官方 ModTools 文档将 `Language` 设为 English，并在游戏中运行 English；Remis 不会替用户自动修改 ModItem、创建 Lua 或上传 Workshop。

## 如果手上的 Mod 是 Workshop 压缩包

Steam Workshop 和游戏的 `PdxMods` 缓存通常只留下 `ModContent.fpk`，它是已编译的 Mod 包，Remis 不能直接把它当作 CSV 源目录读取。需要先在官方 Mod Editor 中把它复制/解包到可编辑的 `AppData/Mods/<Mod 名称>` 目录，再把可读的 Mod 源目录交给 Remis。

在本地 Mod Editor/游戏中测试解包目录时，不必先重新打包；确认 `Game.csv`、ModItem 的 `Filename`、`Language` 和加载顺序都正确后即可测试。若要交给 Workshop 或按正式压缩 Mod 使用，则需要用官方 Mod Editor 的 Pack Mod 动作重新生成 `ModContent.fpk`。请对副本操作，不要覆盖 Workshop 缓存；Remis 当前不自动执行解包、打包或发布。

## 已知边界

当前实现覆盖 CSV 发现、初次翻译、增量快照/写回、人工校对、格式校验和问题导出；它不会读取或修改游戏安装文件，也不会替用户完成 ModItem 创建、字体处理、部署或 Workshop 发布。提交到游戏前应在本机用 ModTools/游戏实际加载一次输出表，确认 Filename、Language 和 Mod 加载顺序。
