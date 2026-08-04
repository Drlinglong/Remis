"""Draft edit and pre-publication contracts for Context Archive tree v2."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, Field, model_validator

from scripts.schemas.context_tree_v2_nodes import (
    MAX_EDGE_COUNT,
    MAX_FRAGMENT_COUNT,
    MAX_GROUP_COUNT,
    MAX_REASON_LENGTH,
    MAX_STORY_COUNT,
    MAX_UNIT_COUNT,
    EntityDigest,
    EntityEvidenceReference,
    Identifier,
    LabelText,
    LocalFragmentCard,
    OrderedFragmentEdge,
    SiblingGroup,
    SourceEvidenceReference,
    Story,
    UnitRoute,
    UnitRouteKind,
    UnresolvedReference,
    _ExternalContract,
)


MAX_OPERATION_COUNT = 500
DraftOperationKind = Literal[
    "create_story", "rename_story", "delete_story", "create_group", "rename_group",
    "delete_group", "move_fragment", "reorder_fragment", "set_unit_route",
    "mark_unresolved", "resolve_reference", "update_derived_summary", "add_story",
    "remove_story", "add_group", "remove_group",
]
ValidationSeverity = Literal["error", "warning"]


class TreeDraftOverrideOperation(_ExternalContract):
    """One relationship or derived-value edit in a tree draft."""

    operation_id: Identifier | None = None
    operation: DraftOperationKind = Field(validation_alias=AliasChoices("operation", "operation_type", "action"))
    story_id: Identifier | None = None
    group_id: Identifier | None = None
    fragment_id: Identifier | None = None
    local_unit_id: Identifier | None = None
    target_group_id: Identifier | None = Field(
        default=None,
        validation_alias=AliasChoices("target_group_id", "to_group_id", "destination_group_id"),
    )
    before_fragment_id: Identifier | None = Field(
        default=None,
        validation_alias=AliasChoices("before_fragment_id", "previous_fragment_id"),
    )
    target_id: Identifier | None = None
    reference_id: Identifier | None = None
    fragment_ids: tuple[Identifier, ...] = Field(default=(), max_length=MAX_FRAGMENT_COUNT)
    new_name: LabelText | None = Field(default=None, validation_alias=AliasChoices("new_name", "name", "label"))
    route: UnitRouteKind | None = None
    derived_summary: str | None = Field(default=None, min_length=1, max_length=1200)
    reason: str | None = Field(default=None, min_length=1, max_length=MAX_REASON_LENGTH)
    note: str | None = Field(default=None, min_length=1, max_length=MAX_REASON_LENGTH)

    @model_validator(mode="after")
    def _validate_operation_payload(self) -> "TreeDraftOverrideOperation":
        allowed = self._allowed_fields()
        supplied = {
            name for name in self.model_fields_set
            if name not in {"operation", "operation_id", "note"}
            and getattr(self, name, None) not in (None, "", (), [], {})
        }
        unexpected = supplied - allowed
        if unexpected:
            raise ValueError(f"{self.operation} draft operation contains unsupported fields: {sorted(unexpected)}")
        required = {
            "create_story": ("story_id", "new_name"), "add_story": ("story_id", "new_name"),
            "rename_story": ("story_id", "new_name"), "delete_story": ("story_id",),
            "remove_story": ("story_id",), "create_group": ("group_id", "story_id", "new_name"),
            "add_group": ("group_id", "story_id", "new_name"), "rename_group": ("group_id", "new_name"),
            "delete_group": ("group_id",), "remove_group": ("group_id",),
            "move_fragment": ("fragment_id", "target_group_id"),
            "reorder_fragment": ("group_id", "fragment_id"),
            "set_unit_route": ("local_unit_id", "route"),
            "mark_unresolved": ("reference_id", "target_id", "reason"),
            "resolve_reference": ("reference_id",),
            "update_derived_summary": ("target_id", "derived_summary"),
        }[self.operation]
        missing = [name for name in required if getattr(self, name) is None]
        if missing:
            raise ValueError(f"{self.operation} draft operation is missing fields: {sorted(missing)}")
        if self.operation == "set_unit_route" and self.route != "narrative" and self.fragment_ids:
            raise ValueError("non-narrative draft routes cannot carry fragment IDs")
        return self

    def _allowed_fields(self) -> set[str]:
        return {
            "create_story": {"story_id", "new_name"}, "add_story": {"story_id", "new_name"},
            "rename_story": {"story_id", "new_name"}, "delete_story": {"story_id"},
            "remove_story": {"story_id"}, "create_group": {"group_id", "story_id", "new_name"},
            "add_group": {"group_id", "story_id", "new_name"}, "rename_group": {"group_id", "new_name"},
            "delete_group": {"group_id"}, "remove_group": {"group_id"},
            "move_fragment": {"fragment_id", "target_group_id", "before_fragment_id"},
            "reorder_fragment": {"group_id", "fragment_id", "before_fragment_id"},
            "set_unit_route": {"local_unit_id", "route", "fragment_ids"},
            "mark_unresolved": {"reference_id", "target_id", "reason"},
            "resolve_reference": {"reference_id"},
            "update_derived_summary": {"target_id", "derived_summary"},
        }[self.operation]


class TreeDraft(_ExternalContract):
    """Draft audit envelope kept separate from a published tree."""

    draft_id: Identifier
    project_id: Identifier
    base_release_id: Identifier
    tree_id: Identifier | None = None
    status: Literal["draft", "published", "approved", "abandoned"] = "draft"
    created_at: str | None = None
    updated_at: str | None = None
    operations: tuple[TreeDraftOverrideOperation, ...] = Field(default=(), max_length=MAX_OPERATION_COUNT)


class ReadTreeResponse(_ExternalContract):
    """Source-grounded tree plus draft relationship state for inspection."""

    project_id: Identifier
    tree_id: Identifier
    release_id: Identifier | None = None
    draft_id: Identifier | None = None
    base_release_id: Identifier | None = None
    source_snapshot_hash: str | None = Field(default=None, min_length=1, max_length=128)
    schema_version: str | None = Field(default=None, min_length=1, max_length=128)
    prompt_version: str | None = Field(default=None, min_length=1, max_length=128)
    project_title: str | None = Field(default=None, max_length=MAX_REASON_LENGTH)
    project_summary: str | None = None
    created_at: str | None = None
    local_fragments: tuple[LocalFragmentCard, ...] = Field(
        default=(), max_length=MAX_FRAGMENT_COUNT,
        validation_alias=AliasChoices("local_fragments", "fragments"),
    )
    unit_routes: tuple[UnitRoute, ...] = Field(default=(), max_length=MAX_UNIT_COUNT)
    stories: tuple[Story, ...] = Field(default=(), max_length=MAX_STORY_COUNT)
    groups: tuple[SiblingGroup, ...] = Field(
        default=(), max_length=MAX_GROUP_COUNT,
        validation_alias=AliasChoices("groups", "sibling_groups"),
    )
    fragment_edges: tuple[OrderedFragmentEdge, ...] = Field(default=(), max_length=MAX_EDGE_COUNT)
    unresolved_references: tuple[UnresolvedReference, ...] = Field(default=(), max_length=MAX_EDGE_COUNT)
    entity_evidence: tuple[EntityEvidenceReference, ...] = ()
    entity_digests: tuple[EntityDigest, ...] = ()
    candidates: tuple[dict[str, Any], ...] = ()
    term_variants: tuple[dict[str, Any], ...] = ()
    draft_operations: tuple[TreeDraftOverrideOperation, ...] = Field(default=(), max_length=MAX_OPERATION_COUNT)


class PrePublicationValidationIssue(_ExternalContract):
    """One actionable pre-publication diagnostic."""

    code: str = Field(min_length=1, max_length=100)
    severity: ValidationSeverity
    message: str = Field(min_length=1, max_length=MAX_REASON_LENGTH)
    reference_ids: tuple[Identifier, ...] = Field(default=(), max_length=20)


class PrePublicationValidationRequest(_ExternalContract):
    """Request to validate one draft before publication."""

    project_id: Identifier
    tree_id: Identifier
    draft_id: Identifier
    base_release_id: Identifier | None = None
    include_warnings: bool = True
    reject_unresolved: bool = True


class PrePublicationValidationResult(_ExternalContract):
    """Bounded, source-independent validation output for publication gates."""

    project_id: Identifier
    tree_id: Identifier
    draft_id: Identifier
    valid: bool
    errors: tuple[PrePublicationValidationIssue, ...] = Field(default=(), max_length=MAX_EDGE_COUNT)
    warnings: tuple[PrePublicationValidationIssue, ...] = Field(default=(), max_length=MAX_EDGE_COUNT)
    unresolved_references: tuple[UnresolvedReference, ...] = Field(default=(), max_length=MAX_EDGE_COUNT)
    fragment_count: int = Field(default=0, ge=0, le=MAX_FRAGMENT_COUNT)
    group_count: int = Field(default=0, ge=0, le=MAX_GROUP_COUNT)
    edge_count: int = Field(default=0, ge=0, le=MAX_EDGE_COUNT)
    unit_route_count: int = Field(default=0, ge=0, le=MAX_UNIT_COUNT)
    checked_at: str | None = None

    @model_validator(mode="after")
    def _keep_validity_consistent(self) -> "PrePublicationValidationResult":
        if self.valid and self.errors:
            raise ValueError("a valid publication result cannot contain errors")
        return self


class PublishTreeDraftRequest(_ExternalContract):
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=240)


__all__ = [
    "DraftOperationKind", "PrePublicationValidationIssue", "PrePublicationValidationRequest",
    "PrePublicationValidationResult", "ReadTreeResponse", "TreeDraft", "TreeDraftOverrideOperation",
    "PublishTreeDraftRequest", "ValidationSeverity", "MAX_OPERATION_COUNT",
]
