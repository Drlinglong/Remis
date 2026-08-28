# Key context 与目标语言规则的因子实验

本工具为 Issue #207 一类 `*_ADJ` 组合式本地化问题提供可复现的测试场地。它不会默认调用模型；只有显式加入 `--confirm-model-usage` 才会执行模型请求。

## 主实验设计

主实验是一个 2×2 因子设计。两个因素分别是“是否给出原始 key”和“是否注入目标语言形态规则”。

| 组别 | 原始 key | 目标语言规则 | 用途 |
| --- | --- | --- | --- |
| A | 否 | 否 | 当前生产基线 |
| B | 否 | 是 | 规则的主效应 |
| C | 是 | 否 | key 的主效应 |
| D | 是 | 是 | 两者组合及交互效应 |

可选 E 组只使用紧凑语义 hint，不再叠加完整目标语言规则。E 是探索性对照，不纳入 A–D 的主因子结论。它用于判断“受控语义信息”是否比直接暴露原始 key 更有效，并让定义轨道能够公平比较 A/C/E。

F/G 是更接近生产约束的探索组：F 用冻结的 Victoria 3 官方国家 TAG 集合在本地识别 `TAG_ADJ` 定义和引用，只注入通用 semantic type，不发送 raw key，也不提供 `possessive/direct_compound` 等答案级 relation；G 发送 raw key 并注入目标语言规则。所有组共享“每条输入独立、禁止使用同批其他条目展开或硬编码变量”的安全规则。F 当前刻意不识别 MOD 自定义国家。

H 在 F 的确定性路由之上加入对应目标语言规则，但仍不发送 raw key。它不是倾倒所有上下文：未命中官方 `TAG_ADJ` 的普通条目没有 semantic hint；规则仅有当前目标语言的一条；不会提供官方答案、其他条目的译文或答案级 relation。

H2 保留 H 的最小上下文边界，但不再把所有语言统一描述为 `reusable_country_entity_stem`。它为每种目标语言声明 definition 的实际 runtime form，以及 reference 必须围绕该 opaque form 采用的句法策略。例如德俄使用可组合词干，法西巴葡使用固定阳性单数 canonical adjective，波兰语使用官方阴性单数主格槽，土耳其语把槽视为词性不统一的不透明 country-related lexeme。H2 仍不发送 raw key 或具体官方答案。

生产使用的官方国家 TAG 目录位于 `data/config/key_context/vic3_official_country_tags_v1.json`，由 `game/common/country_definitions/*.txt` 机械生成并记录每个源文件 SHA-256；benchmark fixture 保留同内容的冻结副本。重新生成生产资源命令：

```powershell
python scripts/developer_tools/build_vic3_country_tag_catalog.py `
  "I:\SteamLibrary\steamapps\common\Victoria 3\game\common\country_definitions" `
  data\config\key_context\vic3_official_country_tags_v1.json
```

Raw key 组使用无歧义字段 `Localization key: "CHI_ADJ"; Source value: "Chinese"`。不要把 key 包在 `[CHI_ADJ]` 中；Victoria 3 生产 prompt 会把方括号识别为受保护函数语法，这会把 prompt 表示方式与“是否提供 key”这一实验因素混在一起。

注意：官方 fixture 自带 README 曾用 A/B/C 表示 value/raw key/semantic hint。这个 runner 的组别定义以上表和每份结果中的 `arms` 元数据为准；不要跨协议只凭字母比较。

所有组都从同一个生产 prompt 构造路径开始，只替换输入块；A 组必须与生产 prompt 完全相等。执行顺序由固定 seed 随机化。同一模型、配置、case 和 repetition 构成配对单元。对存在采样随机性的模型，正式实验建议至少运行 3 次，并固定 temperature、reasoning 等设置。

## 数据与评分边界

正式语料使用 `vic3-adj-multilingual-v1`：10 个统一 case × 10 种官方目标语言，共 100 个官方目标译文。runner 会把每种语言进一步拆成 5 个定义项与 5 个引用句两个独立批次，避免两条轨道在同一 prompt 内互相提供信息。应固定 fixture 内容与 `corpus_fingerprint_sha256`，不得在不同组之间修改语料。

评分必须分层：

- `adj_definition`：官方值可作为严格、可复现的精确金标准。
- `adj_reference`：先检查变量、格式与解析等硬约束，再做隐藏组别的人工自然度评审。官方译文是参考，不是唯一合法字符串。
- key 泄漏单独计数。
- 延迟单独记录，不与质量合并成单一总分。

定义轨道可把 runner 的 A/C/E 分别解读为 value-only、raw key、semantic contract；不要与 fixture README 的旧 A/B/C 字母混用。E 的 hint 明确包含 `semantic_type=country_adjective_definition`、目标语言和 `target_contract`，不只是换一种格式重复 raw key。

引用 token 会解析成 `{base_key, modifiers}`。例如 `$BHT_ADJ|l$` 的底层 key 是 `BHT_ADJ`，修饰符是 `l`。生产硬约束仍要求整个 token 原样保留；分析层另行区分“底层 key 仍在但修饰符变化”和“`$POR_ADJ$` 被替换成 `$POR$`”两种情况。后者记为 token substitution，不能归入普通措辞差异。

部分官方引用句会硬编码改写或消去变量，而 Remis 的生产约束要求保护变量。这种冲突应同时报告为“官方自然度证据”和“生产结构约束”，不能把其中一方悄悄覆盖掉。

生产 MVP 已接入 H2：只对官方目录命中的 country `TAG_ADJ` 定义与引用注入语义 metadata 和当前目标语言的一条 policy，不发送 raw key，也不假定任意 `_ADJ` 都是国家。定义项按各语言 runtime form 翻译；引用 token 仍由原有变量与格式 validator 严格保护，同时额外写入不可交给模型自动修复的人工复核项，用于检查词序、助词和词形协调。官方简中可能存在 `GBR=大不列颠`、`GBR_ADJ=不列颠` 等差异，因此实现不会强制 `TAG_ADJ == TAG`。

当前范围只覆盖 Victoria 3 与十种已评估目标语言。格式作用域的可靠修复、其他游戏的语义目录与语言契约、以及生产命中率、review 率、validator 错误率和实际账单的持续监控，均属于后续工作。

### 定义与引用的组合评分

`tests/fixtures/vic3_adj_composition_zh_cn_v1/cases.json` 是独立 companion fixture，不修改冻结的多语言 v1。它把定义输出与引用输出按 arm 和 repetition 配对，再执行变量展开。评分分别记录：

- 定义是否为官方可复用实体形式；
- 引用是否保留变量与修饰符；
- 引用自身是否命中金标（仅诊断，不作为引用质量的主要判据）；
- 用该 arm 的定义输出展开该 arm 的引用输出后，记录 exact gold，但把自然度与语义完整性留给盲化语言评审；
- “形态被塞进定义、引用处省略形态”即使展开文字碰巧相同，也因实体定义污染而失败。

Fixture 同时包含需要连接助词的 `$POR_ADJ$的关系`、`$HUN_ADJ$的实力`，以及无需连接助词的 `$BHT_ADJ$起义`。具体短语只存在于 gold，不写进共享 prompt policy；模型必须根据简中句法自行判断。

`tests/fixtures/key_context_production_mixed_zh_cn_v1.json` 进一步取消定义/引用分轨提示，把 `Chinese`、三种 `$CHI_ADJ$` 使用位置、普通 UI 标签、国家含义句和语言含义句放进同一个 production-like 批次。它用于检查 value-only 模型是否真的能在没有 “definitions-only” 泄漏时识别可复用定义，并对同一 arm 的输出执行“中国文化 / 中国的实力 / 中国人”组合评分。

免费检查完整 A–E 组合计划：

```powershell
python scripts/developer_tools/evaluate_key_context_factorial.py `
  --fixture tests\fixtures\vic3_adj_composition_zh_cn_v1\cases.json `
  --arm A --arm B --arm C --arm D --arm E `
  --estimate-prompt-tokens `
  --dry-run
```

若要在原始五定义实验中排除 `American/British` 官方词汇选择的干扰，可给所有 arm 加载同一冻结 lexical control：

```powershell
python scripts/developer_tools/evaluate_key_context_factorial.py `
  --fixture tests\fixtures\vic3_adj_multilingual_v1\cases.json `
  --case vic3_adj_simp_chinese_definitions `
  --lexical-control-fixture tests\fixtures\vic3_adj_composition_zh_cn_v1\cases.json `
  --arm A --arm B --arm C --arm D --arm E `
  --dry-run
```

OpenRouter benchmark 调用会为每一次 attempt 保存经过安全筛选的响应头、完整 completion 响应、router metadata、provider、generation ID、原生 input/output/reasoning/cache usage 与 cost。失败 attempt 同样保留，避免把上游空响应误判成翻译质量失败。异步 generation 查询若尚未可用会原样记录状态；不得用延迟反推 token 或缓存。其他 provider 仍只提供旧的文本级证据。

真实运行会在每个 case 完成后原子更新 `*_checkpoint.json`，中断时已完成结果不会丢失。`--request-timeout-seconds` 控制 benchmark 专用的单 attempt 超时；`--openrouter-reasoning-effort` 把推理档位显式写进请求和报告。正式多语言矩阵应优先使用 checkpoint 或异步 batch，不能依赖只在全量完成后才落盘的内存结果。

引用硬约束比较变量、修饰符与显式格式标记的完整性。Victoria 3 Wiki 将 `$key$` 定义为本地化复用，将 `#format … #!` 定义为显式格式范围；当前游戏的 `textformatting.gui` 把 `V` 映射为 `variable` 风格。生产 Victoria 3 prompt 因此要求格式边界继续包裹原来的受保护 token，允许为目标语言语序移动完整格式片段，但禁止跨过受保护 token 或把格式重新绑定到别的内容。当前 validator 仍只把 marker 数量失配作为确定性失败；数量相同但位置变化的案例进入人工复核，直到实现可靠的嵌套格式解析器。

引用轨道的最终等级使用 `FULL / PARTIAL / FAIL`：确定性代码负责变量和修饰符硬约束；盲化语言评审只判断语义完整性与目标语言通顺度。官方逐字一致只作参考，单个 LLM judge 也不是金标。当前评审可以交给本地 Codex subagent 或人工完成，不需要额外调用付费 judge API。

## 使用方法

先做完全免费的计划检查：

```powershell
python scripts/developer_tools/evaluate_key_context_factorial.py --dry-run
```

默认 fixture 即仓库内的 100 个官方目标样本；`key_context_factorial_smoke_v1.json` 只用于 runner 自测，不能作为质量结论。

对官方多语言 fixture 做计划检查：

```powershell
python scripts/developer_tools/evaluate_key_context_factorial.py `
  --fixture tests\fixtures\vic3_adj_multilingual_v1\cases.json `
  --repetitions 3 `
  --estimate-prompt-tokens `
  --estimate-luna-batch-cost `
  --dry-run
```

Luna batch 成本估算采用 [OpenRouter 当前公开价格](https://openrouter.ai/openai/gpt-5.6-luna:batch) 的 `$0.10/M input`、`$0.60/M output`，并以 Aventine 的 Luna 无推理与高推理历史 usage 比率给出区间。中推理没有可核验历史比率，因此不伪造中点，规划时使用高推理作为保守上界。reasoning token 已包含在 billed output 中，不会重复相加；缓存折扣默认按 0 估算。

当前冻结计划的估算如下（美元，实际账单仍以 OpenRouter usage 为准）：

| 计划 | Input estimate | 无推理历史比率 | 高推理历史比率 |
| --- | ---: | ---: | ---: |
| 简中定义 A/C/E × 1 | 1,396 | $0.000377 | $0.000948 |
| 简中定义 A/C/E × 3 | 4,188 | $0.001130 | $0.002843 |
| 10 语言定义 A/C/E × 3 | 41,724 | $0.011263 | $0.028319 |
| 10 语言、定义与引用 A–D × 3 | 131,400 | $0.035469 | $0.089185 |

正式执行采用 OpenRouter 异步 Batch API：提交 `POST /api/beta/batches`，再轮询 `GET /api/beta/batches/:id`。不能只把同步 chat completion 的模型字符串改成 `:batch` 后假定已经得到 batch 折扣。

`--estimate-prompt-tokens` 会用本地 `o200k_base` 对每次完整渲染后的 prompt 分词，按 arm 汇总相对 A 组的 token 增量。它不调用模型，也不等于具体 provider 的计费 tokenizer 或生产账单。

加入探索性 E 组：

```powershell
python scripts/developer_tools/evaluate_key_context_factorial.py `
  --fixture tests\fixtures\vic3_adj_multilingual_v1\cases.json `
  --include-semantic-hint `
  --dry-run
```

先跑建议的定义项 A/C/E 对照：

```powershell
python scripts/developer_tools/evaluate_key_context_factorial.py `
  --track adj_definition `
  --arm A --arm C --arm E `
  --repetitions 3 `
  --estimate-prompt-tokens `
  --dry-run
```

真正调用模型时必须明确 provider、model，并显式确认：

```powershell
python scripts/developer_tools/evaluate_key_context_factorial.py `
  --provider lm_studio `
  --model MODEL_ID `
  --fixture PATH_TO_CASES_JSON `
  --repetitions 3 `
  --confirm-model-usage
```

非 dry-run 默认最多执行 500 次模型调用；超过时必须显式提高 `--max-model-calls`。runner 会在首个请求前渲染检查全部 case × arm 组合，遇到 Hunyuan 等自定义、不兼容的 prompt 结构会零调用退出。执行请求时沿用生产侧的全局限流与重试次数，报告会保留每次成功所需的 attempt 数。

运行后会生成三份文件：原始结果、隐藏 arm 身份的人工评审文件，以及单独保存的解盲映射。盲评文件使用匿名 item id，不显示自动硬约束分数；人工判断冻结后才应读取映射。若模型直接在译文中泄漏原始 key，候选本身仍可能暴露处理组，因此 key 泄漏必须单独报告，不能声称这种候选保持了完全盲态。

## 决策标准

本实验用于量化 trade-off，不预设一定要把 key 加入生产 prompt。最终决策至少同时检查：

- 定义项是否更接近官方组合式形态；
- 引用句是否自然且没有双重助词、错误词尾或错误 demonym；
- JSON、变量、格式与输出数量是否仍然可靠；
- 延迟、实际 input/output/reasoning token、cache usage 与账单变化；
- 效果是否跨语言、跨 case 和重复运行稳定。
