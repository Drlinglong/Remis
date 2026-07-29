"""Pure execution service for a Remis model-arena run.

This module intentionally has no repository or HTTP dependencies. Callers
provide frozen run inputs and a handler factory, then persist the returned
evidence/result dataclasses themselves.

The service calls each provider exactly once and serially. It deliberately does
not use ``BaseApiHandler.translate_batch`` because that method retries and can
fall back to the source text, both of which would corrupt arena evidence.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import re
import time
from typing import Any, Literal
import uuid

from scripts.utils.post_process_validator import (
    PostProcessValidator,
    ValidationLevel,
)

logger = logging.getLogger(__name__)


COMPLETION_SOURCES = frozenset(
    {
        "assistant_content",
        "provider_compatibility_path",
    }
)

FAILURE_HANDLER_INITIALIZATION = "handler_initialization_failed"
FAILURE_HANDLER_CONTRACT = "handler_contract_error"
FAILURE_PROVIDER_REQUEST = "provider_request_failed"
FAILURE_PROVIDER_TIMEOUT = "provider_timeout"
FAILURE_EMPTY_COMPLETION = "empty_completion"
FAILURE_PARSE = "parse_failed"
FAILURE_ITEM_COUNT = "item_count_mismatch"
FAILURE_EMPTY_TRANSLATION = "empty_translation"
FAILURE_VALIDATION = "validation_failed"

_PROTECTED_TOKEN_RE = re.compile(
    r"\$[^$\r\n]+\$|\[[^\[\]\r\n]+\]|§.|#!|#[A-Za-z][\w.-]*|\\n"
)
_SENSITIVE_PARAMETER_KEYS = frozenset(
    {
        "account",
        "account_id",
        "api_key",
        "api_token",
        "api_url",
        "authorization",
        "base_url",
        "endpoint",
        "masked_key",
        "password",
        "secret",
        "token",
        "url",
        "username",
    }
)


def _empty_mapping() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True)
class ArenaSample:
    """A sampled localization entry in its frozen execution order."""

    sample_id: str
    entry_key: str
    source_text: str
    line_number: int | None = None
    dynamic_valid_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArenaContestant:
    """A provider/model pair participating in one run."""

    contestant_id: str
    provider_name: str
    model_id: str
    execution_order: int
    system_instruction: str | None = None
    effective_parameters: Mapping[str, Any] = field(default_factory=_empty_mapping)


@dataclass(frozen=True)
class ArenaExecutionConfig:
    """Frozen configuration shared by every contestant in a run."""

    run_id: str
    game_id: str
    source_lang: Mapping[str, Any]
    target_lang_code: str
    prompt_text: str
    system_instruction: str | None = None
    effective_parameters: Mapping[str, Any] = field(default_factory=_empty_mapping)
    batch_ordinal: int = 0


@dataclass(frozen=True)
class ArenaHandlerCompletion:
    """The adapter-selected final text that is about to enter Remis parsing.

    Provider adapters may return this richer value from
    ``execute_model_arena_request``. They must not put an unused reasoning field
    or the provider response envelope in this object. Reasoning-only output is
    rejected because every contestant must emit final assistant content.
    """

    completion_text_before_parse: str | None
    completion_source: Literal[
        "assistant_content",
        "provider_compatibility_path",
    ] = "assistant_content"
    usage: Mapping[str, Any] = field(default_factory=_empty_mapping)
    system_instruction: str | None = None
    user_prompt: str | None = None
    effective_parameters: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ArenaValidationIssue:
    code: str
    level: str
    message: str
    details: str | None = None
    details_code: str | None = None
    details_params: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ArenaTokenParity:
    passed: bool
    expected: tuple[str, ...]
    actual: tuple[str, ...]
    missing: tuple[str, ...]
    extra: tuple[str, ...]


@dataclass(frozen=True)
class ArenaRequestEvidence:
    request_id: str
    contestant_id: str
    batch_ordinal: int
    system_instruction: str | None
    prompt_text: str
    effective_parameters: Mapping[str, Any]
    prompt_sha256: str
    completion_text_before_parse: str | None
    completion_source: str
    completion_sha256: str | None
    usage: Mapping[str, Any]
    parse_status: str
    failure_code: str | None
    elapsed_ms: int
    created_at: str


@dataclass(frozen=True)
class ArenaOutput:
    output_id: str
    sample_id: str
    contestant_id: str
    translated_text: str | None
    response_sha256: str | None
    parse_status: str
    hard_error_count: int
    validation: tuple[ArenaValidationIssue, ...]
    token_parity: ArenaTokenParity | None
    created_at: str


@dataclass(frozen=True)
class ArenaContestantResult:
    contestant_id: str
    status: Literal["completed", "failed"]
    request_count: int
    elapsed_ms: int
    failure_code: str | None
    hard_error_occurrences: int
    affected_sample_count: int


@dataclass(frozen=True)
class ArenaExecutionResult:
    run_id: str
    status: Literal["voting", "partial_failed", "failed"]
    requests: tuple[ArenaRequestEvidence, ...]
    outputs: tuple[ArenaOutput, ...]
    contestants: tuple[ArenaContestantResult, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable nested structure for routers/repositories."""

        return asdict(self)


HandlerFactory = Callable[[ArenaContestant], Any]


class ModelArenaExecutionService:
    """Execute a frozen model-arena batch without persistence side effects."""

    def __init__(
        self,
        *,
        validator: PostProcessValidator | None = None,
        timer: Callable[[], float] = time.perf_counter,
        utcnow: Callable[[], datetime] | None = None,
    ) -> None:
        self._validator = validator or PostProcessValidator()
        self._timer = timer
        self._utcnow = utcnow or (lambda: datetime.now(timezone.utc))

    def execute(
        self,
        *,
        config: ArenaExecutionConfig,
        samples: Sequence[ArenaSample],
        contestants: Sequence[ArenaContestant],
        handler_factory: HandlerFactory,
        retry_subset: bool = False,
    ) -> ArenaExecutionResult:
        """Run contestants serially and return persistence-ready data.

        Initial execution requires 2 or 3 contestants. After the router has
        obtained a fresh paid-action confirmation, ``retry_subset=True`` allows
        it to pass only the 1-3 failed contestants, avoiding calls to models
        that already succeeded.
        """

        ordered_samples, ordered_contestants = self._validate_inputs(
            config,
            samples,
            contestants,
            retry_subset=retry_subset,
        )
        request_results: list[ArenaRequestEvidence] = []
        output_results: list[ArenaOutput] = []
        contestant_results: list[ArenaContestantResult] = []

        for contestant in ordered_contestants:
            started = self._timer()
            contestant_requests, contestant_outputs, status, failure_code = (
                self._execute_contestant(
                    config=config,
                    samples=ordered_samples,
                    contestant=contestant,
                    handler_factory=handler_factory,
                )
            )
            elapsed_ms = _elapsed_ms(started, self._timer())
            request_results.extend(contestant_requests)
            output_results.extend(contestant_outputs)
            hard_error_occurrences = sum(
                output.hard_error_count for output in contestant_outputs
            )
            affected_sample_count = sum(
                output.hard_error_count > 0 for output in contestant_outputs
            )
            contestant_results.append(
                ArenaContestantResult(
                    contestant_id=contestant.contestant_id,
                    status=status,
                    request_count=len(contestant_requests),
                    elapsed_ms=elapsed_ms,
                    failure_code=failure_code,
                    hard_error_occurrences=hard_error_occurrences,
                    affected_sample_count=affected_sample_count,
                )
            )

        completed_count = sum(
            result.status == "completed" for result in contestant_results
        )
        if completed_count == len(contestant_results):
            aggregate_status: Literal["voting", "partial_failed", "failed"] = "voting"
        elif completed_count:
            aggregate_status = "partial_failed"
        else:
            aggregate_status = "failed"

        return ArenaExecutionResult(
            run_id=config.run_id,
            status=aggregate_status,
            requests=tuple(request_results),
            outputs=tuple(output_results),
            contestants=tuple(contestant_results),
        )

    def _execute_contestant(
        self,
        *,
        config: ArenaExecutionConfig,
        samples: tuple[ArenaSample, ...],
        contestant: ArenaContestant,
        handler_factory: HandlerFactory,
    ) -> tuple[
        list[ArenaRequestEvidence],
        list[ArenaOutput],
        Literal["completed", "failed"],
        str | None,
    ]:
        created_at = self._timestamp()
        try:
            handler = handler_factory(contestant)
        except Exception:
            return (
                [],
                self._failure_outputs(
                    config=config,
                    samples=samples,
                    contestant=contestant,
                    failure_code=FAILURE_HANDLER_INITIALIZATION,
                    created_at=created_at,
                ),
                "failed",
                FAILURE_HANDLER_INITIALIZATION,
            )

        system_instruction = (
            contestant.system_instruction
            if contestant.system_instruction is not None
            else config.system_instruction
        )
        effective_parameters = _sanitize_mapping(
            {
                **dict(config.effective_parameters),
                **dict(contestant.effective_parameters),
            }
        )
        request_started = self._timer()
        try:
            completion = self._invoke_handler(
                handler=handler,
                system_instruction=system_instruction,
                prompt_text=config.prompt_text,
                effective_parameters=effective_parameters,
            )
        except TimeoutError:
            return self._request_failure(
                config=config,
                samples=samples,
                contestant=contestant,
                system_instruction=system_instruction,
                effective_parameters=effective_parameters,
                failure_code=FAILURE_PROVIDER_TIMEOUT,
                request_started=request_started,
                created_at=created_at,
            )
        except _HandlerContractError:
            logger.debug("Model arena handler contract failed", exc_info=True)
            return self._request_failure(
                config=config,
                samples=samples,
                contestant=contestant,
                system_instruction=system_instruction,
                effective_parameters=effective_parameters,
                failure_code=FAILURE_HANDLER_CONTRACT,
                request_started=request_started,
                created_at=created_at,
            )
        except Exception:
            return self._request_failure(
                config=config,
                samples=samples,
                contestant=contestant,
                system_instruction=system_instruction,
                effective_parameters=effective_parameters,
                failure_code=FAILURE_PROVIDER_REQUEST,
                request_started=request_started,
                created_at=created_at,
            )

        request_elapsed_ms = _elapsed_ms(request_started, self._timer())
        actual_system_instruction = (
            completion.system_instruction
            if completion.system_instruction is not None
            else system_instruction
        )
        actual_prompt = (
            completion.user_prompt
            if completion.user_prompt is not None
            else config.prompt_text
        )
        actual_parameters = _sanitize_mapping(
            completion.effective_parameters
            if completion.effective_parameters is not None
            else effective_parameters
        )
        usage = _sanitize_usage(completion.usage)
        completion_text = completion.completion_text_before_parse

        if (
            not isinstance(actual_prompt, str)
            or actual_prompt != config.prompt_text
            or (
                completion_text is not None
                and not isinstance(completion_text, str)
            )
        ):
            failure_code = FAILURE_HANDLER_CONTRACT
            request = self._make_request(
                config=config,
                contestant=contestant,
                system_instruction=actual_system_instruction,
                prompt_text=(
                    actual_prompt
                    if isinstance(actual_prompt, str)
                    else config.prompt_text
                ),
                effective_parameters=actual_parameters,
                completion=ArenaHandlerCompletion(
                    completion_text_before_parse=(
                        completion_text
                        if isinstance(completion_text, str)
                        else None
                    ),
                    completion_source=completion.completion_source,
                ),
                usage=usage,
                parse_status="failed",
                failure_code=failure_code,
                elapsed_ms=request_elapsed_ms,
                created_at=created_at,
            )
            return (
                [request],
                self._failure_outputs(
                    config=config,
                    samples=samples,
                    contestant=contestant,
                    failure_code=failure_code,
                    created_at=created_at,
                ),
                "failed",
                failure_code,
            )

        if completion_text is None or not completion_text.strip():
            failure_code = FAILURE_EMPTY_COMPLETION
            request = self._make_request(
                config=config,
                contestant=contestant,
                system_instruction=actual_system_instruction,
                prompt_text=actual_prompt,
                effective_parameters=actual_parameters,
                completion=completion,
                usage=usage,
                parse_status="failed",
                failure_code=failure_code,
                elapsed_ms=request_elapsed_ms,
                created_at=created_at,
            )
            return (
                [request],
                self._failure_outputs(
                    config=config,
                    samples=samples,
                    contestant=contestant,
                    failure_code=failure_code,
                    created_at=created_at,
                ),
                "failed",
                failure_code,
            )

        source_texts = [sample.source_text for sample in samples]
        try:
            parsed = handler._parse_response(  # noqa: SLF001 - production handler contract
                completion_text,
                source_texts,
                config.target_lang_code,
            )
        except Exception:
            parsed = None

        if parsed is None or isinstance(parsed, (str, bytes)):
            failure_code = FAILURE_PARSE
            return self._parsed_failure(
                config=config,
                samples=samples,
                contestant=contestant,
                completion=completion,
                system_instruction=actual_system_instruction,
                prompt_text=actual_prompt,
                effective_parameters=actual_parameters,
                usage=usage,
                failure_code=failure_code,
                request_elapsed_ms=request_elapsed_ms,
                created_at=created_at,
            )

        try:
            parsed_outputs = list(parsed)
        except TypeError:
            parsed_outputs = []
            failure_code = FAILURE_PARSE
            return self._parsed_failure(
                config=config,
                samples=samples,
                contestant=contestant,
                completion=completion,
                system_instruction=actual_system_instruction,
                prompt_text=actual_prompt,
                effective_parameters=actual_parameters,
                usage=usage,
                failure_code=failure_code,
                request_elapsed_ms=request_elapsed_ms,
                created_at=created_at,
            )

        if len(parsed_outputs) != len(samples):
            failure_code = FAILURE_ITEM_COUNT
            request = self._make_request(
                config=config,
                contestant=contestant,
                system_instruction=actual_system_instruction,
                prompt_text=actual_prompt,
                effective_parameters=actual_parameters,
                completion=completion,
                usage=usage,
                parse_status="item_count_mismatch",
                failure_code=failure_code,
                elapsed_ms=request_elapsed_ms,
                created_at=created_at,
            )
            return (
                [request],
                self._count_mismatch_outputs(
                    config=config,
                    samples=samples,
                    contestant=contestant,
                    parsed_outputs=parsed_outputs,
                    created_at=created_at,
                ),
                "failed",
                failure_code,
            )

        if any(not isinstance(output, str) for output in parsed_outputs):
            failure_code = FAILURE_PARSE
            return self._parsed_failure(
                config=config,
                samples=samples,
                contestant=contestant,
                completion=completion,
                system_instruction=actual_system_instruction,
                prompt_text=actual_prompt,
                effective_parameters=actual_parameters,
                usage=usage,
                failure_code=failure_code,
                request_elapsed_ms=request_elapsed_ms,
                created_at=created_at,
            )

        try:
            outputs = self._validate_outputs(
                config=config,
                samples=samples,
                contestant=contestant,
                translated_texts=parsed_outputs,
                created_at=created_at,
            )
        except Exception:
            failure_code = FAILURE_VALIDATION
            request = self._make_request(
                config=config,
                contestant=contestant,
                system_instruction=actual_system_instruction,
                prompt_text=actual_prompt,
                effective_parameters=actual_parameters,
                completion=completion,
                usage=usage,
                parse_status="validation_failed",
                failure_code=failure_code,
                elapsed_ms=request_elapsed_ms,
                created_at=created_at,
            )
            return (
                [request],
                self._failure_outputs(
                    config=config,
                    samples=samples,
                    contestant=contestant,
                    failure_code=failure_code,
                    created_at=created_at,
                ),
                "failed",
                failure_code,
            )

        empty_output = any(not output.translated_text.strip() for output in outputs)
        failure_code = FAILURE_EMPTY_TRANSLATION if empty_output else None
        request = self._make_request(
            config=config,
            contestant=contestant,
            system_instruction=actual_system_instruction,
            prompt_text=actual_prompt,
            effective_parameters=actual_parameters,
            completion=completion,
            usage=usage,
            parse_status="empty_translation" if empty_output else "parsed",
            failure_code=failure_code,
            elapsed_ms=request_elapsed_ms,
            created_at=created_at,
        )
        return (
            [request],
            outputs,
            "failed" if empty_output else "completed",
            failure_code,
        )

    def _invoke_handler(
        self,
        *,
        handler: Any,
        system_instruction: str | None,
        prompt_text: str,
        effective_parameters: Mapping[str, Any],
    ) -> ArenaHandlerCompletion:
        arena_method = getattr(handler, "execute_model_arena_request", None)
        if callable(arena_method):
            raw_completion = arena_method(
                system_instruction=system_instruction,
                user_prompt=prompt_text,
                effective_parameters=dict(effective_parameters),
            )
        else:
            call_api = getattr(handler, "_call_api", None)
            if not callable(call_api):
                raise _HandlerContractError
            raw_completion = call_api(getattr(handler, "client", None), prompt_text)

        if isinstance(raw_completion, ArenaHandlerCompletion) or (
            hasattr(raw_completion, "completion_text_before_parse")
            and hasattr(raw_completion, "completion_source")
        ):
            completion_source = raw_completion.completion_source
            if completion_source not in COMPLETION_SOURCES:
                logger.debug(
                    "Model arena adapter returned unsupported completion source: %s",
                    completion_source,
                )
                raise _HandlerContractError
            if isinstance(raw_completion, ArenaHandlerCompletion):
                return raw_completion
            # Development hot reload and packaged import aliases can create a
            # structurally identical dataclass with a different class identity.
            return ArenaHandlerCompletion(
                completion_text_before_parse=raw_completion.completion_text_before_parse,
                completion_source=completion_source,
                usage=getattr(raw_completion, "usage", {}) or {},
                system_instruction=getattr(raw_completion, "system_instruction", None),
                user_prompt=getattr(raw_completion, "user_prompt", None),
                effective_parameters=getattr(
                    raw_completion, "effective_parameters", None
                ),
            )
        if isinstance(raw_completion, str):
            return ArenaHandlerCompletion(raw_completion)
        logger.debug(
            "Model arena adapter returned unsupported completion type: %s",
            type(raw_completion).__name__,
        )
        raise _HandlerContractError

    def _validate_outputs(
        self,
        *,
        config: ArenaExecutionConfig,
        samples: tuple[ArenaSample, ...],
        contestant: ArenaContestant,
        translated_texts: list[str],
        created_at: str,
    ) -> list[ArenaOutput]:
        outputs: list[ArenaOutput] = []
        for sample, translated_text in zip(samples, translated_texts):
            is_empty = not translated_text.strip()
            validation_results = (
                []
                if is_empty
                else self._validator.validate_entry(
                    game_id=config.game_id,
                    key=sample.entry_key,
                    value=translated_text,
                    line_number=sample.line_number,
                    source_lang=dict(config.source_lang),
                    source_value=sample.source_text,
                    target_lang=config.target_lang_code,
                    dynamic_valid_tags=list(sample.dynamic_valid_tags),
                )
            )
            issues = _dedupe_validation_errors(validation_results)
            parity = _token_parity(sample.source_text, translated_text)
            if not parity.passed:
                issues.append(
                    ArenaValidationIssue(
                        code="protected_token_parity",
                        level=ValidationLevel.ERROR.value,
                        message="Protected tokens differ from the source text.",
                        details=json.dumps(
                            {
                                "missing": parity.missing,
                                "extra": parity.extra,
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    )
                )
            if is_empty:
                issues.append(
                    ArenaValidationIssue(
                        code=FAILURE_EMPTY_TRANSLATION,
                        level=ValidationLevel.ERROR.value,
                        message="The parsed translation is empty.",
                    )
                )
            outputs.append(
                ArenaOutput(
                    output_id=_stable_id(
                        "output",
                        config.run_id,
                        contestant.contestant_id,
                        sample.sample_id,
                    ),
                    sample_id=sample.sample_id,
                    contestant_id=contestant.contestant_id,
                    translated_text=translated_text,
                    response_sha256=_sha256_text(translated_text),
                    parse_status=(
                        "empty_translation" if is_empty else "parsed"
                    ),
                    hard_error_count=len(issues),
                    validation=tuple(issues),
                    token_parity=parity,
                    created_at=created_at,
                )
            )
        return outputs

    def _request_failure(
        self,
        *,
        config: ArenaExecutionConfig,
        samples: tuple[ArenaSample, ...],
        contestant: ArenaContestant,
        system_instruction: str | None,
        effective_parameters: Mapping[str, Any],
        failure_code: str,
        request_started: float,
        created_at: str,
    ) -> tuple[
        list[ArenaRequestEvidence],
        list[ArenaOutput],
        Literal["failed"],
        str,
    ]:
        completion = ArenaHandlerCompletion(None)
        request = self._make_request(
            config=config,
            contestant=contestant,
            system_instruction=system_instruction,
            prompt_text=config.prompt_text,
            effective_parameters=effective_parameters,
            completion=completion,
            usage={},
            parse_status="failed",
            failure_code=failure_code,
            elapsed_ms=_elapsed_ms(request_started, self._timer()),
            created_at=created_at,
        )
        return (
            [request],
            self._failure_outputs(
                config=config,
                samples=samples,
                contestant=contestant,
                failure_code=failure_code,
                created_at=created_at,
            ),
            "failed",
            failure_code,
        )

    def _parsed_failure(
        self,
        *,
        config: ArenaExecutionConfig,
        samples: tuple[ArenaSample, ...],
        contestant: ArenaContestant,
        completion: ArenaHandlerCompletion,
        system_instruction: str | None,
        prompt_text: str,
        effective_parameters: Mapping[str, Any],
        usage: Mapping[str, Any],
        failure_code: str,
        request_elapsed_ms: int,
        created_at: str,
    ) -> tuple[
        list[ArenaRequestEvidence],
        list[ArenaOutput],
        Literal["failed"],
        str,
    ]:
        request = self._make_request(
            config=config,
            contestant=contestant,
            system_instruction=system_instruction,
            prompt_text=prompt_text,
            effective_parameters=effective_parameters,
            completion=completion,
            usage=usage,
            parse_status="failed",
            failure_code=failure_code,
            elapsed_ms=request_elapsed_ms,
            created_at=created_at,
        )
        return (
            [request],
            self._failure_outputs(
                config=config,
                samples=samples,
                contestant=contestant,
                failure_code=failure_code,
                created_at=created_at,
            ),
            "failed",
            failure_code,
        )

    def _make_request(
        self,
        *,
        config: ArenaExecutionConfig,
        contestant: ArenaContestant,
        system_instruction: str | None,
        prompt_text: str,
        effective_parameters: Mapping[str, Any],
        completion: ArenaHandlerCompletion,
        usage: Mapping[str, Any],
        parse_status: str,
        failure_code: str | None,
        elapsed_ms: int,
        created_at: str,
    ) -> ArenaRequestEvidence:
        completion_text = completion.completion_text_before_parse
        return ArenaRequestEvidence(
            request_id=_stable_id(
                "request",
                config.run_id,
                contestant.contestant_id,
                str(config.batch_ordinal),
            ),
            contestant_id=contestant.contestant_id,
            batch_ordinal=config.batch_ordinal,
            system_instruction=system_instruction,
            prompt_text=prompt_text,
            effective_parameters=_sanitize_mapping(effective_parameters),
            prompt_sha256=_sha256_text(prompt_text),
            completion_text_before_parse=completion_text,
            completion_source=completion.completion_source,
            completion_sha256=(
                _sha256_text(completion_text) if completion_text is not None else None
            ),
            usage=_sanitize_usage(usage),
            parse_status=parse_status,
            failure_code=failure_code,
            elapsed_ms=elapsed_ms,
            created_at=created_at,
        )

    def _failure_outputs(
        self,
        *,
        config: ArenaExecutionConfig,
        samples: tuple[ArenaSample, ...],
        contestant: ArenaContestant,
        failure_code: str,
        created_at: str,
    ) -> list[ArenaOutput]:
        is_hard_output_error = failure_code in {
            FAILURE_EMPTY_COMPLETION,
            FAILURE_PARSE,
        }
        validation = (
            (
                ArenaValidationIssue(
                    code=failure_code,
                    level=ValidationLevel.ERROR.value,
                    message=(
                        "The contestant did not produce a valid translation "
                        "for this sample."
                    ),
                ),
            )
            if is_hard_output_error
            else ()
        )
        return [
            ArenaOutput(
                output_id=_stable_id(
                    "output",
                    config.run_id,
                    contestant.contestant_id,
                    sample.sample_id,
                ),
                sample_id=sample.sample_id,
                contestant_id=contestant.contestant_id,
                translated_text=None,
                response_sha256=None,
                parse_status=failure_code,
                hard_error_count=int(is_hard_output_error),
                validation=validation,
                token_parity=None,
                created_at=created_at,
            )
            for sample in samples
        ]

    def _count_mismatch_outputs(
        self,
        *,
        config: ArenaExecutionConfig,
        samples: tuple[ArenaSample, ...],
        contestant: ArenaContestant,
        parsed_outputs: list[Any],
        created_at: str,
    ) -> list[ArenaOutput]:
        issue = ArenaValidationIssue(
            code=FAILURE_ITEM_COUNT,
            level=ValidationLevel.ERROR.value,
            message=(
                f"Expected {len(samples)} translations but parsed "
                f"{len(parsed_outputs)}."
            ),
        )
        outputs: list[ArenaOutput] = []
        for index, sample in enumerate(samples):
            translated_text = (
                parsed_outputs[index]
                if index < len(parsed_outputs)
                and isinstance(parsed_outputs[index], str)
                else None
            )
            outputs.append(
                ArenaOutput(
                    output_id=_stable_id(
                        "output",
                        config.run_id,
                        contestant.contestant_id,
                        sample.sample_id,
                    ),
                    sample_id=sample.sample_id,
                    contestant_id=contestant.contestant_id,
                    translated_text=translated_text,
                    response_sha256=(
                        _sha256_text(translated_text)
                        if translated_text is not None
                        else None
                    ),
                    parse_status=FAILURE_ITEM_COUNT,
                    hard_error_count=1,
                    validation=(issue,),
                    token_parity=None,
                    created_at=created_at,
                )
            )
        return outputs

    def _validate_inputs(
        self,
        config: ArenaExecutionConfig,
        samples: Sequence[ArenaSample],
        contestants: Sequence[ArenaContestant],
        *,
        retry_subset: bool,
    ) -> tuple[tuple[ArenaSample, ...], tuple[ArenaContestant, ...]]:
        if not config.run_id.strip():
            raise ValueError("run_id must not be empty")
        if not config.prompt_text.strip():
            raise ValueError("prompt_text must not be empty")
        if not samples:
            raise ValueError("at least one sample is required")
        allowed_counts = {1, 2, 3} if retry_subset else {2, 3}
        if len(contestants) not in allowed_counts:
            if retry_subset:
                raise ValueError(
                    "model arena retry requires between 1 and 3 contestants"
                )
            raise ValueError("model arena requires exactly 2 or 3 contestants")

        sample_ids = [sample.sample_id for sample in samples]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("sample_id values must be unique")
        contestant_ids = [contestant.contestant_id for contestant in contestants]
        if len(contestant_ids) != len(set(contestant_ids)):
            raise ValueError("contestant_id values must be unique")
        provider_models = [
            (contestant.provider_name, contestant.model_id)
            for contestant in contestants
        ]
        if len(provider_models) != len(set(provider_models)):
            raise ValueError("provider/model combinations must be unique")
        execution_orders = [contestant.execution_order for contestant in contestants]
        if len(execution_orders) != len(set(execution_orders)):
            raise ValueError("execution_order values must be unique")

        return (
            tuple(samples),
            tuple(sorted(contestants, key=lambda item: item.execution_order)),
        )

    def _timestamp(self) -> str:
        value = self._utcnow()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()


class _HandlerContractError(RuntimeError):
    pass


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_id(kind: str, *parts: str) -> str:
    name = ":".join((kind, *parts))
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"remis:model-arena:{name}"))


def _elapsed_ms(started: float, finished: float) -> int:
    return max(0, round((finished - started) * 1000))


def _normalize_details(value: str | None) -> str:
    return " ".join((value or "").split())


def _dedupe_validation_errors(results: Sequence[Any]) -> list[ArenaValidationIssue]:
    issues: list[ArenaValidationIssue] = []
    seen: set[tuple[str, str]] = set()
    for result in results:
        if result.level != ValidationLevel.ERROR:
            continue
        code = result.code or "validation_error"
        details_params = getattr(result, "details_params", None)
        normalized_payload = json.dumps(
            details_params,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ) if details_params else _normalize_details(
            getattr(result, "details", None) or result.message
        )
        dedupe_key = (code, normalized_payload)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        issues.append(
            ArenaValidationIssue(
                code=code,
                level=result.level.value,
                message=result.message,
                details=getattr(result, "details", None),
                details_code=getattr(result, "details_code", None),
                details_params=(
                    _sanitize_mapping(details_params) if details_params else None
                ),
            )
        )
    return issues


def _token_parity(source: str, target: str) -> ArenaTokenParity:
    expected = Counter(_PROTECTED_TOKEN_RE.findall(source or ""))
    actual = Counter(_PROTECTED_TOKEN_RE.findall(target or ""))
    missing = tuple((expected - actual).elements())
    extra = tuple((actual - expected).elements())
    return ArenaTokenParity(
        passed=not missing and not extra,
        expected=tuple(expected.elements()),
        actual=tuple(actual.elements()),
        missing=missing,
        extra=extra,
    )


def _sanitize_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key)
        if _is_sensitive_key(key):
            continue
        if isinstance(raw_value, Mapping):
            sanitized[key] = dict(_sanitize_mapping(raw_value))
        elif isinstance(raw_value, (list, tuple)):
            sanitized[key] = [
                dict(_sanitize_mapping(item)) if isinstance(item, Mapping) else item
                for item in raw_value
            ]
        else:
            sanitized[key] = raw_value
    return sanitized


def _sanitize_usage(value: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only explicit numeric provider usage metadata."""

    sanitized: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key)
        if _is_sensitive_key(key):
            continue
        if isinstance(raw_value, bool):
            continue
        if isinstance(raw_value, (int, float)):
            sanitized[key] = raw_value
        elif isinstance(raw_value, Mapping):
            nested = _sanitize_usage(raw_value)
            if nested:
                sanitized[key] = dict(nested)
    return sanitized


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    if normalized in _SENSITIVE_PARAMETER_KEYS:
        return True
    if normalized.endswith("_token") and not normalized.endswith("_tokens"):
        return True
    return any(
        marker in normalized
        for marker in (
            "account_id",
            "api_key",
            "api_url",
            "authorization",
            "base_url",
            "masked_key",
            "password",
            "secret",
        )
    )
