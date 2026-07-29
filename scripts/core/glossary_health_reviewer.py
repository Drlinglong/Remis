import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError


class GlossaryHealthReviewError(RuntimeError):
    """Raised when a model cannot produce a trustworthy advisory review."""


class GlossaryHealthStructuredResponseError(GlossaryHealthReviewError):
    """Raised when a model response does not match the requested repair cases."""


class GlossaryHealthAdvice(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    case_id: str = Field(min_length=1, max_length=320)
    entry_id: str = Field(min_length=1, max_length=200)
    issue_code: str = Field(min_length=1, max_length=100)
    suggested_source: Optional[str] = Field(default=None, max_length=1000)
    suggested_translation: Optional[str] = Field(default=None, max_length=1000)
    recommendation: str = Field(min_length=1, max_length=1000)
    rationale: str = Field(min_length=1, max_length=1500)
    priority: Literal["low", "medium", "high"] = "medium"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


ADVICE_LIST_ADAPTER = TypeAdapter(List[GlossaryHealthAdvice])


class GlossaryHealthReviewer:
    """Model boundary that returns suggestions only and never mutates glossary data."""

    MAX_BATCH_SIZE = 12
    MAX_BATCH_INPUT_TOKENS = 2200
    MAX_STRUCTURED_RESPONSE_ATTEMPTS = 2
    CJK_PATTERN = re.compile(
        r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]"
    )
    PLACEHOLDER_PATTERN = re.compile(r"\$[^$]+\$|\[[^\]]+\]|\{[^{}]+\}|%[^%]+%")

    SYSTEM_PROMPT = """
You are a senior game-localization terminology reviewer.

Review every deterministic glossary-health repair case in the supplied batch. Return one
concrete, entry-specific draft for every case. Do not claim that any repair has been applied.
Do not invent entries or evidence beyond the supplied batch.

Return only a JSON array. Each item must use this schema:
[
  {
    "case_id": "missing_translation:entry-123",
    "entry_id": "entry-123",
    "issue_code": "missing_translation",
    "suggested_source": null,
    "suggested_translation": "Tyrian purple",
    "recommendation": "Use the established English name for this historical dye.",
    "rationale": "Tyrian purple is the conventional English rendering of 泰尔紫.",
    "priority": "high",
    "confidence": 0.9
  }
]

Rules:
- Return exactly one item for every supplied `case_id`, with no missing or extra cases.
- Copy `case_id`, `entry_id`, and `issue_code` exactly from the supplied case.
- Never combine multiple entries into one recommendation.
- When `target_lang` is present, `suggested_translation` must be in that language.
- `missing_translation`, `edge_whitespace`, and `placeholder_mismatch` require a concrete
  `suggested_translation`, not an instruction to translate or inspect the term.
- `empty_source` requires a concrete `suggested_source`.
- Preserve placeholders and formatting tokens exactly.
- Preserve a correct existing source or translation; use null when that field needs no change.
- `recommendation` states the proposed edit or review action for this one entry.
- `rationale` briefly explains this specific choice.
- Suggestions are drafts for human review only. Never output commands or claim to save data.
"""

    RETRY_INSTRUCTION = """
Your previous response did not satisfy the structured-output contract. Return only the JSON
array, with exactly one valid item for each supplied case_id and no additional commentary.
"""

    def __init__(self, client: Any):
        self.client = client

    @staticmethod
    def _strip_code_fence(value: str) -> str:
        cleaned = value.strip()
        if cleaned.startswith("```"):
            newline = cleaned.find("\n")
            cleaned = cleaned[newline + 1:] if newline >= 0 else ""
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    @classmethod
    def _estimate_tokens(cls, value: Any) -> int:
        serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        cjk_count = len(cls.CJK_PATTERN.findall(serialized))
        non_cjk_count = max(0, len(serialized) - cjk_count)
        return max(1, cjk_count + math.ceil(non_cjk_count / 4))

    @staticmethod
    def _case_id(issue_code: str, entry_id: str) -> str:
        return f"{issue_code}:{entry_id}"

    @staticmethod
    def _bounded_text(value: Any, max_length: int) -> Optional[str]:
        if value is None:
            return None
        return str(value)[:max_length]

    @classmethod
    def _build_cases(cls, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        cases = []
        seen_case_ids = set()
        target_lang = report.get("target_lang")
        for issue in report.get("issues", []):
            issue_code = str(issue.get("code") or "")
            for evidence in issue.get("items", []):
                entry_id = str(evidence.get("entry_id") or "")
                if not issue_code or not entry_id:
                    continue
                case_id = cls._case_id(issue_code, entry_id)
                if case_id in seen_case_ids:
                    continue
                seen_case_ids.add(case_id)
                cases.append({
                    "case_id": case_id,
                    "entry_id": entry_id,
                    "issue_code": issue_code,
                    "severity": issue.get("severity"),
                    "issue_message": issue.get("message"),
                    "target_lang": target_lang,
                    "glossary_id": evidence.get("glossary_id"),
                    "glossary_name": evidence.get("glossary_name"),
                    "game_id": evidence.get("game_id"),
                    "source": cls._bounded_text(evidence.get("source") or "", 1600),
                    "current_translation": cls._bounded_text(
                        evidence.get("current_translation"),
                        1600,
                    ),
                    "detail": cls._bounded_text(evidence.get("detail") or "", 1200),
                })
        return cases

    @classmethod
    def _build_batches(cls, report: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
        batches: List[List[Dict[str, Any]]] = []
        current_batch: List[Dict[str, Any]] = []
        current_tokens = 0

        for case in cls._build_cases(report):
            case_tokens = cls._estimate_tokens(case)
            would_exceed_size = len(current_batch) >= cls.MAX_BATCH_SIZE
            would_exceed_tokens = (
                current_batch
                and current_tokens + case_tokens > cls.MAX_BATCH_INPUT_TOKENS
            )
            if would_exceed_size or would_exceed_tokens:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            current_batch.append(case)
            current_tokens += case_tokens

        if current_batch:
            batches.append(current_batch)
        return batches

    @classmethod
    def plan(cls, report: Dict[str, Any]) -> Dict[str, Any]:
        batches = cls._build_batches(report)
        return {
            "case_count": sum(len(batch) for batch in batches),
            "batch_count": len(batches),
            "batch_sizes": [len(batch) for batch in batches],
            "max_batch_size": cls.MAX_BATCH_SIZE,
            "input_token_budget": cls.MAX_BATCH_INPUT_TOKENS,
        }

    def _generate(self, messages: List[Dict[str, str]]) -> str:
        try:
            response = self.client.generate_with_messages(messages, temperature=0.1)
        except Exception as exc:
            raise GlossaryHealthReviewError(f"Model request failed: {exc}") from exc
        if not response or not response.strip():
            raise GlossaryHealthStructuredResponseError(
                "Model returned an empty response"
            )
        return response.strip()

    @staticmethod
    def _validate_case_suggestion(
        suggestion: GlossaryHealthAdvice,
        expected_case: Dict[str, Any],
    ) -> None:
        if suggestion.entry_id != expected_case["entry_id"]:
            raise GlossaryHealthStructuredResponseError(
                "Model advice referenced the wrong glossary entry"
            )
        if suggestion.issue_code != expected_case["issue_code"]:
            raise GlossaryHealthStructuredResponseError(
                "Model advice referenced the wrong issue code"
            )

        issue_code = suggestion.issue_code
        if issue_code in {
            "missing_translation",
            "edge_whitespace",
            "placeholder_mismatch",
        } and not suggestion.suggested_translation:
            raise GlossaryHealthStructuredResponseError(
                f"{issue_code} requires a concrete suggested translation"
            )
        if issue_code == "empty_source" and not suggestion.suggested_source:
            raise GlossaryHealthStructuredResponseError(
                "empty_source requires a concrete suggested source"
            )
        if issue_code == "placeholder_mismatch":
            expected_tokens = sorted(
                GlossaryHealthReviewer.PLACEHOLDER_PATTERN.findall(
                    expected_case.get("source") or ""
                )
            )
            suggested_tokens = sorted(
                GlossaryHealthReviewer.PLACEHOLDER_PATTERN.findall(
                    suggestion.suggested_translation or ""
                )
            )
            if expected_tokens != suggested_tokens:
                raise GlossaryHealthStructuredResponseError(
                    "Suggested translation does not preserve source placeholders"
                )

    def _review_batch_once(
        self,
        report: Dict[str, Any],
        batch: List[Dict[str, Any]],
        *,
        retry: bool,
    ) -> List[Dict[str, Any]]:
        payload = {
            "target_lang": report.get("target_lang"),
            "cases": batch,
        }
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        if retry:
            messages.append({"role": "user", "content": self.RETRY_INSTRUCTION})

        response = self._generate(messages)
        try:
            advice = ADVICE_LIST_ADAPTER.validate_python(
                json.loads(self._strip_code_fence(response))
            )
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise GlossaryHealthStructuredResponseError(
                "Model returned invalid structured advice"
            ) from exc

        expected_by_id = {case["case_id"]: case for case in batch}
        advice_by_id: Dict[str, GlossaryHealthAdvice] = {}
        for suggestion in advice:
            if suggestion.case_id not in expected_by_id:
                raise GlossaryHealthStructuredResponseError(
                    "Model advice referenced an unknown repair case"
                )
            if suggestion.case_id in advice_by_id:
                raise GlossaryHealthStructuredResponseError(
                    "Model returned duplicate repair cases"
                )
            self._validate_case_suggestion(
                suggestion,
                expected_by_id[suggestion.case_id],
            )
            advice_by_id[suggestion.case_id] = suggestion

        missing_case_ids = set(expected_by_id) - set(advice_by_id)
        if missing_case_ids:
            raise GlossaryHealthStructuredResponseError(
                "Model omitted one or more repair cases"
            )

        return [
            advice_by_id[case["case_id"]].model_dump()
            for case in batch
        ]

    def _review_batch(
        self,
        report_and_batch: Tuple[Dict[str, Any], List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        report, batch = report_and_batch
        last_error: Optional[GlossaryHealthStructuredResponseError] = None
        for attempt in range(self.MAX_STRUCTURED_RESPONSE_ATTEMPTS):
            try:
                return self._review_batch_once(
                    report,
                    batch,
                    retry=attempt > 0,
                )
            except GlossaryHealthStructuredResponseError as exc:
                last_error = exc
        raise last_error or GlossaryHealthStructuredResponseError(
            "Model returned invalid structured advice"
        )

    def review(
        self,
        report: Dict[str, Any],
        *,
        concurrency_limit: int = 1,
    ) -> List[Dict[str, Any]]:
        batches = self._build_batches(report)
        if not batches:
            return []

        work_items = [(report, batch) for batch in batches]
        max_workers = min(max(1, int(concurrency_limit)), len(work_items))
        if max_workers == 1:
            results = [
                self._review_batch(work_item)
                for work_item in work_items
            ]
        else:
            with ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="glossary-health-review",
            ) as executor:
                results = list(executor.map(self._review_batch, work_items))

        return [
            advice
            for batch_advice in results
            for advice in batch_advice
        ]
