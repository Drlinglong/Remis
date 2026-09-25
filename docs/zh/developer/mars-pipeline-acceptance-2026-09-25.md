# Surviving Mars FPK 国际化流程验收记录

验收日期：2026-09-25。此记录描述一次 Exotic Minerals Expanded 的端到端本地准备、翻译与源副本构建。它不是游戏内验收，也不代表该 Mod 的全部可见文本已被发现或翻译。

后续用户验收：2026-09-25，玲珑报告已经部署并测试该中文完整副本，效果良好。这是当前 Mod 中文版本的用户运行反馈，不扩展为所有 Mod、其他语言或所有旧存档的通用兼容保证。下文原有“尚未安装/运行”描述保留为构建时的历史边界。

## 同日多语言与发布素材跟进

用户随后要求复用国际化源副本增加法语、德语，并报告中文副本已通过游戏 Mod 管理器发布、下载使用正常，但描述与封面仍是原版。检查导出的 `metadata.lua` 确认：标题有本地化前缀，`description` / `short_description` 和 `image` 仍继承原 Mod；这是导出时未提供新发布信息，并非译文 CSV 不生效。

语言目录现仅为 `en`、`zh-CN`、`fr`、`de`、`es`（西班牙）、`pl`、`pt-BR`（巴西）、`ru`、`tr`。GUI 的创建 CSV 项目源语言与翻译目标选择器使用游戏目录；Agent API 和普通翻译 API 在创建任务前拒绝火星不支持的目标语言。其他游戏与全局语言目录保持原规则。

本轮前端增量无新增 state / effect：沿用目标选择清理 effect，在配置加载后才清理不支持的目标；源语言在进入既有 CSV 路线时回退到可用的英语。API 配置加载仍在 hook，语言过滤放在独立工具函数，展示组件不执行请求。`InitialTranslation.jsx` 未修改；相对 HEAD，`ConfigStep.jsx` 为 482 → 489 行、`LanguageTargetSelector.jsx` 为 135 → 170 行。`CreateProjectModal.jsx` 在前序 FPK 交互改造的 197 行基础上达到 213 行，均未增加冻结上限。语言选择、配置加载与源语言回退的 27 项集中测试、相关 ESLint 和 Vite 构建通过。

付费翻译作业 `4b1be1d7-4179-473c-902a-52e57edb68e7` 使用 OpenAI / `gpt-6-luna`，由英文分别生成法语与德语各 88 条；词典、项目档案上下文、嵌入式工作台均关闭。作业暴露了旧的多语言 CSV 输出碰撞：两种语言写入同一个 `Multilanguage-prepared/ModTexts.csv`。两种语言的完整译文均保存在归档版本 31，后续恢复不需要再次调用模型。生产流程已改为各语言独立目录，共享目录仅承担任务检查点身份；相关 64 项回归及 Python 架构检查通过。两种语言都在条目 `908638955531` 省略了第二组重复强调标签，需定点修正后才可交付。

恢复计划 `plan_3978819afc8a46d995fc6a26ed8f96ae` 已经由 Agent API 执行，分别建立并注册 `fr-prepared`、`de-prepared`。随后通过带文档修订校验的 Agent proofreading 保存两条定点格式修正，重新读取确认文件与语言对应的归档基线相同。没有再次调用翻译模型。同步修复了 Mars proofreading 对 `fr-prepared` / `de-prepared` 等目录前缀的识别，避免误同步到默认中文基线；14 项 CSV 测试覆盖只写 Translation 和各语言基线隔离。

最终三语言交付计划 `plan_ea99079d4ccb4d95a817fff9d3c9eec0` 已生成并保存回执，位于上述准备运行目录的 `deliveries/plan_ea99079d4ccb4d95a817fff9d3c9eec0`。共 60 个文件、10,196,278 bytes，中/法/德各 88 条、各 27 个真实换行、无标签或换行不匹配；22 个 Lua 通过独立解析。与已验收的中文包相比，原有 34 张 PNG、`Code/` 玩法代码和中文 CSV 逐字节一致，变化只涉及新增语言表、注册及发布素材。原始 FPK 哈希保持不变。可复现的静态验证脚本和 JSON 证据位于 `.runtime/publication/exotic-minerals-expanded/`。

新增 source-copy 导出 API 的 `metadata_overrides` 可写入标题、描述、简述、更新说明以及受 SHA-256 约束的封面，保留原作者署名。最终包包含中文 BBCode 工坊说明、版权与完整副本原因说明和 Remis 支持链接；新增 AI 封面使用 1254×1254 JPEG（416,607 bytes），原始 PNG 单独保留。SDK 限制封面/截图各不超过 1 MiB，标题 60 字符、描述 8000 字符；本次满足这些可核验限制。

发布身份：用户已发布的中文副本是 Workshop `3807689989` / Mod ID `Remisca294bd547cb`，原作者条目是 `3679917456` / `kz4dEz`。新导出包不带顶层平台发布编号；更新既有用户条目时应保留其自身编号，不能复制原作者编号。最新游戏日志的 mod definition 列表包含二者，但实际 mod items 列表只包含本地化副本。日志未保存用户所见的明确上传失败信息，不能声称报错已修复。

最终集中验证：128 passed、1 skipped（另有已存在的 pykakasi 弃用警告），Python 架构检查、compileall、`git diff --check` 通过。只进行了本地导出；没有覆盖安装目录或操作 Workshop 发布。法语和德语的游戏内显示仍需用户验证。

发布素材同时经 `/api/agent/steam-workshop` 保存到工作台 `60e6bd70-eec1-4c3a-a357-fabd05badc3b`（“奇异矿物扩展 · 中法德本地化发布”），绑定用户条目 `3807689989`。中文说明版本 `a93fa6cd-bd8c-4c8e-bf6b-753dc01f87e4` 和原始封面版本 `17adce49-96f2-470a-acdc-3ecd6b506f6d` 已选中；重新读取验证说明全文与封面 SHA-256 均一致。PNG 主图超出此游戏上传限制，工作台元数据记录了最终 JPEG 的路径、哈希与大小；交付包实际引用的是该 JPEG。

## 输入与准备

- 原归档 SHA-256：`6172b0f49135824271c887930c2601d9e92e36a314169756db8f78b14102e962`。工作流前后哈希一致；没有修改 Workshop 或 `PdxMods` 原件。
- 隔离提取清单：56 个文件，包括 22 个 Lua 和 34 个 PNG。
- 准备计划：`plan_242ef86e61ee47e48a3378572730238e`；Remis 项目：`18c2845f-40aa-4a9f-ad90-6b72013f12a9`。
- 准备选择是完整源码副本路线。准备记录已持久化，并保留供后续 Mod 更新匹配稳定 ID 使用。

准备顺序是：在“创建项目”选择 Surviving Mars → 进入独立 FPK 准备窗口并阅读隔离说明 → 检查归档和文本 → 选择“只准备文本（`text_only`）”或“完整国际化副本（`source_copy`）”。`text_only` 不改写 Lua，待审核候选不进入翻译 CSV，且依赖原 Mod；`source_copy` 包含全部资产，并仅改写已审核且可安全渲染的候选。存在硬编码文本时推荐后者。运行时 `overlay` 仍是高级 API 模式，不是此用户流程的选项。

## 翻译与静态检查

- 翻译作业：`13ad51f1-e272-49ca-99f5-0ceb08e63adc`，OpenAI 直连模型 `gpt-6-luna`，88 行，单批完成；高级特性关闭。
- Remis 校验结果：0 errors、0 warnings。作业响应没有返回费用金额，因此此记录不对费用作零成本断言。
- 交付 CSV 中有 88 个唯一的 ID，译文全部非空。文本含 27 个真实换行、0 个字面 `\n` 序列。
- 选择 `text_only` 的对照预览：47 条现有数字 `T` 项，3 个文件，11,279 bytes；41 条硬编码候选不包含在此文本包中。由此可见文本包不会覆盖 Lua 硬编码文案。
- `ChoiceList` 内部枚举值保持原样；本结果不声称所有游戏内可见英文都已发现或翻译。

## 源副本交付

- 最终交付计划：`plan_8530961bbfef482a82a98e69db8ed319`。
- 输出位置：`.runtime/mars_pipeline/runs/plan_242ef86e61ee47e48a3378572730238e/deliveries/plan_8530961bbfef482a82a98e69db8ed319`；交付回执已保存，同一准备目录内的 `acceptance-proof.json` 保存独立检查结果。
- 新 Mod ID：`Remisca294bd547cb`；游戏内标题带 `[Remis i18n]` 前缀。
- 57 个文件，总计 9,734,892 bytes。34 个 PNG 与提取源逐字节一致；22 个 Lua 文件通过独立 `luaparser` 语法解析检查。解析没有执行 Mod Lua。
- 完整副本仅清除顶层 `steam_id` / `pdx_id` 原发布编号，保留作者、说明、版本和嵌套依赖信息。SDK 将这两个字段标记为平台发布身份；新副本不应继承原发布关系。先前的试验交付目录保留，本记录只推荐上述最终交付。
- 原 FPK SHA-256 保持不变。输出生成在新的本地目录，不曾安装到游戏或发布到 Workshop。
- 同日后端测试：152 passed、2 skipped。覆盖解包、Lua 发现/准备、交付、模式切换、持久化失败、Agent API、CSV 标签和换行；Python 架构检查与编译检查通过。
- `tools/remis_fpk` 的社区构建产物包含 wheel 和 sdist，尚未发布。

## 桌面交互与维护性

真实浏览器在 `http://127.0.0.1:5177/#/project-management` 验证了名称 → 游戏选择 → 自动打开独立 FPK 窗口 → 检查实际归档 → 显示两种交付选择的顺序。真实检查显示 56 个源文件、88 条候选、41 条硬编码；完整副本初选 72 条并要求复核 16 条选项文案。切换文本模式自动重新预览为 47 条，说明未覆盖的 41 条，无需再点检查。返回已有 CSV 文件夹流程后，路径、复制/引用、源语言字段正常恢复。交互验收只预览，没有额外创建项目或付费任务。

`visual-fixtures.html?contract=mars-pipeline&theme=<theme>` 使用注入的静态控制器，不调用导入/导出服务。在 Victorian、Byzantine、SciFi、WWII、Medieval 五套主题逐一检查准备窗口；浅色主题原先的折叠标题和次要按钮对比不足已修复。展开候选区的文本、代码定位与复选框在浅色主题可读。此次五主题目视范围为新的准备窗口，不代表重新验收整款应用的所有页面。

- 前端相关测试 17/17：创建入口、检查前后选项、自动重预览、候选折叠、未批准导出阻断、跨项目/过期响应、文本模式和编码完整性。
- 全量 ESLint 错误检查、涉及生产文件的零警告检查、Vite 构建通过；中英文 locale JSON 解析通过。
- `CreateProjectModal.jsx`：157 → 197 行，增加窗口开关与 CSV 路线两个局部状态，无新增 effect。`ProjectDashboardView.jsx`：205 → 205 行；`ProjectManagement.jsx`：192 → 197 行，只增加准备完成回调。
- 新展示组件 `MarsPipelineImport.jsx` 161 行、`MarsPipelineDelivery.jsx` 97 行。导入组件只有候选勾选这一展示状态；请求、计划失效、提交与跨项目响应控制放在 hooks。
- 新 hooks：`useMarsPipelineImport.js` 54 行，一个聚合状态、两个生命周期 effect；`useMarsPipelineDelivery.js` 45 行，聚合状态和刷新计数、一个带中止控制的加载 effect。独立 service 负责 API 传输。
- 后端准备编译模块 584 行、交付模块 564 行，已按职责拆出 Lua 表达式、运行时 profile、元数据渲染、工作流协调和回执存储；未提高任何架构上限。实际 Mod 文件、翻译与构建产物均在忽略目录，未暂存、提交或发布。

## 手动安装边界与未验证项

若之后决定安装，将导出目录完整复制为 `%APPDATA%/Surviving Mars Relaunched/Mods/Remisca294bd547cb`，使 `metadata.lua` 直接位于该目录下。在启动器停用原 Workshop Mod 和旧翻译补丁，只启用这个源副本；测试简体中文时使用游戏语言 `Schinese`。本次没有执行复制或安装。

`runtime_verified` 仍为 `false`。游戏加载、建筑和事件升级、不同语言切换、旧存档兼容或迁移、Mod 加载顺序均未在游戏中验证。新的 Mod ID 意味着旧存档行为需要单独检查。源码候选计数和成功的静态校验都不能证明整个 Mod 的所有用户可见文本已本地化。

## 后续验收：项目发布身份与多语言副本

上述为最初交付时的验收边界。用户随后确认中文完整副本已部署有效，并提供法语 `Applications exotiques` 科技说明截图，段落、强调色、重音字符可正常显示。只记录已展示场景；德语、所有法语界面及存档兼容性仍未完成验收。

项目 `18c2845f-40aa-4a9f-ad90-6b72013f12a9` 已通过 Agent API 绑定自己的 Steam 条目 `3807689989`，输出 Mod ID 保持 `Remisca294bd547cb`。绑定以项目 ID 持久化在准备/导出目录之外，GET 返回 revision，PUT 只允许批准的首次绑定；拒绝原作者编号、过期 revision、损坏或身份不匹配的记录，不提供重绑或清除。完整副本预览指纹包含绑定快照，执行时重新读取，变化则阻断旧计划。

绑定后的交付：`plan_6c8c1a2a643648eb9bb41efe039ab717`，位于同一准备 run 的 `deliveries/` 下。60 个文件中，59 个非元数据文件与前一中法德包逐字节一致；元数据仅增加自己的顶层 `steam_id`。三种语言各 88 条、原有封面、BBCode 说明、代码和美术资源保持不变。原始 FPK 哈希不变，没有安装或上传。静态证据与脚本在 `.runtime/publication/exotic-minerals-expanded/identity-acceptance-proof.json` 和 `verify_bound_identity.py`。

此次后端 94 项聚焦测试通过，覆盖绑定存储/API、交付和 Agent API；前端 hooks/组件/五主题语义测试 24 项通过。Python 架构、编译、ESLint 和构建检查通过。`MarsPipelineDelivery.jsx` 从此次修改前的 97 行增至 111 行，无新增 state/effect；新展示组件 54 行，新绑定 hook 50 行（一个聚合 state、一个 fetch effect），导出 hook 45 → 51 行，API 和工作流状态仍与展示分离。

Remis 只保存本地绑定并生成带编号的完整副本；不验证 Steam 所有权，也不负责游戏编辑器或平台在条目不存在时的行为。没有实现自动打包上传。

真实浏览器再次打开项目管理中的该项目，确认完整副本区显示已锁定的 `3807689989`、正确工坊链接和“此前导出的文件夹不会改变”说明。此次 preflight 为 ready，开发版本 3.2.1，已核验最新正式发布为 v3.2.0，没有更新版本提示。

用户随后确认：德语已在游戏中查看，未发现问题；本次通过游戏编辑器上传后，确实更新了同一个 Workshop 条目，没有创建新条目。这是用户实测反馈，补充上述静态与单场景验收；不推定所有界面或存档迁移都已完整测试。由此，项目绑定 → 导出携带自己的编号 → 手动发布更新同一条目的实际链路已得到用户验证。

## 后续只读诊断：一个格式问题与语言工作目录

用户询问项目管理中的一个待处理格式问题。本次只读检查确认：项目仍关联 `zh-CN-prepared`、`Multilanguage-prepared`、`fr-prepared`、`de-prepared` 四个译文目录。状态计数来自旧共享目录 `my_translation/Multilanguage-prepared/workshop_issues.json`（生成时间 2026-09-25 18:20:35），对应德语条目 `908638955531`、CSV 行 75、错误码 `validation_surviving_mars_tag_mismatch`，缺少一对 `<em>` / `</em>`。旧共享 CSV 中这项错误仍存在，并非凭空生成的警告。

当前 `zh-CN-prepared`、`fr-prepared`、`de-prepared` 以及最新包 `plan_6c8c1a2a643648eb9bb41efe039ab717` 的三份语言 CSV，各有 88 个唯一 ID；与源文比较，源 Text、标签和换行检查均通过。当前法德目录没有对应的新格式问题 sidecar；项目的 `ValidationSidecarService` 从已关联目录的报告中选中旧共享目录，因此概览仍为 1。概览计数并不是每次针对最新交付包重算的结果。未改写旧 CSV、删除目录/报告或清零计数。

现有后台火星 CSV 校对读取接口可返回当前法德文件的 88 个条目及修订号；它与尚未完善的专用可视化校对界面、自动标签/换行校验是不同能力。本轮没有新增校对 UI。后续若修复状态展示，应让记录按当前语言文件和修订绑定、保存后刷新对应 sidecar，并明确保留旧共享副本自身的未解决问题，不能无条件抹掉报告。

`fr-prepared`、`de-prepared` 等是正常流程保留的分语言译文工作文件，支持后续修改、复用和重新导出；`Multilanguage-prepared` 是此前共享输出尝试的旧目录，目前仍注册在项目中。交付物是独立的 `package_path`，其中同时注册 Schinese、French、German 三种语言，并不是把三个工作目录各自安装成 Mod。新增测试覆盖 `text_only` 和 `source_copy` 两种模式，将三语言合成一个 metadata.lua/Mod ID 并分别验证语言表及注册路径；两项均通过。相关帮助、能力接口、多语言输出和交付聚焦验证共 106 passed、1 skipped；跳过项为已有可选测试，另有既存 pykakasi 弃用警告。

用户指南、文档登记、Help Copilot 的技能目录/操作说明、Codex Skill/API 参考现已统一 FPK 导入 → 翻译 → 合并交付 → 两种安装启用方式 → 游戏 Mod Editor 手动上传的步骤。动态 `source_pipeline` 也提供指南路径、多语言包、发布绑定、手动安装及上传边界。检索测试验证用户问法能在技能目录找到入口、实际加载随应用打包的指南并进入回答上下文；没有执行付费模型回答测试。
