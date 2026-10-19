# Remis v3.4.0 发布准备记录

准备日期：2026-10-20

状态：本地发布候选已构建并完成本地检查，现进入 PR／CI 审阅阶段，尚未正式发布。
基于 `v3.3.0`，整合分支为 `codex/release-next-20261014-integration`。
本记录保留本地构建验证快照；远端 CI、PR 与正式发布状态以 GitHub 为准。

## 中文

## 主要更新

- **减少无效格式修复：**正确译文中的独立变量可随目标语言语序调整位置；完整颜色和
  样式片段也可保持内部关系整体移动，避免正确译文被反复送去修复。变量内容、出现次数、
  格式闭合、嵌套及绑定关系继续检查。
- **汉化命令参考：**翻译、修复和 Copilot 可按游戏获取命令参考，补充 Victoria 3、
  CK3、HOI4、Stellaris 和 EU5 的相关上下文。
- **火星项目创建：**从 Workshop 文件夹创建项目的步骤更简洁，完善已有原生语言注册、
  本地化表选择和交付附属文件的处理。
- **工坊上传（测试功能）：**新增翻译包预览、明确批准、上传记录和结果核验流程。
  直接上传暂限已配置的开发测试环境；当前安装版尚不支持开箱即用的直接上传。
  入口及说明在全部 11 种界面语言中标注测试状态。
- **可靠性改进：**完善校验失败的反馈、归档事务、演示文件保护及工坊发布页面的状态同步。

## 工程质量与可靠性

- #234 的十条诊断对应五组原文／译文，全部纳入回归。相同 token 身份与出现次数，且
  保留已有格式片段内部 token 序列和嵌套关系时，才允许外层语序变化。
- 运行时比较提取到独立模块；保留现有 token 缺失、额外 token、修饰符／函数身份变化、
  错绑、格式身份、闭合及嵌套检查，不修改模型输入或引入 token 掩码。
- 修复后处理校验异常被忽略、空输出误报成功、归档写入事务和演示输出初始化等问题。
- 发布页面完善历史请求顺序、终态保留、卸载后响应处理、20 位 Workshop ID 和 422 错误展示。
- 发布恢复按条目身份和实际核验时间应用结果；同条目的后续“已删除”核验不再被旧“存在”记录覆盖，
  其他条目的核验仍不能解除已有条目约束。历史列表始终保留需要处理的运行中／未知／协议阻断记录。
- 包含 v3.3.0 之后已合入主分支的 Python 与官网依赖安全更新。

## 测试功能范围与兼容性

Workshop 上传保留私密默认值、不可变预览、显式批准、输入身份复核和未知结果人工核验。
运行时未就绪时仍拒绝上传，不因测试标记跳过任何校验或批准。

2026-10-14 已记录一次 Victoria 3 开发版私密新建条目上传成功，用户确认 Steam 页面
内容正确；该证据不涵盖其他游戏、更新已有条目、异常恢复或正式安装包。
当前发布包验证覆盖已支持的 Paradox YML 包，不宣称支持火星 CSV/Lua 上传。

冻结安装版 Worker 接入、SDK 分发方案、安装版端到端测试及更完整的真实上传验收仍待完成。
这些事项是将上传提升为正式功能的前提，本版以明确标注的测试功能提供入口。
不要要求普通安装版用户设置开发环境来完成日常使用。

Lua localization Agent 平台、Grom anchor 方案等设计文档不计作已交付功能。
本地构建验证阶段没有发起收费模型请求、Steam 上传、安装部署、合并、标签或 GitHub Release。
候选随后通过 PR 进入远端 CI，不代表已经合并或发布。

## English

## Highlights

- **Fewer unnecessary format repairs:** intact independent runtime tokens may follow target-language
  word order. Whole formatting spans may also move while preserving their internal relationships.
  Token identity, occurrence counts, closure, nesting and binding checks remain enforced.
- **Localization command reference:** translation, repair and Copilot can retrieve game-specific
  references for Victoria 3, CK3, HOI4, Stellaris and EU5.
- **Surviving Mars project creation:** simpler Workshop-folder import, with improved handling of
  native language registrations, localization-table selection and delivery sidecars.
- **Workshop upload (Beta):** package previews, explicit approval, durable upload records and
  outcome verification. Direct upload currently requires a configured development test environment;
  the installer does not yet provide ready-to-use direct uploads. All 11 UI languages mark the feature Beta.
- **Reliability:** improved validation failure reporting, archive transactions, demo-file preservation
  and publication-page state synchronization.

## Engineering quality and reliability

Issue #234's ten diagnostics represent five source/target pairs, all covered by regressions.
Runtime comparison permits a permutation only when canonical identities and occurrence counts match
and existing formatting spans retain their bound token sequences and enclosing span chains.
Missing or added tokens, changed modifiers or function identities, rebinding, changed formatting,
unbalanced markers and altered nesting remain checked. Model input is never masked or rewritten.

Publication state handling preserves terminal outcomes, sequences history requests, ignores late
responses after unmount, validates Workshop ID lengths and presents structured validation errors.
Recovery tracks each item's verification identity and time, so a later absence can supersede an
earlier presence for the same item. Unrelated absence never clears another item's guard, and
unresolved publications remain visible beyond the fifty most recent plans.
The candidate also includes Python and website dependency security updates merged after v3.3.0.

## Beta scope and compatibility

Uploads retain private visibility by default, immutable previews, explicit approval, input revalidation
and manual verification of unknown outcomes. Missing runtime support continues to block uploads.

One successful private Victoria 3 creation from the development build was recorded on 2026-10-14,
with user confirmation of the Steam page. This does not establish acceptance for other games,
updates, recovery scenarios or the installer. Package validation covers supported Paradox YML
packages, without claiming Surviving Mars CSV/Lua upload support.

Packaged Worker integration, SDK distribution and complete installer/live-upload acceptance remain
prerequisites for promoting uploads to a stable feature. Design proposals for a Lua localization
Agent platform and Grom anchors are not delivered features.

## 本轮发布门禁

| 检查 | 本轮结果 |
| --- | --- |
| 完整后端 pytest | 3018 通过、19 跳过、753 警告；332.26 秒 |
| 完整桌面前端 | 266 文件、1145 通过；668.62 秒 |
| 官网 | 64 测试通过；lint、生产构建通过；生产依赖 0 漏洞 |
| 桌面 lint／生产依赖审计 | 0 错误、13 个既有警告／0 漏洞 |
| 构建、资源、词典聚焦回归 | 34 通过，包含 Windows venv 执行路径回归 |
| 版本同步后的版本／构建聚焦回归 | 37 通过 |
| 发布恢复与 Worker 回归 | 50 通过，覆盖审查发现的两项恢复问题 |
| 最终文本编码复核 | 通过，覆盖候选版本与全部界面文案 |
| Python 架构守卫、compileall、Rust 格式与 diff 检查 | 通过 |
| v3.4.0 冻结后端与安装包 | PyInstaller、Vite、Tauri NSIS／MSI 构建通过；正式候选附件选择 NSIS EXE |
| 冻结后端冒烟 | 隔离 AppData／随机 localhost 端口；health、游戏适配器、Copilot、工坊 Demo、合成 FPK 通过 |
| 冻结版本与测试功能边界 | health／Agent capabilities 均为 3.4.0；工坊输出列表可读，上传运行时按既有规则拒绝 |
| 词典附件与 SHA256 | ZIP CRC、内部 SHA256、外部 sidecar 及 SHA256SUMS 已核对 |
| 远端 CI、PR | 由候选 PR 提供本轮远端执行结果，本表仅记录本地快照 |
| 合并、tag、GitHub Release | 未执行，需后续明确批准 |

最初完整后端验证为 3009 通过、19 跳过；之后完成 Windows venv 支持、版本同步与相关
37 项聚焦检查。预提交独立审查又修复两项发布恢复问题，新增 8 个回归案例；
最终完整后端 3018 项通过，候选已重新打包，最终结果和附件哈希以本表及下方记录为准。
完整后端测试不等于冻结发行环境验收。

前端初始运行使用共享依赖 Junction；几次无终态结果的运行已停止，不计为通过或测试失败。
最终结果来自本工作树独立 `npm ci` 的依赖及 Node 22.22.0：
`NODE_ENV=development npm test -- --maxWorkers=1 --pool=threads --reporter=verbose`。
编码完整性、locale 一致性、发布控制 hook 和页面批准检查包含在最终全量结果中。
完整前端配置加载时版本仍为 3.3.0；随后同步的 3.4.0 元数据由专门测试及最终生产构建核验。

本轮前端只更新 11 份 locale 的上传标题和说明，每份 JSON 替换两行，文件行数不变；
没有新增或修改生产组件／hook，没有新增 state 或 effect。
API／轮询状态继续由原有 `useWorkshopPublication` 管理。
token 比较主模块从 777 行降至 735 行，新比较模块为 64 行。
构建脚本从 765 行增至 771 行，新增环境路径 helper，既有 main 保持 184 行，未提高架构上限。
发布仓储从 160 行增至 185 行，继续只负责持久化及记录约束；回归测试从 361 行增至 457 行。

构建使用 `K:\Remis-Release-Builds\v3.4.0-20261020` 隔离 Windows venv，继承原构建环境基础包，
单独安装候选要求的 `pydantic-ai-slim==2.53.0` 及对应依赖；共享 `local_factory` 中的旧版本未修改。
构建环境 `pip check` 通过，Python 3.10.18 compileall 通过。

## 冻结候选复核与附件

额外启动自有冻结后端实例，用新的 AppData 目录和随机 `127.0.0.1` 端口检查。
`/api/agent/preflight` 成功检查官方 Release，当前正式版仍为 `v3.3.0`；
`/api/health` 与 `/api/agent/capabilities` 均返回候选版本 `3.4.0`。
工坊 options 返回一个演示输出包、默认私密可见性，上传运行时明确返回
`ready=false / packaged_worker_not_configured`。未发起模型调用、预览提交、Steam 上传或安装部署。
检查结束后只停止该自有实例。证据在忽略目录 `build/release-verification.json`。

候选源码基线：`47f8f8d6568873aefeff9ff5054deeb5998fc9c5`，加上本轮修复、
版本准备和测试文案。已改构建输入的原始文件 SHA256 清单位于 `build/candidate-inputs.json`；
清单摘要为 `b0cb230e833005e54a78026a17a534b33b7478c19bceb883d9bc6bd9a406f5ee`。
发布前若再改运行代码、版本元数据或资源，需要重建并重新记录哈希。

| 本地候选附件（`archive/release/stable/`） | 字节 | SHA256 |
| --- | ---: | --- |
| `remis-mod-factory_3.4.0_x64-setup.exe` | 48,812,313 | `8aa69ff151321b348d0dfc947a9b6d552ed4abbf31a720158988d3c4ee84e5da` |
| `Remis-SurvivingMars-Glossary_3.4.0.zip` | 415,009 | `3893102cc15dcaac9344ae1c937722824f49e5bfae716cad21d0ee7be5286531` |
| `Remis-SurvivingMars-Glossary_3.4.0.zip.sha256` | 106 | `081458c1fcc34117d2ef0c393f0a1eff2a938be440cb657ea283a91ef2c4d41e` |

`SHA256SUMS` 包含上述三项附件的哈希。安装包 PE FileVersion／ProductVersion 均为 `3.4.0`。
词典资源仍为 `2026.10.08.1`：英／简中 1711 条、三语 278 条，两个导入载荷均保留
`approved=false`。资源校验通过不代表词条全部经人工认证，下载也不批准导入。

构建日志保留可选 hidden-import 诊断：`pkg_resources.py2_warn`、`tzdata` 和未使用的外部
数据库驱动；流水线成功结束，并完成上述实际冻结进程检查，不将日志描述为零告警。
构建终态记录在系统 TEMP 的 `remis-v340-pre-pr-build.log`。

候选通过 PR 和完整远端 CI 后，才能继续审批合并、tag／Release 和附件上传。
本记录及本地安装包生成不代表合并或正式发布已经发生。
