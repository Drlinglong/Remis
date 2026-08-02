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


def test_review_mismatch_gets_one_targeted_repair():
    client = FakeClient([
        '[{"original":"Wrong Term","suggestion":"错误","reasoning":"Wrong input.","confidence":0.8}]',
        '[{"original":"Pax Remisia","suggestion":"帕克斯·雷米西亚","reasoning":"采用音译；没有既有词典先例；不确定性低。","confidence":0.8}]',
    ])

    reviews = NeologismMiner(client).review_terms(
        [{"original": "Pax Remisia", "contexts": ["Pax Remisia endures."], "frequency": 2}],
        source_lang="en",
        target_lang="zh-CN",
        game_name="Stellaris",
    )

    assert reviews["Pax Remisia"].suggestion == "帕克斯·雷米西亚"
    assert len(client.calls) == 2
    assert "Pax Remisia" in client.calls[1][0][-1]["content"]
    assert "Wrong Term" in client.calls[1][0][-1]["content"]


def test_review_skips_candidates_with_complete_extraction_advice():
    client = FakeClient([])

    reviews = NeologismMiner(client).review_terms(
        [{
            "original": "Pax Remisia",
            "source_keys": ["events/example.yml::pax"],
            "suggestion": "帕克斯·雷米西亚",
            "reasoning": "已根据源文本完成初步术语提议。",
        }],
        source_lang="en",
        target_lang="zh-CN",
        game_name="Stellaris",
    )

    assert reviews == {}
    assert client.calls == []


def test_review_can_force_fallback_for_a_complete_candidate():
    client = FakeClient([json.dumps([{
        "original": "Pax Remisia",
        "suggestion": "帕克斯·雷米西亚",
        "reasoning": "采用音译；需要复核源文本中的专名上下文。",
        "confidence": 0.84,
    }], ensure_ascii=False)])

    reviews = NeologismMiner(client).review_terms(
        [{
            "original": "Pax Remisia",
            "suggestion": "帕克斯·雷米西亚",
            "reasoning": "已根据源文本完成初步术语提议。",
            "needs_review": True,
        }],
        source_lang="en",
        target_lang="zh-CN",
        game_name="Stellaris",
    )

    assert reviews["Pax Remisia"].confidence == 0.84
    assert len(client.calls) == 1


def test_review_repairs_only_missing_candidate_when_similar_names_are_merged():
    client = FakeClient([
        json.dumps([{
            "original": "The Trickster",
            "suggestion": "诡诈者",
            "reasoning": "采用语义翻译；没有既有词典先例；存在上下文不确定性。",
            "confidence": 0.86,
        }], ensure_ascii=False),
        json.dumps([{
            "original": "Trickster",
            "suggestion": "欺诈者",
            "reasoning": "采用语义翻译；没有既有词典先例；存在上下文不确定性。",
            "confidence": 0.81,
        }], ensure_ascii=False),
    ])
    candidates = [
        {"original": "The Trickster", "contexts": ["The Trickster appears."], "frequency": 3},
        {"original": "Trickster", "contexts": ["Trickster appears."], "frequency": 2},
    ]

    reviews = NeologismMiner(client).review_terms(
        candidates,
        source_lang="en",
        target_lang="zh-CN",
        game_name="Stellaris",
    )

    assert set(reviews) == {"The Trickster", "Trickster"}
    assert len(client.calls) == 2
    repair_content = client.calls[1][0][-1]["content"]
    assert '"original": "Trickster"' in repair_content
    assert "The Trickster" not in repair_content


def test_review_duplicate_response_remains_strict_after_targeted_repair():
    duplicate_review = {
        "original": "Pax Remisia",
        "suggestion": "帕克斯·雷米西亚",
        "reasoning": "采用音译；没有既有词典先例；不确定性低。",
        "confidence": 0.8,
    }
    client = FakeClient([
        json.dumps([duplicate_review, duplicate_review], ensure_ascii=False),
        json.dumps([{
            "original": "Trickster",
            "suggestion": "欺诈者",
            "reasoning": "采用语义翻译；没有既有词典先例；存在上下文不确定性。",
            "confidence": 0.81,
        }], ensure_ascii=False),
    ])

    with pytest.raises(NeologismMiningError, match=r"duplicate=\['Pax Remisia'\]"):
        NeologismMiner(client).review_terms(
            [
                {"original": "Pax Remisia", "contexts": ["Pax Remisia endures."], "frequency": 2},
                {"original": "Trickster", "contexts": ["Trickster appears."], "frequency": 1},
            ],
            source_lang="en",
            target_lang="zh-CN",
            game_name="Stellaris",
        )

    assert len(client.calls) == 2


def test_review_mismatch_error_has_bounded_set_diagnostics_after_one_repair():
    client = FakeClient([
        '[{"original":"Wrong Term","suggestion":"错误","reasoning":"Wrong input.","confidence":0.8}]',
        '[{"original":"Still Wrong","suggestion":"错误","reasoning":"Wrong input.","confidence":0.8}]',
    ])

    with pytest.raises(
        NeologismMiningError,
        match=r"missing=\['Pax Remisia'\].*unexpected=\['Still Wrong'\]",
    ) as error:
        NeologismMiner(client).review_terms(
            [{"original": "Pax Remisia", "contexts": ["Pax Remisia endures."], "frequency": 2}],
            source_lang="en",
            target_lang="zh-CN",
            game_name="Stellaris",
        )

    assert "duplicate=[]" in str(error.value)
    assert "repair_attempted=True" in str(error.value)
    assert len(client.calls) == 2


def test_review_prompt_keeps_suggestion_target_separate_from_review_language():
    client = FakeClient([
        json.dumps([{
            "original": "Pax Remisia",
            "suggestion": "Пакс Ремизия",
            "reasoning": "采用音译以保留专名辨识度；没有既有词典先例。",
            "confidence": 0.82,
        }], ensure_ascii=False)
    ])

    NeologismMiner(client).review_terms(
        [{"original": "Pax Remisia", "contexts": ["Pax Remisia endures."], "frequency": 2}],
        source_lang="en",
        target_lang="ru",
        review_language="zh-CN",
        game_name="Stellaris",
    )

    system_prompt = client.calls[0][0][0]["content"]
    assert "Write every `reasoning` value in zh-CN" in system_prompt
    assert "suggestion must remain in ru" in system_prompt
