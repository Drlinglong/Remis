"""Program-built event-group context for tree v2 translation delivery."""

from __future__ import annotations

from typing import Sequence

from scripts.core.services.context_tree_v2_contract import (
    ContextTreeCatalog,
    EventGroupContext,
    LocalFragment,
    ProjectedUnitRoute,
    TranslationContextProjection,
    TreeProjectionResult,
)


class ContextTreeV2ContextService:
    """Build context from stored local summaries without aggregate synthesis."""

    @classmethod
    def build_group_contexts(
        cls,
        catalog: ContextTreeCatalog,
        fragments: Sequence[LocalFragment],
    ) -> tuple[EventGroupContext, ...]:
        fragment_by_id = cls._fragment_index(fragments)
        unresolved = set(catalog.unresolved_fragment_ids)
        contexts: list[EventGroupContext] = []
        # Group IDs are sorted for stable display only; no sibling order is
        # conveyed. Fragment order is copied exactly from each group.
        for group in sorted(catalog.groups, key=lambda item: item.group_id):
            if any(fragment_id not in fragment_by_id for fragment_id in group.fragment_ids):
                missing = [
                    fragment_id for fragment_id in group.fragment_ids
                    if fragment_id not in fragment_by_id
                ]
                raise ValueError(
                    f"Event group {group.group_id} referenced unknown fragments: {missing}"
                )
            if any(fragment_id in unresolved for fragment_id in group.fragment_ids):
                raise ValueError(
                    f"Event group {group.group_id} contains unresolved fragments"
                )
            contexts.append(EventGroupContext(
                group_id=group.group_id,
                fragment_ids=list(group.fragment_ids),
                summary_bullets=[
                    fragment_by_id[fragment_id].summary
                    for fragment_id in group.fragment_ids
                ],
            ))
        return tuple(contexts)

    @staticmethod
    def format_group_context(group: EventGroupContext) -> str:
        """Format one group while keeping its local fragment order visible."""

        return "\n".join(f"- {summary}" for summary in group.summary_bullets)

    @classmethod
    def project_translation_context(
        cls,
        projected_route: ProjectedUnitRoute,
        group_contexts: Sequence[EventGroupContext],
        *,
        project_summary: str = "",
    ) -> TranslationContextProjection:
        contexts_by_id = {context.group_id: context for context in group_contexts}
        missing_groups = {
            group_id for group_id in projected_route.group_ids
            if group_id not in contexts_by_id
        }
        if missing_groups:
            raise ValueError(
                f"Projected route referenced unknown group contexts: {sorted(missing_groups)}"
            )
        event_groups = (
            [contexts_by_id[group_id] for group_id in projected_route.group_ids]
            if projected_route.receives_event_context
            else []
        )
        return TranslationContextProjection(
            local_unit_id=projected_route.local_unit_id,
            route=projected_route.route,
            project_summary=project_summary,
            event_groups=event_groups,
            unresolved_fragment_ids=list(projected_route.unresolved_fragment_ids),
        )

    @classmethod
    def project_all_translation_contexts(
        cls,
        projection: TreeProjectionResult,
        catalog: ContextTreeCatalog,
        fragments: Sequence[LocalFragment],
        *,
        project_summary: str = "",
    ) -> tuple[TranslationContextProjection, ...]:
        groups = cls.build_group_contexts(catalog, fragments)
        return tuple(
            cls.project_translation_context(
                route,
                groups,
                project_summary=project_summary,
            )
            for route in projection.unit_routes
        )

    @staticmethod
    def _fragment_index(fragments: Sequence[LocalFragment]) -> dict[str, LocalFragment]:
        index: dict[str, LocalFragment] = {}
        for fragment in fragments:
            if fragment.fragment_id in index:
                raise ValueError(
                    f"Local fragment identities are duplicated: {fragment.fragment_id}"
                )
            index[fragment.fragment_id] = fragment
        return index
