"""Synthetic filesystem tests for Surviving Mars delivery generation."""

import csv
import hashlib
from pathlib import Path

import pytest

from scripts.core.mars_pipeline.delivery_metadata import _source_copy_mod_id

from scripts.core.mars_pipeline.delivery import (
    MarsDeliveryError,
    build_delivery,
    inspect_delivery,
)
from scripts.core.mars_pipeline.prepare_source import analyze_source
from scripts.core import surviving_mars_csv


def _publication(mod_id="synthetic42", steam_id="3807689989", revision=1):
    return {"status": "bound" if steam_id else "unbound", "steam_id": steam_id,
            "revision": revision, "source_mod_id": mod_id,
            "output_mod_id": _source_copy_mod_id(mod_id)}


def test_bound_source_copy_restores_only_own_top_level_workshop_id(tmp_path):
    from scripts.core.mars_pipeline.publication_identity import read_source_workshop_id

    source = _source(tmp_path / "source")
    manifest, translations = _prepared(source)
    destination = tmp_path / "output"
    result = build_delivery(source, manifest, translations, destination, "source_copy",
                            publication_binding=_publication())
    assert read_source_workshop_id(destination) == "3807689989"
    metadata = (destination / "metadata.lua").read_text(encoding="utf-8")
    assert "3679917456" not in metadata and "136945" not in metadata
    assert "'steam_id', 123" in metadata
    assert read_source_workshop_id(source) == "3679917456"
    assert result["publication_binding"] == _publication()


def test_binding_created_after_preview_invalidates_unbound_export(tmp_path):
    source = _source(tmp_path / "source")
    manifest, translations = _prepared(source)
    preview = inspect_delivery(source, manifest, translations, "source_copy",
                               publication_binding=_publication(steam_id=None, revision=0))
    with pytest.raises(MarsDeliveryError, match="changed"):
        build_delivery(source, manifest, translations, tmp_path / "output", "source_copy",
                       expected_fingerprint=preview["fingerprint"], publication_binding=_publication())
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("binding", [
    _publication(mod_id="other-mod"), _publication(steam_id="0"),
    _publication(steam_id="18446744073709551616"),
    {**_publication(), "status": "unbound"},
])
def test_invalid_publication_binding_cannot_fall_back_to_new_item(tmp_path, binding):
    source = _source(tmp_path / "source")
    manifest, translations = _prepared(source)
    with pytest.raises(ValueError, match="[Pp]ublication binding"):
        build_delivery(source, manifest, translations, tmp_path / "output", "source_copy",
                       publication_binding=binding)
    assert not (tmp_path / "output").exists()


def _source(root: Path, *, mod_id: str = "synthetic42") -> Path:
    root.mkdir(parents=True)
    (root / "metadata.lua").write_text(
        "return PlaceObj('ModDef', {\n"
        f"  'title', \"Synthetic\",\n  'id', \"{mod_id}\",\n"
        f"  'image', \"Mod/{mod_id}/Images/icon.png\",\n"
        f"  'description', \"Keep {mod_id}-suffix unchanged\",\n"
        "  'steam_id', '3679917456',\n  'pdx_id', 136945,\n"
        "  'dependencies', { PlaceObj('ModDependency', { 'id', \"dependency-id\", 'steam_id', 123, }), },\n"
        "  'lua_revision', 350453,\n})\n",
        encoding="utf-8", newline="",
    )
    (root / "items.lua").write_text(
        "return {\n  PlaceObj('ModItemCode', { 'CodeFileName', \"Code/Text.lua\" }),\n}\n",
        encoding="utf-8", newline="",
    )
    (root / "Code").mkdir()
    (root / "Code" / "Text.lua").write_text(
        'local LABEL = Untranslated("Synthetic title")\n'
        '-- synthetic42 comment stays unchanged\n'
        'local EXISTING = T(123456, "Existing <em>text</em>")\n'
        'local DESC = Untranslated("Line one\\n\\nLine two <em>safe</em>")\n',
        encoding="utf-8", newline="",
    )
    with (root / "ModTexts.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\r\n")
        writer.writerow(["sep=", ""])
        writer.writerow(surviving_mars_csv.HEADER)
        writer.writerow(["123456", "Existing <em>text</em>", "", "", "existing T row"])
    return root


def _prepared(root: Path) -> tuple[dict, dict[str, dict[str, str]]]:
    manifest = analyze_source(root)
    manifest["approved_ids"] = sorted(manifest["entries"], key=int)
    translations = {
        code: {
            key: ("译文 " + row["text"] if code == "zh-CN" else "Texte " + row["text"])
            for key, row in manifest["entries"].items()
        }
        for code in ("zh-CN", "fr")
    }
    return manifest, translations


def test_source_copy_uses_distinct_identity_rewrites_only_copy_and_registers_languages(tmp_path):
    source = _source(tmp_path / "source")
    manifest, translations = _prepared(source)
    original = {path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in source.rglob("*") if path.is_file()}
    preview = inspect_delivery(source, manifest, translations, "source_copy")
    destination = tmp_path / "delivery"

    result = build_delivery(source, manifest, translations, destination, "source_copy",
                            expected_fingerprint=preview["fingerprint"])

    assert preview["status"] == "ready"
    assert result["runtime_verified"] is False
    assert result["file_count"] == preview["file_count"]
    output_mod_id = result["manifest_receipt"]["mod_id"]
    assert output_mod_id != "synthetic42"
    assert output_mod_id.startswith("Remis")
    rewritten = (destination / "Code" / "Text.lua").read_text(encoding="utf-8")
    assert "Untranslated(" not in rewritten
    assert "T(" in rewritten
    metadata = (destination / "metadata.lua").read_text(encoding="utf-8")
    assert f"'id', \"{output_mod_id}\"" in metadata
    assert "[Remis i18n] Synthetic" in metadata
    assert f"Mod/{output_mod_id}/Images/icon.png" in metadata
    assert "Keep synthetic42-suffix unchanged" in metadata
    assert "'pdx_id'" not in metadata
    assert "'3679917456'" not in metadata
    assert metadata.count("'steam_id'") == 1
    assert "'steam_id', 123" in metadata
    assert "synthetic42 comment stays unchanged" in rewritten
    assert "'loctables'" in metadata
    assert "Localization/Schinese/ModTexts.csv" in metadata
    assert "Localization/French/RemisLua.csv" in metadata
    items = (destination / "items.lua").read_text(encoding="utf-8")
    assert "Code/Text.lua" in items
    assert "ModItemLocTable" in items
    assert f"Mod/{output_mod_id}/Localization/Schinese/ModTexts.csv" in items
    for language, expected in (("Schinese", "译文"), ("French", "Texte")):
        path = destination / "Localization" / language / "RemisLua.csv"
        document = surviving_mars_csv.parse_file(path)
        assert len(document.entries) == 2
        assert all(expected in row[2] for row in document.rows[document.header_row_index + 1:] if row)
    assert {
        path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source.rglob("*") if path.is_file()
    } == original


def test_source_copy_requires_explicit_approved_id_snapshot(tmp_path):
    source = _source(tmp_path / "source")
    manifest = analyze_source(source)
    manifest.pop("approved_ids", None)
    translations = {"zh-CN": {key: row["text"] for key, row in manifest["entries"].items()}}
    preview = inspect_delivery(source, manifest, translations, "source_copy")
    assert preview["status"] == "blocked"
    assert "approved_ids" in preview["blockers"][0]["reason"]


def test_text_only_emits_three_files_for_one_language_and_warns_about_hardcoded_text(tmp_path):
    source = _source(tmp_path / "source")
    manifest, translations = _prepared(source)
    existing_ids = [key for key, row in manifest["entries"].items() if row["kind"] == "existing_t"]
    assert existing_ids == ["123456"]
    translations = {"zh-CN": {"123456": "现有 <em>文本</em>"}}

    preview = inspect_delivery(source, manifest, translations, "text_only")
    destination = tmp_path / "text-only"
    result = build_delivery(source, manifest, translations, destination, "text_only",
                            expected_fingerprint=preview["fingerprint"])

    assert preview["status"] == "ready"
    assert preview["file_count"] == 3
    assert preview["uncovered_entry_count"] == len(manifest["entries"]) - 1
    assert "hardcoded Lua text remains English" in " ".join(preview["installation_steps"])
    assert result["manifest_receipt"]["localized_ids"] == ["123456"]
    assert not (destination / "Code").exists()
    assert (destination / "items.lua").exists()
    assert (destination / "metadata.lua").exists()
    metadata = (destination / "metadata.lua").read_text(encoding="utf-8")
    assert "RemisText" in metadata and "synthetic42" in metadata
    assert "ModDependency" in metadata and "'required', true" in metadata
    assert "ModItemCode" not in (destination / "items.lua").read_text(encoding="utf-8")
    csv_file = destination / "Localization" / "Schinese" / "RemisLua.csv"
    localized = surviving_mars_csv.parse_file(csv_file)
    assert [row.key for row in localized.entries] == ["123456"]


def test_source_copy_accepts_source_without_any_localization_csv(tmp_path):
    source = _source(tmp_path / "source")
    (source / "ModTexts.csv").unlink()
    manifest, translations = _prepared(source)

    preview = inspect_delivery(source, manifest, translations, "source_copy")

    assert preview["status"] == "ready"
    assert preview["file_count"] > 3
    assert preview["excluded_source_csv_ids"] == []
    assert any(item["path"] == "Localization/Schinese/RemisLua.csv" for item in preview["files"])


@pytest.mark.parametrize("mode", ["source_copy", "text_only"])
def test_three_languages_are_registered_in_one_mod_package(tmp_path, mode):
    source = _source(tmp_path / "source")
    manifest, translations = _prepared(source)
    translations["de"] = {key: "Deutsch " + entry["text"]
                          for key, entry in manifest["entries"].items()}
    destination = tmp_path / "one-multilingual-mod"
    result = build_delivery(source, manifest, translations, destination, mode)
    assert len(list(destination.rglob("metadata.lua"))) == 1
    items = (destination / "items.lua").read_text(encoding="utf-8")
    metadata = (destination / "metadata.lua").read_text(encoding="utf-8")
    expected_ids = {key for key, entry in manifest["entries"].items()
                    if mode == "source_copy" or entry["kind"] == "existing_t"}
    for code, language in (("zh-CN", "Schinese"), ("fr", "French"), ("de", "German")):
        tables = list((destination / "Localization" / language).glob("*.csv"))
        assert tables
        values = {entry.key: entry.value for table in tables
                  for entry in surviving_mars_csv.entries(table, "Translation")}
        assert set(values) == expected_ids
        assert values == {key: translations[code][key] for key in expected_ids}
        for table in tables:
            virtual = f"Mod/{result['output_mod_id']}/{table.relative_to(destination).as_posix()}"
            assert virtual in items and virtual in metadata


def test_overlay_is_profile_guarded_and_unsupported_entries_are_blockers(tmp_path):
    source = _source(tmp_path / "source", mod_id="kz4dEz")
    manifest, translations = _prepared(source)
    from scripts.core.mars_pipeline.overlay import OverlayProfileError
    with pytest.raises((MarsDeliveryError, OverlayProfileError)):
        inspect_delivery(source, manifest, translations, "overlay")


def test_overlay_profile_emits_idempotent_stable_id_only_patch_and_flags_uncovered(tmp_path):
    from scripts.core.mars_pipeline.overlay import PROFILE_MOD_ID, TECH_LABEL, UPGRADE_PROFILE

    source = _source(tmp_path / "source", mod_id=PROFILE_MOD_ID)
    entries = {}
    for upgrade_id, (path, _name) in UPGRADE_PROFILE.items():
        source_path = source.joinpath(*path.split("/"))
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(f'local UPGRADE_ID = "{upgrade_id}"\n', encoding="utf-8")
    label_path, label_text = TECH_LABEL
    label_source = source.joinpath(*label_path.split("/"))
    label_source.parent.mkdir(parents=True, exist_ok=True)
    label_source.write_text('local LABEL_ID = "ExoticsApplications"\n', encoding="utf-8")
    manifest = analyze_source(source)
    for index, (upgrade_id, (path, name)) in enumerate(UPGRADE_PROFILE.items(), start=100):
        key = str(index)
        entries[key] = {"id": key, "text": name, "kind": "literal", "review_required": False,
                        "refs": [{"path": path, "line": 1}]}
    for key in ("200", "201"):
        entries[key] = {"id": key, "text": label_text, "kind": "literal", "review_required": False,
                        "refs": [{"path": label_path, "line": 1}]}
    manifest["entries"] = entries
    translations = {"zh-CN": {key: "译文 " + row["text"] for key, row in entries.items()}}

    preview = inspect_delivery(source, manifest, translations, "overlay")

    assert preview["status"] == "ready"
    assert preview["output_mod_id"].startswith("RemisLua")
    overlay = (preview["files"])
    assert "blockers" in preview and preview["blockers"] == []
    # The generated bridge is exercised as inert source; this test never executes Lua.
    from scripts.core.mars_pipeline.overlay import compile_overlay
    compiled = compile_overlay(manifest, PROFILE_MOD_ID, source)
    assert "OnMsg.PostLoadGame" in compiled["lua"]
    assert "BuildingTemplates" in compiled["lua"] and "g_Classes" in compiled["lua"]
    assert "Untranslated =" not in compiled["lua"]
    assert 'prefix .. "id"' in compiled["lua"]
    assert len(compiled["supported_ids"]) == 10
    assert overlay


def test_stale_source_snapshot_and_existing_destination_are_rejected(tmp_path):
    source = _source(tmp_path / "source")
    manifest, translations = _prepared(source)
    (source / "Code" / "Text.lua").write_text("-- changed\n", encoding="utf-8")
    with pytest.raises(MarsDeliveryError, match="changed after localization preparation"):
        inspect_delivery(source, manifest, translations, "source_copy")

    source = _source(tmp_path / "source2")
    manifest, translations = _prepared(source)
    destination = tmp_path / "existing"
    destination.mkdir()
    with pytest.raises(FileExistsError):
        build_delivery(source, manifest, translations, destination, "source_copy")


def _synthetic_png(width=256, height=256):
    header = bytearray(24)
    header[:8] = b"\x89PNG\r\n\x1a\n"
    header[8:12] = (13).to_bytes(4, "big")
    header[12:16] = b"IHDR"
    header[16:20] = width.to_bytes(4, "big")
    header[20:24] = height.to_bytes(4, "big")
    return bytes(header)


def _synthetic_jpeg(width=256, height=256):
    frame = b"\xff\xc0\x00\x0b\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big")
    frame += b"\x01\x01\x11\x00"
    return b"\xff\xd8" + frame + b"\xff\xda\x00\x02\xff\xd9"


def test_source_copy_metadata_overrides_add_reviewed_cover_and_preserve_author_source(tmp_path):
    source = _source(tmp_path / "source")
    metadata_path = source / "metadata.lua"
    original_metadata = metadata_path.read_bytes().replace(
        b"  'title', \"Synthetic\",",
        b"  'author', \"Original Author\",\n  'title', \"Synthetic\",",
    )
    metadata_path.write_bytes(original_metadata)
    manifest, translations = _prepared(source)
    cover = tmp_path / "cover.png"
    cover_bytes = _synthetic_png()
    cover.write_bytes(cover_bytes)
    cover_hash = hashlib.sha256(cover_bytes).hexdigest()
    overrides = {
        "title": "[中/法/德] 奇异矿物扩展 | Exotic Minerals Expanded",
        "description": "[b]多语言版本[/b]\n[img]safe[/img]",
        "short_description": "简体中文、法语与德语文本。",
        "cover_asset_path": str(cover),
        "cover_asset_sha256": cover_hash,
    }
    source_hashes = {
        path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source.rglob("*") if path.is_file()
    }

    preview = inspect_delivery(source, manifest, translations, "source_copy",
                               metadata_overrides=overrides)
    cover_fact = next(item for item in preview["files"] if item["path"].startswith("Images/RemisCover-"))
    destination = tmp_path / "delivery"
    result = build_delivery(source, manifest, translations, destination, "source_copy",
                            expected_fingerprint=preview["fingerprint"], metadata_overrides=overrides)

    metadata = (destination / "metadata.lua").read_text(encoding="utf-8")
    assert preview["status"] == "ready"
    assert (destination / cover_fact["path"]).read_bytes() == cover_bytes
    assert cover_fact["sha256"] == cover_hash
    assert "[中/法/德] 奇异矿物扩展 | Exotic Minerals Expanded" in metadata
    assert "[b]多语言版本[/b]\\n[img]safe[/img]" in metadata
    assert "简体中文、法语与德语文本。" in metadata
    assert "Original Author" in metadata
    assert f"Mod/{result['output_mod_id']}/{cover_fact['path']}" in metadata
    assert "'pdx_id'" not in metadata and "'3679917456'" not in metadata
    assert {
        path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source.rglob("*") if path.is_file()
    } == source_hashes


def test_source_copy_cover_snapshot_rejects_content_changes_after_preview(tmp_path):
    source = _source(tmp_path / "source")
    manifest, translations = _prepared(source)
    cover = tmp_path / "cover.png"
    cover.write_bytes(_synthetic_png())
    overrides = {
        "cover_asset_path": str(cover),
        "cover_asset_sha256": hashlib.sha256(cover.read_bytes()).hexdigest(),
    }
    preview = inspect_delivery(source, manifest, translations, "source_copy",
                               metadata_overrides=overrides)
    cover.write_bytes(_synthetic_png(height=257))

    with pytest.raises(MarsDeliveryError, match="changed since its reviewed"):
        build_delivery(source, manifest, translations, tmp_path / "delivery", "source_copy",
                       expected_fingerprint=preview["fingerprint"], metadata_overrides=overrides)


def test_description_only_override_preserves_default_copy_title_and_source_image(tmp_path):
    source = _source(tmp_path / "source")
    manifest, translations = _prepared(source)
    overrides = {"description": "[b]Description only[/b]"}
    preview = inspect_delivery(source, manifest, translations, "source_copy",
                               metadata_overrides=overrides)
    destination = tmp_path / "delivery"
    result = build_delivery(source, manifest, translations, destination, "source_copy",
                            expected_fingerprint=preview["fingerprint"], metadata_overrides=overrides)

    metadata = (destination / "metadata.lua").read_text(encoding="utf-8")
    assert "[Remis i18n] Synthetic" in metadata
    assert "[b]Description only[/b]" in metadata
    assert f"Mod/{result['output_mod_id']}/Images/icon.png" in metadata
    assert "short_description" not in metadata and "last_changes" not in metadata


def test_source_copy_cover_rejects_oversized_dimensions_and_bad_hash(tmp_path):
    source = _source(tmp_path / "source")
    manifest, translations = _prepared(source)
    cover = tmp_path / "cover.png"
    cover.write_bytes(_synthetic_png(width=9000))
    overrides = {
        "cover_asset_path": str(cover),
        "cover_asset_sha256": hashlib.sha256(cover.read_bytes()).hexdigest(),
    }

    with pytest.raises(MarsDeliveryError, match="dimensions exceed"):
        inspect_delivery(source, manifest, translations, "source_copy", metadata_overrides=overrides)
    with pytest.raises(MarsDeliveryError, match="changed since its reviewed"):
        inspect_delivery(source, manifest, translations, "source_copy",
                         metadata_overrides={**overrides, "cover_asset_sha256": "0" * 64})
    oversized = _synthetic_png() + b"x" * (1024 * 1024)
    cover.write_bytes(oversized)
    with pytest.raises(MarsDeliveryError, match="size limit"):
        inspect_delivery(source, manifest, translations, "source_copy", metadata_overrides={
            **overrides,
            "cover_asset_sha256": hashlib.sha256(oversized).hexdigest(),
        })


def test_source_copy_accepts_jpeg_cover_and_rejects_truncated_jpeg(tmp_path):
    source = _source(tmp_path / "source")
    manifest, translations = _prepared(source)
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(_synthetic_jpeg())
    overrides = {
        "cover_asset_path": str(cover),
        "cover_asset_sha256": hashlib.sha256(cover.read_bytes()).hexdigest(),
    }

    preview = inspect_delivery(source, manifest, translations, "source_copy", metadata_overrides=overrides)
    assert preview["status"] == "ready"
    assert any(item["path"].endswith(".jpg") and item["path"].startswith("Images/RemisCover-")
               for item in preview["files"])

    cover.write_bytes(b"\xff\xd8\xffbroken\xff\xd9")
    overrides["cover_asset_sha256"] = hashlib.sha256(cover.read_bytes()).hexdigest()
    with pytest.raises(MarsDeliveryError, match="PNG or JPEG"):
        inspect_delivery(source, manifest, translations, "source_copy", metadata_overrides=overrides)


def test_delivery_plan_accepts_bounded_metadata_and_requires_cover_snapshot_pair():
    from pydantic import ValidationError
    from scripts.routers.mars_pipeline import DeliveryPlan

    base = {
        "mode": "source_copy",
        "outputs": [{"output_folder_name": "zh-CN-Loc", "language_code": "zh-CN"}],
    }
    request = DeliveryPlan(**{
        **base,
        "metadata_overrides": {
            "title": "中法德 title",
            "description": "[b]Reviewed BBCode[/b]",
            "short_description": "Short description",
            "last_changes": "Initial release",
            "cover_asset_path": "J:/assets/cover.jpg",
            "cover_asset_sha256": "a" * 64,
        },
    })
    assert request.metadata_overrides.title == "中法德 title"
    assert request.metadata_overrides.last_changes == "Initial release"

    with pytest.raises(ValidationError):
        DeliveryPlan(**{**base, "metadata_overrides": {"title": "x" * 61}})
    with pytest.raises(ValidationError):
        DeliveryPlan(**{
            **base,
            "metadata_overrides": {"cover_asset_path": "J:/assets/cover.jpg"},
        })
