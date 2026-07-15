from unittest.mock import MagicMock, patch

from scripts.workflows.initial_translate import run
from scripts.utils.system_utils import slugify_to_ascii


def test_english_disguise_configuration_reaches_language_service():
    """The real language name and disguised Paradox key survive orchestration."""
    mod_name = "TestProject_EnglishDisguise"
    source_lang = {"code": "en", "key": "l_english", "name": "English"}
    target_lang = {
        "code": "custom",
        "key": "l_english",
        "folder_prefix": "IT-",
        "name": "Italian",
    }
    game_profile = {
        "id": "victoria3",
        "encoding": "utf-8-sig",
        "source_localization_folder": "localization",
    }
    expected_output_folder = f"IT-{slugify_to_ascii(mod_name)}"
    handler = MagicMock()
    handler.client = MagicMock()

    with (
        patch("scripts.workflows.initial_translate.create_translation_handler", return_value=handler),
        patch("scripts.workflows.initial_translate.load_glossaries_for_run"),
        patch(
            "scripts.workflows.initial_translate.prepare_output_workspace",
            return_value="C:/fake-output",
        ) as prepare_workspace,
        patch(
            "scripts.workflows.initial_translate.discover_files",
            return_value=[{"path": "C:/source/test_l_english.yml"}],
        ),
        patch(
            "scripts.workflows.initial_translate.read_files_for_backup",
            return_value=[{"path": "C:/source/test_l_english.yml", "texts_to_translate": ["text"]}],
        ),
        patch("scripts.workflows.initial_translate.get_chunk_size_for_provider", return_value=20),
        patch("scripts.workflows.initial_translate.calculate_total_batches", return_value=1),
        patch("scripts.workflows.initial_translate.create_source_snapshot", return_value=(1, 2)),
        patch("scripts.workflows.initial_translate.run_language_translation") as run_language,
        patch("scripts.workflows.initial_translate.finalize_workflow_run"),
    ):
        run(
            mod_name=mod_name,
            source_lang=source_lang,
            target_languages=[target_lang],
            game_profile=game_profile,
            mod_context="",
            selected_glossary_ids=[],
            model_name="gemini-pro",
            use_glossary=True,
            custom_lang_config=target_lang,
        )

    prepare_workspace.assert_called_once_with(mod_name, expected_output_folder, game_profile)
    run_language.assert_called_once()
    call = run_language.call_args.kwargs
    assert call["output_folder_name"] == expected_output_folder
    assert call["target_lang"]["key"] == "l_english"
    assert call["target_lang"]["name"] == "Italian"
    assert call["handler"] is handler
