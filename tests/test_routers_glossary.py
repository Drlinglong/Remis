import pytest
from fastapi.testclient import TestClient
from scripts.web_server import app
from scripts.routers.glossary import (
    _transform_entry_to_storage_format,
    _transform_storage_to_frontend_format,
)

client = TestClient(app)

def test_get_glossaries():
    # Assuming 'stellaris' is a valid game_id
    response = client.get("/api/glossaries/stellaris")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_search_glossary():
    response = client.post("/api/glossary/search", json={
        "query": "Empire",
        "scope": "game",
        "game_id": "stellaris"
    })
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "entries" in data
    assert isinstance(data["entries"], list)


def test_frontend_source_prefers_canonical_source_text_metadata():
    entry = _transform_storage_to_frontend_format({
        "entry_id": "term-1",
        "translations": {"zh-CN": "泰尔紫"},
        "raw_metadata": {
            "source_text": "泰尔紫 (Tyrian Purple)",
            "source_lang": "zh-CN",
            "target_lang": "zh-CN",
        },
    })

    assert entry["source"] == "泰尔紫 (Tyrian Purple)"


def test_storage_keeps_same_language_source_separate_from_translation():
    entry = _transform_entry_to_storage_format({
        "id": "term-1",
        "source": "泰尔紫 (Tyrian Purple)",
        "translations": {"zh-CN": "泰尔紫"},
        "metadata": {
            "source_lang": "zh-CN",
            "target_lang": "zh-CN",
        },
    })

    assert entry["translations"] == {"zh-CN": "泰尔紫"}
    assert entry["metadata"]["source_text"] == "泰尔紫 (Tyrian Purple)"
