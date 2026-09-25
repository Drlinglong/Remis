from scripts.core.services import initial_translation_run_service as run_service
from scripts.workflows import initial_translate


def test_build_run_plan_for_single_language_keeps_target_prefix():
    plan = run_service.build_run_plan(
        "My Cool Mod",
        [{"code": "ja", "name": "Japanese", "folder_prefix": "ja-"}],
    )

    assert plan.is_batch_mode is False
    assert plan.output_folder_name == "ja-my_cool_mod"
    assert plan.primary_target_lang == {"code": "ja", "name": "Japanese", "folder_prefix": "ja-"}


def test_build_run_plan_for_multi_language_uses_multilanguage_folder(monkeypatch):
    monkeypatch.setitem(run_service.LANGUAGES, "1", {"code": "en", "name": "English"})

    plan = run_service.build_run_plan(
        "My Cool Mod",
        [{"code": "en", "name": "English"}, {"code": "ja", "name": "Japanese"}],
    )

    assert plan.is_batch_mode is True
    assert plan.output_folder_name == "Multilanguage-my_cool_mod"
    assert plan.primary_target_lang == {"code": "en", "name": "English"}


def test_project_output_identity_separates_same_named_source_folders():
    languages = [{"code": "zh-CN", "folder_prefix": "zh-CN-"}]

    first = run_service.build_run_plan("same-mod", languages, project_id="project-a")
    second = run_service.build_run_plan("same-mod", languages, project_id="project-b")

    assert first.output_folder_name != second.output_folder_name
    assert first.output_folder_name.startswith("zh-CN-same-mod--project-a-")
    assert second.output_folder_name.startswith("zh-CN-same-mod--project-b-")


def test_recovery_output_identity_preserves_existing_checkpoint_folder():
    plan, folder_name, _primary = initial_translate._build_run_plan(
        "same-mod",
        [{"code": "zh-CN", "folder_prefix": "zh-CN-"}],
        "project-a",
        {"output_dir": "D:/legacy-output/zh-CN-same-mod"},
    )

    assert folder_name == "zh-CN-same-mod"
    assert plan.output_folder_name == "zh-CN-same-mod"


def test_resolve_provider_model_keeps_configured_model_only():
    assert run_service.resolve_provider_model("gemini", None) is None
    assert run_service.resolve_provider_model("gemini", "gemini-3-pro-preview") == "gemini-3-pro-preview"


def test_create_translation_handler_returns_none_without_client(monkeypatch):
    class HandlerWithoutClient:
        client = None

    monkeypatch.setattr(
        run_service.api_handler,
        "get_handler",
        lambda selected_provider, model_name=None: HandlerWithoutClient(),
    )

    assert run_service.create_translation_handler("local", "model") is None


def test_create_translation_handler_returns_initialized_handler(monkeypatch):
    class Handler:
        client = object()

    handler = Handler()
    monkeypatch.setattr(
        run_service.api_handler,
        "get_handler",
        lambda selected_provider, model_name=None: handler,
    )

    assert run_service.create_translation_handler("local", "model") is handler
