import pytest
from pydantic import ValidationError

from scripts.schemas.neologism import MineNeologismsRequest


def test_mining_request_defaults_to_terms_only_for_compatibility():
    payload = MineNeologismsRequest(project_id="project-1", api_provider="local")

    assert payload.analysis_scope == "terms_only"
    assert payload.effective_description_language == "en"


def test_description_language_overrides_legacy_review_language():
    payload = MineNeologismsRequest(
        project_id="project-1",
        api_provider="local",
        review_language="en",
        description_language="zh-CN",
    )

    assert payload.effective_description_language == "zh-CN"


def test_mining_request_rejects_unknown_analysis_scope():
    with pytest.raises(ValidationError, match="analysis_scope"):
        MineNeologismsRequest(
            project_id="project-1", api_provider="local", analysis_scope="script_context"
        )


def test_mining_request_accepts_bounded_explicit_concurrency():
    payload = MineNeologismsRequest(
        project_id="project-1", api_provider="openrouter", concurrency_limit=20,
    )

    assert payload.concurrency_limit == 20

    with pytest.raises(ValidationError, match="concurrency_limit"):
        MineNeologismsRequest(
            project_id="project-1", api_provider="openrouter", concurrency_limit=51,
        )
