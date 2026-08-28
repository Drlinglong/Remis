"""Cost projections for the key-context benchmark; no provider calls."""

from __future__ import annotations

from typing import Any


LUNA_BATCH_MODEL = "openai/gpt-5.6-luna:batch"
LUNA_BATCH_PRICING = {
    "input_usd_per_million": 0.10,
    "output_usd_per_million": 0.60,
    "cache_read_usd_per_million": 0.01,
    "source_url": "https://openrouter.ai/openai/gpt-5.6-luna:batch",
    "verified_on": "2026-08-28",
}
AVENTINE_LUNA_RATIOS = {
    "no_reasoning_history": {
        "input_tokens": 24_995,
        "output_tokens": 7_079,
        "reasoning_tokens": 0,
        "source": (
            "J:/remis-aventine/benchmark_results/"
            "openrouter-stability-2026-08-01"
        ),
    },
    "high_reasoning_history": {
        "input_tokens": 24_995,
        "output_tokens": 24_109,
        "reasoning_tokens": 16_868,
        "source": (
            "J:/remis-aventine/benchmark_results/"
            "openrouter-high-reasoning-2026-08-01"
        ),
    },
}


def estimate_luna_batch_cost(prompt_estimate: dict[str, Any]) -> dict[str, Any]:
    total_input = sum(
        int(cell["estimated_input_tokens"])
        for cell in prompt_estimate.get("cells", [])
    )
    scenarios = []
    for name, evidence in AVENTINE_LUNA_RATIOS.items():
        output_ratio = evidence["output_tokens"] / evidence["input_tokens"]
        projected_output = round(total_input * output_ratio)
        input_cost = (
            total_input
            * LUNA_BATCH_PRICING["input_usd_per_million"]
            / 1_000_000
        )
        output_cost = (
            projected_output
            * LUNA_BATCH_PRICING["output_usd_per_million"]
            / 1_000_000
        )
        scenarios.append(
            {
                "profile": name,
                "historical_output_input_ratio": round(output_ratio, 6),
                "historical_reasoning_output_share": round(
                    evidence["reasoning_tokens"] / evidence["output_tokens"], 6
                )
                if evidence["output_tokens"]
                else 0.0,
                "estimated_input_tokens": total_input,
                "projected_billed_output_tokens": projected_output,
                "estimated_input_cost_usd": round(input_cost, 6),
                "estimated_output_cost_usd": round(output_cost, 6),
                "estimated_total_cost_usd": round(input_cost + output_cost, 6),
                "historical_evidence": evidence,
            }
        )
    return {
        "model": LUNA_BATCH_MODEL,
        "pricing": LUNA_BATCH_PRICING,
        "cache_assumption": (
            "Conservative: all input is charged at the standard batch input rate; "
            "no cache-read discount is assumed."
        ),
        "reasoning_accounting": (
            "Aventine reasoning_tokens are a subset of billed output_tokens and are "
            "not added a second time."
        ),
        "medium_reasoning_boundary": (
            "No verified Aventine medium-reasoning ratio is available. Do not invent "
            "one; use the high-reasoning scenario as the conservative planning bound."
        ),
        "production_billing_boundary": (
            "This is a tokenizer-and-history projection, not an OpenRouter invoice."
        ),
        "scenarios": scenarios,
    }
