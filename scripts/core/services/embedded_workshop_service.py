import asyncio
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.core.agents.fix_agent import ReflexionFixAgent
from scripts.core.api_handler import get_handler
from scripts.core.services.workshop_issue_export_service import WorkshopIssueExportService

logger = logging.getLogger(__name__)

LOCAL_PROVIDERS = {"ollama", "lm_studio", "vllm", "koboldcpp", "oobabooga", "text-generation-webui", "hunyuan"}


def _resolve_model_config(
    requested_provider: Optional[str],
    requested_model: Optional[str],
    fallback_provider: Optional[str],
    fallback_model: Optional[str],
) -> tuple[str, Optional[str]]:
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


def _load_issues(sidecar_path: Path) -> List[Dict[str, Any]]:
    if not sidecar_path.exists():
        return []

    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to read embedded workshop sidecar %s: %s", sidecar_path, exc)
        return []

    issues = payload.get("issues", []) if isinstance(payload, dict) else payload if isinstance(payload, list) else []
    return [
        issue for issue in issues
        if isinstance(issue, dict) and str(issue.get("status", "detected")).lower() not in {"fixed", "ignored"}
    ]


def _chunked(items: List[Dict[str, Any]], size: int) -> List[List[Dict[str, Any]]]:
    size = max(1, size)
    return [items[index:index + size] for index in range(0, len(items), size)]


def _resolve_issue_target_path(output_root: Path, issue: Dict[str, Any]) -> Optional[Path]:
    file_path = issue.get("file_path")
    if file_path:
        candidate = Path(file_path)
        if candidate.exists():
            return candidate

    file_name = issue.get("file_name")
    if file_name:
        candidate = output_root / file_name
        if candidate.exists():
            return candidate
    return None


def _apply_translation_fix_to_file(file_path: Path, key_to_fix: str, new_value: str) -> bool:
    from scripts.core.loc_parser import parse_loc_file_with_lines

    try:
        entries = parse_loc_file_with_lines(file_path)
        target_line = -1
        for key, _value, line_number in entries:
            if key == key_to_fix or key.split(':')[0] == key_to_fix.split(':')[0]:
                target_line = line_number
                break

        if target_line == -1:
            return False

        index = target_line - 1
        with open(file_path, 'r', encoding='utf-8-sig') as handle:
            lines = handle.readlines()

        old_line = lines[index]
        first_quote = old_line.find('"')
        last_quote = old_line.rfind('"', first_quote + 1)
        if first_quote == -1 or last_quote == -1:
            return False

        safe_value = new_value.replace('"', r'\"')
        lines[index] = old_line[:first_quote + 1] + safe_value + old_line[last_quote:]
        with open(file_path, 'w', encoding='utf-8-sig') as handle:
            handle.writelines(lines)
        return True
    except Exception as exc:
        logger.error("Failed to apply embedded workshop fix to %s: %s", file_path, exc)
        return False


async def run_embedded_workshop(
    output_root: str | Path,
    source_root: str | Path,
    project_id: Optional[str],
    project_name: str,
    source_lang_info: Dict[str, Any],
    target_lang_info: Dict[str, Any],
    game_profile: Dict[str, Any],
    workflow: str,
    config: Optional[Dict[str, Any]] = None,
    fallback_provider: Optional[str] = None,
    fallback_model: Optional[str] = None,
) -> Dict[str, Any]:
    output_root = Path(output_root)
    sidecar_path = output_root / WorkshopIssueExportService.OUTPUT_FILENAME
    issues = _load_issues(sidecar_path)
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
            "issues_path": str(sidecar_path),
        }

    config = dict(config or {})
    provider_name, model_name = _resolve_model_config(
        requested_provider=None if config.get("follow_primary_settings", True) else config.get("api_provider"),
        requested_model=None if config.get("follow_primary_settings", True) else config.get("api_model"),
        fallback_provider=fallback_provider,
        fallback_model=fallback_model,
    )

    batch_size = max(1, int(config.get("batch_size_limit") or (3 if provider_name in LOCAL_PROVIDERS else 10)))
    concurrency = max(1, int(config.get("concurrency_limit") or 1))
    rpm_limit = max(1, int(config.get("rpm_limit") or 40))
    dispatch_interval = 60.0 / rpm_limit

    handler = get_handler(provider_name, model_name=model_name)
    if not handler or not handler.client:
        raise RuntimeError(f"Embedded workshop could not initialize provider '{provider_name}'.")

    agent = ReflexionFixAgent(handler)
    batches = _chunked(issues, batch_size)
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
            batch_result = await agent.fix_batch_loop(batch, game_id=game_profile.get("id", ""))
            for item in batch_result.get("results", []):
                results.append(item)

    await asyncio.gather(*(worker(worker_id + 1) for worker_id in range(max(1, concurrency))))

    fixed_count = 0
    failed_count = 0
    for result in results:
        original_issue = next(
            (
                issue for issue in issues
                if issue.get("file_name") == result.get("file_name") and issue.get("key") == result.get("key")
            ),
            None,
        )
        if result.get("status") != "SUCCESS" or not original_issue:
            failed_count += 1
            continue

        target_path = _resolve_issue_target_path(output_root, original_issue)
        if target_path and _apply_translation_fix_to_file(target_path, result["key"], result.get("suggested_fix", "")):
            fixed_count += 1
        else:
            failed_count += 1

    exporter = WorkshopIssueExportService()
    refreshed_export = exporter.export_for_output(
        output_root=output_root,
        source_root=source_root,
        source_lang_info=source_lang_info,
        target_lang_info=target_lang_info,
        game_profile=game_profile,
        workflow=workflow,
        project_name=project_name,
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
        "issues_path": refreshed_export.get("issues_path"),
        "sidecar_path": refreshed_export.get("sidecar_path"),
    }
