# Demo 冒烟夹具一键重置

开发版提供一个定向重置工具，用于反复执行 UI 和主流程冒烟测试。它只处理三个官方 demo 项目以及仓库自带的测试夹具，不等同于“重置项目数据库”，也不会触碰普通用户项目。

## 使用方式

先关闭正在运行的 Remis 开发版。工具会拒绝在 `127.0.0.1:1453` 仍有后端监听时修改数据库。

在仓库根目录预览：

```powershell
scripts\developer_tools\windows\reset-demo-smoke-state.bat
```

确认预览后，一键执行全部重置：

```powershell
scripts\developer_tools\windows\reset-demo-smoke-state.bat --yes
```

只重置一个或多个流程：

```powershell
scripts\developer_tools\windows\reset-demo-smoke-state.bat --scope incremental --yes
scripts\developer_tools\windows\reset-demo-smoke-state.bat --scope workshop --scope neologism --yes
```

每次执行前，工具会把 `remis.sqlite`、`mods_cache.sqlite` 和被替换的 demo 文件移动或复制到：

```text
%APPDATA%\RemisModFactoryDev\demo_smoke_backups\<时间戳>\
```

终态 demo 任务只会被归档，不会删除任务日志。

## 四个隔离范围

### 初始翻译

使用官方 EU5 demo，避免与 Vic3 增量夹具及 Stellaris 新词夹具互相覆盖。

- 清空 EU5 demo 的翻译输出目录；
- 清空该 demo 在归档数据库中的翻译结果；
- 清除其翻译文件索引；
- 保留源文件和项目身份。

### 增量翻译

使用官方 Vic3 demo。

- 从仓库夹具恢复 `Test_Project_Remis_Vic3`；
- 恢复 `Test_Project_Remis_Vic3_Incremental_Frozen`；
- 从 `assets/mods_cache_skeleton.sqlite` 恢复增量更新前的归档基线；
- 重建基线英文翻译文件；
- 移除所有被该项目历史和任务精确引用的增量输出；
- 清除增量输出的项目注册和文件索引。

预期冻结差异仍为：修改 2 条、新增 6 条、删除 1 条、新增 1 个文件。

### 格式修复台

使用 Stellaris demo 项目，但把故意损坏的翻译放在独立目录：

```text
%APPDATA%\RemisModFactoryDev\demo_smoke\agent_workshop_broken
```

每次重置都会从仓库内只读模板重新复制，其中固定包含非法 key、变量缺失、格式标记不闭合和残留中文标点等问题。该目录会被注册并索引为 Stellaris demo 的翻译输入。

### 新词挖掘与审判庭

使用官方 Stellaris demo。

- 删除各 worktree 中该项目的候选词缓存；
- 删除 `raw_metadata.owner_project_id` 明确属于该 demo 的项目专属词典；
- 不删除主词典、标准词典或用户为项目绑定的共享词典。

## 安全边界

- 只接受固定的官方 demo project ID。
- 文件移动目标必须位于 Remis 开发 AppData、当前 Git worktree 或主 fixture worktree 内。
- 生成输出先移入备份目录，不执行不可恢复的递归删除。
- 数据库修改在 SQLite 事务内完成，执行前保留完整数据库副本。
- 工具不会发起模型调用、翻译、修复、导出或部署。
