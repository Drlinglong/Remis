# Remis 构建流水线架构文档 (Build Pipeline Architecture)

**版本**: 1.1
**日期**: 2025-12-03
**状态**: 已实施

## 1. 概述 (Overview)

Project Remis 采用 **Tauri + React + Python (FastAPI)** 的混合架构。为了将 Python 后端与 Tauri 桌面应用无缝集成，我们采用了 **Sidecar (边车)** 模式。本构建流水线旨在自动化处理从源码清理、后端冻结、资源整合到最终安装包生成的全过程。

**版本 1.1 更新**: 引入了“骨肉分离”的数据库策略，支持 Windows 环境下的用户数据隔离 (`%APPDATA%`) 和演示版种子数据 (`Seed Data`) 的自动导出与初始化。

## 2. 架构设计 (Architecture Design)

构建流程分为三个主要阶段：**数据准备 (Data Prep)**、**后端冻结 (Backend Freezing)** 和 **前端/应用打包 (Frontend/App Bundling)**。

```mermaid
graph TD
    A[开始构建] --> B{环境清理}
    B --> C[数据准备 (Python)]
    C --> D[后端构建 (Python)]
    D --> E[Sidecar 适配]
    E --> F[前端构建 (React)]
    F --> G[Tauri 打包 (Rust)]
    G --> H[最终安装包 (.msi/.exe)]

    subgraph "数据准备"
    C1[export_seed_data.py] -->|导出| C2[seed_data_*.sql]
    C1 -->|路径清洗| C3[Demo 资源]
    end

    subgraph "后端构建"
    D1[web_server.py] -->|PyInstaller| D2[web_server.exe]
    C2 -->|--add-data| D2
    C3 -->|--add-data| D2
    end

    subgraph "Sidecar 适配"
    D2 -->|重命名| E1[web_server-<target-triple>.exe]
    E1 -->|移动| E2[src-tauri/binaries/]
    end
```

## 3. 详细构建步骤 (Detailed Steps)

构建逻辑由 `scripts/build_pipeline.py` 统一编排。

### 3.1 环境清理 (Clean & Init)
为了防止旧构建产物的干扰，脚本首先执行清理操作：
-   删除 `dist/` (PyInstaller 产物)
-   删除 `build/` (PyInstaller 临时文件)
-   删除 `scripts/react-ui/src-tauri/binaries/` (旧的 Sidecar 文件)
-   重建 `binaries/` 目录以确保目标路径存在。

### 3.2 数据准备 (Data Preparation) - [NEW]
为了支持“开箱即用”的演示体验，同时不污染开发者的环境：
-   **脚本**: `scripts/utils/export_seed_data.py`
-   **功能**:
    -   连接开发环境数据库。
    -   导出 `glossaries` (词典) 和指定的 Demo 项目 (`Remis_Demo_*`)。
    -   **路径清洗**: 将 Demo 项目的绝对路径替换为 `{{DEMO_ROOT}}` 占位符。
    -   生成 `data/seed_data_main.sql` 和 `data/seed_data_projects.sql`。

### 3.3 后端冻结 (Backend Freezing)
使用 **PyInstaller** 将 Python 源码打包为独立可执行文件。
-   **入口文件**: `scripts/web_server.py`
-   **资源嵌入**:
    -   `--add-data "data/seed_data_*.sql;data"`: 嵌入种子数据 SQL。
    -   `--add-data "demos;demos"`: 嵌入演示项目源文件 (如果存在)。
-   **关键参数**:
    -   `--onefile`: 生成单文件 exe。
    -   `--noconsole`: 运行时不显示控制台窗口 (后台运行)。
    -   `--name web_server`: 指定输出文件名。
    -   `--hidden-import`: 显式包含 `uvicorn`, `fastapi`, `pydantic` 等动态加载的库。

### 3.4 Sidecar 适配 (Sidecar Compliance)
Tauri 要求 Sidecar 二进制文件必须包含目标平台的 **Target Triple** 后缀。
-   **检测**: 脚本自动检测当前操作系统和 CPU 架构 (例如 `x86_64-pc-windows-msvc`)。
-   **重命名**: 将 `web_server.exe` 重命名为 `web_server-x86_64-pc-windows-msvc.exe`。
-   **部署**: 将重命名后的文件移动到 `src-tauri/binaries/` 目录。

### 3.5 前端构建 (Frontend Build)
调用 Vite 进行 React 前端构建。
-   命令: `npm install` && `npm run build`
-   输出: `scripts/react-ui/dist/`

### 3.6 Tauri 打包 (Tauri Build)
调用 Tauri CLI 生成最终安装包。
-   命令: `npm run tauri build`
-   配置: `tauri.conf.json` 中的 `externalBin` 字段必须包含 `"web_server"`，以便 Tauri 在打包时自动包含 Sidecar 并处理路径映射。

## 4. 运行时行为 (Runtime Behavior)

### 4.1 数据库初始化 (Cold Start)
应用启动时 (`scripts/core/db_initializer.py`) 会执行以下逻辑：
1.  **路径检测**: 识别当前运行环境 (Frozen vs Dev)。
2.  **AppData 定位**: 确定用户数据目录 `%APPDATA%\RemisModFactory`。
3.  **冷启动检查**:
    -   如果 `database.sqlite` 或 `projects.sqlite` 不存在：
    -   读取打包在 exe 内部的 `seed_data_*.sql`。
    -   执行 SQL 初始化表结构和默认数据。
    -   **路径回填 (Hydration)**: 将数据库中的 `{{DEMO_ROOT}}` 替换为实际的 `_internal/demos` 路径，确保 Demo 项目可立即访问。

## 5. 配置说明 (Configuration)

### 5.1 Tauri 配置 (`tauri.conf.json`)
必须在 `bundle` -> `externalBin` 中注册 Sidecar 名称（不带后缀）：

```json
"bundle": {
  "active": true,
  "targets": "all",
  "externalBin": [
    "web_server"
  ],
  ...
}
```

### 5.2 依赖管理
-   **Python**: `requirements.txt` 定义了后端依赖。
-   **Node.js**: `package.json` 定义了前端依赖。
-   **Rust**: `Cargo.toml` 定义了 Tauri 核心依赖。

## 6. 使用指南 (Usage)

### 6.1 运行构建
在项目根目录下运行批处理文件：
```batch
build_app.bat
```
或者直接运行 Python 脚本：
```bash
python scripts/build_pipeline.py
```

### 6.2 前置要求
-   Python 3.x (已安装 pip 依赖)
-   Node.js & npm
-   Rust & Cargo (必须配置在 PATH 中)

## 7. 故障排除 (Troubleshooting)

-   **找不到 Cargo**: 确保安装了 Rust 并重启了终端。
-   **Sidecar 启动失败**: 检查 PyInstaller 的 `--hidden-import` 是否遗漏了库。
-   **构建卡住**: 检查网络连接 (npm/pip/cargo 拉取依赖)。
-   **Demo 项目路径错误**: 检查 `export_seed_data.py` 中的 `sanitize_path` 逻辑是否覆盖了你的本地路径结构。
