from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts.core.services.context_source_parser import ContextSourceParser
from scripts.core.services.incremental_snapshot_service import IncrementalSnapshotService
from scripts.core.services.translation_context_readiness_service import (
    TranslationContextReadinessService,
)
from scripts.core.services.translation_source_snapshot_builder import (
    build_legacy_trimmed_source_snapshot,
    build_translation_source_snapshot,
)


def _write_whitespace_fixture(root: Path, value: str = " A spaced value ") -> Path:
    localization = root / "localisation" / "english"
    localization.mkdir(parents=True, exist_ok=True)
    path = localization / "example_l_english.yml"
    path.write_text(
        f'l_english:\n spaced_key:0 "{value}"\n',
        encoding="utf-8",
    )
    return path


def test_analysis_preserves_source_whitespace_and_matches_translation_snapshot(tmp_path):
    root = tmp_path / "example-mod"
    path = _write_whitespace_fixture(root)
    parser = ContextSourceParser()
    parsed = parser.parse_files([str(path)], str(root))
    inventory = IncrementalSnapshotService().build_snapshot(
        str(root), {"name_en": "English", "code": "en"},
    )

    assert parsed[0].items[0].source_text == " A spaced value "
    assert (
        parser.build_snapshot(parsed).source_snapshot_hash
        == build_translation_source_snapshot(inventory).source_snapshot_hash
    )


@pytest.mark.asyncio
async def test_v3_readiness_accepts_exact_legacy_whitespace_snapshot(tmp_path):
    root = tmp_path / "example-mod"
    _write_whitespace_fixture(root)
    inventory = IncrementalSnapshotService().build_snapshot(
        str(root), {"name_en": "English", "code": "en"},
    )
    current = build_translation_source_snapshot(inventory)
    legacy = build_legacy_trimmed_source_snapshot(inventory)
    assert legacy.source_snapshot_hash != current.source_snapshot_hash

    class TreeRepository:
        def get_latest_release_tree(self, project_id):
            return SimpleNamespace(model_dump=lambda mode="json": {
                "project_id": project_id,
                "release_id": "legacy-v3-release",
                "source_snapshot_hash": legacy.source_snapshot_hash,
                "universal_translation_context": "A compact project summary.",
                "local_fragments": [],
                "groups": [],
                "unit_routes": [],
                "entity_evidence": [],
                "entity_digests": [],
            })

    glossary_manager = SimpleNamespace(
        get_available_glossaries=AsyncMock(
            return_value=[{"glossary_id": 10, "is_main": True}],
        ),
        get_project_glossary=AsyncMock(return_value={"glossary_id": 20}),
        get_entries_for_glossary_ids=AsyncMock(return_value=[{"key": "term"}]),
    )
    service = TranslationContextReadinessService(
        glossary_manager,
        SimpleNamespace(get_pending_candidates=lambda project_id: []),
        tree_v2_repository=TreeRepository(),
    )
    project = {
        "game_id": "stellaris",
        "project_name": "Example",
        "source_path": str(root),
        "source_language": "en",
    }

    readiness = await service.inspect("project-1", "archive", project)

    assert readiness["can_start"] is True
    assert readiness["archive"]["source_snapshot_match"] is True
    assert readiness["archive"]["source_snapshot_hash"] == legacy.source_snapshot_hash
    assert readiness["archive"]["current_source_snapshot_hash"] == current.source_snapshot_hash

    _write_whitespace_fixture(root, "Actually changed")
    stale = await service.inspect("project-1", "archive", project)

    assert stale["can_start"] is False
    assert stale["archive"]["source_snapshot_match"] is False
    assert "context_release_stale" in stale["warnings"]
