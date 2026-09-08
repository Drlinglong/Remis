"""Archived ZIP-upload support for a possible future Remis cloud workflow.

The current desktop product selects a managed local folder and calls
``POST /api/translate/start``. This module only supports the deprecated
``POST /api/translate`` compatibility endpoint; it is not the active desktop
business flow.
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import BinaryIO


logger = logging.getLogger(__name__)


class TranslationArchiveUploadError(ValueError):
    """Raised when a user archive is unsafe or cannot be installed."""


@dataclass(frozen=True)
class InstalledTranslationArchive:
    mod_name: str
    source_path: str


_WINDOWS_RESERVED_DEVICE_NAMES = frozenset(
    ("CON", "PRN", "AUX", "NUL")
    + tuple(f"COM{index}" for index in range(1, 10))
    + tuple(f"LPT{index}" for index in range(1, 10))
)


def _is_reserved_windows_name(name: str) -> bool:
    """Match ``ntpath.isreserved`` on Python versions that do not provide it."""

    checker = getattr(os.path, "isreserved", None)
    if checker is not None:
        return bool(checker(name))
    if name != name.rstrip(" ."):
        return True
    if any(character in name for character in '<>:"/\\|?*'):
        return True
    if any(ord(character) < 32 for character in name):
        return True
    return name.split(".", 1)[0].upper() in _WINDOWS_RESERVED_DEVICE_NAMES


def _safe_upload_name(filename: str | None) -> tuple[str, str]:
    value = str(filename or "")
    if not value or PurePosixPath(value).name != value or PureWindowsPath(value).name != value:
        raise TranslationArchiveUploadError("Archive filename must not contain a directory path.")
    if not value.lower().endswith(".zip"):
        raise TranslationArchiveUploadError("Translation upload must be a ZIP archive.")
    mod_name = value[:-4]
    if not mod_name or mod_name in {".", ".."}:
        raise TranslationArchiveUploadError("Archive filename must include a non-empty mod name.")
    if _is_reserved_windows_name(mod_name):
        raise TranslationArchiveUploadError("Archive filename uses a reserved Windows name.")
    return value, mod_name


def _validate_members(archive: zipfile.ZipFile, staging_root: Path) -> None:
    for member in archive.infolist():
        normalized_name = member.filename.replace("\\", "/")
        member_path = PurePosixPath(normalized_name)
        if (
            member_path.is_absolute()
            or PureWindowsPath(member.filename).drive
            or ".." in member_path.parts
        ):
            raise TranslationArchiveUploadError(
                f"Archive member escapes the staging directory: {member.filename}"
            )
        mode = member.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise TranslationArchiveUploadError(
                f"Archive member is a symbolic link: {member.filename}"
            )
        candidate = (staging_root / Path(*member_path.parts)).resolve()
        if os.path.commonpath([candidate, staging_root]) != str(staging_root):
            raise TranslationArchiveUploadError(
                f"Archive member escapes the staging directory: {member.filename}"
            )


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def install_translation_archive(
    upload_stream: BinaryIO,
    filename: str | None,
    source_root: str | os.PathLike[str],
) -> InstalledTranslationArchive:
    """Validate an uploaded ZIP completely, then atomically replace its mod directory."""

    archive_name, mod_name = _safe_upload_name(filename)
    root = Path(source_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = (root / mod_name).resolve()
    if os.path.commonpath([target, root]) != str(root) or target == root:
        raise TranslationArchiveUploadError("Archive destination is outside the source directory.")

    archive_path: Path | None = None
    staging = Path(tempfile.mkdtemp(prefix=".remis-upload-", dir=root)).resolve()
    backup = root / f".remis-upload-backup-{uuid.uuid4().hex}"
    target_was_moved = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix="remis-upload-", suffix=".zip", delete=False
        ) as archive_file:
            archive_path = Path(archive_file.name)
            shutil.copyfileobj(upload_stream, archive_file)
        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                _validate_members(archive, staging)
                archive.extractall(staging)
        except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
            raise TranslationArchiveUploadError(f"Invalid ZIP archive: {archive_name}") from exc

        extracted = list(staging.iterdir())
        if not extracted:
            raise TranslationArchiveUploadError("Translation archive is empty.")
        payload = extracted[0] if len(extracted) == 1 and extracted[0].is_dir() else staging

        if target.exists() or target.is_symlink():
            os.replace(target, backup)
            target_was_moved = True
        try:
            os.replace(payload, target)
        except Exception:
            if target_was_moved and backup.exists() and not target.exists():
                os.replace(backup, target)
                target_was_moved = False
            raise
        if target_was_moved:
            target_was_moved = False
            try:
                _remove_path(backup)
            except OSError:
                logger.warning("Could not remove translation upload backup: %s", backup)
        return InstalledTranslationArchive(mod_name=mod_name, source_path=str(target))
    finally:
        if target_was_moved and backup.exists() and not target.exists():
            os.replace(backup, target)
        if backup.exists() or backup.is_symlink():
            logger.warning("Leaving translation upload backup after failed cleanup: %s", backup)
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if archive_path is not None:
            archive_path.unlink(missing_ok=True)
