from types import SimpleNamespace

import pytest

from scripts.core.services import embedded_workshop_service
from scripts.core.services.provider_runtime import ProviderRuntimeSnapshot


def _runtime(*, adapter_id: str, model_id: str) -> ProviderRuntimeSnapshot:
    return ProviderRuntimeSnapshot(
        selection_id=f"profile-{adapter_id}",
        adapter_id=adapter_id,
        display_name="Frozen provider",
        model_id=model_id,
        config={
            "base_url": f"https://{adapter_id}.snapshot.example/v1",
            "default_model": model_id,
            "system_prompt_suffix": "frozen instructions",
        },
        api_key="in-memory-secret",
        secret_ref=f"custom_provider_profile:{adapter_id}",
    )


@pytest.mark.asyncio
async def test_follow_primary_uses_runtime_snapshot_after_global_profile_edit(
    monkeypatch, tmp_path
):
    handler_calls = []

    def fake_get_handler(provider_name, *, model_name=None, **kwargs):
        handler_calls.append((provider_name, model_name, kwargs))
        return SimpleNamespace(client=object())

    class FakeAgent:
        def __init__(self, handler):
            self.handler = handler

        async def fix_batch_loop(self, batch, *, game_id, target_lang_code):
            return {"results": [{"status": "failed"} for _ in batch]}

    class FakeExporter:
        OUTPUT_FILENAME = "workshop_issues.json"

        def export_for_output(self, **kwargs):
            return {"issue_count": 0, "issues": [], "issues_path": "issues.json"}

    monkeypatch.setattr(embedded_workshop_service, "get_handler", fake_get_handler)
    monkeypatch.setattr(embedded_workshop_service, "ReflexionFixAgent", FakeAgent)
    monkeypatch.setattr(
        embedded_workshop_service,
        "_load_issues",
        lambda sidecar_path, protected_entries=None: [{"key": "entry-1"}],
    )
    monkeypatch.setattr(
        embedded_workshop_service,
        "_apply_validated_results",
        lambda *args: (0, 1),
    )
    monkeypatch.setattr(
        embedded_workshop_service,
        "WorkshopIssueExportService",
        FakeExporter,
    )
    monkeypatch.setattr(
        "scripts.app_settings.config_manager.get_value",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("runtime execution must not read edited global config")
        ),
    )

    runtime = _runtime(adapter_id="your_favourite_api", model_id="snapshot-model")
    summary = await embedded_workshop_service.run_embedded_workshop(
        output_root=tmp_path / "output",
        source_root=tmp_path / "source",
        project_id="project-1",
        project_name="Demo",
        source_lang_info={"code": "en"},
        target_lang_info={"code": "zh-CN"},
        game_profile={"id": "vic3"},
        workflow="initial",
        config={"follow_primary_settings": True},
        fallback_provider="edited-provider",
        fallback_model="edited-model",
        provider_runtime=runtime,
    )

    assert summary["provider"] == "your_favourite_api"
    assert summary["model"] == "snapshot-model"
    assert handler_calls == [
        (
            "your_favourite_api",
            "snapshot-model",
            {
                "provider_config_snapshot": runtime.config,
                "api_key_override": "in-memory-secret",
            },
        )
    ]


@pytest.mark.asyncio
async def test_independent_workshop_runtime_is_used_when_follow_primary_is_disabled(
    monkeypatch, tmp_path
):
    handler_calls = []

    monkeypatch.setattr(
        embedded_workshop_service,
        "get_handler",
        lambda provider_name, *, model_name=None, **kwargs: (
            handler_calls.append((provider_name, model_name, kwargs))
            or SimpleNamespace(client=object())
        ),
    )
    class FakeAgent:
        def __init__(self, handler):
            self.handler = handler

        async def fix_batch_loop(self, batch, *, game_id, target_lang_code):
            return {"results": []}

    monkeypatch.setattr(embedded_workshop_service, "ReflexionFixAgent", FakeAgent)
    monkeypatch.setattr(
        embedded_workshop_service,
        "_load_issues",
        lambda sidecar_path, protected_entries=None: [{"key": "entry-1"}],
    )
    monkeypatch.setattr(
        embedded_workshop_service,
        "_apply_validated_results",
        lambda *args: (0, 0),
    )
    monkeypatch.setattr(
        embedded_workshop_service,
        "WorkshopIssueExportService",
        type(
            "FakeExporter",
            (),
            {
                "OUTPUT_FILENAME": "workshop_issues.json",
                "export_for_output": lambda self, **kwargs: {
                "issue_count": 0,
                "issues": [],
                "issues_path": "issues.json",
                },
            },
        ),
    )

    runtime = _runtime(adapter_id="lm_studio", model_id="workshop-model")
    await embedded_workshop_service.run_embedded_workshop(
        output_root=tmp_path / "output",
        source_root=tmp_path / "source",
        project_id="project-1",
        project_name="Demo",
        source_lang_info={"code": "en"},
        target_lang_info={"code": "zh-CN"},
        game_profile={"id": "vic3"},
        workflow="incremental",
        config={
            "follow_primary_settings": False,
            "api_provider": "edited-provider",
            "api_model": "edited-model",
        },
        fallback_provider="another-edited-provider",
        fallback_model="another-edited-model",
        provider_runtime=runtime,
    )

    assert handler_calls[0][0:2] == ("lm_studio", "workshop-model")
