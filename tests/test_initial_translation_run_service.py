from scripts.core.services import initial_translation_run_service as run_service


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


def test_resolve_provider_model_defaults_gemini_cli_only():
    assert run_service.resolve_provider_model("gemini_cli", None) == "gemini-1.5-flash"
    assert run_service.resolve_provider_model("gemini", None) is None
    assert run_service.resolve_provider_model("gemini_cli", "gemini-2.5-pro") == "gemini-2.5-pro"


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
