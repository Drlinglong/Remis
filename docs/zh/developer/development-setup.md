# 开发环境搭建指南

本文档介绍如何搭建 Project Remis 的本地开发环境。

## 前置要求

- [Git](https://git-scm.com/)
- [Conda / Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- [NVM for Windows](https://github.com/coreybutler/nvm-windows) (或 macOS/Linux 上的 `nvm`)
- [Rust](https://rustup.rs/)（仅 Tauri 桌面壳开发和发布构建需要）

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/Drlinglong/Remis.git
cd Remis
```

### 2. 配置 Python 环境

```bash
# 创建 Conda 环境
conda create -n local_factory python=3.10 -y
conda activate local_factory

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置 Node.js 环境

```bash
cd scripts/react-ui

# React Router 8 / Vite 8 要求 Node.js 22.22.0 或更高版本
nvm install 22.22.0
nvm use 22.22.0

# 安装前端依赖
npm ci
```

### 4. 启动开发服务器

使用一键启动脚本：

```powershell
.\scripts\developer_tools\windows\run-dev.bat
```

这将同时启动：
- **后端服务**: FastAPI（默认 `127.0.0.1:1453`；如果端口占用，脚本会选择可用端口）
- **前端服务**: Vite React / Tauri 开发界面（默认端口 5174）

开发检出请优先使用这一启动脚本。它负责选择正确的 Python 环境、后端端口和
前端代理配置，避免手动启动到另一套环境。

## 目录结构

```
Remis/
├── scripts/
│   ├── react-ui/                  # React 前端
│   │   └── src-tauri/             # Tauri 桌面外壳 (Rust)
│   ├── web_server.py              # FastAPI 后端入口
│   ├── routers/                   # API 路由
│   ├── core/                      # 核心翻译引擎
│   └── workflows/                 # 翻译工作流
├── website/                       # 产品网站
├── data/                          # 数据目录
├── tests/                         # 测试套件
└── docs/                          # 文档
```

## 构建桌面应用

本地检查 Tauri 桌面壳：

```powershell
cargo fmt --manifest-path scripts/react-ui/src-tauri/Cargo.toml -- --check
New-Item -ItemType File -Force scripts/react-ui/src-tauri/web_server-x86_64-pc-windows-msvc.exe | Out-Null
cargo check --locked --manifest-path scripts/react-ui/src-tauri/Cargo.toml
Remove-Item scripts/react-ui/src-tauri/web_server-x86_64-pc-windows-msvc.exe
```

占位文件只用于 `cargo check`。正式发布必须通过仓库发布构建脚本生成真实 Python
sidecar、执行打包后端健康检查，再构建 Windows 安装包。详见发布构建脚本指南。

## 相关文档

- [文档中心](../../documentation-center.md)
- [本地数据目录说明](./user_data_paths.md)
- [CI 与仓库门禁](./ci-setup.md)
- [发布构建脚本指南](./build-release-script-guide.md)
