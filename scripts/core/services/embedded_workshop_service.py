import asyncio
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.core.agents.fix_agent import ReflexionFixAgent
from scripts.core.api_handler import get_handler
from scripts.core.services.workshop_issue_export_service import WorkshopIssueExportService
from scripts.core.services.workshop_writeback_service import (
    apply_validated_workshop_fix_to_path,
    is_repairable_workshop_issue,
    resolve_output_translation_target,
)
from scripts.core.services.vanilla_reference_service import normalize_reference_key

logger = logging.getLogger(__name__)

LOCAL_PROVIDERS = {"ollama", "lm_studio", "vllm", "koboldcpp", "oobabooga", "text-generation-webui", "hunyuan"}


def _resolve_model_config(
    requested_provider: Optional[str],
    requested_model: Optional[str],
    fallback_provider: Optional[str],
    fallback_model: Optional[str],
    provider_runtime: Any = None,
) -> tuple[str, Optional[str]]:
    if provider_runtime is not None:
        provider_name = getattr(provider_runtime, "adapter_id", None)
        model_name = getattr(provider_runtime, "model_id", None)
        if isinstance(provider_runtime, dict):
            provider_name = provider_runtime.get("adapter_id")
            model_name = provider_runtime.get("model_id")
        if not provider_name:
            raise ValueError("Embedded workshop runtime has no provider adapter")
        return str(provider_name), model_name

    from scripts.app_settings import API_PROVIDERS, DEFAULT_API_PROVIDER, config_manager

    provider_name = requested_provider or fallback_provider or DEFAULT_API_PROVIDER
    provider_config = API_PROVIDERS.get(provider_name, {})
    provider_overrides = config_manager.get_value("provider_config", {}).get(provider_name, {})

    model_name = requested_model or fallback_model
    if not model_name:
        model_name = provider_overrides.get("selected_model")
    if not model_name:
        model_name = provider_config.get("default_model")

    return provider_name, model_name


def _normalize_relpath(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip("/").casefold()


def _protected_issue_identities(protected_entries: Any) -> set[tuple[str, str]]:
    if not isinstance(protected_entries, list):
        return set()
    return {
        (
            _normalize_relpath(entry.get("source_file")),
            normalize_reference_key(entry.get("key")),
        )
        for entry in protected_entries
        if isinstance(entry, dict)
    }


def _load_issues(
    sidecar_path: Path,
    protected_entries: Any = None,
) -> List[Dict[str, Any]]:
    if not sidecar_path.exists():
        return []

    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to read embedded workshop sidecar %s: %s", sidecar_path, exc)
        return []

    issues = payload.get("issues", []) if isinstance(payload, dict) else payload if isinstance(payload, list) else []
    protected_identities = _protected_issue_identities(protected_entries)
    return [
        issue for issue in issues
        if isinstance(issue, dict) and str(issue.get("status", "detected")).lower() not in {"fixed", "ignored"}
        and is_repairable_workshop_issue(issue)
        and (
            _normalize_relpath(issue.get("source_file")),
            normalize_reference_key(issue.get("key")),
        ) not in protected_identities
    ]


def _chunked(items: List[Dict[str, Any]], size: int) -> List[List[Dict[str, Any]]]:
    size = max(1, size)
    return [items[index:index + size] for index in range(0, len(items), size)]


def _apply_validated_results(
    output_root: str | Path,
    results: List[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    game_profile: Dict[str, Any],
    target_lang_info: Dict[str, Any],
) -> tuple[int, int]:
    fixed_count = 0
    failed_count = 0
    issue_map = {
        (issue.get("file_name"), issue.get("key")): issue
        for issue in issues
    }
    for result in results:
        original_issue = issue_map.get((result.get("file_name"), result.get("key")))
        if result.get("status") != "SUCCESS" or not original_issue:
            failed_count += 1
            continue

        target_path = resolve_output_translation_target(output_root, original_issue)
        applied = False
        if target_path:
            applied, _failure_reason, _message = apply_validated_workshop_fix_to_path(
                target_path=target_path,
                game_id=game_profile.get("id", ""),
                key=result["key"],
                source_str=original_issue.get("source_str", ""),
                suggested_fix=result.get("suggested_fix", ""),
                target_lang=original_issue.get("target_lang") or target_lang_info.get("code"),
            )
        if applied:
            fixed_count += 1
        else:
            failed_count += 1
    return fixed_count, failed_count


async def _run_embedded_batches(
    agent: ReflexionFixAgent,
    batches: List[List[Dict[str, Any]]],
    concurrency: int,
    dispatch_interval: float,
    game_profile: Dict[str, Any],
    target_lang_info: Dict[str, Any],
    initial_issue_count: int,
    progress_callback: Optional[Any],
) -> List[Dict[str, Any]]:
    total_batches = len(batches)
    next_batch_index = 0
    next_dispatch_time = asyncio.get_running_loop().time()
    dispatch_lock = asyncio.Lock()
    results: List[Dict[str, Any]] = []

    async def claim_batch() -> Optional[tuple[int, List[Dict[str, Any]]]]:
        nonlocal next_batch_index, next_dispatch_time
        async with dispatch_lock:
            if next_batch_index >= total_batches:
                return None
            batch_number = next_batch_index + 1
            batch = batches[next_batch_index]
            next_batch_index += 1
            now = asyncio.get_running_loop().time()
            wait_seconds = max(0.0, next_dispatch_time - now)
            next_dispatch_time = max(now, next_dispatch_time) + dispatch_interval
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        return batch_number, batch

    async def worker(worker_id: int):
        while True:
            claimed = await claim_batch()
            if not claimed:
                return
            batch_number, batch = claimed
            logger.info(
                "Embedded workshop worker %s processing batch %s/%s (%s issues)",
                worker_id,
                batch_number,
                total_batches,
                len(batch),
            )
            batch_result = await agent.fix_batch_loop(
                batch,
                game_id=game_profile.get("id", ""),
                target_lang_code=target_lang_info.get("code"),
            )
            results.extend(batch_result.get("results", []))
            if progress_callback and initial_issue_count > 0:
                progress_percent = int((len(results) / initial_issue_count) * 100)
                progress_callback({
                    "stage": f"Smart Workshop (Proofreading {target_lang_info.get('code', '')})",
                    "stage_code": "embedded_workshop",
                    "percent": min(99, progress_percent),
                    "message": f"[{target_lang_info.get('code', '').upper()}] Smart Workshop: Proofreading and fixing format issues ({len(results)}/{initial_issue_count} processed)...",
                    "workshop_progress": {
                        "detected_count": initial_issue_count,
                        "processed_count": len(results),
                        "fixed_count": sum(result.get("status") == "fixed" for result in results),
                        "failed_count": sum(result.get("status") == "failed" for result in results),
                        "reflection_round": 1,
                    },
                })

    await asyncio.gather(*(worker(worker_id + 1) for worker_id in range(max(1, concurrency))))
    return results


async def run_embedded_workshop(
    output_root: str | Path,
    source_root: str | Path,
    project_id: Optional[str],
    project_name: str,
    source_lang_info: Dict[str, Any],
    target_lang_info: Dict[str, Any],
    game_profile: Dict[str, Any],
    workflow: str,
    run_id: str = "",
    config: Optional[Dict[str, Any]] = None,
    fallback_provider: Optional[str] = None,
    fallback_model: Optional[str] = None,
    fallback_concurrency: Optional[int] = None,
    fallback_batch_size: Optional[int] = None,
    fallback_rpm: Optional[int] = None,
    progress_callback: Optional[Any] = None,
    dynamic_valid_tags: Optional[List[str]] = None,
    provider_runtime: Any = None,
) -> Dict[str, Any]:
    config = dict(config or {})
    output_root = Path(output_root)
    sidecar_path = output_root / WorkshopIssueExportService.OUTPUT_FILENAME
    issues = _load_issues(sidecar_path, config.get("protected_entries"))
    initial_issue_count = len(issues)
    if initial_issue_count == 0:
        return {
            "enabled": True,
            "provider": fallback_provider,
            "model": fallback_model,
            "detected_count": 0,
            "fixed_count": 0,
            "failed_count": 0,
            "remaining_count": 0,
            "issues": [],
            "issues_path": str(sidecar_path),
        }

    provider_name, model_name = _resolve_model_config(
        requested_provider=None if config.get("follow_primary_settings", True) else config.get("api_provider"),
        requested_model=None if config.get("follow_primary_settings", True) else config.get("api_model"),
        fallback_provider=fallback_provider,
        fallback_model=fallback_model,
        provider_runtime=provider_runtime,
    )

    follow_primary = config.get("follow_primary_settings", True)
    batch_size = max(1, int((None if follow_primary else config.get("batch_size_limit")) or fallback_batch_size or (3 if provider_name in LOCAL_PROVIDERS else 10)))
    concurrency = max(1, int((None if follow_primary else config.get("concurrency_limit")) or fallback_concurrency or 1))
    rpm_limit = max(1, int((None if follow_primary else config.get("rpm_limit")) or fallback_rpm or 40))
    dispatch_interval = 60.0 / rpm_limit

    handler_kwargs = {}
    if provider_runtime is not None:
        handler_kwargs = provider_runtime.handler_kwargs()
    handler = get_handler(
        provider_name,
        model_name=model_name,
        **handler_kwargs,
    )
    if not handler or not handler.client:
        raise RuntimeError(f"Embedded workshop could not initialize provider '{provider_name}'.")

    agent = ReflexionFixAgent(handler)
    batches = _chunked(issues, batch_size)
    results = await _run_embedded_batches(
        agent,
        batches,
        concurrency,
        dispatch_interval,
        game_profile,
        target_lang_info,
        initial_issue_count,
        progress_callback,
    )
    fixed_count, failed_count = _apply_validated_results(
        output_root,
        results,
        issues,
        game_profile,
        target_lang_info,
    )

    exporter = WorkshopIssueExportService()
    refreshed_export = exporter.export_for_output(
        output_root=output_root,
        source_root=source_root,
        source_lang_info=source_lang_info,
        target_lang_info=target_lang_info,
        game_profile=game_profile,
        workflow=workflow,
        project_name=project_name,
        project_id=project_id or "",
        run_id=run_id,
        dynamic_valid_tags=dynamic_valid_tags,
    )

    return {
        "enabled": True,
        "provider": provider_name,
        "model": model_name,
        "detected_count": initial_issue_count,
        "batch_size": batch_size,
        "concurrency": concurrency,
        "rpm_limit": rpm_limit,
        "total_batches": math.ceil(initial_issue_count / batch_size),
        "fixed_count": fixed_count,
        "failed_count": failed_count,
        "remaining_count": int(refreshed_export.get("issue_count", 0) or 0),
        "issues": refreshed_export.get("issues", []),
        "issues_path": refreshed_export.get("issues_path"),
        "sidecar_path": refreshed_export.get("sidecar_path"),
    }
