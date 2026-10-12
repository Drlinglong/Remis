from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from scripts.routers.validation import router


@pytest.mark.parametrize("content, expected", [
    ('l_english:\n broken:0 "unterminated\n', "unterminated_value"),
    ('l_english:\n good:0 "Good"\n broken:0 "unterminated\n', "unterminated_value"),
    ('l_english:\n good:0 "Good"\n broken:0 no quotes\n', "missing_opening_quote"),
    ('l_english:\n good:0 "Good"\n', None),
    ('l_english:\n # empty locale\n', None),
])
def test_validate_file_preserves_parse_diagnostics(tmp_path, content, expected):
    path = tmp_path / "demo_l_english.yml"
    path.write_text(content, encoding="utf-8-sig")
    before = path.read_bytes()
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post("/api/validate_file", json={
        "file_path": str(path), "game_id": "stellaris",
    })
    assert response.status_code == 200
    issues = response.json()["issues"]
    if expected:
        issue = next(issue for issue in issues if issue["code"] == expected)
        assert issue["is_valid"] is False
        assert issue["level"] == "error"
        assert issue["key"] == "broken:0"
        assert issue["line_number"] == content.count("\n")
    else:
        assert issues == []
    assert path.read_bytes() == before


def test_validate_file_missing_returns_404(tmp_path):
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post("/api/validate_file", json={
        "file_path": str(tmp_path / "missing.yml"), "game_id": "stellaris",
    })
    assert response.status_code == 404
