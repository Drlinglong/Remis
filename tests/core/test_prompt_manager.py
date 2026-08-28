from scripts.core import prompt_manager as prompt_manager_module


def _install_profiles(monkeypatch):
    profile = {
        "id": "victoria3",
        "prompt_template": "victoria-system",
        "format_prompt": "victoria-format",
    }
    monkeypatch.setattr(prompt_manager_module, "GAME_PROFILES", {"1": profile})
    monkeypatch.setattr(
        prompt_manager_module,
        "GAME_PROFILES_BY_ID",
        {"victoria3": profile},
    )
    return profile


def test_effective_prompts_resolve_canonical_game_id(monkeypatch):
    _install_profiles(monkeypatch)
    monkeypatch.setattr(
        prompt_manager_module.config_manager,
        "get_value",
        lambda _key, default=None: default,
    )

    assert (
        prompt_manager_module.PromptManager.get_effective_prompt("victoria3")
        == "victoria-system"
    )
    assert (
        prompt_manager_module.PromptManager.get_effective_format_prompt("victoria3")
        == "victoria-format"
    )


def test_canonical_override_precedes_legacy_numeric_override(monkeypatch):
    _install_profiles(monkeypatch)
    overrides = {
        "prompt_overrides": {"1": "legacy-system", "victoria3": "canonical-system"},
        "format_prompt_overrides": {
            "1": "legacy-format",
            "victoria3": "canonical-format",
        },
    }
    monkeypatch.setattr(
        prompt_manager_module.config_manager,
        "get_value",
        lambda key, default=None: overrides.get(key, default),
    )

    assert (
        prompt_manager_module.PromptManager.get_effective_prompt("victoria3")
        == "canonical-system"
    )
    assert (
        prompt_manager_module.PromptManager.get_effective_format_prompt("victoria3")
        == "canonical-format"
    )


def test_legacy_numeric_override_remains_compatible(monkeypatch):
    _install_profiles(monkeypatch)
    overrides = {
        "prompt_overrides": {"1": "legacy-system"},
        "format_prompt_overrides": {"1": "legacy-format"},
    }
    monkeypatch.setattr(
        prompt_manager_module.config_manager,
        "get_value",
        lambda key, default=None: overrides.get(key, default),
    )

    assert (
        prompt_manager_module.PromptManager.get_effective_prompt("victoria3")
        == "legacy-system"
    )
    assert (
        prompt_manager_module.PromptManager.get_effective_format_prompt("victoria3")
        == "legacy-format"
    )
