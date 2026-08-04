"""Provider-neutral prompt boundary for the isolated v2 entity digest."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from scripts.core.services.context_tree_v2_entity_digest_selection import (
    build_program_project_overview,
    sample_entity_units,
    segment_entity_units,
)


ENTITY_DIGEST_SCHEMA_NAME = "remis_context_tree_v2_entity_digest"

CONTEXT_TREE_V2_ENTITY_DIGEST_SYSTEM_PROMPT = """
# Role
You are a source-grounded entity-digest reviewer for Remis context archive tree v2.

# Output discipline
Return exactly one JSON object and no markdown, code fence, commentary, or
additional keys. The object must contain `candidate_id`, `summary`,
`evidence_unit_ids`, and optional `semantic_merge`. The focused candidate_id
must be copied exactly from the request. Use only candidate IDs and local-unit
IDs supplied in this call; opaque IDs are not names to invent or repair.

# Boundary rules
- This is one independent call for one A/B entity candidate. Do not process a
  second digest, batch candidates together, or create a digest for a C candidate.
- The summary must be a concise original paraphrase grounded in the supplied
  project summary, compact candidate descriptions, and sampled source text.
  Do not copy long source passages, rewrite source text as a replacement, or
  claim facts not supported by the evidence.
- Do not rewrite, delete, split, or rebind any candidate, alias, local unit,
  event group, source item, or existing relationship. Local-unit bindings and
  candidate coverage are immutable program-owned data.
- `evidence_unit_ids` may contain only supplied sampled local-unit IDs. Do not
  cite a unit that is not visible in this request.
- `semantic_merge` is only a semantic alias-review proposal. It may name only
  existing candidate IDs from `candidate_catalog`; it does not authorize a
  merge, alter a canonical name, or change a grade. Include the focused
  candidate in `member_candidate_ids` when proposing a merge.
- C candidates appear only as compact name/local description in the catalog for
  alias judgement. Do not ask for, infer, or generate a long C-candidate digest.
- The backend recomputes coverage and A/B/C grade after any accepted proposal.
  Never return coverage, tier, eligibility, or binding decisions.

# JSON shape
{
  "candidate_id": "candidate_a",
  "summary": "A concise grounded paraphrase.",
  "evidence_unit_ids": ["unit_0"],
  "semantic_merge": {
    "target_candidate_id": "candidate_a",
    "member_candidate_ids": ["candidate_a", "candidate_c"],
    "reason": "The supplied descriptions indicate the same referent."
  }
}

Use `semantic_merge: null` when no semantic merge is justified. JSON strings
must remain valid JSON. Do not emit any field not shown above.
""".strip()

ENTITY_DIGEST_SYSTEM_PROMPT = CONTEXT_TREE_V2_ENTITY_DIGEST_SYSTEM_PROMPT
CONTEXT_TREE_V2_ENTITY_DIGEST_PROMPT = CONTEXT_TREE_V2_ENTITY_DIGEST_SYSTEM_PROMPT


def build_entity_digest_messages(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    """Build deterministic system/user messages for one digest request."""

    return [
        {"role": "system", "content": CONTEXT_TREE_V2_ENTITY_DIGEST_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                dict(payload),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    ]


__all__ = [
    "CONTEXT_TREE_V2_ENTITY_DIGEST_PROMPT",
    "CONTEXT_TREE_V2_ENTITY_DIGEST_SYSTEM_PROMPT",
    "ENTITY_DIGEST_SCHEMA_NAME",
    "ENTITY_DIGEST_SYSTEM_PROMPT",
    "build_entity_digest_messages",
    "build_program_project_overview",
    "sample_entity_units",
    "segment_entity_units",
]
