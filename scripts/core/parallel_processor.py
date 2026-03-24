# scripts/core/parallel_processor.py
"""
多文件并行处理器
实现真正的批次级全局并行调度，确保所有批次能同时运行
职责：批次级并行调度，不包含文件操作逻辑
"""

import os
import logging
import concurrent.futures
from typing import List, Dict, Any, Callable, Optional, Tuple
from scripts.core.parallel_types import FileTask, BatchTask
from scripts.core.glossary_manager import glossary_manager
from scripts.utils import i18n
from scripts.app_settings import CHUNK_SIZE, GEMINI_CLI_CHUNK_SIZE
from scripts.core.agents.translation_fixer_agent import TranslationFixerAgent
from scripts.utils.post_process_validator import PostProcessValidator


class ParallelProcessor:
    """批次级全局并行处理器 - 实现真正的批次级并行调度"""

    def __init__(self, max_workers: int = 24):
        self.max_workers = max_workers
        self.logger = logging.getLogger(__name__)

    def process_files_parallel(
        self,
        file_tasks: List[FileTask],
        translation_function: Callable
    ) -> Tuple[Dict[str, List[str]], List[Dict[str, Any]]]:
        if not file_tasks:
            return {}, []
        
        batch_tasks = self._create_batch_tasks(file_tasks)
        self.logger.info(i18n.t("parallel_processing_start", count=len(batch_tasks)))
        
        batch_results, all_warnings = self._process_batches_parallel(batch_tasks, translation_function)
        
        file_results = self._collect_file_results(file_tasks, batch_results)
        
        self.logger.info(i18n.t("all_files_processing_completed", count=len(file_results)))
        return file_results, all_warnings

    def _create_batch_tasks(self, file_tasks: List[FileTask]) -> List[BatchTask]:
        batch_tasks = []
        global_batch_index = 0
        
        for file_task in file_tasks:
            if not file_task.texts_to_translate:
                continue

            chunk_size = GEMINI_CLI_CHUNK_SIZE if file_task.provider_name == "gemini_cli" else CHUNK_SIZE
            
            texts = file_task.texts_to_translate
            for i in range(0, len(texts), chunk_size):
                batch_texts = texts[i:i + chunk_size]
                batch_task = BatchTask(
                    file_task=file_task,
                    batch_index=global_batch_index,
                    start_index=i,
                    end_index=i + len(batch_texts),
                    texts=batch_texts
                )
                batch_tasks.append(batch_task)
                global_batch_index += 1
        
        return batch_tasks

    def _process_batches_parallel(
        self,
        batch_tasks: List[BatchTask],
        translation_function: Callable
    ) -> Tuple[Dict[Tuple[str, int], BatchTask], List[Dict[str, Any]]]:
        if not batch_tasks:
            return {}, []

        batch_results = {}
        all_warnings = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_batch = {
                executor.submit(self._process_single_batch, batch, translation_function): batch
                for batch in batch_tasks
            }

            for future in concurrent.futures.as_completed(future_to_batch):
                batch_task = future_to_batch[future]
                processed_task, warnings = future.result()
                batch_key = (batch_task.file_task.filename, batch_task.batch_index)
                batch_results[batch_key] = processed_task
                if warnings:
                    all_warnings.extend(warnings)

        if any(task.failed for task in batch_results.values()):
            failed_count = sum(1 for task in batch_results.values() if task.failed)
            self.logger.error(f"{failed_count}/{len(batch_tasks)} translation batches failed.")
            raise RuntimeError("One or more translation batches failed. Halting workflow.")

        return batch_results, all_warnings

    def _process_single_batch(
        self,
        batch_task: BatchTask,
        translation_function: Callable
    ) -> Tuple[BatchTask, List[Dict[str, Any]]]:
        warnings = []
        MAX_FIX_ATTEMPTS = 0 # Agent Fixer is disabled until it is more robust
        
        # Initial Translation Pass
        processed_task = translation_function(batch_task)
        
        if processed_task.translated_texts is None:
            processed_task.failed = True
            return processed_task, warnings

        # Glossary Validation (Warnings only)
        glossary = glossary_manager.get_glossary_for_translation()
        if glossary:
            simple_glossary = {}
            source_lang_code = processed_task.file_task.source_lang.get("code")
            target_lang_code = processed_task.file_task.target_lang.get("code")
            if source_lang_code and target_lang_code and 'entries' in glossary:
                for entry in glossary.get('entries', []):
                    translations = entry.get('translations', {})
                    source_term = translations.get(source_lang_code)
                    target_term = translations.get(target_lang_code)
                    if source_term and target_term and isinstance(source_term, str) and isinstance(target_term, str):
                        simple_glossary[source_term] = target_term
            if simple_glossary:
                from scripts.utils.glossary_validator import GlossaryValidator
                validator = GlossaryValidator()
                validation_warnings = validator.validate_batch(processed_task, simple_glossary)
                if validation_warnings:
                    warnings.extend(validation_warnings)

        # --- Post-Processing Validation ---
        game_id = processed_task.file_task.game_profile.get("id")
        if not game_id:
            return processed_task, warnings
            
        format_validator = PostProcessValidator()
        current_translations = processed_task.translated_texts
        
        for attempt in range(MAX_FIX_ATTEMPTS + 1):
            format_warnings = []
            has_critical_error = False
            
            # 1. Run Validation
            batch_num = processed_task.batch_index + 1
            start_line = processed_task.start_index + 1
            
            format_results = format_validator.validate_batch(
                game_id=game_id, 
                texts=current_translations, 
                start_line=start_line, 
                source_lang=processed_task.file_task.source_lang,
                source_texts=processed_task.texts # <-- Pass the original texts for Parity Check
            )
            
            for line_res in format_results.values():
                for res in line_res:
                    format_warnings.append(res)
                    if res.level.value == 'error':
                        has_critical_error = True
                        
            # 2. Check if we need to loop (Fixer is disabled, so we just collect warnings)
            if not has_critical_error or attempt >= MAX_FIX_ATTEMPTS:
                warnings.extend(format_warnings)
                processed_task.translated_texts = current_translations
                break
                
            # Agent Fixer logic removed/bypassed

        return processed_task, warnings

    def process_files_stream(
        self,
        file_tasks_generator: Any, # Iterator[FileTask]
        translation_function: Callable
    ) -> Any: # Iterator[Tuple[str, List[str], List[Dict[str, Any]]]]
        """
        Stream processing of files.
        Yields (filename, translated_texts, warnings) as soon as a file is completed.
        """
        # Buffer to hold incomplete file batches: {filename: {batch_index: BatchTask}}
        file_buffers: Dict[str, Dict[int, BatchTask]] = {}
        # Track total batches expected per file: {filename: total_batches}
        file_batch_counts: Dict[str, int] = {}
        
        # We need a way to map futures back to their file and batch index
        # But since we are consuming a generator, we can't submit everything at once if we want to be lazy?
        # Actually, for "streaming" input, we should submit as we consume.
        # But we also need to yield results as they complete.
        
        # Use a bounded executor or semaphore to prevent submitting too many tasks at once if the generator is infinite?
        # For now, assuming the generator yields all files, but we want to process them in parallel and yield results ASAP.
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # We need to manage submission and completion simultaneously.
            # Since we can't easily "select" on both generator and futures, 
            # we can submit all tasks (if memory allows) or use a separate thread for submission.
            # Given the requirement is to reduce memory usage, we shouldn't generate ALL BatchTasks at once if there are millions.
            # But typically we have thousands. 
            
            # However, the main memory bottleneck is loading ALL file contents into memory.
            # The `file_tasks_generator` should yield FileTasks one by one (reading file content on demand).
            
            future_to_info = {}
            
            # Helper to submit batches for a file
            def submit_file(file_task: FileTask):
                if not file_task.texts_to_translate:
                    # Handle empty file immediately
                    return True, (file_task.filename, [], [])
                
                chunk_size = GEMINI_CLI_CHUNK_SIZE if file_task.provider_name == "gemini_cli" else CHUNK_SIZE
                texts = file_task.texts_to_translate
                total_batches = (len(texts) + chunk_size - 1) // chunk_size
                file_batch_counts[file_task.filename] = total_batches
                file_buffers[file_task.filename] = {}
                
                for i in range(0, len(texts), chunk_size):
                    batch_texts = texts[i:i + chunk_size]
                    batch_index = i // chunk_size
                    
                    batch_task = BatchTask(
                        file_task=file_task,
                        batch_index=batch_index,
                        start_index=i,
                        end_index=i + len(batch_texts),
                        texts=batch_texts
                    )
                    
                    future = executor.submit(self._process_single_batch, batch_task, translation_function)
                    future_to_info[future] = (file_task.filename, batch_index, batch_task)
                return False, None

            # We iterate through the generator and submit tasks. 
            # To avoid loading EVERYTHING, we can't just loop to end.
            # But `as_completed` requires a set of futures.
            
            # Strategy: 
            # 1. Submit a chunk of files.
            # 2. Loop while there are pending futures.
            # 3. In the loop, check for completed futures.
            # 4. Also try to submit more files if we have capacity (optional, for now let's just submit all or use a smart loop).
            
            # Simpler approach for V1: 
            # The generator yields FileTasks. We iterate it.
            # If we just iterate and submit, we still hold all Futures in memory. 
            # But Futures are small. The FileTask content is what's big.
            # Wait, `BatchTask` holds reference to `FileTask`. 
            # So if we submit all, we hold all FileTasks in memory. That defeats the purpose.
            
            # So we MUST limit the number of active files/batches.
            MAX_PENDING_BATCHES = self.max_workers * 4
            pending_batches_count = 0
            
            iterator = iter(file_tasks_generator)
            done_consuming = False
            
            while not done_consuming or future_to_info:
                # 1. Submit new tasks if we have capacity
                while not done_consuming and pending_batches_count < MAX_PENDING_BATCHES:
                    try:
                        file_task = next(iterator)
                        is_empty, empty_result = submit_file(file_task)
                        if is_empty:
                            yield empty_result
                        else:
                            # Update pending count
                            pending_batches_count += file_batch_counts[file_task.filename]
                    except StopIteration:
                        done_consuming = True
                
                # 2. Wait for at least one future to complete
                if future_to_info:
                    # wait for first completed
                    done, _ = concurrent.futures.wait(
                        future_to_info.keys(), 
                        return_when=concurrent.futures.FIRST_COMPLETED
                    )
                    
                    for future in done:
                        filename, batch_index, batch_task = future_to_info.pop(future)
                        pending_batches_count -= 1
                        
                        try:
                            processed_task, warnings = future.result()
                        except Exception as e:
                            self.logger.error(f"Critical error in batch processing thread for {filename} batch {batch_index}: {e}")
                            # Create a failed task result so the file logic can progress
                            batch_task.failed = True
                            batch_task.translated_texts = batch_task.texts
                            processed_task = batch_task

                        if filename not in file_buffers:
                            continue
                            
                        file_buffers[filename][batch_index] = processed_task
                        
                        # Check if file is complete (all batches accounted for, even if failed)
                        if len(file_buffers[filename]) == file_batch_counts[filename]:
                            # Assemble file
                            sorted_batches = [file_buffers[filename][i] for i in range(file_batch_counts[filename])]
                            
                            # Get the FileTask from the first batch (all batches share the same FileTask reference)
                            # We need this to return the full context (original lines, etc.)
                            file_task_ref = sorted_batches[0].file_task
                            
                            full_translated_texts = []
                            file_failed = False
                            
                            for task in sorted_batches:
                                if task.failed:
                                    file_failed = True
                                full_translated_texts.extend(task.translated_texts or [])
                            
                            if file_failed:
                                self.logger.error(f"File {filename} incomplete or failed.")
                                yield (file_task_ref, full_translated_texts, [], True) # Fourth item is 'failed' flag
                            else:
                                yield (file_task_ref, full_translated_texts, [], False)
                            
                            # Cleanup
                            del file_buffers[filename]
                            del file_batch_counts[filename]

    def _collect_file_results(
        self,
        file_tasks: List[FileTask],
        batch_results: Dict[Tuple[str, int], BatchTask]
    ) -> Dict[str, List[str]]:
        file_results = {}
        
        grouped_batch_results: Dict[str, Dict[int, BatchTask]] = {}
        for (filename, batch_idx), task in batch_results.items():
            if filename not in grouped_batch_results:
                grouped_batch_results[filename] = {}
            grouped_batch_results[filename][batch_idx] = task
        
        for file_task in file_tasks:
            if not file_task.texts_to_translate:
                file_results[file_task.filename] = []
                continue

            file_translated_texts = []
            file_failed = False
            
            file_batches = grouped_batch_results.get(file_task.filename, {})
            # Check if we have all batches
            # In the original code, we didn't strictly check if we have ALL batches, 
            # but we iterated sorted keys. 
            # If a batch was missing (e.g. exception), it would be skipped, length mismatch -> fallback.
            
            sorted_batch_indices = sorted(file_batches.keys())

            for batch_idx in sorted_batch_indices:
                task = file_batches[batch_idx]
                if task.failed:
                    file_failed = True
                    break
                file_translated_texts.extend(task.translated_texts)

            if file_failed or len(file_translated_texts) != len(file_task.texts_to_translate):
                self.logger.error(f"File translation failed for {file_task.filename}, using fallback.")
                file_results[file_task.filename] = file_task.texts_to_translate
            else:
                file_results[file_task.filename] = file_translated_texts
                self.logger.info(i18n.t("file_translation_completed", filename=file_task.filename))

        return file_results
