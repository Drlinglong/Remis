# Workshop 上传开发契约（#197）

截至 2026-10-10，此工作树提供发布预览、明确批准、持久执行记录、Task Center 投影和
独立 Python SteamUGC Worker 的首版实现。现有项目监控继续作为更新发现基础。
**本地自动化测试不等于 Steam 真实上传验收；此功能尚未达到桌面发行验收条件。**

用户提供的 SDK 1.65 已在独立子进程完成只读验证：SpaceWar（480）和 Victoria 3（529340）
均能初始化并返回已登录账户身份；不存在条目查询经过 manual dispatch 回调，返回
`steam_item_not_found`。每次进程结束均清理临时 App ID 文件。未调用 CreateItem 或
SubmitItemUpdate；这些验证不证明真实上传成功。SDK descriptor 已核对 `name_flat`、
`SteamAPI_InitFlat`、SetItemTags 的可选 admin 参数和 Win64 回调布局。

隔离验证的脱敏记录在此工作树 `.runtime/native-sdk-165-evidence.json`，未纳入 Git。

技术路线遵循 [#197 的技术决策](https://github.com/Drlinglong/Remis/issues/197#issuecomment-5175234716)：
Python Publication Service → 独立 Python Worker → Valve Flat API → 已登录 Steam Client。
未引入 Go/C++ wrapper，也未在 FastAPI 中加载原生库。

## 当前实现与适用范围

- GUI：`/steam-workshop/:workspaceId/publish`，复用工作区已采用的封面和描述版本。
- 输入：绑定项目中登记的独立翻译输出目录，以目录名称选择；不接受任意本机路径。
- 当前文件校验覆盖 Victoria 3、Stellaris、HOI4、EU4、EU5、CK3 的 YML 包；其他游戏包
  返回 `unsupported_package`，尚未提供 CSV、XML、Lua 等格式的完整发布校验。
- 当前校验检查语法、原文 key 的可辨认性、非空文本、原文 Token/格式规则和活动诊断。
  不将其表述为译文质量、完整覆盖或游戏内效果验收。原文同 key 有歧义时留待人工处理。
- 标题和描述按 UTF-8 字节限额检查；封面须匹配选定版本并小于 1 MiB。
- 默认新建、私密。更新目标须单独填写；工作区的 `workshop_item_id` 可能是原作者条目，
  **不会隐式作为更新目标**。
- 预览写入不可变 DB 记录；上传前重新检查输入，并复制、核验受控快照。Steam 读取快照，
  不读取仍可被编辑的原输出目录。源包、源缓存和用户现有输出不被改写。

## API 与批准身份

API 前缀：`/api/steam-workshop/workspaces/{workspace_id}/publication`。

| 操作 | 端点 | 外部副作用 |
|---|---|---|
| 可用输出和运行时信息 | `GET /options` | 无 |
| 生成不可变预览 | `POST /plans` | 仅 Steam 初始化/账户与游戏拥有检查，无上传 |
| 最近 50 条计划与状态 | `GET /plans` | 无 |
| 查询特定计划与状态 | `GET /plans/{plan_id}` | 无 |
| 批准并提交 | `POST /plans/{plan_id}/submit` | 获得批准后可创建/更新 Workshop |
| 登记人工核验 | `POST /plans/{plan_id}/verify` | 无远端写入；只记录用户确认的观察 |

提交请求必须包含严格布尔值 `approved: true` 与预览的 SHA-256 `fingerprint`。
请求不得携带用户名、密码、API key 或额外任意字段。
批准身份涵盖项目与路径身份、文件清单/哈希、原文校验身份、诊断、封面和描述版本、
Steam 账户、App ID、目标 item ID、可见性、语言、标签、标题与更新说明。
输入变化或预览超过 24 小时，必须重新生成并批准。没有 SDK 时仍可检视离线预览，
但 `allowed_actions` 不包含批准上传，提交接口同样拒绝执行。

## 持久状态和故障语义

主数据库迁移 29 添加 `workshop_publication_plans` 和 `workshop_publication_attempts`。
每个计划只能创建一次 attempt；DB 原子准入与唯一索引只允许一个活动发布。
另有单次执行租约阻止相同任务的重复 Worker 执行。Windows 命名互斥锁阻止跨 Remis
实例并发进入 Steam API，也保护后端崩溃后仍然存活的子进程。

| 状态 | 含义 |
|---|---|
| `preview` | 待批准；尚未上传 |
| `running` | 已持久准入；不代表 Steam 成功 |
| `succeeded` | 收到成功提交回调，EResult=1 且有 item ID |
| `failed` | 已知失败，例如上传前输入变化或 Steam 拒绝 |
| `unknown` | 可能已有远端副作用；须人工核验，禁止盲目重传 |
| `legal_agreement_required` | Steam 要求接受协议；不报告成功 |
| `resolved` | 用户已登记人工核验结果；不等于 Steam 确认上传 |

Worker 以 UTF-8 JSON Lines 汇报操作、创建的 item ID、进度、错误码和终态；不回传原生
stderr 或 Steam 凭据。原生回调结构与接口 accessor 从同一 SDK 的 `steam_api.json` 读取，
回调 ID/大小不匹配则停止。后端启动会把中断的发布记为 `unknown`，保留已收到的 item ID。
Task Center 只有 `succeeded` 映射为 completed；unknown/legal 在任务结果保留精确状态。

重复批准返回已有状态，不能触发第二次上传。同工作区存在 unknown/legal 记录时，新计划
也不得绕过该阻断。发布记录支持用户明确登记 `item_present` 或 `item_absent`：前者只能
继续预览更新所核验的已有 item，后者允许新计划；两者均不重试旧计划，不伪装成上传成功。
人工核验带 `verification_source: user` 与时间，始终区别于 Steam 回调证据。

## SDK 获取与开发环境

官方入口：[Steamworks SDK 文档](https://partner.steamgames.com/doc/sdk) 和
[下载列表](https://partner.steamgames.com/downloads/list)。下载列表需要登录；账户准入和
协议由 Valve 页面管理。不要在聊天中传递 Steam 密码、Steam Guard 代码或开发者凭据。

开发者可把合法取得的 SDK 解压在 J:，在启动开发后端前设置：

```powershell
$env:REMIS_STEAM_SDK_DIR = 'J:\SDKs\Steamworks\sdk'
scripts\developer_tools\windows\run-dev.bat
```

该目录必须含 `redistributable_bin/win64/steam_api64.dll` 和 `public/steam/steam_api.json`。
SDK 使用授权、DLL 再分发权利和最终安装包方案须独立确认；本仓库不带 SDK 二进制。
当前独立 Worker 依赖 Windows x64 Python。冻结应用如果未配置专用 Worker Python，
返回 `packaged_worker_not_configured`；**正式安装版不能要求普通用户安装 SDK/Python
或设置环境变量**，桌面构建接入仍是发行阻塞项。

## 下个版本发布前的验收门

1. SDK 1.65 初始化、描述兼容性与只读回调已验证；继续用实际测试条目验收目标所有权/
   App ID 检查。代码会在更新预览与执行前查询目标，并核验 consumer App ID 和账户拥有者。
2. 用户明确指定自己控制的测试条目/游戏和私密发布内容后，分别验证新建与更新；
   保存 Steam 成功回调、item ID、实际 Workshop 页面和结果日志。开发请求不代替上传批准。
3. 在真实协议/断线场景中验收人工核验登记与恢复更新；不得通过再 CreateItem 恢复已有条目。
4. 完成安装包 Worker、SDK 合法分发、生产 GUI 设置与只读诊断入口，以及 Task Center
   结果的明确展示。不得把开发环境变量当普通用户流程。
5. 扩展非 Paradox 游戏的包验证，明确游戏级包装要求和能力范围；不放宽现有校验。
6. 将已稳定的发布能力接入现有项目/任务结果入口和更新处理流程，再验收端到端 GUI。

本次没有调用付费模型，没有上传 Mod，没有部署到现有 Remis，也没有推送或创建 PR。

## 可维护性复核

现有 `SteamWorkshopWorkspace.jsx` 从 183 行增至 191 行，仅增加一个 lazy 发布页签，
没有新增业务 state/effect。新发布面板、预览和恢复表单分别承担输入、制品展示和人工
核验；API/轮询/批准身份控制放在独立 `useWorkshopPublication`（109 行），5 个工作流
state、2 个 effect。面板有输入对象与批准勾选 2 个 state，恢复表单有 3 个局部输入 state；
展示组件不持有 API 状态。所有新模块低于 600 行，未提高任何既有上限。

focused tests 覆盖 hook 的编辑失效、过期响应、重复点击、失败后的批准清除、历史恢复，
以及页面明确勾选批准、服务端 allowed_actions、未知终态、人工核验确认/拒绝。
后端分别划分 inputs、repository、orchestration、Task Center projection、运行时 composition
和 native adapter/worker；Python 架构门禁通过，未调整架构 baseline。

## 2026-10-14 提交前复核

117 个相关后端测试通过；85 个相关前端测试通过，其中编码完整性扫描在并行运行时
触发 5 秒超时，随后使用单 worker 独立重跑通过。edited locale JSON 解析及替换字符扫描、
compileall、Python 架构门禁、前端 build 和 Git diff 检查通过。全量 ESLint 为 0 error、
13 个未修改文件中的既有 warning，新发布模块没有新增 warning。此复核没有重新上传
或创建 Steam 条目，也没有把 SDK、隔离运行数据、node_modules 或 dist 纳入提交。


## 2026-10-14 本地整合验收

用户完成了 Victoria 3 私密新建条目的真实上传：持久记录为 `succeeded`，用户确认 Steam 页面可访问且内容正确。此证据仅覆盖本次开发版新建上传，不扩展为全部游戏、更新、异常恢复或发行包验收。用户操作见[Steam 工坊指南](../user-guides/steam-workshop.md)。

发布选项接口现在返回共享 Steam 游戏目录及绑定项目的默认 App ID；部署和发布共用同一 ID 映射。发布页提供 SDK 准备说明与独立教学上下文，并保留手动 App ID 和标签输入。
