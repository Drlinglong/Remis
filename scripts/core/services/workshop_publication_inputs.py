"""Read-only, bounded package inspection and approval identity."""
import hashlib
import json
import os
import stat
from pathlib import Path

from scripts.app_settings import GAME_ID_ALIASES, resolve_path
from scripts.core.services.project_version_context import read_project_sidecar
from scripts.schemas.workshop_publication import PublicationError
from scripts.utils.validation_issue_identity import issue_is_active

MAX_FILES = 20_000
MAX_BYTES = 2 * 1024**3
EXCLUDED = {".remis_errors.json", "workshop_issues.json", ".remis_project.json", "project.json"}
FORBIDDEN = {".git", ".env", ".venv", "node_modules", ".runtime", "steam_appid.txt", "config.json", "remis.sqlite"}
PARADOX_GAMES = {"victoria3", "stellaris", "hoi4", "eu4", "eu5", "ck3"}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")).encode("utf-8")).hexdigest()


def reject_links(path):
    path = Path(path).absolute()
    for candidate in [path, *path.parents]:
        attributes = candidate.lstat()
        if candidate.is_symlink() or getattr(attributes, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise PublicationError("unsafe_path", "Publication paths cannot contain links or junctions")


def output_options(project):
    source = Path(resolve_path(project["source_path"]))
    reject_links(source)
    sidecar = read_project_sidecar(str(source))
    config = sidecar.get("config", {})
    paths = config.get("translation_dirs", []) if isinstance(config, dict) else []
    if not isinstance(paths, list):
        raise PublicationError("invalid_project_outputs", "Project output registration is invalid")
    outputs = {}
    for raw in paths:
        if isinstance(raw, str) and raw:
            path = Path(resolve_path(raw)).absolute()
            if path.is_dir():
                reject_links(path)
                if path == source or source.is_relative_to(path) or path.is_relative_to(source):
                    raise PublicationError("source_output_overlap", "Choose an isolated translation output")
                outputs[str(path)] = {"output_folder_name": path.name, "path": str(path)}
    return list(outputs.values())


def package_files(root):
    reject_links(root)
    records, total = [], 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in [*dirs, *files]:
            path = Path(directory) / name
            reject_links(path)
            if name.casefold() in FORBIDDEN or name.casefold().startswith(".env."):
                raise PublicationError("unsafe_package", "Remove private configuration or repository files from the package")
        for name in sorted(files):
            if name in EXCLUDED:
                continue
            path = Path(directory) / name
            if not stat.S_ISREG(path.stat().st_mode):
                raise PublicationError("unsafe_package", "Only regular package files can be published")
            size = path.stat().st_size
            total += size
            if len(records) >= MAX_FILES or total > MAX_BYTES:
                raise PublicationError("package_limit", "Publication package exceeds the supported bounds")
            records.append({"path": path.relative_to(root).as_posix(), "size": size,
                            "sha256": file_hash(path)})
    if not records:
        raise PublicationError("empty_package", "The selected output package is empty")
    return sorted(records, key=lambda item: item["path"])


def file_hash(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def diagnostic_identity(root):
    result = {}
    for name in (".remis_errors.json", "workshop_issues.json"):
        path = root / name
        if not path.exists():
            continue
        reject_links(path)
        if path.stat().st_size > 16 * 1024**2:
            raise PublicationError("invalid_validation_report", "Validation report is too large")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise PublicationError("invalid_validation_report", "Validation report cannot be parsed") from exc
        issues = payload.get("issues") if isinstance(payload, dict) else payload
        if not isinstance(issues, list) or any(not isinstance(item, dict) for item in issues):
            raise PublicationError("invalid_validation_report", "Validation report has an invalid shape")
        if any(issue_is_active(item) for item in issues):
            raise PublicationError("validation_review_required", "Resolve active validation findings before publication")
        result[name] = file_hash(path)
    return result


def validate_paradox_package(project, root, files):
    from scripts.core.paradox_localization_parser import parse_text as parse_localization_text
    from scripts.utils.post_process_validator import PostProcessValidator

    game = GAME_ID_ALIASES.get(project["game_id"], project["game_id"])
    if game not in PARADOX_GAMES:
        raise PublicationError("unsupported_package", "This publication adapter currently validates Paradox YML packages")
    source = Path(resolve_path(project["source_path"]))
    validator = PostProcessValidator().get_validator_by_game_id(game)
    sources = {}
    for path in source.rglob("*.yml"):
        reject_links(path)
        report = parse_localization_text(path.read_text(encoding="utf-8-sig"))
        for entry in report.entries:
            sources.setdefault(entry.base_key, set()).add(entry.value)
    count = 0
    for record in files:
        if not record["path"].lower().endswith(".yml"):
            continue
        text = (root / record["path"]).read_text(encoding="utf-8-sig")
        report = parse_localization_text(text)
        if report.diagnostics or not report.entries:
            raise PublicationError("package_parse_failure", "A package localization file is malformed or empty")
        for entry in report.entries:
            values = sources.get(entry.base_key, set())
            if not entry.value.strip() or len(values) != 1:
                raise PublicationError("source_review_required", "Empty text, missing source, or ambiguous source keys require review")
            findings = validator.validate_entry(entry.base_key, entry.value, source_value=next(iter(values)))
            if any(not finding.is_valid and finding.level.value != "info" for finding in findings):
                raise PublicationError("package_validation_failed", "Localization validation requires review before publication")
            count += 1
    if not count:
        raise PublicationError("localization_missing", "The package has no validated localization entries")
    return {"scope": "paradox_parser_and_source_token_validation", "entry_count": count,
            "source_sha256": digest({key: sorted(values) for key, values in sources.items()}),
            "runtime_verified": False}


class WorkshopPublicationInputs:
    def __init__(self, workshop):
        self.workshop = workshop

    def inspect(self, workspace_id, project, request):
        workspace = self.workshop.get_workspace(workspace_id)
        if not project or workspace.get("project_id") != project.get("project_id"):
            raise PublicationError("project_required", "Bind this workspace to an existing project")
        if project.get("status") != "active":
            raise PublicationError("inactive_project", "The publication project must be active")
        matches = [item for item in output_options(project)
                   if item["output_folder_name"] == request["output_folder_name"]]
        if len(matches) != 1:
            raise PublicationError("output_selection_required", "Output is missing, ambiguous, or not owned by this project")
        root = Path(matches[0]["path"])
        metadata = self._metadata(workspace, request)
        files = package_files(root)
        validation = validate_paradox_package(project, root, files)
        diagnostics = diagnostic_identity(root)
        return {"request": request, "workspace_id": workspace_id,
                "project_id": project["project_id"], "source_path": project["source_path"],
                "content_path": str(root), "files": files, "diagnostics": diagnostics,
                "validation": validation, **metadata}

    def _metadata(self, workspace, request):
        published = request.get("published_file_id")
        if (request["mode"] == "create") == bool(published):
            raise PublicationError("invalid_target", "Create requires no item ID; update requires an explicit target item ID", 400)
        if published and int(published) > 2**64 - 1:
            raise PublicationError("invalid_target", "Workshop item ID exceeds uint64", 400)
        # The workspace Workshop ID may identify the original author's Mod.
        # It must never become the update target implicitly.
        cover_id, description_id = workspace.get("current_cover_version_id"), workspace.get("current_description_version_id")
        if not cover_id or not description_id:
            raise PublicationError("assets_required", "Select a cover and a description version before publication")
        cover, description = self.workshop.get_version(cover_id), self.workshop.get_version(description_id)
        for version, kind in ((cover, "cover"), (description, "description")):
            if version["workspace_id"] != workspace["workspace_id"] or version["asset_type"] != kind:
                raise PublicationError("asset_identity_mismatch", "Selected publication assets do not belong to this workspace")
        preview = self.workshop.get_cover_path(cover_id)
        reject_links(preview)
        if preview.stat().st_size >= 1024**2 or file_hash(preview) != cover["sha256"]:
            raise PublicationError("invalid_cover", "Cover must match its selected version and be smaller than 1 MiB")
        bbcode = description["bbcode"]
        if "\x00" in bbcode or len(bbcode.encode("utf-8")) >= 8000 or digest_text(bbcode) != description["sha256"]:
            raise PublicationError("invalid_description", "Description is invalid or exceeds the Steam limit")
        if len(request["title"].encode("utf-8")) >= 129:
            raise PublicationError("invalid_title", "Steam title exceeds 128 UTF-8 bytes", 400)
        if any(not tag or len(tag.encode("utf-8")) > 255 or "," in tag or not tag.isprintable()
               for tag in request["tags"]):
            raise PublicationError("invalid_tags", "Steam tags must be printable and at most 255 UTF-8 bytes", 400)
        return {"cover_version_id": cover_id, "description_version_id": description_id,
                "preview_path": str(preview), "preview_sha256": cover["sha256"],
                "description": bbcode, "description_sha256": description["sha256"]}


def digest_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
