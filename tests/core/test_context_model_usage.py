from scripts.core.services.context_model_usage import ContextModelUsageLedger


class _Handler:
    def __init__(self, records, config):
        self.records = records
        self.config = config

    def consume_model_call_records(self):
        records, self.records = self.records, []
        return records

    def get_provider_config(self):
        return self.config


def test_usage_ledger_preserves_reported_tokens_cost_and_reasoning_profile():
    handler = _Handler([{
        "input_tokens": 100,
        "output_tokens": 25,
        "reasoning_tokens": 10,
        "total_tokens": 125,
        "cost": 0.002,
        "usage_reported": True,
    }], {"reasoning_effort": "high"})
    ledger = ContextModelUsageLedger()

    ledger.capture(handler, "extraction")
    summary = ledger.summary()

    assert summary["call_count"] == 1
    assert summary["reasoning_profile"] == "reasoning_effort=high"
    assert summary["token_usage"]["total_tokens"] == 125
    assert summary["cost"] == {"amount": 0.002, "currency": "USD", "complete": True}
    assert summary["by_phase"]["extraction"]["call_count"] == 1


def test_usage_ledger_marks_partial_provider_metadata_without_estimating_it():
    ledger = ContextModelUsageLedger()
    ledger.capture(_Handler([{
        "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0,
        "total_tokens": 0, "cost": None, "usage_reported": False,
    }], {"enable_thinking": True}), "synthesis")

    summary = ledger.summary()

    assert summary["token_usage"] is None
    assert summary["cost"] is None
    assert "omitted usage for 1/1" in summary["usage_note"]
