import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

from scripts.core import file_parser
from scripts.core.archive_manager import archive_manager
from scripts.shared.services import project_manager
from scripts.app_settings import CHUNK_SIZE, OLLAMA_CHUNK_SIZE


@dataclass(frozen=True)
class SourceFileIssue:
    filename: str
    code: str
    line_number: Optional[int]
    key: Optional[str]
    recoverable: bool
    action: str

    def log_message(self) -> str:
        location = self.filename
        if self.line_number:
            location = f"{location}:{self.line_number}"
        key_suffix = f" key={self.key}" if self.key else ""
        return f"SOURCE ERROR: {location} {self.code}{key_suffix}; action={self.action}"


@dataclass
class SourceReadResult:
    files: List[dict] = field(default_factory=list)
    issues: List[SourceFileIssue] = field(default_factory=list)

    @property
    def recovered_entry_count(self) -> int:
        return sum(1 for issue in self.issues if issue.recoverable)

    @property
    def dropped_file_count(self) -> int:
        return len({issue.filename for issue in self.issues if not issue.recoverable})


def read_files_for_backup(
    all_file_paths: List[dict],
    total_files: int,
    progress_callback: Optional[Any] = None,
) -> SourceReadResult:
    """Read source files once and attach parsed content for backup and translation."""
    logging.info("Reading all source files for backup...")
    result = SourceReadResult()

    for idx, file_info in enumerate(all_file_paths):
        file_path = file_info["path"]
        if progress_callback:
            progress_callback(idx, total_files, file_info["filename"], "Reading Source")
        try:
            original_lines, texts_to_translate, key_map, diagnostics = (
                file_parser.extract_translatable_content_with_diagnostics(file_path)
            )
        except Exception as e:
            logging.error(f"Failed to parse file {file_path} for backup: {e}")
            issue = SourceFileIssue(
                filename=file_info["filename"],
                code="source_read_error",
                line_number=None,
                key=None,
                recoverable=False,
                action="drop_file",
            )
            result.issues.append(issue)
            if progress_callback:
                progress_callback(
                    idx,
                    total_files,
                    file_info["filename"],
                    "Reading Source",
                    log_message=issue.log_message(),
                )
            continue

        if diagnostics and any(not diagnostic.recoverable for diagnostic in diagnostics):
            for diagnostic in diagnostics:
                issue = SourceFileIssue(
                    filename=file_info["filename"],
                    code=diagnostic.code,
                    line_number=diagnostic.line_number,
                    key=diagnostic.key,
                    recoverable=False,
                    action="drop_file",
                )
                result.issues.append(issue)
                logging.error(issue.log_message())
                if progress_callback:
                    progress_callback(
                        idx,
                        total_files,
                        file_info["filename"],
                        "Reading Source",
                        log_message=issue.log_message(),
                    )
            continue

        recovered_entries = []
        for diagnostic in diagnostics:
            issue = SourceFileIssue(
                filename=file_info["filename"],
                code=diagnostic.code,
                line_number=diagnostic.line_number,
                key=diagnostic.key,
                recoverable=True,
                action="empty_value",
            )
            result.issues.append(issue)
            logging.warning(issue.log_message())
            recovered_entries.append({
                "key_part": diagnostic.key,
                "line_num": diagnostic.line_number - 1,
                "line_number": diagnostic.line_number,
                "code": diagnostic.code,
                "recoverable": True,
                "opening_quote_offset": diagnostic.opening_quote_offset,
                "line_end_offset": diagnostic.line_end_offset,
                "diagnostic": diagnostic,
            })
            if progress_callback:
                progress_callback(
                    idx,
                    total_files,
                    file_info["filename"],
                    "Reading Source",
                    log_message=issue.log_message(),
                )

        parsed_file = dict(file_info)
        parsed_file["original_lines"] = original_lines
        parsed_file["texts_to_translate"] = texts_to_translate
        parsed_file["key_map"] = key_map
        parsed_file["recovered_entries"] = recovered_entries
        archive_texts = list(texts_to_translate)
        archive_key_map = dict(key_map)
        for recovered in recovered_entries:
            archive_index = len(archive_texts)
            archive_texts.append("")
            archive_key_map[archive_index] = recovered
        parsed_file["archive_texts"] = archive_texts
        parsed_file["archive_key_map"] = archive_key_map
        result.files.append(parsed_file)

    return result


def get_chunk_size_for_provider(selected_provider: str, batch_size_limit: Optional[int] = None) -> int:
    if batch_size_limit:
        return max(1, int(batch_size_limit))
    if selected_provider == "ollama":
        return OLLAMA_CHUNK_SIZE
    return CHUNK_SIZE


def calculate_total_batches(all_files_content: List[dict], chunk_size: int) -> int:
    total_batches = 0
    for file_data in all_files_content:
        texts_to_translate = file_data.get("texts_to_translate", [])
        if not texts_to_translate:
            continue
        total_batches += (len(texts_to_translate) + chunk_size - 1) // chunk_size
    return total_batches


def resolve_archive_mod_name(mod_name: str, project_id: Optional[str] = None) -> str:
    archive_mod_name = mod_name
    if not project_id:
        return archive_mod_name

    try:
        project = asyncio.run(project_manager.get_project(project_id))
        if project:
            archive_mod_name = project["name"]
    except Exception as e:
        logging.error(f"Failed to fetch project name for archive: {e}")

    return archive_mod_name


def create_source_snapshot(
    mod_name: str,
    all_files_content: List[dict],
    total_files: int,
    total_batches: int,
    progress_callback: Optional[Any] = None,
    project_id: Optional[str] = None,
):
    archive_mod_name = resolve_archive_mod_name(mod_name, project_id)
    mod_id = archive_manager.get_or_create_mod_entry(archive_mod_name, f"local_{mod_name}")
    if not mod_id:
        logging.error("Failed to get/create mod entry in database. Aborting.")
        return None, None

    logging.info("Creating source version snapshot...")
    if progress_callback:
        progress_callback(0, total_files, "", "Creating Backup", total_batches=total_batches)

    version_id = archive_manager.create_source_version(mod_id, all_files_content)
    if not version_id:
        logging.error("Failed to create source version snapshot. Aborting workflow to prevent data loss.")
        return mod_id, None

    logging.info(f"Source snapshot created successfully (Version ID: {version_id}). Proceeding to translation.")
    return mod_id, version_id
