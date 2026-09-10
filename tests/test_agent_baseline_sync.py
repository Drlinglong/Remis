import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from scripts.routers import agent, agent_baseline as api


@pytest.fixture
def context(tmp_path, monkeypatch):
    path = tmp_path / "sample_l_english.yml"
    path.write_text('l_english:\n key:0 "Ricerca"\n untouched:0 "Altro"\n', encoding="utf-8-sig")
    request = api.BaselineSyncRequest(approved=True, file_name=path.name, keys=["key:0"],
                                    expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    job = {"project_id": "p", "execution_args": {"target_lang_codes": ["custom"]}}
    archive = Mock()
    archive.update_translations.return_value = 1
    monkeypatch.setattr(api, "archive_manager", archive)
    monkeypatch.setattr(api, "project_manager", SimpleNamespace(get_project=AsyncMock(return_value={"name": "Italian"})))
    monkeypatch.setattr(agent, "agent_registry", SimpleNamespace(get_job=lambda _: job, record_event=Mock()))
    monkeypatch.setattr(agent, "_export_candidate", lambda *args: (tmp_path.name, tmp_path))
    monkeypatch.setattr(api.task_state, "get_task", lambda _: {"status": "completed"})
    return tmp_path, request, archive


@pytest.mark.asyncio
async def test_sync_uses_custom_identity_and_only_reviewed_keys(context):
    root, request, archive = context
    result = await api.sync_reviewed_baseline("job", request)
    assert result["updated_entries"] == 1
    assert result["validation_refreshed"] is False
    archive.update_translations.assert_called_once_with(
        "Italian", str(root / request.file_name), [{"key": "key:0", "translation": "Ricerca"}],
        "custom", project_id="p",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value,code", [
    ("approved", False, "approval_required"),
    ("file_name", "../escape.yml", "invalid_output_file"),
    ("expected_sha256", "0" * 64, "output_revision_conflict"),
    ("keys", ["unknown:0"], "entry_not_found"),
])
async def test_rejects_unapproved_stale_or_unscoped_sync(context, field, value, code):
    _, request, archive = context
    request = request.model_copy(update={field: value})
    with pytest.raises(HTTPException) as caught:
        await api.sync_reviewed_baseline("job", request)
    assert caught.value.detail["code"] == code
    archive.update_translations.assert_not_called()
