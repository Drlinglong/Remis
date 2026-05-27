### 🔍 数据库层 (DB Layer) 深度审计报告：明显的技术债与设计缺陷

目前数据库层的实现存在严重的一致性与性能隐患，主要集中在架构分裂、会话管理不当和路径硬编码治理上。以下是具体的审计结果说明：

#### 1. 技术栈架构多头分裂 (Architectural Schism)
项目在数据库访问上表现出极大的不一致性：
*   **双轨并行：** 核心业务层（如 ProjectRepository, GlossaryManager）使用了 SQLModel + SQLAlchemy (Async)；而数据库初始化 (db_initializer.py)、迁移 (db_migrations.py) 和大量工具脚本却在直接使用原始连接器 sqlite3 (Sync)。
*   **手工运维：** 没有使用 Alembic 等专业迁移工具，而是靠手动拼 SQL (ALTER TABLE) 并通过 PRAGMA table_info 检查，这种“手工作坊”式的迁移极易产生脏数据。

#### 2. Session 生命周期管理“反模式” (Session Management Anti-pattern)
这是最严重的性能与数据完整性隐患：
*   **“一法一会话”：** 几乎每个 Repository 方法都在内部独立开启/关闭 Session。这意味着每次简单的查询都有“连接-开启事务-提交-关闭”的完整开销，在批量操作时效率极低。
*   **事务无法跨方法传播：** 由于 Session 在方法内部封闭，业务层无法将多个 Repository 操作封装在一个原子事务中，极易导致数据不一致。

#### 3. 数据模型与 Schema 的原始设计 (Schema Flaws)
*   **脆弱的冗余：** Project 表冗余了部分统计字段，但在缺乏事务保障的情况下，这些信息的准确性极低。
*   **JSON 字符串搜索：** GlossaryManager 在搜索 JSON 列时，直接将 JSON 对象 cast 成 String 后用 LIKE 模糊匹配。这会误搜到 JSON 的 Key 或元数据，且性能极差。

#### 4. 绝对路径依赖与“自愈”黑盒 (Brittle Initialization)
*   **硬编码路径：** db_initializer.py 中硬编码了开发者的本地路径，并试图在用户启动时通过正则替换来“修复”环境路径。
*   **DB 操作文件系统：** 初始化脚本直接操作 shutil.move 等文件系统功能。数据库逻辑与文件操作深度耦合，增加了环境迁移的失败率。

#### 🚀 推荐重构方向：
1. **解耦 Session 管理：** 引入依赖注入或 Context Manager 模式，由业务请求决定 Session 生命周期。
2. **废除绝对路径：** 数据库仅存储相对路径，彻底移除脆弱的路径修复逻辑。
3. **规范 JSON 查询：** 使用 SQLite 原生的 JSON 函数或 SQLAlchemy 的 JSON 操作符。
