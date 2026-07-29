# 前端开发环境设置

本文档概述了如何设置并运行前端开发服务器。

项目使用一个“一键启动”脚本来简化整个开发环境的搭建流程。

## 前置要求

* [Conda / Miniconda](https://docs.conda.io/en/latest/miniconda.html)
* [NVM for Windows](https://github.com/coreybutler/nvm-windows) (或在 macOS/Linux 上使用 `nvm`)

## 一键启动流程

1.  **安装 Node.js**: 首先，进入 `scripts/react-ui` 目录，然后运行 `nvm install`。该命令会读取 `.nvmrc` 并安装 React Router 8 工具链要求的最低版本 Node.js `v22.22.0`。
2.  **运行启动器**: 在项目根目录，直接执行主开发环境启动器：
    ```bash
    scripts\developer_tools\windows\run-dev.bat
    ```

该脚本会自动完成以下操作：
- 启动一个用于后端的终端窗口，激活 `local_factory` Conda 环境，并开启 FastAPI 服务。
- 启动另一个用于前端的终端窗口，使用 `nvm` 设置正确的 Node.js 版本，并开启 Vite 开发服务。

前端开发界面默认位于 `http://127.0.0.1:5174`，并连接到启动器从 `1453` 开始选择的后端端口。
