from pathlib import Path

from scripts.core.services.context_research_external_context import (
    STEAM_WORKSHOP_DETAILS_URL,
    load_external_context,
    normalize_workshop_item_id,
    resolve_metadata_path,
)


def test_game_profiles_resolve_victoria_and_eu5_json_metadata(tmp_path: Path) -> None:
    for game_id in ("vic3", "eu5"):
        root = tmp_path / game_id
        metadata = root / ".metadata" / "metadata.json"
        metadata.parent.mkdir(parents=True)
        metadata.write_text(
            '{"name":"Demo Mod","short_description":"A safe summary","tags":["Translation"]}',
            encoding="utf-8",
        )

        assert resolve_metadata_path(root, game_id) == metadata
        context = load_external_context(root, game_id)
        assert context.metadata["name"] == "Demo Mod"
        assert context.metadata_source.status == "loaded"
        assert context.metadata_source.sha256


def test_descriptor_games_use_descriptor_mod_and_never_return_unbounded_text(tmp_path: Path) -> None:
    root = tmp_path / "stellaris"
    root.mkdir()
    descriptor = root / "descriptor.mod"
    descriptor.write_text(
        'name="Long Mod"\nremote_file_id="3538617386"\n' + 'path="' + ('x' * 5000) + '"\n',
        encoding="utf-8",
    )

    context = load_external_context(root, "stellaris")

    assert resolve_metadata_path(root, "stellaris") == descriptor
    assert context.metadata["remote_file_id"] == "3538617386"
    assert len(context.metadata["path"]) <= 1_200


def test_workshop_description_area_fetch_is_optional_and_read_only(tmp_path: Path) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, _limit):
            return (
                b'{"response":{"publishedfiledetails":[{"result":1,'
                b'"title":"Horizon Signal","description":"Public description",'
                b'"tags":[{"tag":"Story"}],"time_updated":123}]}}'
            )

    calls = []

    def opener(request, timeout):
        calls.append((request.full_url, request.method, timeout))
        return FakeResponse()

    context = load_external_context(
        tmp_path, "victoria3", "3538617386", workshop_opener=opener,
    )

    assert calls == [(STEAM_WORKSHOP_DETAILS_URL, "POST", 15)]
    assert context.workshop == {
        "publishedfileid": "3538617386",
        "title": "Horizon Signal",
        "description": "Public description",
        "tags": ["Story"],
        "time_updated": "123",
        "creator_app_id": "",
        "consumer_app_id": "",
    }
    assert context.workshop_source.status == "loaded"


def test_invalid_or_missing_workshop_id_is_explicit_gap() -> None:
    assert normalize_workshop_item_id("3538617386") == "3538617386"
    assert normalize_workshop_item_id("not-an-id") is None
    context = load_external_context(None, "vic3", "not-an-id")
    assert context.workshop == {}
    assert context.workshop_source.status == "rejected"
    assert context.workshop_source.error_code == "invalid_workshop_item_id"
