# Issue #198 Luna/high 中文翻译 A/B 烟测

日期：2026-08-01

## 实验设置

- 源文本：英文叙事 demo Mod，共 7 个文件、84 个 localization entries。
- 模型：OpenRouter `openai/gpt-5.6-luna`，high reasoning。
- 目标语言：简体中文。
- 两组均为 batch size 10、单并发、主词典开启、resume 关闭、Embedded Workshop 关闭。
- B 组（基础词典）使用没有 Context Release 的隔离项目；任务元数据记录 `context.status=missing`。
- A 组（项目档案）使用 release `a88f7f49-9023-40bb-8268-81f0e77e1528`；任务元数据记录 `context.status=ready`，源快照哈希完全匹配。
- 两组都通过 Remis 验证：0 error、0 warning、0 human-review item。
- 基础组约 3 分 04 秒；档案组约 2 分 45 秒。单次运行不足以推断稳定延迟差异。

## 机械统计

- 两组都产出 84/84 条。
- 完全相同：13 条。
- 文本不同：71 条。
- 本测试未设置 seed，因此 71 条差异不能全部归因于项目档案；它是产品烟测和人工鉴赏样本，不是统计显著性实验。
- 最新档案版本包含一次用于验证 override 机制的 `entity:remis` 人工摘要修订，因此 A 组严格说测试的是当前 effective context，而非纯 generated synthesis。
- 当前项目档案的描述语言为英语；本轮不实现“描述语言”选项。后续该选项应控制实体、事件链和项目摘要供用户阅读时使用的语言，并记录进分析配置与版本元数据。

## 初步观察

1. 项目档案组没有稳定解决专名一致性。Meridian Gate、Kestrel Reach、Watch of Quiet Stars、Ledger-Breaker 等在同一组内仍有多种译法。
2. 档案组在部分语境判断上更好，例如把太空语境中的 Kestrel Convoy 译为“红隼船队”，基础组译为“红隼车队”。
3. 档案组出现了明确回归：`remis_aftershock_action_desc` 遗留英文 `ceremonial locks`。
4. 基础组也有明确问题：`first_contact.220.desc` 的引号转义出现重复弯引号；档案组该处更干净。
5. 两组的确定性验证均未发现这些语言质量问题，说明后续评价不能只依靠语法/格式验证。
6. 当前结果更支持“档案负责理解，正式译名仍必须由词典裁决”的原始边界，而不是让摘要自动承担术语统一职责。

## 人工鉴赏样本

### `character_remis_desc`

- 英文：Remis arrives with a red ledger chained to her wrist and the expression of someone who has already found the leak. The Cartographers' Guild calls her the Red Archivist; the Watch of Quiet Stars calls her the Ledger-Breaker.
- B｜基础词典：蕾姆丝抵达时，手腕上锁着一本链缚的红色账簿，脸上的神情像是已经找到了泄漏源。制图师公会称她为“红色档案官”；静谧群星守望会则称她为“破账者”。
- A｜项目档案：蕾姆丝抵达时，手腕上锁链拴着一本红色账册，脸上带着一种已经找出漏洞之人的神情。制图师行会称她为“红色档案官”；寂静群星守望者则称她为“破账者”。

### `place_meridian_gate`

- 英文：Meridian Gate
- B｜基础词典：子午门
- A｜项目档案：子午线之门

### `first_contact.220.desc`

- 英文：At §H [Root.GetCapitalName]§!, Remis hears a reply hidden inside the Accord of Echoes. The Cartographers' Guild calls it a route; the Watch of Quiet Stars calls it a threat. Remis, the Red Archivist, asks why a distress call would know her name.\n\n\"The signal is not a throne,\" says the Ledger-Breaker. \"It is a door.\"
- B｜基础词典：在§H [Root.GetCapitalName]§!，蕾姆丝听见了一段藏在《回声协定》中的回复。制图师公会称其为一条航线；寂静群星守望者则称其为威胁。蕾姆丝，这位红色档案官，想知道一则求救信号为何会知道她的名字。\n\n\““这信号不是王座，”\”账簿破坏者说道。\““它是一扇门。”\”
- A｜项目档案：在 §H [Root.GetCapitalName]§!，蕾姆丝听见了藏在《回响协定》中的回复。制图师公会称其为一条航路；静默群星守望者则称其为威胁。这位赤红档案官蕾姆丝问道：一则求救信号为何会知道她的名字？\n\n\“这信号不是王座，\”破账者说道。\“它是一扇门。\”

### `meridian_gate.221.desc`

- 英文：The ledger places Kestrel Reach beyond the next jump from Meridian Gate, yet its margin bears Remis's other title: the Ledger-Breaker. The Cartographers' Guild denies drawing it, while Remis says the Accord of Echoes has been keeping accounts.
- B｜基础词典：账簿将红隼边陲标在子午线之门下一跳之外，但其边注上写着蕾姆丝的另一个称号：账簿破坏者。制图师公会否认绘制过它，而蕾姆丝则说，回声协定一直在记账。
- A｜项目档案：账簿记载，红隼边疆位于子午星门下一跳之外，然而页边却写着蕾姆丝的另一个头衔：“破账者”。制图师公会否认绘制过它，而蕾姆丝说，《回响协定》一直在记账。

### `council.310.desc`

- 英文：The Meridian Council gathers at Meridian Gate. Remis presents the ledger from Kestrel Reach, while the Watch of Quiet Stars counts ships and the Cartographers' Guild counts omissions. The Red Archivist refuses to call either count proof.
- B｜基础词典：子午议会齐聚子午门。蕾姆丝展示了来自红隼边疆的账簿，静星守望团清点舰船数量，而制图师公会清点遗漏之处。赤红档案官拒绝承认任何一方的统计是证据。
- A｜项目档案：子午议会在子午门集会。蕾姆丝展示了来自红隼星域的账簿，而寂静群星守望团统计舰船数量，制图师公会统计遗漏项。红色档案员拒绝承认其中任何一种统计可以作为证据。

### `remis198_concord_branch`

- 英文：The Concord faction says the Accord of Echoes carries a genuine roster of forty-eight refugees, and Remis should carry the Meridian Seal to Kestrel Reach under the Mercy Protocol.
- B｜基础词典：协和派称，《回声协约》载有一份真实的四十八名难民名册，蕾姆丝应当依照仁慈协议携带子午印前往红隼边疆。
- A｜项目档案：协和派表示，《回声协定》记载着一份真实的四十八名难民名单，蕾姆丝应当依据《慈悲协议》携带子午印前往红隼星域。

### `remis198_warden_branch`

- 英文：The Warden faction says the Accord of Echoes carries forty-eight stolen clearance signatures, and the Watch of Quiet Stars must guard Meridian Gate until Kestrel Reach is quiet.
- B｜基础词典：守卫派称，《回声协约》载有四十八份被盗的许可签名，静星守望团必须守卫子午门，直到红隼边疆恢复平静。
- A｜项目档案：守望者派表示，《回声协定》记载着四十八份被盗的通行许可签名，寂静群星守望团必须守卫子午门，直到红隼星域恢复平静。

### `tech_accord_lattice_desc`

- 英文：The Echo Lattice converts the Accord of Echoes into a navigable signal for Meridian Gate. Remis warns that the lattice remembers every route, including the route by which the Ledger-Breaker first found Kestrel Reach.
- B｜基础词典：回声晶格将回声协约转换为供子午门导航的信号。蕾姆丝警告说，晶格会记住每一条路线，包括账簿破坏者最初找到红隼边疆的那条路线。
- A｜项目档案：回声晶格将回声协定转化为供子午门导航的信号。蕾姆丝警告说，晶格记得每一条路线，包括“账簿破坏者”最初找到红隼星域的那条路线。

### `resolution.400.desc`

- 英文：From the last charted approach, Meridian Gate answers across the route to §Y Kestrel Reach§! with two tones. Remis holds the Meridian Seal in one hand and the Cartographers' Guild ledger in the other, waiting for the Meridian Council's final order. The Red Archivist says the signal sounds like people; the Watch of Quiet Stars hears a fleet.
- B｜基础词典：根据上次标绘的接近路线，子午门在通往§Y红隼边陲§!的航线上以两种声调回应。蕾姆丝一手握着子午印玺，另一手拿着制图师公会的账簿，等待子午议会的最终命令。赤红档案官说信号听起来像人；寂静群星守望者听见的却是一支舰队。
- A｜项目档案：从最后一条有记录的进路传来回应，子午门沿着通往§Y红隼边陲§!的航线发出两种声调。蕾姆丝一手握着子午印玺，另一手拿着制图师公会的账簿，等待子午议会的最终命令。赤红档案官称这信号听来像是人声；静默群星守望会听见的却是一支舰队。

### `resolution.401.desc`

- 英文：The gate opens or locks according to the council's choice. Neither result changes the evidence that made the other side afraid. Remis orders both transcripts sealed, not because she trusts both stories, but because she remembers what certainty costs.
- B｜基础词典：子午门会按照议会的选择开启或锁闭。无论结果如何，都不会改变令另一方心生恐惧的证据。蕾姆丝下令将两份记录一并封存，并非因为她相信两种说法，而是因为她记得确信要付出什么代价。
- A｜项目档案：子午门会根据议会的选择开启或锁闭。无论结果如何，都无法改变曾令另一方心生恐惧的证据。蕾姆丝下令将两份记录一并封存，并非因为她相信两种说法，而是因为她记得确定真相要付出什么代价。

### `aftershock.410.concord`

- 英文：Concord consequence: the forty-eight refugees reach the archive alive, but one child insists the signal was answered by someone wearing Remis's voice.
- B｜基础词典：协约后果：四十八名难民活着抵达档案库，但有个孩子坚持说，回应信号的是一个使用蕾姆丝声音的人。
- A｜项目档案：协约结果：四十八名难民活着抵达档案馆，但有个孩子坚持说，回应信号的是一个借用了蕾姆丝声音的人。

### `remis_aftershock_action_desc`

- 英文：She removes the archive's ceremonial locks, puts the Cartographers' Guild maps on the floor, and makes the Meridian Council staff sort names by hand. Her reform is tedious by design.
- B｜基础词典：她卸下档案库的仪式锁，将制图师公会的地图铺在地板上，并让子午线议会的工作人员手工整理姓名。她的改革正是刻意设计得如此乏味。
- A｜项目档案：她拆除了档案馆的 ceremonial locks，将制图师公会的地图铺在地板上，并让子午线议会的工作人员手工整理姓名。她的改革正是有意设计得如此繁琐。

### `kestrel_convoy_desc`

- 英文：The Kestrel Convoy is the Concord name for the forty-eight life signs. The Watch of Quiet Stars refuses the name and calls it the Echo Decoy.
- B｜基础词典：红隼车队是协约对这四十八个生命信号的称呼。寂静群星守望团拒绝使用这个名称，而称其为“回声诱饵”。
- A｜项目档案：“红隼船队”是协约对那四十八个生命信号的称呼。寂静群星守望者拒绝使用这个名称，而是称其为“回声诱饵”。

### `remis_final_verdict`

- 英文：The Ledger-Breaker refuses both verdicts. \"A closed case is not a solved case. It is a door with better paperwork.\"
- B｜基础词典：破账者拒绝接受这两种判决。\“结案不等于解决。那只是一扇手续更齐全的门。\”
- A｜项目档案：破账者拒绝接受这两种判决。\“结案不等于破案。那只是一扇手续更加完备的门。\”

### `remis_ledger_reveal_desc`

- 英文：The Red Ledger's red cover was made from emergency marker cloth, and every page lists a person lost by a failing system. Remis's joke about state debts was literal: the state owed them a name.
- B｜基础词典：红色账簿的红色封皮由应急标记布制成，每一页都列着一个因系统失灵而失踪之人的名字。蕾姆丝拿国家债务开的玩笑是字面意思：国家欠他们一个名字。
- A｜项目档案：红色账簿的红色封皮由应急标记布制成，每一页都记录着一个被失灵系统夺走的人。蕾姆丝关于国家债务的玩笑是字面意义上的：这个国家欠他们一个名字。

### `meridian_gate_afterword`

- 英文：Meridian Gate remains open in the maps and closed in the reports. Remis keeps walking between the two.
- B｜基础词典：子午线之门在地图上仍然开放，在报告中却已关闭。蕾姆丝不断在两者之间行走。
- A｜项目档案：子午门在地图上仍然开放，在报告中却已关闭。蕾姆丝继续行走于二者之间。

## 作业审计信息

- 基础词典项目：`43396c46-97df-4232-822b-734774550cb4`
- 基础词典任务：`d619a292-c21b-4cc6-8e14-29f83660420c`
- 项目档案项目：`67660db1-af77-4e84-b836-1efb4338bbc6`
- 项目档案任务：`66bb04b4-9c96-4b95-a205-f342c8cb4778`
