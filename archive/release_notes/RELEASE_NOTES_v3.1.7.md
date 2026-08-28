# Project Remis v3.1.7

Released on 2026-08-28.

Version 3.1.7 improves Victoria 3 translation consistency, adds exact official
translation reuse, and hardens frontend collection payload handling.

## English

### Highlights

- Initial and incremental translation can scan a selected official game
  localization directory and reuse only exact key, source-text, and language
  matches. A preview lets users exclude individual matches before translation.
- Victoria 3 country-adjective definitions and references now receive selective
  semantic guidance for supported target languages while preserving Paradox
  variables and formatting.
- Archives, project history, the project sidebar, and Model Arena now normalize
  supported collection payloads and ignore malformed records safely.

### Safety and reliability

- Official-reference hits are removed from model batches, tracked separately,
  and protected from automatic Workshop rewrites.
- Existing bundled-demo directories are now repaired by filling only missing
  package files, so an upgrade cannot leave a partial demo without overwriting
  user edits.
- Proofreading saves tolerate source keys that are newer than an existing
  archive cache: known entries are updated, missing entries are warned and no
  longer block the file write.
- Reference indexes are cached locally, report stale-state failures, and never
  ingest the current mod or Workshop output as official source material.
- Translation jobs containing human-review items can no longer be approved for
  export until those items are resolved.
- Regression tests cover reference preview and exclusions, initial/incremental
  reassembly, semantic-hint alignment, payload normalization, and review gates.

## 中文

### 主要更新

- 初次翻译与增量翻译现在可扫描用户选择的官方游戏本地化目录，只复用 key、
  源文本与目标语言完全匹配的官方译文；翻译前可预览并逐条取消复用。
- Victoria 3 国家形容词定义与引用会按目标语言获得选择性的语义提示，同时保留
  Paradox 变量与格式。
- 归档、项目历史、项目侧栏和 Model Arena 会统一规范受支持的集合 payload，
  并安全忽略畸形记录。

### 安全性与可靠性

- 官方译文命中项会从模型批次移除、单独记录，并受到保护，避免被 Workshop
  自动改写。
- 升级时若内置 Demo 目录只剩 sidecar 或缺少文件，现在会只补齐包内缺失文件，
  不覆盖用户已有修改，避免出现半空的 Demo。
- 校对保存兼容比现有归档缓存更新的源 key：已有条目照常更新，缺失条目记录警告，
  不再因此阻断文件写回。
- 官方译文索引使用本地缓存；重建失败会明确标记 stale，且不会把当前 Mod 或
  Workshop 输出当作官方来源。
- 含人工复核项的翻译任务在问题解决前不再开放导出批准。
- 新增回归测试，覆盖复用预览与排除、初次/增量结果重组、语义提示位置对齐、
  payload 规范化及人工复核门槛。
