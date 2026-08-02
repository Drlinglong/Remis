# Project Remis v3.1.2

Released on 2026-08-02.

Version 3.1.2 is a focused hotfix for the Steam Workshop workflow and cloud
model configuration introduced around the 3.1.1 release.

## English

### Highlights

- Resolves the five actionable review findings left on the 3.1.1 pull request,
  including safer asset-history deletion, cover draft persistence, and clearer
  Steam Workshop state handling.
- Refreshes the built-in cloud model catalogs, adds the OpenRouter adapter, and
  removes the retiring Gemini 2.5 family from the presets.
- Adds opt-in, model-aware reasoning controls for verified provider/model pairs.
  Unknown or custom models remain safe by default and can use advanced custom
  JSON without Remis guessing an OpenAI-compatible reasoning syntax.
- Adds an Aventine leaderboard link to API Settings to help users choose a
  model, and localizes the Format Repair menu label in all supported languages.
- Includes small Steam cover-editor, date-localization, overflow, test-isolation,
  and frozen-backend startup fixes completed before the larger context-window
  branch diverged.

### Validation

- All 703 backend tests pass, with 1 environment-dependent test skipped.
- Desktop frontend tests, locale/encoding gates, lint, and the production build
  pass. Python architecture and source-compilation checks pass.
- No paid provider call, installation, deployment, or project-file overwrite
  was performed while preparing this hotfix pull request.
- The frozen backend passed its localhost health smoke test. The bundled cloud
  provider catalogs were verified against all 20 packaged provider lists.

## 中文

### 主要更新

- 修复 3.1.1 Pull Request 中遗留的五条可执行审查意见，包括素材历史删除保护、
  封面草稿持久化及更明确的 Steam 工坊状态处理。
- 更新内置云端模型清单，加入 OpenRouter adapter，并从预设中移除即将退役的
  Gemini 2.5 系列。
- 为已经按“供应商 + 精确模型 ID”核验的模型加入可选推理强度控制。未知或自定义
  模型默认不发送内置推理参数，用户仍可通过高级 JSON 自行适配特殊语法。
- 在 API 设置中加入 Aventine 评测榜单入口，帮助用户选择模型；同时让主菜单中的
  Format Repair 在所有受支持语言下正确本地化。
- 纳入 context-window 大分支分叉前已经完成的小型 Steam 封面、日期本地化、长文本
  溢出、测试隔离和冻结后端启动修复。

### 验证

- 后端 703 项测试全部通过，另有 1 项依赖运行环境的测试跳过。
- 桌面前端测试、语言包与编码门禁、lint 和生产构建通过；Python 架构与源码编译
  检查通过。
- 准备本热修复 PR 时未调用付费模型、安装、部署或覆盖项目文件。
- 冻结后端已通过 localhost 健康冒烟测试；安装包内 20 个云端供应商模型清单均已
  与内置新版清单逐项核对。

## Final package / 最终安装包

- File / 文件：`remis-mod-factory_3.1.2_x64-setup.exe`
- Size / 大小：40,547,208 bytes (38.67 MiB)
- SHA-256：`8AEA7C7B5A554B4A13A96BF272BFBABD6A6AAE772983A320E264D0FCB5E9DC09`
- Frozen backend smoke / 冻结后端冒烟：passed on an isolated localhost port
- Code signing / 代码签名：not signed
