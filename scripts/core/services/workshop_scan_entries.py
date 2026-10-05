"""Select source and target cells for the Agent Workshop validation scan."""

from pathlib import Path

from scripts.core import surviving_mars_csv
from scripts.core.loc_parser import parse_loc_file


def validation_entries(
    game_id: str,
    file_path: Path,
    fallback_source_entries: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Read paired source and translation values for the current game format."""
    if game_id == "surviving_mars" and surviving_mars_csv.is_table_file(file_path):
        source = {
            entry.key: entry.value
            for entry in surviving_mars_csv.entries(file_path, "Text")
        }
        translated = {
            entry.key: entry.value
            for entry in surviving_mars_csv.entries(file_path, "Translation")
        }
        return source, translated
    return fallback_source_entries, dict(parse_loc_file(file_path))
