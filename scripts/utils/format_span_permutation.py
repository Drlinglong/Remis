"""Recognize format spans reordered by target-language word order.

Translations often move whole formatting spans (``§Y日本§!完成的§G研究§!`` ->
``§G Research§! completed by §Y Japan§!``).  Positional comparison reports every
swapped opener as an identity change even though each span kept its identity,
its bound protected tokens and its nesting relation.  This module answers one
question: is the target's span set a permutation of the source's span set?
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Hashable, List, Optional, Sequence

if TYPE_CHECKING:
    from scripts.utils.game_format_contract import FormatSpan, ParsedFormatStructure


def _span_keys(spans: Sequence["FormatSpan"]) -> List[Hashable]:
    """Key each span by opener, bound protected tokens and enclosing span chain."""
    keys: List[Hashable] = []
    enclosing: List[tuple] = []
    for span in sorted(spans, key=lambda item: item.opener.start):
        while enclosing and enclosing[-1][0].closer.end <= span.opener.start:
            enclosing.pop()
        parent_key: Optional[Hashable] = enclosing[-1][1] if enclosing else None
        key = (span.opener.raw, span.protected_tokens, parent_key)
        keys.append(key)
        enclosing.append((span, key))
    return keys


def spans_are_permutation(
    source: "ParsedFormatStructure",
    target: "ParsedFormatStructure",
) -> bool:
    """Return whether target spans only differ from source spans by order."""
    if not source.balanced or not target.balanced or not source.spans:
        return False
    if len(source.spans) != len(target.spans):
        return False
    return Counter(_span_keys(source.spans)) == Counter(_span_keys(target.spans))


__all__ = ["spans_are_permutation"]
