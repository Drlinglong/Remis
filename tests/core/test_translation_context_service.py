from types import SimpleNamespace
from pathlib import Path

from scripts.core.base_handler import BaseApiHandler
from scripts.core.parallel_processor import ParallelProcessor
from scripts.core.parallel_types import BatchTask, FileTask
from scripts.core.services.translation_context_service import (
    TranslationContextService,
    build_translation_source_snapshot,
)
from scripts.core.loc_parser import parse_loc_file_with_lines
from scripts.core.services.source_snapshot_service import SourceFileInput, SourceItemInput, SourceSnapshotService


SOURCE_FILES = [
    {
        "filename": "foo_l_english.yml",
        "file_path": "localisation/english/foo_l_english.yml",
        "original_lines": ["l_english:\n", ' republic:0 "The Republic"\n', ' other:0 "Other"\n'],
        "source_entries": [
            {"key": "republic", "source": "The Republic"},
            {"key": "other", "source": "Other"},
        ],
    }
]


class FakeContextService:
    def __init__(self, source_hash):
        self.release = SimpleNamespace(
            release_id="release-1",
            project_id="project-1",
            metadata=SimpleNamespace(source_snapshot_hash=source_hash),
        )
        self.calls = []

    def list_releases(self, project_id):
        self.calls.append(("list_releases", project_id))
        return [self.release]

    def effective_context(self, release_id):
        self.calls.append(("effective_context", release_id))
        return SimpleNamespace(
            release=self.release,
            effective_context={
                "project:summary": {"summary": "The project's setting."},
                "republic": {
                    "summary": "A republic appoints a consul.",
                    "preferred_name": "共和国",
                },
                "unmatched": {"summary": "Never injected."},
            },
        )

    def traceability(self, release_id):
        self.calls.append(("traceability", release_id))
        return [
            {
                "aggregate": {
                    "aggregate_type": "project",
                    "aggregate_key": "project:summary",
                },
                "contributions": [],
            },
            {
                "aggregate": {"aggregate_type": "entity", "aggregate_key": "republic"},
                "contributions": [
                    {
                        "source_item": {
                            "source_ref": "localisation/english/foo_l_english.yml::republic",
                            "metadata": {},
                        }
                    }
                ],
            },
            {
                "aggregate": {"aggregate_type": "entity", "aggregate_key": "unmatched"},
                "contributions": [
                    {
                        "source_item": {
                            "source_ref": "localisation/english/other.yml::unmatched",
                            "metadata": {},
                        }
                    }
                ],
            },
        ]


def _selection(character_budget=4000):
    source_hash = build_translation_source_snapshot(SOURCE_FILES).source_snapshot_hash
    context = FakeContextService(source_hash)
    selection = TranslationContextService(
        context_service=context,
        character_budget=character_budget,
    ).prepare(project_id="project-1", files_data=SOURCE_FILES)
    return selection, context


def test_matching_release_injects_project_and_direct_key_with_human_override_precedence():
    selection, context = _selection()

    summaries, metadata = selection.select_for_batch(
        SOURCE_FILES[0]["file_path"], SOURCE_FILES[0]["source_entries"][:1]
    )

    assert [item["context_key"] for item in summaries] == ["project:summary", "republic"]
    assert summaries[1]["summary"]["preferred_name"] == "共和国"
    assert metadata["context_release_id"] == "release-1"
    assert metadata["source_snapshot_hash"] == context.release.metadata.source_snapshot_hash
    assert context.calls == [
        ("list_releases", "project-1"),
        ("effective_context", "release-1"),
        ("traceability", "release-1"),
    ]


def test_deterministic_order_and_character_budget():
    selection, _ = _selection(character_budget=500)
    first = selection.select_for_batch(
        SOURCE_FILES[0]["file_path"], SOURCE_FILES[0]["source_entries"]
    )[0]
    second = selection.select_for_batch(
        SOURCE_FILES[0]["file_path"], SOURCE_FILES[0]["source_entries"]
    )[0]

    assert first == second
    assert [item["context_key"] for item in first] == ["project:summary", "republic"]
    assert sum(len(str(item)) for item in first) < 500


def test_no_match_only_has_project_summary_and_never_changes_output_count():
    selection, _ = _selection()
    summaries, _ = selection.select_for_batch(
        "localisation/english/foo_l_english.yml", [{"key": "missing", "source": "Missing"}]
    )
    assert [item["context_key"] for item in summaries] == ["project:summary"]

    file_task = FileTask(
        filename="foo_l_english.yml",
        root=".",
        original_lines=[],
        texts_to_translate=["A", "B"],
        key_map={},
        is_custom_loc=False,
        target_lang={"code": "zh-CN", "name": "Chinese"},
        source_lang={"code": "en", "name": "English"},
        game_profile={"id": "test"},
        mod_context="",
        provider_name="local",
        output_folder_name="out",
        source_dir=".",
        dest_dir=".",
        client=None,
        mod_name="Demo",
        file_path="localisation/english/foo_l_english.yml",
        source_entries=[{"key": "missing", "source": "A"}, {"key": "other", "source": "B"}],
        translation_entry_indices=[0, 1],
    )
    batches = ParallelProcessor(chunk_size_override=1, context_selector=selection)._create_batch_tasks([file_task])
    assert [len(batch.texts) for batch in batches] == [1, 1]
    assert all(len(batch.context_summaries) == 1 for batch in batches)


def test_stale_and_missing_releases_warn_without_context():
    source_hash = build_translation_source_snapshot(SOURCE_FILES).source_snapshot_hash
    stale_context = FakeContextService("different-hash")
    stale = TranslationContextService(context_service=stale_context).prepare(
        project_id="project-1", files_data=SOURCE_FILES
    )
    assert stale.status == "stale"
    assert stale.warning["code"] == "context_release_stale"
    assert stale.warning["allowed_actions"] == ["analyze_context", "update_context_archive"]
    assert stale.select_for_batch(SOURCE_FILES[0]["file_path"], SOURCE_FILES[0]["source_entries"])[0] == []

    missing_context = FakeContextService(source_hash)
    missing_context.list_releases = lambda project_id: []
    missing = TranslationContextService(context_service=missing_context).prepare(
        project_id="project-1", files_data=SOURCE_FILES
    )
    assert missing.status == "missing"
    assert missing.warning["code"] == "context_release_missing"


def test_initial_and_incremental_file_material_produce_same_release_gate():
    initial_selection, _ = _selection()
    incremental_files = [
        {
            "filename": SOURCE_FILES[0]["filename"],
            "file_path": SOURCE_FILES[0]["file_path"],
            "original_lines": SOURCE_FILES[0]["original_lines"],
            "parsed_entries": [("republic", "The Republic", 2), ("other", "Other", 3)],
        }
    ]
    source_hash = build_translation_source_snapshot(incremental_files).source_snapshot_hash
    incremental_context = FakeContextService(source_hash)
    incremental_selection = TranslationContextService(context_service=incremental_context).prepare(
        project_id="project-1", files_data=incremental_files
    )
    assert initial_selection.status == incremental_selection.status == "ready"
    assert initial_selection.source_snapshot_hash == incremental_selection.source_snapshot_hash
    assert initial_selection.select_for_batch(
        SOURCE_FILES[0]["file_path"], SOURCE_FILES[0]["source_entries"][:1]
    )[0] == incremental_selection.select_for_batch(
        SOURCE_FILES[0]["file_path"], [{"key": "republic", "source": "The Republic"}]
    )[0]


def test_prompt_contract_has_release_metadata_but_no_rag_or_raw_traceability():
    selection, _ = _selection()
    summaries, metadata = selection.select_for_batch(
        SOURCE_FILES[0]["file_path"], SOURCE_FILES[0]["source_entries"][:1]
    )
    batch = BatchTask(
        file_task=SimpleNamespace(),
        batch_index=0,
        start_index=0,
        end_index=1,
        texts=["The Republic"],
    )
    batch.context_summaries = summaries
    batch.context_metadata = metadata
    prompt = BaseApiHandler._build_context_release_prompt(batch)
    assert "release-1" in prompt
    assert metadata["source_snapshot_hash"] in prompt
    assert "preferred_name" in prompt
    assert "source_ref" not in prompt
    assert "rag" not in prompt.lower()


def test_context_disabled_does_not_read_repository():
    class ExplodingContext:
        def list_releases(self, project_id):
            raise AssertionError("disabled context must not read releases")

    selection = TranslationContextService(context_service=ExplodingContext()).prepare(
        project_id="project-1", files_data=SOURCE_FILES, enabled=False
    )
    assert selection.status == "disabled"
    assert selection.select_for_batch(SOURCE_FILES[0]["file_path"], SOURCE_FILES[0]["source_entries"])[0] == []


def test_real_parsed_localization_snapshot_matches_analysis_contract():
    fixture = "tests/fixtures/demo_smoke/agent_workshop_broken/localization/english/workshop_demo_l_english.yml"
    path = Path(fixture)
    raw_lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    parsed_entries = parse_loc_file_with_lines(path)

    translation_snapshot = build_translation_source_snapshot([
        {
            "file_path": "localization/english/workshop_demo_l_english.yml",
            "original_lines": raw_lines,
            "parsed_entries": parsed_entries,
        }
    ])
    analysis_snapshot = SourceSnapshotService().build_snapshot([
        SourceFileInput(
            relative_path="localization/english/workshop_demo_l_english.yml",
            content="".join(raw_lines),
            items=tuple(
                SourceItemInput(key=key, source_text=source)
                for key, source, _line_number in parsed_entries
            ),
        )
    ])

    assert parsed_entries
    assert translation_snapshot == analysis_snapshot
    assert translation_snapshot.source_snapshot_hash == analysis_snapshot.source_snapshot_hash
