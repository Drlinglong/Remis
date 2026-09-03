from scripts.core import feature_policy


def test_production_enables_archive_and_checkpoint_resume():
    assert feature_policy.mod_archive_enabled() is True
    assert feature_policy.checkpoint_resume_enabled() is True


def test_translation_policy_preserves_archive_and_resume():
    from types import SimpleNamespace

    request = SimpleNamespace(
        translation_context_mode="archive",
        use_project_context=True,
        context_release_id="release-1",
        use_resume=True,
    )

    warning = feature_policy.apply_translation_request_policy(request)

    assert request.translation_context_mode == "archive"
    assert request.use_project_context is True
    assert request.context_release_id == "release-1"
    assert request.use_resume is True
    assert warning is None


def test_unknown_build_channel_fails_closed(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        feature_policy,
        "BUILD_PROFILE",
        SimpleNamespace(channel="future-experiment"),
    )

    assert feature_policy.mod_archive_enabled() is False
    assert feature_policy.checkpoint_resume_enabled() is False
