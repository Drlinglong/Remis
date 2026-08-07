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
| 1 | 主题收敛与清理：`definitions.css` 为主、`themes/*.css` 去功能性覆盖、清理 `App.css`/`theme.js` | 夹具五主题可读性通过，现有回归测试全绿 |
| 2 | 间距/表面/版式 token 体系落地 | 任一页面在五主题下无硬编码间距/颜色残留 |
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
