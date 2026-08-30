# Remis 前端视觉改造 — Phase 3 项目管理工作区执行计划

> 起点：`codex/phase2-foundations` 的 `48ad90a8`。
> 本阶段只重排项目列表、项目详情与 Kanban；不修改后端 API、任务语义、
> 付费/危险操作确认，也不触碰 Judgment Court、Glossary 或 Task Detail 热点。

## 1. 目标

1. 项目列表从营销式 Hero 改成紧凑、可扫描的桌面项目档案馆。
2. 项目详情固定表达项目身份、当前进度和下一项安全行动。
3. 将主流程导航与项目工具导航同时放在稳定位置，移除不断扩张的 `More views` 菜单。
4. Kanban 在 1440–3840 宽度随工作区扩展，窄窗口只保留防崩坏能力。
5. 继续遵守单滚动主人、单主行动、五主题语义表面与危险操作确认契约。

## 2. 信息架构

```text
项目身份
  ├─ 名称 / 游戏 / 源语言 / 状态
  ├─ 扫描 / 翻译 / 校验 / 发布准备度
  └─ 下一项安全行动

稳定导航
  ├─ 主流程：概览 / 校验 / 历史
  └─ 项目工具：项目术语 / 任务看板 / 发布素材

当前工作区
  └─ 当前 Tab 的唯一滚动内容
```

## 3. 执行批次

### Batch 3A — 项目列表

- 删除背景图片 Hero、Overlay 与白字专用硬编码。
- 建立紧凑标题、活动/归档范围、搜索、项目计数与唯一“创建项目”主行动。
- 项目卡作为真实交互对象保留，补齐键盘入口、状态、最后更新时间与空/筛选空状态。

### Batch 3B — 项目详情

- 将 `ProjectHeader` 从 Overview 内移到所有项目 Tab 共用的固定工作区头部。
- 身份条显示项目名、游戏、源语言与状态。
- 主流程与项目工具全部成为稳定可见入口，不再藏入 `More views`。
- 所有 Tab 内容继续由一个 pane-level vertical scroll owner 管理。

### Batch 3C — Kanban

- 列从固定 320px 改为可增长的 `min-width + flex-grow`，在 4K 工作区均匀扩展。
- board 只负责横向溢出，列内任务列表负责纵向滚动。
- 列、卡片、空列和拖拽态使用语义 token，移除 raw glass/white alpha paint。
- 修复 Medieval 等主题的次要文字与次要操作可读性。

### Batch 3D — 视觉门禁

- 保留 375px 防崩坏基线，但不把移动端作为产品目标。
- 自动截图增加 2560×1440 wide viewport；人工检查 3840×2160。
- 五主题覆盖 active list、dashboard detail、Kanban normal、Kanban dragging。
- 有意截图更新独立提交，更新前逐张查看关键宽屏图。

## 4. 完成定义

- 项目详情一屏可识别当前项目、当前状态和下一项行动。
- 项目工具不再依赖 `More views` 菜单发现。
- 最大化窗口时项目列表、详情与 Kanban 使用新增空间，无大块无意义空白。
- 无横向页面溢出、无第二个 page-level vertical scroll owner。
- 五主题、1440/2560/375、单元测试、lint、build 与 `git diff --check` 全部通过。
- 完成报告列明文件行数、state/effect 变化、API/presentation 边界与浏览器检查证据。
