"""Build the compact universal translation context shown to translators."""

from __future__ import annotations

import re
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from scripts.core.services.context_research_external_context import (
    ContextResearchExternalContext,
)


class UniversalTranslationContext(BaseModel):
    """Short, source-audited context shared by every translation batch."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    text: str = Field(default="", max_length=600)
    source_item_ids: tuple[str, ...] = Field(default=(), max_length=20)
    external_source_kinds: tuple[str, ...] = Field(default=(), max_length=4)
    generation: str = Field(default="deterministic_extract", max_length=40)


def build_universal_translation_context(
    request: Any,
    events: Iterable[Any],
    narratives: Iterable[Any],
    entities: Iterable[Any],
    *,
    proposed_text: str = "",
) -> UniversalTranslationContext:
    """Prefer an audited proposal, otherwise create a bounded extractive summary."""

    event_items = sorted(tuple(events), key=lambda item: (item.sequence, item.chain_id))
    narrative_items = tuple(narratives)
    entity_items = tuple(entities)
    external = getattr(request, "external_context", None)
    text = _bounded(proposed_text)
    generation = "lead_synthesized" if text else "deterministic_extract"
    if not text:
        text = _extractive_text(request, event_items, narrative_items, entity_items, external)
    source_ids = _source_ids(event_items, narrative_items, entity_items)
    source_kinds = _external_source_kinds(external)
    return UniversalTranslationContext(
        text=text,
        source_item_ids=source_ids,
        external_source_kinds=source_kinds,
        generation=generation,
    )


def _extractive_text(
    request: Any,
    events: tuple[Any, ...],
    narratives: tuple[Any, ...],
    entities: tuple[Any, ...],
    external: ContextResearchExternalContext | None,
) -> str:
    language = str(getattr(request, "description_language", "")).casefold()
    if language.startswith("zh"):
        return _chinese_text(request, events, narratives, entities, external)
    return _english_text(request, events, narratives, entities, external)


def _chinese_text(request, events, narratives, entities, external) -> str:
    metadata = external.metadata if external else {}
    title = _first(metadata, "name") or str(getattr(request, "game_name", "Paradox 模组"))
    subject = "、".join(_bounded(getattr(item, "name", ""), 18) for item in entities[:2] if getattr(item, "name", ""))
    event_text = "；".join(_sentence(getattr(item, "event", ""), 30) for item in events[:2])
    background = "；".join(_sentence(getattr(item, "summary", ""), 24) for item in narratives[:1])
    workshop_title = _first(external.workshop if external else {}, "title")
    hints = "；".join(value for value in (subject, event_text, background) if value)
    if workshop_title and workshop_title.casefold() != str(title).casefold():
        hints = "；".join(value for value in (hints, _sentence(workshop_title, 20)) if value)
    if not hints:
        hints = "以源文本中的专名、事件因果和界面语气为准"
    return _bounded(f"{title}的翻译语境围绕{hints}展开；保持专名、事件先后、因果关系与玩家可见语气一致。", 100)


def _english_text(request, events, narratives, entities, external) -> str:
    metadata = external.metadata if external else {}
    title = _first(metadata, "name") or str(getattr(request, "game_name", "Paradox mod"))
    subject = ", ".join(_bounded(getattr(item, "name", ""), 24) for item in entities[:2] if getattr(item, "name", ""))
    event_text = "; ".join(_sentence(getattr(item, "event", ""), 42) for item in events[:2])
    background = _sentence(getattr(narratives[0], "summary", ""), 30) if narratives else ""
    hints = "; ".join(value for value in (subject, event_text, background) if value)
    if not hints:
        hints = "the source text's named terms, event order, and player-facing tone"
    return _bounded(f"{title} centers on {hints}. Keep names, event causality, ordering, and player-facing tone consistent.", 300)


def _source_ids(*groups: Iterable[Any]) -> tuple[str, ...]:
    values: list[str] = []
    for group in groups:
        for item in group:
            values.extend(str(value) for value in getattr(item, "source_item_ids", ()) if value)
    return tuple(dict.fromkeys(values))[:20]


def _external_source_kinds(external: ContextResearchExternalContext | None) -> tuple[str, ...]:
    if external is None:
        return ()
    return tuple(
        source.kind
        for source in (external.metadata_source, external.workshop_source)
        if source is not None and source.status == "loaded"
    )


def _first(values: dict[str, Any], key: str) -> str:
    value = values.get(key, "") if isinstance(values, dict) else ""
    return str(value).strip()


def _sentence(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return _bounded(text.rstrip("。.!！?？") + "。", limit) if text else ""


def _bounded(value: Any, limit: int = 240) -> str:
    text = str(value or "").strip()
    return text[: max(0, limit - 1)] + "…" if len(text) > limit else text


__all__ = ["UniversalTranslationContext", "build_universal_translation_context"]
