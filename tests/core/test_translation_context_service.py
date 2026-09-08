from types import SimpleNamespace
from pathlib import Path

from scripts.core.base_handler import BaseApiHandler
from scripts.core.parallel_processor import ParallelProcessor
from scripts.core.parallel_types import BatchTask, FileTask
from scripts.core.services.translation_context_service import (
    TranslationContextService,
    build_translation_source_snapshot,
    context_workflow_kwargs,
    prepare_context_with_warnings,
    prepare_workflow_context,
)
from scripts.core.services.context_source_parser import ContextSourceParser
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
                "event:war": {"summary": "A war spans several localization entries."},
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
            {
                "aggregate": {"aggregate_type": "event", "aggregate_key": "event:war"},
                "contributions": [{
                    "source_item": {
                        "source_ref": "localisation/english/events.yml::war.1.desc",
                        "metadata": {},
                    },
                }],
            },
        ]

    def delivery_memberships(self, release_id):
        self.calls.append(("delivery_memberships", release_id))
        return [{
            "aggregate": {"aggregate_type": "event", "aggregate_key": "event:war"},
            "source_item": {
                "source_ref": "localisation/english/foo_l_english.yml::other",
                "metadata": {},
            },
            "membership": {"role": "primary_member"},
        }]


class FakeTreeV2Repository:
    def __init__(self, source_hash):
        self.source_hash = source_hash

    def get_release_tree(self, project_id, release_id):
        assert project_id == "project-1"
        assert release_id == "tree-release-1"
        payload = {
            "project_id": project_id,
            "release_id": release_id,
            "source_snapshot_hash": self.source_hash,
            "project_summary": "The project follows a dangerous quest.",
            "local_fragments": [{
                "fragment_id": "fragment-1",
                "summary": "The republic begins the quest.",
                "source_evidence_refs": [{
                    "local_unit_id": "unit-1",
                    "source_ref": SOURCE_FILES[0]["file_path"],
                    "item_key": "republic",
                }],
            }],
            "groups": [{
                "group_id": "group-1", "fragment_ids": ["fragment-1"],
            }],
            "unit_routes": [
                {"local_unit_id": "unit-1", "route": "narrative", "fragment_ids": ["fragment-1"]},
                {"local_unit_id": "unit-2", "route": "reference_asset", "fragment_ids": []},
            ],
            "entity_digests": [{
                "entity_id": "entity:other", "level": "A",
                "final_digest": "Other is a named reference asset.",
            }],
            "entity_evidence": [{
                "entity_id": "entity:other",
                "source_ref": SOURCE_FILES[0]["file_path"],
                "item_key": "other",
            }],
        }
        return SimpleNamespace(model_dump=lambda **_kwargs: payload)


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
        ("delivery_memberships", "release-1"),
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
    assert [item["context_key"] for item in first] == [
        "project:summary", "event:war", "republic",
    ]
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
    assert [len(batch.context_summaries) for batch in batches] == [1, 2]


def test_event_delivery_membership_injects_summary_beyond_sparse_evidence():
    selection, _ = _selection()

    summaries, _ = selection.select_for_batch(
        SOURCE_FILES[0]["file_path"], [SOURCE_FILES[0]["source_entries"][1]]
    )

    assert [item["context_key"] for item in summaries] == [
        "project:summary", "event:war",
    ]


def test_tree_v2_release_routes_event_and_entity_context_without_cross_injection():
    source_hash = build_translation_source_snapshot(SOURCE_FILES).source_snapshot_hash
    selection = TranslationContextService(
        context_service=FakeContextService(source_hash),
        tree_v2_repository=FakeTreeV2Repository(source_hash),
    ).prepare(
        project_id="project-1", files_data=SOURCE_FILES,
        requested_release_id="tree-release-1", mode="archive",
    )

    narrative, _ = selection.select_for_batch(
        SOURCE_FILES[0]["file_path"], [SOURCE_FILES[0]["source_entries"][0]],
    )
    reference, _ = selection.select_for_batch(
        SOURCE_FILES[0]["file_path"], [SOURCE_FILES[0]["source_entries"][1]],
    )
    no_context, _ = selection.select_for_batch(
        SOURCE_FILES[0]["file_path"], [{"key": "missing", "source": "Missing"}],
    )

    assert selection.status == "ready"
    assert [item["context_key"] for item in narrative] == [
        "project:project-1", "event_group:group-1",
    ]
    assert [item["context_key"] for item in reference] == [
        "project:project-1", "entity:other",
    ]
    assert [item["context_key"] for item in no_context] == ["project:project-1"]


def test_theme_related_membership_is_audit_only_and_never_injected():
    source_hash = build_translation_source_snapshot(SOURCE_FILES).source_snapshot_hash
    context = FakeContextService(source_hash)
    memberships = context.delivery_memberships("release-1")
    memberships[0]["membership"]["role"] = "theme_related"
    context.delivery_memberships = lambda release_id: memberships
    selection = TranslationContextService(context_service=context).prepare(
        project_id="project-1", files_data=SOURCE_FILES,
    )

    summaries, _ = selection.select_for_batch(
        SOURCE_FILES[0]["file_path"], [SOURCE_FILES[0]["source_entries"][1]],
    )

    assert [item["context_key"] for item in summaries] == ["project:summary"]


def test_stale_and_missing_releases_warn_without_context():
    source_hash = build_translation_source_snapshot(SOURCE_FILES).source_snapshot_hash
    stale_context = FakeContextService("different-hash")
    stale = TranslationContextService(context_service=stale_context).prepare(
        project_id="project-1", files_data=SOURCE_FILES
    )
    assert stale.status == "blocked"
    assert stale.warning["code"] == "context_release_stale"
    assert stale.warning["allowed_actions"] == ["analyze_context", "update_context_archive"]
    assert stale.select_for_batch(SOURCE_FILES[0]["file_path"], SOURCE_FILES[0]["source_entries"])[0] == []

    missing_context = FakeContextService(source_hash)
    missing_context.list_releases = lambda project_id: []
    missing = TranslationContextService(context_service=missing_context).prepare(
        project_id="project-1", files_data=SOURCE_FILES
    )
    assert missing.status == "blocked"
    assert missing.warning["code"] == "context_release_missing"


def test_stale_acknowledgement_allows_only_mod_summary_and_binds_current_snapshot():
    current_hash = build_translation_source_snapshot(SOURCE_FILES).source_snapshot_hash
    context = FakeContextService("different-hash")
    acknowledgement = {
        "choice": "use_old_archive",
        "context_release_id": "release-1",
        "source_snapshot_hash": current_hash,
    }
    selection = TranslationContextService(
        context_service=context,
        workflow_kind="incremental",
    ).prepare(
        project_id="project-1",
        files_data=SOURCE_FILES,
        mode="archive",
        stale_acknowledgement=acknowledgement,
    )

    assert selection.status == "stale_summary_only"
    assert selection.direct_index == {}
    summaries, metadata = selection.select_for_batch(
        SOURCE_FILES[0]["file_path"], SOURCE_FILES[0]["source_entries"],
    )
    assert [item["context_key"] for item in summaries] == ["project:summary"]
    assert metadata["user_choice"] == "use_old_archive"
    assert metadata["workflow"] == "incremental"
    assert metadata["telemetry"]["contexts"][0]["context_key"] == "project:summary"

    changed_hash_ack = {**acknowledgement, "source_snapshot_hash": "another-hash"}
    blocked = TranslationContextService(context_service=context).prepare(
        project_id="project-1",
        files_data=SOURCE_FILES,
        mode="archive",
        stale_acknowledgement=changed_hash_ack,
    )
    assert blocked.status == "blocked"
    assert blocked.direct_index == {}


def test_stale_acknowledgement_can_disable_archive_for_glossary_only_translation():
    current_hash = build_translation_source_snapshot(SOURCE_FILES).source_snapshot_hash
    context = FakeContextService("different-hash")
    selection = TranslationContextService(context_service=context).prepare(
        project_id="project-1",
        files_data=SOURCE_FILES,
        mode="archive",
        stale_ack={
            "choice": "disable_archive",
            "context_release_id": "release-1",
            "source_snapshot_hash": current_hash,
        },
    )
    assert selection.status == "disabled"
    assert selection.enabled is False
    assert selection.select_for_batch(
        SOURCE_FILES[0]["file_path"], SOURCE_FILES[0]["source_entries"],
    )[0] == []


def test_context_workflow_kwargs_preserves_pydantic_acknowledgement_mapping():
    acknowledgement = {
        "choice": "use_old_archive",
        "context_release_id": "release-1",
        "source_snapshot_hash": "hash-1",
    }

    assert context_workflow_kwargs(
        SimpleNamespace(stale_acknowledgement=acknowledgement),
    )["stale_acknowledgement"] == acknowledgement


def test_stale_choice_and_acknowledgement_must_agree():
    current_hash = build_translation_source_snapshot(SOURCE_FILES).source_snapshot_hash
    context = FakeContextService("different-hash")
    blocked = TranslationContextService(context_service=context).prepare(
        project_id="project-1",
        files_data=SOURCE_FILES,
        mode="archive",
        stale_choice="disable_archive",
        stale_acknowledgement={
            "choice": "use_old_archive",
            "context_release_id": "release-1",
            "source_snapshot_hash": current_hash,
        },
    )
    assert blocked.status == "blocked"


def test_v3_tree_projection_uses_orthogonal_delivery_route_and_mod_context():
    from scripts.core.services.context_tree_v2_translation_adapter import (
        ContextTreeV2TranslationAdapter,
    )

    source_hash = build_translation_source_snapshot(SOURCE_FILES).source_snapshot_hash
    projection = ContextTreeV2TranslationAdapter._project({
        "project_id": "project-1",
        "release_id": "v3-release-1",
        "source_snapshot_hash": source_hash,
        "universal_translation_context": "围绕共和国、战争与远征展开，专名和事件因果必须保持一致。",
        "local_fragments": [{
            "fragment_id": "fragment-1",
            "summary": "The republic enters the war.",
            "source_evidence_refs": [{
                "local_unit_id": "unit-event",
                "source_ref": SOURCE_FILES[0]["file_path"],
                "item_key": "republic",
            }],
        }],
        "groups": [{"group_id": "group-1", "fragment_ids": ["fragment-1"]}],
        "unit_routes": [{
            "local_unit_id": "unit-event",
            "route": "narrative",
            "content_role": "event_narrative",
            "delivery_route": "event",
            "fragment_ids": ["fragment-1"],
        }, {
            "local_unit_id": "unit-noise",
            "route": "no_context",
            "content_role": "utility_or_noise",
            "delivery_route": "none",
            "fragment_ids": [],
        }],
        "entity_digests": [{
            "entity_id": "entity:republic", "level": "A",
            "final_digest": "Reference description that must not leak to event delivery.",
        }],
        "entity_evidence": [{
            "entity_id": "entity:republic",
            "local_unit_id": "unit-event",
            "source_ref": SOURCE_FILES[0]["file_path"],
            "item_key": "republic",
        }],
    })
    assert projection.project_summary[0]["summary"]["text"].startswith("围绕共和国")
    assert projection.direct_index[(
        "localisation/english/foo_l_english.yml", "republic",
    )][0]["aggregate_type"] == "event"


def test_stale_summary_prompt_cannot_receive_old_event_chain():
    current_hash = build_translation_source_snapshot(SOURCE_FILES).source_snapshot_hash
    selection = TranslationContextService(
        context_service=FakeContextService("different-hash"),
    ).prepare(
        project_id="project-1",
        files_data=SOURCE_FILES,
        mode="archive",
        stale_acknowledgement={
            "choice": "use_old_archive",
            "context_release_id": "release-1",
            "source_snapshot_hash": current_hash,
        },
    )
    summaries, metadata = selection.select_for_batch(
        SOURCE_FILES[0]["file_path"], SOURCE_FILES[0]["source_entries"],
    )
    batch = BatchTask(
        file_task=SimpleNamespace(), batch_index=0, start_index=0,
        end_index=2, texts=["The Republic", "Other"],
    )
    batch.context_summaries = summaries
    batch.context_metadata = metadata
    prompt = BaseApiHandler._build_context_release_prompt(batch)
    assert "The project's setting." in prompt
    assert "war spans" not in prompt
    assert metadata["telemetry"]["workflow"] == "unknown"


def test_initial_and_incremental_context_wrappers_label_telemetry_phase():
    source_hash = build_translation_source_snapshot(SOURCE_FILES).source_snapshot_hash
    initial = prepare_workflow_context(
        "project-1", SOURCE_FILES, True, "release-1", 4000,
        FakeContextService(source_hash),
    )
    incremental, _warnings = prepare_context_with_warnings(
        "project-1", SOURCE_FILES, True, "release-1", 4000,
        FakeContextService(source_hash),
    )
    assert initial.metadata["workflow"] == "initial"
    assert incremental.metadata["workflow"] == "incremental"


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
                SourceItemInput(key=key, source_order=index, source_text=source)
                for index, (key, source, _line_number) in enumerate(parsed_entries)
            ),
        )
    ])

    assert parsed_entries
    assert translation_snapshot == analysis_snapshot
    assert translation_snapshot.source_snapshot_hash == analysis_snapshot.source_snapshot_hash


def test_narrative_fixture_snapshot_matches_real_analysis_parser():
    root = Path("tests/fixtures/demo_smoke/issue_198_narrative/source_mod").resolve()
    paths = sorted((root / "localisation" / "english").glob("*.yml"))
    parser = ContextSourceParser()
    parsed_files = parser.parse_files([str(path) for path in paths], str(root))

    analysis_snapshot = parser.build_snapshot(parsed_files)
    translation_snapshot = build_translation_source_snapshot([
        {
            "path": str(source_file.path),
            "file_path": source_file.relative_path,
            "original_lines": source_file.content.decode("utf-8-sig").splitlines(keepends=True),
            "source_entries": [
                {"key": item.item_key, "source": item.source_text}
                for item in source_file.items
            ],
        }
        for source_file in parsed_files
    ])

    assert len(parsed_files) == 7
    assert translation_snapshot == analysis_snapshot
