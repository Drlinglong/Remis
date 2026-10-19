"""Compare runtime identities without confusing target word order with damage."""

from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from scripts.utils.format_span_permutation import spans_are_permutation

if TYPE_CHECKING:
    from scripts.utils.game_format_contract import ParsedFormatStructure


def compare_runtime_tokens(
    source_parsed: "ParsedFormatStructure",
    target_parsed: "ParsedFormatStructure",
) -> Tuple[List[str], List[str], List[Dict[str, Any]], bool]:
    """Allow permutations only with exact identities, counts and span binding.

    Canonical identities retain modifiers and nested runtime expressions, while
    allowing the existing Concept display-label policy. Bound token sequences
    and enclosing span chains remain strict; this never normalizes either text.
    The caller must still validate format identity, boundaries and nesting.
    """
    source = source_parsed.runtime_tokens
    target = target_parsed.runtime_tokens
    source_keys = [token.canonical for token in source]
    target_keys = [token.canonical for token in target]
    same_inventory = Counter(source_keys) == Counter(target_keys)
    if same_inventory and source_parsed.balanced and target_parsed.balanced:
        no_spans = not source_parsed.spans and not target_parsed.spans
        if no_spans or spans_are_permutation(source_parsed, target_parsed):
            return [], [], [], False

    # Preserve the existing strict diagnostics when a permutation is unsafe.
    missing: List[str] = []
    extra: List[str] = []
    changed: List[Dict[str, Any]] = []
    matcher = SequenceMatcher(None, source_keys, target_keys, autojunk=False)
    for opcode, source_start, source_end, target_start, target_end in matcher.get_opcodes():
        if opcode == "delete":
            missing.extend(token.raw for token in source[source_start:source_end])
        elif opcode == "insert":
            extra.extend(token.raw for token in target[target_start:target_end])
        elif opcode == "replace":
            source_part = source[source_start:source_end]
            target_part = target[target_start:target_end]
            if len(source_part) == len(target_part):
                for source_token, target_token in zip(source_part, target_part):
                    changed.append(
                        {
                            "source": source_token.raw,
                            "target": target_token.raw,
                            "source_start": source_token.start,
                            "target_start": target_token.start,
                            "kind": source_token.kind,
                        }
                    )
            else:
                missing.extend(token.raw for token in source_part)
                extra.extend(token.raw for token in target_part)
    order_changed = same_inventory and source_keys != target_keys
    return missing, extra, changed, order_changed
