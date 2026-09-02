"""Prompts for the lightweight Context Archive workflow v3 experiment."""

from __future__ import annotations

from scripts.core.prompts.context_tree_v2_prompt import messages


WORKFLOW_V3_VERSION = "context-workflow-v3"
WORKFLOW_V3_PROMPT_VERSION = "context-archive-workflow-v3"
WORKFLOW_V3_CHECKPOINT_VERSION = "context-analysis-workflow-v3"


WORKFLOW_V3_EXTRACTION_PROMPT = """
# Role
You are a source-grounded analyst preparing a game Mod archive for translation.
Analyze the supplied core local units once. Edge units are read-only context.

# Three independent axes
For every core unit return exactly one unit_routes entry.

1. content_role describes what the text itself is:
- event_narrative: a concrete event, quest, decision, dialogue, state change, or
  directly attached event step.
- background_narrative: lore, history, setting, character background, or a
  broad situation that belongs in the archive but is not a concrete event.
- static_reference: a named technology, modifier, weapon, policy, building,
  relic, title, or other stable reference text.
- utility_or_noise: UI glue, formatting, variables, generic labels, or text
  without useful archive context.

2. delivery_route independently describes translation delivery:
- event: concrete event context should accompany translation.
- reference: stable terminology/reference context should accompany translation.
- none: no per-event or per-reference delivery is needed.

3. terms are extracted independently from every content role. Emit only
literal, translation-sensitive domain expressions such as named technologies,
buildings, modifiers, traits, projects, doctrines, slogans, resources, or
other distinctive glossary phrases. Use the same `TermContribution` contract
as the standalone terms-only miner: preserve the literal source surface in
`original`, include a grounded evidence reference, and provide a source-
grounded `suggestion` in the target language plus concise `reasoning` in the
configured review language. Do not turn an entity into a term merely because
its name needs consistent translation.

4. entities are extracted independently from every content role. Emit only
literal, plot-central or materially recurring people, places, organizations,
polities, technologies, concepts, or items. Runtime variables and placeholders
such as $NAME$, [Root.Capital.GetName], ROOT polity, or descriptions of an
unknown dynamic value are not entities.
- Entity `name` and `canonical_candidate` are source-language literal surfaces:
  copy them verbatim from source text and never translate, decorate, quote, or
  combine them with a translated label. Only entity `description` is written
  in the configured description language.

# Structural hints and boundaries
- Keys with dot-number, dot-letter, title/name/desc/tooltip, or other suffixes
  may belong to one event family. Similar key families may form a longer event
  chain. These are hints only: confirm them against the text.
- Prefer one coherent local fragment spanning related units over mechanically
  splitting every localization entry. Do not merge unrelated stories merely
  because they share a faction, character, term, theme, or file.
- Only event_narrative units appear in local_fragments. Every event_narrative
  unit must reference at least one fragment returned in this response.
- A fragment may include several related core units. Preserve source order and
  mark boundary continuation cues when a story crosses this chunk.
- Do not route or claim edge units.

# Grounding
Source item IDs are short aliases valid only in this call. All entity evidence
must cite supplied aliases. Do not invent IDs. Keep summaries concise and write
them in the configured description language.

# Deliberately unused legacy collections
Set facts, events, and relationships to empty arrays. Workflow v3 builds event
chains from local_fragments and the global catalog; generating duplicate legacy
contributions only wastes tokens and can conflict with the three axes. Terms
remain an independent output because the deterministic candidate pipeline uses
them for glossary discovery; never derive them from entity cards.

# Output
Return only JSON. The compatibility `route` mirrors delivery_route: event ->
narrative, reference -> reference_asset, none -> no_context. Remis validates and
re-derives it, so it cannot override the two orthogonal judgments.
{
  "local_fragments": [{
    "fragment_id": "fragment_c0_1",
    "summary": "A coherent local event step.",
    "unit_ids": ["unit_0", "unit_1"],
    "continuation_cues": null,
    "boundary_includes": "What this fragment contains.",
    "boundary_excludes": null,
    "touches_chunk_start": true,
    "touches_chunk_end": false
  }],
  "unit_routes": [{
    "local_unit_id": "unit_0",
    "route": "narrative",
    "content_role": "event_narrative",
    "delivery_route": "event",
    "summary": "Why this unit matters.",
    "fragment_ids": ["fragment_c0_1"]
  }],
  "entities": [],
  "terms": [],
  "facts": [],
  "events": [],
  "relationships": []
}
"""


WORKFLOW_V3_CATALOG_PROMPT = """
# Role
You are the single global lead for a game Mod archive. You receive immutable
local event-fragment cards and chunk-boundary metadata. You do not reread the
raw corpus and you do not rewrite local classifications.

# Event-chain catalog
- Every supplied fragment ID must occur exactly once in one ordered group, or
  exactly once in unresolved_fragment_ids. Never silently drop or invent IDs.
- A group is one coherent event chain or narrative process. Preserve causal and
  source order when the cards support it.
- Prefer modest over-aggregation of clearly related adjacent stages over
  fragmenting one concrete story into many tiny chains. Two related chains in
  one context package are less harmful than splitting one story into eight.
- Still separate unrelated plots, parallel alternatives, and independent
  processes. Shared names, factions, themes, or lore alone do not prove one
  chain.
- Stories are archive containers only. They are not translation targets.

# Universal translation context
Write one 50-100-character overview in the requested description language of
the Mod's central subject, setting, conflict, and tone. It is injected into
every translation batch, so it must describe the Mod as a whole rather than
list fragments or sound like a research report. Do not mention IDs, files,
workflow, uncertainty counts, or analysis methods. Keep source entity names and
terms literal; only the overview and explanatory descriptions follow this
language contract.

Return only JSON:
{
  "stories": [{"story_id": "story_main", "group_ids": ["group_main"]}],
  "groups": [{"group_id": "group_main", "fragment_ids": ["fragment_c0_1"]}],
  "unresolved_fragment_ids": [],
  "universal_translation_context": "50-100 characters in the requested description language."
}
"""


def workflow_v3_extraction_prompt(
    *, game_name: str, target_language: str, reasoning_language: str,
    description_language: str,
) -> str:
    return (
        WORKFLOW_V3_EXTRACTION_PROMPT.strip()
        + f"\n\nGame: {game_name}"
        + f"\nTarget language: {target_language}"
        + f"\nReasoning language: {reasoning_language}"
        + f"\nDescription language: {description_language}"
    )


def workflow_v3_catalog_prompt(description_language: str) -> str:
    return (
        WORKFLOW_V3_CATALOG_PROMPT.strip()
        + f"\n\nDescription language: {description_language}. "
        + "Write universal_translation_context and explanatory descriptions in this language."
    )


__all__ = [
    "WORKFLOW_V3_CHECKPOINT_VERSION",
    "WORKFLOW_V3_PROMPT_VERSION",
    "WORKFLOW_V3_VERSION",
    "messages",
    "workflow_v3_catalog_prompt",
    "workflow_v3_extraction_prompt",
]
