# 项目档案候选治理契约

本文定义 Mod Context 在局部抽取之后、摘要生成之前的确定性治理边界。目标是减少重复别名
与普通名词短语过度抽取，同时保留完整审计证据。

## 固定顺序

```text
原始提及
→ 确定性别名归并
→ 候选类型判断
→ 后端计算覆盖
→ 分档与资格策略
→ 词典候选审议 / 摘要合成 / 仅审计持久化
```

事件范围先完成全局 reconciliation；候选治理只使用最终 local-unit delivery links 计算
事件链覆盖。模型不得返回覆盖数字、tier 或 eligibility flags。

## 别名与身份

英文候选的 `normalized_match_key` 执行 NFKC、大小写折叠、空白与首尾标点清理，并移除
开头 `a`／`an`／`the`。`aggregate_key` 保留既有 `entity:` namespace，例如：

```text
Horizon Signal      ┐
The Horizon Signal  ┴→ entity:horizon signal
```

`canonical_display_name` 与 `aliases` 保留真实词面。跨规范化键的
`canonical_candidate` 只作为语义建议，不自动合并，所以 `The Worm`、
`Worm-in-Waiting`、`The Loop`、`Strange Loop` 与 `Temporal Coil` 保持独立。

## 类型、覆盖与分档

候选类型只有：

- `entity`：稳定且可区分的人、地点、组织、物种、物体、群体、角色或反复出现的叙事对象；
- `glossary_term`：明确命名的技术、建筑、modifier、trait、项目、doctrine 或领域术语；
- `named_phrase`：需要一致翻译的标题、口号或独特命名短语；
- `incidental_concept`：普通描述、一次性观察、推测、孤立事实或泛化动作。

后端计算 `mention_count`、`source_item_coverage`、`local_unit_coverage` 与
`event_chain_coverage`。存在 local unit 时，policy coverage 使用去重后的 local unit 数；
否则回退到 source item coverage。`mention_count` 只作观测，不能靠一个 unit 内重复措辞晋升。

默认策略：

| 条件 | tier | 默认资格 |
|---|---|---|
| policy coverage 至少 3，或跨至少 2 条最终事件链 | `core` | 核心实体可合成摘要；非偶发候选可进入词典审议 |
| policy coverage 为 2 | `secondary` | 可进入词典审议，不生成实体摘要 |
| coverage 为 1，且是明确专名／游戏术语／翻译敏感表达 | `secondary` | 低优先级词典候选，不生成实体摘要 |
| coverage 为 1，且是普通偶发概念 | `incidental` | `audit_only`，不进入默认词典或翻译上下文 |

既有项目词典匹配、用户确认和显式 policy override 可以晋升候选。UI 与下游流程必须以
后端返回的 tier/flags 为准，不能从提及数或类型重新推导；显式 `audit_only` 始终留在折叠
审计区。

## 持久化与投递

所有 governed candidate aggregates 都写入 release traceability payload，包括别名、类型、
四项覆盖、policy reasons 与资格。只有以下 aggregate 进入 synthesis：

- event aggregate；
- project summary；
- `summary_eligible=true` 的候选 aggregate。

项目摘要排除 `audit_only` contribution。没有 synthesis 的次要／偶发 aggregate 不会进入
`effective_context`，因此不占翻译上下文预算。

`glossary_eligible=true` 只允许候选进入新词审议。它不是批准状态，也不能直接写入项目词典。

## 兼容与回归门禁

旧 release 没有 candidate policy 字段时仍可读取，UI 不显示空治理区。必须保留以下回归：

1. `Horizon Signal` 与 `The Horizon Signal` 共享 aggregate，但展示别名完整；
2. 语义近邻不会因字符串相似被合并；
3. 一个 local unit 内重复提及不会把偶发概念晋升；
4. core glossary term 不生成实体摘要；
5. audit-only candidate 持久化可追溯，但不进入词典候选、project summary 或翻译上下文；
6. 人工 tier/eligibility override 在工作流和 UI 中保持一致。

视界信号与毒圣骑士的冻结回归口径、身份门禁和单命令用法见
[Context Archive Demo 金标评分](context-archive-demo-benchmark.md)。
