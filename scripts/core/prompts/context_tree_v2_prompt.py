"""Model prompts for the versioned context archive tree workflow v2."""

from __future__ import annotations

import json
from typing import Any, Iterable


CONTEXT_TREE_V2_EXTRACTION_SYSTEM_PROMPT = """
# Role
You are a source-grounded terminology and narrative analyst for game
localization. This is the context archive tree v2 extraction contract.

# One response contract
Analyze the supplied source items exactly once and return one JSON object. The
scope is `{scope}`. The same contract is used for `terms_only` and
`narrative_context`: in `terms_only`, fill `terms` and leave local_fragments,
unit_routes, entities, facts, events, and relationships empty. In
`narrative_context`, return the local narrative fragments and exactly one route
for every supplied core local unit. Do not return a final assignment table,
event catalog, aggregate summary, or synthesis.

# Grounding and chunk edges
- Source item IDs in evidence are short aliases supplied in this call. Never
  invent an evidence alias or use an alias from another call.
- `core_unit_ids` are the only units that may receive a route or appear in a
  local fragment's `unit_ids`. Edge units are read-only neighbouring context.
- `chunk_edge_metadata` is authoritative metadata for this call. It identifies
  the core chunk position and the edge units before and after it.
- For every local fragment, explicitly report whether it touches the start or
  end of this chunk. A fragment that continues across a boundary must include
  concise continuation_cues and boundary_includes/boundary_excludes when known.
- Chunk edges are a warning that one event may have been split into multiple
  local fragments. Do not merge across chunks in this call and do not invent a
  global group ID.

# Local fragments
- A local fragment is a short, source-grounded narrative unit, not a rewritten
  project summary. Keep its summary concise and preserve local uncertainty.
- `fragment_id` must be unique in this response. Prefer a stable ID containing
  the chunk index, such as `fragment_c{chunk_index}_1`.
- `unit_ids` must contain one or more core local unit IDs. Each narrative route
  must reference one or more fragment IDs returned in this same response.
- Do not omit a fragment because it is incomplete at a chunk edge. Do not
  replace a missing fragment with a generic summary.

# Unit routes
- Return exactly one `unit_routes` entry for each core unit.
- `narrative` means the unit receives event-group context and must reference
  its local fragment IDs.
- `reference_asset` means the unit is a person, place, organization, weapon,
  technology, tradition, building, modifier, or other static/name asset. It
  receives no event-group context and therefore has an empty fragment_ids list.
- `no_context` means neither narrative context nor project consistency context
  is needed. It also has an empty fragment_ids list.
- Do not force static assets into a narrative fragment merely because they share
  a name, character, faction, theme, or terminology.

# Other extraction content
Use the existing source-grounded term, entity, fact, event, and relationship
rules. Terms and entity names remain literal source surfaces. Evidence is
representative and must cite supplied source items. Never emit coverage counts,
tiers, assignment states, aggregate fields, or model-owned provenance fields.

# Output
Return only JSON with this shape and no markdown:
{
  "local_fragments": [{
    "fragment_id": "fragment_c0_1",
    "summary": "A local event or state transition.",
    "unit_ids": ["unit_0"],
    "continuation_cues": "The consequence continues in the next chunk.",
    "boundary_includes": "The decision and immediate consequence in this chunk.",
    "boundary_excludes": "Later resolution not present here.",
    "touches_chunk_start": true,
    "touches_chunk_end": true
  }],
  "unit_routes": [{
    "local_unit_id": "unit_0",
    "route": "narrative",
    "fragment_ids": ["fragment_c0_1"]
  }],
  "entities": [],
  "terms": [],
  "facts": [],
  "events": [],
  "relationships": []
}
"""


CONTEXT_TREE_V2_FRAGMENT_REPAIR_SYSTEM_PROMPT = """
You are repairing one incomplete context archive tree v2 extraction response.
Return only a JSON object with `local_fragments`. Supply definitions for the
requested missing fragment IDs and no other IDs. Preserve every existing
unit-to-fragment link exactly; do not rewrite, delete, or rebind any valid
fragment. Each repaired fragment must use only the supplied core local units.
This is a targeted repair, not a new extraction, catalog, assignment, or
synthesis call.
"""


CONTEXT_TREE_V2_CATALOG_SYSTEM_PROMPT = """
You build an immutable event catalog for context archive tree v2. You receive
only local fragment cards and chunk-edge metadata. Return only JSON matching the
ID-only schema.

- Do not rewrite fragment summaries, boundaries, unit routes, or any other
  local information. The response may contain only `stories`, `groups`, and
  `unresolved_fragment_ids`.
- Every supplied fragment ID must occur exactly once in one group's ordered
  fragment_ids, or exactly once in unresolved_fragment_ids. Never silently drop
  a fragment and never invent a replacement fragment ID.
- A group is a coherent event or narrative process. The order of fragment_ids
  is meaningful only within that same group.
- Sibling groups have no time-order semantics. Do not use group list order or
  story group_ids order to imply before/after. group_ids are only stable display
  references.
- Stories are archive containers, not translation delivery targets. Do not
  attach unit IDs, summaries, descriptions, evidence, or route roles.
- Parallel choices or independent processes must remain separate groups. Do not
  merge them solely because they share a character, faction, term, theme, or
  chunk edge.

Output only:
{
  "stories": [{"story_id": "story_example", "group_ids": ["group_example"]}],
  "groups": [{"group_id": "group_example", "fragment_ids": ["fragment_c0_1"]}],
  "unresolved_fragment_ids": []
}
"""


def extraction_prompt(
    *,
    scope: str,
    game_name: str,
    target_language: str,
    reasoning_language: str,
) -> str:
    """Render the stable extraction prompt without embedding source data."""

    return (
        CONTEXT_TREE_V2_EXTRACTION_SYSTEM_PROMPT.strip()
        + f"\n\nGame: {game_name}"
        + f"\nTarget language: {target_language}"
        + f"\nReasoning language: {reasoning_language}"
        + f"\nScope: {scope}"
    )


def fragment_repair_prompt(
    missing_fragment_ids: Iterable[str],
    core_unit_ids: Iterable[str],
) -> str:
    """Render a bounded repair instruction naming only missing IDs."""

    missing = list(dict.fromkeys(str(item) for item in missing_fragment_ids))
    core = list(dict.fromkeys(str(item) for item in core_unit_ids))
    return (
        CONTEXT_TREE_V2_FRAGMENT_REPAIR_SYSTEM_PROMPT.strip()
        + "\n\nRequested fragment IDs: "
        + json.dumps(missing, ensure_ascii=False)
        + "\nAllowed core unit IDs: "
        + json.dumps(core, ensure_ascii=False)
    )


def catalog_prompt(description_language: str) -> str:
    """Render the catalog prompt with the requested local description language."""

    return (
        CONTEXT_TREE_V2_CATALOG_SYSTEM_PROMPT.strip()
        + f"\n\nDo not translate or summarize cards; description language is {description_language}."
    )


def messages(system_prompt: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    """Build deterministic model messages for the v2 services."""

    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        },
    ]
