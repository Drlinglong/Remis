# 术语审阅复用现有词典系统

此功能与 Batch 已纳入 v3.3.0 的高级 Agent API；模型审阅与术语覆盖扫描仍默认关闭，开放边界见[高级 API 策略](advanced-agent-policy.md)。编辑源是主数据库的
`Glossary` / `GlossaryEntry`，沿用词典管理页面、搜索、保存、删除及资产总览。
没有第二套可编辑术语库，也没有迁移现有数据库表。

`term-releases` 保存不可变发布快照，供异步任务固定输入。主词典的后续修改不会
改变已提交任务的提示词。旧的字面量发布接口和历史快照保留兼容；新工作流应从
主词典冻结，不能把历史快照误当成日常编辑来源。

## 随程序 release 分发词典

程序发行附件与上述 Batch `term-releases` 是不同用途。
`GET /api/agent/glossaries/{id}/terminology/distribution` 接受 `locale` 及
`expected_fingerprint`，只读获取主词典的一致发布快照。保留有效审阅状态、
置信度、英文别名、语境和简中参考；排除 pending / rejected / 缺少译文的词条。
输出只保留公开证据 ID 和哈希，自由文字中的本机证据路径转换为文件名。
返回的 `import_payload` 沿用现有术语导入格式，`approved` 默认 false；
不会自动创建、绑定、修改或替换任何词典，也不会调用模型。

经过审查的英／简中与三语快照存入
`assets/release_glossaries/surviving_mars/`。release 构建仅读取这些静态资产，
不依赖高级接口、Batch 服务或本机数据库。每次生成带程序版本号的词典附件，
保留独立资源版本；更新输入后需要提高资源版本并刷新文件哈希。
实际发布步骤见 [发布构建指南](build-release-script-guide.md)。

## 数据与审阅

词条的 `translations` 保存英文、目标语言及简中参考。`raw_metadata.terminology`
保存概念 ID、源 ID、含义、语境限定、证据、模型审阅来源、置信度、初稿、模型建议、
模型理由及人工决定；语言由 `locale` 区分。相同英文的不同概念保留不同 entry ID。
置信度是定性审阅优先级，不是实测正确率。人工确认也不代表台湾母语或专业认证。

状态包括 candidate、reviewed、pending、approved、rejected。暂定快照可包含前三种中的
candidate 和 reviewed，以及 approved；pending、rejected 和空译文会被明确排除并列出。
正式 approved 快照只允许所有纳入词条已确认。review_basis 绑定原文、译文、含义和
语境；修改这些内容后，旧确认失效，界面与快照都按 candidate 处理。

界面不新增状态或网络调用：新的术语字段组件由现有表单控制，元数据处理是纯函数。
普通词条不显示术语字段。正體中文通过 `glossary_languages` 提供给词典页面，
没有将它伪装成 zh-CN，也没有声明游戏新增官方语言加载槽。

**翻译边界：** 本次打通编辑与审阅，以及冻结给新工作流使用。现有普通翻译器的
字符串匹配不能保证执行 source ID / context_keys 限定，同名多义词不可直接当全局
替换表使用。后续对比试译与 Batch 应使用冻结快照及其语境匹配，不应退回旧的
`英文 -> 中文` 扁平映射。100 条普通 API 模型对比和全量翻译尚未运行。

## Agent API 操作顺序

每次受管工作流先调用 `/api/agent/preflight`。所有写操作需 approved=true；
这是记录已有用户授权，不表示导入后需要再收费。下列操作没有模型调用。

1. `POST /api/agent/glossaries/terminology`：传 game_id、locale、name、description、
   import_key、terms、approved；大型 Mod 另传 scope_id。terms 沿用 TermDefinition，
   加 review_state、confidence、source_id、reference_translations、original_candidate、
   audit_reason、audit_suggestion。创建独立标准词典，不替换主词典、不绑定项目。
   相同 import_key/输入幂等，重复导入保留后续人工编辑和删除；同 key 不同输入拒绝。
2. 返回 glossary_id 和 source_route；浏览器为 HashRouter，打开
   `http://127.0.0.1:FRONTEND_PORT/#` 后接 source_route。选择词条即可在原编辑侧栏审阅。
   人工编辑继续使用原来的词典保存接口，不直接写数据库。
3. `GET /api/agent/glossaries/{glossary_id}/terminology?locale=zh-TW`：返回 fingerprint、
   eligible_count、review_states、excluded，供确认下一次写入基于哪个版本。
4. `POST /api/agent/glossaries/{glossary_id}/terminology/review`：传 locale、
   expected_fingerprint、reviewer、changes、approved。每项 change 含 concept_id、
   review_state、reason，可另给 translation 和 sense。事务内校验当前指纹和全部概念，
   然后一次应用。保留模型证据及人工决定前的译法/含义。任一异常全部回滚。
5. `POST /api/agent/term-releases/from-glossary`：传 glossary_id、locale、version、
   maturity、expected_fingerprint、approved。从一致读快照生成发布物；指纹变化拒绝。
   返回 origin.glossary_id、origin.fingerprint 和排除项，供反向追溯。
6. `GET /api/agent/term-releases/{id}` 回读，再在 Batch 计划引用 term_release_id；
   provisional 版本仍需 allow_provisional_terms=true。冻结版本不能覆盖，改动用新 version。

导入使用主数据库事务及原来的表结构。发布物沿用内容寻址的不可变 artifact；
导入、审阅、冻结都不读取外部证据路径，也不读取或返回 API 密钥。

## 本轮实例与检验

隔离开发后端 1456，前端 5176，正式应用的旧界面不会自动获得这次功能。
本轮官方简中导入 1711 条；正體导入 278 条。玲珑在 2026-10-06 确认 23 项：
18 项修订决定、4 项待决词及 MOXIE。当前 23 approved、110 reviewed、145 candidate。
Core 系列保留核心命名，Extractor AI 用採掘站人工智慧；待决词使用愚鈍、體貼、
吃苦耐勞、太空復健，MOXIE 的中文显示名使用製氧機。

源候选和 Sol 原始审阅不覆盖；当前编辑库经 API 回读生成可读审阅表与新快照。
接口回执记录在独立 ModdingNotes 目录，未提交生成物。旧 v0.1.1 快照保持原样。
v0.1.2 是暂定快照，包含 278 条，并不是全量游戏翻译或游戏内语言质量验收。

测试覆盖主 DB 与原编辑 API 共用词条、并发幂等导入、不覆盖编辑/删除、多义词分开、
待决排除、人工确认、指纹冲突全量回滚、冻结后的修改隔离，以及真实 HTTP 路由。
前端测试覆盖原表单确认/保存、保留参考译文和证据、修改导致确认失效及 11 语言完整性。

## 社区旧译与语境审阅规则（2026-10-06 后续）

以英文概念、完整说明和游戏机制核实语义；简中与历史社区译名同时作为参考。
历史译名有助于降低玩家理解成本，但并不自动证明台湾用语自然，也不能替代机制审阅。
准确、自然的旧名优先保留；机制误解、错配语境或明显用语问题才修订。纯风格差异不必改名。
简繁转换本身不构成错误，不把所有旧词撤回，也不因“社区使用过”就自动批准。
用户明确确认的译法优先于模型建议，模型不得回写覆盖；台湾母语使用评审仍是独立验证维度。
居民特质可以使用自然的名词或形容词，不强制全部加“者”。术语审阅需检索同物件的
DisplayName、Description、ShortDescription、flavor 和实际效果，不能只读标题或内部 ID。

当前使用作者公开的 2020 历史版本：revision `249143.cht.200125.1`，commit
`19f10b308317d46604cc1395fe7faa525e09679f`，CSV SHA-256
`dfdf90c8f2086e4fdce29086a7eb0a10708645f3962e7c4efa74e205bcb8f2fe`。
它与 Workshop 1749276214 的历史社区项目关联，不能声称已核验当前本机订阅包。
`historical_reference.source_kind` 明确区分 author_public_history 与 subscribed_archive。

TermReviewChange 可带 historical_reference（历史 ID、英文、译文、语境、文件路径/hash、
workshop_id、source_kind、match_status）和 confidence。TermReviewRequest 的 review_origin：

- reference：只补充引用，必须保留译文、含义、置信度和审阅状态，不写人审/模型结论。
- model：只能写模型审阅记录，不能标记 approved，也不能覆盖人审确认项。
- human：保存人工决定。approved=true 仍是操作授权，不是自动质量批准。

词条侧栏显示“社区旧译”，便于同时查看英文、官方简中、社区基线、当前译法和审阅来源。
被冻结的术语 evidence_refs 带历史来源信息；模型提示仍不发送本机证据路径列表。
添加可选历史字段时，未提供该字段的旧导入请求保持原指纹，避免破坏幂等性。

历史一致性审计当时的 278 条中：205 条同 ID 同英文（102 原本一致、103 不同），72 条无同 ID 历史项，
1 条英文变化。对未人工确认的 89 个同 ID 差异、21 个跨 ID 同英文候选和 1 个英文变化，
Sol 共审计 111 条：89 high 建议沿用、9 high 保留当前、13 medium 保持待审。
当时实际修改 77 个译名；23 个用户确认项完整保留。当时编辑库 134 candidate、108 reviewed、
23 approved、13 pending；暂定 v0.1.3 快照含 265 条，显式排除 13 条待审。

水量量表、菱形穹頂和太空研究领域等语境冲突不盲目套旧词。Herbs 的前次审计只依据
Basil/Aromatics 保留“香草”，遗漏百科所述的健康加成；本轮以完整产出链和机制修正。
原稿、历史 CSV 与旧发布快照保持不变；审计、API 回执和最新回读表保存在
`terminology-v0.1/community-consistency-audit-20261006`，未运行付费 API 或全量翻译。
上述计数描述 v0.1.3 审计时点，后续实时状态应读取主词典 API；冻结快照不随编辑变动。

本轮机制复核材料为 `community-consistency-audit-20261006/mechanism-review-20261006.json`。
“纖維肌肉”有 carbon fiber 风味文本依据，“鍛鋼”没有 smelting 文本支持。
Sustainability 的研究领域与历史穹顶命名必须分开；“雙尖塔建築”是依据解锁效果提出的
功能性改译，不应把原文 spiral 与 spire 当成同义词。建议、用户决定和已应用状态分别记录。

随后玲珑确认这十项建议。主词典通过 human review API 更新九项，已确认的 Herbs 保持不变；
其余 268 个条目不变。当前 278 条的状态为 33 approved、107 reviewed、134 candidate、
4 pending。最新暂定 v0.1.4（`terms_2b0191f02045f3a5f82cbeab`）含 274 条，排除四项待审；
旧快照保持不变。用户确认与 model reviewed 分开，不能把这些状态等同台湾母语认证。

历史复核版本将 review_basis 与人工保护规则拆到单独纯政策模块；展示组件从 41
增加到 46 行，不增加 state/effect 或网络调用。历史参考、模型复核与人工决定分别保存。
相关验证继续覆盖主库/HTTP 流程、旧导入指纹兼容、参考只读补充、禁止模型伪装人审、
禁止覆盖人工决定和所有语言的新标签。

本轮验证：前端全量 254 文件 / 1052 测试通过，相关后端 84 测试通过；
Python compileall、架构门禁、UTF-8 完整性和前端构建通过。Lint 无错误，13 个既有
警告保留，没有新警告。真实页面已核对两份词库、正體中文选项、製氧機与人工决定。
EditTermForm 274→280 行，GlossaryManagerPage 478→484 行，旧 useGlossaryActions
仍为 891 行（仅替换配置读取表达式，不增加责任）；新增展示组件 41 / 17 行，
元数据纯函数 46 行。没有新增 React state/effect 或前端网络请求。API/工作流状态
仍由原 hook 管理，术语元数据处理与展示分开；不提高任何冻结复杂度或文件长度限额。
# 向现有词典追加术语

`POST /api/agent/glossaries/{glossary_id}/terminology/append` 接受 `locale`、当前预览的
`expected_fingerprint`、`terms: ReviewedGlossaryTerm[]` 和 `approved: true`。
它在同一现有词典数据库内新增词条，原编辑界面立即可见；不创建另一个词典，也不改旧词条。
重复 concept_id、旧指纹、语言冲突或缺少授权会拒绝整个追加。已有概念仍走 review，不用 append 覆盖。
追加后可从新预览指纹冻结新版本；旧 release 和既有任务请求保持不变。

2026-10-06 用户审阅后，词典 291 追加 Renegade / Renegades → 叛逆者，简中对照为叛徒。
v0.1.6 为 provisional，275 条，release `terms_076e017c92b5733605303115`。
v0.1.5 的 274 条逐条未变；本次 40 条对照仍绑定旧快照，不能声称该测试使用了新增术语。
追加集成测试覆盖授权、原词条保留、旧指纹、重复概念、语言冲突和新旧冻结快照；词典测试 15 passed。
服务新增约 33 行（约 226 行总长），router 增加薄调用入口；没有前端状态/effects 或第二存储，架构检查通过。
