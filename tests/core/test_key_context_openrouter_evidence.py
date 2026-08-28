from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from scripts.developer_tools.key_context_openrouter_evidence import (
    OpenRouterAttemptError,
    call_openrouter_chat_with_evidence,
)


class FakeResponse:
    def __init__(self, content):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]

    def model_dump(self, **_kwargs):
        return {
            "id": "gen-test",
            "choices": [{"message": {"content": self.choices[0].message.content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.1},
            "openrouter_metadata": {
                "attempts": [{"provider": "TestProvider", "status": 200}]
            },
        }


def make_handler(content):
    raw_http = SimpleNamespace(
        headers={"x-request-id": "req-test", "authorization": "secret"},
        parse=Mock(return_value=FakeResponse(content)),
    )
    create = Mock(return_value=raw_http)
    client = SimpleNamespace(
        api_key="never-serialize-this",
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                with_raw_response=SimpleNamespace(create=create)
            )
        ),
    )
    handler = SimpleNamespace(
        client=client,
        get_provider_config=Mock(return_value={"default_model": "test/model"}),
        _apply_reasoning_to_openai_kwargs=Mock(side_effect=lambda value: value),
    )
    handler.create = create
    return handler


@patch(
    "scripts.developer_tools.key_context_openrouter_evidence._fetch_generation",
    return_value={"http_status": 200, "response": {"data": {"provider_name": "X"}}},
)
def test_success_preserves_usage_routing_and_only_safe_headers(_fetch):
    handler = make_handler(" ok ")
    text, evidence = call_openrouter_chat_with_evidence(
        handler, "p", request_timeout_seconds=17
    )

    assert text == "ok"
    assert evidence["response"]["usage"]["cost"] == 0.1
    assert evidence["response"]["openrouter_metadata"]["attempts"][0]["provider"] == "TestProvider"
    assert evidence["generation"]["response"]["data"]["provider_name"] == "X"
    assert evidence["response_headers"] == {"x-request-id": "req-test"}
    assert "never-serialize-this" not in str(evidence)
    assert handler.create.call_args.kwargs["timeout"] == 17


@patch(
    "scripts.developer_tools.key_context_openrouter_evidence._fetch_generation",
    return_value={"http_status": 200, "response": {"data": {}}},
)
def test_null_content_raises_with_complete_attempt_evidence(_fetch):
    with pytest.raises(OpenRouterAttemptError) as captured:
        call_openrouter_chat_with_evidence(make_handler(None), "p")

    assert captured.value.evidence["response"]["choices"][0]["message"]["content"] is None
    assert captured.value.evidence["response"]["usage"]["prompt_tokens"] == 10
