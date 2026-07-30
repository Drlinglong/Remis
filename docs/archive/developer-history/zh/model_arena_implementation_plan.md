# Remis 模型竞技场实施计划

> **文档状态：** historical
>
> **原用途：** Model Arena 首版实施前的设计与切片计划
>
> **Copilot 语料：** excluded
>
> **现行替代：** [Model Arena 用户指南](../../../zh/user-guides/model-arena.md)、
> [产品意图](../../../zh/product-intent-model-arena.md)与
> [开发契约](../../../zh/developer/model-arena-contract.md)

## 1. 产品定位

模型竞技场是 Remis 内部的轻量级、人工偏好驱动的试译工具。用户在正式翻译整个 Mod 前，从同一批代表性原文中比较 2 或 3 个候选模型，完成匿名选择后再查看模型身份、偏好次数、偏好理由、格式硬错误、失败类型与耗时。

它解决的是“我在这个 Mod、这个语言方向和这套当前配置下更愿意使用哪个模型”，不是建立全局模型排行榜，也不替代 Aventine 的可复现 translation recipe benchmark。

首版必须保持以下边界：

- 只比较用户明确选择的 2 或 3 个不同 `provider + model` 组合。
- 所有候选接收相同源文本、语言方向、游戏配置、术语表和生产 prompt。
- 模型身份、格式校验和耗时在全部投票完成前不展示，避免影响人工偏好。
- 模型调用属于可能产生费用的动作。创建样本不调用模型；开始试译前必须再次确认调用规模。
- 结果只在本地持久化。Remis 不自动上传竞技场数据。
- 导出前必须预览。默认导出可复核的 evidence 包，包含实际 prompt、原文、解析后的译文、模型解析前的最终回答文本和用户备注；字段级排除 entry key、文件路径、秘密、账号与 API URL。

## 2. 已验证的当前基础

| 能力 | 当前入口 | 竞技场的复用方式 |
|---|---|---|
| 翻译工作流菜单 | `scripts/react-ui/src/components/layout/AppSider.jsx` | 在 `workflowItems` 中增加“模型竞技场” |
| 页面路由 | `scripts/react-ui/src/App.jsx` | 增加 `/model-arena` 懒加载路由 |
| 模型与供应商列表 | `scripts/routers/config.py` | 复用非秘密的 provider/model 配置；不复制或返回 API key |
| Provider handler | `scripts/core/api_handler.py` | 为每个参赛者创建独立 handler |
| 生产翻译 prompt | `scripts/core/base_handler.py` | 通过 `FileTask` / `BatchTask` 使用生产 `_build_prompt()` 与解析路径 |
| 已有 benchmark 适配 | `scripts/developer_tools/evaluate_translation_quality.py` | 抽取可复用的生产 prompt/执行/评分逻辑到产品 service，开发工具改为调用公共 service |
| 格式硬校验 | `scripts/utils/post_process_validator.py` | 对每条 `source -> output` 调用 `validate_entry()`，统计 `ValidationLevel.ERROR` |
| 后台任务与事件 | `background_tasks` / `task_events` | 只复用运行进度、取消与诊断事件，不作为竞技场历史来源 |
| SQLite 迁移 | `scripts/core/db_migrations.py` | 新增独立的竞技场表与索引 |

## 3. 用户流程

### 3.1 设置

1. 从“翻译工作流 > 模型竞技场”进入。
2. 选择一个活动中的项目/Mod。
3. 确认源语言，选择一个目标语言。
4. 选择 2 或 3 个候选模型。允许同一 provider 的不同模型，不允许完全重复的组合。
5. 选择样本数。默认 6 条，首版允许 3–12 条。
6. 选择是否沿用项目已绑定术语表和当前 Mod context，默认沿用。
7. 点击“生成试译样本”。此动作只读取本地项目，不调用模型。

页面展示候选池大小、样本特征分布、预计模型调用数、配置缺失与不可用 provider。用户可以在未开始前“重新抽样”，每次生成新的 seed。

### 3.2 付费调用确认

“开始竞技场”前显示：

- 参赛模型数量；
- 样本数量；
- 预计请求数；
- 云端模型可能产生费用，Remis 无法可靠估算时明确显示“费用未知”；
- 本地模型可能占用较长时间；
- 失败模型不会被静默替换为其他 provider/model。

用户明确确认后，后端创建 `kind=model_arena` 的后台任务并开始执行。相同 `run_id + start_idempotency_key` 不得重复计费。

### 3.3 匿名比较

每条样本显示：

- 固定在顶部的原文；
- 2 或 3 个等权候选卡片；
- “这版更好”按钮；
- “难分高下”“都不满意”两个非强制选项；
- 选择候选后可多选理由：
  - 更忠实；
  - 更自然；
  - 意境/风格更好；
  - 更简洁准确；
  - 术语更合适；
  - 更符合角色或语境；
  - 用户备注（可选填写，默认随 evidence 包导出）。

候选顺序按样本单独置换，而不是整场固定为 A/B/C。后端保存真实映射；投票 DTO 只暴露 opaque `output_id`，在完成前不返回 provider/model。

用户可以修改尚未提交整场结果的选择。样本少于 2 个有效输出时标记为“无法比较”，不强迫投票。

### 3.4 结果

全部可比较样本完成后，用户点击“完成并揭晓”。后端锁定投票并返回模型映射。

每个模型展示：

- 被选为最佳的次数；
- 全部打平次数与全部不满意次数；
- 只以 decisive votes 为分母的偏好率；
- 各偏好理由的次数；
- 产生硬错误的样本数；
- 硬错误总次数，并按稳定 `error_code` 分类；
- 结构化响应失败、数量不匹配、调用失败次数；
- 总耗时与每请求耗时；
- 已知配置快照与未知字段。

结果标题必须使用“本次试译偏好”，不得把 3–12 条样本包装成全局模型推荐或统计显著的排行榜。

## 4. 代表性抽样

纯随机会过度抽到短句和重复文本，也可能完全错过变量、格式标记或术语。首版使用“可复现的分层覆盖 + seed 随机打破平局”。

### 4.1 候选池

从项目中 `file_type=source` 的受支持本地化文件读取条目，沿用 `parse_loc_file_with_lines()` 的 UTF-8/BOM 处理。候选条目：

- 必须有非空可译文本；
- 排除纯变量项；
- 对完全相同的规范化原文去重；
- 保留 key、相对文件路径、行号和源文本哈希；
- 不把绝对本地路径写入竞技场日志或导出。

### 4.2 特征

为每条候选计算：

- 长度桶：短、中、长，阈值按当前 Mod 的长度分布计算；
- 是否包含 `$...$`、`[...]`、`§...§`、`#...#` 等受保护格式；
- 是否包含换行、引号或复杂标点；
- 是否命中当前有效术语表；
- 相对文件身份；
- 重复文本组。

### 4.3 选择算法

1. 使用系统随机数生成 `sample_seed` 并持久化。
2. 逐条贪心选择“新增特征覆盖最多”的候选。
3. 在覆盖收益相同的候选之间，使用 `hash(sample_seed, candidate_id)` 确定随机顺序。
4. 在候选池足够时，每个文件最多选 2 条；不足时自动放宽。
5. 覆盖完成后，用带 seed 的无放回 reservoir sampling 填满剩余名额。
6. 保存算法版本、seed、候选池数量和每条样本的 feature tags，使同一版本可复现。

默认 6 条的目标是提供低成本的个人决策信号，不承诺统计显著性。历史页必须允许用户查看 seed 和抽样特征。

## 5. 执行公平性与失败规则

- 所有参赛者使用同一组样本、相同顺序和同一份已冻结的有效配置快照。
- 参赛者执行顺序由 run seed 决定并持久化。
- 首版按参赛者串行执行，避免本地模型资源竞争和配置热切换污染结果。
- 每个参赛者默认把本次样本作为一个生产 batch；如果 provider 的安全 batch 限制要求拆分，所有参赛者使用同一拆分方案。
- 沿用 handler 内已有的解析和重试规则；竞技场 service 不额外静默重试。
- 单个参赛者失败时整场进入 `partial_failed`，保留其他结果。只允许用户明确确认后重试失败参赛者。
- 不回退到其他 provider/model，不用原文填充缺失译文。
- 持久化并默认导出每次请求的 `completion_text_before_parse`：即 provider adapter 选取的最终 assistant content、进入 Remis `_parse_response()` 之前的文本。它不是完整 HTTP/API 响应对象，也不包含独立 reasoning/thinking 字段。
- 同时记录 `completion_source`，区分正常 `assistant_content` 和其他明确但仍来自最终回答的兼容路径。独立 reasoning 字段不作为日志采集，也不得作为最终回答 fallback。
- 不保存 provider 原始响应 envelope、HTTP headers、请求认证信息或未被采用的独立 thinking/reasoning 内容。若模型把思考与答案混在同一个 `content` 字段中，只能在导出预览中显示并由用户检查，Remis 不声称能可靠拆分。
- 保存实际 user prompt、adapter 添加的 system instruction、有效生成参数、原始 prompt 哈希、规范化回答哈希、字符数、解析状态、稳定失败码和解析后的译文。

## 6. 格式硬错误定义

每条有效输出调用：

```python
PostProcessValidator.validate_entry(
    game_id=...,
    key=...,
    value=translated_text,
    source_lang=...,
    source_value=source_text,
    target_lang=...,
)
```

硬错误包括：

- `ValidationLevel.ERROR` 结果；
- 响应不可解析；
- 返回条目数量不匹配；
- 受保护 token parity 失败；
- 空输出。

同一条 validator 结果按 `(sample_id, contestant_id, code, normalized_details)` 去重。结果页同时展示：

- `hard_error_occurrences`：硬错误事件总数；
- `affected_sample_count`：至少一个硬错误的样本数。

格式统计在投票完成前隐藏。它是与人工偏好并列的观测维度，不自动覆盖用户选择。

## 7. 持久化与独立日志

新增 migration 009。竞技场历史不放入 `project_history`，也不依赖可能被保留策略清理的 `task_events`。

### 7.1 表

#### `model_arena_runs`

- `run_id TEXT PRIMARY KEY`
- `project_id TEXT NULL REFERENCES projects(project_id) ON DELETE SET NULL`
- `project_name_snapshot TEXT NOT NULL`
- `game_id TEXT NOT NULL`
- `source_lang_code TEXT NOT NULL`
- `target_lang_code TEXT NOT NULL`
- `sample_seed TEXT NOT NULL`
- `sampler_version TEXT NOT NULL`
- `sample_size INTEGER NOT NULL`
- `eligible_count INTEGER NOT NULL`
- `status TEXT NOT NULL`
- `settings_json TEXT NOT NULL`
- `created_at / started_at / completed_at TEXT`

状态：`draft | queued | running | voting | completed | partial_failed | failed | abandoned`。

#### `model_arena_contestants`

- `contestant_id TEXT PRIMARY KEY`
- `run_id TEXT NOT NULL REFERENCES model_arena_runs(run_id) ON DELETE CASCADE`
- `provider_id TEXT NOT NULL`
- `model_id TEXT NOT NULL`
- `execution_order INTEGER NOT NULL`
- `config_snapshot_json TEXT NOT NULL`
- `config_fingerprint TEXT NOT NULL`
- `prompt_fingerprint TEXT NOT NULL`
- `status TEXT NOT NULL`
- `request_count INTEGER NOT NULL DEFAULT 0`
- `elapsed_ms INTEGER`
- `failure_code TEXT`

`config_snapshot_json` 不得包含 API key、token、masked key、账号、绝对路径或 API URL。无法从 provider 得知的量化、上下文长度和解码参数保存为 `unknown`，不得推断。

#### `model_arena_requests`

每个实际模型请求一条记录，用于证明模型收到什么、返回什么，以及 Remis 如何解析：

- `request_id TEXT PRIMARY KEY`
- `contestant_id TEXT NOT NULL REFERENCES model_arena_contestants(contestant_id) ON DELETE CASCADE`
- `batch_ordinal INTEGER NOT NULL`
- `system_instruction TEXT`
- `prompt_text TEXT NOT NULL`
- `effective_parameters_json TEXT NOT NULL`
- `prompt_sha256 TEXT NOT NULL`
- `completion_text_before_parse TEXT`
- `completion_source TEXT NOT NULL`
- `completion_sha256 TEXT`
- `usage_json TEXT NOT NULL`
- `parse_status TEXT NOT NULL`
- `failure_code TEXT`
- `elapsed_ms INTEGER`
- `created_at TEXT NOT NULL`

`system_instruction` 与 `prompt_text` 保存本地实际值。`usage_json` 只保存 provider 明确返回的 token 数等非秘密元数据；不保存响应 envelope、headers、request id、账号或 reasoning 内容。

#### `model_arena_samples`

- `sample_id TEXT PRIMARY KEY`
- `run_id TEXT NOT NULL REFERENCES model_arena_runs(run_id) ON DELETE CASCADE`
- `ordinal INTEGER NOT NULL`
- `entry_key TEXT NOT NULL`
- `relative_file_path TEXT NOT NULL`
- `line_number INTEGER`
- `source_text TEXT NOT NULL`
- `source_sha256 TEXT NOT NULL`
- `feature_tags_json TEXT NOT NULL`
- `display_permutation_json TEXT NOT NULL`

#### `model_arena_outputs`

- `output_id TEXT PRIMARY KEY`
- `sample_id TEXT NOT NULL REFERENCES model_arena_samples(sample_id) ON DELETE CASCADE`
- `contestant_id TEXT NOT NULL REFERENCES model_arena_contestants(contestant_id) ON DELETE CASCADE`
- `translated_text TEXT`
- `response_sha256 TEXT`
- `parse_status TEXT NOT NULL`
- `hard_error_count INTEGER NOT NULL DEFAULT 0`
- `validation_json TEXT NOT NULL`

#### `model_arena_votes`

- `vote_id TEXT PRIMARY KEY`
- `sample_id TEXT NOT NULL UNIQUE REFERENCES model_arena_samples(sample_id) ON DELETE CASCADE`
- `verdict TEXT NOT NULL`
- `winner_output_id TEXT NULL REFERENCES model_arena_outputs(output_id) ON DELETE SET NULL`
- `reason_codes_json TEXT NOT NULL`
- `note TEXT`
- `created_at / updated_at TEXT NOT NULL`

`verdict`：`winner | tie | reject_all | unjudgeable`。

#### `model_arena_events`

append-only、每个 run 单调递增的独立事件流：

- `event_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `run_id TEXT NOT NULL REFERENCES model_arena_runs(run_id) ON DELETE CASCADE`
- `sequence INTEGER NOT NULL`
- `timestamp TEXT NOT NULL`
- `level TEXT NOT NULL`
- `event_type TEXT NOT NULL`
- `failure_code TEXT`
- `metrics_json TEXT NOT NULL`

事件表不重复保存 prompt 或回答正文，也不得保存 API URL、绝对路径或秘密。请求证据由 `model_arena_requests` 保存；事件只记录阶段、请求次数、耗时、解析/校验类别和失败码。

### 7.2 删除

- 历史面板允许删除单次 run。
- 删除需要二次确认，并级联删除样本、输出、投票和事件。
- 删除项目时 run 保留，`project_id` 置空并继续使用项目名称快照；历史面板明确显示“原项目已删除”。

## 8. API 契约

路由前缀：`/api/model-arena`。

| Method | Path | 行为 |
|---|---|---|
| `POST` | `/runs` | 创建 draft、冻结配置、抽样；不调用模型 |
| `POST` | `/runs/{run_id}/resample` | draft 状态下重新抽样并生成新 seed |
| `POST` | `/runs/{run_id}/start` | 要求 `confirmed_model_calls=true` 与 idempotency key；启动后台任务 |
| `GET` | `/runs/{run_id}` | 返回按状态裁剪的 DTO；voting 前不返回身份映射 |
| `PUT` | `/runs/{run_id}/samples/{sample_id}/vote` | 幂等新增/更新投票 |
| `POST` | `/runs/{run_id}/complete` | 验证投票覆盖、锁定结果、揭晓身份 |
| `POST` | `/runs/{run_id}/retry-failures` | 再次确认后仅重试失败参赛者 |
| `GET` | `/runs` | 历史分页、项目/语言/模型/状态过滤 |
| `GET` | `/runs/{run_id}/export-preview` | 返回将要导出的精确 JSON 预览 |
| `POST` | `/runs/{run_id}/export` | 明确确认后下载 JSON |
| `DELETE` | `/runs/{run_id}` | 二次确认后删除单次历史 |

`GET /runs/{run_id}` 的匿名性由后端状态机保证，不能通过 query 参数提前 reveal。

## 9. 导出与隐私

文件名：`remis-model-arena-{run_id}.json`，顶层包含 `schema_version`。

### 默认：evidence

包含：

- Remis 版本、sampler 版本、run id 与时间；
- 游戏、语言方向、样本数量与特征统计；
- provider/model 与安全配置快照；
- 实际 system instruction 与 user prompt；
- provider 明确返回的有效生成参数与 token usage；
- 每条样本的原文、解析后的译文和用户备注；
- `completion_text_before_parse` 与 `completion_source`，用于复核代码围栏、解释性前缀、畸形 JSON、数量不匹配和解析结果；
- prompt/config/source/completion/output 哈希；
- 胜负、理由、格式错误码、失败码、请求数与耗时。

不包含：

- entry key、相对或绝对路径；
- API key/token、masked key、账号、API URL；
- provider 原始响应 envelope、HTTP headers、认证信息；
- 未被 provider adapter 采用的独立 thinking/reasoning tokens 或 reasoning 字段。

导出器必须递归扫描 prompt、completion 和用户备注中的秘密与绝对路径。命中秘密时强制替换为 redaction marker；命中路径时替换路径并在 `redactions` 中记录类型。哈希基于本地未删改原文计算，因此导出文本经过路径脱敏时仍可说明它对应哪次本地运行。

### 可选：summary-only

如果用户不希望分享 Mod 内容，可以主动切换为 summary-only，只导出哈希、配置、统计、错误码、失败码、请求数与耗时。它不是默认模式。

首版只下载文件，不直接发帖、不调用 GitHub、不自动上传。用户可以检查 evidence 包后手动附加到 issue #153。

### “原始响应”的准确含义

现有 developer benchmark 中的 `raw_response` 命名容易误解。当前路径实际执行：

```python
completion_text_before_parse = handler._call_api(handler.client, prompt)
parsed_translations = handler._parse_response(
    completion_text_before_parse,
    source_texts,
    target_lang_code,
)
```

这里的值通常是 `response.choices[0].message.content` 或 Gemini 的等价最终文本，不是完整 API 返回对象。它可能包含 JSON 数组、Markdown 代码围栏或模型自行添加的解释，因此对定位解析失败很有价值。

它通常不是 thinking token，但当前 provider 行为并不完全一致：

- 本地 OpenAI-compatible handler 在只有 `reasoning_content`、没有最终 `content` 时会把请求判定为失败，不把 reasoning 当译文；
- NVIDIA 的旧 reasoning fallback 已弃用：最终 `content` 为空时请求失败，`reasoning_content` 不保存、不解析；最终 content 中的 `<think>` 或畸形 JSON 也不由 handler 预先清洗，以便竞技场记录并检验模型实际输出；
- 其他 provider 一般直接返回最终 `message.content`；
- 如果某个模型自行把思考过程写进最终 `content`，Remis 无法普遍可靠地区分。导出预览必须让用户看到实际将导出的文本。

为避免误导，竞技场新代码不再使用 `raw_response` 作为公开字段名，统一使用 `completion_text_before_parse`。

## 10. 前端信息架构

新增：

- `scripts/react-ui/src/pages/ModelArenaPage.jsx`
- `scripts/react-ui/src/pages/ModelArenaPage.module.css`
- `scripts/react-ui/src/components/modelArena/ArenaSetup.jsx`
- `scripts/react-ui/src/components/modelArena/ArenaVoting.jsx`
- `scripts/react-ui/src/components/modelArena/ArenaResults.jsx`
- `scripts/react-ui/src/components/modelArena/ArenaHistory.jsx`
- `scripts/react-ui/src/services/modelArenaService.js`

页面内部四个阶段：`设置 -> 运行 -> 匿名选择 -> 结果`。历史记录作为页面顶部的独立 tab，而不是混入任务中心。

任务中心只负责显示“竞技场正在运行/失败/已完成”和跳回 run 的入口。

## 11. 实施顺序

### Slice A：数据与抽样

1. migration 009、repository 与 schema。
2. 代表性抽样 service、seed 复现和候选池校验。
3. draft/resample/list/detail/delete API。
4. 单元与迁移测试。

验收：不配置任何模型也能创建可复现 draft；同 seed、同候选池、同 sampler 版本得到同一组样本。

### Slice B：执行与硬校验

1. 从 developer benchmark 抽取公共的生产 prompt adapter。
2. 串行执行 2/3 个参赛者，记录后台任务进度。
3. 解析、硬校验、稳定失败码、`partial_failed` 与显式重试。
4. 验证匿名 DTO 不泄露身份。

验收：使用 mocked handlers 完成 2 模型、3 模型、单模型失败、解析失败和格式错误场景；没有真实付费调用。

### Slice C：匿名投票与结果

1. 菜单、路由、设置页和付费确认。
2. 每条样本独立候选置换。
3. 投票状态机、理由、多选、tie/reject。
4. 结果聚合、历史分页和过滤。

验收：完成前 UI 和 API 均不显示模型映射或格式统计；完成后 tally 与真实映射一致。

### Slice D：安全导出与完整 QA

1. evidence/summary-only 两级预览和导出。
2. deterministic secret/path redaction 测试。
3. 单次 run 删除确认。
4. i18n、键盘操作、窄屏布局、空状态、失败恢复。
5. 使用本地 mock provider 做浏览器端到端验证；真实模型调用另需单独批准。

## 12. 测试计划

| 层 | 重点 |
|---|---|
| Unit | sampler 覆盖/seed/去重/文件上限；匿名 permutation；tally；redaction；validator 去重 |
| Repository | migration 009、FK 行为、级联删除、项目删除后 run 保留、分页索引 |
| API | draft 无调用、start 确认/idempotency、状态机、匿名 DTO、vote upsert、complete、export preview |
| Service | 2/3 模型、公平输入、串行顺序、partial failure、显式 retry、硬错误计数 |
| Frontend | 菜单/路由、模型数限制、费用确认、投票完整性、完成前隐藏、结果与历史 |
| E2E | 创建 draft -> mock 试译 -> 匿名投票 -> 揭晓 -> 历史 -> 脱敏导出 |

至少运行：

```powershell
python -m pytest -q tests/test_model_arena_api.py tests/core/test_model_arena_*.py tests/core/test_db_initializer.py
python -m compileall -q scripts tests

Set-Location scripts/react-ui
npm test -- --runInBand
npm run lint
npm run build
```

涉及中日韩文案后，再运行：

```powershell
Set-Location scripts/react-ui
npm test -- src/__tests__/textEncodingIntegrity.test.js
```

## 13. 明确不在首版范围

- Aventine 的 LLM-as-Judge、MQM、ACES、全局 leaderboard 或统计显著性分析；
- 自动根据竞技场结果修改默认模型、prompt 或 provider 配置；
- 自动修复后再比较完整 recipe；
- 自动上传 GitHub issue 或任何远程服务；
- 收集 API key、账号、绝对路径、provider 原始响应 envelope 或独立 thinking/reasoning 内容；
- 一次比较 4 个以上模型；
- 跨用户聚合和在线推荐。

## 14. 首版待确认的产品决策

建议默认采用：

1. 2 或 3 个模型，默认 6 条，允许 3–12 条。
2. 提供“难分高下”和“都不满意”，避免强迫产生虚假赢家。
3. 完成前隐藏模型身份、格式错误和耗时；完成后一次性揭晓。
4. 结果与日志独立持久化；执行进度复用现有任务中心。
5. 默认导出可复核 evidence：实际 prompt、原文、解析后译文、`completion_text_before_parse` 和用户备注；entry key、路径、秘密、账号、API URL、provider envelope 与独立 reasoning 内容始终排除。
6. 首版比较首稿，不自动进入修复流程；首稿硬错误作为模型观测值保留。
