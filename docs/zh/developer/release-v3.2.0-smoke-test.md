# v3.2.0 发布冒烟与风险清单

本文是交给测试和发版人员的执行清单。它区分“接口能返回”与“持久化业务结果正确”，后者才
能作为发布依据。

## 1. 通道与入口矩阵

| 场景 | stable | Agent Preview | 重点观察 |
|---|---|---|---|
| 版本 | `3.2.0` | `3.2.0-agent-preview.1` | Version 页面、Tauri 配置、后端 `/api/health` |
| 后端端口 | `1453` | `1454` | 不能互相占用或串数据 |
| 数据目录 | `RemisModFactory` | `RemisAgentPreview` | Preview 不应读写 stable 数据 |
| Copilot、档案馆、断点续传 | 开启 | 开启 | 未知 channel 必须关闭档案馆与断点续传 |

首先分别检查：

```powershell
Invoke-RestMethod http://127.0.0.1:1453/api/health
Invoke-RestMethod http://127.0.0.1:1453/api/agent/preflight
Invoke-RestMethod http://127.0.0.1:1453/api/agent/capabilities
```

Agent Preview 将端口替换为 `1454`。每次真实工作流前都要先看 `preflight` 的 release check、
provider setup 和 `allowed_actions`，不能只因为接口响应 200 就继续。

## 2. 项目档案馆

1. 用一个小型真实 Mod 运行“仅整理术语”和“整理完整档案”，确认任务结果、项目名、范围和
   源快照都持久化。
2. 打开已发布版本，检查摘要、实体、事件、来源路径和 provenance；确认原始 Mod 文件的
   内容、编码和目录结构未被改写。
3. 从发布版本创建草稿，改一条摘要或关系，保存并再次打开；确认旧发布版本不变，新草稿带有
   正确父版本 ID 和“已继承”标识。
4. 在源文件变化后重新查看发布版本，确认页面显示过期，而不是静默把旧档案当成最新档案。
5. 在发布或删除档案请求中重复点击／重复发送，观察是否出现重复发布、半删除或错误 500；
   删除前确认项目名、审批和“分析任务正在运行”保护都生效。

重点代码定位：

- UI 与 tree-v2：`scripts/react-ui/src/components/neologism/archiveTreeV2/`
- 发布与草稿：`scripts/routers/context_archive.py`、`scripts/core/repositories/context_archive_repository.py`
- Agent 读取与删除：`scripts/routers/agent_context.py`
- 研究链路与证据：`scripts/core/services/context_research_service.py` 及其测试

## 3. Agent / Copilot

1. Copilot 只问一个文档问题，确认回答带来源／置信度，不把 developer 文档、源码、密钥或用户
   Mod 全文当作帮助语料。
2. 让 Copilot 生成“创建项目 + 初次翻译”计划：检查只读规划不写盘；批准前不产生模型费用；
   批准后 Task Center 中出现准确 task ID。
3. 发送未知 action、额外参数和模型伪造的 risk/approval 字段，确认服务端 Registry 拒绝或
   覆盖，而不是照单执行。
4. 访问 `/api/agent/capabilities`，确认 `resume_from_checkpoint`、`repair`、`export` 和
   `cancel` 的批准门；确认 `pause` 明确为不支持，`context_analysis` 明确为未开放。
5. 不配置 Provider 或 preflight 失败时，确认 Agent 停在门禁并给出可行动信息；不要把失败当成
   “没有任务”或成功。

重点代码定位：

- Agent capability 与 preflight：`scripts/routers/agent.py`
- Copilot Registry：`scripts/core/copilot/actions.py`
- Copilot 计划：`scripts/core/copilot/workflow.py`、`scripts/routers/copilot.py`
- 前端入口：`scripts/react-ui/src/components/copilot/`

## 4. 断点续传、取消与重启

1. 启动一个翻译任务，在有检查点后关闭桌面端／结束 worker，再启动应用；确认原任务为中断，
   项目锁不会永久占用，检查点仍存在。
2. 用兼容的源文件和配置快照执行“继续”，确认只创建一个子任务，父任务 ID、`resume_from`
   和最终状态可在 Task Center 找回。
3. 用同一个幂等键重复提交继续请求，确认返回已有子任务，不重复收费、不重复写入。
4. 修改源文件或关键翻译配置后再继续，确认兼容性门禁拒绝恢复，并保留原始任务；选择“从头
   开始”后确认新任务与旧任务关系清晰。
5. 对支持的翻译任务执行取消，确认进入 cancelling 后不会被迟到的 worker 改回 running 或
   completed，并最终释放项目锁。尝试暂停，确认返回不支持而不是假装暂停。
6. 同一项目同时启动两个互斥任务，确认一个被锁保护；取消、失败、重启后再次检查锁是否可用。

重点代码定位：

- 恢复路由：`scripts/routers/translation_recovery.py`
- 状态与检查点：`scripts/core/services/translation_recovery_service.py`、
  `scripts/core/repositories/task_repository.py`
- Task Center 动作：`scripts/routers/tasks.py`
- 取消与 worker 终态：`scripts/core/services/translation_task_service.py`

## 5. 容易出问题的地方与定位方法

| 现象 | 优先检查 |
|---|---|
| stable 页面有按钮但 API 404 | `scripts/core/feature_policy.py`、`scripts/react-ui/src/config/features.js`、`scripts/web_server.py`；先比对 channel |
| Preview 读到了 stable 项目／任务 | `scripts/build_profile.py` 的 port/data folder、Tauri dev profile、环境变量 `REMIS_BUILD_CHANNEL` |
| “已启动”却找不到结果 | Task Center 数据库中的 task ID、`allowed_actions`、业务结果路径；不要看聊天文字 |
| 恢复重复创建任务 | `translation_recovery.py` 的幂等键、父子 task 关系、数据库唯一约束 |
| 恢复被拒绝 | 源文件／配置快照兼容性、checkpoint 版本、项目锁和任务状态 |
| 取消后项目仍锁死 | `cancelling` → terminal 的 worker 收尾、锁释放和重启恢复路径 |
| 档案发布内容不连续或污染 | provenance、实体规范化、事件链和 route-aware gold；检查原始 source fixture，不只看页面摘要 |
| Agent 提议不存在的 action | `/api/copilot/actions` 与 `scripts/core/copilot/actions.py`；文档中的未来候选不能输出 |
| Provider 失败反复重试 | preflight、Provider 错误分类、task fatal terminal state 和日志目录 |

日志默认在 `%APPDATA%\RemisModFactory\logs`；Agent Preview 使用其隔离的数据目录。提交诊断
时不要包含 API key、Cookie、完整私人路径或整个用户 Mod。

## 6. 发布门槛

- 后端测试、前端测试／lint／build、Python compileall 和架构门禁全部通过。
- `git diff --check` 通过；没有把工作区绝对路径、密钥或临时产物写进发布文件。
- `RELEASE_NOTES_v3.2.0.md`、版本元数据、stable/preview 配置和 feature tests 一致。
- 上述冒烟场景至少各跑一次；失败时记录 task ID、project ID、build channel、日志位置和
  可复现步骤，再决定是否阻止发布。
- 本分支完成本地 commit 后才进入玲珑的人工测试；push、PR、merge、tag 和正式发布仍是
  后续独立动作。
