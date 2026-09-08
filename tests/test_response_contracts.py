import pytest
from fastapi import HTTPException

from scripts.routers.translation import start_translation
from scripts.web_server import app


def _response_schema(paths, path, method, status):
    return paths[path][method]["responses"][status]["content"][
        "application/json"
    ]["schema"]


def test_high_risk_router_response_contracts_are_published():
    schema = app.openapi()
    paths = schema["paths"]

    assert _response_schema(
        paths, "/api/translate/start", "post", "200"
    )["$ref"].endswith("/TranslationTaskResponse")
    assert _response_schema(
        paths, "/api/translate_v2", "post", "200"
    )["$ref"].endswith("/TranslationTaskResponse")
    assert _response_schema(
        paths, "/api/model-arena/runs", "post", "201"
    )["$ref"].endswith("/ModelArenaRunResponse")
    assert _response_schema(
        paths, "/api/model-arena/runs/{run_id}", "get", "200"
    )["$ref"].endswith("/ModelArenaRunResponse")
    assert _response_schema(
        paths, "/api/system/stats", "get", "200"
    )["$ref"].endswith("/SystemStatsResponse")
    assert _response_schema(
        paths, "/api/system/reset-db", "post", "200"
    )["$ref"].endswith("/SystemActionResponse")
    assert _response_schema(
        paths, "/api/system/reset-project-db", "post", "200"
    )["$ref"].endswith("/SystemActionResponse")
    assert _response_schema(
        paths, "/api/system/reset-demo-state", "post", "200"
    )["$ref"].endswith("/DemoResetResponse")


def test_zip_upload_is_marked_as_legacy_while_project_translation_is_current():
    paths = app.openapi()["paths"]

    assert paths["/api/translate"]["post"]["deprecated"] is True
    assert paths["/api/translate"]["post"]["summary"] == "Legacy ZIP upload translation"
    assert "not part of the current product flow" in paths["/api/translate"]["post"]["description"]
    assert paths["/api/translate/start"]["post"].get("deprecated") is not True


@pytest.mark.asyncio
async def test_archived_zip_upload_is_not_callable_in_the_desktop_product():
    with pytest.raises(HTTPException) as exc_info:
        await start_translation(None, None, "victoria3", "en", "zh-CN", "gemini", "")

    assert exc_info.value.status_code == 410
