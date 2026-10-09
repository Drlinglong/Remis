# Batch Agent API 与术语发布物：接手说明

2026-10-05。**独立开发分支上的实验实现；不属于本次 v3.2.2 release。**
工作树：`J:\V3_Mod_Localization_Factory-worktrees\batch-term-workflow-20261005`。
基线：`9f67a6f097c4d5873d524e7e768c43f04c7bf427`。
没有增加 GUI，没有执行付费推理或全游戏翻译。模拟工作流通过不代表真实提供方验收。

上句是最初开发时点记录。2026-10-06 后续用户授权 100 条普通试译和 40 条 Batch，
并指定优先 OpenAI 原生接口；原生入口与恢复方法见
[原生 OpenAI 试译说明](native-openai-localization-trials.md)。不要继续要求 OpenRouter 凭据。

## 当前授权与下一步

玲珑已授权先完成：①术语提取、正体候选、审查合并与流程；②独立 Batch API 开发。
后续试译已改为**冻结同一组100条，普通API比较 Luna Pro、GPT-6.1 Sol high、Claude Opus5.5 high**，暂不使用 Batch。
100条比较、全量翻译、导出、安装和上传均不由本接口自动启动。
不要把旧的“300条Batch试译”或 GPT-6 Sol 当作当前任务；也不要虚构 GPT-6.1 Sol Batch 可用。
不静默换模型。开发时只使用假 transport；真实费用由后续授权的小样本校准。

每次操作先 `GET /api/agent/preflight`，报告 release check 和当前实际工作树。
本工作树 VERSION=3.2.2 是发布候选基线的版本，不意味着这些新功能已经发布。
2026-10-05 最初检查时最新正式 GitHub Release 仍为 v3.2.1；2026-10-06 本轮
Agent preflight 已确认最新正式版为 v3.2.2，没有更新版本。Batch 仍只在独立开发分支。
FPK 的128MiB默认资源额度修复已在发布候选中同步（`b5c13419`）；Batch不应一并cherry-pick。

## 启动与状态目录

从本工作树根目录使用 `scripts\developer_tools\windows\run-dev.bat --backend-only`。
可先设置绝对 `REMIS_APP_DATA_DIR` 与空闲 `REMIS_BACKEND_PORT`；开发验证使用1456，生产默认1453。
绑定仅127.0.0.1。凭据只通过Remis Settings配置；接口、日志和文档都不返回密钥。

持久记录在 `<app-data>/agent_batch/batch.sqlite`，独立 `user_version=1`，不增加主数据库迁移。
大对象在同目录 `artifacts/<sha256>.json`，原子写入并校验内容哈希。
新译文在既有 DEST_DIR 下 `agent_batch/<apply-id>/<实际语言>/`；已有 outputs 不覆盖、不清理。
停机后云端继续处理已接受的任务；重启后显式refresh/collect取回，不需重新提交。
不能确认远端接受的请求保留unknown，不能建议关机前把unknown当成已接收。

## 实现边界与可复用分工

`batch_repository`负责唯一提交意图与状态；`batch_artifacts`负责不可变快照；
`openrouter_batch_transport`负责固定上游协议；`agent_batch_service`负责编排；
`batch_sources/prompts/collection/rendering`分别冻结、构造、严格检查、渲染；
`batch_apply_archive/apply_service/project_guard`负责归档CAS、恢复日志和短期项目锁；
`term_release_service`负责不可变词典版本；`routers/agent_batch`是薄API。

没有导入Aventine的运行器或评分器：其Python最低3.11，本应用验证环境为3.10。
实际复用的是冻结样本、快照/哈希、原始响应、明确失败类型和审查记录的契约。
Aventine `structural_validation.classify_structural_result` 可将变量数量异常交给裁判；
生产写回使用现有游戏adapter与严格tokens校验，不接受此宽松策略。
completion/output usage可能已含reasoning，不能再次重复相加计算收费。

语义单位由`concept_id + sense + context_keys`区分；不能仅以英文相同合并词条。
`zh-TW`是内容/归档语言；`Schinese`是引擎加载槽。二者必须分别保存。
第一版正体渲染需明确传兼容的中文槽；不向整个应用宣称游戏原生支持此语言。
现有Mars五列CSV和ParadoxYAML是主要验证路径；其他adapter尚无真实Batch验收。
超过800行模块/120行函数/复杂度20不得加例外；运行结构守卫。

## API参考

所有路径均以`/api/agent`开头，OpenAPI包含可调用schema。

| 方法和路径 | 行为 |
| --- | --- |
| POST `/term-releases` | 以approved发布不可变词典；同版本内容变化409 |
| GET `/term-releases/{id}` | 完整词典、成熟度和artifact引用 |
| POST `/batch-jobs/plan` | 冻结注册源文件、词典、提示词及匿名模型目录，无付费调用 |
| GET `/batch-jobs/plans/{id}` | 重启后读计划 |
| POST `/batch-jobs` | approved、plan_id、idempotency_key；唯一一次远端提交 |
| GET `/batch-jobs` | 本地列表，project_id/limit/offset |
| GET `/batch-jobs/{id}` | 持久状态及allowed_actions |
| POST `/batch-jobs/{id}/refresh` | 查询远端，保存安全原始响应及usage |
| POST `/batch-jobs/{id}/collect` | 严格校验候选，保留原始失败；不修改项目 |
| GET `/batch-jobs/{id}/artifacts/{kind}` | source/requests/catalog/remote/collection，安全原始内容 |
| POST `/batch-jobs/{id}/retry/plan` | 仅选定failed custom_ids，新计划继承已通过译文 |
| POST `/batch-jobs/{id}/reconcile` | approved绑定unknown；需完成结果的精确请求ID集合验证 |
| POST `/batch-jobs/{id}/apply/plan` | 可选file_ids；预览完整文件的新输出、hash、归档旧值 |
| POST `/batch-jobs/{id}/apply` | approved与apply_plan_id；写新文件、归档、注册、读回验收 |

计划请求示例（project_id/file_ids用真实注册ID替换）：

```json
{
  "project_id": "PROJECT_ID",
  "file_ids": ["SOURCE_FILE_ID"],
  "target_locale": "zh-TW",
  "game_language_slot": "Schinese",
  "source_column": "Text",
  "model": "openai/gpt-6-luna-pro:batch",
  "translation_context_mode": "term_release",
  "term_release_id": "TERMS_ID",
  "allow_provisional_terms": true,
  "style_guide": "採用臺灣常用遊戲用語；保留專名和格式，語氣簡潔自然。",
  "reasoning": {"mode": "pro"},
  "provider_only": [],
  "group_size": 30,
  "max_group_chars": 12000
}
```

必须显式选择`translation_context_mode`：none或term_release；暂定词典还需显式ack。
source_column是CSV源列选择，默认Text；选择Translation时缺译文阻断，不能回退英文。
官方游戏完整CSV有20列，不能直接交给五列adapter；先通过获授权的准备流程导入适配形状，
保留完整原件与语境证据。当前不为全游戏创建翻译项目。
模型目录只核验所选`:batch`端点；参数支持/限额/费用仍需真实试验。
Pro模型保留`-pro`基础slug并发送`mode: pro`；不加虚构的输出token上限。
计划24小时过期。`cost_estimate=null`明确表示输出/思考尚未校准；不是免费或预算上限。
模型目录价格被快照保存，费用在usage中返回；暂无美元硬限额或自动分批控费。

提交示例：`{"plan_id":"PLAN_ID","idempotency_key":"稳定业务请求ID","approved":true}`。
同key同fingerprint返回原job；不同payload同key拒绝；同计划换key也拒绝。
付费重试必须先产生新retry计划，再单独approved提交；collect不会收费重试。

## 术语与agent交付契约

2026-10-06 更新：术语编辑与审阅已接入现有词典系统。新标准流程是
`/api/agent/glossaries/terminology` 导入 → 原词典界面编辑/审阅 →
`/api/agent/term-releases/from-glossary` 冻结 → Batch 引用。
详见 [词典接入与 API 契约](terminology-glossary-integration.md)。
下述 v0.1.1 数量为原始交付历史；早期人工决定后的正體 v0.1.2 为 278 条，
23 项人工确认、110 项 Sol 已审阅、145 项候选，4 项待决已解决。

2026-10-06 机制复核后的最新快照是正體 v0.1.4：
`terms_2b0191f02045f3a5f82cbeab`，274 条，maturity=provisional。
主词典 ID=291 共 278 条：33 approved、107 reviewed、134 candidate、4 pending；
4 项 pending 未进入快照。玲珑已确认 Herbs、Artificial Muscles、Stone Garden、
Melancholic、Printed Electronics、Martian Steel、Saint、Sustained Workload、
Multispiral Architecture、Sustainability 的本轮建议。原有人工决定完整保留。
这不表示整份词典通过台湾母语或游戏内验证；实时词典状态应从 API 读取。

本轮实际服务为本工作树的 `127.0.0.1:1456`，capabilities.batch_jobs.experimental=true。
当前本地 Batch 任务列表为空；没有真实 OpenRouter 批次验收，没有付费提交。
提交、重启恢复、取回、失败分类、重试计划和写回已经有实现与模拟测试，仍需真实小批次
核验上游模型/Pro 参数、结果格式、usage/计费及恢复取回。不要把模拟通过称为生产验收。

term请求含game_id、locale、version、maturity、approved及terms；可用scope_id隔离大型Mod/世界观词库。
不带scope_id的是game-wide词库；Mod词库应显式给scope_id，concept_id也应包含源命名空间，
不能把不同Mod的同一数字ID当成同概念。跨版本合并由带证据的决定完成，不按字符串自动合并。
每term：concept_id、source、translation、sense、aliases、context_keys、evidence_refs、reviewer、
review_dimensions、unverified_dimensions。证据支持带path/hash/record_id的对象；服务不擅自读任意路径。
同英文多义分别保留，只按相关source/alias检索给提示词，并带sense，禁止全局查替。
完整证据保留在本机artifact；模型提示只带语义字段，不发送本机证据路径清单。

原始候选JSONL、来源manifest、逐项决定、corrections和release各自保留；审计不要覆盖原件。
本轮交付在 `J:\SurvivingMarsModdingNotes\traditional-base-audit-20261005\terminology-v0.1\`。
SC：1720候选，1711非空可作为官方来源提取基线，9空译隔离。
TW：278候选，133项经Sol路由审计（111接受/18修订/4待决），274条暂定发布物；
145条只经Luna，必须在reviewer中明确。数值置信度未校准，仅用于分流。
来源路径/hash错配有独立corrections；SpaceY为官方品牌/赞助者译名“太空人”，不是通用宇航员。

玲珑是简中母语者，可以流利听读繁中，台湾写作/用语经验有限。
人工审阅着重含义、机制和可读性；模型另列台湾用语证据与不确定性，不能标成专业或母语认证。
将来新游戏/大型Mod按领域分片：Luna提取/候选→强制规则及低置信路由→Sol审计→版本冻结→同文本比较。
不能只审自报低置信；缺证据、多义、机制差异、来源冲突、引用变更始终进入审查。
具体JSONL契约与阈值建议见normalized-release/agent-artifact-contract.json。

## 完整性、恢复与不自动执行的动作

源文中的`$...$`、`[...]`、格式标记及真实换行直接呈现，不变成占位符。
按custom_id配对，顺序无关；未知/重复ID、重复JSON键、缺结果、empty/parser/count/tokens/truncated
分别报告。发生foreign结果时整个集合禁止应用；失败保留安全raw artifact，绝不回退原文充数。
同源输出仅明确同形术语可放行，否则人工核查。
只应用每个eligible entry均通过的完整文件；CSV检查Translation列，其他列原样。

apply：私有staging写入并hash验证→新目录原子rename→归档版本完整(path,key,text)验证→
归档译文旧值CAS→注册路径→读回注册文件→完成日志。跨库/文件系统不冒充单个原子事务。
既有归档snapshot_hash只哈希文本，不能当完整身份；完整三元组不匹配时阻断。
恢复使用同apply计划；接受已写入的相同结果，第三方改译文或文件则409；不回滚删除已有输出。
每job固定一个apply计划，不能换计划绕过恢复；只在短apply阶段拿现有项目锁，24小时云等待不拿锁。
apply生成可管理译文资源，**不是完整可安装Mod包**；后续原有export仍需单独授权。
不自动安装、export、上传Steam、取消/删除远端Batch或轮询外部其它任务。

提交前先记录unknown意图。任何断连/响应未取得ID/保存失败均可能远端已接受，禁止盲重POST。
reconcile只对精确custom_id集合的completed结果绑定；metadata/时间/数量猜测不能绑定。
无法验证时保持unknown，需要操作者调查；第一版没有强行重发按钮。

## 协议依据与验收

官方依据：[OpenRouter Batch Quickstart](https://openrouter.ai/docs/batch-quickstart)，2026-10-05重新核验。
固定`POST /api/v1/batches`与`GET /api/v1/batches/{id}`；单一chat-completions文本形状。
顶层endpoint/model/provider/completion_window先序列化、requests最后，窗口24h。
body省略model继承顶层基础slug，provider只用only；结果inline，无单独下载端点。
云端输入/输出保留30天；取回后有本地hash快照，不依赖永久远端留存。

聚焦检查：`tests/test_agent_batch_persistence.py`、`tests/test_agent_batch_workflow.py`、
（包含FastAPI合同用例）及`tests/test_agent_api.py`；架构守卫与compileall。
测试只用假的模型与fake key，独立app-data；不要改成使用用户真实密钥的测试。
之后需明确授权的真实小样本验证：catalog参数、Pro推理参数、远端结果形状、usage/cost和重启取回。
通过这些验证之前，能力标记experimental，不宣传全量或多游戏生产验收完成。

2026-10-06 状态复核：使用运行后端的 `local_factory` Python 3.10 环境重跑
`tests/test_agent_batch_persistence.py`、`tests/test_agent_batch_workflow.py`、
`tests/test_glossary_terminology_integration.py`，38 项通过（69 条弃用警告）。
这些测试使用模拟 transport，不能据此声称真实 OpenRouter Batch 参数、计费或恢复已经验收。
