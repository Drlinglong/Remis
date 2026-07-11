# Release Build Script Guide (`build_release.bat`)

## Overview

`build_release.bat` is a script used to automate the building of the Project Remis portable release package. It is responsible for cleaning up old build files, creating a new directory structure, embedding the Python environment, copying project source code, downloading and packaging all dependencies, and finally generating a distributable ZIP archive.

## Features

*   **Automated Build**: One-click completion of the portable release package build process.
*   **Environment Isolation**: Packages the Python runtime environment and all dependencies into the release package, eliminating the need for users to manually install Python or configure the environment.
*   **Dependency Management**: Automatically downloads all Python dependencies defined in `requirements.txt` and places them in the `packages` directory.
*   **Structured Output**: Generates a release package that conforms to the Project Remis portable directory structure.
*   **Optional Compression**: If 7-Zip is installed on the system, the script will automatically compress the generated release directory into a ZIP file.

## Release Notes Standard

Every release note must be written for ordinary users first and technical readers second.

1. Begin both the English and Chinese sections with a short `Highlights` / `重点` section.
2. Use two to five plain-language bullets to answer: What is new? What improved? What was removed or changed? Does the user need to take any action?
3. Keep file names, function names, issue numbers, internal architecture, test commands, and other implementation details out of the opening highlights.
4. Preserve those implementation details below under `Technical Details` / `技术细节`, followed by compatibility and validation information where applicable.
5. Keep the English and Chinese summaries equivalent in meaning, even when their wording is adapted for readability.

Recommended structure:

```markdown
## English

## Highlights

- **New or improved:** ...
- **Removed or changed:** ...

## Technical Details

...

## 中文

## 重点

- **新增或改进：**……
- **移除或变更：**……

## 技术细节

……
```

## Usage

### Prerequisites

1.  **Conda Environment**: The script assumes it is run within an activated Conda/Python environment. Please ensure Conda is installed on your system and that the `CONDA_ROOT` and `ENV_NAME` variables are correctly configured in the script.
2.  **7-Zip (Optional)**: If you want the script to automatically generate a ZIP archive, please ensure 7-Zip is installed on your system and its executable (`7z.exe`) is in the system PATH or a default path the script can find.
3.  **Python Embeddable Package**: Ensure that the `python-3.10.11-embed-amd64.zip` file exists in the `archive/build_release_scripts/` directory.

### Running the Script

1.  **Activate Conda Environment**:
    Open a command-line tool (e.g., Anaconda Prompt) and activate the Conda environment you are using for building:
    ```bash
    conda activate your_env_name
    ```
    (Please replace `your_env_name` with the environment name defined in the script's `ENV_NAME` variable)

2.  **Execute the Build Script**:
    Navigate to the `archive/build_release_scripts/` directory, then run `build_release.bat`:
    ```bash
    cd J:\V3_Mod_Localization_Factory\archive\build_release_scripts\
    build_release.bat
    ```

3.  **Wait for Completion**:
    The script will automatically execute all build steps. Detailed log information will be output during the process. Please wait patiently until the script displays `[SUCCESS] Build process completed!`.

## Script Configuration

You can modify the following variables at the beginning of the `build_release.bat` script:

*   `CONDA_ROOT`: Your Conda installation root directory.
*   `ENV_NAME`: The name of the Conda environment used for building.
*   `PROJECT_NAME`: Project name (defaults to `Project_Remis`).
*   `VERSION`: Release version number (defaults to `1.1.0`).

## Build Process Overview

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

## Troubleshooting

*   **`tar` command not found**: Ensure `tar` is installed on your system, or manually extract `python-3.10.11-embed-amd64.zip`.
*   **`python.exe` not found**: Check if `python-3.10.11-embed-amd64.zip` is corrupted or if the path is correct.
*   **`pip download` failed**: Check the `pip_log.txt` file for detailed error messages, ensure network connectivity, and that the Conda environment is correctly activated.
*   **`7z.exe` not found**: If 7-Zip is not installed, the script will skip the automatic compression step, and you will need to manually compress the release directory.

---
