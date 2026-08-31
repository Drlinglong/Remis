# Victoria 3 国家形容词语义上下文

本文记录 Issue [#207](https://github.com/Drlinglong/Remis/issues/207) 引入的生产级 MVP：Remis 在不把完整 localization key 交给模型的前提下，为 Victoria 3 官方国家的 `TAG_ADJ` 定义和引用补充最小、可验证的语义上下文。

这是一份生产行为与维护契约。实验组、夹具、成本估算和历史结果见 [Key context 因子实验](key-context-factorial-benchmark.md)。

## 状态与范围

- 状态：已接入初次翻译和增量翻译主流程的 MVP。
- 游戏：仅 `victoria3`。
- 目标语言：简体中文、日语、韩语、德语、法语、西班牙语、巴西葡萄牙语、波兰语、俄语、土耳其语。
- 候选：官方国家目录中存在的三位 `TAG`，以及对应的 `TAG_ADJ` 定义或 `$TAG_ADJ$` 引用；引用修饰符如 `$BHT_ADJ|l$` 仍属于同一候选。
- 非目标：任意以 `_ADJ` 结尾的 key、Mod 自定义国家、其他游戏、自动证明译文在所有语言中都自然正确。

不满足上述条件时，路由会返回空 hint，条目继续使用原有 value-only 翻译流程。目录或规则资源损坏时也采用同一 fail-open 行为并写 warning，不阻断整个翻译任务。

## 为什么定义和引用必须协同

`TAG_ADJ` 不是一段孤立文本，而是会在运行时插入其他句子的本地化槽。例如简体中文需要同时满足：

```yml
HUN_ADJ:0 "匈牙利"
example_power:0 "$HUN_ADJ$的实力"
```

运行时显示为“匈牙利的实力”。如果把“的”写入定义，游戏会把并非国家实体一部分的字符也放进变量显示范围；如果定义使用“匈牙利”，但引用机械省略“的”，句子又可能不自然。因此生产策略固定为：

> 在保证目标语言语义完整、语言通顺的前提下，保留全部运行时变量与修饰符；定义项只提供该语言约定的可复用 runtime form，助词、词序和词形由引用位置负责。

不同语言的 runtime form 并不相同。中日韩使用可复用的国家实体形式；德语和俄语使用可组合词干；法语、西班牙语和巴西葡萄牙语使用固定的 canonical adjective；波兰语和土耳其语另有明确的不透明槽约束。因此实现不会强制 `TAG_ADJ == TAG`，也不会把一条中文规则机械套到所有语言。

## 生产数据流

```text
解析 localization 文件
  → 本地检查 game、target language、key/value 和官方 TAG 目录
  → 为命中条目生成 index-aligned semantic hint
  → 只注入当前目标语言的一条 morphology policy
  → 沿用原有 provider、JSON 输出、变量和格式保护流程
  → 写出译文并运行现有 validator
  → 对官方 TAG_ADJ 引用额外创建不可自动修复的人工复核项
```

初次翻译和增量翻译都会在构造 `FileTask` 时生成与 source value 一一对齐的 `semantic_hints`，并由 `BaseApiHandler` 消费。模型仍只返回 value JSON，Remis 不要求模型回显 metadata。

### 发送给模型的内容

定义项命中后，模型会看到类似：

```text
Semantic hint: "semantic_type=country_adjective_definition; ...";
Source value: "Chinese"
```

它不会看到 raw key `CHI_ADJ`，也不会看到同批其他条目的答案、官方目标译文或“这里一定要加的”之类答案级关系。

引用项的 source value 本身含有 `$CHI_ADJ$` 等受保护 token，因此 token 会照常出现在输入中；附加 metadata 只说明该 token 的 runtime form 契约和引用处的责任。目标语言规则只在当前 batch 至少有一个命中条目时注入，并要求仅作用于带匹配 metadata 的条目。

## 确定性路由契约

| 输入 | 路由结果 |
| --- | --- |
| Victoria 3、受支持语言、官方 `CHI_ADJ` 定义 | `country_adjective_definition` |
| Victoria 3、受支持语言、value 含 `$CHI_ADJ$` 或 `$CHI_ADJ\|l$` | `country_adjective_reference` |
| 未在官方目录中的 `XYZ_ADJ` | 不注入 |
| 其他游戏或未支持语言 | 不注入 |
| metadata 与 source value 数量不对齐 | 抛出对齐错误，不静默错配条目 |
| 目录或语言规则无法读取/校验 | warning 后 fail open |

识别过程完全在本地完成，不调用 LLM。官方 allowlist 避免把任意 Mod key 的 `_ADJ` 后缀误判成国家；代价是当前不会覆盖 Mod 自定义国家。

## 验证与人工复核

原有 validator 继续负责可确定判断的结构问题，包括变量、修饰符、格式标记和 concept 等受保护结构。H2 不放宽这些约束，也不允许模型为了让句子自然而删除变量、替换成基础 `$TAG$` 或硬编码国家名。

每条命中的官方 `TAG_ADJ` 引用还会写入：

```text
error_code=vic3_country_adjective_reference_review
severity=human_review
requires_human_review=true
```

这不是已证实的错误，而是对词序、助词、性数格或词形协调的保守复核信号。它会出现在 Workshop/Agent 的人工复核统计中，但被明确排除在模型自动修复范围之外。定义项不会仅因命中 H2 而创建该复核项。

质量判定采用三档：

1. `FULL`：语义完整、语言自然，并保留全部变量和修饰符。
2. `PARTIAL`：语义完整且语言自然，但静态引用被消去；对运行时会变化的变量，消去变量仍是 `FAIL`。
3. `FAIL`：句法或语义错误，或者破坏动态变量、修饰符、格式与其他硬结构。

官方译文可作为语言学参考，但官方有时会硬编码或替换变量，不自动等同于 Remis 的安全结构金标。

## 版本化资源

### 官方国家目录

`data/config/key_context/vic3_official_country_tags_v1.json` 包含：

- `schema_version` 和 `catalog_id`；
- 官方 `game/common/country_definitions/*.txt` 的相对路径与 SHA-256；
- `tag_count`；
- 规范化后的 TAG 列表。

更新 Victoria 3 语料后，使用官方安装目录重新生成：

```powershell
python scripts/developer_tools/build_vic3_country_tag_catalog.py `
  "I:\SteamLibrary\steamapps\common\Victoria 3\game\common\country_definitions" `
  data\config\key_context\vic3_official_country_tags_v1.json
```

生成后必须检查源文件指纹、TAG 数量、JSON UTF-8 解析和相关测试。不要手工把 Mod 自定义 tag 混入官方目录。

### 目标语言规则

`data/config/key_context/vic3_language_policies_v1.json` 为十种语言各保存一条 policy。代码中的 `DEFINITION_FORMS`、`REFERENCE_FORMS` 与 JSON policy key 必须完全一致；资源缺项会被视为无效。

新增或修改规则时应同时回答：

- definition 在运行时究竟提供国家实体、词干、canonical adjective，还是其他不透明形式；
- 引用位置可以在 token 外添加什么，必须避免什么；
- 哪些性数格、词尾或语序无法安全自动决定；
- 是否仍能原样保留 token 和修饰符；
- 何时应进入人工复核，而不是让模型猜测。

规则不得包含夹具答案或针对某一句 gold 的硬编码提示。

## 修改和扩展步骤

1. 先在冻结 fixture 中增加能同时覆盖定义与引用的证据，不要直接改生产 prompt。
2. 用 benchmark runner 比较原基线和候选规则；定义项可看 exact gold，引用项必须分开检查结构与语言质量。
3. 只有在契约稳定后，才更新 versioned resource 或确定性路由。
4. 为初次翻译、增量翻译、普通 provider、自定义 prompt provider 和人工复核边界补回归测试。
5. 运行完整翻译链的相关测试，确认未知 tag、其他游戏和未支持语言仍 fail open。

扩展到其他 Paradox 游戏时，应为该游戏建立独立的官方语义目录、runtime form 契约和 fixture；不能仅复用 Victoria 3 的 TAG allowlist 或语言规则。

## 测试门禁

最低检查：

```powershell
python -m pytest -q `
  tests/core/test_vic3_country_adjective_context.py `
  tests/test_initial_translation_task_service.py `
  tests/test_workshop_issue_export_service.py

python -m compileall -q scripts tests
git diff --check
```

修改 prompt 或格式规则时，还应运行对应 prompt、validator 和文本编码测试。正式质量结论必须来自冻结 fixture 的重复实验与人工语言评审，不能只凭 focused unit tests 或 exact string match。

## 监控与后续工作

MVP 发布后至少应分目标语言持续观察：

- definition/reference 路由命中数与占全部条目的比例；
- `vic3_country_adjective_reference_review` 的产生率和人工确认结果；
- 变量、修饰符、格式和 concept 的 validator 错误率；
- 用户报告中的语言协调问题；
- provider 返回的 input/output/reasoning/cache usage、延迟和实际账单。

当前代码尚未把这些指标汇总成专用 dashboard，因此不能把“prompt 已注入”描述为问题已经彻底解决。后续方向包括更可靠的格式作用域修复、减少无效人工复核、扩展更多游戏的语义目录，以及按生产数据继续修订各目标语言 policy。

## 代码入口

- 路由与资源校验：`scripts/core/vic3_country_adjective_context.py`
- 初次翻译接入：`scripts/core/services/initial_translation_task_service.py`
- 增量翻译接入：`scripts/core/services/incremental_preparation_service.py`
- 通用 prompt 接入：`scripts/core/base_handler.py`
- 人工复核导出：`scripts/core/services/workshop_issue_export_service.py`
- 自动修复排除：`scripts/core/services/workshop_writeback_service.py`
- Agent 分类：`scripts/core/services/agent_validation_policy.py`
- 核心回归测试：`tests/core/test_vic3_country_adjective_context.py`
