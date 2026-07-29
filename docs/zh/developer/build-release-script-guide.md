# 发布构建脚本指南 (`build_release.bat`)

## 概述

`build_release.bat` 是一个用于自动化构建 Project Remis 便携版发布包的脚本。它负责清理旧的构建文件、创建新的目录结构、嵌入 Python 环境、复制项目源代码、下载并打包所有依赖项，并最终生成一个可分发的 ZIP 压缩包。

## 功能特性

*   **自动化构建**：一键完成便携版发布包的构建过程。
*   **环境隔离**：将 Python 运行时环境和所有依赖项打包到发布包中，无需用户手动安装 Python 或配置环境。
*   **依赖管理**：自动下载 `requirements.txt` 中定义的所有 Python 依赖项，并将其放置在 `packages` 目录中。
*   **结构化输出**：生成符合 Project Remis 便携版目录结构的发布包。
*   **可选压缩**：如果系统安装了 7-Zip，脚本会自动将生成的发布目录压缩为 ZIP 文件。

## Release Note 编写规范

每份发版说明都应先服务普通用户，再服务需要实现细节的技术读者。

1. 中文和英文部分都必须以简短的 `重点` / `Highlights` 开头。
2. 使用二到五条通俗说明，直接回答：新增了什么、改善了什么、移除了什么或发生了哪些变化，以及用户是否需要采取操作。
3. 开头的重点部分不要堆放文件名、函数名、Issue 编号、内部架构、测试命令等实现细节。
4. 原有实现细节应保留在下方的 `技术细节` / `Technical Details` 中，并按需继续提供兼容性和验证信息。
5. 中英文摘要必须保持语义一致，但可以根据各自语言习惯调整措辞。

推荐结构：

```markdown
## English

## Highlights

- **New or improved:** ...
- **Removed or changed:** ...

## Technical Details

...

## 中文

## 重点

- **新增或改进：**……
- **移除或变更：**……

## 技术细节

……
```

## 使用方法

## 3.1.0 桌面安装包的数据库规则

当前 Tauri 桌面安装包由 `scripts/build_pipeline.py` 构建。数据库初始化分成三层：

1. 用户日常运行 Remis 的数据库位于 AppData，只保存本机项目、任务、Arena
   历史和用户术语表。发布构建禁止读取它。
2. `assets/skeleton.sqlite` 是仓库内、可审查的发布输入。构建脚本从中只导出
   默认术语表数据，以及三个固定 Demo 项目、文件索引和项目术语表绑定。
3. 新安装首次启动时，`scripts/core/db_initializer.py` 创建当前数据库结构，
   再导入构建生成的 `seed_data_main.sql` 和 `seed_data_projects.sql`。

三个允许随安装包发布的 Demo 是：

- `Project Remis - Demo Mod -EU5`
- `Project Remis - Demo Mod - Stellaris`
- `蕾姆丝计划 - 演示Mod - 维多利亚3`

构建会同时检查 `assets/mods_cache_skeleton.sqlite`，并要求其中恰好也是这三个
Demo。任何额外或缺失项目都会使构建失败。活动日志、项目历史、监控快照、后台
任务和 Model Arena 历史不会进入初始化 SQL。

需要新增 Demo 时，先修改 `scripts/utils/export_seed_data.py` 中的
`DEMO_PROJECTS` 白名单，再显式运行：

```powershell
python scripts\db\generate_skeleton.py --from-development
```

该命令会覆盖仓库内的发布资产，因此必须检查数据库差异和测试结果后再提交。
普通发布构建不会自动运行它。

### 前提条件

1.  **Conda 环境**：脚本假设在一个已激活的 Conda/Python 环境中运行。请确保您的系统已安装 Conda，并且 `CONDA_ROOT` 和 `ENV_NAME` 变量在脚本中配置正确。
2.  **7-Zip (可选)**：如果希望脚本自动生成 ZIP 压缩包，请确保您的系统已安装 7-Zip，并且其可执行文件 (`7z.exe`) 位于系统 PATH 中或脚本可以找到的默认路径。
3.  **Python 嵌入包**：确保 `archive/build_release_scripts/` 目录下存在 `python-3.10.11-embed-amd64.zip` 文件。

### 运行脚本

1.  **激活 Conda 环境**：
    打开命令行工具（如 Anaconda Prompt），并激活您用于构建的 Conda 环境：
    ```bash
    conda activate your_env_name
    ```
    （请将 `your_env_name` 替换为脚本中 `ENV_NAME` 定义的环境名称）

2.  **执行构建脚本**：
    导航到 `archive/build_release_scripts/` 目录，然后运行 `build_release.bat`：
    ```bash
    cd J:\V3_Mod_Localization_Factory\archive\build_release_scripts\
    build_release.bat
    ```

3.  **等待完成**：
    脚本将自动执行所有构建步骤。过程中会输出详细的日志信息。请耐心等待，直到脚本显示 `[SUCCESS] Build process completed!`。

## 脚本配置

您可以在 `build_release.bat` 脚本的开头部分修改以下变量：

*   `CONDA_ROOT`：您的 Conda 安装根目录。
*   `ENV_NAME`：用于构建的 Conda 环境名称。
*   `PROJECT_NAME`：项目名称（默认为 `Project_Remis`）。
*   `VERSION`：发布版本号（默认为 `1.1.0`）。

## 构建流程概览

1.  **初始化**：确定项目根目录、发布目录名称和路径。
2.  **清理**：删除之前生成的发布目录（如果存在）。
3.  **脚手架**：创建新的发布目录结构（`app`、`packages`、`python-embed`）。
4.  **Python 嵌入**：从 ZIP 包中提取嵌入式 Python 环境到 `python-embed` 目录。
5.  **复制源代码**：将源代码复制到 `app` 目录。其中 `scripts` 目录的复制使用了 `robocopy` 命令，以精确地排除 `__pycache__`、`.vscode`、`node_modules`、`src` 和 `.vite` 等开发相关的子目录，从而减小发布包的体积。其他如 `data`、`docs`、`requirements.txt` 等必要文件也会被一并复制。
6.  **创建空目录**：在 `app` 目录下创建 `logs`、`my_translation`、`source_mod` 等必要的空目录。
7.  **复制安装脚本**：复制 `setup.bat` 和 `get-pip.py` 到发布目录和嵌入式 Python 目录。
8.  **激活 Conda 环境**：激活指定的 Conda 环境，以便执行 `pip download` 命令。
9.  **打包依赖项**：使用 `pip download` 命令将 `requirements.txt` 中定义的所有依赖项下载到发布包的 `packages` 目录中。
10. **复制运行脚本**：复制 `run.bat` 到发布目录。
11. **最终打包 (可选)**：如果检测到 7-Zip，则将整个发布目录压缩为 ZIP 文件。

## 故障排除

*   **`tar` 命令未找到**：确保您的系统安装了 `tar` 工具，或者手动解压 `python-3.10.11-embed-amd64.zip`。
*   **`python.exe` 未找到**：检查 `python-3.10.11-embed-amd64.zip` 文件是否损坏或路径是否正确。
*   **`pip download` 失败**：检查 `pip_log.txt` 文件以获取详细错误信息，确保网络连接正常，并且 Conda 环境已正确激活。
*   **`7z.exe` 未找到**：如果未安装 7-Zip，脚本将跳过自动压缩步骤，您需要手动压缩发布目录。

---
