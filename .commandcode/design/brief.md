# Remis — Design Brief

## Name
Remis (Project Remis) — 本地优先的 Paradox Mod 本地化工作台

## Category
Desktop product UI (Tauri + React + Mantine), 非营销页。用户是 Mod 作者/本地化协作者，在“扫描 → 术语判决 → 翻译 → 校验 → 发布/归档”闭环中长时间作业。

## User & pressure
- 懂 Paradox 脚本与 yml 的深度用户，频繁处理长路径、超长标识符、中英混排。
- 在一次会话内完成“看项目身份 → 看证据 → 做决定 → 预览影响 → 安全提交”最小闭环；不能迷路、不能误操作付费/破坏性动作。

## Job to be done
Monitor（任务/词典健康/档案状态）+ Operate（术语裁决、文件校对、档案上下文树编辑）+ Configure（项目/提供商设置）。所有页面共享同一套语义表面与主题契约。

## Artifact
- 项目、任务、术语候选/判决、源文件证据行、档案上下文树（event/entity + fragment + evidence）、发布版本。

## Evidence that it works
- 五主题在 1440 与 375 宽度下无横向溢出、单滚动主人、菜单/浮层可读。
- 语义表面声明与实际绘制背景一致（definitions.css 契约 + regression 测试）。
- 长中文/英文、长 Windows 路径、超长无断词标识符均可读且不破坏布局。

## Register
Product — 信任来自一致性与速度，操作者每天反复打开必须无需思考即可移动。主题可换材质/字型/装饰与强调色，但不得改变信息层级、流程语义与安全边界。

## Invariants (from DESIGN.md)
- 材质契约：canvas / surface / paper / elevated，组件以 data-remis-surface 声明并用 --surface-* / --paper-* 等语义 token 绘制。
- 每屏一个主行动；付费/破坏/部署/覆写/修复需显式确认。
- 间距 4px 基准，主节奏 8/12/16/24/32；每 pane 单一滚动主人。
- 可视可靠性门禁：token 对比度 + 确定性夹具 + Playwright 五主题截图 + 溢出/滚动回归。

## Non-goals for this pass
不改变工作流语义与信息架构；不动后端与 Tauri 壳；主题仍保留五套世界观（Byzantine / Victorian / Sci-Fi / WWII / Medieval）。

## Current pain to address
- 视觉层级弱：多处玻璃态卡片等重、缺少单一视觉锚点；主行动不够突出。
- 间距与密度不一致：多套 glassCard / surface Panel 混用，重复实现。
- 版式系统松散：标题/正文/标注对比不足，中文长段落可读性未打磨。
- 动效与反馈薄弱：状态切换、空状态、加载/错误层级不够安静且不统一。
- 审美现代化不足：需在不破坏语义 token 的前提下提升精致度与专业感。
