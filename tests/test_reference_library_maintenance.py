import threading
import time

import pytest

from scripts.core.services import reference_library_service as service_module
from scripts.core.services.reference_library_service import ReferenceLibraryService
from scripts.shared import task_state


def _wait_for_terminal(task_id: str) -> dict:
    for _ in range(100):
        task = task_state.get_task(task_id)
        if task and task.get("status") in task_state.TERMINAL_TASK_STATUSES:
            return task
        time.sleep(0.01)
    pytest.fail(f"task {task_id} did not reach a terminal state")


def test_second_reference_build_returns_the_existing_task(monkeypatch):
    service = ReferenceLibraryService(reference_service=object())
    started = threading.Event()
    release = threading.Event()

    def hold_worker(task_id, operation, candidates):
        started.set()
        release.wait(timeout=2)
        task_state.update_task(task_id, status="completed")

    monkeypatch.setattr(service, "_run_task", hold_worker)
    first = service.build("victoria3", "I:/game/localization")
    assert started.wait(timeout=1)

    second = service.build("ck3", "I:/game/localization")
    assert second["already_running"] is True
    assert second["task_id"] == first["task_id"]

    release.set()
    assert _wait_for_terminal(first["task_id"])["status"] == "completed"


def test_maintenance_persists_per_game_file_and_entry_progress(monkeypatch):
    class FakeReferenceService:
        pass

    service = ReferenceLibraryService(reference_service=FakeReferenceService())
    published = []
    original_publish = service._publish_progress

    def record_progress(task_id, games, *, stage):
        published.append((stage, games[0].get("files_current"), games[0].get("entries_current")))
        original_publish(task_id, games, stage=stage)

    monkeypatch.setattr(service, "_publish_progress", record_progress)

    def fake_build(game_id, path, *, progress_callback=None):
        progress_callback({"stage": "indexing", "files_current": 1, "files_total": 2, "entries_current": 4})
        progress_callback({"stage": "indexing", "files_current": 2, "files_total": 2, "entries_current": 8})
        return {"library": {"game_id": game_id, "entry_count": 8}}

    monkeypatch.setattr(service, "_build_sync", fake_build)
    result = service._start_task(
        operation="build",
        candidates=[{"game_id": "victoria3", "game_name": "Victoria 3", "localization_path": "I:/v3"}],
    )
    task = _wait_for_terminal(result["task_id"])

    assert task["status"] == "completed"
    game = task["progress"]["games"][0]
    assert game["files_current"] == 2
    assert game["files_total"] == 2
    assert game["entries_current"] == 8
    assert game["entries_total"] == 8
    assert ("indexing", 1, 4) in published
    assert ("indexing", 2, 8) in published


def test_partial_reference_maintenance_is_not_reported_as_success(monkeypatch):
    service = ReferenceLibraryService(reference_service=object())
    candidates = [
        {"game_id": "victoria3", "localization_path": "I:/v3"},
        {"game_id": "ck3", "localization_path": "I:/ck3"},
    ]

    def fake_build(game_id, path, *, progress_callback=None):
        if game_id == "victoria3":
            raise OSError("unreadable localization file")
        return {"library": {"game_id": game_id, "entry_count": 2}}

    monkeypatch.setattr(service, "_build_sync", fake_build)
    result = service._start_task(operation="build", candidates=candidates)
    task = _wait_for_terminal(result["task_id"])

    assert task["status"] == "partial_failed"
    assert task["result"]["errors"][0]["game_id"] == "victoria3"
    assert task["result"]["results"][0]["library"]["game_id"] == "ck3"


def test_delete_reports_failed_compaction_instead_of_hiding_it():
    class FakeReferenceService:
        @staticmethod
        def delete_game_reference(_game_id):
            return {
                "reference_sets_deleted": 1,
                "entries_deleted": 5,
                "database_compacted": False,
            }

    service = ReferenceLibraryService(reference_service=FakeReferenceService())
    result = service._start_task(
        operation="delete",
        candidates=[{
            "game_id": "victoria3",
            "game_name": "Victoria 3",
            "localization_path": "I:/v3",
            "entries_total": 5,
        }],
    )
    task = _wait_for_terminal(result["task_id"])

    assert task["status"] == "failed"
    assert "could not reclaim" in task["result"]["errors"][0]["error"]


def test_discover_does_not_start_a_maintenance_task(monkeypatch):
    candidates = [{"game_id": "victoria3", "localization_path": "I:/v3"}]
    monkeypatch.setattr(service_module, "discover_paradox_localizations", lambda *_args: candidates)
    service = ReferenceLibraryService(reference_service=object())

    assert service.discover() == {"status": "success", "candidates": candidates}
