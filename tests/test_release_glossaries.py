"""Release attachments remain reproducible and independent of user state."""
import csv
import hashlib
import io
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from scripts.build_glossary_resources import RESOURCE_PATH, package_glossaries, read_resources
from scripts.core.batch_repository import BatchConflict
from scripts.core.glossary_distribution import distribution_snapshot
from scripts.core.glossary_terminology_service import GlossaryTerminologyService


ROOT = Path(__file__).resolve().parents[1]


def test_release_package_contains_both_locales_and_preserves_csv_records(tmp_path):
    output = package_glossaries(ROOT, tmp_path, "9.9.9")
    first = output.read_bytes()
    assert package_glossaries(ROOT, tmp_path, "9.9.9").read_bytes() == first
    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["remis_release_version"] == "9.9.9"
        assert set(archive.namelist()) == {*manifest["files"], "manifest.json"}
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
        for name in ("surviving-mars.en-zh-CN", "surviving-mars.en-zh-CN-zh-TW"):
            payload = json.loads(archive.read(name + ".json"))["import_payload"]
            csv_bytes = archive.read(name + ".csv")
            assert csv_bytes.startswith(b"\xef\xbb\xbf")
            records = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
            assert len(records) == len(payload["terms"])
            by_id = {row["concept_id"]: row for row in records}
            for term in payload["terms"]:
                row = by_id[term["concept_id"]]
                assert row["en"] == term["source"]
                assert row[payload["locale"]] == term["translation"]
                assert json.loads(row["aliases"]) == term["aliases"]
    assert output.with_suffix(".zip.sha256").read_text(encoding="utf-8").startswith(hashlib.sha256(first).hexdigest())


def test_changed_static_resource_blocks_build_without_reading_user_data(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(ROOT / RESOURCE_PATH, root / RESOURCE_PATH)
    (root / RESOURCE_PATH / "README.zh-CN.md").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        read_resources(root)
    with pytest.raises(ValueError, match="Invalid release version"):
        package_glossaries(ROOT, tmp_path, "../overwrite")


def test_different_existing_attachment_is_not_overwritten(tmp_path):
    output = tmp_path / "Remis-SurvivingMars-Glossary_9.9.9.zip"
    output.write_bytes(b"different existing artifact")
    with pytest.raises(FileExistsError):
        package_glossaries(ROOT, tmp_path, "9.9.9")
    assert output.read_bytes() == b"different existing artifact"


def test_release_pipeline_always_emits_glossary_alongside_installer(tmp_path, monkeypatch):
    from scripts import build_pipeline
    from scripts.build_profile import PROFILES

    installer = tmp_path / "setup.exe"
    monkeypatch.setattr(build_pipeline, "copy_nsis_artifact", lambda *args: installer)
    real_packager = package_glossaries
    destinations = []

    def package(root, output_dir, version):
        destinations.append((Path(output_dir), version))
        return real_packager(root, tmp_path, version)

    monkeypatch.setattr(build_pipeline, "package_glossaries", package)
    copied, attachment = build_pipeline.copy_release_artifacts(ROOT, "tauri", "config", "target", PROFILES["stable"])
    assert copied == installer and attachment.is_file()
    assert destinations == [(ROOT / "archive/release/stable", PROFILES["stable"].version)]


def test_distribution_preserves_senses_reviews_and_excludes_private_evidence():
    glossary = {"game_id": "surviving_mars", "name": "Terms", "description": ""}
    rows = []
    for identity, state in (("1", "approved"), ("2", "pending")):
        rows.append({"entry_id": identity, "glossary_id": 1,
                     "translations": {"en": "Explorer", "zh-CN": "探索者", "zh-TW": "探索載具"},
                     "variants": {"en": ["RC Explorer"]},
                     "raw_metadata": {"source_text": "Explorer", "terminology": {
                         "locale": "zh-TW", "concept_id": identity, "source_id": identity,
                         "sense": "vehicle J:/private/game/Game.csv:19", "review_state": state, "confidence": "high",
                         "context_keys": ["vehicle"], "alias_review_basis": ["RC Explorer"],
                         "review_basis": {"source": "Explorer", "translation": "探索載具",
                                          "sense": "vehicle J:/private/game/Game.csv:19", "context_keys": ["vehicle"]},
                         "evidence_refs": [{"file": "J:/private/input.csv", "sha256": "a" * 64}],
                     }}})
    terms, excluded, states = GlossaryTerminologyService._terms(rows, "zh-TW")
    preview = {"game_id": "surviving_mars", "locale": "zh-TW", "fingerprint": "b" * 64,
               "entry_count": 2, "eligible_count": 1, "excluded": excluded, "review_states": states}
    exported = distribution_snapshot(glossary, rows, terms, preview, "b" * 64)
    term = exported["import_payload"]["terms"][0]
    assert term["review_state"] == "approved" and term["confidence"] == "high"
    assert term["aliases"] == ["RC Explorer"] and term["sense"] == "vehicle Game.csv:19"
    assert term["reference_translations"]["zh-CN"] == "探索者"
    assert "private" not in json.dumps(exported)
    assert exported["snapshot"]["excluded"] == [{"reason": "pending"}]
    assert exported["import_payload"]["approved"] is False
    with pytest.raises(BatchConflict, match="Inspect the glossary"):
        distribution_snapshot(glossary, rows, terms, preview, "c" * 64)


def test_release_assets_are_public_utf8_and_keep_vehicle_alias():
    _, contents = read_resources(ROOT)
    for data in contents.values():
        text = data.decode("utf-8")
        assert "\r" not in text  # Git's eol=lf checkout must preserve the manifest hashes.
        assert "\ufffd" not in text and "???" not in text
        assert "SteamLibrary" not in text and "SurvivingMarsModdingNotes" not in text
    document = json.loads(contents["surviving-mars.en-zh-CN-zh-TW.json"].decode("utf-8"))
    assert any(term["source"] == "RC Explorer" and "Explorer" in term["aliases"]
               for term in document["import_payload"]["terms"])
