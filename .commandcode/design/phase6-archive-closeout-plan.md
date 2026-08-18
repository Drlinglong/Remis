# Remis 前端 — Phase 6 档案馆工作台收口执行计划

> **冷启动交接件。** 主 agent 按批次执行，规格即决策，不要重新决策。
> 遇到第 8 节"升级触发条件"时停止相关批次并回报，不要自行发明替代方案。
>
> **起点分支**：`codex/phase5-motion-accessibility` 的 tip（审计基线：vitest 757 绿、
> Playwright 170/170 绿、ESLint 0 错误、build 绿）。
> **新 worktree（按 AGENTS.md 规则创建）**：
> `git worktree add "J:\V3_Mod_Localization_Factory-worktrees\phase6-archive-closeout" -b codex/phase6-archive-closeout codex/phase5-motion-accessibility`
> 前端目录：`scripts/react-ui`。**禁止 push、禁止动其他分支、禁止创建嵌套 worktree。**

## 0. 必读 steering 文档（先读再动手）

1. `DESIGN.md`（仓库根）——语义表面契约与视觉可靠性门禁，硬约束。
2. `.commandcode/design/visual-audit.md`——总审计；本计划落实其**附录 A.3** 的剩余项。
3. `.commandcode/design/phase1-execution-plan.md`——阶段 1 计划（环境纪律与验收格式沿用）。
4. `docs/zh/developer/context-archive-tree-v2-plan.md`——档案馆后端工作流契约；
   特别遵守"前端审核边界"与"不静默删除 unresolved/reference 记录"。
5. `AGENTS.md`（仓库根）——600 行/文件硬顶与职责拆分红线；提交信息英文
   `<type>(<scope>): <subject>` + `Co-authored-by: CommandCodeBot <noreply@commandcode.ai>` 尾部。

## 1. 背景与目标

档案馆（模组档案馆）是未来重点模块。当前已发布工作台（`PublishedContextWorkbench/Map`）
承载了用户约 80% 的注意力（审核 AI 关系草稿、修订故事线），但交互闭环差最后一口气：
验证内容在聚焦态、修位置必须回总览；重命名/投递角色编辑不在工作台内；例外队列与
正常链同装束。本阶段收口这些断点，并先修一处浅色主题按钮隐形缺陷。

**非目标**：不改后端/API/发布流程；不改五主题世界观；不做移动端布局；不给卡片加
入场动画；不引入第二个关系编辑面（A.1 约束：任何关系编辑能力只存在于已发布工作台）。

## 2. 环境纪律（这台机器的全局坑）

1. 机器全局 `NODE_ENV=production`：所有前端命令必须前缀
   `set NODE_ENV=development&& <命令>`（cmd.exe，`&&` 前无空格），否则 vitest 全灭
   （`React.act is not a function`）、playwright 夹具空白（`$RefreshSig$ is not defined`）。
2. 新 worktree 首次装依赖：`npm ci --include=dev --no-audit --no-fund`。
3. shell 是 cmd.exe：无 `tail/head/grep`；串联用 `&` 或 `&&`；git 提交用多个 `-m`，禁 heredoc。
4. 视觉测试一律**前台**跑（后台会静默失败）：更新 `set NODE_ENV=development&& npm run test:visual:update`，
   校验 `set NODE_ENV=development&& npm run test:visual`。
5. **截图基线更新与代码改动分属两个独立提交**；新基线用 read_file 实际查看后再提交。

## 3. Batch 1 — P1 修复：paper 上的 action 契约错配（前置，小步快走）

**根因（已确诊）**：`src/pages/home/HomeLiveWorkSection.jsx` 任务卡按钮使用
`data-remis-action="secondary"`，但卡片是 paper 材质；secondary 契约解析
`--surface-text-main`（浅色），在浅色 paper（byzantine/wwii/medieval）上等于白字白纸。
sci-fi（深色 paper）下正常，所以五主题截图里只有浅色三主题隐形。

**任务**：
1. 把该文件内位于 paper 卡片上的按钮改为 `data-remis-action="paper-secondary"`；
   面板级主按钮（`data-remis-action="primary"`，位于 surface 面板）不动。
2. 全仓 sweep：grep `data-remis-action` 的所有用法，逐个确认其所处 `data-remis-surface`
   材质匹配（paper 容器内只允许 `paper-*` 变体），列出并修复全部错配。
3. **守卫 a（运行时契约）**：在 `tests/visual/home-dashboard.spec.js` 增加断言——
   遍历夹具 DOM，`[data-remis-surface='paper']` 后代中的每个 `[data-remis-action]`
   必须以 `paper-` 开头；并把任务卡按钮纳入 `renderedContrast` 采样（≥4.5）。
4. **守卫 b（源码契约）**：参照既有 theme-contract 测试风格，新增源码扫描测试，
   禁止在已知 paper 组件中出现非 `paper-*` 的 `data-remis-action`（可用允许列表管理例外）。
5. **验收**：home-dashboard 五主题截图中按钮文字可读（人工查看 byzantine/wwii 两张）；
   全量门禁绿；截图基线独立提交。

## 4. Batch 2 — 聚焦态迷你栏（核心交互，本阶段最大件）

**问题**：聚焦一条事件链时其余链不渲染，跨链移动必须回总览；但总览卡片只有标题——
"验证内容"与"修位置"被拆在两个视图。

**规格（决策已定）**：
1. 聚焦态布局改为：storyRail → **railStrip** → focusedColumn。railStrip 渲染其余
   **真实链**（不含 supporting/needs-placement 伪列）为竖向迷你栏：宽 72px、
   标题两行截断、fragment 计数徽标、安静边框（`--surface-border-quiet` 或 paper 等价物）。
2. 每个迷你栏是 dnd-kit droppable（id 复用总览的 `group:<id>` 约定）；拖入即把
   fragment 移入该链末尾（`overFragmentId: null`）；拖拽悬停时 `data-drag-over` 高亮；
   键盘拖拽（KeyboardSensor）必须同样可达——rail 要对键盘拖放可见。
3. 点击迷你栏 = 聚焦该链（复用 `onSelectGroup`）。
4. focusedColumn 保持现状（max 48rem 居中、accent 边框、阴影）。
5. 视图切换转场沿用已有 motion token（`--motion-duration-standard`、急减速曲线，
   仅 transform/opacity）。
6. `<64em` 视口：railStrip 隐藏（防崩坏即可），跨链移动退回现有总览路径；
   不为窄屏发明替代交互。
7. **验收**：新 vitest——聚焦态渲染其余链 rail、rail 为 droppable、点击 rail 切换聚焦、
   drop 调用 `onMoveFragment` 且 `overFragmentId` 为 null；`context-tree.spec.js` 增加
   聚焦态（含 railStrip）截图断言，五主题基线独立提交并人工查看至少 scifi/byzantine。

**结构红线**：`PublishedContextMap.jsx` 已 412 行。新增渲染前先把 railStrip 抽为
独立子组件文件（如 `FocusedChainRails.jsx`），拖拽编排留在已抽出的 `useFragmentDrag`
（若不存在则新建该 hook）；不得顶着 ESLint 冻结上限堆代码。

## 5. Batch 3 — 链重命名收拢进工作台

1. 聚焦态链标题（focused header 的 `Title`）hover/focus 显示重命名入口（铅笔图标按钮，
   有 aria-label）；点击进入就地编辑：TextInput autoFocus 并全选，Enter/失焦提交
   （trim、非空、与现值不同才调用），Esc 取消并还原。
2. 先查 `useContextArchiveTree`/`contextArchiveTreeController` 暴露的重命名操作
   （预期存在 `renameGroup` 能力；旧草稿编辑器曾消费过）。**若不存在 → 停止并升级（§8）**。
3. 总览态不做重命名（本阶段非目标，控制改动面）。
4. **验收**：新 vitest——进入编辑、Enter 提交调用 controller、Esc 取消不调用、
   空值提交被拒绝；五主题截图回归。

## 6. Batch 4 — 片段投递角色收拢 + 例外队列与构图

**投递角色（detailPanel）**：
1. 在 `PublishedContextEventDetail`（选中片段的详情面板）增加路由切换控件，
   选项文案按后果写：`作为叙事上下文投递` / `仅作参考资产，不投递事件链` /
   `暂不投递（标记未决）`。
2. 先查 controller 的 disposition 操作（预期 `setFragmentDisposition` 存在）；
   **若缺失 → 停止并升级（§8）**。不得绕开 controller 直接改树状态。
3. 切换后片段按路由进入对应区域（narrative 链内 / supporting 伪列 / 待归位伪列），
   选择状态保持合理；尊重后端契约：unresolved/reference 记录必须保留，不静默删除。

**"Needs placement" 例外队列**：
1. 伪列固定排链网格末位；边框/底色用 `--status-warning` 的 color-mix（12–16% 背景、
   42% 边框），标题旁加警示色计数徽标——一眼区别于正常链。
2. "Supporting text" 伪列降权（更安静的边框与标题色），排在真实链之后、例外队列之前。

**页面构图**：
1. 实体摘要区（entitySection）改为可折叠手风琴（`grid-template-rows: 0fr→1fr` 或
   等效，200–250ms，仅 transform/opacity/grid-rows；reduced-motion 下瞬时），
   折叠行显示实体计数；**默认展开**（不藏正在工作的功能），折叠状态不持久化。
2. 关系图（mapPanel）由此获得更大首屏舞台——不得借机改动实体卡片内部样式。

**验收**：新 vitest——路由切换调用 controller 正确操作、伪列 data-attribute 与排序、
手风琴开合；五主题截图回归（独立提交）。

## 7. 全局验收清单（每批次收尾必须全绿）

- [ ] `set NODE_ENV=development&& npm test`——全绿；每个新行为都有新测试
- [ ] `set NODE_ENV=development&& npx vitest run src/themes`——全绿
- [ ] `npm run build`——绿
- [ ] `npx eslint src`——0 错误；无新增警告；无文件超冻结上限
- [ ] `set NODE_ENV=development&& npm run test:visual`——全绿（基线 170）
- [ ] 视觉有意变化：基线已更新、关键截图已人工查看、与代码改动分属两个提交
- [ ] 提交信息英文 `<type>(<scope>): <subject>` + Co-authored-by 尾部
- [ ] 完成报告含：文件行数变化、新增 state/effect 清单、新增/修改测试清单

## 8. 升级触发条件（停止并回报）

- controller/hook 缺少规格所需操作（renameGroup、setFragmentDisposition）；
- 规格与后端契约冲突（如 route 变更会破坏 unresolved/reference 记录保留）；
- 需要动后端、API、数据库、发布流程或 i18n 键结构；
- 需要抬 ESLint 冻结上限或放宽门禁阈值才能过关；
- 同一验证失败两次仍无法定位；
- 需要变更 `DESIGN.md` 语义契约本身。

## 9. 关键文件指针

| 文件 | 作用 |
|---|---|
| `src/components/neologism/archiveTreeV2/PublishedContextMap.jsx` | 关系图总览/聚焦（Batch 2/3 主战场） |
| `src/components/neologism/archiveTreeV2/PublishedContextWorkbench.module.css` | 工作台样式（railStrip、伪列、手风琴） |
| `src/components/neologism/archiveTreeV2/ContextTreeV2ArchiveSummary.jsx` | 页面组装（实体区手风琴） |
| `src/components/neologism/archiveTreeV2/PublishedContextEventDetail.jsx` | 详情面板（Batch 4 路由控件） |
| `src/components/neologism/archiveTreeV2/useContextArchiveTree.js`、`contextArchiveTreeController.js` | 状态与操作（先查后写） |
| `src/components/neologism/archiveTreeV2/useFragmentDrag.js`（如存在） | 拖拽编排（Batch 2 扩展点） |
| `src/pages/home/HomeLiveWorkSection.jsx` | Batch 1 修复点 |
| `tests/visual/context-tree.spec.js`、`home-dashboard.spec.js` | 截图与运行时契约断言 |

## 10. 后续方向（不在本阶段，留给 phase 7+）

token 采用扫荡与惰性 `!important` 清理（全仓 674 处，JudgmentCourt.module.css 74 处优先）；
状态语言统一（9 态清单、空/错误/加载文案三段式）；`Noto Serif SC/Noto Sans SC` 字体
真实加载确认；图表色盲模拟；剩余高频页面（Proofreading 优先）按 Home/PM 范式重排；
命令面板与全局快捷键。
