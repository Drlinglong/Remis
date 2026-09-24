# RimWorld 本地化格式证据与 adapter 边界

状态：离线格式调研；面向 RimWorld 1.6 时代的 mod 布局，尚未在游戏内验证。仓库当前 adapter `scripts/core/surviving_mars_csv.py` 提供了可借鉴的边界：自包含解析器、不可变 entry/document、明确识别而非猜测、保留源文档供安全写回、单独做 token 校验，并适配现有 `(key, text)` 消费端。RimWorld 需要按文件种类保留结构和覆盖语义，不能直接套用 CSV 的单列替换器。

## 已核对的格式事实

- **Keyed**：`Languages/<Language>/Keyed/**/*.xml`，根为 `LanguageData`，子元素名是全局 key、元素文本是译文；Keyed 文件名和内部目录可自组织。默认语言也需要 Keyed 文件。游戏查找不到 key 时会把 key 本身显示出来。不要从 Keyed 中硬推语言必须是 English；输入源语言应由用户/项目设置决定，也允许从任意已有语言文件取源值。
- **RimWorld 语言目录名**：Remis 的 `code`/`key`/本地化显示名不能直接拼成目录。当前产品语言代码映射到游戏目录：`en→English`、`zh-CN→ChineseSimplified`、`fr→French`、`de→German`、`es→Spanish`、`ja→Japanese`、`ko→Korean`、`pl→Polish`、`pt-BR→PortugueseBrazilian`、`ru→Russian`、`tr→Turkish`。官方 [简体中文仓库 README](https://github.com/Ludeon/RimWorld-ChineseSimplified) 明确给出 `ChineseSimplified (简体中文)` 安装目录；官方 [Brazilian Portuguese 仓库](https://github.com/Ludeon/RimWorld-PortugueseBrazilian) 与 [Spanish Latin 仓库](https://github.com/Ludeon/RimWorld-SpanishLatin) 的安装说明分别给出 `PortugueseBrazilian`、`SpanishLatin`。本项目的普通 `es` 映射为官方 `Spanish` 目录（Castilian），并不映射到 Latin American `SpanishLatin`。其他对应名与官方语言仓库名称一致；adapter 对未识别代码保留输入并让资源发现产生无资源诊断，不生成伪造目录名。
- **DefInjected**：`Languages/<Language>/DefInjected/<DefType>/**/*.xml`，`<DefType>` 必须对应 Def 类型；节点名是 `DefName.field.path`，值是译文。常见可见字段不限于 `label`、`description`：有 `labelShort`/`labelPlural`、`gizmoLabel`/`gizmoDesc`、`ingestible.ingestCommandString`/`ingestReportString`、`tools.N.label`、`stages.N.label`/`description`、`WorkGiverDef.gerund`/`verb` 等。应维护带来源版本的显式字段规则集（字段路径 + Def 类型 + 索引列表策略）；已验证的稳定路径跨兼容小版本复用，同时把实际游戏版本记作 provenance 并注明运行时未验证。未知路径给诊断，不能用“所有 XML 叶子文本都是可翻译”推断，也不能因版本未确认就丢弃已知路径。当前规则目录包含 label/description、ThingDef 的 labelShort/labelPlural、ingestible 命令/报告字段、tools 与 comps 中的已知文本、WorkGiverDef gerund/verb、RecipeDef jobString、HediffDef/ThoughtDef stages label/description，以及 RulePackDef rulesStrings 索引。具体适用类型和路径须随规则集版本维护。含继承、类名路径与数字索引的路径须保留原始 key，无法可靠映射时给出可见诊断。
- **`rulesStrings`**：这是 RulePack 中有语义的语法规则列表，不是普通句子列表。规则典型形式 `symbol(selector=value)->literal [grammarSymbol] {NAMED_argument} {0}`。只把 `->` 右侧的自然语言片段作为翻译内容，保持左侧 rule 名/参数、箭头、方括号 grammar 引用、花括号命名参数与数字格式项。`RulePack` 字段标有 `MustTranslate` 与 `TranslationCanChangeCount`（可核对 decompile 参考）；官方格式样例的 DefInjected key 形如 `MyRulePack.rulesStrings.0`。数量可能因语言而变，不能要求源与译文索引数量必然相同，也不可静默截断/重排。只在语法明确可读时产生候选；无法拆解、未知字段嵌套或索引时保留条目并标注待人工复核。
- **Strings**：`Languages/<Language>/Strings/**/*.txt` 是 RulePack `rulesFiles` 引用的词表，文件通常逐行一项；`<li>Names/Words->name</li>` 将路径（语言目录下相对路径）绑定到 grammar symbol。按 UTF-8 文本行记录并保留空行、注释和行尾；不应把文件名、RulePack 字段或 `->` 左侧 symbol 当作译文。词表支持不等长是自然需求，但词序、空项或非文本格式不明确时需诊断。
- **占位符/标记**：Keyed 常见 `{0}`、`{1}` 和 `{PAWN_nameDef}`、`{TARGET_label}`；grammar 还用 `[symbol]`；富文本常见 `<b>…</b>`。这些是运行时语义，不得遮蔽为通用占位符再交给模型。对格式项和 markup 可按类型/多重集核验身份和数量；`[symbol]` 变化会改语法解析，需严格核验。不能确认语义的花括号、方括号或 XML 混合内容标记为人工复核。
- **About 元数据**：`About/About.xml` 的 `packageId` 是稳定 mod identity；`modDependencies/li/packageId` 表依赖，`loadAfter/li` 是加载顺序提示，二者不可混为一类。生成独立翻译 mod 时，依赖源 mod 的 packageId 并保留其必要加载关系；若识别不到 packageId/元数据无效，显示阻断诊断，不能猜 Steam ID 或以文件夹名替代。PawnRules 的 About 示例直接证明 `description` 中的 `Mod Version: 1.5.0` 与 `supportedVersions` 中游戏版本 `1.1`、`1.2`、`1.3` 是不同字段；不能把 mod 版本当游戏版本。
- **有效目录与 overlay**：无 `LoadFolders.xml` 时，版本目录选择最适配的游戏版本，并叠加 `Common` 与根目录；同相对路径按 specificity 覆盖。存在 `LoadFolders.xml` 时（1.1+）由相应 `<vX.Y>` 条目明确选择目录，条目顺序决定重叠文件胜者，`IfModActive`/`IfModNotActive` 条件可多选其一，1.6 的 `IfModActiveAll` 为 AND。About/LoadFolders 解析只能使用不解析外部实体的 XML parser。若用户未提供目标游戏版本或已启用 packageId 集合，报告 overlay 不确定以及可能分支，不得假称已解析出游戏实际加载视图；未知条件/版本也应诊断。

## 建议 adapter 记录契约

采用统一 `Entry` 供 Remis 工作流消费，同时保留 `source_path`、`kind`、`stable_key`、原文档/节点定位、精确源文本、行号/索引、源语言、游戏版本依据、eligible/review 状态与 diagnostics。`stable_key` 可分别是 Keyed key、DefInjected 的完整点路径、Strings 的相对路径+行号、rulesStrings 的 RulePack field+索引。写回由 adapter 根据原始字节/文本只替换内容节点/词表行；XML 保留声明、注释、空白、编码和行尾，不重排或标准化整棵文档。输出采用明确目标语言和目标 mod 目录策略，完整保留 source/Def keys 与 grammar 结构。

解析策略分层：安全 UTF-8 文件发现 → 版本/加载条件解析 → 安全 XML 解析 → 已知模式/字段规则分类 → entry 与诊断。未知字段不默默全收，也不把整类格式判成完全不支持。至少将不认识的 DefType/path、重复/空 key、重复 Keyed key、XML malformed、越界/无法解码列表索引、未知 LoadFolders 条件、继承/运行时生成/程序集字符串列为显式状态。不可执行 DLL/程序集，也不解析 DTD 或外部实体。

现有实现可复用的理念：`parse_file` 显式 UTF-8（对 RimWorld 可允许并保留 BOM）、结构化 parser error、稳定定位、重写前 key-map 对账，以及 compare_tags 的精确 token multiset。Surviving Mars adapter 以 ID 校验后仅写 Translation 列；RimWorld 应为 XML/文本文件设计各自的 loss-minimizing writer，禁止通用 XML serialize 导致注释/格式损失。

## 样例与许可边界

- [Ludeon 官方简体中文数据仓库](https://github.com/Ludeon/RimWorld-ChineseSimplified) 展示 Core 与 DLC 的现实目录；仓库 README 链至 Ludeon 论坛许可页。许可页在本次检索时无法读取，因此这里只引用结构/文件事实，不复制其翻译内容。
- 目录命名另外交叉核对 [Ludeon 官方法语仓库](https://github.com/Ludeon/RimWorld-fr) 的 `French` 安装说明、[官方 Brazilian Portuguese 仓库](https://github.com/Ludeon/RimWorld-PortugueseBrazilian) 的 `PortugueseBrazilian` 安装说明、[官方 Spanish Latin 仓库](https://github.com/Ludeon/RimWorld-SpanishLatin) 的 `SpanishLatin` 安装说明，以及 [Ludeon 官方组织的语言仓库目录](https://github.com/ludeon)；产品当前 `es` 是 Spanish，所以映射到 `Spanish`，不是另一个 `SpanishLatin` 目录。
- [PawnRules](https://github.com/Jaxe-Dev/PawnRules) 是真实 mod 样本，包含 About、Keyed、Defs、程序集路径；About 可直接看到 packageId、支持版本和依赖关系。其 README 仓库列有 LICENSE，可先确认许可再选用短 XML fixture；本报告不复制其表达性文本。该样本支持游戏版本仅至 1.3，适合验证 metadata/格式而非现代游戏兼容性。
- [RimWorld localization guide](https://rimworldwiki.com/wiki/Modding_Tutorials/Localization) 当前标记为 stub，适用于格式入门，不作为完备规则来源；[Mod Folder Structure](https://rimworldwiki.com/wiki/Modding_Tutorials/Mod_Folder_Structure) 有版本目录、LoadFolders 和条件说明。较细的可翻译字段应以逐游戏版本的官方 language files / 官方 Core 内容交叉核验，再固化成规则。
- [Ludeon 论坛语言许可主题](https://ludeon.com/forums/index.php?topic=2933.0) 本次无法打开；[官方语言仓库](https://github.com/Ludeon/RimWorld-ChineseSimplified) README 能确认链接和归属，不能据此声称许可条款内容。
- [PawnRules LICENSE](https://github.com/Jaxe-Dev/PawnRules/blob/master/LICENSE) 已核对为 MIT；它支持版本只到 1.3，且该 repo 当前归档。不会将该仓库代码或原始 Keyed 文本纳入 Git；只在本机 ignored `.runtime` 中保留固定小样例用于可选解析回归，详见末尾 provenance。
- [RimWorld 1.6 XML-first 模板](https://github.com/sanicek/rw-mod-template) 明确标注 MIT，并展示现代 1.6 `Languages/English/Keyed`、About 与 LoadFolders 结构；[独立多人语言仓库](https://github.com/rwmt/Multiplayer-Locale) 也标注 MIT、包含多语言 Keyed 文件。两者仅用于格式与许可核验。
- [Ludeon 官方语言文件样例](https://github.com/Ludeon/RimWorld-ChineseSimplified/blob/master/Core/DefInjected/DifficultyDef/Difficulties.xml) 展示真实 DefInjected 键；[RimWorld decompile 的 IngestibleProperties](https://github.com/josh-m/RW-Decompile/blob/master/RimWorld/IngestibleProperties.cs) 将 ingestible 的命令和报告字段标为 `MustTranslate`。规则表以显式路径归纳；仓库内现有 adapter fixture 为合成数据，另有下方独立可选的上游 Keyed XML 解析回归样例。

## 固定上游 Keyed XML 回归样例

- 来源 mod：[`Jaxe-Dev/PawnRules`](https://github.com/Jaxe-Dev/PawnRules)，固定 commit `86e5cf355dc90e827cf99bcbb2fc2d658ecf9f4b`（已由上游 `master` ref 核对）。样例原路径为 [`Languages/English/Keyed/Keys.xml`](https://github.com/Jaxe-Dev/PawnRules/blob/86e5cf355dc90e827cf99bcbb2fc2d658ecf9f4b/Languages/English/Keyed/Keys.xml)，上游文件大小 12,200 bytes，原始文件 SHA-256：`00b3b04b87bb4ae107fb1b54f5ee4721ac1ffaa3d8b34241ead8746e28235948`。本机可选 fixture 放在忽略目录 `.runtime/rimworld-fixture/Mod/Languages/English/Keyed/Keys.xml`，原样复制，测试会用 SHA-256 固定校验；没有把样例提交到仓库。
- 许可：同一固定 commit 的 [`LICENSE`](https://github.com/Jaxe-Dev/PawnRules/blob/86e5cf355dc90e827cf99bcbb2fc2d658ecf9f4b/LICENSE) 为 MIT。测试只解析原始英文 Keyed XML，不将上游内容用于产品数据或翻译；用一个合成 `About/About.xml` 提供 packageId 与 1.3 supported-version metadata，避免复制 About 或暗示这些 metadata 来自本地用户 mod。
- 新增可选测试 `tests/core/game_adapters/test_rimworld_external_fixture.py`：若忽略 fixture 不存在则 skip；存在时走 adapter 的真实目录发现与 UTF-8 文件读取，检查空翻译 no-op 完整保留文档，替换 `PawnRules.Button.OK` 后写入临时目标文件并重新读取核对值，同时确认原样例哈希未变化。该测试验证离线 adapter I/O，不运行游戏、不调用模型；PawnRules 的支持版本最高为 1.3，不能用它宣称当前 RimWorld 版本的运行时兼容性。

## 未验证边界

本环境无游戏安装，因此本报告覆盖离线发现/解析/writer 与 GUI 可执行的接受性设计，不声称游戏内覆盖顺序、错误报告或翻译效果已验收。运行时 `Translate()` 字符串、程序集硬编码内容、继承展开、PatchOperation 实际结果与依赖 mod 条件需要 game runtime 才能完整确定；离线 adapter 应给出可操作的覆盖阻断或待复核诊断。
