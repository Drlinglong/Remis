# 新词审判庭架构（3.0.7）

新词审判庭是一个受控的术语治理工作流，不是能够自行修改用户文件的自治 Agent。LLM 只负责两个不确定性步骤：候选词提取和译法建议；路径授权、证据校验、查重、状态流转和词典写入均由确定性代码执行。

## 数据流

```text
项目已索引文件
    ↓ 路径必须位于 project.source_path 内
本地化解析器（只提取可翻译文本）
    ↓
Miner（结构化候选提取）
    ↓ 原词必须实际出现在输入块中
跨文件证据聚合（上下文、频次、来源文件）
    ↓
相关词典确定性查重
    ↓
Reviewer（只为无现成译法的候选生成建议）
    ↓
候选 sidecar（项目隔离、原子写入、合并保存）
    ↓
人工裁决：批准 / 沿用重复项 / 项目覆盖 / 新义项 / 忽略
    ↓
项目词典（幂等写入，entry_id = candidate_id）
    ↓
正式翻译：Project > Selected/Game > Main/Global
```

## 失败语义

- API 异常、空响应、连续两次 schema 校验失败、文件读取失败或候选保存失败都会使任务进入 `failed`。
- “成功但候选数为 0”只表示模型调用和持久化都成功，且确实没有通过证据门槛的候选。
- 同一项目同时只能运行一个挖掘任务。
- WebSocket 断线不会把后台任务判为失败，前端会降级为轮询项目状态。

## 候选状态

- `pending`：等待人工裁决。
- `approved`：已写入项目词典。
- `duplicate`：用户确认沿用现有词典，不新增条目。
- `new_meaning`：相同原词在当前项目中产生新义，写入项目词典覆盖上层词典。
- `ignored`：用户确认不处理，后续扫描不会重新创建。

## Golden eval

仓库内的 Stellaris 样本可用于 LLM 回归：

```powershell
python scripts/developer_tools/evaluate_neologism_miner.py --provider gemini
```

默认 fixture 为 `tests/fixtures/neologism_eval_stellaris.json`，至少检查目标新造词召回率和所有候选的源文本证据命中率。该测试会真实调用所选 provider，日常单元测试不会自动运行它。

## 当前边界

- 候选池继续使用项目级 JSON sidecar；3.0.7 通过项目锁、原子替换、合并保存和幂等词典 ID 消除主要并发风险。
- 任务进度仍是当前 Remis 进程内状态。应用重启会中断正在执行的模型调用，但已经保存的候选和人工裁决不会丢失。
- 自动提升到全局词典不在 3.0.7 范围内，避免未经确认污染其他项目。
