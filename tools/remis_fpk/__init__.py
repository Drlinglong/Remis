"""Bounded reader and extractor for the observed Surviving Mars FLPK profile."""

from .reader import ArchiveError, ArchiveLimits, inspect_archive
from .extraction import extract_archive

FpkError = ArchiveError

__all__ = ["ArchiveError", "ArchiveLimits", "FpkError", "inspect_archive", "extract_archive"]
