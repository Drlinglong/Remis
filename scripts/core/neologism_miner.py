import json
import logging
from collections import Counter
from typing import Any, Dict, List, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from scripts.core.neologism_extraction import (
    AnalysisScope,
    NeologismMiningError,
    SourceItem,
    StructuredNeologismExtraction,
    StructuredNeologismExtractor,
)
from scripts.core.context_local_units import LocalTextUnit


class NeologismTerm(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    original: str = Field(min_length=1, max_length=200)
    category: Literal["person", "place", "faction", "concept", "technology", "other"] = "other"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class NeologismReview(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    original: str = Field(min_length=1, max_length=200)
    suggestion: str = Field(min_length=1, max_length=500)
    reasoning: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


REVIEW_LIST_ADAPTER = TypeAdapter(List[NeologismReview])


class NeologismMiner:
    """LLM boundary for grounded extraction and context-aware terminology review."""

    REVIEW_SYSTEM_PROMPT = """
# Role
You are a senior game localization terminology reviewer.

# Task
For every supplied candidate, propose one canonical translation from {source_lang} to {target_lang}.
Use all supplied context snippets, frequency, category, and the game context.
Write every `reasoning` value in {review_language}, regardless of the source or target language.

# Game
{game_name}

# Rules
- Return exactly one review for each input candidate.
- Keep `original` exactly equal to the input value.
- The suggestion must be non-empty and suitable for consistent glossary use.
- Reasoning must be concise and grounded in the supplied contexts.
- Use supplied source_references.item_key values as author-provided structural
  context when resolving a conflict; never translate a localization key.
- In the reasoning, name the translation strategy (transliteration, semantic translation, or mixed),
  mention any supplied glossary precedent, and state material uncertainty.
- Do not translate the suggestion into the review language. The suggestion must remain in {target_lang}.
- Confidence is a number from 0 to 1.

# Output
Output only a JSON array with this schema:
[
  {{
    "original": "Aetherophasic Engine",
    "suggestion": "以太相引擎",
    "reasoning": "A named Stellaris crisis megastructure.",
    "confidence": 0.92
  }}
]
"""

    def __init__(self, client: Any):
        self.client = client
        self.logger = logging.getLogger(__name__)

    def extract_structured(
        self,
        source_items: List[SourceItem],
        *,
        scope: AnalysisScope = AnalysisScope.TERMS_ONLY,
        game_name: str = "Paradox Game",
        target_language: str = "the configured target language",
        reasoning_language: str = "the configured review language",
        core_units: Sequence[LocalTextUnit] | None = None,
        edge_units: Sequence[LocalTextUnit] = (),
    ) -> StructuredNeologismExtraction:
        """Return the unified extraction contract for one already-read chunk."""

        return StructuredNeologismExtractor(self.client).extract(
            source_items,
            scope=scope,
            game_name=game_name,
            allow_legacy_term_array=False,
            target_language=target_language,
            reasoning_language=reasoning_language,
            core_units=core_units,
            edge_units=edge_units,
        )

    def _generate(self, messages: List[Dict[str, str]]) -> str:
        try:
            response = self.client.generate_with_messages(messages, temperature=0.1)
        except Exception as exc:
            raise NeologismMiningError(f"LLM request failed: {exc}") from exc
        if not response or not response.strip():
            raise NeologismMiningError("LLM returned an empty response")
        return response.strip()

    @staticmethod
    def _strip_code_fence(response: str) -> str:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            first_newline = cleaned.find("\n")
            cleaned = cleaned[first_newline + 1:] if first_newline >= 0 else ""
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    def _parse_with_repair(self, messages: List[Dict[str, str]], adapter: TypeAdapter, stage: str):
        response = self._generate(messages)
        try:
            return adapter.validate_python(json.loads(self._strip_code_fence(response)))
        except (json.JSONDecodeError, ValidationError, TypeError) as first_error:
            repair_messages = messages + [
                {"role": "assistant", "content": response},
                {
                    "role": "user",
                    "content": (
                        "The previous response did not satisfy the required JSON schema. "
                        f"Validation error: {first_error}. "
                        "Correct the previous response without changing valid candidate text. "
                        "Return the corrected raw JSON array only. Do not add markdown or commentary."
                    ),
                },
            ]
            repaired = self._generate(repair_messages)
            try:
                return adapter.validate_python(json.loads(self._strip_code_fence(repaired)))
            except (json.JSONDecodeError, ValidationError, TypeError) as second_error:
                self.logger.error("Structured %s output failed validation after one repair", stage)
                raise NeologismMiningError(
                    f"LLM returned invalid structured {stage} output after one repair"
                ) from second_error

    @staticmethod
    def _review_set_diagnostics(
        expected_originals: List[str], reviews: List[NeologismReview]
    ) -> Dict[str, List[str]]:
        expected_counts = Counter(expected_originals)
        received_counts = Counter(review.original for review in reviews)
        return {
            "missing": list((expected_counts - received_counts).elements()),
            "unexpected": list((received_counts - expected_counts).elements()),
            "duplicate": sorted(
                original for original, count in received_counts.items() if count > 1
            ),
        }

    @staticmethod
    def _format_review_diagnostics(diagnostics: Dict[str, List[str]]) -> str:
        def bounded(values: List[str]) -> List[str]:
            limit = 10
            bounded_values = [
                value[:117] + "..." if len(value) > 120 else value
                for value in values[:limit]
            ]
            if len(values) > limit:
                bounded_values.append("...")
            return bounded_values

        return "; ".join(
            f"{name}={bounded(diagnostics[name])}"
            for name in ("missing", "unexpected", "duplicate")
        )

    def _repair_review_set_mismatch(
        self,
        candidates: List[Dict[str, Any]],
        *,
        system_prompt: str,
        diagnostics: Dict[str, List[str]],
    ) -> List[NeologismReview]:
        candidates_by_original = {candidate["original"]: candidate for candidate in candidates}
        repair_originals = list(dict.fromkeys([
            *diagnostics["missing"],
            *diagnostics["duplicate"],
        ]))
        repair_candidates = [
            candidates_by_original[original]
            for original in repair_originals
            if original in candidates_by_original
        ]
        repair_prompt = (
            "The previous review response was rejected because its candidate set did not match. "
            "Return exactly one review for each repair candidate below, and return no other originals. "
            "Preserve each repair candidate's `original` exactly. Unexpected previous rows are discarded. "
            "Output only the raw JSON array.\n\n"
            f"Bounded mismatch diagnostics: {self._format_review_diagnostics(diagnostics)}\n"
            f"Repair candidates:\n{json.dumps(repair_candidates, ensure_ascii=False)}"
        )
        try:
            response = self._generate([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": repair_prompt},
            ])
            return REVIEW_LIST_ADAPTER.validate_python(
                json.loads(self._strip_code_fence(response))
            )
        except (json.JSONDecodeError, ValidationError, TypeError, NeologismMiningError) as error:
            raise NeologismMiningError(
                "LLM review candidate-set mismatch repair failed "
                f"({self._format_review_diagnostics(diagnostics)}; invalid repair output/request)"
            ) from error

    @staticmethod
    def _candidate_requires_review(candidate: Dict[str, Any]) -> bool:
        explicit = candidate.get("needs_review", candidate.get("review_required"))
        if explicit is not None:
            return bool(explicit)
        return not (candidate.get("suggestion") and candidate.get("reasoning"))

    def extract_terms(
        self,
        text_chunk: str,
        target_lang: str = "Chinese",
        target_lang_code: str = "zh-CN",
        game_name: str = "Paradox Game",
    ) -> List[NeologismTerm]:
        del target_lang, target_lang_code
        extraction = StructuredNeologismExtractor(self.client).extract(
            [SourceItem(
                source_item_id="legacy-chunk-0",
                relative_path="legacy-chunk.txt",
                source_order=0,
                source_text=text_chunk,
                provenance="text_inferred",
            )],
            scope=AnalysisScope.TERMS_ONLY,
            game_name=game_name,
            allow_legacy_term_array=True,
        )
        return [NeologismTerm(
            original=term.original,
            category=term.category,
            confidence=term.confidence,
        ) for term in extraction.terms]

    def review_terms(
        self,
        candidates: List[Dict[str, Any]],
        *,
        source_lang: str,
        target_lang: str,
        game_name: str,
        review_language: str = "en",
    ) -> Dict[str, NeologismReview]:
        """Review only incomplete or explicitly flagged fallback candidates.

        The normal extraction contract may already provide suggestion and
        reasoning.  Such candidates are skipped unless ``needs_review`` or
        ``review_required`` is explicitly true; legacy candidates without
        those fields remain reviewable for compatibility.
        """

        review_candidates = [
            candidate for candidate in candidates if self._candidate_requires_review(candidate)
        ]
        if not review_candidates:
            return {}
        system_prompt = self.REVIEW_SYSTEM_PROMPT.format(
            source_lang=source_lang,
            target_lang=target_lang,
            game_name=game_name,
            review_language=review_language,
        )
        reviews = self._parse_with_repair(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(review_candidates, ensure_ascii=False)},
            ],
            REVIEW_LIST_ADAPTER,
            "review",
        )
        expected_originals = [candidate["original"] for candidate in review_candidates]
        expected_original_set = set(expected_originals)
        diagnostics = self._review_set_diagnostics(expected_originals, reviews)
        repair_attempted = bool(diagnostics["missing"] or diagnostics["duplicate"])
        if diagnostics["missing"] or diagnostics["unexpected"] or diagnostics["duplicate"]:
            self.logger.warning(
                "LLM review candidate-set mismatch; applying bounded recovery (%s)",
                self._format_review_diagnostics(diagnostics),
            )
            repaired_reviews = (
                self._repair_review_set_mismatch(
                    review_candidates,
                    system_prompt=system_prompt,
                    diagnostics=diagnostics,
                )
                if repair_attempted
                else []
            )
            duplicate_originals = set(diagnostics["duplicate"])
            valid_initial_reviews = [
                review for review in reviews
                if review.original in expected_original_set
                and review.original not in duplicate_originals
            ]
            reviews = valid_initial_reviews + repaired_reviews

        final_diagnostics = self._review_set_diagnostics(expected_originals, reviews)
        if (
            final_diagnostics["missing"]
            or final_diagnostics["unexpected"]
            or final_diagnostics["duplicate"]
            or len(reviews) != len(review_candidates)
        ):
            raise NeologismMiningError(
                "LLM review output did not match the requested candidate set "
                f"({self._format_review_diagnostics(final_diagnostics)}; repair_attempted="
                f"{repair_attempted})"
            )
        return {review.original: review for review in reviews}
