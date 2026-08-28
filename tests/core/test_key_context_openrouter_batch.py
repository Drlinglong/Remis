from scripts.developer_tools.key_context_openrouter_batch import (
    build_openrouter_batch_manifest,
)


def test_batch_manifest_uses_real_batch_endpoint_and_explicit_reasoning():
    manifest = build_openrouter_batch_manifest(
        [
            {
                "case_id": "case-1",
                "arm_id": "A",
                "repetition": 1,
                "prompt": "translate this",
                "prompt_sha256": "a" * 64,
            }
        ],
        "high",
    )

    assert manifest["submission_endpoint"].endswith("/api/beta/batches")
    assert manifest["batch_model"] == "openai/gpt-5.6-luna:batch"
    assert manifest["request_count"] == 1
    body = manifest["payload"]["requests"][0]["body"]
    assert body["model"] == "openai/gpt-5.6-luna"
    assert body["reasoning"] == {"effort": "high", "exclude": True}
    assert "api_key" not in str(manifest).lower()
