# 火星求生重制版本地化

Remis 支持 Surviving Mars / Relaunched 的 `ModItemLocTable` CSV 初次翻译和增量更新，也可以从原始 Workshop 包准备可翻译项目，再将多个语言输出合并到一个本地交付包。创建项目时选择“Surviving Mars / Relaunched（火星求生重制版）”。本指南的安装路径适用于 Relaunched；不要直接套用到旧版游戏。

Remis 桌面聊天助手可以解释步骤、引导初次翻译并展示计划供你审批；聊天回答本身不会执行准备、翻译或导出。增量更新请在项目界面操作，或使用 Remis Agent API 并将 `workflow` 设为 `incremental`。当前此游戏的项目界面尚无专用可视化校对工作区；已有格式校验，Agent API 可读取译文并在审批及修订校验后定点保存。内置 Agent/Codex 用户可按仓库中的 [Remis Agent Skill](../../../.agents/skills/remis-agent/SKILL.md)、[API 技术参考](../../../.agents/skills/remis-agent/references/api-workflow.md)和本指南操作；以能力接口和本次扫描返回的 `game_support` 为准。

## 从工坊 Mod 开始：手动操作顺序

1. 在 Steam 订阅并下载**原作者的 Mod**。找到它的 `ModContent.fpk`，通常位于所选 Steam 库的 `steamapps/workshop/content/<游戏 AppID>/<原 Mod 工坊 ID>/`。Remis 选择的是本地文件，不是网页链接，也不是你已经发布的翻译副本。
2. 打开**项目管理 → 创建新项目**，填写名称并选择火星求生。在随后的独立准备窗口中浏览或粘贴 FPK 路径。Remis 在隔离工作目录解包和检查，不需要先去编辑器手动导出 CSV 或 Lua。
3. 检查文本候选，选择**只准备文本**或**完整国际化副本**。有硬编码文本时推荐完整副本；复核候选后批准准备。成功后会创建可翻译项目。已有准备项目应继续使用该项目。
4. 进入**初次翻译**，选这个项目、英文源语言、所需目标语言以及 provider/model，再审批翻译。已有项目的新版本改走增量流程；不必为了增加法语、德语另建一份 Mod。
5. 完成后回到项目的**国际化 Mod 导出**，同时选中所需语言输出，例如 `zh-CN-prepared`、`fr-prepared`、`de-prepared`。预览通过后生成**一个多语言 Mod 包**。工作目录保留供后续维护，安装使用返回的导出包目录。
6. 把导出包内容放进 `%APPDATA%/Surviving Mars Relaunched/Mods/<output_mod_id>/`，确保 `metadata.lua` 直接在此目录。文本包与原 Mod 同时启用；完整副本单独启用，并停用原 Mod、旧翻译补丁。在游戏中选择目标语言并重启检查。
7. 如需发布，用**游戏自带 Mod Editor 手动打包/上传**。首次发布取得自己的 Workshop ID 后，在 Remis 的完整副本项目中绑定它；以后导出保留此 ID，再用编辑器更新同一条目。Remis 目前不会自动上传。

如果希望 Agent 操作：内置聊天助手先引导完成 FPK 准备界面，之后可为已创建项目规划初次翻译；Codex 按下方 Skill/API 参考调用准备、翻译与导出接口。安装与编辑器上传步骤仍需明确处理，不能把一次聊天答复当作已执行。

## 支持的文件

Remis 只会自动发现表头完全匹配下面五列的 `.csv` 文件：

火星求生当前工作流恰好支持九种目标语言：简体中文（`zh-CN`）、英语（`en`）、法语（`fr`）、德语（`de`）、西班牙语（西班牙，`es`）、波兰语（`pl`）、葡萄牙语（巴西，`pt-BR`）、俄语（`ru`）和土耳其语（`tr`）。其他游戏仍使用各自的语言目录。

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

在“创建项目”中选择“Surviving Mars / Relaunched”，然后在单独的 FPK 准备窗口中选择原始 `ModContent.fpk`。Remis 会先说明两种准备方式，再检查资源包和文本；它只在隔离目录中读取经过支持的 FLPK v1 归档，原包和 Workshop/PdxMods 缓存保持不变。

检查结果后选择准备方式：

- **只准备文本（`text_only`）**：只生成可翻译 CSV，不改写 Lua；原 Mod 仍是必需依赖。需要保留原 Mod ID、存档关联，或暂时不想制作替代 Mod 时选此项。待复核的文本不会进入翻译 CSV，也不会在交付时被改写。
- **完整国际化副本（`source_copy`，默认并推荐）**：准备全部资源，并将经审核的硬编码文本改为稳定 ID 的本地化调用；译文仍通过各语言 CSV 提供。硬编码文本不能靠 CSV-only 补丁覆盖时，优先选完整副本。导出时生成新的 Mod ID，并在游戏中以 `[Remis i18n]` 标记标题；停用原 Mod 和旧汉化补丁，只启用副本。

确认候选后再批准准备。未知别名、复杂动态表达式、内部选项值及扫描盲区仍需人工处理；候选数不是完整覆盖证明。后续沿用普通英文源文 CSV 翻译流程。保留准备记录编号，未来更新 Mod 时使用它匹配已有稳定 ID。翻译完成后，在项目的国际化 Mod 导出中选择目标语言，先查看预览，再批准生成新的本地目录。

导出时有两种用户模式：完整源副本会携带原 Mod 全部资源并替代原 Mod；只含文本的翻译包只带语言 CSV 并依赖原 Mod。运行时覆盖属于高级 API 配置，不是常规用户选项。两种交付都不会自动安装、覆盖已有包或发布；按预览说明手动安装，并在游戏内检查建筑升级、事件、科技和设置文字。

一个多语言 Mod 可在一次国际化 Mod 导出中选择全部已完成的语言输出，例如 `zh-CN`、`fr`、`de`，并在同一个包中交付。`fr-prepared`、`de-prepared` 等准备输出是持久的翻译工作文件；它们不是 `installedMods`，也不是可删除的临时目录。先在游戏自带 Mod Editor 中手动发布完整副本，取得你自己的 Workshop 条目 ID 后，再在 Remis 项目管理的“国际化 Mod 导出”中绑定该 ID。下一次导出会携带此 ID，用 Mod Editor 再次上传即可更新同一条目；不要绑定原作者 ID。Remis 不自动上传。已绑定 ID 当前不能在此面板更换或清除。

同一个源 Mod 请复用一个 Remis 项目来维护新增语言和发布身份：把新语言输出加入该项目，再一次导出多语言包。完整副本的游戏内 Mod ID 对同一源 Mod 保持稳定；重新创建项目不会生成另一个游戏内身份，而且新项目有独立的发布绑定。不要用重复项目制作或发布同一源 Mod 的“第二个副本”，以免出现相同游戏内 Mod ID、但发布身份分开的包。

**交付模式对照：**

| 模式 | 包含内容 | 游戏中启用方式 |
|---|---|---|
| `text_only` | 已完成语言 CSV；依赖原 Mod | 同时启用原 Mod 与本翻译包；停用旧汉化补丁以免冲突 |
| `source_copy` | 全部原 Mod 资源、受支持且已审核的源码改写、所选语言 CSV；新的输出 Mod ID | 停用原 Mod 和旧汉化补丁，只启用完整副本 |

把预览确认后的整个导出目录放到 `%APPDATA%/Surviving Mars Relaunched/Mods/<output_mod_id>`，确保 `metadata.lua` 直接位于 `<output_mod_id>` 目录下，不要多套一层同名目录。启动器启用所需 Mod 后，在游戏中逐项检查文本与存档行为。已报告中文、法语和德语样例正常，并确认手动上传更新了同一个 Workshop 条目；这不是对所有文本或存档的全面验收。

Agent API 用户可为完整源副本保存项目级本地 Workshop ID：先读取 `GET /api/agent/projects/{project_id}/mars-pipeline/publication`，再将返回的 `revision` 带入同一路径的 `PUT` 请求。该绑定只用于完整源副本；Remis 不验证账号所有权、不上传文件，也不发布到 Workshop。保存前请确认 ID 属于你自己已发布的副本。此 API 不支持静默替换或清除绑定。

绑定状态进入导出预览指纹；预览后发生绑定变化，必须重新预览。损坏记录或不匹配的源 Mod 身份会阻断导出，不能退回新建。发布仍使用游戏编辑器，Steam 条目的存在性、账号权限及编辑器行为由游戏平台处理。

需要使用压缩 Mod 时，请用官方 Mod Editor 的 Pack Mod 动作生成 `ModContent.fpk`。请对副本操作，不要覆盖 Workshop 缓存；Remis 当前不自动执行打包或发布。游戏内验收时需确认 ModItem `Filename`、`Language` 和加载顺序与目标设置相符；Remis 的扫描不验证游戏实际加载行为。

## 已知边界

普通项目支持检查会只读扫描 Lua 中直接调用的 `Untranslated(...)`，在 `hardcoded_lua` 中单列候选。它与 FPK 准备流程是不同入口，不能将发现当成已完成改造。准备流程仅改写可证明含义的受支持表达式，未知别名、引擎继承字段、任意 Lua 逻辑仍需复核；零候选不能证明整 Mod 无遗漏。源代码只做静态读取，不在 Remis 中运行。

完整源副本共用稳定 ID、英文回退和语言 CSV；只含文本包使用现有 CSV ID 并依赖原 Mod。运行时覆盖仅供经验证的高级绑定使用。详见[Lua 国际化工作流](../developer/mars-lua-localization-workflow.md)。不依赖原作者接受上游改造。

2026-09-25，用户反馈 Exotic Minerals Expanded 中文源副本已经部署并在游戏中正常使用。后续新增法语、德语并通过静态检查；用户提供的法语 Applications exotiques 科技说明截图进一步确认了该处的语言加载、分段、强调色和重音字符显示。用户随后确认德语查看正常，且绑定发布编号后的手动上传确实更新了同一 Workshop 条目，没有新建条目。这些反馈不等于所有界面或存档兼容性均已验证。归档范围、校验和、交付文件证据及未验证事项见[验收记录](../developer/mars-pipeline-acceptance-2026-09-25.md)。

普通 CSV 流程继续支持初次翻译、增量快照/写回、格式校验和问题导出。此游戏的新 FPK 项目当前没有专用可视化校对工作区；Agent API 的定点读取/保存不等于已有校对 UI。没有可用 CSV 时应先完成 FPK 准备，不能直接启动普通翻译任务。导出不处理字体、安装部署或 Workshop 发布；动态支持扫描与交付预览都保留 `runtime_verified: false`。安装后请在游戏内检查语言、ModItem 文件引用、加载顺序及动态文本。
