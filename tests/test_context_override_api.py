from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.core.repositories.context_override_repository import (
    ContextDraftNotFoundError,
    ContextKeyNotFoundError,
    ContextOwnershipError,
    ContextReleaseNotFoundError,
)
from scripts.routers import context as context_router
from scripts.schemas.context import (
    ContextDraft,
    ContextRelease,
    ContextReleaseMetadata,
    HumanOverride,
)


def _draft() -> ContextDraft:
    return ContextDraft(
        draft_id="draft-1",
        project_id="project-1",
        base_release_id="release-1",
        status="draft",
        created_at="2026-08-01T00:00:00+00:00",
        updated_at="2026-08-01T00:00:00+00:00",
        overrides=[
            HumanOverride(
                target_key="republic",
                value={"preferred_name": "共和国"},
                note="inherited",
            )
        ],
    )


def _release() -> ContextRelease:
    return ContextRelease(
        release_id="release-2",
        project_id="project-1",
        metadata=ContextReleaseMetadata(
            source_snapshot_hash="snapshot-1",
            schema_version="context-v1",
            prompt_version="prompt-v1",
            provider_id="local",
            model_id="model",
            created_at="2026-08-01T00:00:01+00:00",
            parent_release_id="release-1",
        ),
    )


class FakeOverrideService:
    def start_draft(self, project_id: str, base_release_id: str):
        if base_release_id == "missing":
            raise ContextReleaseNotFoundError("Context release not found")
        return _draft()

    def get_draft(self, project_id: str, draft_id: str):
        if project_id != "project-1":
            raise ContextOwnershipError("Context draft does not belong to this project")
        if draft_id == "missing":
            raise ContextDraftNotFoundError("Context draft not found")
        return _draft()

    def save_override(self, project_id, draft_id, context_key, value, note):
        if context_key == "missing":
            raise ContextKeyNotFoundError("Context key is not in the parent release")
        return _draft()

    def publish_draft(self, project_id: str, draft_id: str):
        if draft_id == "missing":
            raise ContextDraftNotFoundError("Context draft not found")
        return _release()


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr(context_router, "context_override_service", FakeOverrideService())
    app = FastAPI()
    app.include_router(context_router.router)
    return TestClient(app)


def test_context_override_routes_return_drafts_and_child_release(monkeypatch):
    client = _client(monkeypatch)

    started = client.post(
        "/api/context/projects/project-1/drafts",
        json={"base_release_id": "release-1"},
    )
    assert started.status_code == 201
    assert started.json()["overrides"][0]["target_key"] == "republic"

    fetched = client.get("/api/context/projects/project-1/drafts/draft-1")
    assert fetched.status_code == 200

    saved = client.put(
        "/api/context/projects/project-1/drafts/draft-1/overrides",
        json={
            "target_key": "republic",
            "value": {"summary": "Human-confirmed summary."},
            "note": "reviewed",
        },
    )
    assert saved.status_code == 200

    published = client.post(
        "/api/context/projects/project-1/drafts/draft-1/publish"
    )
    assert published.status_code == 200
    assert published.json()["metadata"]["parent_release_id"] == "release-1"


def test_context_override_routes_use_structured_ownership_and_not_found_errors(monkeypatch):
    client = _client(monkeypatch)

    wrong_project = client.get("/api/context/projects/project-2/drafts/draft-1")
    assert wrong_project.status_code == 404
    assert wrong_project.json()["detail"]["code"] == "context_ownership_not_found"

    missing_release = client.post(
        "/api/context/projects/project-1/drafts",
        json={"base_release_id": "missing"},
    )
    assert missing_release.status_code == 404
    assert missing_release.json()["detail"]["code"] == "context_release_not_found"

    missing_draft = client.post(
        "/api/context/projects/project-1/drafts/missing/publish"
    )
    assert missing_draft.status_code == 404
    assert missing_draft.json()["detail"]["code"] == "context_draft_not_found"

    missing_key = client.post(
        "/api/context/projects/project-1/drafts/draft-1/overrides",
        json={"context_key": "missing", "value": {"summary": "x"}},
    )
    assert missing_key.status_code == 422
    assert missing_key.json()["detail"]["code"] == "context_key_not_found"


def test_context_override_routes_bound_override_values_before_service(monkeypatch):
    client = _client(monkeypatch)

    too_long = client.post(
        "/api/context/projects/project-1/drafts/draft-1/overrides",
        json={"context_key": "republic", "value": {"summary": "x" * 1201}},
    )
    assert too_long.status_code == 422
    assert too_long.json()["detail"] == {
        "code": "context_override_invalid",
        "message": "Human override payload failed bounded validation",
        "retryable": False,
    }

    credential_field = client.post(
        "/api/context/projects/project-1/drafts/draft-1/overrides",
        json={"context_key": "republic", "value": {"api_key": "secret"}},
    )
    assert credential_field.status_code == 422
    assert "api_key" not in credential_field.text
    assert "secret" not in credential_field.text
