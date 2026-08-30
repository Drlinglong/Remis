# Context Archive Demo 金标评分

Remis 维护两套冻结的 Context Archive demo：

- `horizon-signal`：视界信号，95 local units；
- `toxic-god`：毒圣骑士，201 local units。

评分器只读取 Remis 数据库和私有 `remis-aventine-benchmark-corpus`，不会调用模型、修改项目或发布档案。

## 一条命令评分

从 Remis 仓库根目录执行：

```powershell
python scripts/developer_tools/context_archive_demo_benchmark.py horizon-signal
python scripts/developer_tools/context_archive_demo_benchmark.py toxic-god
```

脚本按冻结的 `source_snapshot_hash` 自动寻找最新 Context Release 或 Context Analysis Run。对尚未发布、但已经保存最终 aggregation assignment 的失败 run，也可以直接评分。

默认输出：

```text
outputs/context-archive-benchmarks/<demo>/
  <demo>-<target-kind>-<id-prefix>.json
  <demo>-<target-kind>-<id-prefix>.md
```

JSON 适合自动比较；Markdown 包含基线差值和逐 unit 审核信息。

## 指定目标或抢救数据库

```powershell
python scripts/developer_tools/context_archive_demo_benchmark.py toxic-god `
  --analysis-run-id b26e6ddb-07d5-4f7e-9182-e15752ed3810 `
  --database recovery/issue-198/remis-synthesis-rescue-20260804-131640.sqlite
```

也可以用 `--release-id` 指定不可变 Context Release。自动选择会忽略没有 `analysis_run_id` 的旧式 legacy release，避免使用不完整的历史 manifest；这种 release 仍可显式指定进行诊断。

## 私有 corpus 定位

默认会在 Remis 仓库相邻目录寻找 `remis-aventine-benchmark-corpus`。其他布局可使用：

```powershell
$env:REMIS_AVENTINE_BENCHMARK_CORPUS = 'J:\remis-aventine-benchmark-corpus'
```

或传递 `--corpus-root`。

## 身份门禁

每个 demo 同时冻结：

- fixture SHA-256；
- gold SHA-256；
- Remis `source_snapshot_hash`；
- source item 数；
- local unit 数。

任何一项不一致都会停止评分。因此 `toxic-god` 金标不会与条目数不同的 `projects/stellaris/toxoids_test` 混用。

## 指标

评分沿用视界信号的原始口径：

- 投递 Precision / Recall / F1；
- 宽松事件链正确率；
- 严格聚类 Pairwise Precision / Recall / F1；
- 关系类型完全正确率；
- TP、FP、FN、TN 和逐 unit 判定。

宽松事件链允许多个合理子链映射到同一个 Gold 事件族；严格 Pairwise 指标会同时惩罚过度拆分和过度合并。两者回答的问题不同，不应合成一个缺乏解释力的“总分”。

## 更新基线

`context_archive_demo_benchmark.py` 中的 baseline 是人工确认后的冻结结果。更新它必须同时满足：

1. 新 run 使用完全相同的 fixture 和 gold；
2. JSON/Markdown 报告已人工检查；
3. 若 gold 有修改，在私有 corpus 中创建新日期版本并更新 SHA-256；
4. 不得为了提高单一指标，把 `theme_related` 或父故事元数据改成默认翻译注入。

基线比较使用百分点差值；脚本不会自动把一次新结果提升为基线。
