from scripts.core.services.workshop_description_generation_service import (
    WorkshopDescriptionGenerationService,
)


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "response": {
                "publishedfiledetails": [
                    {"result": 1, "description": "[h1]Original[/h1]"}
                ]
            }
        }


class FakeHandler:
    client = object()

    def __init__(self):
        self.prompt = ""

    def generate_with_messages(self, messages, temperature):
        self.prompt = messages[-1]["content"]
        self.temperature = temperature
        return "[h1]本地化标题[/h1]"


def test_generate_reads_steam_and_returns_auditable_candidate():
    handler = FakeHandler()
    seen = {}

    def fake_post(url, *, data, timeout):
        seen.update(url=url, data=data, timeout=timeout)
        return FakeResponse()

    service = WorkshopDescriptionGenerationService(
        handler_factory=lambda provider, model_name: handler,
        http_post=fake_post,
    )

    result = service.generate(
        workshop_item_id="3538617386",
        user_template="[b]Remis[/b]",
        target_language_name="简体中文",
        provider="lm_studio",
        model="google/gemma-4-31b-qat",
    )

    assert seen["data"]["publishedfileids[0]"] == "3538617386"
    assert seen["timeout"] == 20
    assert result.bbcode == "[h1]本地化标题[/h1]"
    assert result.provider == "lm_studio"
    assert result.model == "google/gemma-4-31b-qat"
    assert len(result.source_description_sha256) == 64
    assert "Current Steam Workshop description" in handler.prompt
    assert "简体中文" in handler.prompt
    assert handler.temperature == 0.2
