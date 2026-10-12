"""Preserve canonical syntax diagnostics at file-validation boundaries."""

from scripts.core.loc_parser import parse_loc_file_report, parse_loc_file_with_lines
from scripts.core import surviving_mars_csv
from scripts.utils.validation_results import ValidationResult, ValidationLevel


def read_validation_entries(path):
    if surviving_mars_csv.is_table_file(path):
        return [entry.as_legacy_tuple() for entry in surviving_mars_csv.entries(path, "Translation")], []
    report = parse_loc_file_report(path)
    entries = [entry.as_legacy_tuple() for entry in report.eligible_entries]
    if path.suffix.lower() == ".json" and not report.entries:
        entries = parse_loc_file_with_lines(path)
    issues = [
        ValidationResult(
            is_valid=False, level=ValidationLevel.ERROR,
            message=diagnostic.message, code=diagnostic.code,
            line_number=diagnostic.line_number, key=diagnostic.key,
            text_sample=report.source_text.splitlines()[diagnostic.line_number - 1],
        )
        for diagnostic in report.diagnostics
    ]
    return entries, issues
