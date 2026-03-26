import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from scripts.core.api_handler import get_handler
from scripts.core.parallel_processor import ParallelProcessor
from scripts.core.parallel_types import FileTask
from scripts.app_settings import RECOMMENDED_MAX_WORKERS

logger = logging.getLogger(__name__)


class IncrementalTranslationService:
    LOCAL_PROVIDERS = {"ollama", "lm_studio", "vllm", "koboldcpp", "oobabooga", "text-generation-webui"}

    def _resolve_max_workers(self, selected_provider: str, concurrency_limit: Optional[int]) -> int:
        if concurrency_limit:
            return max(1, concurrency_limit)
        if selected_provider in self.LOCAL_PROVIDERS:
            return 1
        return RECOMMENDED_MAX_WORKERS

    def translate_dirty_files(
        self,
        file_tasks_for_ai: List[FileTask],
        selected_provider: str,
        model_name: Optional[str],
        target_lang_code: str,
        concurrency_limit: Optional[int] = None,
        rpm_limit: Optional[int] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Tuple[Dict[str, List[str]], List[Dict[str, Any]]]:
        if not file_tasks_for_ai:
            if progress_callback:
                progress_callback({
                    "stage": "Finishing",
                    "stage_code": "finishing",
                    "percent": 90,
                    "message": f"No new content for {target_lang_code}.",
                })
            return {}, []

        handler = get_handler(selected_provider, model_name=model_name)
        if not handler or not handler.client:
            raise RuntimeError(f"API Provider {selected_provider} not configured.")

        for task in file_tasks_for_ai:
            task.client = handler.client

        processor = ParallelProcessor(max_workers=self._resolve_max_workers(selected_provider, concurrency_limit))

        def translate_batch(batch):
            return handler.translate_batch(batch)

        def internal_progress(current, total):
            if progress_callback:
                pct = 20 + int((current / total) * 70)
                progress_callback({
                    "stage": "Translating",
                    "stage_code": "translating_content",
                    "percent": pct,
                    "batch_idx": current,
                    "total_batches": total,
                    "message": f"Translating {target_lang_code}: {current}/{total} batches",
                })

        logger.info(
            f"Translating {len(file_tasks_for_ai)} files incrementally for {target_lang_code} "
            f"(workers={processor.max_workers}, rpm_limit={rpm_limit})..."
        )

        from scripts.utils.rate_limiter import rate_limiter
        previous_rpm = rate_limiter.rpm
        if rpm_limit:
            rate_limiter.update_rpm(int(rpm_limit))

        try:
            return processor.process_files_parallel(file_tasks_for_ai, translate_batch, internal_progress)
        finally:
            if rpm_limit and previous_rpm != rate_limiter.rpm:
                rate_limiter.update_rpm(previous_rpm)
