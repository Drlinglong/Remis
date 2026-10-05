# Probably Stolen：Mod 本地化适配调查

核验日期：2026-09-29。状态：**调研与实施准备，尚未适配**。
这是开发资料，不是现行用户操作指南，也不表示 Remis 已能创建此游戏项目。

## 结论

值得支持，但应按资源格式和加载器分别适配。当前可见生态同时包含原生 Mod API
文档、MelonLoader DLL、Custom Start JSON 和 PSApi 内容包；不能用一个“Unity Mod”
解析器覆盖所有情况。优先实现可读文本资源的发现、翻译和受控写回，再验证独立翻译
补丁。DLL 硬编码、源代码国际化和运行时覆盖作为后续明确的交付能力。

本机实包补充后，建议优先 Custom Start JSON，再接 PSApi 物品 JSON；原生 CSV 保留
离线格式工作，但其文档要求的调用方法没有出现在本机方法表中，暂不作为可运行交付。
建议产品 game_id 为 `probably_stolen`，内部记录具体 resource_format / loader_kind。
游戏格式接入沿用 Remis 的 GameAdapter 和现有任务、增量、归档、模型及审批系统。
本调查没有修改生产注册表、游戏语言选项或 README 支持矩阵。

## 游戏与证据状态

- 正式名：Probably Stolen - Cyberpunk Shopkeeper Sim；Steam 中文名“深空当铺：可能是偷得”。
- Steam 正式版 App ID `4348910`，当前计划发售日 **2026-10-28**；Demo 为 `4349200`。
- Steam 英文商店完整表列出简中、英语、德语、日语、俄语、法语、西班牙语（西班牙）、
  波兰语，共八种。Modding 指南另列十个 locale，本机资源亦有十个定义，且与商店
  清单并非同一集合；不能将资源存在等同于正式承诺或完整翻译。
- 用户随后提供本机 `I:\SteamLibrary\steamapps\common\Probably Stolen Demo`；
  已对该目录做静态只读核验，详见下节。本轮未启动游戏、安装 Mod、修改存档或调用付费模型。
- Nexus 抽查可确认存在仓储、交易界面、开局、内容框架等不同 Mod 类型；
  未做全站统计，不将网页缓存计数当作生态成熟度或兼容覆盖率。

来源：[Steam 正式版](https://store.steampowered.com/app/4348910/)、
[Demo](https://store.steampowered.com/app/4349200/)、
[Nexus 分类](https://www.nexusmods.com/games/probablystolen)。

## 固定资料版本

| 来源 | 本轮固定 commit | 证据用途 |
|---|---|---|
| [dragonpan2/probably-stolen-modding](https://github.com/dragonpan2/probably-stolen-modding/tree/f2137eb7bebeecfadca1ccabb0cae3757ea4319f) | `f2137eb7bebeecfadca1ccabb0cae3757ea4319f`，2026-09-16 | 原生 API 文档和 LearnerMod 示例 |
| [nql1314/custom-start-framwork](https://github.com/nql1314/custom-start-framwork/tree/7a976af9d116a3102ee9fb0db171d05b9664c759) | `7a976af9d116a3102ee9fb0db171d05b9664c759`，2026-09-20 | 双语 JSON、实际语言选择代码、MIT 许可证 |
| [muchengbai2005/PSApi](https://github.com/muchengbai2005/PSApi/tree/9b645129cb50e57fbddcf9bdde974dcc6f0e6754) | `9b645129cb50e57fbddcf9bdde974dcc6f0e6754`，2026-09-24 | 内容包模型、物品文本注册与 Harmony 读取路径 |

原生指南声明由 AI 辅助撰写、开发者审阅，并要求以实际游戏行为为准。
它引用 Managed/Assembly-CSharp.dll、IMod 与内建 Harmony；近期 Nexus 作者安装说明
仍明确写 MelonLoader、IL2CPP。本机实包确认有原生类型和部分接口，但文档与实际方法表
存在差异。不能推断原生接口已经取代 MelonLoader，也不能推断二者可以同时正常加载。
APIChanges.md 中标为 in development 的内容不当作已发布接口。

## 本机 Demo 静态实证

安装目录是编译后的游戏，不是完整 C# 源码工程。Steam build 为 `25382790`；
UnityPlayer 文件版本 `2021.3.45.8976527`，IL2CPP metadata version 为 `31`。
存在 GameAssembly.dll 和 global-metadata.dat，不存在实际 Managed/Assembly-CSharp.dll，
检查时也没有 Mods/MelonLoader 目录。ScriptingAssemblies.json 中的逻辑程序集名称不代表
对应可编辑 DLL 实际存在。

本轮参考 [Il2CppDumper 的元数据布局](https://github.com/Perfare/Il2CppDumper/blob/4741d46ba9cd6159c5d853eb9d6fc48b4bfa2b1a/Il2CppDumper/Il2Cpp/MetadataClass.cs)，
编写只读符号探针，验证 11,215 个类型、77,449 个方法的记录边界、token、声明类型归属。
不加载游戏 DLL、不反编译/分发完整游戏源码。得到：

- 存在 IMod、ModLoader、ModManifest、LoadedMod、ModHook、ModHelper、LocHelper 类型。
- ModLoader 方法表有 LoadLocalization、ParseCsvValue、IsModEnabled、LoadModDll；
  LoadedMod 字段有 Localization、IsEnabled；存在 OnModAssetsLoaded 事件相关方法。
- **ModHelper 方法表仅有 GetSoundIdentifier 和静态构造器；没有文档中的 GetLocalized。**
  这可能涉及构建裁剪或代码版本差异，仅凭元数据不能判定原因；当前不能依赖此调用生成可运行补丁。
- LocHelper 保留 GetCurrentLocaleCode、SetLocale 和物品/UI/对话等原版查询接口。
  这提供后续针对性桥接的候选位置，不等于已经验证了补丁安全性或生命周期。

另使用隔离安装的 UnityPy `1.25.3` 只读解析三个 Addressables bundle，零解析失败：

| 资源 | 静态读取结果 |
|---|---|
| localization-locales | 10 个定义：en、zh、fr、de、ru、ja、es、ptBR、it、ko |
| English StringTables | 14 张表，5,677 条存储记录 |
| Simplified Chinese StringTables | 14 张表，5,596 条存储记录 |

每行有 m_Id、m_Localized、m_Metadata。上述数量是存储记录数，不是覆盖率；差异不能
直接判定为缺失 81 条翻译，需要按共享表身份和键对齐才能判断。没有导出游戏译文正文。
英文语法抽样检测到 `{0:P0}`、`{count}`、b/i/u/sprite/wave/slide 标签及 SmartFormatTag 元数据。
因此原版 Unity 表、原生 Mod CSV、社区 JSON 的格式校验必须分开。

复现脚本和摘要位于忽略目录 `.runtime/research/probably-stolen-20260929/`：
`inspect_metadata.py` / `local-metadata-audit.json` 与
`inspect_assets.py` / `local-asset-audit.json`。资源读取前后哈希一致；符号与资源摘要仅保留
结构、计数和哈希。UnityPy 安装在该目录的 python-deps，不加入 Remis 生产依赖。

关键输入 SHA-256：
- global-metadata.dat：`efdca95772fdce327b51e0c7e8d320e7055917be5c669db47c1f7b36389f1f41`
- GameAssembly.dll：`3bea17eeec77adab6418918c28a8aa9a06f290582a2972639a48bd7e5a01ab44`

未运行游戏，未证明原生 DLL 加载、实际语言菜单、字体或热切换行为。

## 四类资源与交付边界

### 1. 原生 Localization CSV：文档契约清楚，本机构建存在接口缺口

[ModdingGuide.md 的 Localization 部分](https://github.com/dragonpan2/probably-stolen-modding/blob/f2137eb7bebeecfadca1ccabb0cae3757ea4319f/ModdingGuide.md#localization)
及相邻资产加载说明给出以下规则：

- `Mods/<folder>/manifest.xml` 的 ID 是 Mod 身份；Localization 目录只扫描直接子文件。
- 每语言一个 UTF-8 CSV，无表头；空行及 `#` 注释跳过。第一个逗号分隔键与值；
  后续逗号属于正文。可用双引号包围正文，内部引号双写。
- 一条记录占一个物理行；换行编码为字面 `\n`，不支持正文内的物理多行。
- `GetLocalized(modId, key, args)` 查当前语言，继而回退英语和键；参数使用数字位置格式。
  Mod 条目不能套用原版 Unity Smart Strings 的命名参数、复数规则。
- 文档代码为 `en/fr/de/ru/zh/ja/es/ptBR/ko/it`；Remis 标准代码应单独映射，
  例如 `zh-CN → zh`、`pt-BR → ptBR`，并由实际构建能力限制可选项。
- 语言资源在 Init/OnEnable 后加载；相关功能需要匹配正确的资产加载时机。

这是不同于火星五列 CSV 的方言，不能交给 surviving_mars_csv.py；也不能直接按
普通多列 CSV 读取，否则未加引号的正文逗号会被错误拆列。

**可先设计的交付：** 在隔离输出中生成原 Mod 的 `Localization/<locale>.csv`，
由安装计划定位目标 Mod ID，再经批准补充该文件。仅发语言文件，不复制 DLL/图片。
这属于“语言文件补丁”，不是已证明可独立启用的翻译 Mod。

**独立补丁待验证：** GetLocalized 带原 Mod ID；另建 Mod ID 的 CSV 不自动拥有原 Mod
的命名空间。需要证实受支持的覆盖注册方式或制作专门的本地化桥接 Mod。
禁止伪造相同 manifest ID，或用模糊的全局文本替换冒充跨 Mod 覆盖。

文档也明确本地化是 opt-in。本轮读取 LearnerMod 示例发现其名称、说明仍直接赋值
于 C#，样本树没有 Localization CSV；因此“有原生 CSV API”不代表现有 Mod 已采用它。
参考 [PurpleBloodSynthesizer.cs](https://github.com/dragonpan2/probably-stolen-modding/blob/f2137eb7bebeecfadca1ccabb0cae3757ea4319f/Modding/LearnerMod/PurpleBloodSynthesizer.cs)。

### 2. Custom Start：适合首批真实 JSON 样本

路径是 `UserData/custom-start/<folder>/profile.json`。实际模型
[CustomStartProfile.cs](https://github.com/nql1314/custom-start-framwork/blob/7a976af9d116a3102ee9fb0db171d05b9664c759/framework/CustomStartProfile.cs)
将 name、description 定义为含 Zh/En 的 LocalizedText。
本轮实际解析 `the_cyber_bear_12/profile.json`，确认这两字段均含 zh/en。

[GameLocaleHelper.cs](https://github.com/nql1314/custom-start-framwork/blob/7a976af9d116a3102ee9fb0db171d05b9664c759/shared/GameLocaleHelper.cs)
只有英文前缀判定；[I18n.cs](https://github.com/nql1314/custom-start-framwork/blob/7a976af9d116a3102ee9fb0db171d05b9664c759/shared/I18n.cs)
优先对应字段，缺失时回退另一字段。当前非英文语言均走中文分支，直接增加 fr/de
字段不会自动生效。首版只能声明该格式已有的 zh/en 支持。

提取白名单只覆盖 name/description 的选定源语言。id、数值、物品清单、阵营、路径、
开局条件等保持不变；中文原文同样是正常输入，不默认所有 Mod 都从英语翻译。
可先输出字段级修改计划或隔离的 profile 文件，部署时检查原文件哈希、备份与回滚。
真实语义不变量：除批准的目标字段外，原 JSON 树完全不变。

仓库 [LICENSE](https://github.com/nql1314/custom-start-framwork/blob/7a976af9d116a3102ee9fb0db171d05b9664c759/LICENSE)
实际存在，MIT；采用其代码/样本时保留许可，并另行核对单独资产的来源。

### 3. PSApi：JSON 可抽取，但目前不是通用多语言表

PSApi 运行于 MelonLoader，包含 JSON pack、PSScript、PSUI，并支持编译内容包。
首批只覆盖已核验物品 schema，不遍历所有 JSON 字符串或随意改脚本。

[ItemModels.cs](https://github.com/muchengbai2005/PSApi/blob/9b645129cb50e57fbddcf9bdde974dcc6f0e6754/_psapi/PSApi.Items/ItemModels.cs)
与 [ItemStore.cs](https://github.com/muchengbai2005/PSApi/blob/9b645129cb50e57fbddcf9bdde974dcc6f0e6754/_psapi/PSApi.Items/ItemStore.cs)
表明可见物品文本为 name、desc、flavor 单字符串。本轮实际解析 example_processor.json，
得到一个物品，存在 name、desc 两个文本字段；没有凭空制造缺失的 flavor。

[LocService.cs](https://github.com/muchengbai2005/PSApi/blob/9b645129cb50e57fbddcf9bdde974dcc6f0e6754/_psapi/PSApi.Items/LocService.cs)
将字段注册为 item_<id>_name/desc/flavor，重名后注册覆盖前者并警告；
Harmony prefix 命中后直接返回文本，没有在这条路径中选择语言或处理 args。
所以不能把原生 CSV 的参数格式化和 fallback 规则套在这里，也不能把任意花括号
自动解释为游戏可执行参数。

可做同一内容包的受控文本覆盖；不能靠另建一个复制同 ID 物品的 pack 实现纯翻译，
那会进入内容注册与覆盖逻辑。独立多语言包应另验证注册 API 或桥接器。
PSUI/PSScript/编译 pack 暂列未支持资源，发现计数与已覆盖文本分开显示。
GitHub API 返回 license=null，已查仓库未发现明确 LICENSE；公开源码不等同于获得
修改副本分发许可。初期不把其源文件作为可再分发 fixture，测试使用自行编写的小样本。

### 4. MelonLoader DLL：不能承诺一键通用汉化

代表性作者页面：

| 样本 | 作者说明中的技术信息 | 对适配的意义 |
|---|---|---|
| [QuickTrade #164](https://www.nexusmods.com/probablystolen/mods/164) | MelonLoader、Demo、可随语言切换中英 UI | 需要区分 Mod 自带语言系统与原版文本 |
| [Marketplace Requests #85](https://www.nexusmods.com/probablystolen/mods/85) | 多 DLL、终端与可选子模块、中英界面 | 一个下载包不一定等于一个独立 Mod/语言资源 |
| [ExpandedStorageBalance #173](https://www.nexusmods.com/probablystolen/mods/173) | DLL、MelonLoader/IL2CPP/.NET6，可能附 JSON | 配置 JSON 不必然是可翻译文本，不能盲扫 |

以上为作者页面声明，未下载/执行其 DLL。页面中的版本与要求只绑定具体文件版本，
不推广到所有 Mod，也不把页面最近更新时间当作游戏兼容性证明。

建议只读读取程序集元数据及字符串候选，并给出上下文和未覆盖诊断；不能通过加载
程序集到 Remis 进程进行探测。拥有源码且许可明确时可以做 C# AST 定点国际化，
构建过程应独立受控；无源码时仅为选定 Mod 设计可验证的运行时补丁，不做任意 DLL 改写。

## Remis 接入设计（尚未实现）

### 资源与身份

现有入口：`scripts/core/game_adapters/contracts.py`、`registry.py`、`workflow_bridge.py`。
adapter 负责读/解析/渲染/校验；部署、数据库和模型仍由共享工作流负责。

- game_id 固定；resource_format 分 native_csv、custom_start_json、psapi_items。
- 稳定条目身份为游戏 + 原 Mod/pack/profile 身份 + 资源命名空间 + 原始键/实体字段。
  文件移动能唯一对应时保留身份；版本和源哈希是快照，不因版本号变化全量重译。
- 文件夹名不能替代 manifest ID；JSON 数组位置不能替代 item/profile ID。
- 记录 loader/API 能力与实测 build。版本差异只触发相关能力核验，不整体丢弃已有格式规则。
- 裸 DLL、未知 JSON、已编译 pack 给出未支持原因；不得回退成 P 社文本并报“完成”。

### 格式校验

原生 CSV 独立处理引号、第一逗号和字面换行；禁止导出正文物理多行。
数字占位符允许翻译调整顺序，但保留参数身份、次数和已确认的格式部分；
双花括号、alignment/format 等扩展先以实际运行时样本建立规则，不从宽泛 string.Format
推测游戏 wrapper 接受所有写法。富文本标签按实际 UI/样本确定，未知标签不静默删除。
所有语义标记保持模型可见，不以不透明占位符代替。导出检查独立预期结果，不能只做
同一解析器的自写自读。JSON 验证未授权字段、类型、数值和引用完全未变。

### GUI、Agent 与合集

入口应是选择游戏后导入下载 ZIP、解压目录或已安装 Mod。Remis 检测格式与加载器，
显示“可翻译字段 / 硬编码候选 / 未覆盖资源 / 可交付方式”，不要求用户预先理解 C#。
压缩包只隔离解压且检查路径/体积/链接，不执行 DLL、安装器或构建脚本。

game_support 应分别投影 import、translation、file_patch、standalone_patch、
collection、runtime_verified，不能只用一个“支持此游戏”布尔值。GUI 与 Agent 共用
相同计划、预览、审批和结果回执。实施时同步用户指南、内置助手帮助包、Codex API 文档；
本调研保持 excluded，避免被用户助手回答为现有能力。

合集继续沿用“成员项目 + 独立发布身份 + 成员版本快照”。运行时桥接必须按实际加载器
检查成员是否启用，按原 Mod/pack 命名空间查找，而非检测 DLL 文件是否存在。
目标不存在时无副作用；不同 Mod 使用同一运行时键且内容不同则报冲突。多语言能力
依赖各格式真实读取路径，不把 Custom Start 的二语言选择器包装成十语言支持。

## 实施顺序与验收

| 阶段 | 可交付结果 | 完成标准 |
|---|---|---|
| P0：运行时确认 | 当前 Demo 的 loader/build/locale 检查记录 | 静态检查已做；下一步需游戏内验证目标加载器与一个样本，解决原生 API 缺口 |
| P1：离线适配 | 首先 Custom Start JSON，其次 PSApi 物品 JSON；原生 CSV 为实验格式 | 独立金标、格式不变量、增量键、GUI/API dry-run；无模型模拟整条正常任务路径 |
| P2：首个真实交付 | 单个 Mod 的语言文件补丁；原生 CSV 待接口可用后加入 | 游戏内名称/UI/换行/语言切换可见，安装卸载可回退；明确覆盖范围后才标 Preview |
| P3：独立补丁与合集 | 一个桥接器加按成员组织的译文数据 | 目标启用/禁用、多个成员、冲突与加载顺序、语言切换、原 Mod 更新/删除条目均验证 |
| 后续：硬编码 | 指定 Mod 的源码改造或特定运行时补丁 | 有明确候选定位、可重复构建与回归，不声称全站 DLL 通用 |

P1 的格式工作现在即可开展；Demo 已在本机，P0/P2 下一步需要代表性 Mod 包及实际运行验证。
正式版发布后重验 P0/P2 关键路径，不把 Demo 的通过结果自动升级成正式版 Stable。

离线夹具至少包括：注释/空行/UTF-8/BOM/CRLF、未加引号正文逗号、双写引号、字面换行、
重复键、缺失源语言、占位符重排/损坏、未知 locale、JSON 数组重排、缺失可选文本、
同键不同 Mod、ZIP 路径穿越以及未识别 DLL。游戏验收至少包括语言切换后既有对象/新建对象、
只启用部分合集成员、全部关闭、存档读写与卸载后无残留影响。

## 本轮验证与边界

- 阅读固定 commit 的文档与 C# 源码；实际解析两个公开 JSON 样本，而非仅看 README。
- 核对了实际 Custom Start LICENSE，以及 PSApi 无明确仓库许可证的现状。
- 外部原文和源码快照只保存在忽略目录 `.runtime/research/probably-stolen-20260929/`，
  community-sources.json 记录 URL、commit 与本地 SHA-256；不将未知许可源码提交到仓库。
- 生产仓库仅新增本报告及文档入口；只读探针和隔离分析依赖留在忽略目录。
  不编写/注册生产 adapter，不启动服务，不生成真实翻译或安装包。
- 独立汉化补丁、原生 API 在当前 Demo 的可用性、字体覆盖、正式版兼容性均未验证。

社区规则见 [CodeOfConduct](https://github.com/dragonpan2/probably-stolen-modding/blob/f2137eb7bebeecfadca1ccabb0cae3757ea4319f/CodeOfConduct.md)
与 [APIChanges 的说明](https://github.com/dragonpan2/probably-stolen-modding/blob/f2137eb7bebeecfadca1ccabb0cae3757ea4319f/APIChanges.md)：
文档允许研究游戏反编译结果，但不允许再分发游戏代码、资产或本地化表；其他作者 Mod 的
再分发也需其许可。Remis 默认交付自己的译文与必要适配层，完整副本应另核实适用许可。
