import json
import threading
import time

import pytest

from scripts.core.glossary_health_reviewer import (
    GlossaryHealthReviewError,
    GlossaryHealthReviewer,
)


def make_report(entry_count=2, *, issue_code="missing_translation", source_size=0):
    items = [
        {
            "entry_id": f"term-{index}",
            "glossary_id": 7,
            "glossary_name": "Health Test",
            "game_id": "vic3",
            "source": ("术" * source_size) if source_size else f"术语 {index}",
            "current_translation": None,
            "detail": "Missing translation for en.",
        }
        for index in range(entry_count)
    ]
    return {
        "score": 82,
        "entry_count": entry_count,
        "target_lang": "en",
        "issues": [{
            "code": issue_code,
            "severity": "warning",
            "count": entry_count,
            "message": "Entries with missing translations",
            "items": items,
        }],
    }


def advice_for_cases(cases):
    return [
        {
            "case_id": case["case_id"],
            "entry_id": case["entry_id"],
            "issue_code": case["issue_code"],
            "suggested_source": None,
            "suggested_translation": f"{case['source']} translated",
            "recommendation": f"Use the English translation for {case['source']}.",
            "rationale": f"This is a direct translation of {case['source']}.",
            "priority": "high",
            "confidence": 0.9,
        }
        for case in cases
    ]


class BatchHandler:
    def __init__(self):
        self.calls = []

    def generate_with_messages(self, messages, temperature=0.1):
        assert temperature == 0.1
        payload = json.loads(messages[1]["content"])
        self.calls.append((messages, payload))
        return json.dumps(advice_for_cases(payload["cases"]), ensure_ascii=False)


def test_health_reviewer_returns_one_structured_suggestion_per_entry_in_one_batch():
    handler = BatchHandler()

    advice = GlossaryHealthReviewer(handler).review(make_report(2))

    assert len(handler.calls) == 1
    assert [item["entry_id"] for item in advice] == ["term-0", "term-1"]
    assert [item["case_id"] for item in advice] == [
        "missing_translation:term-0",
        "missing_translation:term-1",
    ]
    assert all(item["suggested_translation"] for item in advice)
    assert "Never combine multiple entries" in handler.calls[0][0][0]["content"]


def test_health_reviewer_retries_only_an_invalid_structured_batch_once():
    class RetryHandler(BatchHandler):
        def generate_with_messages(self, messages, temperature=0.1):
            payload = json.loads(messages[1]["content"])
            self.calls.append((messages, payload))
            if len(self.calls) == 1:
                return json.dumps([])
            return json.dumps(advice_for_cases(payload["cases"]), ensure_ascii=False)

    handler = RetryHandler()
    advice = GlossaryHealthReviewer(handler).review(make_report(2))

    assert len(handler.calls) == 2
    assert len(advice) == 2
    assert "previous response" in handler.calls[1][0][-1]["content"]


def test_health_reviewer_rejects_missing_cases_after_one_batch_retry():
    class InvalidHandler(BatchHandler):
        def generate_with_messages(self, messages, temperature=0.1):
            payload = json.loads(messages[1]["content"])
            self.calls.append((messages, payload))
            return json.dumps(advice_for_cases(payload["cases"][:1]), ensure_ascii=False)

    handler = InvalidHandler()
    with pytest.raises(GlossaryHealthReviewError, match="omitted"):
        GlossaryHealthReviewer(handler).review(make_report(2))

    assert len(handler.calls) == 2


def test_health_reviewer_rejects_placeholder_suggestions_that_drop_tokens():
    report = make_report(1, issue_code="placeholder_mismatch")
    report["issues"][0]["items"][0]["source"] = "Army $COUNT$"
    report["issues"][0]["items"][0]["current_translation"] = "Army"

    class InvalidPlaceholderHandler(BatchHandler):
        def generate_with_messages(self, messages, temperature=0.1):
            payload = json.loads(messages[1]["content"])
            self.calls.append((messages, payload))
            advice = advice_for_cases(payload["cases"])
            advice[0]["suggested_translation"] = "Army"
            return json.dumps(advice)

    with pytest.raises(GlossaryHealthReviewError, match="preserve source placeholders"):
        GlossaryHealthReviewer(InvalidPlaceholderHandler()).review(report)


def test_health_reviewer_splits_by_batch_size_and_parallelizes_batches():
    class ConcurrentHandler(BatchHandler):
        def __init__(self):
            super().__init__()
            self.active = 0
            self.max_active = 0
            self.lock = threading.Lock()

        def generate_with_messages(self, messages, temperature=0.1):
            payload = json.loads(messages[1]["content"])
            with self.lock:
                self.calls.append((messages, payload))
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            time.sleep(0.05)
            with self.lock:
                self.active -= 1
            return json.dumps(advice_for_cases(payload["cases"]), ensure_ascii=False)

    handler = ConcurrentHandler()
    reviewer = GlossaryHealthReviewer(handler)
    report = make_report(13)

    plan = reviewer.plan(report)
    advice = reviewer.review(report, concurrency_limit=2)

    assert plan["batch_sizes"] == [12, 1]
    assert len(handler.calls) == 2
    assert len(advice) == 13
    assert handler.max_active == 2


def test_health_reviewer_splits_oversized_cases_by_token_budget():
    plan = GlossaryHealthReviewer.plan(make_report(2, source_size=2500))

    assert plan["batch_count"] == 2
    assert plan["batch_sizes"] == [1, 1]
    assert plan["input_token_budget"] == 2200
