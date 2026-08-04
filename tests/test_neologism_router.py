from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from scripts.routers import neologism as neologism_router
from scripts.schemas.context import ContextRelease, ContextReleaseMetadata
from scripts.schemas.context_analysis_preview import (
    ContextAnalysisPreview,
    ContextAnalysisPreviewEntry,
    ContextAnalysisPreviewRun,
)
from scripts.web_server import app


client = TestClient(app)


def test_latest_context_release_includes_model_facing_prompt_example(monkeypatch):
    release = ContextRelease(
        release_id="release-1",
        project_id="project-1",
        metadata=ContextReleaseMetadata(
            source_snapshot_hash="snapshot-1",
            analysis_scope={"mode": "narrative_context"},
            schema_version="context-v1",
            prompt_version="context-synthesis-v4",
            provider_id="local",
            model_id="model-1",
            analysis_config={"description_language": "zh-CN"},
        ),
    )
    monkeypatch.setattr(
        neologism_router.context_repository,
        "list_releases",
        lambda project_id: [release] if project_id == "project-1" else [],
    )

    response = client.get("/api/context/releases/project-1/latest")

    assert response.status_code == 200
    metadata = response.json()["metadata"]
    assert "Simplified Chinese (zh-CN)" in metadata["prompt_example"]
    assert "System message:" in metadata["prompt_example"]
    assert "User message:" in metadata["prompt_example"]


def test_unpublished_context_analysis_preview_is_read_only_and_explicit(monkeypatch):
    preview = ContextAnalysisPreview(
        project_id="project-1",
        run=ContextAnalysisPreviewRun(
            run_id="run-1",
            project_id="project-1",
            status="failed",
            phase="synthesis",
            publication_status="not_published",
            source_snapshot_hash="snapshot-1",
            provider_id="openrouter",
            model_id="openai/gpt-5.6-luna",
            created_at="2026-08-04T00:00:00Z",
            updated_at="2026-08-04T01:00:00Z",
        ),
        counts={"entities": 1, "events": 1},
        entries=[
            ContextAnalysisPreviewEntry(
                aggregate_id="entity-1",
                aggregate_key="entity:toxic god",
                aggregate_type="entity",
                label="Toxic God",
                payload={"tier": "core"},
                summary="A toxic entity.",
            ),
        ],
    )
    monkeypatch.setattr(
        neologism_router.context_analysis_preview_service,
        "latest",
        lambda project_id: preview if project_id == "project-1" else None,
    )

    response = client.get("/api/context/projects/project-1/analysis-preview")

    assert response.status_code == 200
    assert response.json()["published"] is False
    assert response.json()["warning_code"] == "unpublished_analysis_preview"
    assert response.json()["entries"][0]["label"] == "Toxic God"


def test_unpublished_context_analysis_preview_returns_not_found(monkeypatch):
    monkeypatch.setattr(
        neologism_router.context_analysis_preview_service,
        "latest",
        lambda project_id: None,
    )

    response = client.get("/api/context/projects/missing/analysis-preview")

    assert response.status_code == 404

    optional_response = client.get(
        "/api/context/projects/missing/analysis-preview?optional=true"
    )
    assert optional_response.status_code == 200
    assert optional_response.json() == {"preview": None}


@pytest.mark.parametrize(
    ("source_language", "target_language"),
    [
        ("zh-CN", "zh-CN"),
        ("simp_chinese", "zh-CN"),
        ("english", "en"),
    ],
)
def test_mining_rejects_project_source_language_as_target(
    monkeypatch,
    source_language,
    target_language,
):
    monkeypatch.setattr(
        neologism_router.project_manager,
        "get_project",
        AsyncMock(return_value={
            "project_id": "project-1",
            "name": "Demo",
            "game_id": "victoria3",
            "source_language": source_language,
        }),
    )

    response = client.post("/api/neologisms/mine", json={
        "project_id": "project-1",
        "api_provider": "unused-because-validation-runs-first",
        "target_lang": target_language,
    })

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Target language must be different from the project source language."
    )
