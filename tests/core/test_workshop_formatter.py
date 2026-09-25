from pathlib import Path

import pytest

from scripts.core.workshop_formatter import archive_generated_description


def test_archive_generated_description_preserves_project_relative_location(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    saved_path = archive_generated_description(
        "project-123", "[b]Description[/b]", "76561198012345678"
    )

    assert saved_path is not None
    archive = tmp_path / saved_path
    assert Path(saved_path).is_relative_to(
        Path("my_translation/project-123/generated_descriptions")
    )
    assert archive.read_text(encoding="utf-8") == "[b]Description[/b]"


@pytest.mark.parametrize(
    ("project_id", "workshop_id"),
    [
        ("../outside", "123456"),
        ("", "../../outside"),
        ("C:outside", "123456"),
        ("CON", "123456"),
    ],
)
def test_archive_generated_description_rejects_unsafe_identifiers(
    tmp_path, monkeypatch, project_id, workshop_id
):
    monkeypatch.chdir(tmp_path)

    assert archive_generated_description(project_id, "Description", workshop_id) is None
    assert not (tmp_path.parent / "outside").exists()


def test_archive_generated_description_rejects_project_symlink_escape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    translations = tmp_path / "my_translation"
    translations.mkdir()
    original_resolve = Path.resolve

    def resolve_with_external_link(path, *args, **kwargs):
        if path == Path("my_translation/project-123/generated_descriptions"):
            return outside
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_with_external_link)

    assert archive_generated_description("project-123", "Description", "123456") is None
    assert list(outside.iterdir()) == []
