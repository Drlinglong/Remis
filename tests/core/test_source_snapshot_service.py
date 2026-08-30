import hashlib

import pytest

from scripts.core.context_local_units import ContextLocalUnitBuilder
from scripts.core.services.context_release_assembler import ContextReleaseAssembler
from scripts.core.services.source_snapshot_service import (
    SourceChangeKind,
    SourceFileInput,
    SourceItemInput,
    SourceSnapshotService,
    normalize_relative_path,
    sha256_bytes,
)
from scripts.core.services.context_source_parser import ContextSourceParser


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


def test_prepend_localization_entry_preserves_existing_logical_identities(tmp_path):
    root = tmp_path / "mod"
    path = root / "localisation" / "main.yml"
    path.parent.mkdir(parents=True)
    parser = ContextSourceParser()
    path.write_text(
        'l_english:\n old_key:0 "Old text"\n later_key:0 "Later text"\n',
        encoding="utf-8",
    )
    previous = parser.parse_files([str(path)], str(root))[0]
    path.write_text(
        'l_english:\n new_key:0 "New text"\n old_key:0 "Old text"\n'
        ' later_key:0 "Later text"\n',
        encoding="utf-8",
    )
    current = parser.parse_files([str(path)], str(root))[0]

    previous_ids = {item.item_key: item.source_item_id for item in previous.items}
    current_ids = {item.item_key: item.source_item_id for item in current.items}
    assert current_ids["old_key:0"] == previous_ids["old_key:0"]
    assert current_ids["later_key:0"] == previous_ids["later_key:0"]
    assert [item.source_order for item in current.items] == [0, 1, 2]
    assert [item.item_key for item in current.items] == [
        "new_key:0", "old_key:0", "later_key:0"
    ]


def test_duplicate_localization_keys_use_ordinal_in_logical_identity(tmp_path):
    root = tmp_path / "mod"
    path = root / "localisation" / "main.yml"
    path.parent.mkdir(parents=True)
    path.write_text(
        'l_english:\n repeated:0 "First"\n repeated:0 "Second"\n',
        encoding="utf-8",
    )

    parsed = ContextSourceParser().parse_files([str(path)], str(root))[0]

    assert [item.duplicate_key_ordinal for item in parsed.items] == [0, 1]
    assert parsed.items[0].source_item_id != parsed.items[1].source_item_id


def test_content_change_keeps_logical_identity_but_creates_new_revision(tmp_path):
    root = tmp_path / "mod"
    path = root / "localisation" / "main.yml"
    path.parent.mkdir(parents=True)
    parser = ContextSourceParser()
    path.write_text('l_english:\n key:0 "Old text"\n', encoding="utf-8")
    previous = parser.parse_files([str(path)], str(root))
    previous_snapshot = parser.build_snapshot(previous)
    previous_manifest = ContextReleaseAssembler(None).build_manifest(
        previous,
        previous_snapshot,
        ContextLocalUnitBuilder.build(previous[0].items),
    )
    path.write_text('l_english:\n key:0 "New text"\n', encoding="utf-8")
    current = parser.parse_files([str(path)], str(root))
    current_snapshot = parser.build_snapshot(current)
    current_manifest = ContextReleaseAssembler(None).build_manifest(
        current,
        current_snapshot,
        ContextLocalUnitBuilder.build(current[0].items),
    )

    assert previous[0].items[0].source_item_id == current[0].items[0].source_item_id
    assert previous_manifest.source_items[0].content_hash != current_manifest.source_items[0].content_hash
    assert previous_manifest.source_items[0].source_revision_id != current_manifest.source_items[0].source_revision_id
