# Project Remis Vic3 增量更新冻结用例

这个用例用于发布前手动冒烟，也用于后续自动化回归。它基于仓库内置的 Victoria 3 范例模组，不依赖本机私有素材。

## 固定目录

- 基线目录：`source_mod/Test_Project_Remis_Vic3`
- 更新目录：`source_mod/Test_Project_Remis_Vic3_Incremental_Frozen`
- 安装版基线目录：`%APPDATA%/RemisModFactory/demos/Test_Project_Remis_Vic3`
- 安装版更新目录：`%APPDATA%/RemisModFactory/demos/Test_Project_Remis_Vic3_Incremental_Frozen`
- 源语言：`zh-CN`
- 游戏：`victoria3`

## 固定差异

相对基线目录，更新目录固定包含：

- 修改 2 条：`remis_event.2.d`、`remis_event.4.a`
- 新增 2 条：`remis_event.7.b`、`remis_journal.remis_restoration`
- 删除 1 条：`remis_event.3.b`
- 新增 1 个文件：`localization/simp_chinese/remis_newspaper_l_simp_chinese.yml`

新增文件包含 4 条新文本：

- `remis_news.1.t`
- `remis_news.1.d`
- `remis_news.1.f`
- `remis_news.1.a`

## 预期摘要

如果基线归档来自 `source_mod/Test_Project_Remis_Vic3`，对更新目录运行 dry-run 时，核心预期是：

```text
changed = 2
new = 6
deleted_from_baseline = 1
new_files = 1
```

当前增量更新 UI 的摘要主要展示当前源码中需要处理的条目，因此删除项通常不会作为待翻译条目出现。删除项的存在用于人工确认归档差异和输出重建不会错误保留旧 key。

## 手动冒烟步骤

1. 用 `source_mod/Test_Project_Remis_Vic3` 建立或导入基线项目。
2. 确认基线翻译已归档。
3. 打开增量更新页，选择该项目。
4. 自定义源码路径选择 `source_mod/Test_Project_Remis_Vic3_Incremental_Frozen`。
5. 先运行 dry-run，确认新增和修改条目符合预期。
6. 再运行正式增量更新，确认输出目录生成成功。
7. 检查输出中不应再包含 `remis_event.3.b`，并应包含新增报纸文件。

## 反复执行与重置

开发版可以直接重复使用仓库内的两个固定目录。安装版会把这两个目录释放到 `%APPDATA%/RemisModFactory/demos`，所以不需要用户自己复制测试素材。

如果需要从“增量更新前”的干净状态重跑：

1. 打开设置页。
2. 使用“重置项目数据库”。
3. 重启应用或返回项目页刷新。
4. 重新打开内置 Vic3 范例项目，并按上面的步骤选择冻结更新目录。

这个重置只清理 Remis 内部项目记录，不删除磁盘上的示范素材。这样安装版也可以把这套素材作为教程来反复演示。

注意：旧的“商船”冒烟素材不应进入默认数据库。默认安装库只应保留官方 Remis 示例项目和官方教程素材。
