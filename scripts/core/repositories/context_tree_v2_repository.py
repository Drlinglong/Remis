"""Stable facade for the split context tree v2 read/write repository."""

from scripts.core.repositories.context_tree_v2_reader import ContextTreeV2Reader
from scripts.core.repositories.context_tree_v2_storage import (
    ContextTreeV2ConflictError,
    ContextTreeV2DraftClosedError,
    ContextTreeV2NotFoundError,
    ContextTreeV2OwnershipError,
    ContextTreeV2ValidationError,
)
from scripts.core.repositories.context_tree_v2_writer import ContextTreeV2Writer


class ContextTreeV2Repository(ContextTreeV2Writer, ContextTreeV2Reader):
    """Public repository combining immutable reads with draft commands."""


__all__ = [
    "ContextTreeV2ConflictError",
    "ContextTreeV2DraftClosedError",
    "ContextTreeV2NotFoundError",
    "ContextTreeV2OwnershipError",
    "ContextTreeV2Repository",
    "ContextTreeV2ValidationError",
]
