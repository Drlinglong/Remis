# Remis v3.2.2 发布准备记录

准备日期：2026-10-05

状态：候选版本；正式发布时间和安装包以 GitHub Release 为准。

## 本次范围

- 修复首次初始化对已有示例、翻译与归档的覆盖；JSON 路径重定位只处理声明的路径字段，保留用户文本。
- 归档持久化失败明确报告，完成检查点在归档成功后更新；数据库迁移 27 统一 fresh / v26 升级的 Workshop parent 外键约束，孤儿数据需人工处理。
- 零文件校验返回失败，避免将缺失输出视为通过。
- 优化火星求生重制版源语言与资源选择、翻译伙伴项目、CSV 写回和 FPK 资源边界；改进 Agent 增量预览与发布说明。
- 加入同一游戏翻译合集：选择各项目输出、预览冲突、审批本地导出、保留独立回执与发布身份；导出不代表游戏加载或 Workshop 上传成功。
- 补充公开模型代号，保留原默认模型。

多游戏适配与火星首次支持已经进入 v3.2.1；本版只记后续优化。独立 Aventine 和 remis-fpk 仓库不合入本仓库。OpenRouter Batch API 留待单独开发，本次不含实现。

## 验证

- 后端全量：2343 passed / 14 skipped，171.80 秒；跳过项为环境/外部样本依赖和平台能力限制。
- 桌面：253 文件、1047 测试通过；locale consistency 与 text encoding integrity 通过。
- 网站：64 测试、lint 与 build 通过。
- Python compileall、致命语法/名称 lint、架构守卫与 git diff --check 通过。
- 桌面 lint：0 errors / 13 个既有 warnings，未增加超限模块。
- 正式 stable 构建：PyInstaller、冻结后端健康/适配器/FPK 冒烟、Vite、Tauri/NSIS 通过；种子数据只从仓库已审阅 assets 导出。
- 初轮失败保留记录：后端 3 处文档/模型/资源上限契约未同步、桌面 2 处 locale 缺失，修正后全量复跑通过。
- 未运行真实游戏加载、Mod Editor 上传或收费模型调用；不据离线检查声称运行时覆盖已验证。

## 安装包

`remis-mod-factory_3.2.2_x64-setup.exe`，45,007,343 字节。

SHA256：`1adf58f36182aaae21df8fa493d81c3fb7cb5383197dce1def21dd9f4ba95e71`。

本地包位于 `archive/release/stable/`，与 SHA256SUMS 一同保留，均不进入 Git 源码提交。

## 架构复核

合集请求状态集中于 `useTranslationCollections`（285 行，10 state / 1 effect），新显示组件 32–55 行；本轮修复未增加 state/effect。Mars import 176 行、ProjectManagement 207 行，工作流与显示继续分离。数据库初始化 520→466 行、归档管理 867→803 行，架构例外同步收紧；取消恢复 service 186 行、portable inventory 244 行。新增真实 Modal 延迟响应、取消/回执、Paradox 运行时资源及 FPK 边界回归。

## English release notes

- Preserve existing demos, translation files and archive data during first-run initialization; hydrate declared JSON paths without changing user text.
- Fail explicitly on archive persistence errors and only advance completion checkpoints after successful archival.
- Align fresh and upgraded Workshop parent constraints with database migration 27; reject orphaned legacy data without discarding it.
- Reject validation runs with no recognized output files.
- Improve Surviving Mars: Relaunched source selection, companion projects, CSV writeback, FPK handling and incremental Agent previews.
- Add project-owned translation collection previews, conflict checks, approved local exports and export history. Local export is not in-game or Workshop-upload verification.
- Add reviewed public model identifiers without changing defaults.

Multi-game support first shipped in v3.2.1. OpenRouter Batch API is outside this release.
