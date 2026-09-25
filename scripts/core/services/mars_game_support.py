"""Read-only discovery reusing the existing Surviving Mars CSV parser."""
from pathlib import Path
import os
import stat

from scripts.core import surviving_mars_csv as csv_adapter
from scripts.core.game_adapters.registry import game_capabilities
from scripts.core.services.mars_lua_coverage import LuaCoverage

MAX_SCAN_FILES = 10000


def csv_contract() -> dict:
    return {
        "header": list(csv_adapter.HEADER), "optional_first_line": "sep=,", "source_column": "Text",
        "writable_column": "Translation",
        "preserved_columns": ["ID", "Text", "VoiceActor", "Context"],
        "id_policy": "ASCII decimal string; preserve leading zeros and exact identity",
        "tag_policy": "Preserve exact tag spelling, parameters, case and multiplicity",
        "newline_policy": "Preserve real CSV cell line breaks and paragraph separator runs; do not write Paradox-style literal backslash-n escapes.",
        "encoding": "UTF-8", "preserve_relative_paths": True,
        "compressed_packages_supported": False,
    }


def _linked(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def inspect_csv_support(source_path: str) -> dict:
    result = {"game_id": "surviving_mars", "capabilities": game_capabilities("surviving_mars"),
              "resources": [], "diagnostics": [], "metadata": {"scan_complete": True}}
    diagnostics = result["diagnostics"]
    root = Path(source_path)
    packed = []
    lua = LuaCoverage(root)

    def failed(exc):
        diagnostics.append({"code": "resource_discovery_error", "severity": "error", "message": str(exc)})
        result["metadata"]["scan_complete"] = False

    try:
        if _linked(root) or not root.is_dir():
            raise ValueError("Select an existing, non-linked editable Mod source directory.")
        scanned = 0
        for directory, names, files in os.walk(root, followlinks=False, onerror=failed):
            base = Path(directory)
            names[:] = sorted(name for name in names if not name.startswith(".") and not _linked(base / name))
            for name in sorted(files):
                scanned += 1
                if scanned > MAX_SCAN_FILES:
                    raise ValueError("Source scan limit reached; select a smaller Mod source directory.")
                path = base / name
                if _linked(path):
                    continue
                if path.suffix.lower() == ".fpk":
                    packed.append(path)
                if path.suffix.lower() == ".lua":
                    lua.inspect(path)
                if not csv_adapter.is_table_file(path):
                    continue
                try:
                    document = csv_adapter.parse_file(path)
                    result["resources"].append({"path": str(path), "entry_count": len(document.entries)})
                except (OSError, ValueError) as exc:
                    diagnostics.append({"code": "resource_parse_error", "severity": "error",
                                        "path": str(path), "message": str(exc)})
    except (OSError, ValueError) as exc:
        failed(exc)
    result["hardcoded_lua"] = lua.result(result["metadata"]["scan_complete"] and not packed)
    diagnostics.extend(lua.diagnostics)
    if lua.candidates:
        diagnostics.append({"code": "hardcoded_lua_outside_csv", "severity": "warning",
            "message": f"Found {len(lua.candidates)} direct Untranslated call candidates outside CSV translation coverage. Review hardcoded_lua before claiming whole-Mod completion."})
    if packed:
        diagnostics.append({"code": "compiled_package_unsupported",
            "severity": "warning" if result["resources"] else "error", "path": str(packed[0]),
            "message": "This ordinary CSV scan does not unpack FPK files. Use Create Project > Surviving Mars to prepare ModContent.fpk in isolation, or import CSV exported by the official Mod Editor."})
    if not result["resources"]:
        diagnostics.append({"code": "csv_resources_missing", "severity": "error",
            "message": "No valid ModItemLocTable CSV found. Expected header: " + ",".join(csv_adapter.HEADER)})
    return result
