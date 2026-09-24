# 多检出开发运行数据隔离

每个开发检出需要使用独立的 Remis 用户数据目录，避免不同分支读写同一份 SQLite 数据库、配置和日志。

## 启动

从检出根目录运行一键启动器：

```powershell
.\scripts\developer_tools\windows\run-dev.bat
```

后端也可以单独启动：

```powershell
.\scripts\react-ui\run-backend.bat
```

这两个启动器会识别 Git worktree，并在启动后端或端口预检前，将 `REMIS_APP_DATA_DIR` 默认设为该 worktree 根目录下的 `.runtime`。普通克隆不设置新默认值，继续使用现有 build profile 路径。例如，`J:\V3_Mod_Localization_Factory-worktrees\multi-game-adapters` 使用：

```text
J:\V3_Mod_Localization_Factory-worktrees\multi-game-adapters\.runtime
```

如需指定其他隔离目录，先在当前 PowerShell 会话中设置绝对路径，再启动：

```powershell
$env:REMIS_APP_DATA_DIR = 'J:\Remis-dev-data\multi-game-adapters'
.\scripts\developer_tools\windows\run-dev.bat
```

相对路径会在启动器和 Python 配置入口处被拒绝。生产构建没有设置该变量时仍使用现有 build profile 路径。

## 路径归属

`APP_DATA_DIR` 下的 `config.json`、`remis.sqlite`、`mods_cache.sqlite`、`vanilla_reference.sqlite`、`translation_progress.sqlite`、Agent 注册数据、工作坊资产与日志都归属于该检出的运行目录。新检出启动时会在其中初始化自己的开发数据库；不会从其他检出或用户 AppData 复制配置。

开发模式下的模组输入和翻译目标继续使用各检出自己的 `source_mod` 与 `my_translation`；当前检出的导出目录继续使用仓库根目录的 `output`。这些路径随工作树分开。SQLite 和用户配置等运行状态位于 `.runtime`，不进入 Git。

## Python 环境

启动器优先使用 `REMIS_PYTHON_EXE`，其次尝试 `REMIS_CONDA_BASE`、已激活的 Conda 环境和常见 Conda 安装位置中的 `local_factory`。本机若使用默认安装位置，可以检查启动器会找到的解释器：

```powershell
Test-Path 'K:\MiniConda\envs\local_factory\python.exe'
```

也可以设置 `REMIS_PYTHON_EXE` 指向已配置好项目依赖的 Python。启动器的 `--check` 仅检查脚本路径、绝对运行目录和目标端口，不启动服务。
