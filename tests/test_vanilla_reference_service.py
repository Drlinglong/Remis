from pathlib import Path

import pytest

from scripts.core.services.vanilla_reference_service import (
    VanillaReferenceService,
    normalize_reference_key,
)
from scripts.core.services.reference_reuse_preview_service import ReferenceReusePreviewService
from scripts.core.services.vanilla_reference_version import detect_reference_game_version


def _write_loc(root: Path, language: str, header: str, filename: str, rows: str) -> None:
    path = root / language / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{header}:\n{rows}", encoding="utf-8-sig")


def _build_root(tmp_path: Path) -> Path:
    root = tmp_path / "Victoria 3" / "game" / "localization"
    _write_loc(
        root,
        "english",
        "l_english",
        "countries_l_english.yml",
        ' TRK:0 "Turkana"\n SRB:0 "Sorbs"\n QUOTE:0 "The \\\"Dawn\\\""\n',
    )
    _write_loc(
        root,
        "simp_chinese",
        "l_simp_chinese",
        "countries_l_simp_chinese.yml",
        ' TRK:0 "图尔卡纳"\n SRB:0 "索布"\n QUOTE:0 "《黎明》"\n',
    )
    return root


def test_normalize_reference_key_removes_only_numeric_revision():
    assert normalize_reference_key("TRK:0") == "TRK"
    assert normalize_reference_key(" event:key ") == "event:key"


def test_detect_reference_game_version_uses_matching_steam_manifest(tmp_path):
    root = tmp_path / "SteamLibrary" / "steamapps" / "common" / "Victoria 3" / "game" / "localization"
    root.mkdir(parents=True)
    (tmp_path / "SteamLibrary" / "steamapps" / "appmanifest_529340.acf").write_text(
        '"AppState"\n{\n "appid" "529340"\n "installdir" "Victoria 3"\n "buildid" "24799966"\n}\n',
        encoding="utf-8",
    )

    assert detect_reference_game_version(root) == "steam-build-24799966"


def test_exact_key_and_canonical_source_hit_skips_api(tmp_path):
    root = _build_root(tmp_path)
    service = VanillaReferenceService(tmp_path / "reference.sqlite")
    resolver = service.open_resolver(
        game_id="victoria3",
        localization_root=root,
        source_lang_code="en",
        target_lang_code="zh-CN",
        supported_language_keys=["1", "2"],
    )

    hit = resolver.lookup("TRK:0", "Turkana")
    redefined = resolver.lookup("TRK:0", "Turkey")
    quote_hit = resolver.lookup("QUOTE:0", 'The "Dawn"')

    assert hit.hit is True
    assert hit.translation == "图尔卡纳"
    assert redefined.status == "source_mismatch"
    assert quote_hit.translation == "《黎明》"
    assert resolver.metrics()["reference_matched"] == 2
    assert resolver.metrics()["api_skipped"] == 2


def test_duplicate_key_in_another_file_keeps_source_rows_independent(tmp_path):
    root = _build_root(tmp_path)
    _write_loc(
        root,
        "english",
        "l_english",
        "duplicate_l_english.yml",
        ' TRK:0 "Turkey"\n EN_ONLY:0 "English only"\n',
    )
    service = VanillaReferenceService(tmp_path / "reference.sqlite")
    resolver = service.open_resolver(
        game_id="victoria3",
        localization_root=root,
        source_lang_code="en",
        target_lang_code="zh-CN",
        supported_language_keys=["1", "2"],
    )

    assert resolver.lookup("TRK", "Turkana").translation == "图尔卡纳"
    assert resolver.lookup("TRK", "Turkey").status == "missing_target"
    assert resolver.lookup("EN_ONLY", "English only").status == "missing_target"
    assert resolver.metrics()["missing_targets"] == 2


def test_conflicting_duplicate_inside_the_same_vanilla_file_is_a_miss(tmp_path):
    root = _build_root(tmp_path)
    source_file = root / "english" / "countries_l_english.yml"
    source_file.write_text(
        source_file.read_text(encoding="utf-8-sig") + ' TRK:0 "Turkey"\n',
        encoding="utf-8-sig",
    )
    resolver = VanillaReferenceService(tmp_path / "reference.sqlite").open_resolver(
        game_id="victoria3",
        localization_root=root,
        source_lang_code="en",
        target_lang_code="zh-CN",
        supported_language_keys=["1", "2"],
    )

    assert resolver.lookup("TRK", "Turkana").status == "conflict"
    assert resolver.lookup("TRK", "Turkey").status == "conflict"


def test_unchanged_file_stats_reuse_the_cached_reference_set(tmp_path):
    root = _build_root(tmp_path)
    service = VanillaReferenceService(tmp_path / "reference.sqlite")
    first = service.open_resolver(
        game_id="victoria3",
        localization_root=root,
        source_lang_code="en",
        target_lang_code="zh-CN",
        supported_language_keys=["1", "2"],
    )
    second = service.open_resolver(
        game_id="victoria3",
        localization_root=root,
        source_lang_code="en",
        target_lang_code="zh-CN",
        supported_language_keys=["1", "2"],
    )

    assert second.info.reference_set_id == first.info.reference_set_id
    assert second.info.content_fingerprint == first.info.content_fingerprint


def test_active_index_opens_without_rescanning_source_tree(tmp_path, monkeypatch):
    root = _build_root(tmp_path)
    service = VanillaReferenceService(tmp_path / "reference.sqlite")
    built = service.build_index(
        game_id="victoria3",
        localization_root=root,
        supported_language_keys=["1", "2"],
    )
    monkeypatch.setattr(
        service,
        "_collect_language_files",
        lambda *_args, **_kwargs: pytest.fail("active lookup rescanned the source tree"),
    )

    resolver = service.open_active_resolver(
        game_id="victoria3",
        source_lang_code="en",
        target_lang_code="zh-CN",
    )

    assert resolver is not None
    assert resolver.info.reference_set_id == built.reference_set_id
    assert resolver.lookup("TRK:0", "Turkana").translation == "图尔卡纳"


def test_delete_game_reference_removes_binding_sets_and_entries_atomically(tmp_path):
    root = _build_root(tmp_path)
    service = VanillaReferenceService(tmp_path / "reference.sqlite")
    first = service.build_index(
        game_id="victoria3",
        localization_root=root,
        supported_language_keys=["1", "2"],
    )

    result = service.delete_game_reference("victoria3")

    assert result["reference_sets_deleted"] == 1
    assert result["entries_deleted"] > 0
    assert service.get_active_index("victoria3") is None
    assert service.count_entries(first.reference_set_id) == 0


def test_force_rebuild_repairs_same_fingerprint_index(tmp_path):
    root = _build_root(tmp_path)
    service = VanillaReferenceService(tmp_path / "reference.sqlite")
    first = service.build_index(
        game_id="victoria3",
        localization_root=root,
        supported_language_keys=["1", "2"],
    )
    original_count = service.count_entries(first.reference_set_id)
    with service._connect() as connection:
        connection.execute(
            """
            DELETE FROM reference_entries_v2
            WHERE rowid = (
                SELECT rowid FROM reference_entries_v2
                WHERE reference_set_id = ? LIMIT 1
            )
            """,
            (first.reference_set_id,),
        )
    assert service.count_entries(first.reference_set_id) == original_count - 1

    rebuilt = service.build_index(
        game_id="victoria3",
        localization_root=root,
        supported_language_keys=["1", "2"],
        force_rebuild=True,
        allow_stale_fallback=False,
    )

    assert service.count_entries(rebuilt.reference_set_id) == original_count
    assert service.get_active_index("victoria3").reference_set_id == rebuilt.reference_set_id


def test_game_version_is_stored_and_part_of_the_index_identity(tmp_path):
    root = _build_root(tmp_path)
    launcher_path = root.parent / "launcher-settings.json"
    launcher_path.write_text('{"rawVersion":"1.9.8"}', encoding="utf-8")
    service = VanillaReferenceService(tmp_path / "reference.sqlite")

    first = service.open_resolver(
        game_id="victoria3",
        localization_root=root,
        source_lang_code="en",
        target_lang_code="zh-CN",
        supported_language_keys=["1", "2"],
    )
    launcher_path.write_text('{"rawVersion":"1.9.9"}', encoding="utf-8")
    second = service.open_resolver(
        game_id="victoria3",
        localization_root=root,
        source_lang_code="en",
        target_lang_code="zh-CN",
        supported_language_keys=["1", "2"],
    )

    assert first.info.game_version == "1.9.8"
    assert second.info.game_version == "1.9.9"
    assert second.info.reference_set_id != first.info.reference_set_id


def test_failed_rebuild_warns_via_stale_metrics_but_keeps_exact_lookup(tmp_path, monkeypatch):
    root = _build_root(tmp_path)
    service = VanillaReferenceService(tmp_path / "reference.sqlite")
    service.open_resolver(
        game_id="victoria3",
        localization_root=root,
        source_lang_code="en",
        target_lang_code="zh-CN",
        supported_language_keys=["1", "2"],
    )
    target_file = root / "simp_chinese" / "countries_l_simp_chinese.yml"
    target_file.write_text(
        'l_simp_chinese:\n TRK:0 "图尔卡纳"\n SRB:0 "索布"\n QUOTE:0 "《黎明》"\n\n',
        encoding="utf-8-sig",
    )

    def fail_rebuild(**_kwargs):
        raise OSError("simulated rebuild failure")

    monkeypatch.setattr(service, "_build_reference_set", fail_rebuild)
    resolver = service.open_resolver(
        game_id="victoria3",
        localization_root=root,
        source_lang_code="en",
        target_lang_code="zh-CN",
        supported_language_keys=["1", "2"],
    )

    assert resolver.lookup("TRK:0", "Turkana").translation == "图尔卡纳"
    assert resolver.metrics()["reference_stale"] is True
    assert resolver.metrics()["stale_reference_hits"] == 1


def test_explicitly_deselected_hit_returns_to_model_path(tmp_path):
    root = _build_root(tmp_path)
    service = VanillaReferenceService(tmp_path / "reference.sqlite")
    resolver = service.open_resolver(
        game_id="victoria3",
        localization_root=root,
        source_lang_code="en",
        target_lang_code="zh-CN",
        supported_language_keys=["1", "2"],
        excluded_entries=[{
            "file_path": "localization/english/countries_l_english.yml",
            "key": "TRK:0",
            "source_text": "Turkana",
            "target_lang_code": "zh-CN",
        }],
    )

    result = resolver.lookup(
        "TRK:0",
        "Turkana",
        "localization/english/countries_l_english.yml",
    )

    assert result.status == "deselected"
    assert resolver.metrics()["reference_deselected"] == 1
    assert resolver.metrics()["api_skipped"] == 0


def test_preview_lists_only_exact_source_matches(tmp_path):
    vanilla_root = _build_root(tmp_path)
    source_root = tmp_path / "source_mod"
    _write_loc(
        source_root / "localization",
        "english",
        "l_english",
        "demo_l_english.yml",
        ' TRK:0 "Turkana"\n TRK_CUSTOM:0 "Turkana"\n',
    )
    reference_service = VanillaReferenceService(tmp_path / "preview.sqlite")

    def resolver_factory(config, *, game_profile, source_lang, target_lang):
        return reference_service.open_resolver(
            game_id=game_profile["id"],
            localization_root=config["localization_path"],
            source_lang_code=source_lang["code"],
            target_lang_code=target_lang["code"],
            supported_language_keys=game_profile["supported_language_keys"],
        )

    result = ReferenceReusePreviewService(resolver_factory).preview(
        source_path=str(source_root),
        game_profile={"id": "victoria3", "supported_language_keys": ["1", "2"]},
        source_lang={"code": "en", "key": "l_english", "name_en": "English"},
        target_languages=[{"code": "zh-CN", "key": "l_simp_chinese"}],
        localization_path=str(vanilla_root),
    )

    assert result["matched_count"] == 1
    assert result["matches"][0]["key"] == "TRK:0"
    assert result["matches"][0]["target_text"] == "图尔卡纳"


def test_preview_surfaces_invalid_reference_path(tmp_path):
    with pytest.raises((OSError, ValueError)):
        ReferenceReusePreviewService().preview(
            source_path=str(tmp_path),
            game_profile={"id": "victoria3", "supported_language_keys": ["1", "2"]},
            source_lang={"code": "en", "key": "l_english", "name_en": "English"},
            target_languages=[{"code": "zh-CN", "key": "l_simp_chinese"}],
            localization_path=str(tmp_path / "missing-localization"),
        )
