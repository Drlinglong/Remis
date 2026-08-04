# 项目档案树状工作流 v2

状态：实施契约。旧的 v10 工作流冻结在
`codex/issue-198-context-v10-frozen`，新实现位于
`codex/issue-198-context-tree-v2`。本轮不修改人工金标。

## 目标

把模型判断收敛到两个位置：

1. 分块内理解文本并保存不可丢失的局部结果；
2. 全局判断哪些局部叙事片段属于同一个事件组，以及组内顺序。

覆盖计数、等级、投递关系、事件上下文组装和术语选择均由程序完成。
模型返回不完整时定向修复；修复失败时保留未解决记录，不静默删除。

## 名词与投递规则

### narrative unit

具有实质叙事意义的文本。翻译时接收：

- 项目摘要；
- 所属事件组的上下文；
- 实际命中的词典约束和实体摘要。

### reference asset

人名、地名、组织名、武器、科技、传统、建筑、修正及其他主要承担
名称或静态资产翻译的文本。翻译时接收：

- 项目摘要；
- 实际命中的词典约束和实体摘要；
- 不接收任何事件链摘要。

`reference_asset` 是 source/local-unit 的投递角色，不取代实体候选或术语
候选。一个人物名称所在的 unit 可以是 reference asset，同时该人物可以在
A/B 级后拥有实体摘要。

### no context

既无叙事投递价值，也不是需要项目一致性治理的静态资产。默认不接收档案
上下文；普通翻译规则仍然适用。

## 工作流

### #1 整理文本（程序）

沿用可追溯 local unit。保留 source item、路径、原始顺序和完整原文。

### #2 局部抽取（模型，分批）

完整档案模式与仅术语模式使用同一条 Prompt 和同一返回契约。模型返回：

- `local_fragments`：局部叙事片段 ID、简短摘要、unit IDs、组内延续线索、
  边界包含/排除信息；
- `unit_routes`：每个 unit 是 narrative、reference_asset 或 no_context；
- `entities`：实体候选、别名候选、局部描述和证据；
- `terms`：术语原文、建议译文、解释和证据；
- 既有事实/关系等审计信息可继续保留，但不得控制投递。

每个返回中的引用必须存在。若 unit 引用了未返回的 fragment，执行一次只补
缺失 fragment 的定向 repair。repair 仍失败时保存 unresolved 记录，不得删除
原始链接，也不得把该批次伪装成完整成功。

Prompt 明示每个 fragment 是否接触 chunk 开头或结尾、前后相邻 unit，提醒
模型分块边缘更可能把同一事件拆成多个局部片段。

### #3 候选治理（程序；实体摘要除外）

术语和实体候选先做确定性别名归并，再按 local-unit 覆盖计算等级：

- A：覆盖至少 3 个 local units；
- B：覆盖 2 个 local units；
- C：覆盖 1 个 local unit；
- 人工等级覆盖自动等级。

mention count 只展示，不用于等级。每个术语保留每个批次产生的全部 AI
译文和解释，不提前抹平冲突。

#### A/B 级实体摘要（独立、受预算约束的模型调用）

程序完成初步归并和覆盖计数后，将候选清单、项目摘要和受限原文证据发送给
模型。该调用负责：

- 对 A/B 实体及其可能别名做语义去重；
- 为最终 A/B 实体生成摘要；
- 返回所使用的 evidence unit IDs。

默认每个实体最多提供 12 个 local units、总计最多 8,000 个原文字符。采样
必须确定性地覆盖不同事件组、首次出现、末次出现和高信息密度片段，不能因
“Knight”贯穿整个模组而发送整个项目。C 级候选只以紧凑名称/局部描述参与
别名判断，不生成长摘要。最终等级在语义合并后由程序重新计算。

该预算只限制发送给摘要模型的内容，不得裁剪持久化证据。#2 在每个分块中
返回的实体描述、原文证据、批次来源和别名判断必须全部保留。高级界面展示
完整分块证据，并逐条标明 `included_in_digest`；用户应能对比机械拼接的局部
描述与 LLM 摘要。这样后续评估可以决定保留摘要调用，还是改为纯程序拼接，
而不需要重新运行 #2。

项目摘要优先使用人工已编辑版本；否则由程序从项目标题和事件组/局部摘要
构造有长度上限的项目概览，不增加单独的摘要模型调用。

### #4 全局事件编排（模型）

模型只接收不可变的 local fragment cards 和 chunk-edge 元数据，只返回 ID
结构：

```json
{
  "stories": [
    {
      "story_id": "story_toxic_god",
      "group_ids": ["group_syamelle", "group_finale"]
    }
  ],
  "groups": [
    {
      "group_id": "group_syamelle",
      "fragment_ids": ["fragment_a1", "fragment_a2"]
    }
  ]
}
```

语义约束：

- `fragment_ids` 的顺序只表示同一个 group 内部的顺序；
- sibling groups 之间没有时间顺序语义，`group_ids` 只用于稳定显示；
- 平行选择应成为不同 groups，不能强行判断先后；
- parent story 只组织档案，不是翻译投递目标；
- 模型不能重写局部摘要、重新绑定 unit 或删除 fragment；
- 每个 fragment 必须恰好进入一个 group，或明确保留为 unresolved；
- catalog 输出只引用已有 ID，不生成替代局部信息的新事件链。

### #5 投递关系（程序）

局部绑定直接投影到事件组：

```text
unit -> local fragment -> event group
```

不再对全部 units 运行最终 Assignment 模型调用。仅 unresolved 数据允许进入
显式的定向修复流程。

### #6 事件上下文（程序）

事件组上下文是其局部摘要按 `fragment_ids` 顺序组成的项目符号列表。不得再
调用模型生成覆盖局部事实的聚合摘要。项目档案显示：

```text
项目标题
+ unordered event groups
  + ordered local fragments
+ related reference assets
```

reference assets 只以关联引用显示，不获得事件上下文投递。

## 仅术语模式

仅术语模式仍执行 #1 和相同的 #2 Prompt，但持久化时只保留 `terms` 和其
证据；丢弃 fragments、unit routes、entities、facts 和 relationships。它不执行
全局事件编排、实体摘要或事件上下文构造。

程序按确定性别名归并后的 local-unit 覆盖计算 A/B/C，并保存每个批次给出的
全部译文和解释。审核界面允许用户逐项选择一个方案；“全部批准”时默认选择
稳定排序后的第一个方案，保存所选方案并删除其余待选方案。

## 前端审核边界

树状审核页用于编辑关系：

- 新建、删除或重命名 story/group 容器；
- 拖动 fragment 到其他 group；
- 调整同一 group 内 fragment 顺序；
- 将误判 fragment 改为 unresolved/reference asset；
- 预览某个 narrative unit 最终收到的事件上下文。

树状页可以查看节点摘要、等级、覆盖和证据，但不直接编辑节点属性。实体和
事件内容继续在既有详情/编辑入口修改。原始 source evidence 不可变；用户可
编辑派生实体和事件信息，且修改必须进入 draft/override 审计记录。

实体高级详情必须展示全部分块证据，而不只是摘要调用采样到的证据；采样内
与采样外证据应有清晰标签。默认普通用户仍只看最终 A/B 摘要和简明覆盖信息。

## 数据与兼容性

- 新 schema/prompt 版本与 v10 release 并存，不原地改写历史发布档案；
- 新建 fragment、event group、tree edge、reference-asset route 和 unresolved
  记录；
- tree draft 修改与正式 release 分离，发布仍保持事务性和幂等；
- 旧 aggregate/delivery/synthesis 表保持只读兼容，迁移不得删除历史数据；
- v2 评分必须使用新版本号，不能与旧 F1 直接比较。

## 本轮不做

- 不修改 Toxic God 或 Horizon Signal 人工金标；
- 不依赖 CWTools 推断静态资产与脚本效果；
- 不让 reference assets 获得事件摘要；
- 不把全局 assignment 或聚合 synthesis 以其他名字重新引入。

## 验收要点

1. 悬空 fragment 引用触发定向 repair，二次失败保留 unresolved。
2. 已绑定 fragment 的 unit 在全局编排后不会无理由变成 unassigned。
3. sibling groups 没有时间顺序语义，group 内顺序稳定且可人工调整。
4. narrative 翻译获得项目摘要与事件组上下文；reference asset 不获得事件组
   上下文。
5. A/B 实体有受证据预算约束的摘要；C 级无长摘要。
6. 术语模式不调用 catalog、实体摘要或事件上下文流程，并保存重复候选方案。
7. 树状 UI 只编辑关系；节点内容仍走现有编辑入口。
8. v10 发布档案可继续读取，新旧 schema 不混写。
