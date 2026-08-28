from scripts.core.base_handler import _build_numbered_input
from scripts.core.parallel_types import BatchTask, FileTask
from scripts.core.services.agent_validation_policy import classify_issues, repairable_issues
from scripts.core.services.incremental_preparation_service import (
    _build_incremental_file_task,
)
from scripts.core.services.workshop_writeback_service import (
    is_repairable_workshop_issue,
)
from scripts.core.vic3_country_adjective_context import (
    build_file_hints,
    detect_hint,
    load_language_policies,
    load_official_country_tags,
    prompt_policy,
)


def _file_task(**overrides):
    values = {
        "filename": "sample_l_english.yml",
        "root": "root",
        "original_lines": [],
        "texts_to_translate": ["Chinese", "$CHI_ADJ$ power"],
        "key_map": {},
        "is_custom_loc": False,
        "target_lang": {"code": "zh-CN", "name": "Simplified Chinese"},
        "source_lang": {"code": "en", "name": "English"},
        "game_profile": {"id": "victoria3"},
        "mod_context": "",
        "provider_name": "openrouter",
        "output_folder_name": "output",
        "source_dir": "source",
        "dest_dir": "dest",
        "client": None,
        "mod_name": "Demo",
    }
    values.update(overrides)
    return FileTask(**values)


def test_production_resources_cover_official_tags_and_ten_languages():
    assert len(load_official_country_tags()) == 830
    assert set(load_language_policies()) == {
        "zh-CN", "ja", "ko", "de", "fr", "es", "pt-BR", "pl", "ru", "tr"
    }


def test_h2_routes_official_definition_and_modified_reference_only():
    definition = detect_hint("CHI_ADJ", "Chinese", "zh-CN")
    reference = detect_hint("demo", "$CHI_ADJ|l$ power", "zh-CN")

    assert "country_adjective_definition" in definition
    assert "country_adjective_reference" in reference
    assert detect_hint("XYZ_ADJ", "Example", "zh-CN") is None
    assert detect_hint("demo", "$XYZ_ADJ$ power", "zh-CN") is None


def test_non_vic3_and_unsupported_language_fail_open_without_hints():
    key_infos = [{"key_part": "CHI_ADJ"}]
    assert build_file_hints(
        game_id="stellaris", target_lang="zh-CN", texts=["Chinese"], key_infos=key_infos
    ) == [None]
    assert build_file_hints(
        game_id="victoria3", target_lang="en", texts=["Chinese"], key_infos=key_infos
    ) == [None]


def test_prompt_input_uses_h2_metadata_without_raw_key_and_preserves_alignment():
    hints = build_file_hints(
        game_id="victoria3",
        target_lang="zh-CN",
        texts=["Chinese", "Ordinary"],
        key_infos=[{"key_part": "CHI_ADJ"}, {"key_part": "ordinary.key"}],
    )
    file_task = _file_task(
        texts_to_translate=["Chinese", "Ordinary"], semantic_hints=hints
    )
    batch = BatchTask(file_task, 0, 0, 2, file_task.texts_to_translate)

    numbered, batch_hints = _build_numbered_input(batch, file_task.texts_to_translate)

    assert "Semantic hint:" in numbered
    assert '2. Source value: "Ordinary"' in numbered
    assert "CHI_ADJ" not in numbered
    assert "Localization key:" not in numbered
    assert "Simplified Chinese" in prompt_policy("zh-CN", batch_hints)


def test_incremental_task_keeps_dirty_keys_aligned_with_h2_hints(tmp_path):
    task = _build_incremental_file_task(
        filename="sample.yml",
        file_data={"root": "root", "original_lines": []},
        texts=["Ordinary", "Chinese"],
        key_delta_indices=[2, 5],
        dirty_key_infos=[{"key_part": "ordinary.key"}, {"key_part": "CHI_ADJ"}],
        target_lang_info={"code": "zh-CN", "name": "Simplified Chinese"},
        source_lang_info={"code": "en", "name": "English"},
        game_profile={"id": "victoria3"},
        mod_context="",
        selected_provider="openrouter",
        source_path="source",
        lang_dest_dir=tmp_path,
    )

    assert task.semantic_hints[0] is None
    assert "country_adjective_definition" in task.semantic_hints[1]


def test_reference_review_issue_is_human_only_and_not_model_repairable():
    issue = {
        "severity": "human_review",
        "requires_human_review": True,
        "error_code": "vic3_country_adjective_reference_review",
    }

    public, summary = classify_issues([issue])

    assert public[0]["category"] == "human_review"
    assert summary.human_review_items == 1
    assert repairable_issues([issue]) == []
    assert not is_repairable_workshop_issue(issue)
