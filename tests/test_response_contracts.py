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
