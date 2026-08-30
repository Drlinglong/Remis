# Remis 前端视觉改造 — Phase 2 基础设施与 Home 试点执行计划

> **状态：待评审、尚未授权编码。** 本文件接续已完成的
> `phase1-execution-plan.md`，把设计审计中的“间距/表面/版式基础设施”落成可执行批次，
> 并以 Home 作为第一个真实页面试点。评审通过前不得开始页面级改造。
>
> 计划依据：`DESIGN.md`、`.commandcode/design/brief.md`、
> `.commandcode/design/visual-audit.md`、Phase 1 的最终 checkout，以及三个独立
> `gpt-5.6-luna` 只读审查（token、Home、治理）。

## 0. 起点、分支与施工纪律

### 0.1 已核实起点

- Phase 1 checkout：
  `J:\V3_Mod_Localization_Factory-worktrees\phase1-theme-convergence`
- 分支：`codex/phase1-theme-convergence`
- 评审时 HEAD：`71d42101c5fffb27fbf76efa31321673560ef292`
- 相对 `codex/issue-198-context-tree-v2`：领先 22 个提交。
- 工作区仅有用户自有的未跟踪 `.commandcode/settings.json` 与
  `.commandcode/taste/`；不得修改、提交或删除。
- Phase 1 最终门禁：173 个 Vitest 文件 / 674 项测试、主题契约 57 项、build 通过、
  ESLint 0 error / 15 条既有 warning、Playwright 50/50。

### 0.2 开工前置条件

1. **先评审并落地 Phase 1。** Phase 2 不继续堆在 22-commit-ahead 的施工分支上。
2. Phase 1 集成目标明确后，才创建独立 worktree：
   `J:\V3_Mod_Localization_Factory-worktrees\phase2-foundations`。
3. 建议分支：`codex/phase2-foundations`，必须从实际已落地的 Phase 1 HEAD 创建；创建前
   用 `git worktree list --porcelain`、`git branch --show-current`、`git rev-parse HEAD`
   三重核对。
4. 禁止在 C 盘、仓库 `.tmp` 或仓库根内创建 Remis worktree。
5. 禁止 push；每个提交使用英文 `<type>(<scope>): <subject>`，并附：
   `Co-authored-by: CommandCodeBot <noreply@commandcode.ai>`。
6. 所有前端命令从 `scripts/react-ui` 运行，并显式设置
   `NODE_ENV=development`。

## 1. 为什么 Phase 2 先做基础设施

Phase 1 已消除主题双轨和档案工作台的主要视觉/交互债，但下列证据说明现在直接 relayout
Home 或项目管理，会继续复制页面级实现：

- `definitions.css` 只有单值 `--card-radius`、`--surface-border`、
  `--shadow-elevation`；尚无正式的 `--space-*`、字阶、quiet/anchor 装饰权重。
- `HomePage.jsx` 同时管理问候语、stats/charts/activity API、Task Center 派生任务、任务归档
  与整页 presentation，共 7 个本地 state 和 2 个 effect。
- `MainLayout.jsx` 已在中心内容区声明唯一 `overflowY: auto`；`HomePage.jsx` 又创建
  `100vh + overflow-y:auto`，构成嵌套滚动风险。
- `HomePage.module.css` 只有 `pageScroll/pageTitle/glassCard` 被 Home 使用，其余 welcome
  banner、floating animation 等为遗留死样式。
- `ProjectManagement.module.css` 为 507 行，被 12 个运行时组件跨 Kanban、项目列表与项目详情
  共享，另有 1 个主题契约测试直接读取该 CSS，仍含 104 个 `!important` 和 51 处 raw
  color literal。
- Home 的两个图表组件仍直接写入 13+ 个 hex 色与旧 `--glass-*` tooltip 材质。
- 当前有 12 个生产 JS/JSX 文件达到或超过 500 行；不能用一次大重写解决，必须维持
  “触碰即缩小”的棘轮。

## 2. 本阶段目标与非目标

### 2.1 目标

1. 建立稳定的 spacing、radius、type、border/shadow weight、status/chart token 契约。
2. 用自动测试保证五主题 token 完整、别名兼容和语义表面不退化。
3. 把 Home 的 API/workflow state 与 presentation 分离，修复双滚动主人。
4. 在 Home 证明“单一视觉锚点 + 单一主行动 + 安静辅助信息”的页面语言。
5. 给 Home 增加 1440/375、五主题、真实浏览器的确定性验收。
6. 将 `ProjectManagement.module.css` 按职责拆分，但本阶段不重做项目管理信息架构。

### 2.2 非目标

- 不修改后端 API、数据库、Tauri 壳、任务语义或付费/危险操作确认流程。
- 不把全仓硬编码数值一次性替换成 token。
- 不立即重写 JudgmentCourt、Glossary、Task Detail 等 500+ 行热点。
- 不先造一套通用 `WorkspaceHeader/SurfaceSection/EmptyState` 组件库；同一模式出现第二个
  真实消费者后再抽取。
- 不改变五主题的世界观、信息层级或 status/risk 的业务含义。
- 不用截图更新掩盖回归，不放宽 `maxDiffPixelRatio`、对比度或 ESLint 门槛。

## 3. Phase 2 token 契约（决策已定）

### 3.1 固定全局原语

以下 token 在 `:root` 定义，五主题不得重写其数值：

```css
--space-1: 0.25rem;  /* 4px */
--space-2: 0.5rem;   /* 8px */
--space-3: 0.75rem;  /* 12px */
--space-4: 1rem;     /* 16px */
--space-6: 1.5rem;   /* 24px */
--space-8: 2rem;     /* 32px */
--space-12: 3rem;    /* 48px */

--type-size-label: 0.75rem;
--type-size-body-sm: 0.875rem;
--type-size-body: 1rem;
--type-size-section: 1.25rem;
--type-size-page: clamp(1.75rem, 2vw, 2.25rem);
--type-leading-tight: 1.2;
--type-leading-ui: 1.4;
--type-leading-body: 1.6;
--type-measure-body: 72ch;
```

规则：

- spacing token 只表达 4px 节奏；不得创建 `--space-5/7/9` 来迁就旧值。
- 字号与行高保持主题不变量；主题只更换 `--font-header/--font-body`。
- 技术路径继续使用 monospace，并保留 `overflow-wrap:anywhere`、可选择文本和完整值入口。

### 3.2 主题化 radius

每个主题必须显式定义：

```css
--radius-control;
--radius-panel;
--radius-paper;
--radius-pill;
```

初始映射如下；视觉检查发现主题身份失真时只能在独立提交中调整：

| Theme | control | panel | paper | pill |
|---|---:|---:|---:|---:|
| Byzantine | 6px | 8px | 6px | 999px |
| Victorian | 2px | 2px | 2px | 999px |
| Sci-Fi | 0 | 0 | 0 | 0 |
| WWII | 0 | 0 | 0 | 999px |
| Medieval | 8px | 12px | 8px | 999px |

兼容策略：`--card-radius: var(--radius-panel)` 保留一个阶段，不删除存量消费者。禁止为每个
组件再造 radius token。

### 3.3 quiet/default/anchor 装饰权重

保留现有 `--surface-border` 作为 default；新增：

```css
--surface-border-quiet;
--surface-border-anchor;
--paper-border-quiet;
--paper-border;
--paper-border-anchor;
--shadow-quiet;
--shadow-anchor;
--shadow-elevated;
```

默认推导规则：

- `surface quiet`：`surface-text-main` 与 transparent 的 12–16% mix。
- `surface anchor`：`interactive-accent` 与原 `surface-border` 的 70–80% mix。
- `paper quiet`：`paper-text-main` 与 transparent 的 10–14% mix。
- `paper default`：`paper-text-main` 与 transparent 的 22–30% mix。
- `paper anchor`：`interactive-accent` 与 `paper-text-main` 的 55–70% mix。
- `shadow-quiet` 不得制造 glow；用于辅助卡片。
- `shadow-anchor` 初始别名到当前 `--shadow-elevation`，随后按主题视觉 review 收敛。
- `shadow-elevated` 只供 modal/menu/drawer 等真正 elevated 内容使用。

组件只能按信息权重选择 quiet/default/anchor，不得因主题名分支。

### 3.4 status 与 chart token

Home 试点需要一并消除图表中的 raw hex 和旧 glass tooltip：

```css
--status-neutral;
--status-info;
--status-success;
--status-warning; /* 已存在，保留 */
--status-error;

--chart-series-1;
--chart-series-2;
--chart-series-3;
--chart-series-4;
--chart-series-5;
--chart-series-6;
--chart-series-7;
--chart-empty;
--chart-tooltip-bg;
--chart-tooltip-border;
--chart-tooltip-text;
```

要求：

- status token 在五主题中保持同一业务含义，不随世界观翻转成功/危险含义。
- chart series 可随主题微调材质，但相邻系列必须可区分；不得只靠红/绿区分状态。
- Recharts 使用 `var(--chart-*)`，tooltip 声明 elevated material，不再消费 `--glass-*`。
- Phase 2 只迁移 Home 的两个图表；其他图表进入后续 backlog。

### 3.5 fallback 与测试规则

1. `:root` 提供所有 token 的安全 fallback。
2. 五个 `[data-theme]` 块必须显式覆盖 radius、status、chart series 与主题相关 shadow。
3. 派生 quiet border 可以引用 surface/paper text token；主题只有在视觉证据证明失真时覆盖。
4. 新建 `src/themes/designPrimitiveContract.test.js`：
   - 检查 `:root` 与五主题所需 token 集合；
   - 检查 `--card-radius` 兼容别名；
   - 禁止 token 值引用主题 class 或组件选择器；
   - 检查 spacing 数值严格等于 4px 阶梯。
5. 扩充 `semanticContrast.test.js`：验证新增 status 文本/底色组合；chart series 不冒充正文
   对比度测试。
6. 扩充 `semanticSurfacePaint.regression.test.js`：tooltip 的声明与实际 elevated 绘制一致。
7. 静态测试不能替代五主题浏览器验收。

## 4. Home 架构边界

### 4.1 数据与 workflow state

新增文件：

| File | 唯一职责 | 目标上限 |
|---|---|---:|
| `src/pages/home/homeDashboardModel.js` | 默认数据、问候语与可见任务纯函数 | 100 行 |
| `src/pages/home/useHomeDashboardData.js` | `/api/system/stats` 请求、phase/error/retry、stats/charts/activity | 130 行 |
| `src/pages/home/useHomeLiveWork.js` | TaskCenter 派生列表、archive 操作、handling/error | 130 行 |
| `src/pages/home/HomeDashboardView.jsx` | 无 API/effect 的页面 composition | 260 行 |
| `src/pages/home/HomeLiveWorkSection.jsx` | 当前任务锚点、任务/空/错误/行动展示 | 190 行 |
| `src/pages/HomePage.jsx` | context、navigation、两个 hook 与 presentation 接线 | 110 行 |
| `src/pages/HomePage.module.css` | Home 专属 layout/type/weight；无通用 glass 实现 | 180 行 |

约束：

- `HomeDashboardView` 与 section 组件不得 import `api` 或 TaskCenter context。
- greeting 改为纯派生值，不保留独立 state/effect。
- dashboard hook 返回 `{ phase, data, error, refresh }`；请求失败不得只 `console.error` 后伪装成
  空数据。
- live-work hook 继续复用 TaskCenterContext 的既有任务，不重复请求任务 API。
- task archive 的失败只影响 Live Work；stats 请求失败只影响 overview，二者呈现 partial failure，
  不拖垮整页。
- 不修改 `/api/system/stats`、`/api/tasks/:id/archive` 或任务状态语义。

### 4.2 单滚动主人

- `MainLayout.jsx` 中心内容 Box 保持唯一 page scroll owner。
- 给该 Box 添加 `data-remis-scroll-owner="main-content"`，把滚动 ownership 变成可测试合同。
- 删除 Home 根节点的 `h="100vh"` 与 `.pageScroll { overflow-y:auto }`。
- Home 根节点只需 `min-width:0`、正常文档流和 canvas surface。
- `RecentActivityList` 移除固定 `ScrollArea h={300}`；默认随页面流展开并设置合理条目上限。
  若产品明确要求 activity pane 独立滚动，必须单独记录交互理由并新增浏览器 scroll-owner 测试。
- 375px 下不得以内部横向滚动解决普通卡片布局。

### 4.3 信息层级与行动

Home 的扫描顺序固定为：

1. 紧凑 workspace header：页面身份和一句说明，不占据主要工作视口。
2. **唯一 anchor：Live Work surface。** 当前最需处理任务、状态、下一安全行动。
3. attention 信息并入 Live Work 标题区或其紧邻位置，不再成为等重整页 Alert。
4. stats 降为 quiet 辅助 rail，不使用三个同重玻璃卡竞争注意力。
5. portfolio 与 recent activity 放入次级 overview；图表是辅助解释，不是首屏主锚点。

主行动规则：

- 有可行动任务：主行动是打开最优先任务。
- 无可行动任务：主行动是继续/选择项目。
- refresh/history 为 secondary；archive/handle 仍为任务行内次级操作。
- 不得同时出现两个视觉上等重的 primary button。

### 4.4 状态与长内容

必须覆盖：

| State | 行为 |
|---|---|
| initial/loading | Live Work 与 dashboard 独立 loading；布局不跳变 |
| ready/actionable | 最多 2 个可行动任务 + 最近完成任务，保持现有契约 |
| ready/empty | 说明“这里是什么、为什么空、下一步去哪”并给单一 CTA |
| dashboard error | 显示失败范围与 retry；Live Work 仍可操作 |
| task archive error | 错误靠近被操作任务；不抹掉 dashboard |
| partial failure | 明确哪个区域不可用，不显示伪造的 0 数据 |
| long content | 长中英文项目名、任务名、Windows path、无断词 ID 不溢出 |
| disabled/busy | handling task 的按钮不可重复提交，其他任务仍可打开 |

## 5. ProjectManagement CSS 责任拆分（零视觉变化批次）

`ProjectManagement.module.css` 当前跨 12 个运行时消费者，且
`ProjectDetail.theme-contract.test.jsx` 直接读取它；先按真实 ownership 搬迁，不做 selector
重命名和视觉改造的混合提交。

| 新模块 | 迁移职责/消费者 |
|---|---|
| `components/tools/KanbanBoard.module.css` | boardContainer；KanbanBoard |
| `components/tools/KanbanColumn.module.css` | column/header/taskList/scrollbar/ghost；KanbanColumn |
| `components/tools/TaskCard.module.css` | taskCard、dragging、type indicators；TaskCard |
| `components/projectManagement/ProjectListView.module.css` | hero、search、list/grid action toolbar、projectCard |
| `components/projectManagement/ProjectDashboardView.module.css` | project canvas、tabs、dashboard layout |
| `components/project/ProjectDetailSurfaces.module.css` | surface/paper/inset/alert/menu contract，供 project detail 子组件暂时共享 |
| `components/project/ProjectHeader.module.css` | header、primary translation action；ProjectHeader |

拆分规则：

- 一个提交只搬迁一组消费者，保持 class 名与 computed style。
- 每迁移一组就删除旧 CSS 中对应块；旧文件只减不增。
- `ProjectDetailSurfaces.module.css` 是过渡共享层，只包含 material contract，不接收业务 layout。
- 开工前核对 `styles.tabsList`、`styles.table` 等引用是否缺失 selector，并核对
  `startTranslationButton/startBtnLabel/startBtnIcon` 是否仍有消费者；缺失接口与遗留清理各自
  独立提交，禁止在机械搬迁中猜测或顺手删除。
- 有真实消费者的 CTA pulse/shimmer 在本批只原样迁移；无消费者时记录证据，留到遗留清理
  提交删除。
- 任何 raw color、`!important` 移除或视觉变化都另起提交并跑五主题验证。
- `ProjectDetail.theme-contract.test.jsx` 必须改为读取全部新 material 模块，不能随旧文件一起
  删除或缩小断言。
- 迁移结束后删除空的 `ProjectManagement.module.css`；若仍有跨域消费者，不得宣称完成。

## 6. 500+ 行热点治理

### 6.1 Phase 2 必做

- 所有现有 ESLint frozen ceiling 不得上调。
- Phase 2 不给以下热点添加新责任：JudgmentCourt、useGlossaryActions、TaskDetailPage、
  GlossaryOverview、GlossaryOperations、useIncrementalTranslation、ModelArenaPage、
  ProjectTrackingPage、AgentWorkshopPage、InitialTranslation、ApiSettingsTab。
- 触碰某热点时，文件总行数不得增长；功能必须在新 hook/controller/子组件中实现。
- 在完成报告中记录 touched hotspot 的前后行数、state/effect 和职责变化。

### 6.2 适合后续渐进拆分

- `JudgmentCourt.jsx`：先拆 query/workflow controller，再拆 evidence/decision presentation；不做一次性重写。
- `useGlossaryActions.js`：按读取、判决、导入/导出、批量操作拆 service hooks。
- `TaskDetailPage.jsx`：按 task presentation、event timeline、attention/repair actions 拆分。
- `GlossaryOverview/Operations`：在共享 glossary controller 稳定后逐个拆。

这些工作进入 Phase 3 backlog，不与 Home 视觉试点同批。

## 7. 执行批次与提交节奏

### Batch 2A — token contract（预期零视觉变化）

1. 添加 §3 全局与五主题 token。
2. 保留兼容别名；不迁移页面。
3. 添加 token/contrast/surface-paint 测试。
4. 运行全量门禁；任何截图 diff 都视为回归，不更新基线。

建议提交：`refactor(theme): define phase two design primitives`

### Batch 2B — Home state/presentation 拆分（零视觉变化）

1. 添加 model 和两个 hooks。
2. 提取 `HomeDashboardView` 与 `HomeLiveWorkSection`。
3. 现有 Home 测试按行为边界拆分并保持通过。
4. 只允许结构变化；Playwright 不得产生有意 diff。

建议提交：`refactor(home): separate dashboard state from presentation`

### Batch 2C — Home 单滚动与视觉试点

1. 修复单滚动主人和 RecentActivityList 嵌套 ScrollArea。
2. 使用新 spacing/type/weight/radius tokens。
3. 移除 Home 死 CSS、`glassCard` 和 JSX 中的 material paint。
4. 重塑 anchor/secondary hierarchy 与完整状态。
5. 迁移 StatCard、两个 Home chart 的语义颜色和 elevated tooltip。

建议拆成两个代码提交：

- `fix(home): restore single-page scroll ownership`
- `refactor(home): establish the dashboard visual hierarchy`

### Batch 2D — Home 五主题真实浏览器 gate

1. 新增 `HomeDashboardVisualFixture.jsx`，直接渲染无 API/effect 的 presentation。
2. 新增 `home-dashboard.spec.js`。
3. 先 compare 验证行为断言，再人工查看关键 actual，最后 update。
4. 截图必须独立提交：
   `test(visual): add five-theme home dashboard baselines`

### Batch 2E — ProjectManagement CSS 责任拆分

0. 先新增 ProjectManagement 确定性 fixture 与 §8.3 的 40 张保护基线，并核对缺失/遗留
   selector；不得先搬 CSS 后补证据。
1. 按 §5 从 Kanban → list → dashboard → project detail 依次迁移。
2. 每组一个提交；整个批次应零视觉变化。
3. 完成后再决定是否启动 Phase 3 Project Management relayout。

## 8. 浏览器与状态验收矩阵

### 8.1 Home fixture

主题：Byzantine / Victorian / Sci-Fi / WWII / Medieval。

视口：

- desktop：1440 × 1100
- compact：375 × 900

确定性场景：

1. `active-partial`：长项目名、2 个 actionable task、1 个 completed task、attention、stats、
   chart、activity；用于验证主锚点、长内容与完整页面。
2. `empty-error`：无 task、dashboard 请求失败、retry 与 continue-project CTA；用于验证空/错/
   partial failure 层级。

共 5 × 2 × 2 = 20 张 Home 基线；加入现有 50 项后，预期视觉测试总数至少 70。

### 8.2 每个场景的行为断言

- `html[data-theme]` 与 fixture ready 标记正确。
- 无 console/page error。
- `documentElement.scrollWidth <= clientWidth`。
- Home 内不存在第二个 page-level `overflow-y:auto/scroll` 主人。
- 375px 下操作顺序与 desktop 相同；主 CTA 不被 stats/chart 推出首屏逻辑顺序。
- 长路径、无断词 ID 不逃出声明表面。
- 只有一个 `data-remis-action="primary"` 的页面级主行动。
- tooltip/elevated material 的实际背景与声明匹配。
- `prefers-reduced-motion: reduce` 下无非必要 animation。

### 8.3 ProjectManagement CSS 拆分验收

- 新增 `ProjectManagementVisualFixture.jsx` 与 `project-management.spec.js`，固定四个场景：
  `active-list`、`dashboard-detail`、`kanban-normal`、`kanban-dragging`。
- 四场景均覆盖五主题、1440 × 1100 与 375 × 900，共 4 × 5 × 2 = 40 张保护基线。
  加上 Home 的 20 张与现有 50 项，Phase 2 全部落地后的预期视觉测试总数至少 110。
- 拆分前后五主题 computed style probe 与上述截图必须一致；纯搬迁不得刷新基线。
- `dashboard-detail` 必须实际覆盖 material contract、tabs 和至少一个 detail 子视图；
  `kanban-dragging` 必须通过真实交互进入拖拽态后截图。
- 项目列表、项目详情和 Kanban 有稳定 fixture 覆盖后，才能删除旧共享 CSS；fixture 未就绪时
  不盲搬。
- CSS import 不再从 `components/tools` 或 `components/project` 反向依赖 `pages/`。

## 9. 每批全局门禁

```powershell
Set-Location scripts/react-ui
cmd.exe /d /c "set NODE_ENV=development&& npm test"
cmd.exe /d /c "set NODE_ENV=development&& npx vitest run src/themes"
cmd.exe /d /c "set NODE_ENV=development&& npm run build"
cmd.exe /d /c "set NODE_ENV=development&& npx eslint src"
cmd.exe /d /c "set NODE_ENV=development&& npm run test:visual"
git diff --check
```

验收口径：

- Vitest 不低于 Phase 1 的 173 files / 674 tests，除非有书面删除依据。
- 主题契约保持全绿；新 primitive tests 单列数量。
- ESLint 0 error，不新增 warning，不上调 frozen ceiling。
- `definitions.css` 与全 CSS 的 `!important` 只减不增。
- token 批与结构拆分批不得产生视觉 diff。
- 有意视觉变化的代码与截图分属独立提交，关键图必须人工查看。
- locale 修改时使用 UTF-8，解析全部 JSON、扫描 replacement chars/mojibake，并跑
  `textEncodingIntegrity.test.js`。

## 10. 升级触发条件

出现以下任一情况，停止相关批次并回报：

- Phase 1 尚未落地，无法确定 Phase 2 正确 base。
- token 契约要求改变 DESIGN.md 的 surface/主题不变量。
- Home 拆分需要修改后端 API、TaskCenter 契约或危险操作语义。
- 需要新增第二个 page scroll owner 才能实现设计。
- token 批或纯结构拆分出现无法解释的视觉 diff。
- 需要上调 ESLint frozen ceiling、对比度门槛或截图 diff 阈值。
- ProjectManagement CSS selector 无法归属单一消费者，且没有浏览器 fixture 支撑搬迁。
- 同一批次同一门禁连续失败两次仍无法定位。
- 五主题中任一主题的实际 material/readability 未验证。

## 11. Phase 2 完成定义

只有同时满足以下条件，才能宣称 Phase 2 完成：

1. 新 token 契约、fallback、五主题定义和测试全部落地。
2. Home 不再拥有嵌套 page scroll；API/workflow/presentation 边界符合 §4。
3. Home 的单锚点、单主行动、状态与长内容在 20 张新基线中通过人工检查。
4. Home/Chart 不再新增 raw theme color、旧 `glassCard` 或旧 `--glass-*` tooltip。
5. `ProjectManagement.module.css` 的跨域 ownership 已消除，或逐项列明尚未迁移的阻塞消费者；
   不得用“部分拆分”冒充完成。
6. 全局 gates 全绿，截图和代码提交分离，无 push。
7. 完成报告包含：文件行数、state/effect、API/presentation 分离、token/`!important` 前后计数、
   五主题实际浏览器证据与任何剩余 backlog。
