import io
import zipfile
from pathlib import Path

import pytest

from scripts.core.services import translation_upload_service
from scripts.core.services.translation_upload_service import (
    TranslationArchiveUploadError,
    install_translation_archive,
)


def _archive(entries: dict[str, str]) -> io.BytesIO:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    stream.seek(0)
    return stream


@pytest.mark.parametrize(
    "filename",
    [".zip", "../outside.zip", "..\\outside.zip", "C:\\outside.zip", "not-a-zip.txt"],
)
def test_rejects_unsafe_upload_name_without_touching_existing_source(tmp_path, filename):
    source_root = tmp_path / "sources"
    existing = source_root / "existing" / "keep.txt"
    existing.parent.mkdir(parents=True)
    existing.write_text("keep", encoding="utf-8")

    with pytest.raises(TranslationArchiveUploadError):
        install_translation_archive(_archive({"file.txt": "value"}), filename, source_root)

    assert existing.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("filename", ["CON.zip", "CON.txt.zip", "COM1.zip", "LPT9.zip", "demo .zip"])
def test_rejects_reserved_windows_upload_name_on_python_310(monkeypatch, filename):
    monkeypatch.delattr(translation_upload_service.os.path, "isreserved", raising=False)

    with pytest.raises(TranslationArchiveUploadError, match="reserved Windows name"):
        translation_upload_service._safe_upload_name(filename)


def test_invalid_zip_preserves_existing_mod_directory(tmp_path):
    source_root = tmp_path / "sources"
    existing = source_root / "demo" / "keep.txt"
    existing.parent.mkdir(parents=True)
    existing.write_text("keep", encoding="utf-8")

    with pytest.raises(TranslationArchiveUploadError, match="Invalid ZIP"):
        install_translation_archive(io.BytesIO(b"not-a-zip"), "demo.zip", source_root)

    assert existing.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("member", ["../../escape.txt", "..\\..\\escape.txt", "C:\\escape.txt"])
def test_rejects_archive_member_outside_staging_directory(tmp_path, member):
    source_root = tmp_path / "sources"

    with pytest.raises(TranslationArchiveUploadError, match="escapes"):
        install_translation_archive(_archive({member: "unsafe"}), "demo.zip", source_root)

    assert not (tmp_path / "escape.txt").exists()


def test_valid_archive_atomically_replaces_existing_mod(tmp_path):
    source_root = tmp_path / "sources"
    existing = source_root / "demo" / "old.txt"
    existing.parent.mkdir(parents=True)
    existing.write_text("old", encoding="utf-8")

    result = install_translation_archive(
        _archive({"demo/localization/new.yml": 'l_english:\n key:0 "Value"\n'}),
        "demo.zip",
        source_root,
    )

    assert result.mod_name == "demo"
    assert Path(result.source_path) == source_root / "demo"
    assert not existing.exists()
    assert (source_root / "demo" / "localization" / "new.yml").is_file()
    assert not list(source_root.glob(".remis-upload-*"))
