from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.routers import context_tree_v2
from scripts.schemas.context_tree_v2 import (
    PrePublicationValidationResult,
    ReadTreeResponse,
    TreeDraft,
)


class _FakeRepository:
    def get_tree(self, project_id, tree_id, draft_id=None):
        return ReadTreeResponse(project_id=project_id, tree_id=tree_id, draft_id=draft_id)

    def get_latest_tree(self, project_id):
        return self.get_tree(project_id, "latest-tree")

    def get_release_tree(self, project_id, release_id):
        return self.get_tree(project_id, f"tree-for-{release_id}")

    def create_draft(self, project_id, tree_id):
        return TreeDraft(
            draft_id="draft-1",
            project_id=project_id,
            base_release_id=tree_id,
            tree_id=tree_id,
        )

    def get_draft(self, project_id, draft_id):
        return TreeDraft(
            draft_id=draft_id,
            project_id=project_id,
            base_release_id="tree-1",
        )

    def save_draft_operation(self, project_id, draft_id, operation):
        return TreeDraft(
            draft_id=draft_id,
            project_id=project_id,
            base_release_id="tree-1",
            operations=(operation,),
        )

    def validate_draft(self, project_id, draft_id, **_kwargs):
        return PrePublicationValidationResult(
            project_id=project_id,
            tree_id="tree-1",
            draft_id=draft_id,
            valid=True,
        )


def _client(monkeypatch):
    monkeypatch.setattr(context_tree_v2, "repository", _FakeRepository())
    app = FastAPI()
    app.include_router(context_tree_v2.router)
    return TestClient(app)


def test_tree_v2_read_and_draft_contract_endpoints(monkeypatch):
    client = _client(monkeypatch)

    assert client.get("/api/context/tree-v2/projects/project-1/trees/tree-1").status_code == 200
    assert client.get("/api/context/tree-v2/projects/project-1/latest").json()["tree_id"] == "latest-tree"
    assert client.get("/api/context/tree-v2/projects/project-1/releases/release-1").json()["tree_id"] == "tree-for-release-1"
    assert client.post("/api/context/tree-v2/projects/project-1/trees/tree-1/drafts").status_code == 201


def test_tree_v2_draft_edit_and_validation_endpoints(monkeypatch):
    client = _client(monkeypatch)

    operation = {
        "operation": "move_fragment",
        "fragment_id": "fragment-1",
        "target_group_id": "group-2",
    }
    response = client.post(
        "/api/context/tree-v2/projects/project-1/drafts/draft-1/operations",
        json=operation,
    )
    assert response.status_code == 200
    assert response.json()["operations"][0]["operation"] == "move_fragment"

    validation = client.post(
        "/api/context/tree-v2/projects/project-1/drafts/draft-1/validate",
        json={
            "project_id": "project-1",
            "tree_id": "tree-1",
            "draft_id": "draft-1",
        },
    )
    assert validation.status_code == 200
    assert validation.json()["valid"] is True
