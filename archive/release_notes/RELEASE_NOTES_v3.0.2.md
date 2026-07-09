# Project Remis v3.0.2

This release improves new project creation for large Paradox mods and fixes the development launcher so the app consistently uses the current source backend during testing.

## Highlights

- New project creation now lets users choose between copying a mod into Remis or using the original folder in place.
- Source paths are normalized automatically, so selecting a localization subfolder such as `TNO/localisation` still resolves to the mod root for metadata handling.
- Copy mode now imports the game-specific localization and metadata scope instead of blindly copying the whole mod folder.
- Added clearer project creation progress feedback.
- Added English, Simplified Chinese, and Russian UI strings for the new project creation controls.
- Fixed development startup so `run-dev.bat` waits for backend health before opening the frontend.
- Fixed the dev backend launcher to use the `local_factory` Python environment directly instead of depending on fragile `conda activate` state.
- Fixed stale version display by sourcing the frontend version from `package.json` and backend health version from `scripts.app_settings.VERSION`.

## Notes

- This release addresses the large-mod import issues discussed in GitHub issue #143.
- Existing projects created by older versions are not deleted or migrated automatically.
