from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from scripts.core.services.proofreading_service import ProofreadingConflictError, ProofreadingDataError
from scripts.web_server import app


client = TestClient(app)


def test_save_proofread_data_forwards_structure_patches():
    mock_service = MagicMock()
    mock_service.save_proofread_data = AsyncMock(return_value=True)

    with patch("scripts.routers.proofreading.proofreading_service", mock_service):
        response = client.post(
            "/api/proofread/save",
            json={
                "project_id": "project-1",
                "file_id": "file-1",
                "entries": [
                    {"key": "demo.key:0", "translation": "Edited translation"},
                ],
                "structure_patches": [
                    {
                        "entry_id": "structure-comment-1-2",
                        "line_start": 2,
                        "line_end": 3,
                        "content": " # Edited comment\n # Still a comment",
                    },
                ],
                "target_language": "zh-CN",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    mock_service.save_proofread_data.assert_awaited_once_with(
        "project-1",
        "file-1",
        [{"key": "demo.key:0", "translation": "Edited translation"}],
        [
            {
                "entry_id": "structure-comment-1-2",
                "line_start": 2,
                "line_end": 3,
                "content": " # Edited comment\n # Still a comment",
            },
        ],
        None,
    )


def test_save_proofread_data_defaults_missing_structure_patches_to_empty_list():
    mock_service = MagicMock()
    mock_service.save_proofread_data = AsyncMock(return_value=True)

    with patch("scripts.routers.proofreading.proofreading_service", mock_service):
        response = client.post(
            "/api/proofread/save",
            json={
                "project_id": "project-1",
                "file_id": "file-1",
                "entries": [
                    {"key": "demo.key:0", "translation": "Edited translation"},
                ],
            },
        )

    assert response.status_code == 200
    mock_service.save_proofread_data.assert_awaited_once_with(
        "project-1",
        "file-1",
        [{"key": "demo.key:0", "translation": "Edited translation"}],
        [],
        None,
    )


def test_save_proofread_data_returns_new_revision():
    mock_service = MagicMock()
    mock_service.save_proofread_data = AsyncMock(return_value={
        "status": "success",
        "document_revision": "revision-2",
    })

    with patch("scripts.routers.proofreading.proofreading_service", mock_service):
        response = client.post(
            "/api/proofread/save",
            json={
                "project_id": "project-1",
                "file_id": "file-1",
                "base_revision": "revision-1",
                "entries": [{"key": "demo.key:0", "translation": "Edited"}],
            },
        )

    assert response.status_code == 200
    assert response.json()["document_revision"] == "revision-2"
    mock_service.save_proofread_data.assert_awaited_once_with(
        "project-1",
        "file-1",
        [{"key": "demo.key:0", "translation": "Edited"}],
        [],
        "revision-1",
    )


def test_save_proofread_data_maps_revision_conflict_to_409():
    mock_service = MagicMock()
    mock_service.save_proofread_data = AsyncMock(
        side_effect=ProofreadingConflictError("Target changed")
    )

    with patch("scripts.routers.proofreading.proofreading_service", mock_service):
        response = client.post(
            "/api/proofread/save",
            json={
                "project_id": "project-1",
                "file_id": "file-1",
                "base_revision": "old",
                "entries": [],
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "proofreading_revision_conflict"


def test_get_proofread_data_maps_service_error_detail():
    mock_service = MagicMock()
    mock_service.get_proofread_data = AsyncMock(
        side_effect=ProofreadingDataError(
            "file_path_not_found",
            "Indexed file is missing.",
            status_code=404,
        )
    )

    with patch("scripts.routers.proofreading.proofreading_service", mock_service):
        response = client.get("/api/proofread/project-1/file-1")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "file_path_not_found",
            "message": "Indexed file is missing.",
        }
    }


def test_get_proofread_revision_returns_lightweight_revision():
    mock_service = MagicMock()
    mock_service.get_document_revision = AsyncMock(return_value={
        "document_revision": "revision-2",
    })

    with patch("scripts.routers.proofreading.proofreading_service", mock_service):
        response = client.get("/api/proofread/project-1/file-1/revision")

    assert response.status_code == 200
    assert response.json() == {"document_revision": "revision-2"}
    mock_service.get_document_revision.assert_awaited_once_with("project-1", "file-1")
