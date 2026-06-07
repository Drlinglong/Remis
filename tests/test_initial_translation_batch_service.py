import logging

from scripts.core.services import initial_translation_batch_service as batch_service


def test_resolve_max_workers_honors_explicit_limit():
    assert batch_service.resolve_max_workers(3, "local") == 3
    assert batch_service.resolve_max_workers(0, "gemini") >= 1


def test_resolve_max_workers_serializes_local_providers(monkeypatch):
    monkeypatch.setattr(batch_service, "RECOMMENDED_MAX_WORKERS", 8)

    assert batch_service.resolve_max_workers(None, "local") == 1
    assert batch_service.resolve_max_workers(None, "ollama") == 1
    assert batch_service.resolve_max_workers(None, "gemini") == 8


def test_summarize_batch_warning_codes_handles_dicts_and_objects():
    class WarningObject:
        code = "placeholder_mismatch"

    summary = batch_service.summarize_batch_warning_codes(
        [
            {"type": "api_error"},
            {"level": "warning"},
            WarningObject(),
            object(),
            {"type": "api_error"},
            {"level": "warning", "source_term": "泰尔紫", "target_term": "Tyrian Purple"},
        ]
    )

    assert summary == "api_error, glossary_mismatch, placeholder_mismatch, warning"


def test_log_batch_warnings_outputs_details(caplog):
    warnings = [
        {
            "level": "warning",
            "batch_id": 0,
            "source_term": "泰尔紫",
            "target_term": "Tyrian Purple",
            "source_count": 1,
            "translated_count": 0,
            "message": "Expected glossary term was not used.",
        }
    ]

    with caplog.at_level(logging.WARNING):
        batch_service.log_batch_warnings("remis_demo.yml", warnings)

    messages = [record.getMessage() for record in caplog.records]
    assert any("glossary_mismatch" in message for message in messages)
    assert any("泰尔紫(1) -> Tyrian Purple(0)" in message for message in messages)
    assert any("file=remis_demo.yml" in message for message in messages)


def test_log_batch_warnings_skips_empty_warnings(caplog):
    with caplog.at_level(logging.WARNING):
        batch_service.log_batch_warnings("file.yml", [])

    assert not caplog.records


def test_temporary_rpm_limit_restores_previous_value(monkeypatch):
    class FakeRateLimiter:
        rpm = 40

        def __init__(self):
            self.updates = []

        def update_rpm(self, value):
            self.updates.append(value)
            self.rpm = value

    fake_rate_limiter = FakeRateLimiter()
    monkeypatch.setattr(batch_service, "rate_limiter", fake_rate_limiter)

    with batch_service.temporary_rpm_limit(12):
        assert fake_rate_limiter.rpm == 12

    assert fake_rate_limiter.rpm == 40
    assert fake_rate_limiter.updates == [12, 40]
