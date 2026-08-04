"""Public import surface for Context Archive tree v2 contracts.

The implementation is split into immutable node contracts and draft/validation
contracts so each production module remains a focused responsibility.
"""

from scripts.schemas.context_tree_v2_drafts import *  # noqa: F401,F403
from scripts.schemas.context_tree_v2_nodes import *  # noqa: F401,F403
from pydantic import model_validator


_NodeUnitRoute = UnitRoute


class UnitRoute(_NodeUnitRoute):
    """Facade-level route contract with the narrative binding invariant."""

    @model_validator(mode="after")
    def _require_narrative_fragment(self) -> "UnitRoute":
        if self.route == "narrative" and not self.fragment_ids:
            raise ValueError("narrative routes require at least one fragment")
        return self

    @property
    def role(self) -> UnitRouteKind:
        return self.route

FragmentCard = LocalFragmentCard
FragmentEdge = OrderedFragmentEdge
ContextTreeLocalFragmentCard = LocalFragmentCard
ContextTreeChunkEdgeMetadata = ChunkEdgeMetadata
ContextTreeSourceEvidenceReference = SourceEvidenceReference
ContextTreeUnitRoute = UnitRoute
ContextTreeStory = Story
ContextTreeSiblingGroup = SiblingGroup
ContextTreeFragmentEdge = OrderedFragmentEdge
ContextTreeUnresolvedReference = UnresolvedReference
ContextTreeDraftOverrideOperation = TreeDraftOverrideOperation
ContextTreeDraft = TreeDraft
ContextTreeReadResponse = ReadTreeResponse
ContextTreeV2 = ReadTreeResponse
ContextTree = ReadTreeResponse
ContextTreeV2Draft = TreeDraft
ContextTreePrePublicationValidationIssue = PrePublicationValidationIssue
ContextTreePrePublicationValidationRequest = PrePublicationValidationRequest
ContextTreePrePublicationValidationResult = PrePublicationValidationResult
TreeStory = Story
TreeGroup = SiblingGroup
TreeValidationResult = PrePublicationValidationResult
ContextTreeV2ValidationResult = PrePublicationValidationResult

__all__ = [
    "ChunkEdgeMetadata", "ContextTreeChunkEdgeMetadata", "ContextTreeDraft",
    "ContextTreeDraftOverrideOperation", "ContextTreeFragmentEdge",
    "ContextTreeLocalFragmentCard", "ContextTreePrePublicationValidationIssue",
    "ContextTreePrePublicationValidationRequest", "ContextTreePrePublicationValidationResult",
    "ContextTreeReadResponse", "ContextTreeSiblingGroup", "ContextTreeSourceEvidenceReference",
    "ContextTreeStory", "ContextTreeUnitRoute", "ContextTreeUnresolvedReference",
    "ContextTree", "ContextTreeV2", "ContextTreeV2Draft", "ContextTreeV2ValidationResult",
    "EntityAliasDescription", "EntityDigest", "EntityDigestSegment", "EntityEvidenceReference",
    "DraftOperationKind", "FragmentCard", "FragmentEdge", "LocalFragmentCard",
    "OrderedFragmentEdge", "PrePublicationValidationIssue", "PrePublicationValidationRequest",
    "PrePublicationValidationResult", "ReadTreeResponse", "SiblingGroup",
    "SourceEvidenceReference", "Story", "TreeDraft", "TreeDraftOverrideOperation", "UnitRoute",
    "TreeGroup", "TreeStory", "TreeValidationResult", "UnitRouteKind", "UnresolvedReference",
    "UnresolvedReferenceKind",
]
