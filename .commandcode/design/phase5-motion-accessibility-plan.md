# Remis 前端视觉改造 — Phase 5 动效与可访问性收尾计划

> 起点：`codex/phase4-terminology-workbench` 的 `37253397`。
> 本阶段不改变业务流程、信息架构、后端 API 或主题世界观；只补齐状态变化的身体语言与桌面工作区的键盘可达性。

## 1. 目标

1. 建立主题无关的 motion duration/easing/distance 与 44px 命中区 token。
2. 为 `prefers-reduced-motion: reduce` 提供全局可靠兜底，避免遗漏零散动画。
3. 让 Judgment Court 支持案卷方向键导航，并在单项批准、拒绝或恢复后把焦点交给相邻案件。
4. 让案件切换和批量工具栏出现时使用克制的 opacity/transform 动效，不制造布局位移。
5. 让 Kanban 支持键盘拖拽、列上下文明确的“添加便签”名称和至少 44px 的高价值操作命中区。

## 2. 非目标

- 不做移动端产品布局；窄屏只保持防崩坏。
- 不给所有卡片添加入场动画，也不引入弹簧动画库。
- 不改变 Kanban 状态、Judgment payload、批量并发或确认语义。
- 不用颜色单独传达状态；现有文字、图标和 badge 语义继续保留。

## 3. 实施边界

| 区域 | 改动 | 验证 |
|---|---|---|
| `themes/definitions.css` | motion/target token、全局 reduced-motion 兜底 | token 契约测试 |
| `JudgmentDocket.jsx` | roving tab stop、方向键、焦点恢复 | RTL 键盘回归 |
| `useJudgmentCourtWorkflow.js` | 成功单项操作后的焦点请求 | 真实 Court 工作流测试 |
| `JudgmentCaseWorkspace.jsx` / CSS | `aria-busy`、案件切换与工具栏动效 | reduced-motion + 五主题浏览器检查 |
| `KanbanBoard.jsx` / `TaskCard.jsx` | KeyboardSensor、保留 Enter 打开详情、Space 拖拽 | RTL/源码契约 |
| `KanbanColumn.jsx` / CSS | 列特定 accessible name、44px 命中区 | RTL + 浏览器尺寸断言 |

## 4. 验收矩阵

- 2560 与 3840 桌面：Judgment Court、Kanban 无横向溢出，新增空间继续给主工作区。
- 五主题：焦点环清晰，状态不依赖单一颜色，操作名称可区分。
- 键盘：Tab、方向键、Enter、Space 的职责不冲突；完成判决后不丢焦点。
- reduced motion：系统偏好开启后，动画/过渡缩短到 1ms，滚动行为为 `auto`。
- 全量 Vitest、ESLint、build、Playwright、文本完整性与 `git diff --check`。
