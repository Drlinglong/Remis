"""Collection workflow orchestration, shared by desktop and Agent routes."""
from __future__ import annotations

import asyncio
from pathlib import Path
import re
import shutil

from scripts.app_settings import APP_DATA_DIR
from scripts.core.agent_service import agent_registry
from scripts.core.services.translation_package_workflow import PackageWorkflowError
from .repository import CollectionRepository
from . import sources

repository = CollectionRepository()
# One application process serves both GUI and Agent clients. SQLite revision
# checks provide the additional cross-process edit boundary.
_locks: dict[str, asyncio.Lock] = {}


def lock_for(collection_id: str) -> asyncio.Lock:
    return _locks.setdefault(collection_id, asyncio.Lock())


async def get_collection(collection_id: str) -> dict:
    record = await asyncio.to_thread(repository.get, collection_id)
    if record is None:
        raise PackageWorkflowError(404, "collection_not_found", "Translation collection not found.")
    return record


async def list_collections() -> dict:
    return {"collections": await asyncio.to_thread(repository.list)}


async def create_collection(data: dict) -> dict:
    await sources.validate_members(data["game_id"], data)
    return await asyncio.to_thread(repository.create, data)


async def update_collection(collection_id: str, data: dict) -> dict:
    async with lock_for(collection_id):
        current = await get_collection(collection_id)
        changes = {key: data[key] for key in ("title", "description", "target_languages", "members")}
        await sources.validate_members(current["game_id"], changes)
        await sources.reject_source_publication({**current, **changes}, current["steam_id"])
        return await asyncio.to_thread(repository.replace, collection_id, data["expected_revision"], changes)


async def delete_collection(collection_id: str, revision: int) -> dict:
    async with lock_for(collection_id):
        await get_collection(collection_id)
        await asyncio.to_thread(repository.delete, collection_id, revision)
    return {"collection_id": collection_id, "deleted": True,
            "projects_deleted": False, "exports_deleted": False}


async def bind_publication(collection_id: str, data: dict) -> dict:
    if not data["approved"]:
        raise PackageWorkflowError(409, "approval_required", "Confirm the collection's publication identity before saving it.")
    from scripts.core.mars_pipeline.publication_identity import validate_steam_id
    steam_id = validate_steam_id(data["steam_id"]) if data["steam_id"] else ""
    async with lock_for(collection_id):
        collection = await get_collection(collection_id)
        await sources.reject_source_publication(collection, steam_id)
        return await asyncio.to_thread(repository.replace, collection_id, data["expected_revision"], {"steam_id": steam_id})


async def plan_export(collection_id: str) -> dict:
    from .packaging import inspect_collection
    collection = await get_collection(collection_id)
    inspection = await inspect_collection(collection)
    previous = collection.get("last_export")
    history = await asyncio.to_thread(repository.history, collection_id) if previous else []
    inspection["changes"] = _changes(collection, history[0] if history else None, inspection["members"])
    if not inspection["can_export"]:
        return {"collection_id": collection_id, "inspection": inspection, "plan_id": None,
                "requires_approval": False, "allowed_actions": ["edit_collection", "translate_members"]}
    plan = agent_registry.create_plan(project_id=None, kind="translation_collection", dry_run=False,
        execution_args={"collection_id": collection_id, "revision": collection["revision"],
                        "fingerprint": inspection["fingerprint"]}, inspection=inspection,
        summary="Export a local translation collection; does not translate, install or publish.")
    return {"collection_id": collection_id, "plan_id": plan["plan_id"], "inspection": inspection,
            "expires_at": plan["expires_at"], "requires_approval": True,
            "risk": {"may_use_paid_api": False, "writes_output": True, "overwrites_existing_output": False},
            "allowed_actions": ["approve_collection_export"]}


def _changes(collection: dict, previous: dict | None, inspected: list[dict]) -> dict:
    before = (previous or {}).get("snapshot", {})
    old = {member["project_id"]: member for member in before.get("members", [])}
    new = {member["project_id"]: member for member in collection["members"]}
    old_facts = {member["project_id"]: member for member in (previous or {}).get("members", [])}
    new_facts = {member["project_id"]: member for member in inspected}
    return {"added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()),
            "selection_changed": sorted(key for key in old.keys() & new.keys() if old[key] != new[key]),
            "content_changed": sorted(key for key in old_facts.keys() & new_facts.keys()
                                      if old_facts[key] != new_facts[key]),
            "previous_package_path": (previous or {}).get("package_path"),
            "previous_export_retained": bool(previous)}


def _consume(plan_id: str, approved: bool) -> dict:
    if not approved:
        raise PackageWorkflowError(409, "approval_required", "Approve the collection export preview first.")
    try:
        return agent_registry.consume_plan(plan_id, approved=True)
    except KeyError as exc:
        raise PackageWorkflowError(404, "plan_not_found", "Collection plan not found.") from exc
    except (TimeoutError, RuntimeError) as exc:
        raise PackageWorkflowError(409, "stale_plan", "Plan expired or was used; generate another preview.") from exc


async def _settle_worker(operation):
    """Finish a worker before acting on cancellation or its transaction result."""
    worker = asyncio.create_task(operation)
    cancellation = None
    while not worker.done():
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError as error:
            cancellation = error
        except Exception:
            break
    return worker, cancellation


async def export_collection(collection_id: str, plan_id: str, approved: bool) -> dict:
    from .packaging import build_collection
    async with lock_for(collection_id):
        collection = await get_collection(collection_id)
        plan = _consume(plan_id, approved)
        receipt_recorded = False
        try:
            args = plan["execution_args"]
            if plan["kind"] != "translation_collection" or args.get("collection_id") != collection_id:
                raise PackageWorkflowError(409, "wrong_plan", "Preview belongs to another workflow or collection.")
            if args["revision"] != collection["revision"]:
                raise PackageWorkflowError(409, "stale_plan", "Collection changed since preview; preview again.")
            if not re.fullmatch(r"[a-f0-9]{32}", collection_id):
                raise ValueError("Invalid persisted collection identity")
            destination = Path(APP_DATA_DIR) / "translation_collections" / collection_id / plan_id / collection["mod_id"]
            result = await build_collection(collection, destination, args["fingerprint"])
            worker, cancellation = await _settle_worker(
                asyncio.to_thread(repository.record_export, collection, plan_id, result)
            )
            try:
                receipt = worker.result()
            except Exception:
                # This newly generated package has not been acknowledged to any
                # caller. Roll it back if the receipt transaction fails, leaving
                # every older export intact and the same preview retryable.
                cleanup, cleanup_cancellation = await _settle_worker(
                    asyncio.to_thread(_rollback_unrecorded, destination, collection_id, plan_id)
                )
                cleanup.result()
                if cancellation or cleanup_cancellation:
                    raise cancellation or cleanup_cancellation
                raise
            receipt_recorded = True
            if cancellation:
                raise cancellation
        except BaseException:
            if not receipt_recorded:
                agent_registry.release_plan(plan_id)
            raise
    agent_registry.record_event("translation_collection_exported", collection_id=collection_id, plan_id=plan_id)
    return {**receipt, "allowed_actions": ["inspect_local_output"], "runtime_verified": False}


async def export_history(collection_id: str) -> dict:
    await get_collection(collection_id)
    return {"exports": await asyncio.to_thread(repository.history, collection_id)}


def _rollback_unrecorded(destination: Path, collection_id: str, plan_id: str) -> None:
    from .packaging import _is_reparse
    intended = (Path(APP_DATA_DIR) / "translation_collections" / collection_id / plan_id).absolute()
    resolved = destination.resolve()
    if resolved.parent != intended or destination.absolute() != resolved:
        raise OSError(f"Export receipt failed; retained unrecorded output at {destination}")
    for item in (destination, *destination.parents):
        if _is_reparse(item):
            raise OSError(f"Export receipt failed; retained redirected output at {destination}")
    if destination.is_dir():
        shutil.rmtree(destination)
