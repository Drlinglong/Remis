import json

import pytest

from scripts.core.neologism_miner import NeologismMiner, NeologismMiningError


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate_with_messages(self, messages, temperature=0.1):
        self.calls.append((messages, temperature))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_extract_terms_validates_structured_output():
    client = FakeClient([
        json.dumps([{"original": "Curia Caelestis", "category": "faction", "confidence": 0.94}])
    ])

    terms = NeologismMiner(client).extract_terms("The Curia Caelestis convenes.", game_name="Stellaris")

    assert terms[0].original == "Curia Caelestis"
    assert terms[0].category == "faction"
    assert terms[0].confidence == 0.94


def test_invalid_json_gets_one_bounded_repair_attempt():
    client = FakeClient([
        "not-json",
        '[{"original":"Pax Remisia","category":"concept","confidence":0.8}]',
    ])

    terms = NeologismMiner(client).extract_terms("Pax Remisia endures.")

    assert [term.original for term in terms] == ["Pax Remisia"]
    assert len(client.calls) == 2
    assert "corrected raw JSON array" in client.calls[1][0][-1]["content"]
    assert "validation error" in client.calls[1][0][-1]["content"].lower()


def test_extraction_prompt_lists_every_allowed_category():
    client = FakeClient(["[]"])

    NeologismMiner(client).extract_terms("Pax Remisia endures.")

    system_prompt = client.calls[0][0][0]["content"]
    assert '"person", "place", "faction", "concept", "technology", or "other"' in system_prompt


def test_empty_provider_response_is_a_real_failure():
    with pytest.raises(NeologismMiningError, match="empty response"):
        NeologismMiner(FakeClient([""])).extract_terms("Pax Remisia endures.")


def test_review_requires_exact_candidate_set():
    client = FakeClient([
        '[{"original":"Wrong Term","suggestion":"错误","reasoning":"Wrong input.","confidence":0.8}]'
    ])

    with pytest.raises(NeologismMiningError, match="did not match"):
        NeologismMiner(client).review_terms(
            [{"original": "Pax Remisia", "contexts": ["Pax Remisia endures."], "frequency": 2}],
            source_lang="en",
            target_lang="zh-CN",
            game_name="Stellaris",
        )
