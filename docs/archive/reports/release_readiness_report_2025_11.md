# Remis Mod Factory - 项目现状与 Tauri 发布准备度报告

**日期**: 2025-11-23
**版本目标**: Tauri Alpha/Beta (桌面应用化)

---

## 1. 最近更新摘要 (Git Commit Summary)

基于最近的 Git 提交记录（截至 2025-11-21），项目经历了一次重大的 UI/UX 升级和核心功能修复。

### 🎨 UI/UX 重构 (Major Overhaul)
- **玻璃拟态 (Glassmorphism)**: 全局应用了玻璃拟态设计系统，侧边栏和主容器实现了半透明效果 (`glass-bg`)，底层纹理背景现在清晰可见。
- **主题系统 (Theming)**: 修复了主题切换导致的背景黑屏问题，引入了 `GlobalStyles.jsx` 动态生成 CSS 渐变纹理，不再依赖静态图片。
- **布局优化**: 放弃了 Mantine Grid，转而使用更稳定的 Flexbox 布局，解决了高度计算 (`calc`) 带来的溢出问题。

### 🛠️ 功能修复与改进
- **词典管理器 (Glossary Manager)**: 
  - 彻底修复了滚动条行为，现在滚动条正确地限制在内容区域内，不再导致整个页面滚动。
  - 增强了搜索功能，支持跨文件、跨游戏的“高级搜索范围”。
- **项目管理 (Kanban)**: 
  - 重构为看板 (Kanban) 模式，支持任务拖拽 (`@dnd-kit`)。
  - 实现了看板与侧边栏 (`ContextualSider`) 的强绑定，点击任务卡片可直接编辑详情。

---

## 2. Tauri 发布准备度分析 (Tauri Readiness Analysis)

为了实现“近期发布第一个 Tauri 版本”的目标，通过对 `src-tauri`、后端 `web_server.py` 及前端代码的审计，发现以下关键问题需要优先解决。

### 🔴 关键阻碍 (Critical Blockers)

#### 1. Python 后端打包 (Sidecar Packaging)
- **现状**: 目前 `run.bat` 依赖用户本地安装的 Conda 环境。Tauri 构建出的 `.exe` 默认不会包含 Python 环境。
- **问题**: 用户下载安装包后，如果没有 Python/Conda，应用将无法运行。
- **解决方案**: 
  - 使用 PyInstaller 或 Nuitka 将 `web_server.py` 打包为独立的可执行文件（`.exe`）。
  - 在 `tauri.conf.json` 中配置 `externalBin` (Sidecar 模式)，让 Tauri 启动时自动拉起这个 Python 进程。

#### 2. API 通信地址 (Hardcoded URLs)
- **现状**: 前端代码 (如 `useKanban.js`) 硬编码了 `http://localhost:8000`。
- **问题**: 
  - 如果端口 8000 被占用，Python 后端启动失败，前端无法连接。
  - 在生产环境中，Sidecar 可能会被分配动态端口。
- **解决方案**: 
  - **短期**: 保持 8000 端口，但在 Python 端增加端口占用检测和提示。
  - **长期**: Tauri 启动 Sidecar 时通过环境变量传递随机端口，前端通过 Tauri API 读取该配置。

#### 3. 数据持久化路径 (Data Persistence)
- **现状**: 数据库 (`database.sqlite`) 和项目配置文件 (`.remis_project.json`) 目前存储在项目根目录或 `data/` 目录下。
- **问题**: 安装到 `C:\Program Files` 后，应用通常没有写入权限，会导致数据库只读或报错。
- **解决方案**: 
  - 必须检测运行环境。如果是打包版本，需将数据文件重定向到用户的 `AppData` (Windows) 或 `Application Support` (macOS) 目录。
  - 使用 `appdirs` 库或 Tauri 的 `path` API 来确定正确的存储路径。

### 🟡 重要配置 (Important Configuration)

- **应用标识 (Identifier)**: `tauri.conf.json` 仍使用默认的 `com.tauri.dev`。发布前必须修改为唯一的标识符 (如 `com.remis.modfactory`)，否则无法通过操作系统签名验证，且可能与其他 Tauri 应用冲突。
- **图标资源**: 目前使用的是 Tauri 默认图标。需要替换为项目专属图标。

---

## 3. 长远改进建议 (Long-term Roadmap)

### 🏗️ 架构演进
- **IPC 通信**: 目前前端通过 HTTP 请求与 Python 后端通信。长远来看，可以考虑封装 Tauri Command，将 HTTP 请求转化为本地 IPC 调用，安全性更高，且不受网络防火墙影响。
- **依赖解耦**: 现在的 `web_server.py` 混合了 API 定义和部分业务逻辑。建议进一步将业务逻辑剥离到纯 Python 包中，API 层只负责数据转发。

### 🛡️ 代码质量与测试
- **TypeScript 迁移**: 前端目前是 JavaScript。随着项目复杂度增加（特别是看板和词典的数据结构变复杂），迁移到 TypeScript 能显著减少“属性不存在”类的运行时错误。
- **E2E 测试稳定性**: 既然 Playwright 存在路由不稳定的问题，建议在 Tauri 环境下引入集成测试，直接测试打包后的应用行为。

### 🧩 功能扩展
- **插件化架构**: 既然目标是 Mod 工厂，未来可以允许用户编写简单的 Python 脚本作为“插件”挂载到工厂中，处理特定的文本格式转换。

---

**总结**: 项目 UI/UX 已达到较高水平，核心功能逻辑闭环。接下来的工作重心应从“功能开发”转向“工程化打包”，重点解决 Python 环境分发和文件读写权限问题。
