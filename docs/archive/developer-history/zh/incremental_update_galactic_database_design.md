# 增量更新技术设计文档（星系数据库方案）

## 1. 文档目的

本文档用于冻结本项目“增量更新”功能的核心设计，作为后续重构、测试和实现的统一依据。

本文档不讨论历史方案优劣，不再以 `git diff` 或“追加旧译文文件”为核心思路。当前唯一有效的主线方案是：

- 以语义快照为输入
- 以数据库归档为基线
- 以翻译决策层为核心
- 以新版源文件模板重建为输出

增量更新不是“补丁式追加”，而是“基于新版模板的选择性重建”。

## 2. 问题定义

当前 `initial_translate.py` 适合处理首次全量翻译，但当同一个 Mod 发布新版本后，现有工作流存在三个根本问题：

- 未变化文本会被重复翻译，导致 API 成本和耗时失控。
- 已完成的人工校对与润色成果容易在重翻时丢失。
- 系统缺少一个稳定的“旧版本基线”，导致更新逻辑容易退化成一次新的全量翻译。

增量更新功能的目标是：只处理真正变化的内容，并最大化复用已有翻译资产。

## 3. 目标与非目标

### 3.1 目标

- 仅对新增或修改的条目触发新的翻译决策。
- 对未变化条目优先继承旧译文。
- 对命中官方文本的条目优先复用官方译文。
- 最终输出与新版源文件的结构、顺序、注释保持一致。
- 每次成功执行后，生成可供下一次更新使用的稳定归档基线。

### 3.2 非目标

以下内容不属于第一阶段增量更新核心闭环，不能继续掺入主工作流：

- Steam 创意工坊自动监控
- Watchlist 批量巡检
- 复杂的 UI 引导和可视化流程编排
- 自动识别任意目录中的旧版本来源
- 激进的跨 Mod 语义相似度复用

第一阶段只做“给定项目 + 给定新版源目录 + 已有归档基线”的稳定增量更新。

## 4. 核心设计原则

### 4.1 Parse, Don’t Diff

系统对比的对象不是文本行，而是本地化条目。空行、注释、缩进、文件内顺序调整都不应被当成翻译差异。

### 4.2 Rebuild, Don’t Append

最终产物必须以新版源文件为模板重建，不能继续采用“在旧译文文件末尾追加新条目”的策略。否则会出现脏文件残留、结构失真和删除不生效的问题。

### 4.3 Reuse Before Translate

完整形态下，翻译决策应遵守严格优先级：

1. 继承旧译文
2. 复用官方译文
3. 复用全局缓存译文
4. 调用 AI 翻译

当前重构阶段只启用第一层：

- 继承旧译文
- 剩余条目进入 AI

“官方复用”和“全局复用”接口在当前阶段视为后续能力，不参与本轮实现与验收。

### 4.4 File Path Is Part of Identity

项目内条目标识不能只靠 `key`。在 Mod 内部，主标识至少应为：

- `file_path`
- `entry_key`

如果仅按 `key` 建模，会在重复 key、跨文件同名 key、多模块结构下产生误判。

### 4.5 Workflow Is Thin, Services Are Thick

`workflows/update_translate.py` 只能承担 orchestration 角色，不应继续承载核心业务细节。真正的逻辑必须下沉到稳定的 service 或 core 模块。

## 5. 系统分层

### 5.1 Snapshot Layer

职责：

- 递归扫描源目录中的本地化文件
- 将源文件解析为标准化语义快照
- 保留文件路径、条目 key、源文本等稳定字段

输入：

- `source_path`
- `source_lang_info`
- `game_profile`

输出：

- `Snapshot`

### 5.2 Archive Layer

职责：

- 存储和读取历史版本快照
- 存储和读取旧译文
- 提供官方文本库查询
- 提供跨项目全局复用查询

说明：

- `mods_cache.sqlite` 是 Mod 历史快照与译文归档库
- 后续可扩展独立的 `vanilla_[game_id].sqlite` 作为官方文本库

### 5.3 Diff Layer

职责：

- 比较 `old_snapshot` 与 `new_snapshot`
- 输出干净的差异结果

Diff 结果只允许三类：

- `new`
- `changed`
- `unchanged`

这一层不允许触碰翻译接口、文件写入和 UI 状态。

### 5.4 Resolution Layer

职责：

- 对每个条目做最终翻译来源决策
- 构建完整的 `resolved_translation_map`

决策结果只允许四类：

- `reuse_old`
- `reuse_vanilla`
- `reuse_global`
- `ai_translate`

### 5.5 Build Layer

职责：

- 以新版源文件为模板重建目标语言文件
- 按决策结果填充译文
- 生成完整、可部署的增量输出目录

### 5.6 Workflow Layer

职责：

- 编排各层调用顺序
- 管理进度回调
- 记录历史事件
- 处理运行时异常并终止任务

这一层不得再直接实现条目比对、缓存决策、重建细节。

## 6. 核心数据模型

### 6.1 SourceEntry

```python
@dataclass
class SourceEntry:
    file_path: str
    entry_key: str
    source_text: str
```

说明：

- `file_path` 必须使用项目内稳定相对路径，而不是仅使用文件名。
- `entry_key` 允许保留版本号形式，如 `foo.bar:0`，但系统内部应提供统一标准化规则。

### 6.2 Snapshot

```python
@dataclass
class Snapshot:
    project_id: str
    version_id: str | None
    entries: list[SourceEntry]
```

### 6.3 DiffItem

```python
@dataclass
class DiffItem:
    file_path: str
    entry_key: str
    old_text: str | None
    new_text: str
    status: str  # new | changed | unchanged
```

### 6.4 ResolutionItem

```python
@dataclass
class ResolutionItem:
    file_path: str
    entry_key: str
    source_text: str
    decision: str  # reuse_old | reuse_vanilla | reuse_global | ai_translate
    resolved_text: str
```

## 7. 数据流

增量更新的标准数据流如下：

1. 扫描新版源目录，生成 `new_snapshot`
2. 从归档库中读取该项目最近一次成功归档的 `old_snapshot`
3. 在 Diff Layer 中比较两者，得到 `diff_items`
4. 根据 `diff_items` 构建待处理条目列表
5. 对待处理条目依次执行：
   - 查旧译文是否可继承
   - 查官方译文是否可复用
   - 查全局缓存是否可复用
   - 剩余条目送 AI
6. 得到完整的 `resolved_translation_map`
7. 以新版源文件为模板，重建目标语言输出
8. 将本次新版快照与生成结果归档，作为下一次更新基线

## 8. 决策规则

### 8.1 未变化条目

如果条目在 `old_snapshot` 中存在，且 `source_text` 与 `new_snapshot` 完全一致：

- 状态判定为 `unchanged`
- 直接继承旧译文
- 不允许再走官方库或 AI

### 8.2 修改条目

如果条目在新旧快照中都存在，但 `source_text` 不一致：

- 状态判定为 `changed`
- 优先检查是否命中官方库
- 其次检查是否命中全局缓存库
- 否则进入 AI

### 8.3 新增条目

如果条目只存在于 `new_snapshot`：

- 状态判定为 `new`
- 优先检查官方库
- 其次检查全局缓存库
- 否则进入 AI

### 8.4 删除条目

删除条目不进入翻译决策。它的处理方式是：

- 不再出现在最终构建输出中
- 在归档中由新快照自然淘汰旧条目

这也是系统必须“模板重建”而不是“旧文件追加”的原因。

## 9. 数据库存储策略

### 9.1 mods_cache.sqlite 的职责

当前 `mods_cache.sqlite` 继续作为项目内的 Mod 快照与译文归档库。

建议稳定为以下职责：

- 维护 `mods`
- 维护版本快照 `source_versions`
- 维护源条目 `source_entries`
- 维护目标语言译文 `translated_entries`

### 9.2 条目标识约束

在 `source_entries` 中，唯一约束应至少体现：

- `version_id`
- `file_path`
- `entry_key`

仅以 `entry_key` 作为查找键是不可靠的。

### 9.3 官方文本库

建议后续引入只读数据库：

- `vanilla_[game_id].sqlite`

最小数据模型可为：

- `game_id`
- `file_path` 或官方来源标识
- `entry_key`
- `source_lang`
- `source_text`
- `target_lang`
- `translated_text`

第一阶段如果官方库尚未落地，可在 Resolution Layer 中保留接口，但允许以空实现返回。

## 10. 当前实现的主要问题

以下问题是当前 `scripts/workflows/update_translate.py` 失效和持续失控的主要原因。

### 10.1 单文件承担过多职责

当前工作流同时负责：

- 扫描源文件
- 解析条目
- 查询归档
- 计算差异
- 触发翻译
- 重建输出
- 写入归档
- 写项目历史

这使任何一个修复都会污染主流程，代码难以维护和验证。

### 10.2 归档模型与比对模型不一致

数据库层已经开始引入 `file_path` 维度，但增量工作流仍存在按全局 `key` 压平查询的逻辑。结果是：

- 同名 key 在不同文件中会互相污染
- 不同文件的旧译文可能被错误继承
- 差异分类会出现误判

### 10.3 多语言状态隔离不足

当前实现中，多目标语言执行时存在缓存和结果容器跨语言污染的风险。增量更新中，语言维度必须是一级隔离维度，任何跨语言缓存都必须显式带上 `target_lang_code`。

### 10.4 输出目录不是严格意义上的“完整重建结果”

当前逻辑更像“把本次生成的文件写到目录里”，而不是“确保输出严格镜像新版源结构”。结果是：

- 已删除文件可能残留在旧输出中
- 重命名文件后可能同时保留新旧两个版本
- 构建结果与新版源文件结构逐渐偏离

### 10.5 Workflow 依赖过深，无法局部验证

现在很难只测试“语义 diff 是否正确”或“翻译决策是否正确”，因为这些逻辑被直接埋在工作流中，导致测试需要构造过多环境，开发效率极低。

## 11. 激进重构策略

当前状态下，继续在 `update_translate.py` 上打补丁的收益很低。建议采用受控的激进重构：

### 11.1 重构原则

- 不在旧流程中继续叠加分支
- 先冻结接口，再迁移实现
- 先抽核心纯逻辑，再接回现有 IO
- 允许短期并行保留旧实现，但新实现必须有明确入口

### 11.2 推荐拆分模块

建议新增或重组以下模块：

- `scripts/core/services/incremental_snapshot_service.py`
- `scripts/core/services/incremental_diff_service.py`
- `scripts/core/services/incremental_resolution_service.py`
- `scripts/core/services/incremental_build_service.py`
- `scripts/core/services/incremental_archive_service.py`

`scripts/workflows/update_translate.py` 最终只保留编排逻辑。

### 11.3 实施顺序

第一阶段：

- 从 `update_translate.py` 中抽离快照构建逻辑
- 定义标准化 `SourceEntry` 和 `Snapshot`
- 写纯逻辑测试，确保快照输出稳定

第二阶段：

- 实现独立的 Diff Service
- 禁止再按全局 `key` 直接比对
- 所有比较必须基于 `file_path + entry_key`

第三阶段：

- 实现 Resolution Service
- 统一翻译来源优先级
- 将语言隔离和缓存隔离固定下来

第四阶段：

- 实现 Build Service
- 以新版模板完整重建输出
- 增加脏文件清理或输出目录镜像策略

第五阶段：

- 工作流接线
- 历史记录与 UI 进度回调接回
- 最后才处理体验层和自动化入口

### 11.4 为什么这是“激进但合理”的

因为当前的阻碍已经发生在第一步，即 `update_translate.py` 自身无法稳定工作。此时继续局部修补，只会把更多历史设计债固化进主工作流。与其在错误边界上继续补洞，不如先把边界重新立起来。

这不是推倒重来，而是把当前已经混在一起的职责重新归位。

## 12. 第一阶段最小可交付版本

第一阶段的增量更新 MVP 必须满足以下条件：

- 输入：
  - `project_id`
  - `target_lang_infos`
  - `source_lang_info`
  - `game_profile`
  - `custom_source_path`
- 前提：
  - 项目已有至少一次成功归档
- 能力：
  - 读取新版源目录
  - 读取旧快照和旧译文
  - 计算语义差异
  - 复用旧译文
  - 只对剩余条目调用 AI
  - 按新版模板重建完整输出
  - 更新归档

如果上述闭环未打通，不应继续开发更高层的自动化功能。

## 13. 必测场景

以下场景必须被测试覆盖，否则增量更新不能视为稳定：

- 同文件新增条目
- 同文件修改条目
- 不同文件存在同名 key
- 多目标语言并行执行
- 新版删除旧文件
- 未变化条目继承旧译文
- 命中官方文本库时跳过 AI
- 更新归档后，下一次更新以本次结果为基线

## 14. 当前结论

本项目的增量更新功能，已经不适合继续围绕单个工作流脚本迭代。后续开发必须严格转向：

- 以数据库快照为基础
- 以语义 diff 为中心
- 以翻译决策层为核心
- 以模板重建为输出
- 以 service 分层替代 workflow 细节堆积

`update_translate.py` 的下一阶段目标，不是继续长大，而是变薄。
