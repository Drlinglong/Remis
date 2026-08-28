from scripts.developer_tools.key_context_cost_estimate import (
    estimate_luna_batch_cost,
)


def test_luna_batch_cost_uses_frozen_ratios_without_double_counting_reasoning():
    estimate = estimate_luna_batch_cost(
        {"cells": [{"estimated_input_tokens": 41_724}]}
    )
    scenarios = {item["profile"]: item for item in estimate["scenarios"]}

    assert estimate["model"] == "openai/gpt-5.6-luna:batch"
    assert scenarios["no_reasoning_history"]["projected_billed_output_tokens"] == 11_817
    assert scenarios["high_reasoning_history"]["projected_billed_output_tokens"] == 40_245
    assert scenarios["high_reasoning_history"]["estimated_total_cost_usd"] == 0.028319
