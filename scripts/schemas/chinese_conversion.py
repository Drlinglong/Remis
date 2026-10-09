"""Deterministic Chinese conversion, not an LLM translation/provider schema."""
from typing import Literal

from pydantic import Field, model_validator

from .agent_batch import StrictInput


class ConversionEntry(StrictInput):
    id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=100000)


class ChineseConversionRequest(StrictInput):
    entries: list[ConversionEntry] = Field(min_length=1, max_length=100)
    converter: Literal["Simplified", "Traditional", "Taiwan", "China", "Hongkong"] = "Taiwan"
    pre_replace: dict[str, str] = Field(default_factory=dict, max_length=100)
    post_replace: dict[str, str] = Field(default_factory=dict, max_length=100)
    protected_words: list[str] = Field(default_factory=list, max_length=500)
    modules: dict[str, Literal[-1, 0, 1]] = Field(default_factory=dict, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=200)
    approved: bool = False

    @model_validator(mode="after")
    def bounded_text_and_unambiguous_rules(self):
        if len({e.id for e in self.entries}) != len(self.entries):
            raise ValueError("Entry IDs must be unique")
        if sum(len(e.text) for e in self.entries) > 200000:
            raise ValueError("Split text into requests of at most 200,000 characters")
        for rules in [self.pre_replace, self.post_replace]:
            for key, value in rules.items():
                if not key or any(c in key + value for c in "\r\n=") or max(len(key), len(value)) > 1000:
                    raise ValueError("Replacement rules are literal single-line pairs, without '='")
        if any(not w or "\n" in w or "\r" in w or len(w) > 2000 for w in self.protected_words):
            raise ValueError("Protected words must be nonempty single-line strings")
        return self
