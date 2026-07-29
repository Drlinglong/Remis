from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

import pytest

from scripts.core.services.model_arena_execution_service import (
    ArenaContestant,
    ArenaExecutionConfig,
    ArenaHandlerCompletion,
    ArenaSample,
    FAILURE_EMPTY_TRANSLATION,
    FAILURE_HANDLER_CONTRACT,
    FAILURE_ITEM_COUNT,
    FAILURE_PARSE,
    FAILURE_PROVIDER_REQUEST,
    FAILURE_VALIDATION,
    ModelArenaExecutionService,
)
from scripts.utils.post_process_validator import ValidationLevel, ValidationResult


class FakeValidator:
    def __init__(
        self,
        results_by_value: dict[str, list[ValidationResult]] | None = None,
        *,
        fail: bool = False,
    ) -> None:
        self.results_by_value = results_by_value or {}
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def validate_entry(self, **kwargs: Any) -> list[ValidationResult]:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("validator unavailable")
        return self.results_by_value.get(kwargs["value"], [])


class FakeHandler:
    def __init__(
        self,
        contestant_id: str,
        completion: ArenaHandlerCompletion | str | Exception,
        parsed: list[str] | None,
        call_log: list[tuple[Any, ...]],
    ) -> None:
        self.contestant_id = contestant_id
        self.completion = completion
        self.parsed = parsed
        self.call_log = call_log

    @property
    def reasoning_content(self) -> str:
        raise AssertionError("execution service must not inspect reasoning content")

    def execute_model_arena_request(
        self,
        *,
        system_instruction: str | None,
        user_prompt: str,
        effective_parameters: dict[str, Any],
    ) -> ArenaHandlerCompletion | str:
        self.call_log.append(
            (
                "call",
                self.contestant_id,
                system_instruction,
                user_prompt,
                effective_parameters,
            )
        )
        if isinstance(self.completion, Exception):
            raise self.completion
        return self.completion

    def _parse_response(
        self,
        completion_text: str,
        source_texts: list[str],
        target_lang_code: str,
    ) -> list[str] | None:
        self.call_log.append(
            (
                "parse",
                self.contestant_id,
                completion_text,
                tuple(source_texts),
                target_lang_code,
            )
        )
        return self.parsed


class LegacyHandler:
    def __init__(self, parsed: list[str], call_log: list[tuple[Any, ...]]) -> None:
        self.client = object()
        self.parsed = parsed
        self.call_log = call_log

    def _call_api(self, client: object, prompt: str) -> str:
        self.call_log.append(("legacy_call", client, prompt))
        return json.dumps(self.parsed)

    def _parse_response(
        self,
        completion_text: str,
        source_texts: list[str],
        target_lang_code: str,
    ) -> list[str]:
        self.call_log.append(
            ("legacy_parse", completion_text, tuple(source_texts), target_lang_code)
        )
        return self.parsed


@pytest.fixture
def samples() -> list[ArenaSample]:
    return [
        ArenaSample(
            sample_id="sample-1",
            entry_key="event.title",
            source_text="The $RULER$ arrives",
            line_number=10,
        ),
        ArenaSample(
            sample_id="sample-2",
            entry_key="event.desc",
            source_text="A quiet morning",
            line_number=11,
            dynamic_valid_tags=("RULER",),
        ),
    ]


@pytest.fixture
def config() -> ArenaExecutionConfig:
    return ArenaExecutionConfig(
        run_id="run-1",
        game_id="victoria3",
        source_lang={"code": "english", "name": "English"},
        target_lang_code="simp_chinese",
        prompt_text="FROZEN USER PROMPT",
        system_instruction="shared system",
        effective_parameters={
            "temperature": 0.2,
            "api_key": "must-not-be-recorded",
        },
    )


def contestant(
    contestant_id: str,
    *,
    order: int,
    provider: str | None = None,
) -> ArenaContestant:
    return ArenaContestant(
        contestant_id=contestant_id,
        provider_name=provider or f"provider-{contestant_id}",
        model_id=f"model-{contestant_id}",
        execution_order=order,
        effective_parameters={
            "top_p": 0.9,
            "base_url": "https://must-not-be-recorded.invalid",
        },
    )


def make_service(validator: FakeValidator) -> ModelArenaExecutionService:
    tick = iter(index / 10 for index in range(100))
    return ModelArenaExecutionService(
        validator=validator,  # type: ignore[arg-type]
        timer=lambda: next(tick),
        utcnow=lambda: datetime(2026, 7, 26, 1, 2, 3, tzinfo=timezone.utc),
    )


@pytest.mark.parametrize("contestant_count", [2, 3])
def test_executes_contestants_serially_with_the_same_frozen_batch(
    contestant_count: int,
    samples: list[ArenaSample],
    config: ArenaExecutionConfig,
) -> None:
    call_log: list[tuple[Any, ...]] = []
    contestants = [
        contestant(f"c{index}", order=contestant_count - index)
        for index in range(1, contestant_count + 1)
    ]
    completions = {
        item.contestant_id: ArenaHandlerCompletion(
            completion_text_before_parse=json.dumps(
                [f"{item.contestant_id} $RULER$", f"{item.contestant_id} second"]
            ),
            completion_source="assistant_content",
            usage={
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "account_id": "must-not-be-recorded",
            },
            system_instruction=f"actual system {item.contestant_id}",
            user_prompt=config.prompt_text,
            effective_parameters={
                "temperature": 0.2,
                "max_tokens": 200,
                "api_url": "https://must-not-be-recorded.invalid",
            },
        )
        for item in contestants
    }

    def handler_factory(item: ArenaContestant) -> FakeHandler:
        call_log.append(("factory", item.contestant_id))
        return FakeHandler(
            item.contestant_id,
            completions[item.contestant_id],
            [f"{item.contestant_id} $RULER$", f"{item.contestant_id} second"],
            call_log,
        )

    result = make_service(FakeValidator()).execute(
        config=config,
        samples=samples,
        contestants=contestants,
        handler_factory=handler_factory,
    )

    expected_order = [
        item.contestant_id
        for item in sorted(contestants, key=lambda item: item.execution_order)
    ]
    assert [item.contestant_id for item in result.contestants] == expected_order
    assert [event[1] for event in call_log if event[0] == "call"] == expected_order
    assert [event[1] for event in call_log if event[0] == "parse"] == expected_order
    for contestant_id in expected_order:
        factory_index = call_log.index(("factory", contestant_id))
        call_index = next(
            index
            for index, event in enumerate(call_log)
            if event[0:2] == ("call", contestant_id)
        )
        parse_index = next(
            index
            for index, event in enumerate(call_log)
            if event[0:2] == ("parse", contestant_id)
        )
        assert factory_index < call_index < parse_index

    assert result.status == "voting"
    assert len(result.requests) == contestant_count
    assert len(result.outputs) == contestant_count * len(samples)
    assert {request.prompt_text for request in result.requests} == {
        config.prompt_text
    }
    assert {
        event[3] for event in call_log if event[0] == "call"
    } == {config.prompt_text}
    assert all(request.prompt_sha256 for request in result.requests)
    assert all(request.completion_sha256 for request in result.requests)
    recorded_request = next(
        request
        for request in result.requests
        if request.contestant_id == f"c{contestant_count}"
    )
    assert recorded_request.completion_source == "assistant_content"
    assert recorded_request.completion_text_before_parse
    assert recorded_request.system_instruction == (
        f"actual system c{contestant_count}"
    )
    assert dict(recorded_request.effective_parameters) == {
        "temperature": 0.2,
        "max_tokens": 200,
    }
    assert dict(recorded_request.usage) == {
        "prompt_tokens": 20,
        "completion_tokens": 10,
    }
    assert json.loads(json.dumps(result.to_dict()))["status"] == "voting"


def test_rejects_adapter_prompt_drift_after_preserving_request_evidence(
    samples: list[ArenaSample],
    config: ArenaExecutionConfig,
) -> None:
    call_log: list[tuple[Any, ...]] = []

    def handler_factory(item: ArenaContestant) -> FakeHandler:
        return FakeHandler(
            item.contestant_id,
            ArenaHandlerCompletion(
                '["ok $RULER$", "ok"]',
                user_prompt=(
                    "CHANGED PROMPT"
                    if item.contestant_id == "drift"
                    else config.prompt_text
                ),
            ),
            ["ok $RULER$", "ok"],
            call_log,
        )

    result = make_service(FakeValidator()).execute(
        config=config,
        samples=samples,
        contestants=[
            contestant("drift", order=1),
            contestant("good", order=2),
        ],
        handler_factory=handler_factory,
    )

    drift = next(
        item for item in result.contestants if item.contestant_id == "drift"
    )
    request = next(
        item for item in result.requests if item.contestant_id == "drift"
    )
    assert result.status == "partial_failed"
    assert drift.failure_code == FAILURE_HANDLER_CONTRACT
    assert request.prompt_text == "CHANGED PROMPT"
    assert request.failure_code == FAILURE_HANDLER_CONTRACT
    assert not any(
        event[0:2] == ("parse", "drift") for event in call_log
    )


def test_provider_failure_is_partial_and_never_falls_back_to_source(
    samples: list[ArenaSample],
    config: ArenaExecutionConfig,
) -> None:
    call_log: list[tuple[Any, ...]] = []
    responses = {
        "good": (
            ArenaHandlerCompletion('["好 $RULER$", "清晨"]'),
            ["好 $RULER$", "清晨"],
        ),
        "bad": (RuntimeError("provider unavailable"), None),
    }

    def handler_factory(item: ArenaContestant) -> FakeHandler:
        completion, parsed = responses[item.contestant_id]
        return FakeHandler(item.contestant_id, completion, parsed, call_log)

    result = make_service(FakeValidator()).execute(
        config=config,
        samples=samples,
        contestants=[
            contestant("bad", order=1),
            contestant("good", order=2),
        ],
        handler_factory=handler_factory,
    )

    assert result.status == "partial_failed"
    bad = next(item for item in result.contestants if item.contestant_id == "bad")
    assert bad.status == "failed"
    assert bad.failure_code == FAILURE_PROVIDER_REQUEST
    assert bad.request_count == 1
    assert bad.hard_error_occurrences == 0
    assert bad.affected_sample_count == 0
    bad_outputs = [
        output for output in result.outputs if output.contestant_id == "bad"
    ]
    assert all(output.translated_text is None for output in bad_outputs)
    assert all(
        output.translated_text not in {sample.source_text for sample in samples}
        for output in bad_outputs
    )
    assert [event[1] for event in call_log if event[0] == "call"] == [
        "bad",
        "good",
    ]


def test_legacy_production_handler_contract_calls_api_once_per_contestant(
    samples: list[ArenaSample],
    config: ArenaExecutionConfig,
) -> None:
    call_log: list[tuple[Any, ...]] = []

    result = make_service(FakeValidator()).execute(
        config=config,
        samples=samples,
        contestants=[
            contestant("c1", order=1),
            contestant("c2", order=2),
        ],
        handler_factory=lambda item: LegacyHandler(
            [f"{item.contestant_id} $RULER$", item.contestant_id],
            call_log,
        ),
    )

    assert result.status == "voting"
    assert len(
        [event for event in call_log if event[0] == "legacy_call"]
    ) == 2
    assert all(
        event[2] == config.prompt_text
        for event in call_log
        if event[0] == "legacy_call"
    )
    assert {
        request.completion_source for request in result.requests
    } == {"assistant_content"}


def test_explicit_retry_subset_only_calls_the_failed_contestants_supplied(
    samples: list[ArenaSample],
    config: ArenaExecutionConfig,
) -> None:
    call_log: list[tuple[Any, ...]] = []

    result = make_service(FakeValidator()).execute(
        config=config,
        samples=samples,
        contestants=[contestant("failed-before", order=1)],
        handler_factory=lambda item: FakeHandler(
            item.contestant_id,
            ArenaHandlerCompletion('["fixed $RULER$", "fixed"]'),
            ["fixed $RULER$", "fixed"],
            call_log,
        ),
        retry_subset=True,
    )

    assert result.status == "voting"
    assert [event[1] for event in call_log if event[0] == "call"] == [
        "failed-before"
    ]


@pytest.mark.parametrize(
    ("bad_parsed", "expected_failure"),
    [
        (None, FAILURE_PARSE),
        (["only one"], FAILURE_ITEM_COUNT),
        (["valid $RULER$", ""], FAILURE_EMPTY_TRANSLATION),
    ],
)
def test_parse_count_and_empty_failures_have_stable_codes(
    bad_parsed: list[str] | None,
    expected_failure: str,
    samples: list[ArenaSample],
    config: ArenaExecutionConfig,
) -> None:
    call_log: list[tuple[Any, ...]] = []

    def handler_factory(item: ArenaContestant) -> FakeHandler:
        parsed = (
            ["good $RULER$", "good"]
            if item.contestant_id == "good"
            else bad_parsed
        )
        return FakeHandler(
            item.contestant_id,
            ArenaHandlerCompletion('["candidate"]'),
            parsed,
            call_log,
        )

    result = make_service(FakeValidator()).execute(
        config=config,
        samples=samples,
        contestants=[
            contestant("good", order=1),
            contestant("bad", order=2),
        ],
        handler_factory=handler_factory,
    )

    bad = next(item for item in result.contestants if item.contestant_id == "bad")
    bad_request = next(
        item for item in result.requests if item.contestant_id == "bad"
    )
    assert result.status == "partial_failed"
    assert bad.status == "failed"
    assert bad.failure_code == expected_failure
    assert bad_request.failure_code == expected_failure
    assert bad_request.completion_text_before_parse == '["candidate"]'


def test_hard_errors_are_deduplicated_and_token_parity_is_counted(
    samples: list[ArenaSample],
    config: ArenaExecutionConfig,
) -> None:
    duplicate_error = ValidationResult(
        is_valid=False,
        level=ValidationLevel.ERROR,
        code="bad_format",
        message="Bad format",
        details=" same   detail ",
    )
    warning = ValidationResult(
        is_valid=True,
        level=ValidationLevel.WARNING,
        code="warning_only",
        message="Warning",
    )
    validator = FakeValidator(
        {
            "No ruler token": [duplicate_error, duplicate_error, warning],
        }
    )
    call_log: list[tuple[Any, ...]] = []

    def handler_factory(item: ArenaContestant) -> FakeHandler:
        return FakeHandler(
            item.contestant_id,
            ArenaHandlerCompletion('["No ruler token", "Fine"]'),
            ["No ruler token", "Fine"],
            call_log,
        )

    result = make_service(validator).execute(
        config=config,
        samples=samples,
        contestants=[
            contestant("c1", order=1),
            contestant("c2", order=2),
        ],
        handler_factory=handler_factory,
    )

    first_output = next(
        output
        for output in result.outputs
        if output.contestant_id == "c1" and output.sample_id == "sample-1"
    )
    first_contestant = next(
        item for item in result.contestants if item.contestant_id == "c1"
    )
    assert result.status == "voting"
    assert first_output.hard_error_count == 2
    assert {issue.code for issue in first_output.validation} == {
        "bad_format",
        "protected_token_parity",
    }
    assert first_output.token_parity is not None
    assert first_output.token_parity.missing == ("$RULER$",)
    assert first_contestant.hard_error_occurrences == 2
    assert first_contestant.affected_sample_count == 1
    assert validator.calls[0] == {
        "game_id": "victoria3",
        "key": "event.title",
        "value": "No ruler token",
        "line_number": 10,
        "source_lang": {"code": "english", "name": "English"},
        "source_value": "The $RULER$ arrives",
        "target_lang": "simp_chinese",
        "dynamic_valid_tags": [],
    }
    assert validator.calls[1]["dynamic_valid_tags"] == ["RULER"]


def test_validator_failure_is_not_silently_ignored(
    samples: list[ArenaSample],
    config: ArenaExecutionConfig,
) -> None:
    call_log: list[tuple[Any, ...]] = []

    def handler_factory(item: ArenaContestant) -> FakeHandler:
        return FakeHandler(
            item.contestant_id,
            ArenaHandlerCompletion('["ok", "ok"]'),
            ["ok", "ok"],
            call_log,
        )

    result = make_service(FakeValidator(fail=True)).execute(
        config=config,
        samples=samples,
        contestants=[
            contestant("c1", order=1),
            contestant("c2", order=2),
        ],
        handler_factory=handler_factory,
    )

    assert result.status == "failed"
    assert all(
        item.failure_code == FAILURE_VALIDATION for item in result.contestants
    )
    assert all(
        request.failure_code == FAILURE_VALIDATION for request in result.requests
    )


@pytest.mark.parametrize("contestant_count", [0, 1, 4])
def test_rejects_unsupported_contestant_counts(
    contestant_count: int,
    samples: list[ArenaSample],
    config: ArenaExecutionConfig,
) -> None:
    with pytest.raises(ValueError, match="exactly 2 or 3"):
        make_service(FakeValidator()).execute(
            config=config,
            samples=samples,
            contestants=[
                contestant(f"c{index}", order=index)
                for index in range(contestant_count)
            ],
            handler_factory=lambda item: None,
        )
