"""Resolve collection references through existing managed project outputs."""
from pathlib import Path

from scripts.app_settings import GAME_PROFILES_BY_ID, LANGUAGE_BY_CODE
from scripts.core.services.translation_package_workflow import _outputs, _select_output, PackageWorkflowError
from scripts.core.services.mars_translation_package import LANGUAGE_NAMES
from scripts.shared.services import project_manager


async def project_by_id(project_id: str) -> dict:
    project = await project_manager.get_project(project_id)
    if not project:
        raise PackageWorkflowError(404, "project_not_found", "Member project no longer exists.")
    return project


def output_options(project: dict) -> list[dict]:
    # Ownership is recorded in the project sidecar; filenames alone never grant
    # access to arbitrary directories supplied by a caller.
    rows = _outputs(project)
    for row in rows:
        row["language_code"] = next((code for code in LANGUAGE_BY_CODE
                                     if row["output_folder_name"].startswith(code + "-")), "")
    return rows


def select_output(project: dict, selection: dict) -> Path:
    name, language = selection["output_folder_name"], selection["language_code"]
    matches = [row for row in output_options(project) if row["output_folder_name"] == name]
    if len(matches) != 1 or matches[0]["language_code"] != language:
        raise ValueError("Select a project-owned output with the matching target language.")
    return _select_output(project, name)


def supported_languages(game_id: str) -> list[str]:
    if game_id == "surviving_mars":
        return list(LANGUAGE_NAMES)
    profile = GAME_PROFILES_BY_ID.get(game_id, {})
    configured = profile.get("supported_language_keys")
    if isinstance(configured, list):
        return [code for code, language in LANGUAGE_BY_CODE.items() if language["key"] in configured]
    return list(LANGUAGE_BY_CODE)


async def project_options(project_id: str) -> dict:
    project = await project_by_id(project_id)
    game_id = project.get("game_id", "")
    return {"project_id": project_id, "game_id": game_id,
            "translation_outputs": [{key: row[key] for key in ("output_folder_name", "language_code")}
                                    for row in output_options(project)],
            "languages": [{"code": code, "name": LANGUAGE_BY_CODE.get(code, {}).get("name", code)}
                          for code in supported_languages(game_id)], "warnings": []}


async def validate_members(game_id: str, data: dict) -> None:
    if game_id not in GAME_PROFILES_BY_ID:
        raise PackageWorkflowError(422, "unsupported_game", "Choose a registered Remis game.")
    if not set(data["target_languages"]).issubset(supported_languages(game_id)):
        raise PackageWorkflowError(422, "unsupported_language", "Choose target languages supported by this game.")
    for member in data["members"]:
        project = await project_by_id(member["project_id"])
        if project.get("game_id") != game_id:
            raise PackageWorkflowError(422, "mixed_games", "All member projects must belong to the collection's game.")
        # Incomplete selections may be saved as a draft; previews block export.
        for selection in member["outputs"]:
            select_output(project, selection)


async def reject_source_publication(collection: dict, steam_id: str) -> None:
    if not steam_id or collection["game_id"] != "surviving_mars":
        return
    from scripts.core.mars_pipeline.publication_identity import read_source_workshop_id
    from scripts.core.mars_pipeline.workflow_delivery import _context
    for member in collection["members"]:
        _, receipt = await _context(member["project_id"])
        if read_source_workshop_id(receipt["source_path"]) == steam_id:
            raise PackageWorkflowError(422, "source_publication_id", "Bind your own collection Workshop item, not an original author's item.")
