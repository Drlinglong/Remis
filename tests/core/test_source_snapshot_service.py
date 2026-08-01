import hashlib

import pytest

from scripts.core.services.source_snapshot_service import (
    SourceChangeKind,
    SourceFileInput,
    SourceItemInput,
    SourceSnapshotService,
    normalize_relative_path,
    sha256_bytes,
)


def file(path, content, *items):
    return SourceFileInput(
        relative_path=path,
        content=content,
        items=tuple(SourceItemInput(key, source) for key, source in items),
    )


def test_snapshot_hash_is_deterministic_and_independent_of_input_order():
    service = SourceSnapshotService()
    first = service.build_snapshot([
        file(r"localization\english\b.yml", "B", ("b.key", "Bee")),
        file("localization/english/a.yml", "A", ("a.key", "Aye")),
    ])
    second = service.build_snapshot([
        file("localization/english/a.yml", "A", ("a.key", "Aye")),
        file(r"localization\english\b.yml", "B", ("b.key", "Bee")),
    ])

    assert first == second
    assert first.source_snapshot_hash == second.source_snapshot_hash
    assert [item.relative_path for item in first.files] == [
        "localization/english/a.yml",
        "localization/english/b.yml",
    ]


def test_windows_relative_paths_are_canonicalized_and_absolute_paths_rejected():
    assert normalize_relative_path(r".\localisation\english\..\english\events.yml") == (
        "localisation/english/events.yml"
    )

    with pytest.raises(ValueError):
        normalize_relative_path(r"C:\mods\events.yml")


def test_content_change_classifies_file_and_item_as_modified():
    service = SourceSnapshotService()
    previous = service.build_snapshot([file("events.yml", "old", ("event.one", "Old"))])
    current = service.build_snapshot([file("events.yml", "new", ("event.one", "New"))])

    diff = current.diff(previous)

    assert [(change.relative_path, change.kind) for change in diff.files] == [
        ("events.yml", SourceChangeKind.MODIFIED)
    ]
    assert [(change.identity.item_key, change.kind) for change in diff.items] == [
        ("event.one", SourceChangeKind.MODIFIED)
    ]
    assert diff.has_changes is True


def test_item_content_changes_project_hash_even_when_file_bytes_are_unchanged():
    service = SourceSnapshotService()
    first = service.build_snapshot([file("events.yml", "same", ("event.one", "Old"))])
    second = service.build_snapshot([file("events.yml", "same", ("event.one", "New"))])

    assert first.files[0].source_sha256 == second.files[0].source_sha256
    assert first.source_snapshot_hash != second.source_snapshot_hash


def test_add_delete_and_unchanged_classifications_are_stable():
    service = SourceSnapshotService()
    previous = service.build_snapshot([
        file("same.yml", "same", ("same.key", "Same")),
        file("deleted.yml", "deleted", ("deleted.key", "Deleted")),
    ])
    current = service.build_snapshot([
        file("same.yml", "same", ("same.key", "Same")),
        file("added.yml", "added", ("added.key", "Added")),
    ])

    diff = current.diff(previous)

    assert [(change.relative_path, change.kind) for change in diff.files] == [
        ("added.yml", SourceChangeKind.ADDED),
        ("deleted.yml", SourceChangeKind.DELETED),
        ("same.yml", SourceChangeKind.UNCHANGED),
    ]
    assert [(change.identity.canonical, change.kind) for change in diff.items] == [
        ("9:added.yml:9:added.key", SourceChangeKind.ADDED),
        ("11:deleted.yml:11:deleted.key", SourceChangeKind.DELETED),
        ("8:same.yml:8:same.key", SourceChangeKind.UNCHANGED),
    ]


def test_file_sha256_matches_existing_sha256_definition(tmp_path):
    source = tmp_path / "source.yml"
    source.write_bytes("你好".encode("utf-8"))
    snapshot = SourceSnapshotService().build_snapshot([
        SourceFileInput(relative_path="source.yml", path=source),
    ])

    assert snapshot.files[0].source_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert sha256_bytes(source.read_bytes()) == snapshot.files[0].source_sha256
