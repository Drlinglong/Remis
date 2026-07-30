# Model Arena 开发契约

本文把[Model Arena 产品意图](../product-intent-model-arena.md)转换成实现边界，并区分
3.1.0 已实现行为、当前差距和稳定性观察项。普通操作见
[模型竞技场用户指南](../user-guides/model-arena.md)。

## 范围

包含项目抽样、参赛配置、模型执行、匿名投票、本地历史、结果汇总、导出和删除。
不包含正式翻译执行、项目默认模型修改或全局 benchmark 排名。

## 当前入口

- 侧栏“翻译工作流 → 模型竞技场”；
- 页面路由 `/model-arena`；
- Task Center 只显示竞技场后台执行状态并跳回对应 run；
- 历史记录保存在竞技场自己的表中，不依赖任务事件保留期。

后端路由前缀为 `/api/model-arena`：

| 方法与路径 | 当前行为 |
|---|---|
| `POST /runs` | 创建草稿、冻结配置并抽样；不调用模型 |
| `POST /runs/{id}/resample` | 只在草稿状态重新抽样 |
| `POST /runs/{id}/start` | 确认调用并以幂等键启动后台任务 |
| `POST /runs/{id}/retry-failures` | 再次确认后只重试失败参赛者 |
| `GET /runs/{id}` | 按当前状态裁剪匿名或揭晓后的数据 |
| `PUT /runs/{id}/samples/{sample}/vote` | 新增或修改当前样本投票 |
| `POST /runs/{id}/complete` | 检查投票覆盖并揭晓身份 |
| `GET /runs` | 查询本地历史 |
| `GET /runs/{id}/export-preview` | 生成精确导出预览 |
| `POST /runs/{id}/export` | 明确批准后写出 JSON |
| `DELETE /runs/{id}?confirmed=true` | 确认后删除单次历史 |

## 设置与确认

`CreateModelArenaRunRequest` 要求：

- 有效项目和目标语言；
- 2 或 3 个不同的 `provider_id + model_id`；
- 样本数 3–12，默认 6；
- 默认使用项目上下文和项目词典；
- 可选固定 seed。

前端草稿展示项目、源／目标语言、参赛者、样本数量、预计请求数、词典快照、seed 和每条
样本文本。创建与重新抽样都不调用模型。

开始弹窗显示模型数、样本数、预计请求数和“费用未知”，并要求勾选确认。后端仍强制
`confirmed_model_calls=true`。相同 run 与幂等键不会重复调用；不同幂等键不能再次启动
已经开始的 run。

## 抽样契约

`ModelArenaSamplingService` 从项目源语言本地化文件构建候选池，排除空文本和纯变量，按
规范化文本去重，并记录长度、保护标记、复杂标点、换行、术语命中和文件来源等特征。

算法用 seed 做可复现的分层覆盖；候选足够时限制单文件过度占比。默认选择 6 条，当前
接口允许 3–12 条。样本保存源文本哈希、特征和匿名显示置换；对外 DTO 删除 entry key、
文件路径和行号。

## 冻结配置与执行

创建 run 时冻结：

- 项目、游戏和语言方向；
- 参赛供应商与模型的非秘密配置；
- 当前游戏主词典和项目词典；
- 样本、seed 和抽样算法版本；
- 是否使用项目上下文。

参赛者串行执行同一批样本和同一生产 prompt，避免本地资源竞争。执行服务不会使用会把
失败输出回退成原文的常规 `translate_batch()`；未知供应商直接失败，不切换替代模型。

模型请求、解析前最终回答、解析状态、输出、硬格式错误、耗时和事件写入独立 SQLite 表。
秘密、认证头、完整 provider envelope 和独立 reasoning/thinking 字段不进入持久化证据。

## 当前状态机

```text
draft → queued → running
                    ├─ 全部成功 → voting → completed
                    ├─ 至少两人成功 → partial_failed → voting / retry → completed
                    ├─ 仅一人成功 → partial_failed → retry（产品目标：不可投票）
                    └─ 全部失败 → failed → retry
```

完成状态要求每个样本都有一条投票。投票可以是 `winner`、`tie`、`reject_all` 或
`unjudgeable`。只有 `completed` 才返回真实供应商、模型和结果汇总，也只有完成后才能导出。

## 当前部分失败行为与产品边界

3.1.0 当前实现把“至少一人成功”都记为 `partial_failed`，并允许查看、投票、完成或明确
确认后重试失败参赛者。

产品规则更精确：

- 三人局有两人成功时，已经存在两份可比较成果，可以继续投票并完成；
- 两人局只有一人成功，或三人局只有一人成功时，不足两份成果，不能形成比较；
- 所有已生成结果都应保留并显示警告，失败参赛者只能在用户确认后重试。

当前后端没有在 `save_vote()` 和 `complete_run()` 检查成功参赛者至少为 2，因此“仅一人
成功也能用无法判断完成整局”仍是实现差距。未来修复应在后端统一计算可比较参赛者数量，
前端在不足 2 人时只提供查看、重试或放弃，并补两人局和三人局的边界测试。

本轮只记录契约，不修改状态机。

## 匿名与结果

`ANONYMOUS_STATUSES` 包含 `queued`、`running`、`voting` 和 `partial_failed`。这些状态下
后端移除供应商／模型身份、请求正文和真实 contestant 映射，仅返回不透明 output ID 与
按样本置换的候选标签。

完成后结果汇总每个模型的被选次数、偏好率、理由、硬错误、受影响样本数、请求数、耗时
和失败码。格式统计是并列证据，不自动否决用户选择，也不产生自动“冠军”。

当前结果页没有：

- 把偏好模型设为项目默认模型的动作；
- 自动开始初次或增量翻译；
- 引导用户带着判断返回正式翻译的提示。

前两项符合禁止副作用；第三项是产品允许的低风险提示增强，但 3.1.x 尚无升级计划。

## 本地保存与正式翻译边界

竞技场使用 migration 009 建立独立的 runs、contestants、requests、samples、outputs、votes
和 events 表。全部候选输出可以保存为本地证据，不要求用户先批准某个候选。

这些写入绝不能解释为采用译文。竞技场代码没有写项目翻译文件、修改项目默认模型或启动
正式翻译的入口。

## 导出契约

只有 `completed` run 可以导出。流程是：

1. `GET export-preview` 返回将要写出的精确 JSON；
2. 用户选择 evidence 或 summary-only；
3. `POST export` 要求 `approved=true`；
4. 后端在 Remis 输出目录创建 `model_arena_exports` 并写 JSON；
5. 前端下载文件并可打开所在路径。

Evidence 模式包含实际 prompt、项目样本、译文、投票备注和解析前最终回答；summary-only
省略正文。两种模式都排除 entry key、相对／绝对路径、密钥、账号、API URL、认证信息和
独立推理字段。Remis 不直接发帖或上传。

## 当前实现差距

| 产品意图 | 当前实现 | 状态 |
|---|---|---|
| 至少两名参赛者成功后可正式投票 | 当前一名成功也可用无法判断完成 | 边界冲突 |
| 默认用 6 条控制成本 | 默认 6，可手动选择 3–12 | 一致；不是硬上限 |
| 确认项目、语言、模型和样本 | 草稿页全部可见，调用前另有确认弹窗 | 一致 |
| 费用无法可靠确认 | 明确显示费用未知 | 一致 |
| 全部样本投票后才完成 | 后端检查每条样本已有投票 | 一致 |
| 不自动选模型或启动翻译 | 没有相应写入或动作 | 一致 |
| 完成后可以给下一步提示 | 当前尚未实现正式翻译提示 | 可选增强，非缺陷 |
| 本地保留全部候选 | 独立 SQLite 历史持久化 | 一致 |
| 不偷偷导出 | 预览与 `approved=true` 双边界 | 一致 |

## 测试门禁

必须保留或补充：

1. 草稿不调用模型，开始与重试缺少确认均返回 409。
2. 默认 6 条，schema 拒绝少于 3 或多于 12。
3. 2／3 个参赛者必须不同；未知供应商不被替换。
4. 同一 run 与幂等键不会重复计费。
5. 所有参赛者收到相同冻结样本、prompt、词典和配置。
6. 投票前后匿名边界不能被 query 参数绕过。
7. 所有样本未投票时不能完成。
8. `partial_failed` 至少两人成功时可投票；只有一人成功时只能查看、重试或放弃。
9. 本地历史完整，删除需要确认并级联限定在该 run。
10. 导出预览与批准后的文件内容一致，敏感字段和路径被移除。
11. 竞技场从不写翻译文件、修改项目模型或启动翻译。

## 代码证据

- `scripts/schemas/model_arena.py`
- `scripts/routers/model_arena.py`
- `scripts/core/services/model_arena_service.py`
- `scripts/core/services/model_arena_sampling_service.py`
- `scripts/core/services/model_arena_execution_service.py`
- `scripts/core/services/model_arena_export_service.py`
- `scripts/core/repositories/model_arena_repository.py`
- `scripts/react-ui/src/pages/ModelArenaPage.jsx`
- `scripts/react-ui/src/components/modelArena/`
- `scripts/react-ui/src/services/modelArenaService.js`
- `tests/test_model_arena_api.py`
- `tests/core/test_model_arena_repository.py`
- `tests/core/test_model_arena_sampling_service.py`
- `tests/core/test_model_arena_execution_service.py`
- `tests/core/test_model_arena_export_service.py`
- `scripts/react-ui/src/components/modelArena/*.test.jsx`

更长的首版设计背景已归档为[历史实施计划](../../archive/developer-history/zh/model_arena_implementation_plan.md)；
它只用于回顾设计演化，不代表当前实现。
