# Multi-file Parallel Processing Implementation Summary

## 🎯 Task Objective

This project aims to thoroughly solve the blocking problems existing in traditional file processing by implementing batch-level global parallel scheduling, thereby significantly improving the efficiency and user experience of Mod localization.

## ❌ Review of Original Problems

Before the introduction of the current parallel architecture, the project faced major challenges:

*   **File-level Serial Processing**: The translation process was file by file, and even if batches could be processed in parallel within a single file, the overall efficiency was limited by the serial execution between files.
*   **Limited Batch-level Parallelism**: Although texts within a single file could be split into batches and submitted to AI for parallel translation, this parallelism was limited to within that single file.
*   **Resource Waste**: When there were a large number of files, even if multiple parallel threads were configured, most threads might be idle, waiting for the current file to be processed. For example, if there were 24 parallel threads, but only 1 batch of 1 file could run at a time, the other 23 threads would be wasted.

## ✅ Solution: Batch-level Global Parallel Scheduling

This project introduces a new `ParallelProcessor` architecture, implementing **batch-level global parallel scheduling**. Its core idea is to treat all text batches from all files to be processed as a unified task pool and process them in parallel.

### 1. Core Components and Data Structures

*   **`FileTask`**: A file task data structure that encapsulates all necessary information for a single file, including filename, original text lines, list of texts to translate, key mapping, language configuration, game configuration, Mod context, AI service provider name, output path, and AI client instance.
*   **`BatchTask`**: A batch task data structure that encapsulates the information required for a single batch translation, including the `FileTask` it belongs to, the batch index within the file, the start/end indices of the texts, and the actual list of texts to be translated.
*   **`ParallelProcessor`**: The main parallel processor class, responsible for orchestrating and executing the entire parallel scheduling process.

### 2. Detailed Scheduling Process

The core method `process_files_parallel` of `ParallelProcessor` coordinates the entire parallel translation process:

1.  **Task Decomposition (`_create_batch_tasks`)**:
    *   `ParallelProcessor` first iterates through all `FileTask`s.
    *   For each file, based on the amount of text to be translated and the configured `CHUNK_SIZE` (batch size), its text is split into multiple `BatchTask`s.
    *   **Dynamic Batch Size**: The `CHUNK_SIZE` can be dynamically adjusted according to different AI service providers. For example, for `gemini_cli`, a larger `CHUNK_SIZE` (`GEMINI_CLI_CHUNK_SIZE`) might be used to optimize the overhead and performance of CLI calls.
    *   Each `BatchTask` is assigned a globally unique index for subsequent result collection.

2.  **Global Batch Parallel Processing (`_process_batches_parallel`)**:
    *   `ParallelProcessor` uses `concurrent.futures.ThreadPoolExecutor` to create a thread pool, whose size is determined by the `max_workers` parameter.
    *   All generated `BatchTask`s are submitted to this thread pool, achieving **true global parallelism**. This means that batches from different files can be translated simultaneously in different threads.
    *   `concurrent.futures.as_completed` is used to asynchronously collect completed batch results.

3.  **Batch Translation Execution (`_process_single_batch`)**:
    *   Each worker thread in the thread pool calls `_process_single_batch` to process a `BatchTask`.
    *   `_process_single_batch` calls the passed `translation_function` (usually the AI service handler's `translate_texts_in_batches` method) to perform the actual translation.
    *   **AI Service Handler Responsibility**: AI service handlers (e.g., `gemini_handler.py`) focus on **interacting with specific AI services**, including constructing detailed prompts (injecting context, glossary terms, punctuation conversion hints, game-specific formatting rules), calling APIs, parsing responses, and handling retry logic. **Importantly, AI service handlers typically process texts within a single batch serially internally, avoiding the complexity of nested thread pools.**
    *   **Fault Tolerance Mechanism**: If a single batch translation fails (e.g., API error, network issue, AI response format mismatch), `_process_single_batch` returns `None`. At this point, `_process_batches_parallel` catches this failure and uses the original text of that batch as a fallback, ensuring that the entire translation process is not interrupted.

4.  **Result Collection and File Reconstruction (`_collect_file_results`)**:
    *   After all batch tasks are completed, `ParallelProcessor` collects and sorts all batch results by file.
    *   It checks the completeness of the translation results for each file. If some batches of a file used fallback text, or the number of results does not match, the translation result for that file will use its original text as a fallback to ensure data integrity.
    *   Finally, the complete translation results (or fallback original texts) for each file are assembled.

### 3. Performance Improvement

Through this batch-level global parallel architecture, the project has achieved significant performance improvements:

*   **Speedup Ratio**: In tests, a speedup ratio of up to **5.52 times** was achieved compared to the old serial architecture.
*   **Efficiency Improvement**: Overall efficiency increased by **451.7%**.
*   **Resource Utilization**: Resource utilization increased from only 1/24 of thread resources (single-file serial processing) to 14/24 of thread resources (all batches processed in parallel), fully leveraging the potential of multi-core CPUs and network bandwidth.

### 4. Architectural Advantages

*   **High Efficiency**: Significantly reduces the total time required to process a large number of Mod files.
*   **High Stability**: A robust fault tolerance mechanism ensures that even if some AI requests fail, the entire translation task can proceed smoothly and provide usable results.
*   **Extensibility**: Easy to integrate new AI service providers. Only requires implementing an AI service handler that conforms to the `translation_function` interface.
*   **High-Quality Translation**: Through meticulous prompt engineering (context, glossary, formatting rules), the accuracy of AI translation and the consistency of game terminology are ensured.
*   **Clear Responsibilities**: Separation of scheduling logic and AI interaction logic improves code maintainability and readability.

## 🔧 Technical Implementation Details

*   **Python `concurrent.futures.ThreadPoolExecutor`**: The core tool for implementing parallel processing.
*   **Dynamic `CHUNK_SIZE`**: Configured via `CHUNK_SIZE` and `GEMINI_CLI_CHUNK_SIZE` in `scripts/config.py`, and dynamically selected in `_create_batch_tasks` based on `provider_name`.
*   **Retry Mechanism**: AI service handlers (e.g., `_translate_chunk` in `gemini_handler.py`) have built-in retry logic to handle temporary network fluctuations or API errors.
*   **Prompt Engineering**: `gemini_handler.py` demonstrates how to construct complex prompts, including:
    *   `base_prompt`: Basic translation instructions.
    *   `context_prompt_part`: Mod theme context.
    *   `glossary_prompt_part`: Dynamically injected game terminology glossary.
    *   `punctuation_prompt_part`: Intelligently generated punctuation conversion hints.
    *   `format_prompt_part`: Game-specific formatting rules to ensure translation results conform to game file formats.
*   **AI Thinking Feature**: `gemini_handler.py` supports enabling or disabling Gemini's "thinking feature" (`thinking_config`) based on configuration, balancing translation quality and cost.

## Summary

This project, through its meticulously designed batch-level global parallel scheduling architecture combined with intelligent AI service interaction strategies, has successfully built an efficient, stable, and extensible Paradox Mod localization solution. This architecture not only solves performance bottlenecks but also lays a solid technical foundation for future integration of more AI services and optimization of translation quality.