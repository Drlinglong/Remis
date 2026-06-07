import os

from scripts.core.services import initial_translation_workshop_service as workshop_service


def test_export_workshop_issues_uses_initial_workflow_contract(monkeypatch, tmp_path):
    calls = []

    class FakeExporter:
        def export_for_output(self, **kwargs):
            calls.append(kwargs)
            return {"issue_count": 2, "issues_path": "issues.json"}

    monkeypatch.setattr(workshop_service, "SOURCE_DIR", str(tmp_path / "source"))
    monkeypatch.setattr(workshop_service, "WorkshopIssueExportService", lambda: FakeExporter())
    monkeypatch.setattr(workshop_service, "resolve_archive_mod_name", lambda mod_name, project_id=None: "Project Name")

    workshop_service.export_workshop_issues_for_language(
        output_dir_path=str(tmp_path / "dest" / "zh-CN-MyMod"),
        override_path=None,
        mod_name="MyMod",
        project_id="project-1",
        source_lang={"code": "en"},
        target_lang={"code": "zh-CN"},
        game_profile={"id": "vic3"},
        dynamic_valid_tags=["tag_a"],
    )

    assert calls == [
        {
            "output_root": str(tmp_path / "dest" / "zh-CN-MyMod"),
            "source_root": os.path.join(str(tmp_path / "source"), "MyMod"),
            "source_lang_info": {"code": "en"},
            "target_lang_info": {"code": "zh-CN"},
            "game_profile": {"id": "vic3"},
            "workflow": "initial",
            "project_name": "Project Name",
            "project_id": "project-1",
            "dynamic_valid_tags": ["tag_a"],
        }
    ]


def test_run_embedded_workshop_disabled_reports_skip():
    progress_events = []

    workshop_service.run_embedded_workshop_for_language(
        embedded_workshop={"enabled": False},
        output_dir_path="out",
        override_path=None,
        mod_name="MyMod",
        project_id="project-1",
        source_lang={"code": "en"},
        target_lang={"code": "zh-CN"},
        game_profile={"id": "vic3"},
        selected_provider="gemini",
        model_name="gemini-2.5-flash",
        update_progress_callback=lambda **payload: progress_events.append(payload),
    )

    assert progress_events == [
        {"log_message": "[ZH-CN] Smart Workshop skipped: disabled."}
    ]


def test_run_embedded_workshop_bridges_progress_and_completion(monkeypatch, tmp_path):
    progress_events = []
    run_calls = []

    async def fake_run_embedded_workshop(**kwargs):
        run_calls.append(kwargs)
        kwargs["progress_callback"]({
            "stage": "Scanning",
            "message": "scan started",
            "workshop_progress": {"detected_count": 4, "processed_count": 1, "reflection_round": 1},
        })
        return {
            "detected_count": 4,
            "fixed_count": 3,
            "failed_count": 1,
            "remaining_count": 1,
            "provider": "gemini",
            "model": "gemini-2.5-flash",
        }

    monkeypatch.setattr(workshop_service, "SOURCE_DIR", str(tmp_path / "source"))
    monkeypatch.setattr(workshop_service, "resolve_archive_mod_name", lambda mod_name, project_id=None: "Project Name")
    monkeypatch.setattr(workshop_service, "run_embedded_workshop", fake_run_embedded_workshop)

    workshop_service.run_embedded_workshop_for_language(
        embedded_workshop={"enabled": True, "follow_primary_settings": True},
        output_dir_path=str(tmp_path / "dest"),
        override_path=None,
        mod_name="MyMod",
        project_id="project-1",
        source_lang={"code": "en"},
        target_lang={"code": "zh-CN"},
        game_profile={"id": "vic3"},
        selected_provider="gemini",
        model_name="gemini-2.5-flash",
        concurrency_limit=2,
        batch_size_limit=5,
        rpm_limit=40,
        dynamic_valid_tags=["tag_a"],
        update_progress_callback=lambda **payload: progress_events.append(payload),
    )

    assert run_calls[0]["workflow"] == "initial"
    assert run_calls[0]["project_name"] == "Project Name"
    assert run_calls[0]["source_root"] == os.path.join(str(tmp_path / "source"), "MyMod")
    assert run_calls[0]["fallback_concurrency"] == 2
    assert run_calls[0]["fallback_batch_size"] == 5
    assert run_calls[0]["fallback_rpm"] == 40
    assert progress_events == [
        {
            "stage": "Scanning",
            "log_message": "scan started",
            "workshop_progress": {"detected_count": 4, "processed_count": 1, "reflection_round": 1},
        },
        {
            "stage": "Smart Workshop",
            "log_message": "[ZH-CN] Smart Workshop completed: 3/4 fixed, 1 remaining.",
            "format_repair": {
                "detected_count": 4,
                "fixed_count": 3,
                "remaining_count": 1,
                "failed_count": 1,
            },
            "workshop_progress": {
                "detected_count": 4,
                "processed_count": 4,
                "fixed_count": 3,
                "failed_count": 1,
                "reflection_round": 1,
            },
        },
    ]
