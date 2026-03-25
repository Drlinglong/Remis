# 流式翻译与断点续传系统架构 (Streaming Translation & Checkpoint System Architecture)

## 1. 概述 (Overview)
本系统旨在解决大型 Mod 翻译过程中的内存瓶颈问题，并提供健壮的断点续传能力。通过采用流式处理（Streaming Processing）和检查点（Checkpointing）机制，系统能够在有限的内存资源下处理包含数千个文件的项目，并允许用户在任务中断后无缝恢复。

## 2. 核心架构 (Core Architecture)

### 2.1 流式处理 (Streaming Processing)
传统的“全量加载”模式会将所有文件内容一次性读入内存，导致处理大型 Mod 时发生 OOM (Out of Memory) 错误。本系统采用了**生产者-消费者**模式：

*   **生产者 (Producer)**: `FileTaskGenerator` 负责按需读取文件内容，生成 `FileTask` 对象。它实现了“懒加载” (Lazy Loading)，确保同一时刻只有少量文件内容驻留在内存中。
*   **消费者 (Consumer)**: `ParallelProcessor` 接收 `FileTask` 流，将其拆分为更小的 `BatchTask`，并分发给线程池进行并行翻译。
*   **聚合器 (Aggregator)**: 翻译完成的批次会被重新组装成完整的文件，并立即写入磁盘。

### 2.2 断点续传 (Checkpoint & Resume)
为了防止长任务中断导致前功尽弃，系统引入了 `CheckpointManager` 来管理任务状态。

*   **状态存储**: 进度信息存储在输出目录下的 `.remis_checkpoint.json` 文件中。
*   **原子性**: 采用“写入临时文件 -> 重命名”的原子操作，防止写入过程中断导致文件损坏。
*   **元数据校验**: 记录模型名称、源语言、目标语言等关键配置。恢复任务时会校验配置一致性，防止“缝合怪”现象。

## 3. 关键组件 (Key Components)

### 3.1 CheckpointManager (`scripts/core/checkpoint_manager.py`)
负责管理断点文件的生命周期。

*   **`save_checkpoint()`**: 使用 `threading.Lock` 保证线程安全，将已完成的文件列表和元数据原子写入磁盘。
*   **`mark_file_completed(filename)`**: 标记单个文件完成并触发保存。
*   **`filter_pending_files(all_files)`**: 在任务启动时，过滤掉已在检查点中记录的完成文件。
*   **`_validate_config()`**: 校验当前运行参数与检查点记录的参数是否一致。

### 3.2 ParallelProcessor (`scripts/core/parallel_processor.py`)
负责并行任务调度。

*   **`process_files_stream()`**: 新增的流式处理入口。
*   **贪婪调度 (Greedy Scheduling)**: 维护一个大小约为 `max_workers * 4` 的任务缓冲区。只要缓冲区未满，就会立即从生成器读取新文件并提交任务，确保线程池始终处于满载状态，避免“队头阻塞” (Head-of-Line Blocking)。

## 4. 技术问答 (Q&A)

### Q1: "脏"检查点问题 (Checkpoint Corruption)
**问题**: 如果中途更换模型（如从 GPT-4 换到 DeepSeek），会导致翻译风格不一致吗？
**方案**: `CheckpointManager` 会记录 `model_name` 等元数据。恢复任务时，如果检测到配置变更，系统会发出警告或拒绝恢复，确保一致性。

### Q2: 并发写入的线程安全 (Race Conditions)
**问题**: 多线程同时完成翻译时，会不会写坏 `.json` 检查点文件？
**方案**:
1.  **原子写入**: 使用 `tempfile` + `shutil.move` 确保文件写入的原子性。
2.  **线程锁**: 使用 `threading.Lock` 确保同一时间只有一个线程能执行状态更新和保存操作。

### Q3: 颗粒度陷阱 (The Granularity Trap)
**问题**: 是按批次保存还是按文件保存？
**方案**: **按文件 (Per-File) 保存**。只有当一个文件的所有批次都成功翻译并聚合写入磁盘后，才会标记该文件为 Completed。这避免了部分批次失败导致文件损坏的问题。

### Q4: 批处理效率 (Pipeline Efficiency)
**问题**: 逐个加载文件会导致线程池闲置等待吗？
**方案**: **不会**。系统采用贪婪调度策略，只要任务缓冲区有空位，就会立即加载下一个文件的批次填补空缺，确保所有并发线程始终忙碌。

## 5. API 参考 (API Reference)

### 5.1 检查断点状态
*   **Endpoint**: `POST /api/translation/checkpoint-status`
*   **Payload**: `{ "mod_name": "...", "target_lang_codes": ["..."] }`
*   **Response**: `{ "exists": true, "completed_count": 450, "total_files_estimate": 2000, "metadata": {...} }`

### 5.2 清除断点
*   **Endpoint**: `DELETE /api/translation/checkpoint`
*   **Payload**: `{ "mod_name": "...", "target_lang_codes": ["..."] }`
*   **Response**: `{ "status": "success", "message": "Checkpoint deleted." }`
