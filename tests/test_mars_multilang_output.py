import os
from types import SimpleNamespace

from scripts.core.services import initial_translation_file_service
from scripts.core.services import translation_task_runtime
from scripts.workflows import initial_translate


MARS_PROFILE = {"id": "surviving_mars", "format_adapter_id": "surviving_mars_csv"}
FRENCH = {"code": "fr", "name": "French", "folder_prefix": "fr-", "key": "l_french"}
GERMAN = {"code": "de", "name": "German", "folder_prefix": "de-", "key": "l_german"}


def test_mars_batch_outputs_use_stable_per_language_folders(monkeypatch, tmp_path):
    monkeypatch.setattr(translation_task_runtime, "DEST_DIR", str(tmp_path))
    assert translation_task_runtime.get_output_directories(
        "prepared", [FRENCH, GERMAN], MARS_PROFILE
    ) == [str(tmp_path / "fr-prepared"), str(tmp_path / "de-prepared")]

    # Other game batch output semantics stay shared and unchanged.
    assert translation_task_runtime.get_output_directories(
        "prepared", [FRENCH, GERMAN], {"id": "victoria3"}
    ) == [str(tmp_path / "Multilanguage-prepared")]


def test_mars_batch_dispatch_keeps_checkpoint_root_separate_from_language_outputs(
    monkeypatch, tmp_path,
):
    calls = []
    monkeypatch.setattr(initial_translate, "DEST_DIR", str(tmp_path))
    monkeypatch.setattr(
        initial_translate,
        "run_language_translation",
        lambda **kwargs: calls.append(kwargs) or {"target_lang": kwargs["target_lang"]["code"]},
    )
    shared = {
        "target_languages": [FRENCH, GERMAN],
        "mod_name": "prepared",
        "source_lang": {"code": "en"},
        "game_profile": MARS_PROFILE,
        "mod_context": "",
        "handler": object(),
        "output_folder_name": "Multilanguage-prepared",
        "output_dir_path": str(tmp_path / "Multilanguage-prepared"),
        "selected_provider": "provider",
        "model_name": None,
        "all_files_content": [],
        "total_batches": 0,
        "effective_chunk_size": 1,
        "progress_callback": None,
        "project_id": "project-1",
        "version_id": 1,
        "override_path": None,
        "use_resume": True,
        "concurrency_limit": 1,
        "rpm_limit": None,
        "batch_size_limit": None,
        "embedded_workshop": None,
        "reference_reuse": None,
        "source_context_overlap": 0,
        "context_selection": None,
        "provider_runtime": None,
        "should_cancel": None,
        "task_id": "task-1",
        "run_id": "run-1",
        "source_root": "source",
        "source_snapshot_hash": "hash",
        "config_fingerprint": "config",
    }

    initial_translate._run_language_targets(**shared)

    expected_names = [
        translation_task_runtime.get_output_folder_names(
            "prepared", [language], "project-1", MARS_PROFILE
        )[0]
        for language in (FRENCH, GERMAN)
    ]
    other_project_names = [
        translation_task_runtime.get_output_folder_names(
            "prepared", [language], "project-2", MARS_PROFILE
        )[0]
        for language in (FRENCH, GERMAN)
    ]
    assert expected_names != other_project_names
    assert [call["output_folder_name"] for call in calls] == expected_names
    assert [call["output_dir_path"] for call in calls] == [
        os.path.join(str(tmp_path), folder_name)
        for folder_name in expected_names
    ]
    assert [call["target_lang"]["_checkpoint_output_dir_path"] for call in calls] == [
        shared["output_dir_path"], shared["output_dir_path"],
    ]

    monkeypatch.setattr(initial_translation_file_service, "DEST_DIR", str(tmp_path))
    written = {}
    for language in (FRENCH, GERMAN):
        task = SimpleNamespace(file_path="ModTexts.csv", filename="ModTexts.csv")
        destination = initial_translation_file_service.build_dest_dir(
            task,
            language,
            f"{language['folder_prefix']}prepared",
            MARS_PROFILE,
        )
        os.makedirs(destination, exist_ok=True)
        path = os.path.join(destination, "ModTexts.csv")
        with open(path, "w", encoding="utf-8") as output:
            output.write(language["code"])
        written[language["code"]] = path

    assert written["fr"] != written["de"]
    assert open(written["fr"], encoding="utf-8").read() == "fr"
    assert open(written["de"], encoding="utf-8").read() == "de"
