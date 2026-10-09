# 高级 Agent：术语覆盖与稀疏模型审阅

> 发布策略：原生 Batch 可供高级 Agent 使用；即时 trials、模型审阅、术语 coverage
> 和 base-patch 默认关闭。使用前核对 live capabilities，不得自动开启开关。
> 具体实验开关、重启要求及默认 403/发现限制见
> [高级 Agent API 策略](advanced-agent-policy.md)。


v3.3.0 保留此高级实验 API，但默认关闭。仅在显式启用对应实验开关后提供，没有普通用户 GUI 入口。
先 `/api/agent/preflight` 和 `/api/agent/capabilities`；凭据由 Remis 设置内部解析，永不返回。
现有授权继续有效；明确指定模型的付费试验不需要重复确认。

## 术语覆盖

先 GET `/api/agent/terminology-coverage/scans?project_id=PROJECT_ID&limit=50&offset=0` 查找既有扫描。
返回 `scans`、`limit`、`offset`，列表仅带摘要和快照身份；详细报告仍按 scan ID 获取。
`limit` 为 1–100，offset 非负。省略 project_id 可查同一受管存储内的全部扫描。

`POST /api/agent/terminology-coverage/scans`

```json
{"project_id":"PROJECT_ID","file_ids":["REGISTERED_SOURCE_ID"],"glossary_id":291,"locale":"zh-TW","minimum_occurrences":3,"example_limit":3}
```

返回持久 scan ID、输入快照哈希与摘要。GET `/scans/{id}` 返回 report。
GET `/scans/{id}/artifacts/{kind}` 可读取 source、reference、glossary、report 的冻结快照，
读取时校验哈希；不需要手工读取数据库或猜测 artifact 文件路径。
报告包括源名称/源 ID、游戏对象、官方参考（ID+英文相同）、包含该词的源条目数、原文例句、
现有概念匹配、未覆盖词形与别名建议。计数使用最长字符串覆盖重叠区间，不等于语义出现次数。
没有模型调用，也不写词典。缺少语境的未绑定名称可能漏检；结构化名称候选不自动等于术语。

观察到的同对象单复数可以提出高置信度别名；不能把同对象的升级名、变体建筑名当作同义词。
缺少同对象证据的词形仍需语境审核。pending/rejected 词条不算已覆盖的发布约束。

`POST /scans/{id}/candidates`，传 `candidate_ids`（最多 500）与 `approved: true`，
复用项目档案的 SourceEvidence、词形归一、TermOnlyResult/Variant、
ContextTreeV2TermCandidateService 和现有 NeologismManager 候选存储。
没有第二个可编辑候选库；导入状态是 pending，保留既有已确认决定，不自动覆盖词典。
重复扫描导入选择 `append_evidence` 策略，保留既有 pending 的非空译名建议、理由、置信度和旧证据；
新证据和来源变体去重追加。项目档案其他入口继续使用原有刷新策略。

新词条/别名由现有 glossary Agent append/review 接口维护，再冻结新 term release。
扫描派生报告仍用受管哈希快照记录，便于复现；不要直接改数据库或源文件。

## 审阅计划与付费运行

先 GET `/api/agent/localization-reviews?project_id=PROJECT_ID&limit=50&offset=0` 查找已有任务。
返回 `jobs` 与分页参数，包含持久状态和 allowed_actions，不执行模型请求。
翻译任务的对应列表是 `/api/agent/batch-jobs`；两类任务不可互相当作 apply 输入。

`POST /api/agent/localization-reviews/plan`

```json
{"translation_job_id":"COMPLETED_AGENT_BATCH_OR_TRIAL_ID","reference_project_id":"REFERENCE_PROJECT_ID","reference_file_ids":["REGISTERED_REFERENCE_SOURCE_ID"],"reference_locale":"zh-CN","model":"gpt-6-luna","execution_mode":"immediate","reasoning":{"mode":"pro","effort":"max"},"term_release_id":"FROZEN_TERMS_ID","allow_provisional_terms":true,"group_size":20,"max_group_chars":40000,"style_guide":"游戏的语言风格指南"}
```

可传 `entry_ids` 选子集；默认所有保留的、解析出完整 ID 组的候选。以前标签校验失败的候选
仍可被审阅，不能把它们藏掉。当前来源是 Agent translation-trials/batch-jobs 的持久任务，
终止 Batch 的已返回有效候选也可以审阅，缺失或失败请求不能假装提供了候选。
不支持直接传任意外部译文；原有普通任务中心 job 不是这个 ledger 的 job ID。
参考项目当前支持 Mars 五列 CSV 的 Translation；空参考、重复全局 ID、英文变化都不盲配。
其他游戏的审阅仍能通过适配器校验语义 tokens，参考导入适配器可另扩展。

计划固定输入、译文、参考、词典、请求与模型目录，模型 GET 预检不收费。
返回 entry_count、request_count、reference_match_count、paid_calls=0 与 allowed_actions。
Pro 模式与 effort 独立；两者都要记录，不能把 Pro 描述成默认 max。

`POST /api/agent/localization-reviews`

```json
{"plan_id":"REVIEW_PLAN_ID","idempotency_key":"STABLE_BUSINESS_KEY","approved":true}
```

普通审阅在后台运行，每次请求前记录 in-flight，返回后即保存原始响应；失败停止，不自动付费重试。
这里 `immediate` 指本地后台任务持有普通 HTTP 长连接，不代表 OpenAI 的原生后台模式。

长时间 Pro 评估使用 `execution_mode: background`：仍是常规 `/v1/responses`，设置
`background=true, store=true`，不是 Files/Batches，也没有 Batch 折扣。每组提交前标记未知，
拿到 response ID 后立即持久保存，再用 GET `/v1/responses/{id}` 查询。
ID 保存在 job 的 response_submissions 内，逐组状态为 not_submitted、submission_unknown 或 accepted；
response_status 记录 queued/in_progress/completed/failed 等真实状态。refresh 只查询，不生成或重提请求。
以 GET job 的 `shutdown_recovery_ready:true` 作为关机恢复条件；它要求全部请求已 accepted，
活动响应回报 background/store 均为 true，或终止结果已保存本地。重启同一存储后按旧 job ID refresh。
终止响应已下载后使用本地缓存，不再依赖云端文件长期可用。远端保留仍受账户数据保留策略影响；
ZDR 强制 store=false 的账户不能套用普通存储保证，当前实现显式请求 store=true。
官方行为见 [OpenAI 原生后台模式](https://developers.openai.com/api/docs/guides/background)。

如果原生后台创建的应答丢失但有可验证 response ID，用 POST `/{job_id}/responses/reconcile`，
传 `custom_id`、`response_id` 和 `approved:true`。Remis 核验 plan/custom/hash 的完整 metadata，
同一 ID 不可绑定给多个请求，也不可替换已保存的 ID。缺少 ID 时不能自动重提未知请求。
剩余未提交请求保持 not_submitted，不在重启时悄悄收费。后台查询的并发更新按单请求原子合并，
不能丢掉其他组的 ID，也不让迟到的 queued 状态覆盖已保存的终止结果。
若派发期间退出，全部 ID 已保存时由记录推导派发完成；若新进程发现旧派发未结束且尚有
unknown/not_submitted，会标记 dispatch_interrupted。已接受响应继续查询，未知和未提交条目保留，
绝不因为补状态而补发付费请求。

`execution_mode: batch` 使用原生 Files + Batches，返回远端 ID 后才能确认已接受并关机。
GET `/localization-reviews/{job_id}` 查询；Batch 用 POST `/{job_id}/refresh` 取回。
未知提交只通过 POST `/{job_id}/reconcile`，传真实 remote_id/approved，且必须验证完整 custom ID 集合。
不同计划不得混用 key，数据库原子意图防止重复收费；审阅记录 kind 与翻译/apply 隔离。

## 稀疏输出与本地重建

模型每组只见短编号 001…020；Remis 持久保存它们与真实源 ID/entry ID 的映射。
输出仅 `findings` 数组：entry_label、category、severity、confidence、简短 explanation，
以及最小 `edits[{find,replace}]`。无问题条目不输出记录，没有强迫重抄整句或整段。
模型未报告问题的条目叫 no_reported_issue，绝不等于人工认证通过。

原文/译文/参考/语境都是数据；原文控制含义，简中可错，不作为不可质疑的标准答案。
评估检出能力时不发送已知错误清单、Sol 答案或人工判词。规则诊断不作为此轮模型的提示答案。

编辑在本地重建：每个 find 必须恰好匹配一次，匹配不到或多次均不可应用。
建议再走现有游戏适配器，以及标签/换行/强调结构完整性检查。
百分比后误接人数量词、已确认术语被强调标签割裂等是 warning，不擅自语义改写。
所有修改都是建议，automatic_apply=false；不存在从审阅报告直接安装、发布或覆盖原译文的动作。

GET `/{job_id}/artifacts/{kind}`：entries、requests、source、reference、remote、report。
`saved_results` 可以读取逐次已保存响应，包括中断任务；在途响应是否未知会明确返回。
普通审阅关机不会自动续跑，先检查持久结果，不因 job 显示 running 就盲目再收费。
上述限制针对 immediate 长连接；background 的已接受远端请求可按 response ID 恢复。
Batch 的持久 ID、原输入文件与本地下载恢复规则见原生 Batch Skill。

`completed`、`expired`、`cancelled`、`failed` 都是终止状态。后面三种状态不代表没有成果：
有 output_file_id/error_file_id 时，仍须下载并持久保存已返回的结果。
审阅报告保留真实远端状态，缺失、过期或失败的请求不计入已审阅条目；原译文仍不覆盖。
翻译 collect 也可以收集终止 Batch 的部分结果，但只有满足完整文件校验的文件才允许规划 apply。
取消和过期 Batch 的部分成果行为见 [OpenAI 官方 Batch 指南](https://developers.openai.com/api/docs/guides/batch)。

Responses 远端失败，即便附带可解析 JSON，也不能当作有效审阅。`incomplete/length`、失败、
空输出、解析失败、ID 错误分别记录，稀疏 `findings: []` 仅在正常完成时表示模型未报告问题。

只读呈现工具：`python -m scripts.developer_tools.remis_review_report JOB_ID OUTPUT_DIR --base BACKEND_URL`。
它从 Agent API 导出报告和原始记录，重建建议文本，生成 Markdown/可搜索 HTML，没有模型调用。

外部字形/用语转换的独立样本对照见[繁化姬试验工具](zhconvert-conversion-trials.md)。
它从 Agent API 读取已冻结参考，单独保留原始转换候选，不写回项目或伪装成模型 job。

## 分层实现与测试

Coverage 纯算法、受管 scan 服务、项目档案 candidate bridge 分开。
Review 输入/schema、prompt、collection、service、runner、Batch transport 调度与结果持久化分开。
复用现有 BatchRepository/BatchArtifacts 和 OpenAIBatchTransport；没有第二凭据/词典/候选存储。
新增 review_job/review_plan kind，在现有 ledger 内隔离，不能被翻译 apply 接口调用。

Focused tests 覆盖稀疏编号、零问题/未审区别、错误编号、不可匹配编辑、同对象误合并、
结构警报、幂等、重启读取、原译文保留、审阅不可 apply 和原生 Batch 重启取回。
原生普通后台另测 response ID 重启读取、部分结果/未审条目区分、未知应答恢复、并发 ID 保留、
终止状态不回退，以及 refresh 仅 GET、绝不调用 Batch 或重新生成。
没有前端 state/effect 或生产组件增长；Python 架构扫描通过，不提高既有豁免。

2026-10-06 收尾验证：以下 focused suite 共 120 passed（76 条既有 SQLAlchemy 弃用警告），
compileall、Python architecture guard、git diff --check 与三个 Skill 的 quick_validate 均通过。
测试使用独立 `.runtime/test-app`，不复用真实工作项目库或真实模型传输。

```powershell
python -m pytest -q tests/test_agent_api.py tests/test_agent_batch_workflow.py tests/test_glossary_terminology_integration.py tests/test_native_openai_trials.py tests/test_localization_quality_workflows.py tests/test_localization_review_background.py tests/core/test_context_tree_v2_term_only.py
python scripts/developer_tools/check_python_architecture.py
python -m compileall -q scripts tests
```

运行这些命令时使用规定开发启动器选择的 Python 环境。所有新增生产模块均在 800 行内，
未提高 architecture baseline；输入/schema、纯检查、持久化、模型传输和报告呈现保持分离。

## 本地实例与接手

工作树 `J:\V3_Mod_Localization_Factory-worktrees\batch-term-workflow-20261005`；backend 1456。
运行证据 `J:\SurvivingMarsModdingNotes\traditional-base-audit-20261005\quality-workflows-20261006`。
先读该目录 RESUME-STATE.json：保存 corpus/scan/review/translation/dictionary ID。
本轮是 40 条既有 Luna medium 候选交给 Luna pro max 审阅，并非全量初翻。
首次 immediate 首组约 30 分钟后 upstream_transport_error，0/40 已审，后组未发出；
旧请求实际是否计费未知，不能由缺失 usage 推导免费。后 20 条另以常规 Pro background 提交，
前 20 条用户已单独明确同意重提。两组现均 completed/collected，40/40 有效审阅，
共 12 条有意见、14 条 findings；原译文未覆盖，测试仍固定用 v0.1.7。
具体 ID、输入、原始响应和决定保存在 RESUME-STATE.json 及各组报告。
`LunaProMax审阅效果.zh-CN.md` 和 review-evaluation.json 记录独立评价：
9 条有效问题、4 条可选润色、1 条低置信度语境提醒；原先留出的 8 个检查点中，
4 个检出、3 个未检出、1 个语境风险未解决，不据此声称一般正确率。
review-costs.json 按普通费率算得本轮约 US$0.0307449；旧超时请求费用未知，另列不混入。
测试结束另冻 v0.1.8，新增 Asteroid/Asteroids、Exotic Mineral Treatment、Exotic Mineral Therapy，
278 个可入快照词条，4 个待决定；新词是 model-reviewed，不宣称人工核准。
后端 worker 真正重启后已读回两组相同 job/response ID，未重提；
actual-background-worker-restart-readback.json 保存证据。此验证不是整机断电试验。
现在完整结果已下载本地，接手应直接读取，禁止将旧任务再次付费提交。

三个高级入口在本工作树内，未全局安装，也未进入正式 release：

- `.agents/skills/remis-native-batch/SKILL.md`
- `.agents/skills/remis-terminology-coverage/SKILL.md`
- `.agents/skills/remis-model-review/SKILL.md`

父 Skill remis-agent 已链接这些入口。它们调用受管 API，而不是自己实现翻译、词典或凭据存储。
不要清理工作树、.runtime/app、source_mod、my_translation、outputs 或 artifacts。
项目档案候选复用现有 `data/cache/neologism_candidates` 存储，也需要保留；该运行数据目录已加入 Git 忽略。
这不是第二个术语数据库，冻结报告和词典快照仍存于 `.runtime/app/agent_batch`。
