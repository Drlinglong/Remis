# 开发环境搭建指南

本文档介绍如何搭建 Project Remis 的本地开发环境。

## 前置要求

- [Git](https://git-scm.com/)
- [Conda / Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- [NVM for Windows](https://github.com/coreybutler/nvm-windows) (或 macOS/Linux 上的 `nvm`)

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

# 安装指定版本的 Node.js
nvm install v20.12.2
nvm use v20.12.2

# 安装前端依赖
npm install
```

### 4. 启动开发服务器

使用一键启动脚本：

```bash
./run-dev.bat
```

这将同时启动：
- **后端服务**: FastAPI (端口 8000)
- **前端服务**: Vite React (端口 5173)

或者手动启动：

**终端 1 - 后端：**
```bash
conda activate local_factory
uvicorn scripts.web_server:app --reload --port 8000
```

**终端 2 - 前端：**
```bash
cd scripts/react-ui
npm run dev
```

## 目录结构

```
remis-mod-factory/
├── src-tauri/                     # Tauri 桌面外壳 (Rust)
├── scripts/
│   ├── react-ui/                  # React 前端
│   ├── web_server.py              # FastAPI 后端入口
│   ├── routers/                   # API 路由
│   ├── services/                  # 业务服务层
│   ├── core/                      # 核心翻译引擎
│   └── workflows/                 # 翻译工作流
├── data/                          # 数据目录
├── tests/                         # 测试套件
└── docs/                          # 文档
```

## 构建桌面应用

构建 Tauri 桌面应用需要额外安装 Rust 工具链：

```bash
# 安装 Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 构建
npm run tauri build
```

## 相关文档

- [项目技术文档](../main.md)
- [前端开发指南](../frontend/)
- [API 文档](../technical/)
