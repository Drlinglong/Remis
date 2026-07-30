# Developer History

这里存放的是已经退出开发者主入口的历史技术文档。

它们通常包括：

- 某次重构的总结
- 某个集成方案的阶段性结论
- 某项功能的冻结设计
- 某轮专项治理或代码质量改造记录

这些文档仍然有价值，但价值主要在：

- 回顾为什么当时这么改
- 追踪某项技术债或架构演化的来龙去脉
- 帮助未来排查“这套结构是怎么来的”

不要默认把这里的内容当作当前实现规范。

## 状态字段

本目录中的文档统一视为：

- `status: historical`
- `copilot_scope: excluded`
- `audience: developer`

如果文档开头列出“现行替代”，应优先阅读替代文档。历史文档没有替代文档时，当前行为
仍以代码和测试为准。

## 已归档的中文阶段材料

| 文档 | 原用途 | 现行替代 |
|---|---|---|
| [增量更新 MVP 验收 Checklist](zh/incremental_update_mvp_checklist.md) | 已弃用的人工 MVP 验收单 | [用户指南](../../zh/user-guides/incremental-update.md) / [产品意图](../../zh/product-intent-translation-workflows.md) / [开发契约](../../zh/developer/translation-workflow-contract.md) |
| [增量更新 MVP 状态清单](zh/incremental_update_mvp_status.md) | 阶段性完成度与里程碑快照 | [开发契约](../../zh/developer/translation-workflow-contract.md) |
| [Model Arena 实施计划](zh/model_arena_implementation_plan.md) | 首版设计与实施切片 | [用户指南](../../zh/user-guides/model-arena.md) / [产品意图](../../zh/product-intent-model-arena.md) / [开发契约](../../zh/developer/model-arena-contract.md) |
| [格式化提示词改进](zh/format_prompt_improvements.md) | 2025 年提示词改造快照 | [智能工坊开发契约](../../zh/developer/agent-workshop-contract.md)与当前代码 |
