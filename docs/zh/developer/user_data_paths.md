# Remis 本地数据目录说明

本文档用于区分开发、安装版和历史遗留目录，避免在调试时误删或误判当前数据源。

## 当前目录分工

| 目录 | 状态 | 用途 |
| --- | --- | --- |
| `C:\Users\Drlin\AppData\Roaming\RemisModFactoryDev` | 当前开发环境活跃 | 非打包 Python/Tauri 开发环境的数据目录。包含 `remis.sqlite`、`mods_cache.sqlite`、开发 demo、日志和开发版 `my_translation`。 |
| `C:\Users\Drlin\AppData\Roaming\RemisModFactory` | 安装版/打包版数据 | `sys.frozen == True` 时使用。适合保留为正式安装版用户数据；不要用它判断当前开发版状态。 |
| `C:\Users\Drlin\AppData\Roaming\_remis_archive\Remis_legacy_2025-12-01` | 已归档的历史遗留 | 原 `C:\Users\Drlin\AppData\Roaming\Remis`。旧配置时代使用过的目录；当前 `scripts/app_settings.py` 已不再把它作为标准路径。 |
| `J:\V3_Mod_Localization_Factory\source_mod` | 当前开发工作区活跃 | 开发环境默认源码 mod 工作区。测试 demo 和本地导入项目会使用这里。 |
| `J:\V3_Mod_Localization_Factory\my_translation` | 当前开发工作区活跃 | 开发环境默认生成翻译输出目录。 |

## 代码里的权威规则

路径规则由 `scripts/app_settings.py` 定义：

- 开发环境：`getattr(sys, "frozen", False) == False`
  - `APP_DATA_DIR = %APPDATA%\RemisModFactoryDev`
  - `SOURCE_DIR = <repo>\source_mod`
  - `DEST_DIR = <repo>\my_translation`
- 安装/打包环境：`getattr(sys, "frozen", False) == True`
  - `APP_DATA_DIR = %APPDATA%\RemisModFactory`
  - `SOURCE_DIR = %APPDATA%\RemisModFactory\source_mod`
  - `DEST_DIR = %APPDATA%\RemisModFactory\my_translation`

数据库始终放在 `APP_DATA_DIR`：

- `remis.sqlite`：项目与词典主库
- `mods_cache.sqlite`：mod 缓存库
- `translation_progress.sqlite`：翻译进度库

## 2026-06-16 本机盘点结果

- `RemisModFactoryDev` 最后写入：2026-06-16 07:48 左右；当前开发进程和日志正在使用。
- `RemisModFactory` 最后写入：2026-06-07 12:15 左右；更像安装版/打包版残留状态。
- `Remis` 最后写入：2025-12-01；盘点时为空目录，已移到 `_remis_archive\Remis_legacy_2025-12-01`。
- repo 内 `source_mod` 最后活跃：2026-06-08；仍是开发版源码 mod 工作区。
- repo 内 `my_translation` 最后活跃：2026-06-12；仍是开发版输出工作区。

## 清理建议

建议先归档，不直接删除：

1. 保留 `RemisModFactoryDev`、`source_mod`、`my_translation`，它们是当前开发版会用到的路径。
2. 保留 `RemisModFactory`，除非你确认不再需要安装版历史项目和配置。
3. `Remis` 已归档到 `C:\Users\Drlin\AppData\Roaming\_remis_archive\Remis_legacy_2025-12-01`，观察一段时间后再删除。

如果需要重置安装版数据，使用 `scripts/reset_user_data.bat`；它只针对 `%APPDATA%\RemisModFactory`，不会清理开发版 `RemisModFactoryDev`。
