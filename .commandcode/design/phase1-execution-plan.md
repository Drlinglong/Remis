# Remis 前端视觉改造 — 阶段 1 执行计划与验收清单

> **这份文档是冷启动交接件。** 主 agent（muse-spark-1.2-contributor）带子 agent 按批次执行；
> 架构决策已全部内嵌在批次规格里，执行时不要再重新决策。出现"升级触发条件"（见第 8 节）
> 时停止相关批次并回报，不要自行发明替代方案。
>
> 工作目录（git worktree）：`J:\V3_Mod_Localization_Factory-worktrees\phase1-theme-convergence`
> 分支：`codex/phase1-theme-convergence`（基于 `codex/issue-198-context-tree-v2`）
> 前端目录：`scripts/react-ui`。**禁止 push、禁止动其他分支、禁止创建新 worktree。**

## 0. 必读 steering 文档（先读再动手）

1. `DESIGN.md`（仓库根）——语义表面契约、五主题门禁、滚动/间距/版式规则，是硬约束。
2. `.commandcode/design/visual-audit.md`——审计与改良提案，含附录 A（档案馆专项）。
3. `.commandcode/design/brief.md`——产品定位与不可变量。
4. `docs/zh/developer/context-archive-tree-v2-plan.md`——档案馆后端工作流契约。
5. `AGENTS.md`（仓库根）——维护性红线：新 JSX 文件 600 行硬顶（ESLint 强制）、存量文件
   冻结上限不得上调；组件获得第三种职责必须拆分；提交信息英文 `<type>(<scope>): <subject>`。

## 1. 当前状态（已完成，勿重做）

| 提交 | 内容 |
|---|---|
| `44376d44` | 删除旧草稿编辑器（ContextArchiveTreeReview/Canvas/Preview + 独占 CSS + 2 测试），AnalysisPreviewPanel 与 index.js 已清理引用 |
| `2abc7943` | 背景降噪：GlobalStyles.css 每主题单一母题（科幻删扫描线/CRT/RGB 色散，拜占庭去金粉留晕影，噪点 0.05→0.03） |
| `d6f722c5` | 上述视觉基线截图更新（10 张 visual-contract，已人工 review） |
| `db99f5f2` | 设计文档：审计复核 + 档案馆附录 A（A.3 为已发布工作台专项） |

依赖已安装（`npm ci --include=dev`），Playwright chromium 已就位。

**当前测试基线（重要）：** `npm run test:visual` 为 42 绿 / 8 红。这 8 红是
**分支既有问题**（已在不含本批改动的旧 worktree 上复现，逐字节相同），由 Batch X 负责修复。
除此之外：`npm run build` 绿；`npx eslint src/components/neologism` 0 错误；
`set NODE_ENV=development&& npx vitest run src/themes` 57 绿。

## 2. 环境纪律（这台机器的全局坑，每条都踩过）

1. **机器全局 `NODE_ENV=production`。** 直接跑 vitest 会因加载 react-dom 生产构建而全灭
   （`React.act is not a function`）；直接跑 playwright 会让 vite dev server 产生
   `$RefreshSig$ is not defined`，夹具页空白。所有前端命令必须前缀：
   `set NODE_ENV=development&& <命令>`（cmd.exe 语法，`&&` 前无空格）。
2. `npm ci` 必须带 `--include=dev`（全局 NODE_ENV 会让它跳过 devDependencies）。
3. shell 是 **cmd.exe**：没有 `tail/head/grep`；串联命令用 `&` 或 `&&`；git 提交用多个
   `-m` 参数，禁止 heredoc。
4. 视觉测试命令：更新基线 `set NODE_ENV=development&& npm run test:visual:update`；
   校验 `set NODE_ENV=development&& npm run test:visual`。
   **截图基线更新必须与代码改动分成两个独立提交**（DESIGN.md 门禁 5），且更新后的
   关键截图要用 read_file 实际看过再提交。
5. 后台运行 `npm run test:visual*` 会静默失败（日志为空）——一律前台跑，超时给足 600s。

## 3. Batch X — 修复 8 个分支既有视觉测试失败（最先做，恢复门禁信号）

> 目标：让 `test:visual` 全绿，后续批次才有可信的回归信号。这些失败位于用户重点关注
> 的"已发布档案"模块。诊断结论未明前**禁止**通过删断言、放宽阈值（maxDiffPixelRatio）
> 或改 `renderedContrast` 来"修绿"。

### 3.1 五主题 `published archive preserves hierarchy and readability`（visual-reliability.spec.js:72）

- **现象**：`getByTestId('mod-archive-metadata-details')` 找不到元素。该元素由
  `src/components/neologism/PublishedArchiveContent.jsx:133` 在 `showAdvanced` 为真时渲染；
  夹具 `src/visual-fixtures/VisualReliabilityLab.jsx` 的 `PublishedArchiveVisualFixture`
  渲染 `ReleaseMetadata` 时没有传相关 prop。
- **诊断步骤**：`git log -p --follow scripts/react-ui/src/components/neologism/PublishedArchiveContent.jsx`
  查 `showAdvanced` 的默认值/来源何时变化（怀疑近期 context-tree v2 提交导致规格漂移）。
- **修复方向（按优先级）**：a) 若测试反映当前设计意图（元数据区应可检查）→ 改夹具
  渲染参数使其出现；b) 若组件契约是有意变更 → 更新测试以匹配现实，并在提交信息里说明依据。
  判断不了就升级（见第 8 节）。
- **验收**：5 个主题该测试全绿；`published-archive-*.png` 基线按需更新并人工 review
  （独立提交）。

### 3.2 三主题 `project glossary paper content remains readable`（:170，byzantine/wwii/medieval）

- **现象**：`renderedContrast` 实测 1.37–1.51（要求 ≥4.5）。三个失败主题恰好是
  **浅色 paper** 主题（byzantine #FFF8E1 / wwii #FCF5E5 / medieval #F5E6D3），
  victorian/scifi（深色 paper）通过。夹具是 `VisualReliabilityLab.jsx` 的
  `ProjectGlossaryContrastFixture`，采样点为 title/description/badge/alert 四个 testid。
- **诊断步骤**：起 dev server 用 Playwright 逐采样点打印 computed color/background 链，
  定位是哪个采样点、哪一层背景/前景 token 配对错误（高度怀疑 Badge/Alert 的 light
  variant 在浅色 paper 上的 color-mix 结果）。参考修复脚本模式见本文件附录（§9）。
- **修复方向**：修正 token 配对（首选，改 definitions.css 相应规则）或夹具声明的表面
  （若夹具声明与实际绘制不符）。禁止把阈值改小。
- **验收**：3 个主题对比度 ≥4.5；`semanticContrast.test.js` 57 项继续全绿；如改了
  definitions.css，全部五主题截图回归。

## 4. Batch 1b — 主题收敛（核心重构，决策已定，按序执行）

> 目标：`definitions.css` 的 `[data-theme]` 语义 token 成为唯一事实来源；退役遗留表的
> 功能性覆盖；`!important` 只减不增。每一步都要可独立提交、可回滚。

**侦察结论（已核实，直接采用）：**
- `src/themes/theme-byzantine.css`、`theme-victorian.css` **无任何 import，死文件** → 删除。
- `src/themes/index.css` 被 `main.jsx`、`visual-fixtures/main.jsx`、`incrementalMain.jsx`
  三处 import，其内容 = 五个遗留表。
- `--menu-*` 变量（`--menu-bg/text/muted/border/hover-bg/selected-bg/selected-text`）
  定义在五个遗留表里，`definitions.css` 539–617 行的下拉规则消费它们 → **必须先迁入
  `definitions.css` 对应 `[data-theme]` 块**，否则下拉菜单全灭。
- `MainLayout.jsx` 只用 `AppShell.Main`（无 Navbar/Header DOM）→ 遗留表里所有
  `.mantine-AppShell-navbar/-header` 规则是死选择器。
- `App.css`：`.logo*/.card/.read-the-docs/.steps-content/.log-container/.ant-menu*/logo-spin`
  全是死代码（Vite 模板 + antd 遗留，本项目用 Mantine）；仅全局滚动条规则活着。

**执行步骤：**

1. **TOKEN 迁移**：把五个主题的 `--menu-*` 全组与 `--mantine-color-dark-*` 色阶（保持
   原值，零视觉变化）迁入 `definitions.css` 各 `[data-theme='x']` 块。同时把
   `--font-header/--font-body` 声明补上 CJK 回退栈（见 §4 附 CJK 决策）。
2. **删死文件**：`theme-byzantine.css`、`theme-victorian.css`；`App.css` 死块（保留滚动条
   但把硬编码 `rgba(255,255,255,0.2/0.3)` 换成 `color-mix(in srgb, var(--canvas-text-main) 22%/30%, transparent)`——白色滚动条在中世纪浅色 canvas 上会隐形）。
3. **退役 FUNCTIONAL 覆盖**：逐表删除对 `.mantine-Button-root/-Paper-root/-Card-root/
   -Input-input/-Title-root/-Badge-root/-Alert-root` 等的颜色/边框/阴影覆盖及 `html.x
   body/h1-h6` 字体规则之外的装饰残留。**用户可感知的装饰损失要单独列出**（如拜占庭按钮
   金色渐变+扫光 hover、标题 text-shadow）——默认接受损失（语义契约的克制风格是目标），
   但清单要写进提交信息供 review。
4. **ThemeContext.jsx**：grep 全仓 `\.(byzantine|victorian|scifi|wwii|medieval)` 选择器在
   `themes/` 之外的消费者；若无，`root.classList.add(theme)` 与遗留 class 清理逻辑一并
   简化（保留 `data-theme` 属性，它是契约的锚）。
5. **theme.js 瘦身**：删 `components.Card.defaultProps.bg='dark.6'` 与 `AppShell.styles`
   （均被契约/GlobalStyles 覆盖，零视觉变化）；`colors.brand/dark` 与 `primaryColor`
   暂保留（牵连 Mantine 默认组件色，另行处理）。
6. **`themes/index.css`**：五个遗留表清空后删除该文件及三处 import。
7. **`!important` 降级**：仅在对手规则已删除的前提下，分组移除 `definitions.css` 契约层
   的 `!important`；每删一组跑一遍 §6 验收。任何视觉 diff 出现即恢复该组并记录，不要硬闯。

**Batch 1b 验收**：§6 全局验收全绿 + `definitions.css` 的 `!important` 计数显著下降
（当前 123 处，目标 <40，并在提交信息中报告前后数值）+ 全仓 `!important` 总数从 832 下降
（报告前后数值）。

**CJK 字体栈决策（迁入时执行）**：`--font-body` 各主题尾部追加
`"Noto Sans SC", "Microsoft YaHei", "PingFang SC", sans-serif`；
`--font-header` 在 Cinzel/Playfair Display 之后插入 `"Noto Serif SC", serif`；
Orbitron/Courier New 之后插入 `"Noto Sans SC", sans-serif`。

## 5. Batch 2 — 已发布档案馆工作台视觉与动效（用户主战场）

> 依据 `visual-audit.md` 附录 A.3。改动集中在
> `archiveTreeV2/PublishedContextMap.jsx`、`PublishedContextWorkbench.module.css`、
> `ContextTreeV2ArchiveSummary.jsx`、`PublishedContextEventDetail.jsx`。
> **注意 ESLint 冻结上限**（PublishedContextMap.jsx 412 行）：加行为前先抽取
> hook/子组件（如把拖拽编排抽成 `useFragmentDrag`），不得顶着上限堆代码。

### Batch 2a — 观感与动效（安全面）

1. **删原生拖拽 fallback**：移除 `handleNativeDragStart/handleNativeDrop`、
   `nativeDragOver` state、GroupColumn 上的 `onDragOver/onDrop/native` 属性——统一走
   @dnd-kit（原生路径在 Tauri WebView 会触发系统"禁止"光标）。
2. **总览↔聚焦转场**：`mapPanel` 已有 `data-view="overview|focused"`。为两种视图的容器加
   三拍入场（opacity 0→1 + scale 0.98→1，约 250ms，expo-out 类急减速度曲线），离场约
   70% 时长；仅 `transform/opacity`；`@media (prefers-reduced-motion: reduce)` 下瞬时。
3. **原生 `<details>` 开合动画**（workbench 内 sourceItem/entityDetails/lowerEntityGroup）：
   用 `grid-template-rows: 0fr→1fr` 或等效方案消除瞬间跳变（200–250ms），保留键盘/aria
   语义与 `open` 属性的测试断言（spec 里有 `not.toHaveAttribute('open')` 等断言，
   实现方式必须兼容）。
4. **"Needs placement" 伪列区分**：警示色边框/底色（`--status-warning`），固定排在链网格
   末位，加小型计数徽标；"Supporting text" 伪列降权（更安静的边框与文本）。
5. **卡片降噪**：fragmentCard 默认边框降到 ~8–10% 不透明度（现为 17%），完整边框只在
   hover/focus/selected/drag-over 出现；grip 把手只在 hover/focus-within 出现（保持
   焦点可达）；单元计数徽标降 muted。
6. **间距收敛**：模块内 0.42/0.45/0.55/0.62rem 等随意值收敛到 4px 基准阶梯
   （0.25/0.5/0.75/1/1.5rem）。
7. **验收**：§6 全局验收 + `context-tree.spec.js` 与 `visual-reliability.spec.js` 截图
   更新（独立提交，人工 review 至少 scifi/byzantine 两主题的 overview 与 focused）。

### Batch 2b — 交互升级（高价值高风险，规格即决策）

1. **聚焦态迷你栏**：聚焦某条事件链时，其余链渲染为窄可拖放 rail（约 56–72px 宽，显示
   截断标题 + 计数），是 dnd-kit 的 droppable；点击 rail 切换聚焦。验收标准：聚焦态下
   把卡片拖到另一条的 rail 上即完成跨链移动，无需先回总览。
2. **链重命名收拢**：聚焦态链标题 hover 出现重命名入口，点击就地编辑（Enter 提交 /
   Esc 取消）——复用 controller 的 `renameGroup` 能力。
3. **片段投递角色收拢**：在详情面板（detailPanel）提供路由切换，选项文案按后果写
   （"作为叙事上下文投递 / 仅作参考资产，不投递事件链 / 暂不投递（标记未决）"）。
   **先查 `contextArchiveTreeController.js` 是否已有 disposition 操作**；若缺，不要
   发明后端契约——升级（§8）。
4. **验收**：§6 全局验收 + 为 1–3 各补一个 vitest 组件测试（聚焦态拖放目标存在、
   重命名提交、路由切换调用 controller）+ 五主题截图更新（独立提交）。

## 6. 全局验收清单（每个批次收尾都必须全绿）

- [ ] `set NODE_ENV=development&& npm test`（vitest 全量）——绿；新行为有新测试
- [ ] `set NODE_ENV=development&& npx vitest run src/themes`——57 绿（对比度/表面绘制/标题契约）
- [ ] `npm run build`——绿
- [ ] `npx eslint src`——0 错误；无新增警告；无文件超 ESLint 冻结上限
- [ ] `set NODE_ENV=development&& npm run test:visual`——绿（Batch X 完成后应为 50/50）
- [ ] 若视觉有意变化：截图基线已更新、已人工查看关键截图、且与代码改动分属两个提交
- [ ] 每个提交信息为英文 `<type>(<scope>): <subject>`，尾部含
      `Co-authored-by: CommandCodeBot <noreply@commandcode.ai>`
- [ ] 完成报告含：文件行数变化、新增 state/effect 清单、!important 计数变化（如适用）

## 7. 建议批次顺序与提交节奏

`Batch X`（修既有红）→ `Batch 1b`（主题收敛；步骤 1–2 一个提交、3–6 一个提交、
7 一个提交）→ `Batch 2a` → `Batch 2b`。每批结束跑 §6 全量清单。
截图基线更新一律独立提交，信息格式：`test(visual): refresh baselines after <change>`。

## 8. 升级触发条件（停止并回报，不要自行发明方案）

- 规格与代码现实冲突（如 controller 没有 disposition 操作、fixtures 与 spec 互相矛盾）；
- 需要改动后端/API 契约、数据库、发布流程；
- 需要提升 ESLint 冻结上限或修改门禁阈值才能过关；
- 同一批次同一验证失败两次仍无法定位；
- 发现 DESIGN.md 语义契约本身需要变更（不是实现层能决定的）。

## 9. 附录：诊断探针模式（cmd.exe 可用）

```js
// probe.js —— 打印夹具页计算样式链；playwright 用绝对路径 require：
const { chromium } = require('J:/V3_Mod_Localization_Factory-worktrees/phase1-theme-convergence/scripts/react-ui/node_modules/playwright');
// 先起 dev server：set NODE_ENV=development&& npm run dev -- --host 127.0.0.1 --port 4174 --strictPort
// 再 node probe.js；注意 dev server 与测试都要带 NODE_ENV=development 前缀。
```
