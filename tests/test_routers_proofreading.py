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


def test_agent_get_proofread_alias_reuses_existing_service():
    mock_service = MagicMock()
    mock_service.get_proofread_data = AsyncMock(return_value={"entries": []})

    with patch("scripts.routers.proofreading.proofreading_service", mock_service):
        response = client.get("/api/agent/proofread/project-1/file-1")

    assert response.status_code == 200
    assert response.json() == {"entries": []}
    mock_service.get_proofread_data.assert_awaited_once_with("project-1", "file-1")


def test_agent_save_requires_explicit_approval_and_nonblank_revision():
    mock_service = MagicMock()
    mock_service.save_proofread_data = AsyncMock(return_value=True)
    base = {
        "project_id": "project-1",
        "file_id": "file-1",
        "entries": [],
        "approved": True,
        "base_revision": "revision-1",
    }

    with patch("scripts.routers.proofreading.proofreading_service", mock_service):
        missing_approval = client.post(
            "/api/agent/proofread/save",
            json={key: value for key, value in base.items() if key != "approved"},
        )
        denied = client.post("/api/agent/proofread/save", json={**base, "approved": False})
        missing_revision = client.post(
            "/api/agent/proofread/save",
            json={key: value for key, value in base.items() if key != "base_revision"},
        )
        empty_revision = client.post("/api/agent/proofread/save", json={**base, "base_revision": ""})
        blank_revision = client.post("/api/agent/proofread/save", json={**base, "base_revision": "   "})

    assert [response.status_code for response in (
        missing_approval, denied, missing_revision, empty_revision, blank_revision,
    )] == [422, 422, 422, 422, 422]
    mock_service.save_proofread_data.assert_not_awaited()


def test_agent_save_forwards_approved_revision_and_maps_conflict():
    mock_service = MagicMock()
    mock_service.save_proofread_data = AsyncMock(
        side_effect=ProofreadingConflictError("Target changed")
    )
    mock_service.project_manager.get_project_files = AsyncMock(return_value=[{
        "file_id": "file-1", "file_type": "translation",
    }])

    with patch("scripts.routers.proofreading.proofreading_service", mock_service):
        response = client.post(
            "/api/agent/proofread/save",
            json={
                "project_id": "project-1",
                "file_id": "file-1",
                "entries": [{"key": "demo.key:0", "translation": "Edited"}],
                "approved": True,
                "base_revision": "revision-1",
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "proofreading_revision_conflict"
    mock_service.save_proofread_data.assert_awaited_once_with(
        "project-1", "file-1", [{"key": "demo.key:0", "translation": "Edited"}], [], "revision-1",
    )


def test_agent_save_rejects_source_file_without_calling_service():
    mock_service = MagicMock()
    mock_service.save_proofread_data = AsyncMock(return_value=True)
    mock_service.project_manager.get_project_files = AsyncMock(return_value=[{
        "file_id": "file-source", "file_type": "source",
    }])

    with patch("scripts.routers.proofreading.proofreading_service", mock_service):
        response = client.post(
            "/api/agent/proofread/save",
            json={
                "project_id": "project-1", "file_id": "file-source", "entries": [],
                "approved": True, "base_revision": "revision-1",
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "proofreading_target_not_translation"
    mock_service.save_proofread_data.assert_not_awaited()


def test_agent_save_rejects_file_missing_from_requested_project():
    mock_service = MagicMock()
    mock_service.save_proofread_data = AsyncMock(return_value=True)
    mock_service.project_manager.get_project_files = AsyncMock(return_value=[])

    with patch("scripts.routers.proofreading.proofreading_service", mock_service):
        response = client.post(
            "/api/agent/proofread/save",
            json={
                "project_id": "project-other", "file_id": "file-1", "entries": [],
                "approved": True, "base_revision": "revision-1",
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "proofreading_translation_not_found"
    mock_service.save_proofread_data.assert_not_awaited()
