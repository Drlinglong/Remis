# Issue #198 档案上下文翻译 A/B 评测包

这是 developer-only 的离线评测工具，不是生产翻译 workflow。它读取已配置 benchmark corpus root
中的原文和三轴 gold；Wiki 事实作为 judge/人工证据，
真实 B 臂上下文只能通过 Remis Agent API 读取已发布的 archive release。默认 dry-run
不调用真实 provider，不做付费翻译或 judge。

## 评测单位

- `event_narrative`：一整条事件链是一个 case。case 同时携带该链全部原文、三轴映射、Wiki 事实包和 A/B 整条译文；字符串只用于定位错误，不能投票。
- `reference_batch`、`background_narrative`、`static_reference`：一个语义关联的完整批次是一个 case。只有受上下文/输出上限约束时才确定性切块，并记录 `chunk_index`、`chunk_count` 和 `chunk_reason`；两臂边界和顺序相同。
- Judge prompt 的通用说明只出现一次，然后评整条链或整批 reference，避免每条 entry 重复放大 prompt。

当前 fixture 选择：

- Horizon Signal：`horizon_signal` 完整事件链，以及 `tech_akx_worm_` 静态技术 reference family。
- Toxic God：`first_quest_sinople` 完整事件链。

## A/B 合同

两臂共用 provider/model/revision、temperature、top_p、seed、request fingerprint、prompt version、词典、重试策略、reference reuse
和 case 边界。A 没有档案上下文；fresh B 只能使用真实持久化 Remis archive artifact。
Wiki 事实只进入 judge/人工证据，不进入 B 翻译臂。增量场景中未变化 case 直接跳过；
stale B 只能使用旧的持久化 archive artifact。

每个 case 先做确定性 hard check：条目 ID/数量和 Paradox `$...$`、`[...]`、`£...£`、
`§...§` 占位符必须保持。hard failure 不交给 judge 猜。软 judge 以随机匿名顺序
呈现两次，并以相反顺序重复；底层赢家不一致则 `tie` + `needs_adjudication`。

## 可复现运行

从 Remis 仓库根目录运行：

```powershell
python scripts/developer_tools/run_archive_ab_benchmark.py --dry-run
```

默认输出在 `.tmp/archive-ab/dry-run-<UTC时间>-<内容哈希>.json`；已有结果不会被覆盖。增量 stale 示例：

```powershell
python scripts/developer_tools/run_archive_ab_benchmark.py --dry-run --mode incremental --archive-mode stale --changed-source-id 'akx.9000.name:0'
```

`--dry-run` 使用透明 fake provider 和 tie judge；它只验证协议、边界、manifest 和
hard check，不是翻译质量结论。默认 fresh 场景若没有真实持久化 Remis archive artifact，
会在 manifest 中明确将每个 case 标为 `missing_persisted_archive_artifact`，不会把 fixture
中的说明文字伪装成 archive；使用 `--archive-mode none` 可运行无 archive 的协议 smoke。
接入真实 release 时显式传入本地 Agent API 和 release ID；stale 模式还要传旧 release：

```powershell
python scripts/developer_tools/run_archive_ab_benchmark.py --archive-api-base-url http://127.0.0.1:1453 `
  --archive-release-id <published-release-id> --archive-previous-release-id <previous-release-id>
```

loader 会直接读取 `/api/agent/context/releases/{id}/effective`，并把 endpoint、内容 hash、
release ID 和 source snapshot hash 写入 manifest；不会接受一个自行发明的 JSON artifact 路径。
真实 Luna judge 只能在玲珑审查后另行接入，而且 judge adapter 必须返回 `(payload, Usage)`。

## Manifest 与指标

`remis-archive-ab-run-v1` 记录原文/金标 SHA-256、gold schema/version、Wiki 事实包 schema/package version、Wiki URL/标题/
访问日期/版本信息、recipe/prompt hash、case/batch IDs、顺序、chunk 元数据和
input/output/cached/reasoning/cost 字段，并分开记录 A/B translation、judge 和 archive generation 用量。
provider 只收到匿名 request ID，不收到 A/B 臂身份；总实验成本包含两臂翻译、judge 和档案生成，
feature incremental cost 则是 B 翻译减 A 翻译再加档案生成。
`remis-archive-ab-score-v1` 按 canonical chain/reference cluster（不是 chunk）汇总 chain-level /
reference-batch-level 汇总 win/tie/loss，并以 case 为独立单位做 bootstrap 95% CI，
同时报告重大上下文错误、hard 格式错误、增量 cost、档案生成 cost，以及每避免一个
重大错误的增量成本。

## Wiki 证据包

`tests/fixtures/remis_archive_ab_v1/wiki_evidence.json` 是浏览器核验后的结构化事实包，只保存事实、事件链结构、分支约束、实体词表和短摘录，不复制整页；主来源是你指定的 Paradox Wiki：

- Horizon Signal：<https://stellaris.paradoxwikis.com/Horizon_Signal>
- Quest for the Toxic God events：<https://stellaris.paradoxwikis.com/Quest_for_the_Toxic_God_events>

访问日期为 `2026-09-02`。HTTP 抓取端仍返回 401，但浏览器 DOM 可以读取两页正文，
所以包内分别记录 `verified_in_browser` 和
`verified_in_browser_with_user_accuracy_confirmation`，并保留 HTTP 401 作为取得路径的
审计信息。Horizon 页面标注当前 PC 版 `4.4`；Toxic God 页面标注部分旧段落最后核验于
`3.13`，同时单独记录玲珑关于近期版本未改动且 Wiki 准确的领域确认。不能用这个确认
覆盖页面自己的版本标记，也不能把页面事实升级成游戏脚本事实。

Wiki 事实包由 judge 和人工抽检使用，不注入任一翻译臂；因此它不会给 B 臂额外
上下文优势。翻译臂的 B 输入只来自真实持久化 Remis archive artifact；缺失 artifact
时 fresh B 明确跳过。这样 Wiki 事实包仍参与评判证据，同时 immutable local
source/gold 和真实档案 artifact 保持硬边界。

## Developer-only 人工抽检

`archive_ab_review_queue.py` 和 `archive_ab_review_adapter.py` 提供与 Model Arena 相同的“先盲评、后 reveal”数据边界：
初始 payload 只有原文、必要故事证据和匿名左右候选；提交前没有 arm 名称、档案标记
或 LLM 结论。提交后才能 reveal 实际顺序、Luna 结果和理由。人工可选左右/平局/无法
判断、错误标签、置信度和备注，并以 JSONL append-only 保存复核历史。reveal 会追加
一个 supersedes 事件，原始人工判断不被覆盖。

`run_archive_ab_benchmark.py --dry-run` 现在会在结果 JSON 中同时写入 `review_cases`：
它包含 GUI 所需的完整原文、故事事实和匿名候选，以及仅供后端 reveal 的私有结果区。
浏览器永远不能任意读取文件；`/api/archive-ab-review/cases`、`/api/archive-ab-review/reviews`
和 `/api/archive-ab-review/summary` 只通过后端适配器访问固定的 `.tmp/archive-ab` 目录，
并在提交后才返回 reveal。

入口默认关闭，必须设置明确的开发者开关：

```powershell
$env:REMIS_BUILD_CHANNEL = 'agent-preview'
$env:VITE_REMIS_BUILD_CHANNEL = 'agent-preview'
$env:REMIS_ENABLE_ARCHIVE_AB_REVIEW = '1'
```

然后启动开发后端和 Agent Preview 前端，在 Remis 中打开：
`#/developer/archive-ab-review`。该路由不进入普通导航，只在 Agent Preview 前端
feature policy 开启时生成；后端还要求 `REMIS_ENABLE_ARCHIVE_AB_REVIEW=1`，否则
cases/reviews API 返回 404。页面会先读取 backend capability/status，再加载 manifest、
当前 result/review batch 和 append-only review queue。页面提供 manifest、dataset、
case kind、review 状态筛选，整链/完整 reference batch 原文、故事事实、匿名 left/right
译文，left/right/tie/uncertain/skip、错误标签、置信度、备注、上一条/下一条、进度和
提交后 reveal。提交按钮只完成当前 case 的判断并揭晓；用户手动点击“下一条”，页面会把焦点移动到下一条 case 标题，
揭晓时则把焦点移动到 reveal 区域。reveal 同时明确显示左右当前对应的 `baseline(no archive)` 或
`archive(fresh|stale)`，避免匿名顺序被误读。

前端复用了 Model Arena 的 `ArenaVoting` 视觉契约（匿名候选卡、锁定提示、决策按钮、
进度条和 reveal 语义），抽检入口本身保持独立，避免将 developer 文件适配逻辑混入
生产竞技场。抽样/汇总仍由 `archive_ab_review_queue.py` 保持 case ID 去重覆盖率。

## 验证

```powershell
python -m pytest -q tests/developer_tools/test_archive_ab_benchmark.py
python -m pytest -q tests/test_archive_ab_review_api.py tests/core/test_feature_policy.py
python -m compileall -q scripts tests
git diff --check
```

前端 focused test、lint 和 build：

```powershell
Set-Location scripts/react-ui
npm test -- --run src/components/archiveABReview/ArchiveABReviewPanel.test.jsx src/config/pageRegistry.test.js
npm run lint
npm run build
```

当前没有接入真实 provider、没有付费调用、没有导出生产译文，也没有改变任何 gold。
