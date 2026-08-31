from types import SimpleNamespace

from scripts.core import feature_policy


def test_stable_build_disables_archive_and_checkpoint_resume(monkeypatch):
    monkeypatch.setattr(feature_policy, "BUILD_PROFILE", SimpleNamespace(channel="stable"))

    assert feature_policy.mod_archive_enabled() is False
    assert feature_policy.checkpoint_resume_enabled() is False


def test_agent_preview_keeps_isolated_archive_and_resume_testing(monkeypatch):
    monkeypatch.setattr(feature_policy, "BUILD_PROFILE", SimpleNamespace(channel="agent-preview"))

    assert feature_policy.mod_archive_enabled() is True
    assert feature_policy.checkpoint_resume_enabled() is True


def test_stable_translation_policy_forces_glossaries_and_fresh_run(monkeypatch):
    monkeypatch.setattr(feature_policy, "BUILD_PROFILE", SimpleNamespace(channel="stable"))
    request = SimpleNamespace(
        translation_context_mode="archive",
        use_project_context=True,
        context_release_id="release-1",
        use_resume=True,
    )

    warning = feature_policy.apply_translation_request_policy(request)

    assert request.translation_context_mode == "glossaries"
    assert request.use_project_context is False
    assert request.context_release_id is None
    assert request.use_resume is False
    assert warning["code"] == "project_archive_disabled"
