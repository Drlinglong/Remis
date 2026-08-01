from __future__ import annotations

from fastapi.testclient import TestClient

from scripts.core.services.agent_context_service import AgentContextService
from scripts.routers import agent_context as agent_context_router
from scripts.schemas.context import ContextRelease, ContextReleaseMetadata, EffectiveContext


def _release() -> ContextRelease:
    return ContextRelease(
        release_id="release-1",
        project_id="project-1",
        metadata=ContextReleaseMetadata(
            source_snapshot_hash="snapshot-1",
            analysis_scope={
                "mode": "narrative_context",
                "files": ["localization/events.yml", "C:/private/secret.yml"],
            },
            schema_version="context-v1",
            prompt_version="context-synthesis-v1",
            provider_id="lm_studio",
            model_id="local-model",
            analysis_config={
                "description_language": "zh-CN",
                "source_items": [
                    {"relative_path": "localization/events.yml"},
                    {"relative_path": "C:/private/secret.yml"},
                ]
            },
        ),
    )


class FakeRepository:
    def __init__(self, release: ContextRelease):
        self.release = release

    def list_releases(self, project_id: str):
        return [self.release] if project_id == self.release.project_id else []

    def get_release(self, release_id: str):
        return self.release if release_id == self.release.release_id else None


class FakeContextService:
    def __init__(self, release: ContextRelease):
        self.release = release
        self.trace_rows = [
            {
                "aggregate": {
                    "aggregate_id": "aggregate-1",
                    "aggregate_type": "entity",
                    "aggregate_key": "entity:remis",
                    "payload": {"active_contribution_count": 1, "api_key": "never-return"},
                },
                "contributions": [
                    {
                        "contribution": {
                            "contribution_id": "contribution-1",
                            "source_item_id": "source-1",
                            "contribution_type": "mention",
                            "subject_key": "entity:remis",
                            "provenance": "text_inferred",
                            "payload": {
                                "original": "Remis",
                                "source_file": "C:/private/events.yml",
                                "nested": {"token": "never-return", "safe": "yes"},
                            },
                        },
                        "source_item": {
                            "source_item_id": "source-1",
                            "source_type": "localization",
                            "source_ref": "localization/events.yml::0:remis_name",
                            "content": "Remis enters the Meridian Gate.",
                            "content_hash": "content-hash-1",
                            "created_at": "2026-08-01T00:00:00+00:00",
                            "metadata": {"source_path": "C:/private/events.yml"},
                        },
                    }
                ],
                "syntheses": [
                    {
                        "synthesis_id": "synthesis-1",
                        "context_key": "context.remis",
                        "content": {
                            "summary": "Remis is tied to the Meridian Gate.",
                            "path": "C:/private/events.yml",
                            "secret": "never-return",
                        },
                    }
                ],
            }
        ]

    def effective_context(self, release_id: str):
        if release_id != self.release.release_id:
            return None
        return EffectiveContext(
            release=self.release,
            generated_synthesis={
                "context.remis": {"summary": "Generated summary."}
            },
            human_overrides={
                "context.remis": {
                    "summary": "Human-confirmed summary.",
                    "api_key": "never-return",
                    "path": "C:/private/events.yml",
                }
            },
            effective_context={
                "context.remis": {
                    "summary": "Human-confirmed summary.",
                    "api_key": "never-return",
                    "path": "C:/private/events.yml",
                }
            },
        )

    def traceability(self, release_id: str):
        return self.trace_rows if release_id == self.release.release_id else []


def _service() -> AgentContextService:
    release = _release()
    return AgentContextService(
        FakeRepository(release),
        context_service=FakeContextService(release),
    )


def test_agent_context_service_projects_published_metadata_without_internal_paths():
    response = _service().latest_release("project-1")

    assert response is not None
    assert response.release_id == "release-1"
    assert response.source_refs == ["localization/events.yml"]
    assert response.analysis_scope == {
        "mode": "narrative_context",
        "source_file_count": 1,
    }
    assert response.description_language == "zh-CN"
    assert "analysis_config" not in response.model_dump()
    assert "private" not in response.model_dump_json()


def test_agent_context_effective_and_traceability_are_selected_and_bounded():
    service = _service()

    effective = service.effective_context("release-1")
    assert effective is not None
    assert effective.effective_context["context.remis"] == {
        "summary": "Human-confirmed summary."
    }

    trace = service.traceability(
        "release-1",
        aggregate_key="entity:remis",
        context_key="context.remis",
    )
    assert trace is not None
    assert len(trace.traceability) == 1
    item = trace.traceability[0]
    assert item.aggregate.aggregate_key == "entity:remis"
    assert item.syntheses[0].context_key == "context.remis"
    assert item.source_evidence[0].source_ref == "localization/events.yml::0:remis_name"
    assert item.source_evidence[0].content_excerpt == "Remis enters the Meridian Gate."
    assert "never-return" not in trace.model_dump_json()
    assert "C:/private" not in trace.model_dump_json()


def test_agent_context_routes_have_structured_selection_errors(monkeypatch):
    from scripts.web_server import app

    monkeypatch.setattr(agent_context_router, "agent_context_service", _service())
    client = TestClient(app)

    response = client.get(
        "/api/agent/context/releases/release-1/traceability"
    )
    assert response.status_code == 400
    assert response.json() == {
        "detail": {
            "code": "context_selection_required",
            "message": "Select an aggregate_key or context_key",
            "retryable": False,
        }
    }

    latest = client.get("/api/agent/context/releases/project-1/latest")
    assert latest.status_code == 200
    assert latest.json()["release_id"] == "release-1"
    assert latest.json()["allowed_actions"] == [
        "read_effective_context",
        "read_context_traceability",
    ]

    effective = client.get("/api/agent/context/releases/release-1/effective")
    assert effective.status_code == 200
    assert effective.json()["human_overrides"]["context.remis"] == {
        "summary": "Human-confirmed summary."
    }

    trace = client.get(
        "/api/agent/context/releases/release-1/traceability",
        params={"context_key": "context.remis"},
    )
    assert trace.status_code == 200
    assert trace.json()["selection"] == {
        "aggregate_key": None,
        "context_key": "context.remis",
    }


def test_agent_context_capabilities_are_read_only_and_do_not_claim_execution():
    import asyncio

    from scripts.routers import agent as agent_router

    capabilities = asyncio.run(agent_router.get_capabilities())
    assert capabilities["actions"]["read_context_release"]["requires_approval"] is False
    assert capabilities["actions"]["read_context_release"]["read_only"] is True
    assert capabilities["actions"]["context_analysis"]["supported"] is False
    assert capabilities["actions"]["context_analysis"]["requires_approval"] is True
