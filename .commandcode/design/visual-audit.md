# Remis 前端视觉审计与改良提案

> 审计范围：`scripts/react-ui` 全部可视层 — `DESIGN.md` 语义表面契约、五主题 token 体系、GlobalStyles 背景层、AppShell 布局、Home/项目管理/档案上下文树等核心页面与组件库。
> 目标：从“功能可用、设计感偏弱”提升到“专业、克制、主题自洽但现代”的桌面工作台质感。所有改良在不破坏语义表面与流程语义的前提下进行。

## 1. 总体诊断（一句话）

骨架扎实、契约先进、实现欠精：语义表面与五主题回归体系已经解决“可读性与可维护性”，但**层级、密度、版式、动效、材质精致度**五项仍处在“功能堆叠”阶段，导致界面看起来像“套了主题的后台”，而非“有美术指导的工作台”。

**首要处方：** 以 `recolor → typeset → relayout → refine/surface → motion` 的顺序做一轮系统化升级；每一步都受 DESIGN.md 与视觉可靠性门禁约束，并以 `VisualReliabilityLab` 与 Playwright 五主题截图为验收。

---

## 2. 做得对的地方（保留并发扬）

- **语义表面契约** (`definitions.css` + `data-remis-surface`) 非常前瞻：canvas/surface/paper/elevated 四层材质 + 每主题对比度达标，解决了多主题可读性的根本问题。
- **确定性夹具与浏览器门禁** 是硬资产：长路径、超长标识符、中英混排的回归能力为视觉改良提供了安全网。
- **主题世界观有辨识度**：五套主题各有材质隐喻（大理石/木纹/全息/档案纸/羊皮纸），不该被抹平成一套普通深色主题。
- **任务中心与档案树的信息模型清晰**：下一步可在此之上做层级强化，而非推倒重来。

## 3. 核心问题清单（按影响排序）

### P0 — 必须改

1. **层级扁平、锚点缺失。** 多个 `glassCard`/`surfacePanel` 同等重量地铺满页面，`DESIGN.md` 要求的“每工作区一个强视觉锚点、每屏一个主行动”未被视觉语言执行。`HomePage` 的问候语、实时作业卡与统计卡在视觉重量上几乎等价。
2. **双重主题系统打架。** `definitions.css` 的 `[data-theme]` 语义 token 与 `themes/*.css` 的 `.byzantine/.scifi` 遗留覆盖是两套并行系统（按钮、输入框、Title 阴影等被多处 `!important` 重写），导致同一组件在不同主题下行为不一致，维护成本与回归风险高。`theme.js` 的 `brand/dark` 调色板与语义 token 也未对齐。
3. **间距与密度不统一。** `HomePage.module.css`、`ProjectManagement.module.css`、`ContextArchiveTree.module.css`、`Layout.module.css` 各自定义了 `glassCard/glassPanel`，半径、边框、阴影、毛玻璃强度各不相同；`DESIGN.md` 要求的 4px 基准与 8/12/16/24/32 节奏未被系统化执行。
4. **`App.css` 与全局滚动条遗留债。** 残留的 `.logo/.card/.steps-content/.log-container` 与 `ant-menu` 样式未被使用；全局滚动条在 `App.css` 与各模块中重复定义；`index.css` 把 `html,body,#root` 锁死为 `100vh + overflow:hidden`，与 `MainLayout` 的嵌套滚动配合脆弱，易在新增页面时回归。

### P1 — 强烈建议改

5. **版式系统薄弱。** 中文长段落在小字号下行高与字距未做补偿；`--font-header/--font-body` 每主题声明了但未形成 type scale（字阶、字重对比、度量 60–76ch）；二级标题与正文的区分度不足。
6. **状态与空状态语言不统一。** 加载、空、错误、部分失败、被阻断等状态在各页面用 Alert/Badge/内联文本混排，次要信息不够“安静”，主要行动不够突出；部分空状态未达到“说明此处应放什么、为何重要、如何填入”的标准。
7. **动效与反馈缺席。** 除导航 `width` 过渡与零星 `hover` 位移外，几乎无入场/退场/排序动效；拖拽、筛选、分页等操作的反馈不明确，缺乏“身体语言”。
8. **侧边栏交互可精致化。** 80↔240px 的 hover 展开在桌面端可用，但在触控/窄视口下体验粗糙；图钉、徽点、分组标题的视觉重量可进一步收敛。

### P2 — 锦上添花

9. 背景材质（`GlobalStyles.css` 的多重渐变/噪点/扫描线）在部分主题下过重，与前景玻璃卡叠加后产生“纹理打架”；可在保留世界观的前提下做减法与降噪。
10. 图表与数据可视化的主题适配停留在默认色，需与语义 token 对齐并做色盲模拟校验。

### 复核增补（2026-08-07，基于五主题渲染截图与代码量化）

本次复核用 Playwright 五主题截图（视觉契约夹具 + 档案树真实页面）与样式层量化扫描验证了上述判断，结论全部成立，并作如下修正与补充：

- **P0-1 的根因确认——装饰权重原语缺失。** 截图眯眼测试五主题全灭：拜占庭每个面板 2px 金边、维多利亚 3px 双线黄铜、科幻全面辉光、中世纪 3px 金边。根本原因是每个主题只有**一根** `--surface-border`/`--glass-border`，面板无法"安静"。token 体系必须新增**安静/锚点两级装饰权重**（如 `--surface-border-quiet` / `--surface-border-anchor`），否则层级问题治标不本。
- **P2-9 升级为 P0，并提前至阶段 1。** 科幻主题背景同时叠加星空 + 4px 扫描线 + 2px CRT + RGB 色散条纹四层（`GlobalStyles.css`），动画扫描线直接穿过半透明面板；拜占庭金粉颗粒在玻璃卡后呈现"屏幕脏点"感。背景降噪成本极低、视觉收益立现，每主题只保留一个背景母题。
- **新发现：CJK 字体栈全主题缺失。** 五个主题的 `--font-body`（Lato/Georgia/Roboto/Arial/Times）均未声明中文回退；Cinzel/Orbitron/Playfair 无中文字形。中文为主的本地化工具，标题混排不可控——比行高补偿更根本。
- **新发现：`paper` 材质隐喻跨主题互相矛盾。** 纸面在拜占庭/二战/中世纪为浅色、在维多利亚/科幻为深色。对比度契约能兜底可读性，但"纸 = 证据文档"的心智模型在主题间翻转，是长期迷惑源。
- **量化证据：** `!important` 共 832 处、散布 40 个 CSS 文件（`definitions.css` 123、`ProjectManagement.module.css` 104、`ModArchive.module.css` 62、`JudgmentCourt.module.css` 57）；模块 CSS 硬编码圆角 10+ 种取值（0/2/3/4/6/8/10/12/14/16/999px），主题自身的圆角身份（科幻 0px、中世纪 12px）被模块随手打破；`glassCard` 模式在 27 个文件重复实现；`definitions.css` 无任何 `--space-*` 与字阶 token。

---

## 4. 改良策略（与 DESIGN.md 兼容）

> 原则：不动信息架构与语义表面契约；所有视觉改良通过语义 token 表达，不引入主题名分支与硬编码 hex。

### 4.1 策略一 — 收敛主题系统（先做，否则一切改良都会被覆盖打回）

- 以 `definitions.css` 的 `[data-theme]` 语义 token 为**唯一事实来源**；将 `themes/*.css` 的遗留覆盖逐步收敛为“仅装饰层”（如字体、装饰性渐变），移除对 `Mantine Paper/Input/Button/Title` 的 `!important` 功能性重写，改由 `data-remis-surface` 与 `data-remis-action` 驱动。
- 对齐 `theme.js` 与语义 token：移除与 `dark/brand` 硬编码调色板的冲突，让 Mantine 组件默认走语义 token。
- 清理 `App.css` 无用样式与重复滚动条定义；将滚动条收敛到单一实现。

### 4.2 策略二 — 建立间距与表面系统

- 以 `definitions.css` 为中心补齐缺失 token：`--space-*` (4/8/12/16/24/32/48)、`--radius-*`、`--shadow-*`、`--border-*`，并在各模块中替换硬编码值。
- 收敛重复的 `glassCard/surfacePanel/paperPanel` 为 2–3 个语义表面工具类（canvas 上标题区、surface 工作区、paper 证据区），而非每页面一套。

### 4.3 策略三 — 版式系统（typeset）

- 建立 type scale（建议 1.25 比率）与三级层级：hook（页面标题）/ bridge（区段标题与描述）/ detail（正文与标注）；为中文长段落设定 1.6–1.75 行高与 65–75ch 度量。
- “亮底深字”主题（Byzantine 的纸面、WWII/Medieval 的浅色材质）补偿字重与字距，避免细字在浅底上发虚。

### 4.4 策略四 — 布局重塑（relayout，以 Home 与项目管理为试点）

- **Home：** 强化单一锚点 — 将问候区收敛为紧凑的 canvas 标题带，`实时作业`作为 surface 主工作区，统计卡降权为 muted 辅助信息；图表区改为“作品集”而非等重卡片堆叠。
- **项目管理：** 列表态与看板态的卡片密度与空状态需统一语言；英雄区高度与搜索控件对比度需可用性校验（当前白字在部分背景上依赖半透明遮罩）。

### 4.5 策略五 — 状态与表面硬化（surface）

- 为每个可复用组件补齐 9 态：idle/hover/active/focus/loading/empty/error/disabled/overflow；空状态统一为“说明+重要性+行动”三段式；错误态给出恢复路径而非仅标红。
- 长路径与超长标识符的换行/截断策略在组件层面显式声明（`overflow-wrap: anywhere` + `min-width: 0` + title/tooltip）。

### 4.6 策略六 — 动效系统（motion，克制且功能性）

- 仅对 `transform/opacity` 做动画；入场用三拍心跳（0→150→250ms 含微过冲），退场为入场 70% 时长；列表 stagger 为 `index*20ms ±5ms` 随机抖动。
- 为 `prefers-reduced-motion` 提供三档（无/弱/标准），拖拽与排序动效遵循质量-阻尼-弹簧模型而非线性位移。

---

## 5. 分阶段实施路线（建议顺序）

| 阶段 | 内容 | 验收 |
|------|------|------|
| 0 | 基线截图：`npm run test:visual` 在 1440/375 下对 `VisualReliabilityLab` 全主题留底 | 截图基线已提交 |
| 1 | 主题收敛与清理 + 背景降噪：`definitions.css` 为主、`themes/*.css` 去功能性覆盖、清理 `App.css`/`theme.js`；每主题背景收敛为单一母题（删科幻 RGB 色散层与扫描线动画、拜占庭去金粉留晕影） | 夹具五主题可读性通过，现有回归测试全绿 |
| 2 | 间距/表面/版式 token 体系落地，以**装饰权重两级 token**（quiet/anchor）为基石；补齐显式 CJK 字体栈 | 任一页面在五主题下无硬编码间距/颜色残留；眯眼测试可识别单一锚点 |
| 3 | Home + 项目管理 relayout 试点 | 单锚点与主行动可一扫识别，空/加载/错误态完整 |
| 4 | 档案上下文树与术语判决区 surface 硬化 | 长文本/长路径/超长标识符无溢出，编辑态可追溯 |
| 5 | 动效与可访问性收尾（focus ring、触控 44px、色盲模拟） | 键盘可达、对比度 AA、动效可关闭 |

---

## 6. 风险与约束重申

- 任何涉及 `data-remis-surface`、`--surface-*`、`--paper-*`、`--interactive-accent` 的改动必须通过 `themes/semanticContrast.test.js`、`semanticSurfacePaint` 回归与 Playwright 五主题截图三重门禁。
- 主题不得改变信息层级与流程语义；付费/危险操作保持显式确认；背景材质不得以牺牲可读性为代价。
- 600 行/文件的 ESLint 维护性门禁仍有效，禁止为视觉改良而堆高单文件行数 — 需拆分为 hook/controller/子组件。

---

## 7. 下一步（待你确认）

- 若认可此提案，我将按阶段 1 开始执行：先做**主题收敛与清理**（风险最高但收益最大），随后进入 Home 与项目管理的视觉重塑。每阶段结束以五主题截图与对比度测试为交付物。
- 若你希望先看效果，我也可以先对 **HomePage** 做一个不触及主题覆盖的**局部 `refine`**（版式+间距+层级收敛），作为审美方向的小样供你定调，再铺开系统化改造。

> 提案文件位置：`.commandcode/design/visual-audit.md`；设计上下文：`.commandcode/design/brief.md`。

---

## 附录 A：模组档案馆（Context Archive Tree v2）专项（2026-08-07）

> 该模块（`components/neologism/archiveTreeV2/` + `ModArchive*`）是未来一段时间的重点开发对象。其代码纪律优于老模块（`ContextArchiveTree.module.css` 仅 19 处 `!important`，`ModArchive.module.css` 62 处），骨架（缩进导线、sticky inspector、mono 序号、aria 树角色、键盘可达）值得保留。以下诊断把"感觉难受但说不出来"翻译为具体设计语言问题。

### A.1 “难受”的具体来源（按体感权重排序）

1. **转场全面缺席。** 全模块仅 `.fragment` 有一条 120ms hover 过渡（其中 `transform` 从未被触发，属死代码）。4 处原生 `<details>` 瞬间开合；新建表单、空/加载态、总览↔编辑器切换均为条件渲染硬切；拖拽排序与上下移动瞬间换位。人眼把一切瞬间跳变读作"粗糙"。
2. **拖拽反馈装死。** dropTarget 只有 `:hover`/`:focus-within` 高亮，HTML5 拖拽过程中二者都不触发——拖一个 fragment 时整个界面零反馈。
3. **五层嵌套边框。** treePanel > story > group > dropTarget（常驻虚线框）> fragment，每个嵌套层级各画一个矩形。这是"草稿/线框感"的直接来源：边框本应表达分组，现在每层都在喊。`DESIGN.md` 第 56 行已禁止此模式。
4. **标题常驻表单态。** story/group 标题始终渲染为 `TextInput`，整棵树读作"待填表单"而非内容作品。应为阅读态标题 + hover/点击进入编辑。
5. **注意力预算失衡。** guide 三步条（帮助文本）用 accent 着色背景，比工作区更抢眼；每个 fragment 2 个 badge + 每组/每 story 计数 badge；grip 图标常驻。次要信息不够安静，主行动（Save draft）与 Reset/Add story 重量接近。
6. **间距不系统。** 0.35/0.45/0.55/0.65/0.7/0.75rem 等 10+ 种随意值，未落 DESIGN.md 的 4px 基准与 8/12/16/24/32 节奏。
7. **死代码。** `.editorToggle` 有样式定义但无 JSX 引用。

### A.2 改良处方（按收益/成本排序）

1. **动效系统（最优先，直接回应"转场难受"）。** `<details>` 改可控 accordion，用 `grid-template-rows: 0fr → 1fr` 做高度动画（250ms ease-out，退场 70% 时长）；总览↔编辑器、加载→内容切换用三拍入场（0→150→250ms，scale 0.98→1 + opacity）；列表重排加 FLIP 位移动画；新建表单同高度动画展开而非闪现。仅动 `transform/opacity/grid-rows`，全部提供 `prefers-reduced-motion` 降级。折叠/切换/重排动画纯 CSS + 少量 hook 即可，无需新依赖。**拖拽直接采用 @dnd-kit 替换原生 HTML5 DnD**（2026-08-07 由"中期可评估"升级为本次必做）：项目已有 `@dnd-kit/core+sortable+utilities` 依赖，`KanbanBoard` 与本模块 `PublishedContextMap` 均在使用；原生 draggable 在 Tauri WebView 中会触发系统"禁止"反馈（首版即无法拖拽），且其 ghost 与零放置反馈是廉价感大户。@dnd-kit 的 `DragOverlay` 可同时解决功能与观感。
2. **拖拽反馈。** 拖拽会话期间在 canvas 根加 `data-dragging`，此时才显示 dropTarget 虚线框并对悬停目标加 `data-drag-over` 高亮；被拖元素 8% 缩放 + 半透明。平时 dropTarget 收成安静的空态 hint。
3. **去框。** story 保留卡片（它是内容锚点）；group 去边框只留左侧缩进导线 + 连接 tick；fragment 去边框改细分隔线或纯留白分隔，选中/悬停才现框。目标：5 层矩形 → 1 层卡片 + 导线。
4. **标题阅读态化。** story/group 标题默认渲染为主题 header 字体文本，hover 显示重命名入口，点击进入编辑；删除按钮 hover 才出现（保持焦点可达）。
5. **注意力重排。** guide 三步条去掉 accent 底色，降为安静文本行或可折叠 hint；tier/route badge 移入选中 fragment 的 inspector，树上只保留必要计数；Save draft 成为唯一 accent 填充主行动。
6. **间距 token 化。** 收敛至 4/8/12/16/24 阶梯，模块内不再出现 0.35rem 这类随意值。
7. **验收。** 全部改动走既有 `context-tree.spec.js` 五主题 Playwright 截图门禁 + 对比度测试；动效补 reduced-motion 变体用例。
