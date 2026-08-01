"""Resolve the resources an initial translation run may consume."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


TRANSLATION_CONTEXT_MODES = frozenset({"none", "glossaries", "archive"})


@dataclass(frozen=True)
class TranslationResourcePolicy:
    mode: str | None
    include_main_glossary: bool
    include_project_glossary: bool
    include_selected_glossaries: bool
    include_project_context: bool

    @property
    def use_glossaries(self) -> bool:
        return any(
            (
                self.include_main_glossary,
                self.include_project_glossary,
                self.include_selected_glossaries,
            )
        )


@dataclass(frozen=True)
class TranslationRunResources:
    policy: TranslationResourcePolicy
    glossary_ids: tuple[int, ...]
    project: dict[str, Any] | None
    override_path: str | None
    project_glossary_id: int | None


def resolve_translation_resource_policy(
    mode: str | None,
    *,
    legacy_use_main_glossary: bool,
    legacy_use_project_context: bool,
) -> TranslationResourcePolicy:
    """Resolve explicit tiers while preserving requests from older clients."""

    if mode is None:
        return TranslationResourcePolicy(
            mode=None,
            include_main_glossary=legacy_use_main_glossary,
            include_project_glossary=True,
            include_selected_glossaries=True,
            include_project_context=legacy_use_project_context,
        )
    if mode not in TRANSLATION_CONTEXT_MODES:
        raise ValueError(f"Unknown translation context mode: {mode}")
    if mode == "none":
        return TranslationResourcePolicy(mode, False, False, False, False)
    return TranslationResourcePolicy(
        mode,
        include_main_glossary=True,
        include_project_glossary=True,
        include_selected_glossaries=True,
        include_project_context=mode == "archive",
    )


def resolve_translation_run_resources(
    *,
    game_id: str,
    project_id: str | None,
    selected_glossary_ids: list[int] | None,
    mode: str | None,
    legacy_use_main_glossary: bool,
    legacy_use_project_context: bool,
    project_manager: Any,
    glossary_manager: Any,
    run_async: Callable[[Any], Any],
) -> TranslationRunResources:
    """Resolve project path and ordered glossary IDs for one translation run."""

    policy = resolve_translation_resource_policy(
        mode,
        legacy_use_main_glossary=legacy_use_main_glossary,
        legacy_use_project_context=legacy_use_project_context,
    )
    glossary_ids: list[int] = []
    if policy.include_main_glossary:
        available = run_async(glossary_manager.get_available_glossaries(game_id))
        main = next((item for item in available if item.get("is_main")), None)
        if main:
            glossary_ids.append(main["glossary_id"])

    project = run_async(project_manager.get_project(project_id)) if project_id else None
    override_path = project.get("source_path") if project else None
    project_glossary_id = None
    if project_id and policy.include_project_glossary:
        project_glossary = run_async(
            glossary_manager.get_project_glossary(
                game_id,
                project_id,
                (project or {}).get("name"),
            )
        )
        if project_glossary:
            project_glossary_id = project_glossary.get("glossary_id")
            if project_glossary_id is not None and project_glossary_id not in glossary_ids:
                glossary_ids.append(project_glossary_id)

    if policy.include_selected_glossaries:
        glossary_ids.extend(
            glossary_id
            for glossary_id in selected_glossary_ids or []
            if glossary_id not in glossary_ids
        )
    return TranslationRunResources(
        policy=policy,
        glossary_ids=tuple(glossary_ids),
        project=project,
        override_path=override_path,
        project_glossary_id=project_glossary_id,
    )
