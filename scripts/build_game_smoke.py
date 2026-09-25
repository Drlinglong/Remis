"""Inspect packaged game adapter modules before release runtime checks."""

REQUIRED_FROZEN_GAME_ADAPTER_MODULES = (
    "scripts.core.game_adapters.project_zomboid",
    "scripts.core.game_adapters.rimworld",
    "scripts.core.game_adapters.rimworld_text",
    "scripts.core.game_adapters.rimworld_xml",
)

def verify_frozen_game_adapter_modules(executable):
    """Fail packaging if registry-discovered adapters are absent from the PYZ."""
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader

    archive = CArchiveReader(executable)
    pyz_entry = archive.toc.get("PYZ.pyz")
    if not pyz_entry:
        raise RuntimeError("Packaged backend does not contain a PYZ module archive.")

    pyz = ZlibArchiveReader(
        executable,
        start_offset=archive._start_offset + pyz_entry[0],
    )
    missing = sorted(set(REQUIRED_FROZEN_GAME_ADAPTER_MODULES) - pyz.toc.keys())
    if missing:
        raise RuntimeError(
            "Packaged backend is missing game adapter modules: " + ", ".join(missing)
        )
    print("[SUCCESS] Packaged backend contains all registry game adapter modules.")
