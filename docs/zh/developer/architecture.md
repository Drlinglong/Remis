# 🏗️ 项目架构

> 系统设计说明和技术架构详解
>
> 状态说明：这份文档包含较早阶段的 CLI/分层架构描述与后续能力扩展说明，适合作为背景阅读，不应默认视为当前代码的精确镜像。当前实现事实以代码和测试为准；仓库协作与安全规则见根目录 `AGENTS.md`。

## 🏛️ 系统架构图

目前项目已从早期的 CLI 脚本工具演进为**现代 Web SPA 架构**，采用 FastAPI 后端服务 + SQLite 数据存储 + React 响应式前端的整体结构：

```
┌─────────────────────────────────────────────────────────────┐
│                 表现层 (React SPA Frontend)                 │
├─────────────────────────────────────────────────────────────┤
│  scripts/react-ui/src/                                      │
│  ├── components/            # 交互组件 (看板、校对、项目配置)│
│  └── services/              # API 客户端与状态管理           │
├─────────────────────────────────────────────────────────────┤
│                 接口与控制层 (API & Web Server)             │
├─────────────────────────────────────────────────────────────┤
│  scripts/web_server.py      # FastAPI 主服务入口             │
│  └── scripts/routers/       # RESTful API 路由分发           │
├─────────────────────────────────────────────────────────────┤
│                 业务服务层 (Services Layer)                 │
├─────────────────────────────────────────────────────────────┤
│  scripts/core/services/                                     │
│  ├── initial_translation_*  # 细粒度初次翻译服务 (批处理/文件)│
│  ├── incremental_*          # 增量翻译、快照与 Diff 链条      │
│  ├── kanban_service.py      # 翻译看板状态机与任务跟踪       │
│  ├── proofreading_service.py# 校对状态管理                   │
│  └── project_watch_service.py # 本地化目录文件监听服务       │
├─────────────────────────────────────────────────────────────┤
│                 核心引擎层 (Core Engine Layer)              │
├─────────────────────────────────────────────────────────────┤
│  scripts/core/                                              │
│  ├── project_manager.py     # 项目生命周期管理器             │
│  ├── api_handlers/          # LLM 适配器体系 (Gemini/DeepSeek)│
│  ├── glossary_manager.py    # 游戏专用术语词典               │
│  ├── file_parser.py         # Paradox .yml 格式解析器        │
│  ├── file_builder.py        # Paradox 格式高保真重构器       │
│  ├── parallel_processor.py  # 多任务并行执行引擎             │
│  └── post_processing_manager.py # 后处理与验证器管理         │
├─────────────────────────────────────────────────────────────┤
│                 持久化数据层 (Data & Storage)                │
├─────────────────────────────────────────────────────────────┤
│  scripts/core/              # 数据库控制与迁移               │
│  ├── db_manager.py          # SQLite 连接管理器              │
│  ├── db_models.py           # SQLAlchemy 模型定义            │
│  └── db_initializer.py      # 初始库表与测试套件库构建       │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 核心模块与现代服务详解

### 1. Web 接口层 (`web_server.py` & `routers/`)
*   **FastAPI 驱动**：作为应用核心枢纽，提供完整的 RESTful API 以驱动 React 界面。
*   **路由解耦**：将不同功能（如项目管理、翻译流、词典操作、看板交互）拆分在 `routers/` 的子模块中。
*   **生命周期监控**：负责挂载后台定时任务和文件目录监听器。

### 2. 精细化服务层 (`core/services/`)
这是目前 Remis 核心业务逻辑沉淀的主要位置，摆脱了对 UI 和 CLI 的直接依赖：
*   **初次翻译链条 (`initial_translation_*_service.py`)**：负责处理新 Mod 的全量翻译，支持批处理分片 (`batch_service`)、断点快照 (`snapshot_service`) 以及翻译发现与自动构建。
*   **增量翻译链条 (`incremental_*_service.py`)**：专门用于已翻译 Mod 在版本升级时的增量处理。通过对新旧版本文件生成哈希与结构 Diff (`diff_service`)，只翻译新增或修改的键值，极大节省了 API 开销并保留了已有校对成果。
*   **看板服务 (`kanban_service.py`)**：实现类似 Jira 的可视化汉化工作流状态追踪，对词条细分“未翻译、翻译中、已翻译、校对中、已完成”等状态。

### 3. 数据层 (`core/db_*`)
*   **关系型存储**：使用 SQLite 作为本地存储引擎，依托 SQLAlchemy 映射模型（`db_models.py`）。
*   **增量迁移**：拥有独立的 `db_migrations.py` 机制，确保不同版本升级时本地数据的结构兼容。

### 4. 插件式 AI 翻译适配层 (`core/*_handler.py`)
系统建立在统一的基类 `base_handler.py` 之上，提供极其丰富的 AI 服务商接入：
*   **闭源/商用 API**：`gemini_handler.py`, `openai_handler.py`, `deepseek_handler.py`, `grok_handler.py`, `qwen_handler.py`, `hunyuan_handler.py`。
*   **代理与中转**：`modelscope_handler.py`, `siliconflow_handler.py`, `nvidia_handler.py`。
*   **本地算力**：`local_handler.py`，支持无缝桥接本地的 Ollama/vLLM 推理端。

### 5. Paradox 解析与并行处理
*   **高保真解析/生成 (`file_parser.py` / `file_builder.py` / `loc_parser.py`)**：针对 Paradox 游戏本地化文件独特的编码（UTF-8-BOM）和键值结构（如 `key:0 "value"`）提供严格解析，完美还原注释、缩进和特殊控制符。
*   **并行计算 (`parallel_processor.py`)**：采用多线程与分批处理技术，避免了翻译过程中的长文本阻塞，在测试中可实现数倍的加速效果。

---

## 🚀 原有功能特性保留说明

### 1. 多游戏/多语言支持
*   **多游戏档案**：支持为不同 P社游戏（维多利亚3、群星、钢铁雄心4、十字军之王3等）定义不同的文件结构和处理规则。
*   **“一键多语”模式**：支持将源语言版本，一键批量翻译为其余所有官方语言。
    - 维多利亚3：11种官方语言
    - 群星：10种官方语言
    - 钢铁雄心4：9种官方语言
    - 十字军之王3：8种官方语言
    - 欧陆风云4：4种官方语言（由于 EU4 的旧引擎限制，暂不支持对 EU4 的中文本地化）。
*   **自定义目标语言支持**：支持用户创建非官方语言或“套壳”语言包，兼容将翻译内容伪装成英文文件等特殊汉化场景。

### 2. 完整的 Mod 包处理与校验
*   **深度文件扫描**：递归遍历本地化文件夹下的所有子目录。
*   **元数据同步**：自动处理并翻译 Victoria 3 的 `.metadata/metadata.json` 和群星的 `descriptor.mod` 文件。
*   **后处理格式验证 (`post_process_validator.py` / `punctuation_handler.py`)**：格式验证与智能标点映射，保证翻译文本完全符合游戏特定格式，防止闪退或乱码。

---

## 🔄 数据流向与生命周期

### 1. 全新项目载入与初次翻译
```
选择 Mod 目录 ──> 读取 metadata ──> 解析 .yml ──> 结构导入 SQLite ──> 生成看板任务 ──> 分批 LLM 翻译 ──> 后处理验证 ──> 高保真写回 .yml
```

### 2. Mod 更新时的增量翻译
```
旧版本 Snapshot
              ├──> 结构与哈希 Diff ──> 提取新增/修改键 ──> 发送增量翻译 ──> 更新 SQLite ──> 重建目标文件
新版本 Snapshot
```

---

## 🔒 性能与并发优化

*   **数据库事务锁**：合理使用 SQLite 的 WAL 模式，确保 API 请求高频写入与后台文件监听器写入不产生冲突。
*   **API 速率保护**：各大 AI Handler 内置指数退避重试和动态速率限制器（Rate Limiter），避免高并发下的 429 报错。
*   **前端状态批处理**：React 页面通过 WebSocket 或轮询高效获取后台 Task 进度，保证界面实时渲染不卡顿。

---

## 🚀 未来扩展与改进规划

1.  **本地嵌入式 RAG 系统 (本地知识库)**
    *   内置轻量级向量化模型（`bge-m3` ONNX 格式，按需延迟下载）。
    *   内置轻量级重排序模型（`bge-reranker-base` ONNX 格式）或桥接云端 API。
    *   自动索引项目下的技术规范、翻译记忆和历史校对词典，实现 AI 翻译时的自动上下文检索。
2.  **更智能的新词挖掘系统 (Neologism Mining)**
    *   深化 `neologism_miner.py` 的自然语言处理，自动提取游戏文本中的人名、地名等专有名词并一键录入词典。
3.  **社区词典云端共享**
    *   支持用户将本地词典以加密形式上传并共享给汉化组其他成员。

---

> 📚 **关联文档**:
> - [RAG 架构与模型选型](rag-design.md)
> - [并行处理技术详解](developer/parallel-processing.md)
> - [重构决策指南](developer/refactor_decision_guide.md)
