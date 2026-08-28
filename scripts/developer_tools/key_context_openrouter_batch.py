"""Build an auditable OpenRouter Batch API manifest without submitting it."""

from __future__ import annotations

import hashlib
from typing import Any


BATCH_MODEL = "openai/gpt-5.6-luna:batch"
REQUEST_MODEL = "openai/gpt-5.6-luna"


def build_openrouter_batch_manifest(
    rendered: list[dict[str, Any]], reasoning_effort: str
) -> dict[str, Any]:
    if reasoning_effort not in {"medium", "high"}:
        raise ValueError("Batch reasoning effort must be medium or high")
    requests = []
    request_index = []
    for item in rendered:
        identity = (
            f"{item['case_id']}:{item['arm_id']}:{item['repetition']}:"
            f"{item['prompt_sha256']}"
        )
        custom_id = "remis-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
        requests.append(
            {
                "custom_id": custom_id,
                "body": {
                    "model": REQUEST_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a professional translator for game mods.",
                        },
                        {"role": "user", "content": item["prompt"]},
                    ],
                    "max_completion_tokens": 4000,
                    "reasoning": {
                        "effort": reasoning_effort,
                        "exclude": True,
                    },
                },
            }
        )
        request_index.append(
            {
                "custom_id": custom_id,
                "case_id": item["case_id"],
                "arm_id": item["arm_id"],
                "repetition": item["repetition"],
                "prompt_sha256": item["prompt_sha256"],
            }
        )
    return {
        "schema_version": 1,
        "manifest_type": "openrouter_batch_submission_preview",
        "submission_endpoint": "https://openrouter.ai/api/beta/batches",
        "poll_endpoint_template": (
            "https://openrouter.ai/api/beta/batches/{batch_id}"
        ),
        "batch_model": BATCH_MODEL,
        "request_model": REQUEST_MODEL,
        "reasoning_effort": reasoning_effort,
        "retention_warning": (
            "OpenRouter states that batch inputs and results are retained for 30 days."
        ),
        "request_count": len(requests),
        "payload": {
            "endpoint": "/v1/chat/completions",
            "model": REQUEST_MODEL,
            "requests": requests,
        },
        "request_index": request_index,
    }
