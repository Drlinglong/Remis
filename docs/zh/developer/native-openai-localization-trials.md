# 原生 OpenAI：普通试译与 Batch 接手说明

> 发布策略：原生 Batch 可供高级 Agent 使用；即时 trials、模型审阅、术语 coverage
> 和 base-patch 默认关闭。使用前核对 live capabilities，不得自动开启开关。
> 具体实验开关、重启要求及默认 403/发现限制见
> [高级 Agent API 策略](advanced-agent-policy.md)。


2026-10-06，独立开发分支上的实验功能，不属于正式 v3.2.2。
执行平面是 Remis `/api/agent`；不要在外部脚本中直接调用付费模型后手写受管理译文。

## 实际协议

- 原生模型 ID 为 `gpt-6-luna`，Pro 用 `reasoning: {"mode":"pro","effort":"medium"}`；不使用 OpenRouter 的 `openai/`、`-pro` 或 `:batch` slug。
- 普通请求用 `POST https://api.openai.com/v1/responses`。
- Batch 先上传 `purpose=batch` 的 JSONL，再创建 `/v1/batches`，endpoint 为 `/v1/responses`、completion_window 为 `24h`。
- 凭据复用 Remis Settings 的 OpenAI 配置，仅在产品内部解析。不要把 key 写入对话、manifest、原始响应记录或命令行参数。
- 模型 GET 检查是无推理的访问检查；实际 Pro/Batch 参数接受必须以云端提交和结果为证。

官方依据：[推理模式](https://developers.openai.com/api/docs/guides/reasoning)、
[Batch](https://developers.openai.com/api/docs/guides/batch)。Pro 产生的额外模型工作计入用量；输出 tokens 已含 reasoning，不能再次相加计费。

## 共用工作流

普通与 Batch 复用同一个 `AgentBatchService` 的源文件冻结、语义术语匹配、分组提示词与 JSON schema。
原生 transport 把请求转成 Responses 形状，保留完整变量、标签、上下文和换行。
结果归一化保留原生 output/usage，再交给同一个 collector 严格检查 ID、数量、标签、换行、空输出、解析失败和原文回退。
写回仍使用已有 apply plan、归档 CAS、原子新目录和项目注册，不覆盖现有资源，也不自动安装或上传。

`api_provider` 为 openai 或 openrouter；旧 Batch 调用默认 openrouter，保留兼容。
`execution_mode` 为 batch 或 immediate，默认 batch。
`POST /api/agent/translation-trials/plan` 使用专用 schema，provider 固定 openai、mode 固定 immediate，拒绝其它显式选择，避免静默替换供应商。

普通计划示例：

```json
{
  "project_id": "REAL_PROJECT_ID",
  "file_ids": ["REAL_SOURCE_FILE_ID"],
  "api_provider": "openai",
  "execution_mode": "immediate",
  "model": "gpt-6-luna",
  "reasoning": {"mode": "pro", "effort": "medium"},
  "target_locale": "zh-TW",
  "game_language_slot": "Schinese",
  "translation_context_mode": "term_release",
  "term_release_id": "terms_2b0191f02045f3a5f82cbeab",
  "allow_provisional_terms": true,
  "group_size": 10,
  "max_group_chars": 20000,
  "style_guide": "採用臺灣常用正體中文；保留原有變數、格式與換行。"
}
```

随后 `POST /api/agent/translation-trials`：

```json
{"plan_id":"REAL_PLAN_ID","idempotency_key":"STABLE_BUSINESS_KEY","approved":true}
```

普通任务在后端执行；响应 queued 不是完成。通过 `GET /api/agent/batch-jobs/{id}` 读取持久状态。
每个请求发送前记录 in-flight，完成后持久保存安全原始响应。出现失败即停止后续付费调用，没有自动付费重试。
本版普通请求没有断电后自动续跑；请等普通试译完成再关机。已有响应仍保存，不能因中断盲目重新收费。

Batch 用同样配置，execution_mode=batch；调用 `/api/agent/batch-jobs/plan` 与 `/api/agent/batch-jobs`。
两种计划和同一个幂等键不应混用。相同 key 返回原任务，不会重复提交；新计划需要新 key。

## Batch：提交后关机、重启后取回

1. 只有远端 ID 已返回且 `submission_state=submitted` 才确认已接受。validating 不表示已经完成。
2. Remis 在 `<app-data>/agent_batch/batch.sqlite` 保存 job/plan/remote_id；哈希快照保存在同目录 artifacts。
3. 原生创建结果保留 input_file_id；不能确认创建结果时保留 submission_unknown，上传已成功的 file ID 也会记录，不盲重发。
4. 重启使用原工作树、同一 `REMIS_APP_DATA_DIR` 和后端端口，再 `GET /api/agent/preflight?provider_id=openai`。
5. `GET /api/agent/batch-jobs/{local_job_id}`，核对 remote_id，然后 `POST .../{id}/refresh`。
6. completed 后 `POST .../{id}/collect`。transport 通过 Files API 下载 output_file_id 与 error_file_id，并按 custom_id 对应，不能依赖顺序。
7. 检查诊断和候选数量；通过后才做 apply plan 与授权 apply。错误、原始响应和请求映射均保留。

不要删除工作树里的 `.runtime/app`、词典数据库、Batch SQLite、哈希快照、`source_mod` 或已写回的译文。
云端文件不是永久存储；取回后本地 artifacts 和审阅材料成为长期记录。

## 本次冻结样本与独立接手记录

规范来源：`J:/SurvivingMarsModdingNotes/traditional-base-audit-20261005/luna-trial-20261006-v1/`。
`manifest.json` 保存来源 CSV SHA-256、种子、100 个 ID 与 40 个子集 ID。
100 条为科技 25、事件 25、教程 20、百科 20、标签 10；短 34、中 36、长 30。
40 条严格为同一组子集，用来对照普通与 Batch 的质量及接口表现，不是第二个独立质量考试。
没有给模型发送官方简中译文作为答案；词典与风格指南是唯一翻译参考。

`RESUME-STATE.json` 保存本地/远端任务 ID、计划 ID、稳定提交 key、模型、词典版本、工作树与 app-data 路径。
同目录的 API 回读 source/requests/catalog/remote 快照保存在开发工作树外，便于下一位 agent 接手。
下一位 agent 先读这些记录和持久 job 状态，不要重新抽样，不要重新提交旧 Batch。

## 验证与剩余边界

模拟测试覆盖原生文件上传/创建/结果下载、Pro 格式转换、秘密脱敏、usage 不重复计算、幂等普通任务、原生 Batch 重启后取回与不重复提交，以及既有 apply。
跨进程持久性与云端参数仍须保留实际回执，不以模拟测试替代。
没有美元硬预算上限、GUI 或自动取回调度；整款游戏翻译尚未开始。

## 2026-10-06 实际执行与恢复验证

- 普通 100：`batch_5d17274353c343f68a540d58e265751b`，10 个原生 Responses 请求均返回，所有 100 个候选 ID 齐全。
- 严格 collector 为 `collected_with_errors`：百科 ID `5419` 的迁移词遗漏一对 `<em>` 标签；该十条请求整组不接受，因此接受 90 条。没有自动重试、手动修饰原始答案或放松校验。
- 其中四个完整资源文件共 80 条，经原 apply 工作流保存为新目录并归档。百科的另 20 条仍在原始响应及独立审阅表；不要将 80、90、99、100 四种不同口径混用。
- 普通用量：输入 161,116（其中缓存 35,534），输出 37,895（其中思考 16,547）；此输出总数已含思考，不再叠加。原生 API 未返回美元账单。
- Batch 40：本地 `batch_d0d37af275d345c2bdf9d8691f70f443`，云端 `batch_6ac3be48a96c81908098f73e1e64b759`；完成前状态会变化，以 `RESUME-STATE.json` 与 refresh 为准。
- 随后 Batch 实际 completed，4/4 请求返回，无远端执行错误；output 文件已通过 Files API 下载并在 Remis artifacts 与独立目录保存。全部 40 个候选齐全，38 条独立标签/换行检查通过；ID 6509、628936758990 各新增一对 `<em>`，collector 按整组只接受 20 条。其中完整文件 18 条经原 apply 保存和归档。用量输入 65,721（缓存 16,389），输出 16,355（含思考 7,858）。同 ID 普通与 Batch 对照见 `40-review.json` 与 `40-试译逐条审阅.zh-CN.md`。这次结果不是 Batch 天生质量更差的统计证据，分组上下文与生成随机性也有差别。
- 普通完成后，实际停止该开发版的 Uvicorn 父进程和应用子进程，再用规定 launcher 启动。重启后同一 SQLite 读回普通原始成果及原 Batch ID，并成功原生 refresh，当时完成 1/4 请求。没有再次创建 Batch。证据为 `backend-restarted-health.json`、`job-readback-*-after-restart.json` 与 `40-native-refreshed-after-restart.json`。
- 重启应用后继续使用原 `REMIS_APP_DATA_DIR`；不是全电脑重启测试，也不是断电故障注入测试。Batch 不依赖本机持续在线，下一位 agent 必须先取回旧任务再决定其它动作。
- `100-review.json` 与 `100-试译逐条审阅.zh-CN.md` 保存全部候选、逐条技术结果及事后简中对照；`100-试译审阅.html` 可独立搜索。`初读问题.zh-CN.md` 记录有限初读发现，并非完整质量评分。

历史验证记录：原生/Agent/词典 focused 测试 57 passed；原生与既有 Batch workflow 20 passed；Python 架构检查和相关 compileall 通过。生产代码分别保留 transport、普通 orchestration、持久 repository、collector 与 apply 边界；没有新增前端 GUI、状态或 effects，也没有提高架构豁免上限。v3.3.0 已纳入原生 Batch API；本文的即时模型试验保留代码但默认关闭，需显式开发开关，见[高级 API 策略](advanced-agent-policy.md)。

## Pro 模式和推理强度是独立参数

`reasoning.mode=pro` 是增加模型工作、最后返回单个答案的执行模式，不是高于 max 的强度档位。
`reasoning.effort` 控制该模式内部的推理投入；GPT-6 Luna 支持 medium、high、xhigh、max 等。
省略 effort 默认 medium，不要把标为 Pro 的任务描述成最高推理。
两者要分别记录，检查响应中的实际 reasoning 字段，不能仅凭模型昵称判断。
来源：[官方推理指南](https://developers.openai.com/api/docs/guides/reasoning)。

2026-10-06 第二轮：沿用 40 个 ID，词典 v0.1.5（274 条，新增 Explorer 别名），
20 条补同对象英文语境。两份正文除 model/reasoning 完全一致。
GPT-6.1 Sol standard high 与 Luna pro medium 各 4/4 普通请求完成，各 40 条通过标签/换行检查并收集。
原生返回确认两组模式及强度；这不是 Luna Pro 最高推理的对照。
先冻结 40 条匿名 A/B 初审再揭盲：30 条差异不显著、9 条偏好 Sol、1 条两份待修。
其中 7 条偏好涉及机制/专名/呈现风险，2 条主要是表达；不是独立人类或台湾母语专业认证，也不是通用模型排名。
原始响应、词典覆盖证据、全部意见与恢复状态见
`J:/SurvivingMarsModdingNotes/traditional-base-audit-20261005/sol-luna-comparison-20261006-v2/`。
本轮未 apply、未重试、未全量翻译。以后重跑不同 effort 必须新增试验版本，不能覆盖这轮结果。

别名审阅复用现有词典的 `variants.en` 与术语元数据，同步更新并冻结；通用编辑修改已审别名会使审阅依据失效。
本轮新增两个别名集成测试，词典/Batch/native focused 35 passed；架构检查通过。
生产文件规模：审阅模块 57 行、词典桥接服务 193 行、schema 69 行，无前端状态/effects 或架构上限增长。
