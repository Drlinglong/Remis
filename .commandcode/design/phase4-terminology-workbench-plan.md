# Remis 前端视觉改造 — Phase 4 术语判决工作台执行计划

> 起点：`codex/phase3-project-management-relayout` 的 `321ad259`。
> 本阶段渐进拆分并硬化术语判决工作台；不修改后端 API、候选状态语义、
> 项目词典绑定、批量操作并发上限、AI/付费权限或恢复操作的既有安全含义。

## 1. 目标

1. 将 1278 行、12 个本地 state 的 `JudgmentCourt.jsx` 缩为纯组合组件。
2. 把项目/候选查询、草稿保持、单项判决、批量判决和通知集中到可聚焦测试的 controller hook。
3. 把案卷、证据/分析、决策和确认浮层拆为单一职责组件。
4. 在 1440–3840 桌面宽度使用新增空间；案卷栏保持可扫描宽度，证据和决策区域扩展。
5. 保持完整 Windows 路径、长术语、长证据、键盘选择、批量部分失败和单一滚动主人契约。

## 2. 不可变业务边界

- `pending` 与 `processed` 查询参数、排序和相邻候选选择行为不变。
- 单项批准继续提交 resolution、最终译文、词典、源/目标语言；空白非重复候选不得批准。
- 批量批准最多四并发；批量操作只移除成功项，失败项继续被选中。
- 恢复已批准候选不删除既有词典条目，继续显示明确说明。
- 项目词典仍通过既有绑定 API 获取和打开；AI 建议没有自动写入权。
- 不触碰 `useGlossaryActions.js`、`GlossaryOverview.jsx` 或 `GlossaryOperations.jsx`；它们进入后续独立批次。

## 3. 组件边界

| 文件 | 职责 | 目标上限 |
|---|---|---:|
| `useJudgmentCourtData.js` | 项目/候选/词典查询与案卷选择 | 220 行 |
| `useJudgmentCourtWorkflow.js` | 草稿、单项/批量判决与通知 | 320 行 |
| `useJudgmentCourtController.js` | data/workflow 接线，不直接持有状态 | 100 行 |
| `JudgmentCourtBatchModals.jsx` | 三种确认浮层 | 220 行 |
| `JudgmentDocket.jsx` | 案卷筛选、选择和批量入口 | 260 行 |
| `JudgmentCaseWorkspace.jsx` | 当前案件的证据/分析/决策组合 | 380 行 |
| `JudgmentCourt.jsx` | toolbar、controller 与工作区接线 | 180 行 |

新文件不得超过 600 行；若 controller 接近 500 行，优先再提取纯工作流函数，而不是提高上限。

## 4. 桌面布局

```text
项目与词典上下文（固定）

┌────────案卷 20–24rem────────┬────────────当前案件，自适应────────────┐
│ 筛选 / 批量入口 / 独立滚动   │ 术语锚点                              │
│ 候选列表                     │ 分析与证据（宽屏双列，窄屏单列）        │
│                              │ 决策面板（工作区底部稳定可见）          │
└─────────────────────────────┴──────────────────────────────────────┘
```

- 4K 下案卷栏不按 25% 无限膨胀；空间交给证据与决策内容。
- 普通桌面保持工作区内部单一案卷滚动和单一案件正文滚动。
- 低于 900px 只保证防崩坏：案卷与案件上下堆叠，不作为移动端产品优化。
- 移除运行时 raw `rgba`、旧 `--glass-bg` 和 JSX material paint，统一使用 Phase 2 token。

## 5. 验收

- 现有 Judgment Court 回归、payload、主题和批量操作测试全部通过。
- 为 controller 增加草稿保持、相邻选择、四并发与部分失败聚焦测试。
- 新增实际 Judgment Court 确定性视觉夹具：五主题 × 1440/2560/375；另加五主题 3840 结构断言。
- 断言完整路径不溢出、案卷栏在 4K 不超过 28rem、主工作区获得新增空间、页面无横向溢出。
- 全量 Vitest、ESLint、build、文本完整性和 `git diff --check` 通过。
- 完成报告记录前后行数、state/effect、API/presentation 分离和真实浏览器证据。
