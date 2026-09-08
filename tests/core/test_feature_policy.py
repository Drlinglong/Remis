from types import SimpleNamespace

from scripts.core import feature_policy


def test_production_enables_archive_and_checkpoint_resume():
    assert feature_policy.mod_archive_enabled() is True
    assert feature_policy.checkpoint_resume_enabled() is True


def test_translation_policy_preserves_archive_and_resume():
    from types import SimpleNamespace

def test_archive_ab_review_requires_preview_and_explicit_developer_flag(monkeypatch):
    monkeypatch.setattr(feature_policy, "BUILD_PROFILE", SimpleNamespace(channel="agent-preview"))
    monkeypatch.delenv("REMIS_ENABLE_ARCHIVE_AB_REVIEW", raising=False)
    assert feature_policy.archive_ab_review_enabled() is False
    monkeypatch.setenv("REMIS_ENABLE_ARCHIVE_AB_REVIEW", "1")
    assert feature_policy.archive_ab_review_enabled() is True


def test_archive_ab_capability_is_closed_without_flag(monkeypatch):
    monkeypatch.setattr(feature_policy, "BUILD_PROFILE", SimpleNamespace(channel="stable"))
    monkeypatch.delenv("REMIS_ENABLE_ARCHIVE_AB_REVIEW", raising=False)
    capabilities = feature_policy.apply_agent_capability_policy({
        "resume_from_checkpoint": {"supported": True},
        "archive_ab_review": {"supported": True},
        "read_context_release": {"supported": True},
        "read_effective_context": {"supported": True},
        "read_context_traceability": {"supported": True},
        "remove_context_archive": {"supported": True},
        "context_analysis": {"supported": True},
    })
    assert capabilities["archive_ab_review"]["supported"] is False

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
