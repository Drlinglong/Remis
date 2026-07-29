from scripts.core.services.model_arena_export_service import (
    EXPORT_SCHEMA_VERSION,
    build_model_arena_export,
)


def _bundle():
    return {
        "run_id": "run-1",
        "project_name_snapshot": "Demo",
        "settings": {
            "api_url": "http://localhost:1234/v1",
            "safe": "yes",
        },
        "requests": [
            {
                "system_instruction": "Translate the mod.",
                "prompt_text": (
                    "Translate C:\\Users\\alice\\private\\demo.yml "
                    "with api_key=secret-value"
                ),
                "prompt_sha256": "prompt-hash",
                "completion_text_before_parse": '["译文"]',
                "completion_source": "assistant_content",
                "reasoning_content": "private chain of thought",
            }
        ],
        "samples": [
            {
                "entry_key": "demo.key",
                "relative_file_path": "localisation/demo.yml",
                "source_text": "Original",
                "source_sha256": "source-hash",
                "outputs": [
                    {
                        "translated_text": "Translated",
                        "output_sha256": "output-hash",
                    }
                ],
                "vote": {
                    "verdict": "winner",
                    "note": "Compared locally in J:\\mods\\demo",
                },
            }
        ],
    }


def test_evidence_export_keeps_reviewable_content_and_removes_private_fields():
    artifact = build_model_arena_export(_bundle(), remis_version="3.0.8")

    assert artifact["schema_version"] == EXPORT_SCHEMA_VERSION
    assert artifact["export_mode"] == "evidence"
    body = artifact["arena_run"]
    assert body["requests"][0]["system_instruction"] == "Translate the mod."
    assert body["requests"][0]["completion_text_before_parse"] == '["译文"]'
    assert body["samples"][0]["source_text"] == "Original"
    assert body["samples"][0]["outputs"][0]["translated_text"] == "Translated"
    assert body["samples"][0]["vote"]["note"].startswith("Compared locally")

    rendered = str(artifact)
    assert "demo.key" not in rendered
    assert "localisation/demo.yml" not in rendered
    assert "localhost:1234" not in rendered
    assert "secret-value" not in rendered
    assert "private chain of thought" not in rendered
    assert "C:\\Users\\alice" not in rendered
    assert "J:\\mods\\demo" not in rendered
    assert "[REDACTED_SECRET]" in rendered
    assert "[REDACTED_PATH]" in rendered


def test_summary_only_export_removes_prompt_source_output_and_notes_but_keeps_hashes():
    artifact = build_model_arena_export(_bundle(), mode="summary-only")
    rendered = str(artifact)

    assert artifact["export_mode"] == "summary-only"
    assert "Translate the mod." not in rendered
    assert '["译文"]' not in rendered
    assert "Original" not in rendered
    assert "Translated" not in rendered
    assert "Compared locally" not in rendered
    assert "prompt-hash" in rendered
    assert "source-hash" in rendered
    assert "output-hash" in rendered


def test_export_rejects_unknown_mode():
    try:
        build_model_arena_export({}, mode="full")
    except ValueError as exc:
        assert "Unsupported model arena export mode" in str(exc)
    else:
        raise AssertionError("unknown export mode should fail")
