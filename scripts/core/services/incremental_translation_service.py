import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from scripts.core.api_handler import get_handler
from scripts.core.parallel_processor import ParallelProcessor
from scripts.core.parallel_types import FileTask

logger = logging.getLogger(__name__)


class IncrementalTranslationService:
    def translate_dirty_files(
        self,
        file_tasks_for_ai: List[FileTask],
        selected_provider: str,
        model_name: Optional[str],
        target_lang_code: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Tuple[Dict[str, List[str]], List[Dict[str, Any]]]:
        if not file_tasks_for_ai:
            if progress_callback:
                progress_callback({
                    "stage": "Finishing",
                    "percent": 90,
                    "message": f"No new content for {target_lang_code}.",
                })
            return {}, []

        handler = get_handler(selected_provider, model_name=model_name)
        if not handler or not handler.client:
            raise RuntimeError(f"API Provider {selected_provider} not configured.")

        for task in file_tasks_for_ai:
            task.client = handler.client

        processor = ParallelProcessor()

        def translate_batch(batch):
            return handler.translate_batch(batch)

        def internal_progress(current, total):
            if progress_callback:
                pct = 20 + int((current / total) * 70)
                progress_callback({
                    "stage": "Translating",
                    "percent": pct,
                    "batch_idx": current,
                    "total_batches": total,
                    "message": f"Translating {target_lang_code}: {current}/{total} batches",
                })

        logger.info(f"Translating {len(file_tasks_for_ai)} files incrementally for {target_lang_code}...")
        return processor.process_files_parallel(file_tasks_for_ai, translate_batch, internal_progress)
