import json
import logging
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError


class NeologismMiningError(RuntimeError):
    """Raised when a mining model call cannot produce trustworthy structured output."""


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


TERM_LIST_ADAPTER = TypeAdapter(List[NeologismTerm])
REVIEW_LIST_ADAPTER = TypeAdapter(List[NeologismReview])


class NeologismMiner:
    """LLM boundary for grounded extraction and context-aware terminology review."""

    EXTRACTION_SYSTEM_PROMPT = """
# Role
You are a terminology analyst for game localization.

# Task
Extract potential proper nouns or author-created concepts from the supplied localization text.
Return candidates only. Do not translate them in this stage.

# Game
{game_name}

# Rules
- Every `original` value MUST occur verbatim in the user text.
- Include names, places, factions, fictional concepts, technologies, and coined phrases.
- Exclude localization keys, variables, commands, formatting codes, generic words, and punctuation.
- Prefer a complete phrase over overlapping fragments.
- `category` MUST be exactly one of: "person", "place", "faction", "concept", "technology", or "other".
- Map characters and named individuals to "person"; map events, units, and unmatched kinds to "other".
- Confidence is a number from 0 to 1.

# Output
Output only a JSON array with this schema:
[
  {{"original": "Aetherophasic Engine", "category": "technology", "confidence": 0.95}}
]
"""

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

    def extract_terms(
        self,
        text_chunk: str,
        target_lang: str = "Chinese",
        target_lang_code: str = "zh-CN",
        game_name: str = "Paradox Game",
    ) -> List[NeologismTerm]:
        del target_lang, target_lang_code
        system_prompt = self.EXTRACTION_SYSTEM_PROMPT.format(game_name=game_name)
        terms = self._parse_with_repair(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_chunk},
            ],
            TERM_LIST_ADAPTER,
            "extraction",
        )
        if len(terms) > 100:
            raise NeologismMiningError("LLM extraction exceeded the 100-candidate safety limit for one chunk")
        return terms

    def review_terms(
        self,
        candidates: List[Dict[str, Any]],
        *,
        source_lang: str,
        target_lang: str,
        game_name: str,
        review_language: str = "en",
    ) -> Dict[str, NeologismReview]:
        if not candidates:
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
                {"role": "user", "content": json.dumps(candidates, ensure_ascii=False)},
            ],
            REVIEW_LIST_ADAPTER,
            "review",
        )
        expected = {candidate["original"] for candidate in candidates}
        received = {review.original for review in reviews}
        if received != expected or len(reviews) != len(candidates):
            raise NeologismMiningError("LLM review output did not match the requested candidate set")
        return {review.original: review for review in reviews}
