"""Application facade for Remis' lightweight, human-judged model arena."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import threading
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
import uuid

from scripts import app_settings
from scripts.core.api_handler import get_handler
from scripts.core.base_handler import BaseApiHandler
from scripts.core.parallel_types import BatchTask, FileTask
from scripts.core.glossary_manager import glossary_manager as global_glossary_manager
from scripts.core.repositories.model_arena_repository import ModelArenaRepository
from scripts.core.services.model_arena_execution_service import (
    ArenaContestant,
    ArenaExecutionConfig,
    ArenaSample,
    ModelArenaExecutionService,
)
from scripts.core.services.model_arena_export_service import build_model_arena_export
from scripts.core.services.model_arena_runtime import (
    build_handler_factory,
    safe_provider_snapshot,
)
from scripts.core.services.model_arena_sampling_service import ModelArenaSamplingService
from scripts.schemas.model_arena import CreateModelArenaRunRequest, ModelArenaVoteRequest


SYSTEM_INSTRUCTION = "You are a professional translator for game mods."
ALLOWED_REASON_CODES = {
    "faithful",
    "natural",
    "style",
    "concise",
    "terminology",
    "context",
}
ANONYMOUS_STATUSES = {"queued", "running", "voting", "partial_failed"}
_PROMPT_GLOSSARY_LOCK = threading.RLock()


class ModelArenaRunClaimError(RuntimeError):
    """Raised when another worker already owns an arena execution."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _language(code: str) -> dict[str, Any]:
    for language in app_settings.LANGUAGES.values():
        if language.get("code") == code:
            return dict(language)
    return {"code": code, "name": code, "name_en": code, "key": code}


def _count_glossary_matches(
    entries: Iterable[Mapping[str, Any]],
    samples: Iterable[Mapping[str, Any]],
    source_lang_code: str,
) -> int:
    selected_source_text = "\n".join(
        str(sample.get("source_text") or "") for sample in samples
    ).casefold()
    return sum(
        1
        for entry in entries
        if (
            term := str(
                (entry.get("translations") or {}).get(source_lang_code, "")
            ).strip().casefold()
        )
        and term in selected_source_text
    )


def _record_to_dict(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {
            field.name: _record_to_dict(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _record_to_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_record_to_dict(item) for item in value]
    return value


class _NeutralPromptBuilder:
    """Reuse the production prompt contract without provider-specific prefixes."""
    _build_custom_global_prompt_part = BaseApiHandler._build_custom_global_prompt_part
    _build_source_context_prompt = staticmethod(BaseApiHandler._build_source_context_prompt)
    _build_context_release_prompt = staticmethod(BaseApiHandler._build_context_release_prompt)
    def __init__(self) -> None:
        import logging

        self.logger = logging.getLogger("ModelArenaPromptBuilder")

    @staticmethod
    def _apply_model_prompt_adapter(prompt: str) -> str:
        return prompt

    def build(self, task: BatchTask) -> str:
        return BaseApiHandler._build_prompt(self, task)


class ModelArenaService:
    def __init__(
        self,
        *,
        repository: ModelArenaRepository,
        project_manager: Any,
        sampler: Optional[ModelArenaSamplingService] = None,
        executor: Optional[ModelArenaExecutionService] = None,
        handler_factory: Any = get_handler,
        glossary_manager: Any = None,
    ) -> None:
        self.repository = repository
        self.project_manager = project_manager
        self.sampler = sampler or ModelArenaSamplingService()
        self.executor = executor or ModelArenaExecutionService()
        self.handler_factory = handler_factory
        self.glossary_manager = glossary_manager

    async def _snapshot_translation_glossaries(
        self,
        *,
        project: Mapping[str, Any],
        request: CreateModelArenaRunRequest,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Freeze the default initial-translation glossary stack for one arena.

        Initial translation mounts the game's main glossary first and the
        project-bound glossary last, so project terms win conflicts. Arena runs
        must use the same ordering; otherwise the comparison silently measures
        a different translation setup.
        """

        if not request.use_project_glossaries or self.glossary_manager is None:
            return [], {"enabled": False, "entry_count": 0, "glossaries": []}

        game_id = str(project.get("game_id") or "").strip()
        if not game_id:
            raise ValueError(
                "The selected project has no game type; Remis cannot choose a glossary stack."
            )
        selected: list[dict[str, Any]] = []
        if hasattr(self.glossary_manager, "get_available_glossaries"):
            available = await self.glossary_manager.get_available_glossaries(game_id)
            main_glossary = next(
                (item for item in available if item.get("is_main")),
                None,
            )
            if main_glossary:
                selected.append(main_glossary)

        project_glossary = await self.glossary_manager.get_project_glossary(
            game_id,
            request.project_id,
            project.get("name"),
        )
        if project_glossary and project_glossary.get("glossary_id") not in {
            item.get("glossary_id") for item in selected
        }:
            selected.append(project_glossary)

        glossary_ids = [
            int(item["glossary_id"])
            for item in selected
            if item.get("glossary_id") is not None
        ]
        raw_entries = (
            await self.glossary_manager.get_entries_for_glossary_ids(glossary_ids)
            if glossary_ids
            else []
        )
        priority_by_id = {
            glossary_id: priority
            for priority, glossary_id in enumerate(glossary_ids)
        }
        entries = [
            {
                **entry,
                "_glossary_priority": priority_by_id.get(
                    int(entry.get("glossary_id") or -1),
                    -1,
                ),
            }
            for entry in raw_entries
        ]
        counts = Counter(
            int(entry["glossary_id"])
            for entry in entries
            if entry.get("glossary_id") is not None
        )
        snapshot_items = [
            {
                "glossary_id": int(item["glossary_id"]),
                "name": item.get("name") or str(item["glossary_id"]),
                "kind": "main" if item.get("is_main") else "project",
                "entry_count": counts.get(int(item["glossary_id"]), 0),
            }
            for item in selected
            if item.get("glossary_id") is not None
        ]
        return entries, {
            "enabled": bool(glossary_ids),
            "entry_count": len(entries),
            "glossaries": snapshot_items,
            "content_sha256": _sha256_json(entries) if entries else None,
        }

    async def create_run(
        self, request: CreateModelArenaRunRequest
    ) -> dict[str, Any]:
        project = await self.project_manager.get_project(request.project_id)
        if not project:
            raise KeyError("Project not found")
        game_id = str(project.get("game_id") or "").strip()
        if not game_id:
            raise ValueError(
                "The selected project has no game type; Remis cannot create an arena run."
            )
        source_root = os.path.abspath(project["source_path"])
        if not os.path.isdir(source_root):
            raise ValueError("Project source path is unavailable")
        unknown_providers = sorted(
            {
                selection.provider_id
                for selection in request.contestants
                if selection.provider_id not in app_settings.API_PROVIDERS
            }
        )
        if unknown_providers:
            raise ValueError(
                "Unknown model arena provider(s): "
                + ", ".join(unknown_providers)
                + ". Arena execution never substitutes another provider."
            )

        project_files = await self.project_manager.get_project_files(request.project_id)
        file_paths = [
            item["file_path"]
            for item in project_files
            if item.get("file_type") == "source"
            and Path(item.get("file_path", "")).suffix.lower() in {".yml", ".yaml", ".json"}
            and os.path.isfile(item.get("file_path", ""))
        ]
        glossary_entries, glossary_snapshot = (
            await self._snapshot_translation_glossaries(
                project=project,
                request=request,
            )
        )
        glossary_terms = [
            translations.get(project.get("source_language") or "en")
            for entry in glossary_entries
            for translations in [entry.get("translations") or {}]
            if translations.get(project.get("source_language") or "en")
        ]
        selected, eligible_count, seed = self.sampler.sample_project(
            source_root,
            sample_size=request.sample_size,
            seed=request.sample_seed,
            file_paths=file_paths or None,
            glossary_terms=glossary_terms,
        )
        run_id = str(uuid.uuid4())
        contestants: list[dict[str, Any]] = []
        for order, selection in enumerate(request.contestants):
            snapshot = safe_provider_snapshot(
                selection.provider_id, selection.model_id
            )
            contestant_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"remis:model-arena:{run_id}:{order}:{selection.provider_id}:{selection.model_id}",
                )
            )
            contestants.append(
                {
                    "contestant_id": contestant_id,
                    "provider_id": selection.provider_id,
                    "model_id": selection.model_id,
                    "execution_order": order,
                    "config_snapshot": snapshot,
                    "config_fingerprint": _sha256_json(snapshot),
                    "prompt_fingerprint": _sha256_json(
                        {
                            "game_id": game_id,
                            "source_lang_code": project.get("source_language", "en"),
                            "target_lang_code": request.target_lang_code,
                            "use_project_glossaries": request.use_project_glossaries,
                            "use_mod_context": request.use_mod_context,
                        }
                    ),
                    "status": "draft",
                }
            )
        samples = self.sampler.build_samples(
            run_id,
            selected,
            contestant_ids=[item["contestant_id"] for item in contestants],
            seed=seed,
        )
        glossary_snapshot["matched_entry_count"] = _count_glossary_matches(
            glossary_entries,
            samples,
            project.get("source_language") or "en",
        )
        settings = {
            "use_project_glossaries": request.use_project_glossaries,
            "use_mod_context": request.use_mod_context,
            "glossary_snapshot": glossary_snapshot,
            "glossary_entries": glossary_entries,
        }
        run = self.repository.create_run(
            {
                "run_id": run_id,
                "project_id": request.project_id,
                "project_name_snapshot": project.get("name") or request.project_id,
                "game_id": game_id,
                "source_lang_code": project.get("source_language") or "en",
                "target_lang_code": request.target_lang_code,
                "sample_seed": seed,
                "sampler_version": self.sampler.SAMPLER_VERSION,
                "sample_size": len(samples),
                "eligible_count": eligible_count,
                "status": "draft",
                "settings": settings,
            },
            contestants,
            samples,
        )
        self.repository.append_event(
            run_id,
            {
                "event_type": "draft_created",
                "metrics": {
                    "sample_size": len(samples),
                    "eligible_count": eligible_count,
                    "contestant_count": len(contestants),
                },
            },
        )
        return self.public_run(run)

    async def resample(self, run_id: str) -> dict[str, Any]:
        run = self._require_run(run_id)
        if run["status"] != "draft":
            raise ValueError("Only draft runs can be resampled")
        project_id = run.get("project_id")
        project = (
            await self.project_manager.get_project(project_id) if project_id else None
        )
        if not project:
            raise ValueError("The source project is unavailable")
        source_root = os.path.abspath(project["source_path"])
        project_files = await self.project_manager.get_project_files(project_id)
        file_paths = [
            item["file_path"]
            for item in project_files
            if item.get("file_type") == "source"
            and Path(item.get("file_path", "")).suffix.lower() in {".yml", ".yaml", ".json"}
            and os.path.isfile(item.get("file_path", ""))
        ]
        selected, eligible_count, seed = self.sampler.sample_project(
            source_root,
            sample_size=run["sample_size"],
            seed=self.sampler.generate_seed(),
            file_paths=file_paths or None,
            glossary_terms=[
                translations.get(run["source_lang_code"])
                for entry in (run.get("settings") or {}).get("glossary_entries", [])
                for translations in [entry.get("translations") or {}]
                if translations.get(run["source_lang_code"])
            ],
        )
        samples = self.sampler.build_samples(
            run_id,
            selected,
            contestant_ids=[item["contestant_id"] for item in run["contestants"]],
            seed=seed,
        )
        settings = dict(run.get("settings") or {})
        glossary_snapshot = dict(settings.get("glossary_snapshot") or {})
        glossary_snapshot["matched_entry_count"] = _count_glossary_matches(
            settings.get("glossary_entries") or [],
            samples,
            run["source_lang_code"],
        )
        settings["glossary_snapshot"] = glossary_snapshot
        self.repository.update_run(run_id, settings=settings)
        replaced = self.repository.replace_samples(
            run_id,
            samples,
            sample_seed=seed,
            eligible_count=eligible_count,
            sample_size=len(samples),
        )
        self.repository.append_event(
            run_id,
            {"event_type": "samples_replaced", "metrics": {"sample_size": len(samples)}},
        )
        return self.public_run(replaced)

    def prepare_start(
        self, run_id: str, *, idempotency_key: str, task_id: str
    ) -> dict[str, Any]:
        run = self._require_run(run_id)
        settings = dict(run.get("settings") or {})
        prior_key = settings.get("start_idempotency_key")
        if prior_key:
            if prior_key == idempotency_key:
                return {
                    "run_id": run_id,
                    "task_id": settings.get("task_id"),
                    "status": run["status"],
                    "idempotent_replay": True,
                }
            raise ValueError("This arena run has already been started")
        if run["status"] != "draft":
            raise ValueError("Only draft runs can be started")
        settings.update(
            {"start_idempotency_key": idempotency_key, "task_id": task_id}
        )
        claimed = self.repository.claim_run_transition(
            run_id,
            expected_statuses={"draft"},
            status="queued",
            settings=settings,
        )
        if claimed is None:
            latest = self._require_run(run_id)
            latest_settings = dict(latest.get("settings") or {})
            if latest_settings.get("start_idempotency_key") == idempotency_key:
                return {
                    "run_id": run_id,
                    "task_id": latest_settings.get("task_id"),
                    "status": latest["status"],
                    "idempotent_replay": True,
                }
            raise ValueError("This arena run has already been started")
        self.repository.append_event(run_id, {"event_type": "run_queued"})
        return {
            "run_id": run_id,
            "task_id": task_id,
            "status": "queued",
            "idempotent_replay": False,
        }

    def execute_run(self, run_id: str) -> dict[str, Any]:
        run = self.repository.claim_run_transition(
            run_id,
            expected_statuses={"queued"},
            status="running",
            started_at=_utc_now(),
        )
        if run is None:
            raise ModelArenaRunClaimError(
                "Arena run is not queued for execution"
            )
        self.repository.append_event(run_id, {"event_type": "execution_started"})
        return self._execute_bundle(
            run,
            run["contestants"],
            retry_subset=False,
            batch_ordinal=0,
        )

    def prepare_retry(
        self, run_id: str, *, idempotency_key: str, task_id: str
    ) -> dict[str, Any]:
        run = self._require_run(run_id)
        settings = dict(run.get("settings") or {})
        retries = dict(settings.get("retry_tasks") or {})
        if idempotency_key in retries:
            prior = retries[idempotency_key]
            return {
                "run_id": run_id,
                "task_id": prior["task_id"],
                "status": run["status"],
                "idempotent_replay": True,
            }
        if run["status"] not in {"failed", "partial_failed"}:
            raise ValueError("Only failed contestants can be retried")
        failed_ids = [
            item["contestant_id"]
            for item in run["contestants"]
            if item.get("status") == "failed"
        ]
        if not failed_ids:
            raise ValueError("This arena run has no failed contestants")
        retries[idempotency_key] = {
            "task_id": task_id,
            "contestant_ids": failed_ids,
        }
        settings["retry_tasks"] = retries
        settings["active_retry_key"] = idempotency_key
        claimed = self.repository.claim_run_transition(
            run_id,
            expected_statuses={"failed", "partial_failed"},
            status="queued",
            settings=settings,
        )
        if claimed is None:
            latest = self._require_run(run_id)
            latest_retries = dict(
                (latest.get("settings") or {}).get("retry_tasks") or {}
            )
            if idempotency_key in latest_retries:
                return {
                    "run_id": run_id,
                    "task_id": latest_retries[idempotency_key]["task_id"],
                    "status": latest["status"],
                    "idempotent_replay": True,
                }
            raise ValueError("This arena run already has a queued retry")
        self.repository.append_event(
            run_id,
            {
                "event_type": "retry_queued",
                "metrics": {"contestant_count": len(failed_ids)},
            },
        )
        return {
            "run_id": run_id,
            "task_id": task_id,
            "status": "queued",
            "idempotent_replay": False,
        }

    def execute_retry(self, run_id: str) -> dict[str, Any]:
        run = self.repository.claim_run_transition(
            run_id,
            expected_statuses={"queued"},
            status="running",
        )
        if run is None:
            raise ModelArenaRunClaimError("Arena retry is not queued")
        settings = dict(run.get("settings") or {})
        retry_key = settings.get("active_retry_key")
        retry = (settings.get("retry_tasks") or {}).get(retry_key, {})
        failed_ids = set(retry.get("contestant_ids") or [])
        contestants = [
            item for item in run["contestants"] if item["contestant_id"] in failed_ids
        ]
        if not contestants:
            raise ValueError("Arena retry has no frozen failed contestant subset")
        self.repository.append_event(
            run_id,
            {
                "event_type": "retry_started",
                "metrics": {"contestant_count": len(contestants)},
            },
        )
        batch_ordinal = 1 + max(
            [int(item.get("batch_ordinal") or 0) for item in run.get("requests", [])],
            default=0,
        )
        return self._execute_bundle(
            run,
            contestants,
            retry_subset=True,
            batch_ordinal=batch_ordinal,
        )

    def _execute_bundle(
        self,
        run: dict[str, Any],
        contestant_rows: list[dict[str, Any]],
        *,
        retry_subset: bool,
        batch_ordinal: int,
    ) -> dict[str, Any]:
        run_id = run["run_id"]

        samples = [
            ArenaSample(
                sample_id=item["sample_id"],
                entry_key=item["entry_key"],
                source_text=item["source_text"],
                line_number=item.get("line_number"),
            )
            for item in run["samples"]
        ]
        contestants = [
            ArenaContestant(
                contestant_id=item["contestant_id"],
                provider_name=item["provider_id"],
                model_id=item["model_id"],
                execution_order=item["execution_order"],
                system_instruction=item.get("config_snapshot", {}).get(
                    "system_instruction", SYSTEM_INSTRUCTION
                ),
                effective_parameters=item.get("config_snapshot", {}).get(
                    "parameters", {}
                ),
            )
            for item in contestant_rows
        ]
        snapshot_by_contestant_id = {
            item["contestant_id"]: dict(item.get("config_snapshot") or {})
            for item in contestant_rows
        }
        source_lang = _language(run["source_lang_code"])
        prompt_task = self._make_batch_task(
            run,
            type("_ArenaPromptContext", (), {"provider_name": "model_arena", "client": None})(),
            source_lang,
        )
        with _PROMPT_GLOSSARY_LOCK:
            previous_glossary = global_glossary_manager.in_memory_glossary
            global_glossary_manager.in_memory_glossary = {
                "entries": list((run.get("settings") or {}).get("glossary_entries") or [])
            }
            try:
                shared_prompt = _NeutralPromptBuilder().build(prompt_task)
            finally:
                global_glossary_manager.in_memory_glossary = previous_glossary
        execution_config = ArenaExecutionConfig(
            run_id=run_id,
            game_id=run["game_id"],
            source_lang=source_lang,
            target_lang_code=run["target_lang_code"],
            prompt_text=shared_prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            batch_ordinal=batch_ordinal,
        )

        result = self.executor.execute(
            config=execution_config,
            samples=samples,
            contestants=contestants,
            handler_factory=build_handler_factory(
                self.handler_factory,
                snapshot_by_contestant_id,
                shared_prompt,
            ),
            retry_subset=retry_subset,
        )
        self.repository.insert_requests(
            [_record_to_dict(item) for item in result.requests]
        )
        output_rows = []
        for item in result.outputs:
            row = _record_to_dict(item)
            row.pop("token_parity", None)
            row.pop("created_at", None)
            output_rows.append(row)
        self.repository.insert_outputs(output_rows)
        prior_contestants = {
            item["contestant_id"]: item for item in run.get("contestants", [])
        }
        for item in result.contestants:
            prior = prior_contestants.get(item.contestant_id, {})
            self.repository.update_contestant(
                item.contestant_id,
                status=item.status,
                request_count=(
                    int(prior.get("request_count") or 0) + item.request_count
                    if retry_subset
                    else item.request_count
                ),
                elapsed_ms=(
                    int(prior.get("elapsed_ms") or 0) + item.elapsed_ms
                    if retry_subset
                    else item.elapsed_ms
                ),
                failure_code=item.failure_code,
            )
        refreshed = self._require_run(run_id)
        all_statuses = [item.get("status") for item in refreshed["contestants"]]
        completed_count = all_statuses.count("completed")
        if completed_count == len(all_statuses):
            aggregate_status = "voting"
        elif completed_count:
            aggregate_status = "partial_failed"
        else:
            aggregate_status = "failed"
        self.repository.update_run(run_id, status=aggregate_status)
        self.repository.append_event(
            run_id,
            {
                "event_type": "retry_finished" if retry_subset else "execution_finished",
                "level": "error" if aggregate_status == "failed" else "info",
                "metrics": {
                    "status": aggregate_status,
                    "request_count": len(result.requests),
                    "output_count": len(result.outputs),
                },
            },
        )
        return self.public_run(self._require_run(run_id))

    def save_vote(
        self, run_id: str, sample_id: str, request: ModelArenaVoteRequest
    ) -> dict[str, Any]:
        run = self._require_run(run_id)
        if run["status"] not in {"voting", "partial_failed"}:
            raise ValueError("Votes are only accepted while judging is open")
        if sample_id not in {sample["sample_id"] for sample in run["samples"]}:
            raise KeyError("Sample not found in this run")
        reasons = list(dict.fromkeys(request.reason_codes))
        invalid = sorted(set(reasons) - ALLOWED_REASON_CODES)
        if invalid:
            raise ValueError(f"Unknown reason code: {invalid[0]}")
        note = (request.note or "").strip() or None
        if note and len(note) > 2000:
            raise ValueError("Vote note must be at most 2000 characters")
        vote = self.repository.upsert_vote(
            {
                "vote_id": str(uuid.uuid4()),
                "sample_id": sample_id,
                "verdict": request.verdict,
                "winner_output_id": request.winner_output_id,
                "reason_codes": reasons,
                "note": note,
            }
        )
        return vote

    def complete_run(self, run_id: str) -> dict[str, Any]:
        run = self._require_run(run_id)
        if run["status"] not in {"voting", "partial_failed"}:
            raise ValueError("Arena run is not open for judging")
        sample_ids = {sample["sample_id"] for sample in run["samples"]}
        voted_ids = {vote["sample_id"] for vote in run["votes"]}
        missing = len(sample_ids - voted_ids)
        if missing:
            raise ValueError(f"{missing} sample vote(s) are still required")
        completed = self.repository.claim_run_transition(
            run_id,
            expected_statuses={"voting", "partial_failed"},
            status="completed",
            completed_at=_utc_now(),
        )
        if completed is None:
            raise ValueError("Arena run is no longer open for judging")
        self.repository.append_event(
            run_id,
            {"event_type": "identities_revealed", "metrics": {"vote_count": len(voted_ids)}},
        )
        return self.public_run(self._require_run(run_id))

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self.public_run(self._require_run(run_id))

    def list_runs(self, **filters: Any) -> dict[str, Any]:
        result = self.repository.list_runs(**filters)
        return {
            "runs": [self.public_run(item) for item in result["runs"]],
            "total_count": result["total_count"],
        }

    def export_preview(
        self, run_id: str, *, mode: str = "evidence"
    ) -> dict[str, Any]:
        run = self._require_run(run_id)
        if run["status"] != "completed":
            raise ValueError("Complete and reveal the arena before exporting")
        bundle = dict(run)
        bundle["results"] = self._results(run)
        return build_model_arena_export(
            bundle, mode=mode, remis_version=app_settings.VERSION
        )

    def delete_run(self, run_id: str) -> bool:
        return self.repository.delete_run(run_id)

    def _require_run(self, run_id: str) -> dict[str, Any]:
        run = self.repository.get_run(run_id)
        if run is None:
            raise KeyError("Model arena run not found")
        return run

    def _make_batch_task(
        self, run: dict[str, Any], handler: Any, source_lang: dict[str, Any]
    ) -> BatchTask:
        game_profile = app_settings.GAME_PROFILES_BY_ID.get(run["game_id"])
        if not game_profile:
            game_profile = next(iter(app_settings.GAME_PROFILES.values()))
        target_lang = _language(run["target_lang_code"])
        settings = run.get("settings") or {}
        mod_context = (
            run["project_name_snapshot"] if settings.get("use_mod_context") else ""
        )
        file_task = FileTask(
            filename="model_arena.yml",
            root="",
            original_lines=[],
            texts_to_translate=[sample["source_text"] for sample in run["samples"]],
            key_map={},
            is_custom_loc=False,
            target_lang=target_lang,
            source_lang=source_lang,
            game_profile=dict(game_profile),
            mod_context=mod_context,
            provider_name=handler.provider_name,
            output_folder_name="",
            source_dir="",
            dest_dir="",
            client=handler.client,
            mod_name=run["project_name_snapshot"],
        )
        return BatchTask(
            file_task=file_task,
            batch_index=0,
            start_index=0,
            end_index=len(run["samples"]),
            texts=[sample["source_text"] for sample in run["samples"]],
        )

    def public_run(self, run: dict[str, Any]) -> dict[str, Any]:
        public = json.loads(json.dumps(run, ensure_ascii=False, default=str))
        public["request_batch_count"] = 1
        public["estimated_request_count"] = len(public.get("contestants") or [])
        if isinstance(public.get("settings"), dict):
            public["settings"] = {
                key: public["settings"].get(key)
                for key in (
                    "use_project_glossaries",
                    "use_mod_context",
                    "glossary_snapshot",
                )
                if key in public["settings"]
            }
        status = public.get("status")
        if status in ANONYMOUS_STATUSES:
            contestants = public.get("contestants", [])
            contestant_ids = [item["contestant_id"] for item in contestants]
            public["contestants"] = [
                {
                    "candidate_id": f"candidate-{index + 1}",
                    "status": item.get("status"),
                }
                for index, item in enumerate(contestants)
            ]
            sample_by_id = {
                item["sample_id"]: item for item in public.get("samples", [])
            }
            anonymous_outputs = []
            for output in public.get("outputs", []):
                sample = sample_by_id.get(output["sample_id"], {})
                permutation = sample.get("display_permutation") or contestant_ids
                try:
                    display_index = permutation.index(output["contestant_id"])
                except ValueError:
                    display_index = contestant_ids.index(output["contestant_id"])
                anonymous_outputs.append(
                    {
                        "output_id": output["output_id"],
                        "sample_id": output["sample_id"],
                        "candidate_id": f"candidate-{display_index + 1}",
                        "translated_text": output.get("translated_text"),
                        "parse_status": output.get("parse_status"),
                    }
                )
            public["outputs"] = anonymous_outputs
            public["requests"] = []
            public["events"] = [
                {
                    key: event.get(key)
                    for key in ("sequence", "timestamp", "level", "event_type", "failure_code")
                }
                for event in public.get("events", [])
            ]
        for sample in public.get("samples", []):
            sample.pop("entry_key", None)
            sample.pop("relative_file_path", None)
            sample.pop("line_number", None)
            sample.pop("display_permutation", None)
        if status == "completed":
            public["results"] = self._results(run)
        return public

    @staticmethod
    def _results(run: dict[str, Any]) -> dict[str, Any]:
        outputs = {item["output_id"]: item for item in run.get("outputs", [])}
        contestant_stats: dict[str, dict[str, Any]] = {}
        reasons: dict[str, Counter[str]] = defaultdict(Counter)
        for contestant in run.get("contestants", []):
            contestant_stats[contestant["contestant_id"]] = {
                "contestant_id": contestant["contestant_id"],
                "provider_id": contestant["provider_id"],
                "model_id": contestant["model_id"],
                "selected_count": 0,
                "preference_rate": 0.0,
                "reason_counts": {},
                "hard_error_count": 0,
                "affected_sample_count": 0,
                "request_count": contestant.get("request_count", 0),
                "elapsed_ms": contestant.get("elapsed_ms"),
                "failure_code": contestant.get("failure_code"),
            }
        decisive = 0
        tie_count = 0
        reject_all_count = 0
        unjudgeable_count = 0
        for vote in run.get("votes", []):
            verdict = vote["verdict"]
            if verdict == "winner":
                winner = outputs.get(vote.get("winner_output_id"))
                if winner and winner["contestant_id"] in contestant_stats:
                    contestant_id = winner["contestant_id"]
                    contestant_stats[contestant_id]["selected_count"] += 1
                    reasons[contestant_id].update(vote.get("reason_codes") or [])
                    decisive += 1
            elif verdict == "tie":
                tie_count += 1
            elif verdict == "reject_all":
                reject_all_count += 1
            elif verdict == "unjudgeable":
                unjudgeable_count += 1
        for output in run.get("outputs", []):
            stats = contestant_stats.get(output["contestant_id"])
            if not stats:
                continue
            hard_count = int(output.get("hard_error_count") or 0)
            stats["hard_error_count"] += hard_count
            stats["affected_sample_count"] += int(hard_count > 0)
        for contestant_id, stats in contestant_stats.items():
            stats["preference_rate"] = (
                round(stats["selected_count"] / decisive, 4) if decisive else 0.0
            )
            stats["reason_counts"] = dict(reasons[contestant_id])
        return {
            "contestants": list(contestant_stats.values()),
            "decisive_vote_count": decisive,
            "tie_count": tie_count,
            "reject_all_count": reject_all_count,
            "unjudgeable_count": unjudgeable_count,
        }
