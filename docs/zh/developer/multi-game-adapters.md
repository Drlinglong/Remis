# 多游戏本地化适配与离线验收

本轮在 `codex/multi-game-adapters` 上增加 Project Zomboid 和 RimWorld，基线为
`283b55912a5e4393e25eb7b8c8f193f2b634b2ab`。现有 Surviving Mars Relaunched CSV
提交 `2721c9ba` 已包含在基线中。本轮复用其 CSV 能力，不生成新的火星独立翻译 Mod。

## 支持范围

| 游戏 | 读取与写回 | 生成物 | 明确边界 |
| --- | --- | --- | --- |
| Project Zomboid | Translate 目录的字符串值 JSON、安全 Lua-table TXT；common/版本目录；单 Mod 的 Workshop 容器 | 目标语言资源、独立 mod.info、原 Mod 的 require 依赖 | 不执行 Lua；复杂表达式、未知 JSON 形状和多 Mod 容器报诊断；不翻译硬编码脚本文字 |
| RimWorld | Keyed、DefInjected、Strings；Defs 中显式规则支持的可翻译字段和 rulesStrings；版本目录与 LoadFolders 证据 | Languages/目标游戏语言目录、独立 About.xml、原 packageId 依赖与 loadAfter | 不执行程序集或 PatchOperation；继承和依赖条件不能离线完整展开；未知字段、条件和混合 XML 内容显示诊断 |
| Surviving Mars Relaunched | 现有 ModItemLocTable CSV | 保留现有 Translation 列写回 | 独立翻译 Mod 的生成留给以后 |
| P 社游戏 | 现有 localization/localisation 解析与工作流 | 现有产物 | 回归原有路径与语义 token 保护 |

版本号用于说明证据与选择有效目录。Mod 元数据版本变化不会使所有条目重新翻译；已知规则
不会因为游戏的小版本不同而被整体禁用。具体资料与许可见
[PZ 证据](multi-game-pz-evidence.md)和 [RimWorld 证据](multi-game-rimworld-evidence.md)。

## 同一工作流内的扩展方式

`scripts/core/game_adapters/contracts.py` 定义 Entry、Document、Resource、Discovery、Diagnostic
和 GameAdapter。适配器只负责发现、解析、渲染、包元数据、语言目录和格式校验，不调用模型、
不写数据库，也不创建第二套任务系统。原文保存在 Document 中，写出仅改变可翻译值与必要的语言标记。

共享 `workflow_bridge` 把资源映射到现有初次翻译、增量快照和 file_builder。
现有 provider、队列、取消、checkpoint、归档、词典/上下文、校对与 Workshop 继续工作。
`LegacyAdapter` 通过已有 CSV/P 社解析器实现同一约定，不替换原来的生产工作流。

以后新增游戏，应完成一个 adapter、在 registry 注册格式识别与能力、增加 profile/语言映射和
fixture 契约测试。不要给 TaskRunner、项目管理器或模型客户端增加某游戏专用的任务分支。
多种文件格式可以像 RimWorld 一样分为 XML/文本辅助模块。未知能力应由诊断和能力投影表达。

## 身份、复用和人工确认

- 项目隔离游戏与 Mod；PZ 使用声明的 Mod ID，RimWorld 使用 packageId。包目录冲突按 Mod 身份和资源路径拒绝覆盖。
- 条目键保留资源命名空间。版本、绝对工作树路径和目标语言不进入稳定键。
- 增量比较条目原文，唯一稳定键允许移动后的匹配；多候选已有译文不任意选一个。
- 原文改变时保留已有译文，标记 `needs_review`，不自动提交重译或格式修复。人工校对成功更新归档后清除该标记。
- `.remis-localization-manifest.json` 记录每个实际输出文件的源相对路径、条目、原文哈希、语言及待复核状态。
  多 DefType 输出分别记录自身条目。此文件用于 Remis 管理，不是游戏加载配置。
- 保存校对前检查文件 revision；源资源只读。文件写回与 SQLite 同步失败时恢复原文件。
- 结构化资源翻译缺失、键/值回读不一致、危险路径或重建失败会阻断；不把源文本回退当成完成译文。
- 新任务使用独立输出目录，避免旧包中的已删除资源混进新包。初次翻译的同一 checkpoint run
  保持目录身份；增量复跑从归档重建新包。每份文档对应的资源、元数据和 manifest 写入失败时一起回滚；
  任务此前已完成的其他文档仍作为部分产物保留，不宣称整个任务具有数据库级事务性。
  普通异常与可捕获的 KeyboardInterrupt 均覆盖；断电/强杀不具备事务保证。现有 workflow
  在各自独立目录串行写出，不支持多个外部进程直接对同一包根目录并发调用 writer。
- 多目标语言任务在交付目录内按语言代码生成独立 Mod 子目录，每个子目录有自己的元数据与
  manifest；安装时选择所需语言的子目录，语言顺序不会改变其 Mod 身份。

## GUI 与运行隔离

项目创建/管理中可选择两个新游戏。项目概览显示识别到的资源与条目、未支持内容和运行时未验证状态。
初次翻译、增量、校对、词典、Mod 档案和格式修复沿用既有页面。新游戏不显示 P 社部署/清理入口；
仅有源文件时主操作是初次翻译，源文件只能预览。
预览接口绑定项目 ID 与已登记源文件 ID，并重新核验当前资源发现结果；不扩大通用文件读取接口的权限。

已有译文通过条目键复用，已有词典/参考治理入口继续使用。本轮没有增加“官方语言包批量导入
并自动生成待审术语候选”的专用入口；这是后续参考库扩展的具体缺口，不能把本次文件复用
称作已建成官方术语库，也不会把句子或模型建议自动提升为权威词典。

运行目录的设置与实际解析路径见 [隔离说明](multi-game-runtime-isolation.md)。本轮工作树为
`J:\V3_Mod_Localization_Factory-worktrees\multi-game-adapters`，SQLite、缓存和日志位于其 `.runtime`；
源/译文产物位于该工作树自己的目录。GUI 验收使用后端 `127.0.0.1:1456` 与前端 `127.0.0.1:5177`。
未操作主工作树的项目状态。测试 fixture、日志、数据库、真实小样例和产物不进入 Git。

## 验证方式与边界

自动化覆盖安全解析、token 多重集、注释/BOM/换行、目标目录与元数据的独立预期、重复键、危险路径、
版本目录、初次翻译完整流水线（只替换 provider）、真实 SQLite 归档、增量条目复用、校对与回滚、
Workshop 写回、取消/中断终态及切换项目时的恢复隔离。新旧游戏一起跑回归，并执行 Python 架构 guard、
compileall、前端 test/lint/build 与 locale 编码测试。

2026-09-25 最终验证：

- 后端选定回归：299 passed、3 skipped；随后新增的真实 RimWorld fixture 验证另有 1 passed。
  合计 300 passed、3 skipped。跳过项为当前 Windows 权限无法创建的链接样例；
  原有 pykakasi 与 SQLAlchemy 弃用警告仍存在。P 社、火星 CSV、项目归档、Agent API、隔离路径均在回归内。
- 前端：238 个测试文件、963 项测试通过；lint 为 0 errors、13 条已有 warnings；生产构建通过。
- Python 架构检查、compileall 和 diff 空白检查通过，未抬高任何架构基线。
- 完整初次翻译与完整增量 wrapper 都使用真实写出、归档与校验，仅替换模型 provider。
  测试验证同名资源隔离、多 DefType 输出、变化条目待复核持续性，以及源 DLL/Lua/贴图不被复制。
  双语言初次/增量场景验证各语言包身份、资源、manifest 和归档独立；普通写盘失败及
  写盘后 KeyboardInterrupt 都验证新包清理与已有包逐字节恢复。
- 实际 GUI 显示 PZ 1 个资源/1 个条目，RimWorld 2 个资源/3 个条目；源文件预览成功且只读。
  太空科幻、维多利亚、拜占庭、二战、中世纪宫廷五套主题均完成实际视觉检查。

复现后端主要验证（使用开发环境 Python，先设置隔离目录）：

```powershell
$env:REMIS_APP_DATA_DIR = Join-Path (Get-Location) '.runtime'
$extra = @(rg --files tests | Where-Object {
    $_ -match 'test_.*(initial_translation|incremental|file_service|file_builder|proofreading|postprocess|workshop_writeback|workshop_issue_export|translation_archive|embedded_workshop|loc_parser|project_watch)' -and $_ -notmatch 'game_adapters'
})
python -m pytest -q @extra tests/core/game_adapters tests/core/test_rimworld_adapter.py tests/core/test_surviving_mars_csv.py tests/core/test_paradox_localization_parser.py tests/core/test_project_manager.py tests/test_agent_api.py tests/test_build_profile.py
python scripts/developer_tools/check_python_architecture.py
python -m compileall -q scripts tests
```

前端在 `scripts/react-ui` 运行 `npm test -- --run`、`npm run lint`、`npm run build`。

## 前端职责与规模复核

新增支持面板 177 行、只读预览 68 行、P 社完成动作 44 行、支持信息 hook 37 行。
TaskRunner 429→442 行；ProjectFileList 118→147 行；ProjectHeader 228→243 行；
ProjectDashboardView 178→199 行；增量监视 hook 165→184 行；恢复 hook 176→216 行。
新增文件均低于 600 行，相关组件未超过 500 行；未给已有超大组件增加游戏专用职责。

支持信息的 API 请求独立在 hook 中，面板负责展示。文件列表新增一个预览选择状态；预览弹窗
有三个加载/内容/错误状态和一个可取消请求 effect；支持信息 hook 有两个状态和一个可取消 effect。
监视与恢复逻辑未增加 state/effect，增加了终态收敛和项目归属检查。对应 hook、源文件列表、
项目主动作、主题约定和完成动作都有聚焦测试。

## 实机验收与费用

实际 Agent API 验收仅导入专用合成 Mod、创建零费用 dry-run，并读取持久化任务终态和能力。
`dry_run` 的 `validation.available=false` 不是格式验证成功；格式验证由上述真实文件流水线测试覆盖。
付费模型调用次数为 0，授权的 OpenRouter GPT-6 Luna 预算未使用。

本环境未安装两款游戏。因此本轮的“完成”限于产品集成与离线契约，不能声称所有 Mod 字符串均覆盖，
也不能声称游戏已成功加载。最终游戏验收由用户执行：启用原 Mod 与生成翻译包、检查依赖/加载顺序、
检查实际文本与占位符/grammar，并检查游戏日志。遇到未覆盖字段时，保留资源样本及版本/来源，再扩展规则。

## Agent API 与文档治理补充（2026-09-25）

面向操作者的步骤统一维护在 [Codex Skill](../../../.agents/skills/remis-agent/SKILL.md)
及其 [API 参考](../../../.agents/skills/remis-agent/references/api-workflow.md)。
[用户指南](../user-guides/multi-game-localization.md) 已登记到内置 Help Copilot 的帮助目录，
中英 API quickstart 和文档导航指向这些现行入口；旧 `agent.md` 只补迁移指引。

`game_support_service` 为 Agent API 和 Copilot 提供同一份静态能力与动态项目检查。
新增游戏时应更新适配器注册、格式/语言映射和该能力契约，再补扫描、输出、工具与文档回归；
工具 schema 的游戏枚举直接来自注册的 game profiles，不另维护游戏 ID 白名单。

- `GET /api/agent/capabilities`：每个游戏的 `game_support` 包含格式、输出方式、增量规则和限制。
- `GET /api/agent/projects/{project_id}/game-support`：扫描项目资源、条目与诊断；
  `POST /projects/inspect` 可显式指定游戏、源语言和只读版本提示。
- `POST /api/agent/jobs/plan`：以 `workflow=initial|incremental` 选择既有执行器，默认保持初次翻译。
  两种流程均沿用计划、审批、任务持久化和结果查询；增量 checkpoint 重试返回明确的不支持原因。
- 任务与 validation 读取当前任务输出 manifest 的 `needs_review`，把保留的旧译文标为人工复核，
  不作为可强制模型修复的条目。PZ/RimWorld 输出预览只检查包记录和资源存在，不调用 P 社部署器。
- 内置 Help Copilot 可查询能力、检查已选项目、引导并提交初次翻译计划供用户审批；
  增量执行入口为项目界面或 Agent API，聊天助手不会把增量请求当成初次翻译启动。

运行中接口验收使用隔离后端 `127.0.0.1:1456`：preflight 成功，未发现更新的正式 Release；
PZ 返回 1 个资源/1 个条目，RimWorld 返回 2 个资源/3 个条目；OpenAPI 已包含新路由与 workflow 枚举。
两款游戏的增量 dry-run 均持久化为 `completed`，产物为空、`validation.available=false`。
这是就绪检查，不是增量差异计算或格式验收。未调用模型，费用为 0。

该补充的 Agent/Copilot 回归为 208 passed（退出码 0），覆盖真实注册工具调用、API 路由与执行器分发、
审批/恢复限制、旧 P 社导出、输出包检查、人工复核投影和文档链接。Python 架构 guard、
compileall、diff 空白检查通过。

职责复核：`agent.py` 由 1000 行降至 965 行，架构基线同步降低；任务分发、输出路径选择、
游戏输出预览和人工复核投影抽到独立服务。新增 Python 服务均低于 800 行。
本补充不修改前端组件、状态或 effects。

## 本地提交记录

- `da262d50` — `feat(localization): add extensible PZ and RimWorld workflows`
- `8c6e4c0e` — `feat(ui): integrate multi-game project support and recovery guards`
- 支持矩阵、来源记录与验收说明随单独的文档提交保存。

全部留在本地 `codex/multi-game-adapters`；未 push、创建 PR、合并或发布。
