# Release Build Guide (Tauri EXE and legacy portable ZIP)

## Overview

The formal release path for the 3.2.0 Windows application is the Tauri NSIS
installer built by `scripts/build_pipeline.py`. The older
`archive/build_release_scripts/build_release.bat` remains only for the
historical portable ZIP format and must not be used to produce the current EXE
release.

## Features

*   **Automated Build**: The current pipeline freezes the backend, builds the React frontend, and creates the Tauri Windows installer.
*   **Channel Isolation**: Stable and Agent Preview builds use separate application identities, ports, and data directories.
*   **Dependency Management**: CI installs the locked frontend and website dependency trees before running audits, tests, lint, and production builds.
*   **Structured Output**: Produces a versioned Windows NSIS installer in the release archive.
*   **Legacy Portable ZIP**: The archived batch script can still create the older ZIP format when that format is specifically required.

## Release Notes Standard

Every release note must be written for ordinary users first and technical readers second.

1. Begin both the English and Chinese sections with `Highlights` / `主要更新`.
2. Reserve that section for important user-visible changes: a significant new
   capability, a major workflow or UI/UX/HCI change, a major change in how Remis
   is used, or a change that may affect an existing project or require action.
3. Write Highlights so a non-developer can understand them without knowing
   implementation terms. Describe outcomes—for example, that Workshop preview
   accurately reproduces links, lists, and separators—not parser internals.
4. Keep refactors, filenames, functions, issues, architecture, test commands,
   security implementation, and similarly technical material under
   `Engineering quality and reliability` / `工程质量与可靠性` below Highlights.
5. Add compatibility, known boundaries, validation, and installer sections as
   needed. Keep English and Chinese equivalent in meaning while writing each
   naturally.
6. Update `releaseDate` in `scripts/react-ui/package.json`, use the same date in
   the release note's `Released on YYYY-MM-DD.` line, and confirm Settings >
   Version Info > Last Updated displays it. The release metadata test is a
   mandatory pre-package gate.

Recommended structure:

```markdown
## English

## Highlights

- **New or improved:** ...
- **Removed or changed:** ...

## Engineering quality and reliability

...

## 中文

## 主要更新

- **新增或改进：**……
- **移除或变更：**……

## 工程质量与可靠性

……
```

Before packaging, run:

```powershell
python -m pytest -q tests/test_release_metadata.py
```

The canonical and complete convention is maintained in
`archive/release_notes/README.md`.

## Usage

## Tauri installer data policy for the 3.2.0 desktop release

The current Tauri installer is built by `scripts/build_pipeline.py`. First-run
database setup has three layers:

1. The user's AppData database stores local projects, tasks, Model Arena
   history, and user glossaries. Release builds are forbidden from reading it.
2. `assets/skeleton.sqlite` is the checked-in, reviewable release input. The
   build exports only the default glossary data plus the three approved demo
   projects, their file index, and their glossary bindings.
3. On first launch, `scripts/core/db_initializer.py` creates the current schema
   and imports the generated `seed_data_main.sql` and
   `seed_data_projects.sql`.

The only demo projects allowed in an installer are:

- `Project Remis - Demo Mod -EU5`
- `Project Remis - Demo Mod - Stellaris`
- `蕾姆丝计划 - 演示Mod - 维多利亚3`

The build also checks `assets/mods_cache_skeleton.sqlite` and requires it to
contain exactly the same three demos. Extra or missing projects fail the build.
Activity logs, project history, watch snapshots, background tasks, and Model
Arena history are never exported into first-run seed SQL.

To add a future demo, update the `DEMO_PROJECTS` allowlist in
`scripts/utils/export_seed_data.py`, then explicitly run:

```powershell
python scripts\db\generate_skeleton.py --from-development
```

That command overwrites checked-in release assets and therefore requires a
database diff and test review before commit. Normal release builds never run it.

### Building the current stable EXE

Run these commands from the repository root after the release candidate has
passed review:

```powershell
python -m pytest -q tests/test_release_metadata.py
python scripts/build_pipeline.py --channel stable
```

The pipeline uses the `local_factory` Conda environment, freezes and health-
checks the Python sidecar, builds the frontend, and then runs the Tauri build.
The stable NSIS installer is copied to
`archive/release/stable/remis-mod-factory_3.2.0_x64-setup.exe`. Use
`--channel agent-preview` only when intentionally producing the isolated
`3.2.0-agent-preview.1` preview installer.

### Legacy portable ZIP (`build_release.bat`)

The following prerequisites and steps apply only to the historical portable
ZIP script. They are not part of the current Tauri EXE release process.

#### Prerequisites

1.  **Conda Environment**: The script assumes it is run within an activated Conda/Python environment. Please ensure Conda is installed on your system and that the `CONDA_ROOT` and `ENV_NAME` variables are correctly configured in the script.
2.  **7-Zip (Optional)**: If you want the script to automatically generate a ZIP archive, please ensure 7-Zip is installed on your system and its executable (`7z.exe`) is in the system PATH or a default path the script can find.
3.  **Python Embeddable Package**: Ensure that the `python-3.10.11-embed-amd64.zip` file exists in the `archive/build_release_scripts/` directory.

#### Running the Legacy Script

1.  **Activate Conda Environment**:
    Open a command-line tool (e.g., Anaconda Prompt) and activate the Conda environment you are using for building:
    ```bash
    conda activate your_env_name
    ```
    (Please replace `your_env_name` with the environment name defined in the script's `ENV_NAME` variable)

2.  **Execute the Legacy Script**:
    Navigate to the `archive/build_release_scripts/` directory, then run `build_release.bat` only when a portable ZIP is explicitly required:
    ```bash
    cd J:\V3_Mod_Localization_Factory\archive\build_release_scripts\
    build_release.bat
    ```

3.  **Wait for Completion**:
    The script will automatically execute all build steps. Detailed log information will be output during the process. Please wait patiently until the script displays `[SUCCESS] Build process completed!`.

#### Legacy Script Configuration

You can modify the following variables at the beginning of the `build_release.bat` script:

*   `CONDA_ROOT`: Your Conda installation root directory.
*   `ENV_NAME`: The name of the Conda environment used for building.
*   `PROJECT_NAME`: Project name (defaults to `Project_Remis`).
*   `VERSION`: Release version number (defaults to `1.1.0`).

#### Legacy Portable ZIP Process

1.  **Initialization**: Determine the project root directory, release directory name, and path.
2.  **Cleanup**: Delete the previously generated release directory (if it exists).
3.  **Scaffolding**: Create the new release directory structure (`app`, `packages`, `python-embed`).
4.  **Python Embedding**: Extract the embeddable Python environment from the ZIP package to the `python-embed` directory.
5.  **Copy Source Code**: Copy source code to the `app` directory. The `scripts` directory is copied using `robocopy` to specifically exclude development-related subdirectories such as `__pycache__`, `.vscode`, `node_modules`, `src`, and `.vite`, ensuring a smaller package size. Other necessary files like `data`, `docs`, `requirements.txt`, etc., are also copied.
6.  **Create Empty Directories**: Create necessary empty directories like `logs`, `my_translation`, `source_mod` under the `app` directory.
7.  **Copy Installation Scripts**: Copy `setup.bat` and `get-pip.py` to the release directory and embeddable Python directory.
8.  **Activate Conda Environment**: Activate the specified Conda environment to execute the `pip download` command.
9.  **Package Dependencies**: Use the `pip download` command to download all dependencies defined in `requirements.txt` to the `packages` directory of the release package.
10. **Copy Run Script**: Copy `run.bat` to the release directory.
11. **Final Packaging (Optional)**: If 7-Zip is detected, the entire release directory will be compressed into a ZIP file.

#### Legacy ZIP Troubleshooting

*   **`tar` command not found**: Ensure `tar` is installed on your system, or manually extract `python-3.10.11-embed-amd64.zip`.
*   **`python.exe` not found**: Check if `python-3.10.11-embed-amd64.zip` is corrupted or if the path is correct.
*   **`pip download` failed**: Check the `pip_log.txt` file for detailed error messages, ensure network connectivity, and that the Conda environment is correctly activated.
*   **`7z.exe` not found**: If 7-Zip is not installed, the script will skip the automatic compression step, and you will need to manually compress the release directory.

---
